import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.assistant_orchestrator import AssistantOrchestrator
from ai.conversation_store import ConversationStore
from ai.provider_base import BaseAIProvider
from ai.provider_router import ProviderRouter
from ai.schemas import ProviderResponse, SearchResult, ToolRequest
from tools.registry import ToolRegistry


class QueueProvider(BaseAIProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.messages_seen = []
        self.tools_seen = []

    @property
    def provider_name(self):
        return "groq"

    @property
    def model_name(self):
        return "test-model"

    def is_configured(self):
        return True

    def supports_tools(self):
        return True

    def health_check(self):
        return True

    def normalize_error(self, exc):
        return "unknown_provider_error"

    def generate(self, messages, system_instruction=None, tools=None):
        self.messages_seen.append(list(messages))
        self.tools_seen.append(tools)
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]


def provider_response(content="answer", tool_calls=None, success=True, code=None):
    return ProviderResponse(
        content=content if success else None,
        tool_calls=tool_calls or [],
        provider_name="groq",
        model_name="test-model",
        success=success,
        error_code=code,
    )


class FakeSearch:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = 0
        self.last_error = None

    def is_configured(self):
        return True

    def search(self, query):
        self.calls += 1
        return self.results


class AssistantOrchestratorTests(unittest.TestCase):
    def build(self, provider, search=None):
        search = search or FakeSearch()
        router = ProviderRouter(
            providers=[provider],
            provider_order=["groq"],
            max_retries=0,
            sleep_fn=lambda _: None,
        )
        store = ConversationStore(max_messages=16, max_characters=24000)
        return AssistantOrchestrator(
            provider_router=router,
            conversation_store=store,
            search_service=search,
            tool_registry=ToolRegistry(search_service=search),
            max_input_characters=1000,
            web_search_enabled=True,
        )

    def test_local_command_uses_zero_ai_providers(self):
        provider = QueueProvider([provider_response()])
        orchestrator = self.build(provider)
        with patch("subprocess.Popen"):
            result = orchestrator.handle_request(
                __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                    message="Open Notepad"
                )
            )
        self.assertEqual(provider.calls, 0)
        self.assertEqual(result.provider, "local")
        self.assertTrue(result.action_executed)

    def test_general_question_uses_primary_provider(self):
        provider = QueueProvider([provider_response("Flutter Provider explanation")])
        result = self.build(provider).handle_request(
            __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                message="Explain Flutter Provider", session_id="one"
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "groq")
        self.assertEqual(provider.calls, 1)
        self.assertIsNone(provider.tools_seen[0])

    def test_short_typed_greeting_never_reaches_provider(self):
        provider = QueueProvider([provider_response("unused")])
        result = self.build(provider).handle_request(
            __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                message="hy", session_id="short-greeting"
            )
        )
        self.assertEqual(provider.calls, 0)
        self.assertEqual(result.provider, "local")
        self.assertNotIn("<function", result.reply.lower())

    def test_current_information_uses_search_but_timeless_question_does_not(self):
        source = SearchResult(
            title="Official release", url="https://example.com/release", content="Version facts"
        )
        provider = QueueProvider([provider_response("Grounded answer"), provider_response("Timeless")])
        search = FakeSearch([source])
        orchestrator = self.build(provider, search)
        current = orchestrator.handle_request(
            __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                message="What is the latest Flutter stable version?", session_id="a"
            )
        )
        timeless = orchestrator.handle_request(
            __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                message="Explain dependency injection", session_id="b"
            )
        )
        self.assertTrue(current.used_web_search)
        self.assertEqual(current.sources[0]["title"], "Official release")
        self.assertFalse(timeless.used_web_search)
        self.assertEqual(search.calls, 1)

    def test_nested_text_tool_call_parses_and_executes_once(self):
        call_text = '[TOOL_CALL] {"name":"open_application","arguments":{"app_name":"notepad"}}'
        provider = QueueProvider([
            provider_response(call_text),
            provider_response("Notepad request completed."),
        ])
        orchestrator = self.build(provider)
        with patch("platform.system", return_value="Windows"), patch("subprocess.Popen") as popen:
            result = orchestrator.handle_request(
                __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                    message="Please launch the allowed editor", session_id="tool"
                )
            )
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(result.tool_used, "open_application")
        self.assertTrue(result.action_executed)

    def test_xml_tool_markup_is_hidden_and_not_executed_without_permission(self):
        provider = QueueProvider([
            provider_response(
                'Bilkul, main madad karta hoon. '
                '<function=open_application>{"app_name":"calculator"}</function>'
            )
        ])
        orchestrator = self.build(provider)
        with patch("subprocess.Popen") as popen:
            result = orchestrator.handle_request(
                __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                    message="Tell me something interesting", session_id="no-tool-leak"
                )
            )
        self.assertEqual(popen.call_count, 0)
        self.assertIsNone(result.tool_used)
        self.assertNotIn("<function", result.reply.lower())
        self.assertEqual(result.reply, "Bilkul, main madad karta hoon.")

    def test_xml_tool_call_executes_for_explicit_action_only(self):
        provider = QueueProvider([
            provider_response(
                '<function=open_application>{"app_name":"notepad"}</function>'
            ),
            provider_response("Notepad request completed."),
        ])
        orchestrator = self.build(provider)
        with patch("platform.system", return_value="Windows"), patch("subprocess.Popen") as popen:
            result = orchestrator.handle_request(
                __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                    message="Please launch the allowed editor", session_id="xml-tool"
                )
            )
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(result.tool_used, "open_application")
        self.assertNotIn("<function", result.reply.lower())

    def test_failed_tool_is_never_reported_as_successful_execution(self):
        provider = QueueProvider([
            provider_response(
                "",
                [ToolRequest(name="open_application", arguments={"app_name": "powershell"})],
            ),
            provider_response("The request was blocked."),
        ])
        result = self.build(provider).handle_request(
            __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                message="Try an unsafe app", session_id="unsafe"
            )
        )
        self.assertFalse(result.success)
        self.assertFalse(result.action_executed)
        self.assertEqual(result.error_code, "tool_failed")

    def test_same_session_history_is_sent_to_provider(self):
        provider = QueueProvider([
            provider_response("Widgets are reusable UI building blocks."),
            provider_response("Here is a follow-up example."),
        ])
        orchestrator = self.build(provider)
        ChatRequest = __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest
        orchestrator.handle_request(
            ChatRequest(message="Explain Flutter widgets.", session_id="history")
        )
        orchestrator.handle_request(
            ChatRequest(message="Give me a short example.", session_id="history")
        )
        second_messages = provider.messages_seen[1]
        joined = " ".join(item.content for item in second_messages)
        self.assertIn("Explain Flutter widgets", joined)
        self.assertIn("Widgets are reusable UI building blocks", joined)


    def test_unconfigured_ai_does_not_consume_web_search(self):
        provider = QueueProvider([provider_response()])
        provider.is_configured = lambda: False
        search = FakeSearch([
            SearchResult(title="Unused", url="https://example.com", content="Unused")
        ])
        result = self.build(provider, search).handle_request(
            __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(
                message="What is the latest Flutter version?"
            )
        )
        self.assertFalse(result.success)
        self.assertEqual(result.provider, "none")
        self.assertEqual(provider.calls, 0)
        self.assertEqual(search.calls, 0)

    def test_oversized_input_is_rejected_without_provider_call(self):
        provider = QueueProvider([provider_response()])
        result = self.build(provider).handle_request(
            __import__("ai.schemas", fromlist=["ChatRequest"]).ChatRequest(message="x" * 1001)
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "input_too_large")
        self.assertEqual(provider.calls, 0)


if __name__ == "__main__":
    unittest.main()
