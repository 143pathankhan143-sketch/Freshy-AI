"""Stable, exclusive PCM audio playback for Freshy Phase 4.3.

The previous Gemini path opened and purged a new temporary WAV for every text
chunk. That design can create audible gaps and device races. This module keeps a
single output stream open, normalizes every WAV to one PCM format, trims only
excessive boundary silence, and supports immediate cancellation.
"""

from __future__ import annotations

import audioop
import io
import logging
import sys
import threading
import time
import wave
from array import array
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("FreshyAudioOutput")

TARGET_RATE = 24_000
TARGET_CHANNELS = 1
TARGET_WIDTH = 2


class AudioPlaybackError(RuntimeError):
    """Playback failure that records whether audible data had already started."""

    def __init__(self, message: str, partial_playback: bool = False) -> None:
        super().__init__(message)
        self.partial_playback = bool(partial_playback)


@dataclass(frozen=True)
class NormalizedAudio:
    pcm: bytes
    sample_rate: int = TARGET_RATE
    channels: int = TARGET_CHANNELS
    sample_width: int = TARGET_WIDTH

    @property
    def duration_seconds(self) -> float:
        bytes_per_second = self.sample_rate * self.channels * self.sample_width
        return len(self.pcm) / max(1, bytes_per_second)


def _pcm16_samples(pcm: bytes) -> array:
    even = len(pcm) - (len(pcm) % 2)
    samples = array("h")
    samples.frombytes(pcm[:even])
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _trim_boundary_silence(
    pcm: bytes,
    sample_rate: int,
    threshold: int = 220,
    max_trim_ms: int = 220,
    keep_ms: int = 12,
) -> bytes:
    """Trim only long low-energy padding, never ordinary pauses inside speech."""
    samples = _pcm16_samples(pcm)
    if not samples:
        return pcm
    max_trim = int(sample_rate * max_trim_ms / 1000)
    keep = int(sample_rate * keep_ms / 1000)

    first_loud = 0
    upper = min(len(samples), max_trim)
    while first_loud < upper and abs(samples[first_loud]) <= threshold:
        first_loud += 1

    last_loud = len(samples) - 1
    lower = max(0, len(samples) - max_trim)
    while last_loud >= lower and abs(samples[last_loud]) <= threshold:
        last_loud -= 1

    start = max(0, first_loud - keep)
    end = min(len(samples), last_loud + keep + 1)
    if end <= start:
        return pcm
    trimmed = samples[start:end]
    if sys.byteorder != "little":
        trimmed.byteswap()
    return trimmed.tobytes()


