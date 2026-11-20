import os
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(__file__))

from natural_tts_service import GeminiNaturalTTS, ensure_wav
from tts_service import TTSService
from test_tts import FakeEngine, wait_for


class FakeModels:
    def __init__(self, audio=b"\x01\x00\x02\x00"):
        self.audio = audio
        self.last_request = None

    def generate_content(self, **kwargs):
        self.last_request = kwargs
        inline = SimpleNamespace(data=self.audio, mime_type="audio/L16;rate=24000")
        part = SimpleNamespace(inline_data=inline)
        content = SimpleNamespace(parts=[part])
        return SimpleNamespace(candidates=[SimpleNamespace(content=content)])


class FakeClient:
    def __init__(self):
        self.models = FakeModels()


class FakeNaturalGenerator:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def is_configured(self):
        return True

    def generate_wav(self, text, **kwargs):
        self.calls.append((text, kwargs))
        if self.fail:
            raise RuntimeError("injected natural failure")
        return ensure_wav(b"\x01\x00\x02\x00", "audio/L16;rate=24000")


class FakePlayer:
    def __init__(self):
        self.played = []
        self.stop_calls = 0

    def play(self, wav_bytes):
        self.played.append(wav_bytes)
        return True

    def stop(self):
        self.stop_calls += 1


class NaturalTTSGenerationTests(unittest.TestCase):
    def test_gemini_natural_tts_builds_hindi_female_audio_request(self):
        client = FakeClient()
        tts = GeminiNaturalTTS(
            api_key="fake-key-for-injected-client",
            model="gemini-2.5-flash-preview-tts",
            client=client,
        )
        wav = tts.generate_wav(
            "नमस्ते, मैं फ्रेशी हूँ।",
            voice_profile="hindi_female",
            speech_language="hi-IN",
            rate=175,
            volume=0.8,
        )
        self.assertEqual(wav[:4], b"RIFF")
        request = client.models.last_request
        self.assertEqual(request["model"], "gemini-2.5-flash-preview-tts")
        prompt = request["contents"][0]["parts"][0]["text"]
        self.assertIn("adult Indian female", prompt)
        self.assertIn("Hindi/Hinglish", prompt)
        self.assertIn("नमस्ते", prompt)

    def test_missing_key_is_not_available(self):
        tts = GeminiNaturalTTS(api_key="", model="gemini-2.5-flash-preview-tts")
        self.assertFalse(tts.is_configured())
        with self.assertRaises(RuntimeError):
            tts.generate_wav("Hello")


class NaturalTTSRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = FakeEngine()
        self.player = FakePlayer()

    def tearDown(self):
        self.temp.cleanup()

    def _service(self, natural):
        service = TTSService(
            settings_file=os.path.join(self.temp.name, "tts.json"),
            engine_factory=lambda: self.engine,
            com_initialize=lambda: None,
            com_uninitialize=lambda: None,
            natural_tts_factory=lambda: natural,
            natural_audio_player=self.player,
        )
        self.addCleanup(
            lambda: service.shutdown(timeout=0.5)
            if service._worker_thread.is_alive()
            else None
        )
        self.assertTrue(wait_for(lambda: service.get_status()["engine_available"]))
        return service

    def test_natural_provider_uses_gemini_and_not_sapi(self):
        natural = FakeNaturalGenerator()
        service = self._service(natural)
        service.update_settings(
            {
                "provider": "gemini",
                "natural_voice": "hindi_male",
                "speech_language": "hi-IN",
            }
        )
        result = service.speak("नमस्ते")
        self.assertTrue(result["accepted"])
        self.assertTrue(wait_for(lambda: len(self.player.played) == 1))
        self.assertEqual(len(self.engine.said_utterances), 0)
        self.assertEqual(natural.calls[0][1]["voice_profile"], "hindi_male")

    def test_natural_failure_is_silent_by_default(self):
        natural = FakeNaturalGenerator(fail=True)
        service = self._service(natural)
        service.update_settings(
            {"provider": "gemini", "failure_behavior": "silent", "fallback_provider": "none"}
        )
        service.speak("Remain text only")
        self.assertTrue(wait_for(lambda: service.get_status()["queue_size"] == 0))
        self.assertEqual(self.engine.said_utterances, [])
        self.assertIn("injected natural failure", service.get_status()["voice_last_error"])

    def test_user_selected_system_fallback_is_explicit(self):
        natural = FakeNaturalGenerator(fail=True)
        service = self._service(natural)
        service.update_settings(
            {
                "provider": "gemini",
                "failure_behavior": "selected_fallback",
                "fallback_provider": "system",
            }
        )
        service.speak("Use my chosen Windows fallback")
        self.assertTrue(wait_for(lambda: len(self.engine.said_utterances) == 1))
        self.assertEqual(
            self.engine.said_utterances[0][0], "Use my chosen Windows fallback"
        )

    def test_stop_reaches_natural_player(self):
        service = self._service(FakeNaturalGenerator())
        before = self.player.stop_calls
        result = service.stop_speaking()
        self.assertTrue(result["accepted"])
        self.assertGreater(self.player.stop_calls, before)


if __name__ == "__main__":
    unittest.main()
