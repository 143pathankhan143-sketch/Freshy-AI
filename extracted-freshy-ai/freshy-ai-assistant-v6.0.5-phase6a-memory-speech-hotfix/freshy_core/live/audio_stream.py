from __future__ import annotations

import logging
import queue
from collections import deque
import threading
import time
from typing import Any, Callable, Optional

try:
    from voice_activity import pcm16_rms
except ImportError:
    from freshy_core.voice_activity import pcm16_rms

logger = logging.getLogger("FreshyLiveAudio")


class LivePcmOutput:
    """Persistent raw PCM speaker stream with immediate queue flushing."""

    def __init__(
        self,
        sample_rate: int = 24000,
        block_ms: int = 20,
        buffer_ms: int = 80,
        sounddevice_module: Optional[Any] = None,
        on_playback_started: Optional[Callable[[], None]] = None,
        on_playback_stopped: Optional[Callable[[], None]] = None,
    ) -> None:
        self.sample_rate = int(sample_rate)
        self.block_frames = max(120, int(self.sample_rate * block_ms / 1000))
        self.prefill_bytes = max(self.block_frames * 2, int(self.sample_rate * 2 * buffer_ms / 1000))
        self._sd = sounddevice_module
        self._on_started = on_playback_started
        self._on_stopped = on_playback_stopped
        self._queue: queue.Queue[tuple[int, bytes]] = queue.Queue(maxsize=128)
        self._stop = threading.Event()
        self._flush_generation = 0
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stream: Optional[Any] = None
        self._playing = False
        self._output_level = 0.0
        self._last_error = ""
        self._underruns = 0

    @property
    def playing(self) -> bool:
        with self._lock:
            return self._playing

    @property
    def output_level(self) -> float:
        with self._lock:
            return self._output_level

    @property
    def underruns(self) -> int:
        with self._lock:
            return self._underruns

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="FreshyLiveOutput", daemon=True)
            self._thread.start()

    def enqueue(self, pcm: bytes) -> bool:
        if not pcm:
            return False
        self.start()
        with self._lock:
            generation = self._flush_generation
        try:
            self._queue.put_nowait((generation, bytes(pcm)))
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait((generation, bytes(pcm)))
            except queue.Full:
                return False
        return True

    def flush(self) -> None:
        with self._lock:
            self._flush_generation += 1
            was_playing = self._playing
            self._playing = False
            self._output_level = 0.0
            stream = self._stream
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        if stream is not None:
            try:
                stream.abort()
                stream.start()
            except Exception:
                pass
        if was_playing and self._on_stopped:
            self._on_stopped()

    def _ensure_stream(self) -> Any:
        if self._sd is None:
            import sounddevice as sd  # type: ignore
            self._sd = sd
        with self._lock:
            if self._stream is not None:
                return self._stream
            self._stream = self._sd.RawOutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.block_frames,
                latency="low",
            )
            self._stream.start()
            return self._stream

    def _set_playing(self, value: bool) -> None:
        callback = None
        with self._lock:
            if self._playing == value:
                return
            self._playing = value
            callback = self._on_started if value else self._on_stopped
        if callback:
            try:
                callback()
            except Exception:
                pass

    def _run(self) -> None:
        pending = bytearray()
        active_generation = -1
        while not self._stop.is_set():
            try:
                generation, packet = self._queue.get(timeout=0.05)
            except queue.Empty:
                if pending:
                    continue
                self._set_playing(False)
                continue
            with self._lock:
                current_generation = self._flush_generation
            if generation != current_generation:
                continue
            if active_generation != generation:
                pending.clear()
                active_generation = generation
            pending.extend(packet)
            while len(pending) < self.prefill_bytes and not self._stop.is_set():
                try:
                    next_generation, next_packet = self._queue.get(timeout=0.025)
                except queue.Empty:
                    break
                if next_generation == generation:
                    pending.extend(next_packet)
            try:
                stream = self._ensure_stream()
                block_bytes = self.block_frames * 2
                while pending and not self._stop.is_set():
                    with self._lock:
                        if generation != self._flush_generation:
                            pending.clear()
                            break
                    block = bytes(pending[:block_bytes])
                    del pending[:len(block)]
                    if not block:
                        break
                    self._set_playing(True)
                    with self._lock:
                        self._output_level = min(1.0, pcm16_rms(block) * 8.0)
                    stream.write(block)
            except Exception as exc:
                self._last_error = str(exc)[:240]
                logger.warning("Live PCM output failed: %s", self._last_error)
                self._set_playing(False)
                with self._lock:
                    self._stream = None
                    self._underruns += 1
                time.sleep(0.1)
        self._set_playing(False)

    def stop(self) -> None:
        self._stop.set()
        self.flush()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "playing": self._playing,
                "output_level": self._output_level,
                "queue_size": self._queue.qsize(),
                "underruns": self._underruns,
                "last_error": self._last_error,
                "sample_rate": self.sample_rate,
            }


