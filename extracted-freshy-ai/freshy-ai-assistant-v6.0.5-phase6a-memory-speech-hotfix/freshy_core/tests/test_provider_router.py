import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.provider_base import BaseAIProvider
from ai.provider_router import ProviderRouter
from ai.schemas import ChatMessage, ProviderResponse


class FakeProvider(BaseAIProvider):
    def __init__(self, name, configured=True, responses=None):
        self._name = name
        self._configured = configured
        self.responses = list(responses or [])
        self.calls = 0

    @property
    def provider_name(self):
        return self._name

    @property
    def model_name(self):
        return f"{self._name}-model"

    def is_configured(self):
        return self._configured

    def supports_tools(self):
        return True

    def health_check(self):
        return self._configured

    def normalize_error(self, exc):
        return "unknown_provider_error"

    def generate(self, messages, system_instruction=None, tools=None):
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]


def result(name, success, code=None, content="answer"):
    return ProviderResponse(
        provider_name=name,
        model_name=f"{name}-model",
        success=success,
        content=content if success else None,
        error_code=code,
    )


class ProviderRouterTests(unittest.TestCase):
    def test_missing_key_and_rate_limit_fall_back(self):
        groq = FakeProvider("groq", configured=False, responses=[result("groq", False)])
        mistral = FakeProvider("mistral", responses=[result("mistral", False, "rate_limited")])
        gemini = FakeProvider("gemini", responses=[result("gemini", True)])
        router = ProviderRouter(
            providers=[groq, mistral, gemini],
            provider_order=["groq", "mistral", "gemini"],
            max_retries=0,
            cooldown_seconds=60,
            sleep_fn=lambda _: None,
        )
        response, chain = router.route_request([ChatMessage(role="user", content="hello")])
        self.assertTrue(response.success)
        self.assertEqual(response.provider_name, "gemini")
        self.assertEqual(chain, [
            {"provider": "groq", "status": "missing_key"},
            {"provider": "mistral", "status": "rate_limited"},
            {"provider": "gemini", "status": "success"},
        ])
        self.assertEqual(mistral.calls, 1)
        self.assertEqual(gemini.calls, 1)

    def test_cooldown_is_not_immediately_overridden(self):
        clock = [100.0]
        groq = FakeProvider("groq", responses=[result("groq", False, "timeout")])
        router = ProviderRouter(
            providers=[groq],
            provider_order=["groq"],
            max_retries=0,
            cooldown_seconds=60,
            time_fn=lambda: clock[0],
            sleep_fn=lambda _: None,
        )
        router.route_request([ChatMessage(role="user", content="one")])
        _, second_chain = router.route_request([ChatMessage(role="user", content="two")])
        self.assertEqual(groq.calls, 1)
        self.assertEqual(second_chain, [{"provider": "groq", "status": "cooldown"}])
        clock[0] += 61
        router.route_request([ChatMessage(role="user", content="three")])
        self.assertEqual(groq.calls, 2)

    def test_authentication_error_is_not_retried(self):
        provider = FakeProvider("groq", responses=[result("groq", False, "authentication_error")])
        router = ProviderRouter(
            providers=[provider],
            provider_order=["groq"],
            max_retries=3,
            sleep_fn=lambda _: None,
        )
        response, _ = router.route_request([ChatMessage(role="user", content="hello")])
        self.assertFalse(response.success)
        self.assertEqual(provider.calls, 1)

    def test_ai_disabled_makes_no_provider_calls(self):
        provider = FakeProvider("groq", responses=[result("groq", True)])
        router = ProviderRouter(
            providers=[provider],
            provider_order=["groq"],
            ai_enabled=False,
        )
        response, chain = router.route_request([ChatMessage(role="user", content="hello")])
        self.assertEqual(response.error_code, "ai_disabled")
        self.assertEqual(chain, [])
        self.assertEqual(provider.calls, 0)


if __name__ == "__main__":
    unittest.main()
