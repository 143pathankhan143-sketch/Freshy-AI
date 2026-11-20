import os
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from live.audio_stream import LiveMicrophone, LivePcmOutput
from live.schemas import LiveSettings
from live.session_manager import LiveSessionManager
from live.tool_bridge import LiveToolBridge


class FakeRawOutputStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.active = False
        self.writes = []
        self.aborts = 0

    def start(self):
        self.active = True

    def write(self, data):
        self.writes.append(bytes(data))

    def abort(self):
        self.aborts += 1
        self.active = False

    def stop(self):
        self.active = False

    def close(self):
        self.active = False


class FakeRawInputStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.callback = kwargs["callback"]
        self.active = False

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def close(self):
        self.active = False


class FakeSoundDevice:
    def __init__(self):
        self.outputs = []
        self.inputs = []

    def RawOutputStream(self, **kwargs):
        stream = FakeRawOutputStream(**kwargs)
        self.outputs.append(stream)
        return stream

    def RawInputStream(self, **kwargs):
        stream = FakeRawInputStream(**kwargs)
        self.inputs.append(stream)
        return stream


class Phase6LiveVoiceTests(unittest.TestCase):
    def test_live_settings_are_bounded_and_validate_modes(self):
        settings = LiveSettings(
            conversation_mode="live",
            silence_duration_ms=700,
            microphone_chunk_ms=40,
            output_buffer_ms=80,
        )
        self.assertEqual(settings.conversation_mode, "live")
        with self.assertRaises(Exception):
            LiveSettings(conversation_mode="unsafe")
        with self.assertRaises(Exception):
            LiveSettings(silence_duration_ms=50)
        with self.assertRaises(Exception):
            LiveSettings(model="")

    def test_live_config_contains_memory_safe_tools_and_no_api_key(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = LiveSessionManager(
                settings_file=os.path.join(temp, "live.json"),
                memory_context_provider=lambda: "- name: Pathan\n- preferred language: Hinglish",
                sounddevice_module=FakeSoundDevice(),
            )
            manager.settings = manager.settings.model_copy(
                update={"conversation_mode": "live", "tools_enabled": True}
            )
            rendered = repr(manager._live_config()).lower()
            self.assertIn("function_declarations", rendered)
            self.assertIn("pathan", rendered)
            self.assertNotIn("api_key", rendered)
            self.assertNotIn("gemini_api_key", rendered)
            self.assertIn("never speak or spell a url", rendered)

    def test_output_stream_reuses_one_device_and_flushes(self):
        fake = FakeSoundDevice()
        started = []
        stopped = []
        output = LivePcmOutput(
            sounddevice_module=fake,
            buffer_ms=20,
            on_playback_started=lambda: started.append(True),
            on_playback_stopped=lambda: stopped.append(True),
        )
        packet = struct.pack("<" + "h" * 960, *([3000] * 960))
        self.assertTrue(output.enqueue(packet))
        deadline = time.time() + 1.0
        while time.time() < deadline and not fake.outputs:
            time.sleep(0.01)
        while time.time() < deadline and fake.outputs and not fake.outputs[0].writes:
            time.sleep(0.01)
        self.assertEqual(len(fake.outputs), 1)
        self.assertTrue(fake.outputs[0].writes)
        output.flush()
        self.assertGreaterEqual(fake.outputs[0].aborts, 1)
        output.stop()
        self.assertTrue(started)

    def test_local_barge_in_requires_sustained_level_above_echo_guard(self):
        fake = FakeSoundDevice()
        audio_packets = []
        interruptions = []
        speech_started = []
        microphone = LiveMicrophone(
            on_audio=audio_packets.append,
            on_local_barge_in=lambda: interruptions.append(True),
            output_state=lambda: (True, 0.05),
            on_speech_started=lambda: speech_started.append(True),
            sample_rate=16000,
            chunk_ms=40,
            noise_threshold=0.01,
            sounddevice_module=fake,
        )
        microphone.start()
        loud = struct.pack("<" + "h" * 640, *([10000] * 640))
        fake.inputs[0].callback(loud, 640, None, None)
        fake.inputs[0].callback(loud, 640, None, None)
        self.assertEqual(len(audio_packets), 2)
        self.assertTrue(speech_started)
        self.assertTrue(interruptions)
        microphone.stop()


    def test_echo_guard_drops_probable_speaker_echo_until_user_barge_in(self):
        fake = FakeSoundDevice()
        forwarded = []
        interruptions = []
        microphone = LiveMicrophone(
            on_audio=forwarded.append,
            on_local_barge_in=lambda: interruptions.append(True),
            output_state=lambda: (True, 0.25),
            sample_rate=16000,
            chunk_ms=40,
            noise_threshold=0.01,
            sounddevice_module=fake,
        )
        microphone.start()
        probable_echo = struct.pack("<" + "h" * 640, *([1200] * 640))
        fake.inputs[0].callback(probable_echo, 640, None, None)
        self.assertEqual(forwarded, [])
        self.assertEqual(interruptions, [])
        microphone.stop()

    def test_completed_live_turn_exposes_one_stable_result(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = LiveSessionManager(
                settings_file=os.path.join(temp, "live.json"),
                sounddevice_module=FakeSoundDevice(),
            )
            manager._current_input_transcript = "What is your name?"
            manager._current_output_transcript = "My name is Freshy."
            manager._complete_turn()
            status = manager.status()
            self.assertEqual(status.result_id, 1)
            self.assertTrue(status.result_token)
            self.assertEqual(status.last_input_transcript, "What is your name?")
            self.assertEqual(status.last_output_transcript, "My name is Freshy.")



    def test_fake_live_session_streams_audio_and_fails_soft_without_network(self):
        from types import SimpleNamespace
        from config import config

        class FakeSession:
            def __init__(self):
                self.receive_calls = 0

            async def send_realtime_input(self, **kwargs):
                self.last_input = kwargs

            async def send_tool_response(self, **kwargs):
                self.last_tool_response = kwargs

            async def receive(self):
                self.receive_calls += 1
                if self.receive_calls > 1:
                    raise RuntimeError("simulated disconnect")
                yield SimpleNamespace(
                    data=struct.pack("<" + "h" * 960, *([900] * 960)),
                    server_content=SimpleNamespace(
                        interrupted=False,
                        turn_complete=True,
                        input_transcription=SimpleNamespace(text="Hello Freshy"),
                        output_transcription=SimpleNamespace(text="Hello Pathan"),
                    ),
                    tool_call=None,
                    tool_call_cancellation=None,
                    session_resumption_update=None,
                )

            async def close(self):
                return None

        class ConnectContext:
            def __init__(self, owner, model, live_config):
                self.owner = owner
                self.model = model
                self.live_config = live_config
                self.session = FakeSession()

            async def __aenter__(self):
                self.owner.calls.append((self.model, self.live_config))
                return self.session

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class LiveEndpoint:
            def __init__(self, owner):
                self.owner = owner

            def connect(self, model, config):
                return ConnectContext(self.owner, model, config)

        class FakeClient:
            def __init__(self):
                self.calls = []
                self.aio = SimpleNamespace(live=LiveEndpoint(self))

        original_key = config.GEMINI_API_KEY
        fake_client = FakeClient()
        fallbacks = []
        try:
            config.GEMINI_API_KEY = "test-only-key"
            with tempfile.TemporaryDirectory() as temp:
                manager = LiveSessionManager(
                    settings_file=os.path.join(temp, "live.json"),
                    sounddevice_module=FakeSoundDevice(),
                    client_factory=lambda: fake_client,
                    fallback_callback=fallbacks.append,
                )
                manager.settings = manager.settings.model_copy(
                    update={
                        "conversation_mode": "live",
                        "reconnect_attempts": 0,
                        "fallback_mode": "standard",
                    }
                )
                with self.assertLogs("FreshyLiveSession", level="ERROR"):
                    started = manager.start()
                    self.assertTrue(started["accepted"])
                    deadline = time.time() + 2.0
                    while manager.is_running and time.time() < deadline:
                        time.sleep(0.01)
                status = manager.status()
                self.assertEqual(len(fake_client.calls), 1)
                self.assertEqual(status.last_input_transcript, "Hello Freshy")
                self.assertEqual(status.last_output_transcript, "Hello Pathan")
                self.assertEqual(status.conversation_mode, "standard")
                self.assertEqual(fallbacks, ["standard"])
                manager.stop()
        finally:
            config.GEMINI_API_KEY = original_key

    def test_live_memory_tools_use_phase5_privacy_service(self):
        class MemoryResult:
            success = True
            reply = "Theek hai, maine yaad rakh liya."
            error_code = None
            memory_count = 1
            pending_confirmation = False

        class Recall:
            context = "- [profile/name] Pathan"
            records = [object()]

        class MemoryService:
            def process_control_message(self, session_id, message):
                self.saved = (session_id, message)
                return MemoryResult()

            def recall(self, query):
                self.query = query
                return Recall()

        import asyncio
        memory = MemoryService()
        bridge = LiveToolBridge(memory_service=memory)

        class SaveCall:
            id = "memory-1"
            name = "memory_control"
            args = {"message": "Yaad rakho ki mera naam Pathan hai"}

        saved = asyncio.run(bridge.execute(SaveCall()))
        self.assertTrue(saved["response"]["success"])
        self.assertEqual(memory.saved[0], "live-voice-session")

        class LookupCall:
            id = "memory-2"
            name = "memory_lookup"
            args = {"query": "Mera naam kya hai?"}

        recalled = asyncio.run(bridge.execute(LookupCall()))
        self.assertIn("Pathan", recalled["response"]["output"])

    def test_live_turn_persistence_callback_receives_completed_pair(self):
        captured = []
        with tempfile.TemporaryDirectory() as temp:
            manager = LiveSessionManager(
                settings_file=os.path.join(temp, "live.json"),
                turn_persistence_callback=lambda user, assistant: captured.append((user, assistant)),
                sounddevice_module=FakeSoundDevice(),
            )
            manager._current_input_transcript = "Remember this conversation."
            manager._current_output_transcript = "I will keep the bounded history."
            manager._complete_turn()
        self.assertEqual(captured, [("Remember this conversation.", "I will keep the bounded history.")])

    def test_live_tool_bridge_uses_existing_registry_and_rejects_unknown(self):
        bridge = LiveToolBridge()

        class Call:
            id = "1"
            name = "get_time_date"
            args = {}

        import asyncio

        accepted = asyncio.run(bridge.execute(Call()))
        self.assertTrue(accepted["response"]["success"])

        class Unknown:
            id = "2"
            name = "run_powershell"
            args = {"command": "whoami"}

        rejected = asyncio.run(bridge.execute(Unknown()))
        self.assertFalse(rejected["response"]["success"])
        self.assertIn("not registered", rejected["response"]["error"].lower())


if __name__ == "__main__":
    unittest.main()
