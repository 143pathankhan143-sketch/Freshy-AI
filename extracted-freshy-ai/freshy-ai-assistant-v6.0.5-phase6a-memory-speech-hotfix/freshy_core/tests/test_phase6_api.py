import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
import main
from live.schemas import LiveSettings, LiveStatus
from config import config


class FakeLiveService:
    def __init__(self):
        self.settings = LiveSettings(conversation_mode="standard")
        self.started = False
        self.muted = False

    def status(self):
        return LiveStatus(
            configured=True,
            conversation_mode=self.settings.conversation_mode,
            connected=self.started,
            state="listening" if self.started else "idle",
            model=self.settings.model,
            voice_name=self.settings.voice_name,
            microphone_active=self.started,
        )

    def update_settings(self, updates):
        self.settings = LiveSettings.model_validate({**self.settings.model_dump(), **updates})
        return self.settings

    def start(self):
        self.started = True
        return {"accepted": True, "reason": "started"}

    def stop(self):
        self.started = False
        return {"accepted": True, "reason": "stopped"}

    def set_muted(self, value):
        self.muted = value
        return {"accepted": True, "muted": value}

    def send_text(self, text):
        return {"accepted": bool(text.strip()), "reason": "sent"}

    def interrupt(self):
        return {"accepted": True, "reason": "interrupted"}


class FakeVoice:
    def stop_listening(self):
        return {"accepted": True}

    def shutdown(self):
        pass


class FakeTTS:
    class Settings:
        enabled = False
        startup_greeting = False

    settings = Settings()

    def stop_speaking(self):
        return {"accepted": True}

    def shutdown(self):
        pass


class Phase6ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_gemini_key = config.GEMINI_API_KEY
        config.GEMINI_API_KEY = "phase6-test-key"
        cls.live = FakeLiveService()
        main.set_live_service(cls.live)
        main.set_voice_service(FakeVoice())
        main.set_tts_service(FakeTTS())
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        main.set_live_service(None)
        config.GEMINI_API_KEY = cls.original_gemini_key
        main.set_voice_service(None)
        main.set_tts_service(None)

    def test_live_settings_status_and_session_endpoints(self):
        saved = self.client.post(
            "/api/live/settings",
            json={**self.live.settings.model_dump(), "conversation_mode": "live", "voice_name": "Kore"},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["conversation_mode"], "live")

        started = self.client.post("/api/live/session/start")
        self.assertEqual(started.status_code, 200)
        status = self.client.get("/api/live/status")
        self.assertTrue(status.json()["connected"])
        self.assertNotIn("api_key", str(status.json()).lower())

        muted = self.client.post("/api/live/mute", json={"muted": True})
        self.assertEqual(muted.status_code, 200)
        self.assertTrue(self.live.muted)

        text = self.client.post("/api/live/text", json={"text": "Hello Freshy"})
        self.assertEqual(text.status_code, 200)
        interrupted = self.client.post("/api/live/interrupt")
        self.assertEqual(interrupted.status_code, 200)
        stopped = self.client.post("/api/live/session/stop")
        self.assertEqual(stopped.status_code, 200)

    def test_missing_live_key_rejects_before_standard_voice_shutdown(self):
        class GuardVoice(FakeVoice):
            def __init__(self):
                self.shutdown_called = False

            def shutdown(self):
                self.shutdown_called = True

        guard = GuardVoice()
        main.set_voice_service(guard)
        original = config.GEMINI_API_KEY
        try:
            config.GEMINI_API_KEY = ""
            response = self.client.post("/api/live/session/start")
            self.assertEqual(response.status_code, 503)
            self.assertFalse(guard.shutdown_called)
        finally:
            config.GEMINI_API_KEY = original
            main.set_voice_service(FakeVoice())


if __name__ == "__main__":
    unittest.main()
