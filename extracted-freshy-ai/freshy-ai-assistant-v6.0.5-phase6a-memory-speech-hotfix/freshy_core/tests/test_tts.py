import unittest
import os
import sys
import tempfile
import time
import threading
from typing import Optional, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import patch
from tts_service import TTSService, TTSSettings

class FakeVoice:
    def __init__(self, voice_id="voice_1", name="Fake Voice 1", languages=None):
        self.id = voice_id
        self.name = name
        self.languages = languages or ["en-US"]

class FakeEngine:
    def __init__(
        self,
        fail_say: bool = False,
        fail_iterate: bool = False,
        fail_connect: bool = False,
        fail_property: bool = False,
    ):
        self.fail_say = fail_say
        self.fail_iterate = fail_iterate
        self.fail_connect = fail_connect
        self.fail_property = fail_property
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
        if self.fail_property:
            raise RuntimeError(f"Fake Engine setProperty failed for {name}")
        self.properties[name] = value

    def connect(self, event, callback):
        if self.fail_connect:
            raise RuntimeError("Callback connection failed")
        self.callbacks[event] = callback

    def say(self, text: str, name: Optional[str] = None):
        if self.fail_say:
            raise RuntimeError("Fake Engine Say Failed")
        self.said_utterances.append((text, name))

    def stop(self):
        self.stopped = True

    def iterate(self):
        if self.fail_iterate:
            raise RuntimeError("Fake Engine Iterate Failed")

    def trigger_start(self, utt_id: str):
        if "started-utterance" in self.callbacks:
            self.callbacks["started-utterance"](utt_id)

    def trigger_finish(self, utt_id: str, completed: bool = True):
        if "finished-utterance" in self.callbacks:
            self.callbacks["finished-utterance"](utt_id, completed)

    def trigger_error(self, utt_id: str, exception: Exception):
        if "error" in self.callbacks:
            self.callbacks["error"](utt_id, exception)

def wait_for(predicate, timeout=2.0, interval=0.01) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()