def _apply_short_fade(pcm: bytes, sample_rate: int, fade_ms: int = 4) -> bytes:
    samples = _pcm16_samples(pcm)
    if not samples:
        return pcm
    fade = min(len(samples) // 2, int(sample_rate * fade_ms / 1000))
    if fade <= 1:
        return pcm
    for index in range(fade):
        factor = index / fade
        samples[index] = int(samples[index] * factor)
        tail = len(samples) - index - 1
        samples[tail] = int(samples[tail] * factor)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def normalize_wav_bytes(
    wav_bytes: bytes,
    target_rate: int = TARGET_RATE,
    trim_silence: bool = True,
) -> NormalizedAudio:
    if not wav_bytes:
        raise ValueError("Audio payload is empty")
    with wave.open(io.BytesIO(wav_bytes), "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        frames = source.readframes(source.getnframes())

    if not frames:
        raise ValueError("WAV payload contains no frames")
    if width != TARGET_WIDTH:
        frames = audioop.lin2lin(frames, width, TARGET_WIDTH)
        width = TARGET_WIDTH
    if channels == 2:
        frames = audioop.tomono(frames, width, 0.5, 0.5)
        channels = 1
    elif channels != 1:
        raise ValueError(f"Unsupported WAV channel count: {channels}")
    if rate != target_rate:
        frames, _state = audioop.ratecv(
            frames,
            width,
            channels,
            rate,
            target_rate,
            None,
        )
        rate = target_rate
    if trim_silence:
        frames = _trim_boundary_silence(frames, rate)
    frames = _apply_short_fade(frames, rate)
    return NormalizedAudio(frames, rate, channels, width)


class SoundDeviceStreamPlayer:
    """One reusable low-latency output stream with cooperative cancellation."""

    def __init__(
        self,
        sounddevice_module: Optional[Any] = None,
        sample_rate: int = TARGET_RATE,
        block_ms: int = 20,
        trim_silence: bool = True,
    ) -> None:
        if sounddevice_module is None:
            import sounddevice as sounddevice_module  # type: ignore
        self._sd = sounddevice_module
        self.sample_rate = sample_rate
        self.block_frames = max(120, int(sample_rate * block_ms / 1000))
        self.trim_silence = trim_silence
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._stream: Optional[Any] = None
        self._generation = 0
        self._last_error = ""
        self._played_packets = 0

    @property
    def backend_name(self) -> str:
        return "sounddevice_raw_stream"

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def played_packets(self) -> int:
        return self._played_packets

    def _ensure_stream(self) -> Any:
        with self._lock:
            if self._stream is not None:
                try:
                    if not getattr(self._stream, "active", True):
                        self._stream.start()
                    return self._stream
                except Exception:
                    self._close_stream_locked()
            self._stream = self._sd.RawOutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.block_frames,
                latency="low",
            )
            self._stream.start()
            return self._stream

    def set_trim_silence(self, enabled: bool) -> None:
        with self._lock:
            self.trim_silence = bool(enabled)

    def play(self, wav_bytes: bytes) -> bool:
        with self._lock:
            trim_silence = self.trim_silence
        audio = normalize_wav_bytes(
            wav_bytes,
            target_rate=self.sample_rate,
            trim_silence=trim_silence,
        )
        with self._lock:
            generation = self._generation
            self._stop_event.clear()
        wrote_any = False
        try:
            stream = self._ensure_stream()
            block_bytes = self.block_frames * TARGET_WIDTH
            offset = 0
            while offset < len(audio.pcm):
                with self._lock:
                    cancelled = generation != self._generation or self._stop_event.is_set()
                if cancelled:
                    return False
                block = audio.pcm[offset : offset + block_bytes]
                stream.write(block)
                wrote_any = wrote_any or bool(block)
                offset += len(block)
            self._played_packets += 1
            self._last_error = ""
            return True
        except Exception as exc:
            self._last_error = str(exc)[:240]
            logger.warning("Stable audio stream failed: %s", self._last_error)
            with self._lock:
                self._close_stream_locked()
            raise AudioPlaybackError(
                f"Stable audio playback failed: {self._last_error}",
                partial_playback=wrote_any,
            ) from exc

    def stop(self) -> None:
        with self._lock:
            self._generation += 1
            self._stop_event.set()
            stream = self._stream
        if stream is not None:
            try:
                stream.abort()
            except Exception:
                pass

    def _close_stream_locked(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass

    def close(self) -> None:
        self.stop()
        with self._lock:
            self._close_stream_locked()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "backend": self.backend_name,
                "stream_open": self._stream is not None,
                "sample_rate": self.sample_rate,
                "block_frames": self.block_frames,
                "last_error": self._last_error,
                "played_packets": self._played_packets,
            }


class StableAudioPlayer:
    """Primary stream player with the old Windows player as a last-resort fallback."""

    def __init__(
        self,
        sounddevice_module: Optional[Any] = None,
        fallback_player: Optional[Any] = None,
        trim_silence: bool = True,
        stream_enabled: bool = True,
    ) -> None:
        self._stream_player: Optional[SoundDeviceStreamPlayer] = None
        self._stream_enabled = bool(stream_enabled)
        if self._stream_enabled:
            try:
                self._stream_player = SoundDeviceStreamPlayer(
                    sounddevice_module=sounddevice_module,
                    trim_silence=trim_silence,
                )
            except Exception as exc:
                logger.warning("Stable sounddevice output unavailable: %s", str(exc)[:180])
        self._fallback = fallback_player
        self._last_backend = "none"
        self._last_error = ""
        self._lock = threading.RLock()

    def set_trim_silence(self, enabled: bool) -> None:
        if self._stream_player is not None:
            self._stream_player.set_trim_silence(enabled)

    def set_stream_enabled(self, enabled: bool) -> None:
        # Creating a sounddevice stream requires the original dependency/module,
        # so runtime enabling is supported only when a stream player already exists.
        with self._lock:
            self._stream_enabled = bool(enabled)

    def play(self, wav_bytes: bytes) -> bool:
        with self._lock:
            use_stream = self._stream_enabled and self._stream_player is not None
        if use_stream:
            try:
                result = self._stream_player.play(wav_bytes)
                self._last_backend = self._stream_player.backend_name
                self._last_error = ""
                return result
            except AudioPlaybackError as exc:
                self._last_error = str(exc)[:240]
                # Never replay a packet from the beginning after partial output: that
                # is a common source of overlapping/duplicated words.
                if exc.partial_playback:
                    raise
            except Exception as exc:
                self._last_error = str(exc)[:240]
        if self._fallback is None:
            raise RuntimeError(self._last_error or "No audio output backend is available")
        result = bool(self._fallback.play(wav_bytes))
        self._last_backend = "windows_wav_fallback"
        return result

    def stop(self) -> None:
        if self._stream_player is not None:
            self._stream_player.stop()
        if self._fallback is not None:
            try:
                self._fallback.stop()
            except Exception:
                pass

    def close(self) -> None:
        if self._stream_player is not None:
            self._stream_player.close()
        if self._fallback is not None:
            close = getattr(self._fallback, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def status(self) -> dict[str, Any]:
        detail = self._stream_player.status() if self._stream_player else {}
        return {
            "backend": self._last_backend or detail.get("backend", "none"),
            "last_error": self._last_error,
            "stream_enabled": self._stream_enabled,
            "stream": detail,
        }
