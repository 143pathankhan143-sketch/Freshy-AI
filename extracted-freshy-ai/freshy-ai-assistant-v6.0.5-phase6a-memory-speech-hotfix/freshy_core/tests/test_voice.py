import os
import struct
import sys
import tempfile
import threading
import time
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock


sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from intents import RuleBasedIntentParser
from voice_input_service import (
    UnavailableVoiceInputService,
    VoiceInputService,
    VoiceSettings,
    compute_pcm_rms,
    normalize_text,
    split_wake_phrase,
)


def wait_for(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


class FakeRecognizer:
    def AcceptWaveform(self, data: bytes) -> bool:
        return False

    def Result(self) -> str:
        return '{"text": ""}'

    def PartialResult(self) -> str:
        return '{"partial": ""}'

    def FinalResult(self) -> str:
        return '{"text": ""}'


class FakeVosk:
    def __init__(self):
        self.models: List[Any] = []
        self.recognizers: List[FakeRecognizer] = []

    def Model(self, model_dir: str) -> object:
        model = {"path": model_dir}
        self.models.append(model)
        return model

    def KaldiRecognizer(self, model: object, sample_rate: int) -> FakeRecognizer:
        del model
        if sample_rate != 16_000:
            raise AssertionError("Freshy must use 16 kHz Vosk recognition")
        recognizer = FakeRecognizer()
        self.recognizers.append(recognizer)
        return recognizer


class FakeStream:
    def __init__(self, callback, device):
        self.callback = callback
        self.device = device
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True

    def emit(self, pcm: bytes) -> None:
        self.callback(pcm, len(pcm) // 2, None, None)


class FakeSoundDevice:
    class _Default:
        device = (0, None)

    def __init__(self):
        self.default = self._Default()
        self.devices = [
            {
                "name": "Default Microphone",
                "max_input_channels": 1,
                "default_samplerate": 16_000,
            },
            {
                "name": "USB Microphone",
                "max_input_channels": 2,
                "default_samplerate": 48_000,
            },
        ]
        self.streams: List[FakeStream] = []

    def query_devices(self):
        return list(self.devices)

    def RawInputStream(self, **kwargs):
        stream = FakeStream(kwargs["callback"], kwargs.get("device"))
        self.streams.append(stream)
        return stream


class FakeHotkeyListener:
    def __init__(self, mapping):
        self.mapping = mapping
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class FakeKeyboard:
    def __init__(self):
        self.listeners: List[FakeHotkeyListener] = []

    def GlobalHotKeys(self, mapping):
        listener = FakeHotkeyListener(mapping)
        self.listeners.append(listener)
        return listener


class FakePynput:
    def __init__(self):
        self.keyboard = FakeKeyboard()


class VoiceInputServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.model_dir = os.path.join(self.temp_dir.name, "model")
        os.makedirs(self.model_dir)
        self.settings_file = os.path.join(
            self.temp_dir.name, "voice_settings.json"
        )
        self.vosk = FakeVosk()
        self.sounddevice = FakeSoundDevice()
        self.pynput = FakePynput()
        self.chat_callback = MagicMock(
            return_value={
                "reply": "Opened Notepad successfully.",
                "intent_name": "OPEN_APP",
                "success": True,
                "action_executed": True,
                "freshy_status": "speaking",
                "details": {"app": "notepad"},
            }
        )
        self.tts_stop = MagicMock()
        self.tts_status: Dict[str, Any] = {
            "is_speaking": False,
            "queue_size": 0,
            "current_text": None,
        }

    def make_service(self, **overrides) -> VoiceInputService:
        options = {
            "settings_file": self.settings_file,
            "model_dir": self.model_dir,
            "chat_callback": self.chat_callback,
            "tts_stop_callback": self.tts_stop,
            "tts_status_callback": lambda: dict(self.tts_status),
            "vosk_module": self.vosk,
            "sounddevice_module": self.sounddevice,
            "pynput_module": self.pynput,
        }
        options.update(overrides)
        service = VoiceInputService(**options)
        self.addCleanup(service.shutdown)
        self.assertTrue(service.wait_until_ready(2.0))
        self.assertTrue(
            wait_for(lambda: service.get_status()["shutdown_state"] == "active")
        )
        return service

    def test_settings_round_trip_and_bounds(self):
        settings = VoiceSettings(
            device_index=1,
            listening_timeout=99,
            noise_threshold=0,
        )
        self.assertEqual(settings.listening_timeout, 30.0)
        self.assertEqual(settings.noise_threshold, 0.001)
        restored = VoiceSettings.from_dict(settings.to_dict())
        self.assertEqual(restored.device_index, 1)

    def test_pcm_rms_and_normalization(self):
        self.assertEqual(compute_pcm_rms(b"\x00\x00" * 20), 0.0)
        samples = struct.pack("<20h", *([8192] * 20))
        self.assertGreater(compute_pcm_rms(samples), 0.2)
        self.assertEqual(normalize_text(" Hello, Freshy! "), "hello freshy")

    def test_worker_owns_one_stream_and_reopens_for_device_change(self):
        service = self.make_service()
        self.assertEqual(len(self.sounddevice.streams), 1)
        first_stream = self.sounddevice.streams[0]

        updated = service.update_settings({"device_index": 1})
        self.assertEqual(updated.device_index, 1)
        self.assertTrue(wait_for(lambda: len(self.sounddevice.streams) == 2))
        self.assertTrue(first_stream.stopped)
        self.assertTrue(first_stream.closed)
        self.assertEqual(self.sounddevice.streams[-1].device, 1)

        service.update_settings({"device_index": None})
        self.assertTrue(wait_for(lambda: len(self.sounddevice.streams) == 3))
        self.assertIsNone(self.sounddevice.streams[-1].device)

    def test_invalid_device_is_rejected_without_changing_settings(self):
        service = self.make_service()
        with self.assertRaises(ValueError):
            service.update_settings({"device_index": 99})
        self.assertIsNone(service.get_status()["settings"]["device_index"])

    def test_wake_word_accepts_observed_vosk_variants(self):
        service = self.make_service()

        service._handle_recognized_speech_worker("Freshy")
        service._handle_recognized_speech_worker("Hey Freshy")
        self.assertFalse(service.get_status()["is_listening"])

        service._handle_recognized_speech_worker("Hello crazy")
        self.assertTrue(service.get_status()["is_listening"])
        self.assertEqual(service.get_status()["freshy_status"], "listening")
        self.tts_stop.assert_called_once()

    def test_wake_phrase_splitter(self):
        self.assertEqual(split_wake_phrase("Hello Freshy"), "")
        self.assertEqual(
            split_wake_phrase("hello freshly open calculator"),
            "open calculator",
        )
        self.assertIsNone(split_wake_phrase("hey Freshy"))

    def test_inline_wake_command_is_processed_once(self):
        service = self.make_service()
        service._handle_recognized_speech_worker(
            "Hello Freshy open notepad"
        )
        self.chat_callback.assert_called_once_with("open notepad")
        status = service.get_status()
        self.assertEqual(status["result_id"], 1)
        self.assertTrue(status["result_token"])
        self.assertTrue(status["action_executed"])
        self.assertEqual(status["assistant_reply"], "Opened Notepad successfully.")
        self.assertEqual(status["freshy_status"], "idle")

    def test_push_to_talk_interrupts_tts_and_processes_result(self):
        service = self.make_service()
        start = service.start_listening()
        self.assertTrue(start["accepted"])
        self.assertTrue(wait_for(lambda: service.get_status()["is_listening"]))
        self.tts_stop.assert_called_once()

        service._handle_recognized_speech_worker("Notepad kholo")
        self.chat_callback.assert_called_once_with("Notepad kholo")
        status = service.get_status()
        self.assertEqual(status["intent"], "OPEN_APP")
        self.assertTrue(status["success"])

    def test_normal_user_speech_automatically_barges_in(self):
        service = self.make_service()
        self.tts_status.update(
            {
                "is_speaking": True,
                "current_text": "I opened Calculator successfully for you.",
            }
        )
        service._sync_tts_recognizer_mode_worker()

        self.assertTrue(
            service._is_probable_user_barge_in("open notepad please")
        )
        service._activate_barge_in_worker("open notepad please")

        self.tts_stop.assert_called_once()
        status = service.get_status()
        self.assertTrue(status["is_listening"])
        self.assertEqual(status["partial_transcript"], "open notepad please")

    def test_loudspeaker_echo_does_not_trigger_barge_in(self):
        service = self.make_service()
        self.tts_status.update(
            {
                "is_speaking": True,
                "current_text": "I opened Calculator successfully for you.",
            }
        )

        self.assertFalse(
            service._is_probable_user_barge_in(
                "opened calculator successfully"
            )
        )
        self.assertFalse(service._is_probable_user_barge_in("calculator"))

    def test_continuous_mode_waits_for_tts_before_resuming(self):
        service = self.make_service()
        service.update_settings({"continuous_listening": True})
        self.assertTrue(service.start_listening()["accepted"])
        self.assertTrue(wait_for(lambda: service.get_status()["is_listening"]))

        self.tts_status.update({"is_speaking": True, "queue_size": 1})
        service._handle_recognized_speech_worker("open notepad")
        self.assertFalse(service.get_status()["is_listening"])

        self.tts_status.update({"is_speaking": False, "queue_size": 0})
        self.assertTrue(wait_for(lambda: service.get_status()["is_listening"]))

    def test_calibration_returns_completed_threshold(self):
        service = self.make_service()
        stream = self.sounddevice.streams[-1]
        pcm = struct.pack("<200h", *([1200] * 200))

        def emit_audio():
            self.assertTrue(
                wait_for(lambda: service.get_status()["is_calibrating"])
            )
            for _ in range(30):
                stream.emit(pcm)
                time.sleep(0.01)

        emitter = threading.Thread(target=emit_audio)
        emitter.start()
        result = service.calibrate_noise(timeout=4.0)
        emitter.join(timeout=2.0)

        self.assertTrue(result["success"])
        self.assertGreater(result["calibrated_threshold"], 0.005)
        self.assertFalse(service.get_status()["is_calibrating"])

    def test_muted_and_shutdown_requests_are_rejected_truthfully(self):
        service = self.make_service()
        service.update_settings({"muted": True})
        self.assertTrue(
            wait_for(lambda: service.get_status()["voice_mode"] == "muted")
        )
        self.assertFalse(service.start_listening()["accepted"])

        shutdown = service.shutdown()
        self.assertTrue(shutdown["accepted"])
        self.assertFalse(service.start_listening()["accepted"])

    def test_missing_model_does_not_break_service(self):
        missing_path = os.path.join(self.temp_dir.name, "missing")
        service = VoiceInputService(
            settings_file=self.settings_file,
            model_dir=missing_path,
            vosk_module=self.vosk,
            sounddevice_module=self.sounddevice,
            pynput_module=self.pynput,
        )
        self.addCleanup(service.shutdown)
        self.assertTrue(service.wait_until_ready())
        status = service.get_status()
        self.assertFalse(status["model_loaded"])
        self.assertFalse(service.start_listening()["accepted"])

    def test_unavailable_fallback(self):
        fallback = UnavailableVoiceInputService("injected failure")
        self.assertFalse(fallback.start_listening()["accepted"])
        self.assertFalse(fallback.get_status()["mic_available"])
        with self.assertRaises(RuntimeError):
            fallback.update_settings({"muted": True})


class HinglishIntentTests(unittest.TestCase):
    def test_phase3_hinglish_commands(self):
        cases = [
            ("Notepad kholo", "OPEN_APP"),
            ("Calculator kholo", "OPEN_APP"),
            ("Google kholo", "OPEN_WEBSITE"),
            ("YouTube kholo", "OPEN_WEBSITE"),
            ("Time kya hai", "TIME_DATE"),
            ("Namaste kaise ho", "GREETING"),
            ("Hello Freshy open calculator", "OPEN_APP"),
        ]
        for phrase, expected in cases:
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    RuleBasedIntentParser.parse(phrase).name,
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