class TestTTSService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_file = os.path.join(self.temp_dir.name, "test_tts_settings.json")
        self.fake_engine = FakeEngine()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_service(self, engine_factory=None, com_init=None, com_uninit=None) -> TTSService:
        if not os.path.exists(self.settings_file):
            with open(self.settings_file, "w", encoding="utf-8") as handle:
                handle.write('{"provider":"system"}')
        ef = engine_factory or (lambda: self.fake_engine)
        ci = com_init or (lambda: None)
        cu = com_uninit or (lambda: None)
        tts = TTSService(
            settings_file=self.settings_file,
            engine_factory=ef,
            com_initialize=ci,
            com_uninitialize=cu
        )
        self.addCleanup(lambda: tts.shutdown(timeout=0.5) if (hasattr(tts, '_worker_thread') and tts._worker_thread.is_alive()) else None)
        return tts

    def test_empty_and_whitespace_speech_and_test_rejection(self):
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        res1 = tts.speak("")
        res2 = tts.speak("   \t\n  ")
        res3 = tts.test_voice("")
        res4 = tts.test_voice("   ")

        self.assertFalse(res1["accepted"])
        self.assertFalse(res2["accepted"])
        self.assertFalse(res3["accepted"])
        self.assertFalse(res4["accepted"])
        self.assertIn("cannot be empty", res1["reason"])

    def test_disabled_tts_rejection(self):
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.update_settings({"enabled": False})
        res1 = tts.speak("Hello")
        res2 = tts.test_voice("Testing")

        self.assertFalse(res1["accepted"])
        self.assertFalse(res2["accepted"])
        self.assertIn("disabled", res1["reason"])

    def test_settings_save_and_reload_persistence(self):
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.update_settings({"rate": 220, "volume": 0.85, "selected_voice": "voice_2"})
        tts.shutdown()

        # Reload settings in new service instance
        tts2 = TTSService(
            settings_file=self.settings_file,
            engine_factory=lambda: self.fake_engine,
            com_initialize=lambda: None,
            com_uninitialize=lambda: None
        )
        self.addCleanup(lambda: tts2.shutdown(timeout=0.5) if (hasattr(tts2, '_worker_thread') and tts2._worker_thread.is_alive()) else None)

        self.assertEqual(tts2.settings.rate, 220)
        self.assertEqual(tts2.settings.volume, 0.85)
        self.assertEqual(tts2.settings.selected_voice, "voice_2")

    def test_settings_persistence_failure(self):
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        with patch("os.replace", side_effect=OSError("Disk write protected")):
            with self.assertRaises(RuntimeError):
                tts.update_settings({"rate": 300})
        self.assertNotEqual(tts.settings.rate, 300)

    def test_invalid_selected_voice(self):
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        with self.assertRaises(ValueError):
            tts.update_settings({"selected_voice": "non_existent_voice_999"})

    def test_system_default_voice_restores_original_engine_voice(self):
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        self.assertEqual(self.fake_engine.properties["voice"], "voice_1")

        tts.update_settings({"selected_voice": "voice_2"})
        self.assertTrue(wait_for(lambda: self.fake_engine.properties["voice"] == "voice_2"))

        tts.update_settings({"selected_voice": ""})
        self.assertTrue(wait_for(lambda: self.fake_engine.properties["voice"] == "voice_1"))

    def test_engine_property_failure(self):
        class PropertyFailingEngine(FakeEngine):
            def __init__(self):
                super().__init__()
                self.fail_property = False
            def setProperty(self, name, value):
                if self.fail_property and name == "rate":
                    raise RuntimeError("SAPI5 setProperty rate failed")
                super().setProperty(name, value)

        failing_engine = PropertyFailingEngine()
        tts = self._create_service(engine_factory=lambda: failing_engine)
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        failing_engine.fail_property = True
        tts.update_settings({"rate": 300})
        self.assertTrue(wait_for(lambda: not tts.get_status()["engine_available"]))
        self.assertIn("runtime engine error", tts.get_status()["error_status"].lower())

    def test_property_failure_before_say_does_not_activate_utterance(self):
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        self.fake_engine.fail_property = True
        result = tts.speak("This phrase must not reach engine.say")
        self.assertTrue(result["accepted"])
        self.assertTrue(wait_for(lambda: not tts.get_status()["engine_available"]))

        status = tts.get_status()
        self.assertFalse(status["is_speaking"])
        self.assertIsNone(status["current_text"])
        self.assertEqual(status["queue_size"], 0)
        self.assertEqual(self.fake_engine.said_utterances, [])

    def test_engine_failure_with_queued_commands(self):
        failing_engine = FakeEngine(fail_say=True)
        tts = self._create_service(engine_factory=lambda: failing_engine)
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.speak("First message causes failure")
        tts.speak("Second message enqueued behind failure")

        self.assertTrue(wait_for(lambda: not tts.get_status()["engine_available"]))
        self.assertTrue(wait_for(lambda: tts.get_status()["queue_size"] == 0))
        status = tts.get_status()
        self.assertEqual(status["queue_size"], 0)
        self.assertFalse(status["engine_available"])
        self.assertTrue(tts._cmd_queue.empty())

    def test_shutdown_success_and_timeout_truthfulness(self):
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        res = tts.shutdown()
        self.assertTrue(res["accepted"])
        status = tts.get_status()
        self.assertFalse(status["running"])
        self.assertFalse(status["worker_alive"])
        self.assertEqual(status["shutdown_state"], "shut_down")

    def test_blocked_worker_shutdown_timeout(self):
        unblock_event = threading.Event()

        def blocking_com_uninit():
            unblock_event.wait(timeout=5.0)

        tts = self._create_service(com_uninit=blocking_com_uninit)
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        try:
            res = tts.shutdown(timeout=0.1)
            self.assertFalse(res["accepted"])
            self.assertIn("timed out", res["reason"].lower())

            status = tts.get_status()
            self.assertEqual(status["shutdown_state"], "shutdown_timeout")
            self.assertTrue(status["worker_alive"])
            self.assertIn("timed out", status["error_status"].lower())
        finally:
            unblock_event.set()
            tts._worker_thread.join(timeout=1.0)
            status_after = tts.get_status()
            self.assertFalse(status_after["worker_alive"])
            self.assertEqual(status_after["shutdown_state"], "shut_down")

    def test_com_initialization_failure_is_reported_without_thread_crash(self):
        def failing_com_init():
            raise RuntimeError("COM apartment initialization failed")

        tts = self._create_service(com_init=failing_com_init)
        self.assertTrue(wait_for(lambda: not tts.get_status()["engine_initializing"]))

        status = tts.get_status()
        self.assertTrue(status["running"])
        self.assertTrue(status["worker_alive"])
        self.assertFalse(status["engine_available"])
        self.assertIn("com initialization failed", status["error_status"].lower())

    def test_worker_unexpected_exit_state(self):
        class CrashingQueue:
            def get(self, timeout=None):
                raise RuntimeError("Injected command queue crash")

            def put(self, item):
                pass

        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))
        tts._cmd_queue = CrashingQueue()
        self.assertTrue(wait_for(lambda: not tts._worker_thread.is_alive()))

        status = tts.get_status()
        self.assertFalse(status["running"])
        self.assertFalse(status["worker_alive"])
        self.assertEqual(status["shutdown_state"], "failed")
        self.assertIn("worker loop terminated unexpectedly", status["error_status"].lower())

    def test_three_messages_exact_queue_size_and_progression(self):
        """
        1. After three accepted messages, only the first reaches engine.say() and queue_size is exactly 2.
        2. Finishing message one starts message two and changes queue size exactly to 1.
        """
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        res1 = tts.speak("Message 1")
        res2 = tts.speak("Message 2")
        res3 = tts.speak("Message 3")

        self.assertTrue(res1["accepted"])
        self.assertTrue(res2["accepted"])
        self.assertTrue(res3["accepted"])

        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) == 1))

        status = tts.get_status()
        self.assertEqual(len(self.fake_engine.said_utterances), 1)
        self.assertEqual(self.fake_engine.said_utterances[0][0], "Message 1")
        self.assertEqual(status["queue_size"], 2)
        self.assertTrue(status["is_speaking"])

        utt1_id = self.fake_engine.said_utterances[0][1]
        self.fake_engine.trigger_finish(utt1_id)

        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) == 2))

        status2 = tts.get_status()
        self.assertEqual(len(self.fake_engine.said_utterances), 2)
        self.assertEqual(self.fake_engine.said_utterances[1][0], "Message 2")
        self.assertEqual(status2["queue_size"], 1)

        tts.shutdown()

    def test_newer_speech_survives_stop(self):
        """
        Speech enqueued AFTER stop_speaking() is NOT cleared by stop_speaking().
        """
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.speak("Old Message")
        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) == 1))

        tts.stop_speaking()
        tts.speak("New Message")

        utt1_id = self.fake_engine.said_utterances[0][1]
        self.fake_engine.trigger_finish(utt1_id)

        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) == 2))
        self.assertEqual(self.fake_engine.said_utterances[1][0], "New Message")

        tts.shutdown()

    def test_newer_speech_survives_test_speak(self):
        """
        Speech enqueued AFTER test_voice() is NOT cleared by test_voice(), and test phrase is spoken first.
        """
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.speak("Old Message")
        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) == 1))

        tts.test_voice("Test Phrase")
        tts.speak("New Message")

        utt1_id = self.fake_engine.said_utterances[0][1]
        self.fake_engine.trigger_finish(utt1_id)

        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) >= 2))
        self.assertEqual(self.fake_engine.said_utterances[1][0], "Test Phrase")

        utt2_id = self.fake_engine.said_utterances[1][1]
        self.fake_engine.trigger_finish(utt2_id)

        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) == 3))
        self.assertEqual(self.fake_engine.said_utterances[2][0], "New Message")

        tts.shutdown()

    def test_init_failure_clears_queue_and_rejects_subsequent(self):
        """
        Initialization failure clears speech accepted during initialization and leaves queue size 0.
        """
        init_event = threading.Event()

        def slow_failing_factory():
            init_event.wait(timeout=2.0)
            raise RuntimeError("SAPI5 initialization failed")

        tts = self._create_service(engine_factory=slow_failing_factory)

        res1 = tts.speak("Enqueued SPEAK during init")
        res2 = tts.test_voice("Enqueued TEST during init")
        self.assertTrue(res1["accepted"])
        self.assertTrue(res2["accepted"])
        # TEST_SPEAK intentionally cancels the older queued phrase, so only
        # the explicit test utterance remains pending.
        self.assertEqual(tts.get_status()["queue_size"], 1)

        init_event.set()

        self.assertTrue(wait_for(lambda: not tts.get_status()["engine_initializing"]))

        status = tts.get_status()
        self.assertFalse(status["engine_available"])
        self.assertFalse(status["engine_initializing"])
        self.assertEqual(status["queue_size"], 0)

        later_res = tts.speak("Future message")
        self.assertFalse(later_res["accepted"])

        tts.shutdown()

    def test_shutdown_racing_with_initialization_failure(self):
        """
        Shutdown called while engine initialization is blocked cleanly terminates worker when init fails.
        """
        init_event = threading.Event()

        def slow_failing_factory():
            init_event.wait(timeout=2.0)
            raise RuntimeError("Init failed during race")

        tts = self._create_service(engine_factory=slow_failing_factory)

        shut_res = tts.shutdown(timeout=0.01) # Will queue SHUTDOWN while blocked

        init_event.set() # Unblock factory

        # Wait for worker thread to exit
        self.assertTrue(wait_for(lambda: not tts._worker_thread.is_alive()))

    def test_worker_termination_and_com_cleanup(self):
        """
        Worker thread calls com_initialize on startup and com_uninitialize on exit, then terminates.
        """
        com_init_called = False
        com_uninit_called = False

        def ci():
            nonlocal com_init_called
            com_init_called = True

        def cu():
            nonlocal com_uninit_called
            com_uninit_called = True

        tts = self._create_service(com_init=ci, com_uninit=cu)
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))
        self.assertTrue(com_init_called)

        shut_res = tts.shutdown()
        self.assertTrue(shut_res["accepted"])
        self.assertTrue(com_uninit_called)
        self.assertFalse(tts._worker_thread.is_alive())

    def test_callback_registration_failure(self):
        """
        Failure to connect engine callbacks marks engine unavailable and sets error status.
        """
        failing_engine = FakeEngine(fail_connect=True)
        tts = self._create_service(engine_factory=lambda: failing_engine)

        self.assertTrue(wait_for(lambda: not tts.get_status()["engine_initializing"]))

        status = tts.get_status()
        self.assertFalse(status["engine_available"])
        self.assertIn("callback connection failed", status["error_status"].lower())

        tts.shutdown()

    def test_runtime_say_failure(self):
        """
        Runtime say failure updates status truthfully and rejects later speech.
        """
        failing_engine = FakeEngine(fail_say=True)
        tts = self._create_service(engine_factory=lambda: failing_engine)
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.speak("Fail on say")

        self.assertTrue(wait_for(lambda: not tts.get_status()["engine_available"]))

        status = tts.get_status()
        self.assertFalse(status["engine_available"])
        self.assertIn("runtime engine error", status["error_status"].lower())

        later_res = tts.speak("Rejected after say error")
        self.assertFalse(later_res["accepted"])

        tts.shutdown()

    def test_runtime_iterate_failure(self):
        """
        Runtime iterate failure updates status truthfully and rejects later speech.
        """
        failing_engine = FakeEngine(fail_iterate=True)
        tts = self._create_service(engine_factory=lambda: failing_engine)

        self.assertTrue(wait_for(lambda: not tts.get_status()["engine_available"]))

        status = tts.get_status()
        self.assertFalse(status["engine_available"])
        self.assertIn("runtime engine error", status["error_status"].lower())

        later_res = tts.speak("Rejected after iterate error")
        self.assertFalse(later_res["accepted"])

        tts.shutdown()

    def test_runtime_callback_error(self):
        """
        Runtime error callback updates status truthfully and rejects later speech.
        """
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.speak("Active utterance")
        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) == 1))

        active_id = self.fake_engine.said_utterances[0][1]
        self.fake_engine.trigger_error(active_id, RuntimeError("Driver playback crash"))

        self.assertTrue(wait_for(lambda: not tts.get_status()["engine_available"]))

        status = tts.get_status()
        self.assertFalse(status["engine_available"])
        self.assertIn("runtime engine error", status["error_status"].lower())

        later_res = tts.speak("Rejected after callback error")
        self.assertFalse(later_res["accepted"])

        tts.shutdown()

    def test_stop_speaking_clears_pending(self):
        """
        stop_speaking stops active speech and clears pending queue.
        """
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.speak("Message 1")
        tts.speak("Message 2")

        stop_res = tts.stop_speaking()
        self.assertTrue(stop_res["accepted"])

        self.assertTrue(wait_for(lambda: tts.get_status()["queue_size"] == 0))
        self.assertFalse(tts.get_status()["is_speaking"])

        tts.shutdown()

    def test_disable_and_reenable_clears_and_does_not_resume(self):
        """
        Disabling TTS stops active speech and clears pending queue; re-enabling does not resume old speech.
        """
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.speak("Message 1")
        tts.speak("Message 2")

        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) == 1))

        tts.update_settings({"enabled": False})

        self.assertTrue(wait_for(lambda: tts.get_status()["queue_size"] == 0))
        self.assertFalse(tts.get_status()["enabled"])

        tts.update_settings({"enabled": True})
        self.assertTrue(tts.get_status()["enabled"])

        time.sleep(0.05)
        self.assertEqual(len(self.fake_engine.said_utterances), 1)

        res_new = tts.speak("Fresh Message")
        self.assertTrue(res_new["accepted"])
        self.assertTrue(wait_for(lambda: len(self.fake_engine.said_utterances) == 2))

        tts.shutdown()

    def test_shutdown_rejection(self):
        """
        Calling speak, test_voice, stop_speaking after shutdown returns accepted=False.
        """
        tts = self._create_service()
        self.assertTrue(wait_for(lambda: tts.get_status()["engine_available"]))

        tts.shutdown()

        self.assertFalse(tts.speak("Post shutdown")["accepted"])
        self.assertFalse(tts.test_voice("Post shutdown")["accepted"])
        self.assertFalse(tts.stop_speaking()["accepted"])

if __name__ == '__main__':
    unittest.main()
