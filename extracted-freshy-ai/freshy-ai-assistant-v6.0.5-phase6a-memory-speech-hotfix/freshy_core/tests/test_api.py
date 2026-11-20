import unittest
import sys
import os
import tempfile
from typing import Optional, List, Tuple
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tts_service import TTSService
from voice_input_service import VoiceSettings
import main
from intents import Intent, RuleBasedIntentParser
from fastapi.testclient import TestClient

class FakeVoice:
    def __init__(self, voice_id="voice_1", name="Fake Voice 1", languages=None):
        self.id = voice_id
        self.name = name
        self.languages = languages or ["en-US"]

class FakeEngine:
    def __init__(self):
        self.callbacks = {}
        self.properties = {"rate": 175, "volume": 1.0, "voice": "voice_1"}
        self.voices = [FakeVoice("voice_1", "Fake Voice 1"), FakeVoice("voice_2", "Fake Voice 2")]
        self.said_utterances: List[Tuple[str, Optional[str]]] = []
        self.stopped = False

    def startLoop(self, use_driver=True):
        pass

    def endLoop(self):
        pass

    def getProperty(self, name):
        if name == "voices":
            return self.voices
        return self.properties.get(name)

    def setProperty(self, name, value):
        self.properties[name] = value

    def connect(self, event, callback):
        self.callbacks[event] = callback

    def say(self, text: str, name: Optional[str] = None):
        self.said_utterances.append((text, name))

    def stop(self):
        self.stopped = True

    def iterate(self):
        pass

class FakeVoiceService:
    """Hardware-free API fake; never imports Vosk, PortAudio, or pynput."""

    def __init__(self):
        self.settings = VoiceSettings()
        self.started = False

    def get_devices(self):
        return [
            {
                "id": 0,
                "name": "Fake Microphone",
                "channels": 1,
                "sample_rate": 16000,
                "is_default": True,
            }
        ]

    def get_status(self):
        return {
            "is_listening": self.started,
            "is_calibrating": False,
            "model_initializing": False,
            "model_loaded": True,
            "mic_available": True,
            "error_status": "",
            "freshy_status": "listening" if self.started else "idle",
            "voice_mode": "push_to_talk" if self.started else "wake",
            "session_id": "fake-session",
            "result_id": 0,
            "partial_transcript": "",
            "final_transcript": "",
            "assistant_reply": "",
            "intent": "",
            "success": False,
            "action_executed": False,
            "action_result": {},
            "calibration_id": 0,
            "calibration_result": {},
            "settings": self.settings.to_dict(),
            "running": True,
            "worker_alive": True,
            "shutdown_state": "active",
        }

    def update_settings(self, updates):
        self.settings = self.settings.updated(updates)
        return self.settings

    def start_listening(self, origin="api"):
        del origin
        if self.settings.muted:
            return {"accepted": False, "reason": "Microphone is muted"}
        self.started = True
        return {
            "accepted": True,
            "session_id": "fake-session",
            "reason": "Voice listening requested",
        }

    def stop_listening(self):
        self.started = False
        return {"accepted": True, "reason": "Voice listening stopped"}

    def calibrate_noise(self, timeout=4.0):
        del timeout
        return {
            "success": True,
            "reason": "Ambient noise calibration completed",
            "calibration_id": 1,
            "calibrated_threshold": 0.03,
        }

    def shutdown(self, timeout=0.0):
        del timeout
        self.started = False
        return {"accepted": True, "shutdown_state": "shut_down"}

class TestFastAPIEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.settings_file = os.path.join(cls.temp_dir.name, "api_test_tts_settings.json")
        with open(cls.settings_file, "w", encoding="utf-8") as handle:
            handle.write('{"provider":"system"}')
        cls.fake_engine = FakeEngine()

        cls.fake_tts = TTSService(
            settings_file=cls.settings_file,
            engine_factory=lambda: cls.fake_engine,
            com_initialize=lambda: None,
            com_uninitialize=lambda: None
        )

        # Inject fake TTS service into main before creating TestClient
        main.set_tts_service(cls.fake_tts)
        cls.fake_voice = FakeVoiceService()
        main.set_voice_service(cls.fake_voice)
        cls.client = TestClient(main.app)

        # Mock Gemini intent analyzer to use RuleBasedIntentParser in tests
        cls.gemini_patcher = patch.object(
            main.gemini_analyzer,
            'analyze_intent',
            side_effect=lambda msg: RuleBasedIntentParser.parse(msg)
        )
        cls.gemini_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.gemini_patcher.stop()
        cls.client.close()
        main.set_voice_service(None)
        main.set_tts_service(None)
        cls.temp_dir.cleanup()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("Freshy", data["app"])

    def test_status_endpoint(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("tts", data)

    def test_commands_endpoint(self):
        response = self.client.get("/api/commands")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("commands", data)
        self.assertGreater(len(data["commands"]), 0)

    def test_tts_settings_get_and_post(self):
        res_get = self.client.get("/api/tts/settings")
        self.assertEqual(res_get.status_code, 200)
        self.assertIn("enabled", res_get.json())

        res_post = self.client.post("/api/tts/settings", json={"rate": 180, "volume": 0.9})
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(res_post.json()["rate"], 180)

    def test_tts_settings_range_validation_returns_400(self):
        response = self.client.post("/api/tts/settings", json={"rate": 999})
        self.assertEqual(response.status_code, 400)
        self.assertIn("less than or equal to 400", response.json().get("detail", ""))

    def test_tts_settings_update_during_shutdown(self):
        isolated_shut_tts = TTSService(
            settings_file=os.path.join(self.temp_dir.name, "shut_tts.json"),
            engine_factory=lambda: FakeEngine(),
            com_initialize=lambda: None,
            com_uninitialize=lambda: None
        )
        isolated_shut_tts.shutdown()
        main.set_tts_service(isolated_shut_tts)

        try:
            res = self.client.post("/api/tts/settings", json={"rate": 200})
            self.assertEqual(res.status_code, 503)
            self.assertIn("shutting down", res.json().get("detail", ""))
        finally:
            fresh_fake_tts = TTSService(
                settings_file=self.settings_file,
                engine_factory=lambda: self.fake_engine,
                com_initialize=lambda: None,
                com_uninitialize=lambda: None
            )
            main.set_tts_service(fresh_fake_tts)

    def test_tts_constructor_failure_does_not_break_chat(self):
        main.set_tts_service(None)
        try:
            with patch.object(main, "TTSService", side_effect=RuntimeError("Injected TTS constructor failure")):
                fallback = main.get_tts_service()
                self.assertFalse(fallback.get_status()["engine_available"])

                response = self.client.post("/api/chat", json={"message": "Hello Freshy"})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["intent_name"], "GREETING")
                self.assertTrue(data["action_executed"])
                self.assertEqual(data["freshy_status"], "idle")
        finally:
            replacement = TTSService(
                settings_file=self.settings_file,
                engine_factory=lambda: self.fake_engine,
                com_initialize=lambda: None,
                com_uninitialize=lambda: None
            )
            main.set_tts_service(replacement)

    def test_chat_intents_enqueue_speech(self):
        with patch("subprocess.Popen") as mock_popen, patch("webbrowser.open") as mock_web_open:
            initial_said_count = len(self.fake_engine.said_utterances)

            # 1. Greeting
            res_greet = self.client.post("/api/chat", json={"message": "Hello Freshy"})
            self.assertEqual(res_greet.status_code, 200)
            data_greet = res_greet.json()
            self.assertEqual(data_greet["intent_name"], "GREETING")
            self.assertTrue(data_greet["action_executed"])
            self.assertIn("Freshy", data_greet["reply"])
            self.assertEqual(data_greet["freshy_status"], "speaking")

            # 2. Time / Date
            res_time = self.client.post("/api/chat", json={"message": "What time is it?"})
            self.assertEqual(res_time.status_code, 200)
            data_time = res_time.json()
            self.assertEqual(data_time["intent_name"], "TIME_DATE")
            self.assertTrue(data_time["action_executed"])
            self.assertIn("current time", data_time["reply"])
            self.assertEqual(data_time["freshy_status"], "speaking")

            # 3. Open Notepad
            res_notepad = self.client.post("/api/chat", json={"message": "Open Notepad"})
            self.assertEqual(res_notepad.status_code, 200)
            data_notepad = res_notepad.json()
            self.assertEqual(data_notepad["intent_name"], "OPEN_APP")
            self.assertTrue(data_notepad["action_executed"])
            self.assertIn("Notepad", data_notepad["reply"])

            # 4. Open Calculator
            res_calc = self.client.post("/api/chat", json={"message": "Open Calculator"})
            self.assertEqual(res_calc.status_code, 200)
            data_calc = res_calc.json()
            self.assertEqual(data_calc["intent_name"], "OPEN_APP")
            self.assertTrue(data_calc["action_executed"])
            self.assertIn("Calculator", data_calc["reply"])

            # 5. Blocked App
            with patch.object(main.gemini_analyzer, 'analyze_intent', return_value=Intent(name="OPEN_APP", confidence=0.9, parameters={"app_name": "cmd"})):
                res_blocked_app = self.client.post("/api/chat", json={"message": "Open command prompt"})
                self.assertEqual(res_blocked_app.status_code, 200)
                data_blocked_app = res_blocked_app.json()
                self.assertEqual(data_blocked_app["intent_name"], "OPEN_APP")
                self.assertFalse(data_blocked_app["action_executed"])
                self.assertIn("Security Block", data_blocked_app["reply"])

            # 6. Open Website
            res_web = self.client.post("/api/chat", json={"message": "Open youtube"})
            self.assertEqual(res_web.status_code, 200)
            data_web = res_web.json()
            self.assertEqual(data_web["intent_name"], "OPEN_WEBSITE")
            self.assertTrue(data_web["action_executed"])
            self.assertIn("youtube.com", data_web["reply"])

            # 7. Blocked Domain Website
            with patch.object(main.gemini_analyzer, 'analyze_intent', return_value=Intent(name="OPEN_WEBSITE", confidence=0.9, parameters={"url": "https://unallowed-site.com"})):
                res_blocked_web = self.client.post("/api/chat", json={"message": "Open unallowed site"})
                self.assertEqual(res_blocked_web.status_code, 200)
                data_blocked_web = res_blocked_web.json()
                self.assertEqual(data_blocked_web["intent_name"], "OPEN_WEBSITE")
                self.assertFalse(data_blocked_web["action_executed"])
                self.assertIn("Security Block", data_blocked_web["reply"])

            # 8. Fallback / Unknown
            res_unknown = self.client.post("/api/chat", json={"message": "Random unhandled command 123"})
            self.assertEqual(res_unknown.status_code, 200)
            data_unknown = res_unknown.json()
            self.assertEqual(data_unknown["intent_name"], "GENERAL_CHAT")
            self.assertFalse(data_unknown["action_executed"])
            self.assertIn("could not reach", data_unknown["reply"])
            self.assertEqual(data_unknown["error_code"], "all_providers_failed")

            # 9. Empty message produces 400 and creates NO TTS request
            said_before_empty = len(self.fake_engine.said_utterances)
            res_empty = self.client.post("/api/chat", json={"message": "   "})
            self.assertEqual(res_empty.status_code, 400)
            self.assertEqual(len(self.fake_engine.said_utterances), said_before_empty)

    def test_explicit_accepted_false_when_tts_disabled(self):
        self.client.post("/api/tts/settings", json={"enabled": False})
        try:
            res = self.client.post("/api/tts/test", json={"text": "Test phrase"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertFalse(data["accepted"])
            self.assertEqual(data["status"], "rejected")
            self.assertIn("disabled", data["reason"])
        finally:
            self.client.post("/api/tts/settings", json={"enabled": True})

    def test_tts_voices(self):
        res = self.client.get("/api/tts/voices")
        self.assertEqual(res.status_code, 200)
        self.assertIn("voices", res.json())

    def test_tts_status(self):
        res = self.client.get("/api/tts/status")
        self.assertEqual(res.status_code, 200)
        self.assertIn("is_speaking", res.json())

    def test_tts_test_endpoint(self):
        res = self.client.post("/api/tts/test", json={"text": "Freshy testing endpoint"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["accepted"])

    def test_tts_stop_endpoint(self):
        res = self.client.post("/api/tts/stop")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_voice_endpoints(self):
        # 1. Voice settings GET
        res_settings = self.client.get("/api/voice/settings")
        self.assertEqual(res_settings.status_code, 200)
        self.assertIn("wake_word_enabled", res_settings.json())

        # 2. Voice settings POST
        res_post_settings = self.client.post("/api/voice/settings", json={"listening_timeout": 8.0})
        self.assertEqual(res_post_settings.status_code, 200)
        self.assertEqual(res_post_settings.json()["listening_timeout"], 8.0)

        # 3. Explicit null clears a selected microphone.
        self.client.post("/api/voice/settings", json={"device_index": 0})
        res_default = self.client.post(
            "/api/voice/settings", json={"device_index": None}
        )
        self.assertEqual(res_default.status_code, 200)
        self.assertIsNone(res_default.json()["device_index"])

        # 4. Voice status GET
        res_status = self.client.get("/api/voice/status")
        self.assertEqual(res_status.status_code, 200)
        self.assertIn("is_listening", res_status.json())
        self.assertIn("tts_is_speaking", res_status.json())

        # 5. Voice devices GET
        res_devices = self.client.get("/api/voice/devices")
        self.assertEqual(res_devices.status_code, 200)
        self.assertIn("devices", res_devices.json())

        # 6. Start, stop, and completed calibration endpoints.
        res_start = self.client.post("/api/voice/listen/start")
        self.assertEqual(res_start.status_code, 200)
        self.assertTrue(res_start.json()["accepted"])

        res_stop = self.client.post("/api/voice/listen/stop")
        self.assertEqual(res_stop.status_code, 200)
        self.assertTrue(res_stop.json()["accepted"])

        res_calibrate = self.client.post("/api/voice/calibrate")
        self.assertEqual(res_calibrate.status_code, 200)
        self.assertTrue(res_calibrate.json()["success"])
        self.assertEqual(
            res_calibrate.json()["calibrated_threshold"], 0.03
        )

    def test_chat_endpoint_greeting(self):
        response = self.client.post("/api/chat", json={"message": "Hello Freshy"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent_name"], "GREETING")
        self.assertIn("Freshy", data["reply"])
        self.assertIn("freshy_status", data)

    def test_chat_endpoint_empty_message(self):
        response = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("Message cannot be empty", data.get("detail", ""))

if __name__ == '__main__':
    unittest.main()