class LiveMicrophone:
    """Continuous 16-bit mono microphone capture for Gemini Live."""

    def __init__(
        self,
        on_audio: Callable[[bytes], None],
        on_local_barge_in: Callable[[], None],
        output_state: Callable[[], tuple[bool, float]],
        on_speech_started: Optional[Callable[[], None]] = None,
        on_speech_ended: Optional[Callable[[], None]] = None,
        sample_rate: int = 16000,
        chunk_ms: int = 40,
        device_index: Optional[int] = None,
        noise_threshold: float = 0.018,
        echo_guard_enabled: bool = True,
        sounddevice_module: Optional[Any] = None,
    ) -> None:
        self.on_audio = on_audio
        self.on_local_barge_in = on_local_barge_in
        self.output_state = output_state
        self.on_speech_started = on_speech_started
        self.on_speech_ended = on_speech_ended
        self.sample_rate = int(sample_rate)
        self.chunk_frames = max(160, int(sample_rate * chunk_ms / 1000))
        self.device_index = device_index
        self.noise_threshold = float(noise_threshold)
        self.echo_guard_enabled = bool(echo_guard_enabled)
        self._sd = sounddevice_module
        self._stream: Optional[Any] = None
        self._muted = False
        self._level = 0.0
        self._speech_votes = 0
        self._last_barge_in = 0.0
        self._speech_active = False
        self._silence_votes = 0
        self._barge_active = False
        self._barge_silence_votes = 0
        self._pre_roll: deque[bytes] = deque(maxlen=6)
        self._lock = threading.RLock()
        self._last_error = ""

    @property
    def active(self) -> bool:
        with self._lock:
            return self._stream is not None

    @property
    def level(self) -> float:
        with self._lock:
            return self._level

    @property
    def muted(self) -> bool:
        with self._lock:
            return self._muted

    def set_muted(self, value: bool) -> None:
        with self._lock:
            self._muted = bool(value)

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
        if self._sd is None:
            import sounddevice as sd  # type: ignore
            self._sd = sd
        stream = self._sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_frames,
            device=self.device_index,
            callback=self._callback,
        )
        stream.start()
        with self._lock:
            self._stream = stream
            self._last_error = ""

    def _emit_audio(self, pcm: bytes) -> None:
        try:
            self.on_audio(pcm)
        except Exception:
            pass

    def _update_speech_state(self, is_speech: bool) -> None:
        if is_speech:
            self._silence_votes = 0
            if not self._speech_active:
                self._speech_active = True
                if self.on_speech_started:
                    try:
                        self.on_speech_started()
                    except Exception:
                        pass
            return
        if not self._speech_active:
            return
        self._silence_votes += 1
        if self._silence_votes >= 8:
            self._speech_active = False
            self._silence_votes = 0
            if self.on_speech_ended:
                try:
                    self.on_speech_ended()
                except Exception:
                    pass

    def _callback(self, indata: Any, frames: int, time_info: Any, status: Any) -> None:
        del frames, time_info
        if status:
            self._last_error = str(status)[:180]
        pcm = bytes(indata)
        rms = pcm16_rms(pcm)
        level = min(1.0, rms * 8.0)
        with self._lock:
            self._level = level
            muted = self._muted
        if muted:
            return

        output_playing, output_level = self.output_state()
        base_speech_threshold = self.noise_threshold * 1.35
        if not output_playing:
            self._barge_active = False
            self._barge_silence_votes = 0
            self._speech_votes = 0
            self._pre_roll.clear()
            self._emit_audio(pcm)
            self._update_speech_state(rms >= base_speech_threshold)
            return

        # While Freshy is speaking, do not continuously send speaker echo back
        # into the Live session. Keep a short pre-roll and release it only after
        # sustained user speech is confirmed. This preserves first words while
        # preventing self-interruption loops on open speakers.
        self._pre_roll.append(pcm)
        threshold = self.noise_threshold * 1.6
        if self.echo_guard_enabled:
            threshold = max(threshold, output_level * 0.34 + self.noise_threshold)

        if self._barge_active:
            self._emit_audio(pcm)
            is_speech = rms >= base_speech_threshold
            self._update_speech_state(is_speech)
            if is_speech:
                self._barge_silence_votes = 0
            else:
                self._barge_silence_votes += 1
                if self._barge_silence_votes >= 8:
                    self._barge_active = False
                    self._barge_silence_votes = 0
            return

        if rms >= threshold:
            self._speech_votes += 1
        else:
            self._speech_votes = max(0, self._speech_votes - 1)

        now = time.monotonic()
        if self._speech_votes < 2 or now - self._last_barge_in < 0.45:
            return

        self._last_barge_in = now
        self._speech_votes = 0
        self._barge_active = True
        self._barge_silence_votes = 0
        try:
            self.on_local_barge_in()
        except Exception:
            pass
        while self._pre_roll:
            self._emit_audio(self._pre_roll.popleft())
        self._update_speech_state(True)

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
            self._level = 0.0
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active": self._stream is not None,
                "muted": self._muted,
                "input_level": self._level,
                "last_error": self._last_error,
                "sample_rate": self.sample_rate,
                "chunk_frames": self.chunk_frames,
            }
