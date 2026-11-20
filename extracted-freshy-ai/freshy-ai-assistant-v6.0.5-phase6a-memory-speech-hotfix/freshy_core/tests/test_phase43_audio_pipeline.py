import io
import json
import os
import struct
import sys
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(__file__))

from audio_output import AudioPlaybackError, StableAudioPlayer, normalize_wav_bytes
from human_tts_service import HumanVoiceProfileStore, XTTSHumanTTS
from tts_service import TTSService, split_speech_chunks
from test_tts import FakeEngine, wait_for


def make_wav(
    duration_seconds=0.12,
    sample_rate=16000,
    channels=1,
    amplitude=4000,
    leading_silence=0.0,
    trailing_silence=0.0,
):
    frames = []
    frames.extend([0] * int(sample_rate * leading_silence))
    frames.extend([amplitude] * int(sample_rate * duration_seconds))
    frames.extend([0] * int(sample_rate * trailing_silence))
    pcm = struct.pack("<" + "h" * len(frames), *frames)
    if channels == 2:
        stereo = []
        for value in frames:
            stereo.extend((value, value))
        pcm = struct.pack("<" + "h" * len(stereo), *stereo)
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(pcm)
    return output.getvalue()


class FakeRawOutputStream:
    def __init__(self, fail_after_writes=None):
        self.active = False
        self.writes = []
        self.fail_after_writes = fail_after_writes
        self.aborted = False
        self.closed = False

    def start(self):
        self.active = True

    def write(self, block):
        if self.fail_after_writes is not None and len(self.writes) >= self.fail_after_writes:
            raise RuntimeError("injected PortAudio write failure")
        self.writes.append(bytes(block))

    def abort(self):
        self.aborted = True
        self.active = False

    def stop(self):
        self.active = False

    def close(self):
        self.closed = True


class FakeSoundDevice:
    def __init__(self, fail_after_writes=None):
        self.created = []
        self.fail_after_writes = fail_after_writes

    def RawOutputStream(self, **kwargs):
        stream = FakeRawOutputStream(self.fail_after_writes)
        stream.kwargs = kwargs
        self.created.append(stream)
        return stream


class RecordingFallback:
    def __init__(self):
        self.played = []
        self.stop_calls = 0

    def play(self, payload):
        self.played.append(payload)
        return True

    def stop(self):
        self.stop_calls += 1


class FakeNatural:
    def __init__(self, delay=0.0, fail=False):
        self.delay = delay
        self.fail = fail
        self.calls = []

    def is_configured(self):
        return True

    def generate_wav(self, text, **kwargs):
        self.calls.append((text, kwargs))
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("injected Gemini failure")
        return make_wav(duration_seconds=0.04)


class BlockingPlayer:
    def __init__(self):
        self.play_started = threading.Event()
        self.release = threading.Event()
        self.played = []
        self.stop_calls = 0
        self.trim = True

    def play(self, payload):
        self.played.append(payload)
        self.play_started.set()
        self.release.wait(2.0)
        return True

    def stop(self):
        self.stop_calls += 1
        self.release.set()

    def set_trim_silence(self, enabled):
        self.trim = bool(enabled)

    def set_stream_enabled(self, enabled):
        pass

    def status(self):
        return {"backend": "blocking_fake"}


class FakeResponse:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


class FakeRequests:
    def __init__(self, wav):
        self.wav = wav
        self.posts = []
        self.gets = []

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return FakeResponse(200)

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse(200, self.wav)


class Phase43StableAudioTests(unittest.TestCase):
    def test_wav_normalization_uses_one_pcm_format_and_trims_only_edges(self):
        source = make_wav(
            duration_seconds=0.08,
            sample_rate=16000,
            channels=2,
            leading_silence=0.15,
            trailing_silence=0.15,
        )
        normalized = normalize_wav_bytes(source, trim_silence=True)
        self.assertEqual(normalized.sample_rate, 24000)
        self.assertEqual(normalized.channels, 1)
        self.assertEqual(normalized.sample_width, 2)
        self.assertGreater(len(normalized.pcm), 0)
        self.assertLess(normalized.duration_seconds, 0.28)

    def test_persistent_stream_is_reused_across_packets(self):
        sd = FakeSoundDevice()
        player = StableAudioPlayer(sounddevice_module=sd, fallback_player=RecordingFallback())
        self.assertTrue(player.play(make_wav()))
        self.assertTrue(player.play(make_wav()))
        self.assertEqual(len(sd.created), 1)
        self.assertGreaterEqual(len(sd.created[0].writes), 2)
        self.assertEqual(player.status()["backend"], "sounddevice_raw_stream")
        player.close()

    def test_partial_stream_failure_never_replays_packet_from_start(self):
        sd = FakeSoundDevice(fail_after_writes=1)
        fallback = RecordingFallback()
        player = StableAudioPlayer(sounddevice_module=sd, fallback_player=fallback)
        with self.assertRaises(AudioPlaybackError):
            player.play(make_wav(duration_seconds=0.08))
        self.assertEqual(fallback.played, [])
        player.close()

    def test_stream_failure_before_audio_can_use_wav_fallback_once(self):
        sd = FakeSoundDevice(fail_after_writes=0)
        fallback = RecordingFallback()
        player = StableAudioPlayer(sounddevice_module=sd, fallback_player=fallback)
        self.assertTrue(player.play(make_wav(duration_seconds=0.04)))
        self.assertEqual(len(fallback.played), 1)
        player.close()

    def test_short_first_chunk_never_splits_inside_a_word(self):
        text = (
            "Freshy gives a short first sentence. "
            "This continuation contains several technical words and should stay ordered."
        )
        chunks = split_speech_chunks(text, max_characters=120, first_chunk_characters=80)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(" ".join(chunks), text)
        self.assertTrue(all(chunk and not chunk.startswith(" ") for chunk in chunks))


