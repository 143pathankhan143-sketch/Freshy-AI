import asyncio
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main
from ai.assistant_orchestrator import AssistantOrchestrator
from ai.conversation_store import ConversationStore
from ai.provider_base import BaseAIProvider
from ai.provider_router import ProviderRouter
from ai.schemas import AssistantResponse, ChatRequest, ProviderResponse, ToolRequest, ToolResult
from ai.web_search_service import WebSearchService
from live.tool_bridge import LiveToolBridge
from tools.registry import ToolRegistry


class QueueProvider(BaseAIProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

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
        del messages, system_instruction, tools
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]


class NoSearch(WebSearchService):
    def __init__(self):
        self.last_error = None

    def is_configured(self):
        return False

    def search(self, query):
        del query
        return []


class CaptureTTS:
    def __init__(self):
        self.spoken = []

    def speak(self, text, prepared_token=None):
        del prepared_token
        self.spoken.append(text)
        return {"accepted": True, "reason": "captured"}


class RawRegistry:
    def list_tools(self):
        return []

    def execute_tool(self, name, args):
        del name, args
        return ToolResult(
            success=True,
            output="Opening https://www.google.com in your default browser.",
            error=None,
            metadata={"action_executed": True, "url": "https://www.google.com"},
        )


class ActionSpeechTests(unittest.TestCase):
    def build_orchestrator(self, provider):
        search = NoSearch()
        return AssistantOrchestrator(
            provider_router=ProviderRouter(
                providers=[provider],
                provider_order=["groq"],
                max_retries=0,
                sleep_fn=lambda _: None,
            ),
            conversation_store=ConversationStore(max_messages=16, max_characters=24000),
            search_service=search,
            tool_registry=ToolRegistry(search_service=search),
            max_input_characters=1000,
            web_search_enabled=False,
        )

    def test_local_open_google_keeps_url_in_chat_but_not_in_speech(self):
        provider = QueueProvider([
            ProviderResponse(
                content="unused",
                provider_name="groq",
                model_name="test-model",
                success=True,
            )
        ])
        orchestrator = self.build_orchestrator(provider)
        with patch("webbrowser.open", return_value=True):
            result = orchestrator.handle_request(ChatRequest(message="Open Google"))
        self.assertTrue(result.action_executed)
        self.assertIn("https://", result.reply)
        self.assertEqual(result.speech_text, "Google is open.")
        self.assertNotIn("http", result.speech_text.lower())
        self.assertEqual(provider.calls, 0)

    def test_provider_tool_action_uses_fixed_url_free_speech(self):
        provider = QueueProvider([
            ProviderResponse(
                content="",
                tool_calls=[
                    ToolRequest(
                        name="open_website",
                        arguments={"url": "https://www.google.com"},
                    )
                ],
                provider_name="groq",
                model_name="test-model",
                success=True,
            ),
            ProviderResponse(
                content="I opened https://www.google.com in your browser.",
                provider_name="groq",
                model_name="test-model",
                success=True,
            ),
        ])
        orchestrator = self.build_orchestrator(provider)
        with patch("webbrowser.open", return_value=True):
            result = orchestrator.handle_request(
                ChatRequest(message="Could you visit Google for me?", session_id="tool-speech")
            )
        self.assertTrue(result.action_executed)
        self.assertEqual(result.speech_text, "Google is open.")
        self.assertNotIn("http", result.speech_text.lower())

    def test_api_tts_uses_speech_text_instead_of_display_reply(self):
        capture = CaptureTTS()
        response = AssistantResponse(
            reply="Opening https://www.google.com in your default browser.",
            speech_text="Google is open.",
            intent="open_website",
            action="open_website",
            action_executed=True,
            success=True,
            provider="local",
            tts_requested=True,
        )
        with patch.object(main, "get_tts_service", return_value=capture):
            mapped = main._assistant_response_to_chat_response(response)
        self.assertEqual(mapped.reply, response.reply)
        self.assertEqual(capture.spoken, ["Google is open."])
        self.assertNotIn("http", capture.spoken[0].lower())

    def test_gemini_live_tool_payload_hides_raw_url(self):
        bridge = LiveToolBridge(registry=RawRegistry())

        class Call:
            id = "website-1"
            name = "open_website"
            args = {"url": "https://www.google.com"}

        result = asyncio.run(bridge.execute(Call()))
        payload = result["response"]
        self.assertTrue(payload["success"])
        self.assertEqual(payload["output"], "Google is open.")
        self.assertNotIn("http", payload["output"].lower())
        self.assertIsNone(payload["error"])


if __name__ == "__main__":
    unittest.main()
