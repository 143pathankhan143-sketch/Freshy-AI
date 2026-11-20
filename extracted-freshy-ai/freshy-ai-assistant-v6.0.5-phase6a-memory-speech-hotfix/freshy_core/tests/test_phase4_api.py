import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
import main


class NullTTS:
    class Settings:
        enabled = False
        startup_greeting = False
        def model_dump(self):
            return {"enabled": False, "startup_greeting": False}
    settings = Settings()
    def speak(self, text): return {"accepted": False, "reason": "disabled"}
    def get_status(self): return {"is_speaking": False, "queue_size": 0, "enabled": False}
    def shutdown(self): return {"accepted": True}


class Phase4ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main.set_tts_service(NullTTS())
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        main.set_tts_service(None)

    def test_old_message_only_request_remains_compatible(self):
        response = self.client.post("/api/chat", json={"message": "Hello Freshy"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["intent_name"], "GREETING")
        self.assertEqual(data["provider"], "local")
        self.assertIn("sources", data)
        self.assertIn("fallback_chain", data)

    def test_ai_status_is_credential_free(self):
        data = self.client.get("/api/ai/status").json()
        rendered = str(data).lower()
        self.assertNotIn("api_key", rendered)
        self.assertIn("providers", data)
        self.assertIn("tavily_search_configured", data)

    def test_conversation_clear_accepts_json_body(self):
        response = self.client.post(
            "/api/conversation/clear", json={"session_id": "phase4-test"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session_id"], "phase4-test")


if __name__ == "__main__":
    unittest.main()
