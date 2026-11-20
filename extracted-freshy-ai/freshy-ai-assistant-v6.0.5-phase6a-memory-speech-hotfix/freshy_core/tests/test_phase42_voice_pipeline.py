import os
import struct
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tts_service import TTSService, split_speech_chunks
from voice_activity import AdaptiveVoiceActivityDetector
from voice_input_service import VoiceInputService, VoiceSettings
from whisper_service import WhisperTranscriber

from test_voice import FakePynput, FakeSoundDevice, FakeVosk, wait_for
from test_tts import FakeEngine


class _FakeWhisperModel:
    def __init__(self, *args, **kwargs):
        self.created_with = (args, kwargs)
        self.calls = []

    def transcribe(self, path, **kwargs):
        self.calls.append((path, kwargs))
        return [SimpleNamespace(text=" नमस्ते "), SimpleNamespace(text="Freshy")], {}


class _FakeWhisperModule:
    WhisperModel = _FakeWhisperModel




class _FakeNaturalTTS:
    def __init__(self):
        self.calls = []

    def is_configured(self):
        return True

    def generate_wav(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return b"prepared-wav-" + text.encode("utf-8")


class _FakeAudioPlayer:
    def __init__(self):
        self.played = []
        self.stopped = False

    def play(self, wav_bytes):
        self.played.append(wav_bytes)
        return True

    def stop(self):
        self.stopped = True

class Phase42VoicePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.settings_file = os.path.join(self.temp_dir.name, "voice_settings.json")
        self.model_dir = os.path.join(self.temp_dir.name, "vosk-model")
        os.makedirs(self.model_dir)

    def make_service(self, **overrides):
        status = {
            "is_speaking": False,
            "queue_size": 0,
            "current_text": None,
        }
        options = {
            "settings_file": self.settings_file,
            "model_dir": self.model_dir,
            "chat_callback": MagicMock(
                return_value={
                    "reply": "My name is Freshy.",
                    "intent_name": "GENERAL_CHAT",
                    "success": True,
                    "action_executed": False,
                    "details": {},
                }
            ),
            "prepare_callback": MagicMock(
                return_value={
                    "reply": "My name is Freshy.",
                    "intent": "general_chat",
                    "action": "none",
                    "action_executed": False,
                    "success": True,
                    "provider": "fake",
                    "model": "fake-model",
                    "used_web_search": False,
                    "sources": [],
                    "fallback_chain": [],
                    "tool_used": None,
                    "tts_requested": True,
                    "error_code": None,
                    "user_safe_error": None,
                }
            ),
            "tts_stop_callback": MagicMock(),
            "tts_status_callback": lambda: dict(status),
            "vosk_module": FakeVosk(),
            "sounddevice_module": FakeSoundDevice(),
            "pynput_module": FakePynput(),
            "webrtcvad_module": object(),
        }
        options.update(overrides)
        service = VoiceInputService(**options)
        service._test_tts_status = status
        self.addCleanup(service.shutdown)
        self.assertTrue(service.wait_until_ready(2.0))
        self.assertTrue(wait_for(lambda: service.get_status()["shutdown_state"] == "active"))
        return service

    def test_phase42_settings_validate_engine_silence_and_sensitivity(self):
        settings = VoiceSettings(
            recognition_engine="WHISPER",
            whisper_model="small",
            adaptive_silence=False,
            response_silence_seconds=99,
            interruption_sensitivity="HIGH",
        )
        self.assertEqual(settings.recognition_engine, "whisper")
        self.assertEqual(settings.whisper_model, "small")
        self.assertEqual(settings.response_silence_seconds, 5.0)
        self.assertEqual(settings.interruption_sensitivity, "high")

    def test_whisper_adapter_is_lazy_and_maps_hindi_language(self):
        transcriber = WhisperTranscriber(model_name="base", module=_FakeWhisperModule())
        self.assertFalse(transcriber.model_loaded)
        pcm = struct.pack("<1600h", *([1200] * 1600))
        text = transcriber.transcribe_pcm(pcm, language="hi-IN")
        self.assertEqual(text, "नमस्ते Freshy")
        self.assertTrue(transcriber.model_loaded)
        _path, kwargs = transcriber._model.calls[0]
        self.assertEqual(kwargs["language"], "hi")
        self.assertFalse(kwargs["vad_filter"])

    def test_adaptive_vad_fallback_detects_speech_without_optional_module(self):
        detector = AdaptiveVoiceActivityDetector(
            sensitivity="normal", webrtcvad_module=object()
        )
        # object() has no Vad constructor, so deterministic RMS fallback is used.
        quiet = struct.pack("<1600h", *([0] * 1600))
        speech = struct.pack("<1600h", *([9000] * 1600))
        self.assertFalse(detector.decide(quiet, 0.02).is_speech)
        self.assertTrue(detector.decide(speech, 0.02).is_speech)
        self.assertEqual(detector.engine_name, "adaptive_rms")

    def test_queued_or_generating_audio_does_not_trigger_false_speaking_state(self):
        service = self.make_service()
        service._test_tts_status.update(
            {
                "is_speaking": True,
                "is_audio_playing": False,
                "is_generating_audio": True,
                "queue_size": 3,
            }
        )
        service._sync_tts_state_worker()
        self.assertFalse(service._tts_was_busy)

    def test_vad_barge_in_stops_tts_and_enters_listening(self):
        service = self.make_service()
        service.update_settings({"interruption_sensitivity": "high"})
        self.assertTrue(wait_for(lambda: service.settings.interruption_sensitivity == "high"))
        service._test_tts_status.update(
            {
                "is_speaking": True,
                "queue_size": 1,
                "current_text": "I am explaining Flutter Provider in detail.",
            }
        )
        service._sync_tts_state_worker()
        speaker_echo = struct.pack("<1600h", *([3000] * 1600))
        loud_user = struct.pack("<1600h", *([12000] * 1600))
        service._process_audio_worker(speaker_echo)
        time.sleep(0.16)
        service._process_audio_worker(loud_user)
        time.sleep(0.13)
        service._process_audio_worker(loud_user)
        self.assertTrue(service.get_status()["is_listening"])
        service.tts_stop_callback.assert_called()
        self.assertEqual(service.get_status()["voice_mode"], "barge_in")

    def test_stable_safe_partial_prepares_once_and_final_reuses_it(self):
        service = self.make_service()
        self.assertTrue(service.start_listening()["accepted"])
        self.assertTrue(wait_for(lambda: service.get_status()["is_listening"]))
        service._update_partial_text("what is your name please")
        with service._lock:
            service._partial_changed_at = time.monotonic() - 1.0
        service._maybe_start_fast_preparation_worker()
        self.assertTrue(wait_for(lambda: service.get_status()["prepared_response_ready"]))
        service.prepare_callback.assert_called_once()

        service._accept_final_transcript("what is your name please")
        args = service.chat_callback.call_args.args
        self.assertEqual(args[0], "what is your name please")
        self.assertEqual(args[1]["reply"], "My name is Freshy.")

    def test_partial_tool_request_never_starts_speculative_provider_call(self):
        service = self.make_service()
        self.assertTrue(service.start_listening()["accepted"])
        self.assertTrue(wait_for(lambda: service.get_status()["is_listening"]))
        service._update_partial_text("please open notepad for me")
        with service._lock:
            service._partial_changed_at = time.monotonic() - 1.0
        service._maybe_start_fast_preparation_worker()
        time.sleep(0.05)
        service.prepare_callback.assert_not_called()

    def test_adaptive_silence_extends_unfinished_conjunction(self):
        service = self.make_service()
        with service._lock:
            service.settings = service.settings.updated(
                {"adaptive_silence": True, "response_silence_seconds": 3.0}
            )
            service._partial_transcript = "tell me about Flutter and"
        self.assertEqual(service._effective_silence_seconds(), 4.2)

    def test_prepared_natural_audio_is_reused_without_second_generation(self):
        natural = _FakeNaturalTTS()
        player = _FakeAudioPlayer()
        engine = FakeEngine()
        settings_path = os.path.join(self.temp_dir.name, "tts-settings.json")
        service = TTSService(
            settings_file=settings_path,
            engine_factory=lambda: engine,
            com_initialize=lambda: None,
            com_uninitialize=lambda: None,
            natural_tts_factory=lambda: natural,
            natural_audio_player=player,
        )
        self.addCleanup(service.shutdown)
        self.assertTrue(wait_for(lambda: service.get_status()["engine_available"]))
        service.update_settings(
            {
                "provider": "gemini",
                "fast_start_enabled": True,
                "prepare_during_silence": True,
            }
        )
        prepared = service.prepare_speech("My name is Freshy.")
        self.assertTrue(prepared["accepted"])
        result = service.speak("My name is Freshy.", prepared["token"])
        self.assertTrue(result["accepted"])
        self.assertTrue(result["prepared_audio_used"])
        self.assertTrue(wait_for(lambda: bool(player.played)))
        self.assertEqual(len(natural.calls), 1)

    def test_auto_engine_uses_vosk_during_whisper_warmup_then_switches(self):
        service = self.make_service()
        with service._lock:
            service.settings = service.settings.updated({"recognition_engine": "auto"})
            service._vosk_model_loaded = True
            service._whisper_dependency_available = True
            service._whisper_load_failed = False
            service._whisper._model = None
        self.assertEqual(service._resolved_engine(), "vosk")

        with service._lock:
            service._whisper._model = object()
        self.assertEqual(service._resolved_engine(), "whisper")

    def test_fast_tts_chunks_start_with_first_sentence(self):
        text = (
            "Freshy is ready to help you. "
            "This second sentence contains more detail for the answer. "
            "The final sentence should remain ordered."
        )
        chunks = split_speech_chunks(text, max_characters=120)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(chunks[0].startswith("Freshy is ready"))
        self.assertEqual(" ".join(chunks), text)


if __name__ == "__main__":
    unittest.main()