class Phase43HumanVoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _reference(self, name):
        path = self.root / name
        path.write_bytes(make_wav(duration_seconds=3.1, sample_rate=16000))
        return str(path)

    def test_multiple_consented_references_install_as_one_profile(self):
        store = HumanVoiceProfileStore(str(self.root / "profiles"))
        profile = store.install_profile(
            profile_id="natural_male",
            label="Natural Male",
            reference_wavs=[self._reference("one.wav"), self._reference("two.wav")],
            language="hi",
        )
        self.assertEqual(profile.id, "natural_male")
        self.assertEqual(len(profile.reference_wavs), 2)
        public = profile.to_public_dict()
        self.assertEqual(public["reference_count"], 2)
        manifest = json.loads(
            (self.root / "profiles" / "natural_male" / "manifest.json").read_text()
        )
        self.assertEqual(len(manifest["reference_wavs"]), 2)

    def test_xtts_server_client_sends_profile_id_not_arbitrary_path(self):
        store = HumanVoiceProfileStore(str(self.root / "profiles"))
        profile = store.install_profile(
            profile_id="my_voice",
            label="My Voice",
            reference_wav=self._reference("voice.wav"),
            language="hi",
        )
        requests = FakeRequests(make_wav())
        service = XTTSHumanTTS(
            mode="server",
            server_url="http://127.0.0.1:8020",
            server_token="secret",
            profile_store=store,
            requests_module=requests,
        )
        payload = service.generate_wav(
            "नमस्ते Freshy",
            voice_profile=profile.id,
            speech_language="hi-IN",
            volume=0.8,
        )
        self.assertEqual(payload[:4], b"RIFF")
        sent = requests.posts[0][1]["json"]
        self.assertEqual(sent["profile_id"], "my_voice")
        self.assertNotIn("reference_wav", sent)
        self.assertEqual(sent["language"], "hi")


class Phase43ExclusiveRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = FakeEngine()

    def _service(self, natural, player=None):
        path = os.path.join(self.temp.name, "tts.json")
        service = TTSService(
            settings_file=path,
            engine_factory=lambda: self.engine,
            com_initialize=lambda: None,
            com_uninitialize=lambda: None,
            natural_tts_factory=lambda: natural,
            natural_audio_player=player or BlockingPlayer(),
        )
        self.addCleanup(lambda: service.shutdown(timeout=0.5))
        self.assertTrue(wait_for(lambda: service.get_status()["engine_available"]))
        return service

    def test_gemini_failure_does_not_activate_david_or_zira_automatically(self):
        service = self._service(FakeNatural(fail=True))
        service.update_settings(
            {"provider": "gemini", "failure_behavior": "silent", "fallback_provider": "none"}
        )
        self.assertTrue(service.speak("Text remains visible")["accepted"])
        self.assertTrue(wait_for(lambda: service.get_status()["queue_size"] == 0))
        self.assertEqual(self.engine.said_utterances, [])

    def test_generation_continues_while_first_audio_chunk_is_playing(self):
        natural = FakeNatural()
        player = BlockingPlayer()
        service = self._service(natural, player)
        service.update_settings(
            {
                "provider": "gemini",
                "fast_start_enabled": True,
                "first_chunk_characters": 80,
                "fast_chunk_characters": 120,
            }
        )
        text = (
            "Freshy starts speaking this short sentence. "
            "The second sentence is generated while the first packet is still playing."
        )
        result = service.speak(text)
        self.assertGreaterEqual(result["chunk_count"], 2)
        self.assertTrue(player.play_started.wait(1.0))
        self.assertTrue(wait_for(lambda: len(natural.calls) >= 2))
        player.release.set()
        self.assertTrue(wait_for(lambda: service.get_status()["queue_size"] == 0))


    def test_changing_gemini_voice_profile_invalidates_old_generated_audio(self):
        natural = FakeNatural(delay=0.12)
        player = BlockingPlayer()
        service = self._service(natural, player)
        service.update_settings({"provider": "gemini", "natural_voice": "hindi_female"})
        service.speak("This old female profile packet must be discarded.")
        service.update_settings({"natural_voice": "hindi_male"})
        self.assertTrue(wait_for(lambda: service.get_status()["queue_size"] == 0))
        self.assertEqual(player.played, [])

    def test_switching_to_windows_voice_invalidates_old_neural_audio(self):
        natural = FakeNatural(delay=0.12)
        player = BlockingPlayer()
        service = self._service(natural, player)
        service.update_settings({"provider": "gemini"})
        service.speak("This old Gemini packet must be discarded after switching.")
        service.update_settings({"provider": "system", "selected_voice": "voice_1"})
        service.speak("Windows voice selected explicitly")
        self.assertTrue(wait_for(lambda: len(self.engine.said_utterances) == 1))
        self.assertEqual(player.played, [])
        self.assertEqual(self.engine.said_utterances[0][0], "Windows voice selected explicitly")


if __name__ == "__main__":
    unittest.main()
