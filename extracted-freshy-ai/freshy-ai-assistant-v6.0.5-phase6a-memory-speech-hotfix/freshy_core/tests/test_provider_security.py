import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.openai_compatible_provider import OpenAICompatibleProvider
from ai.provider_router import ProviderRouter
from ai.schemas import ChatMessage


class ErrorSession:
    def post(self, *args, **kwargs):
        raise RuntimeError("Authorization: Bearer super-secret-token")


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


class RecordingSession:
    def __init__(self):
        self.kwargs = None

    def post(self, *args, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class ProviderSecurityTests(unittest.TestCase):
    def test_provider_error_redacts_bearer_token(self):
        provider = OpenAICompatibleProvider(
            name="groq",
            base_url="https://api.example.com/v1",
            api_key="super-secret-token",
            model_name="model",
            session=ErrorSession(),
        )
        result = provider.generate([ChatMessage(role="user", content="hello")])
        self.assertFalse(result.success)
        self.assertNotIn("super-secret-token", result.error_message or "")
        self.assertIn("REDACTED", result.error_message or "")


    def test_provider_agnostic_tool_history_is_sent_as_user_context(self):
        session = RecordingSession()
        provider = OpenAICompatibleProvider(
            name="groq",
            base_url="https://api.example.com/v1",
            api_key="configured-key",
            model_name="model",
            session=session,
        )
        result = provider.generate([
            ChatMessage(role="user", content="Do the safe action"),
            ChatMessage(role="tool", content="[TOOL_RESULT] success=True"),
        ])
        self.assertTrue(result.success)
        messages = session.kwargs["json"]["messages"]
        self.assertEqual(messages[-1]["role"], "user")
        self.assertIn("TOOL_RESULT", messages[-1]["content"])

    def test_router_status_contains_no_api_key_field_or_value(self):
        provider = OpenAICompatibleProvider(
            name="groq",
            base_url="https://api.example.com/v1",
            api_key="secret-status-key",
            model_name="model",
        )
        status = ProviderRouter(
            providers=[provider], provider_order=["groq"]
        ).status()
        rendered = str(status)
        self.assertNotIn("secret-status-key", rendered)
        self.assertNotIn("api_key", rendered.lower())


if __name__ == "__main__":
    unittest.main()
