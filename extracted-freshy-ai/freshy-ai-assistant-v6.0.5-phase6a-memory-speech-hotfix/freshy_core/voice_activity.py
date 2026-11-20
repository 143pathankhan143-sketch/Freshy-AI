from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Any, Optional


def pcm16_rms(pcm_bytes: bytes) -> float:
    """Return normalized RMS for little-endian mono 16-bit PCM."""
    sample_count = len(pcm_bytes) // 2
    if sample_count <= 0:
        return 0.0
    try:
        usable = pcm_bytes[: sample_count * 2]
        samples = struct.unpack(f"<{sample_count}h", usable)
        sum_sq = sum((sample / 32768.0) ** 2 for sample in samples)
        return math.sqrt(sum_sq / sample_count)
    except (struct.error, TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class VadDecision:
    is_speech: bool
    score: float
    engine: str


class AdaptiveVoiceActivityDetector:
    """
    Optional WebRTC VAD with a deterministic RMS fallback.

    The detector accepts Freshy's 100 ms, 16 kHz mono PCM chunks and internally
    splits them into 20 ms frames for WebRTC. If the optional dependency is not
    available, calibrated RMS remains fully functional.
    """

    _MODE_BY_SENSITIVITY = {"low": 3, "normal": 2, "high": 1}
    _RMS_MULTIPLIER = {"low": 1.9, "normal": 1.45, "high": 1.15}

    def __init__(
        self,
        sample_rate: int = 16_000,
        sensitivity: str = "normal",
        webrtcvad_module: Optional[Any] = None,
        preferred_engine: str = "auto",
    ) -> None:
        self.sample_rate = sample_rate
        self.sensitivity = self._normalize_sensitivity(sensitivity)
        self.preferred_engine = self._normalize_engine(preferred_engine)
        self._webrtcvad_module = webrtcvad_module
        self._vad: Optional[Any] = None
        self._initialize_webrtc()

    @staticmethod
    def _normalize_engine(value: str) -> str:
        value = str(value or "auto").strip().lower()
        return value if value in {"auto", "webrtc", "adaptive_rms"} else "auto"

    @staticmethod
    def _normalize_sensitivity(value: str) -> str:
        value = str(value or "normal").strip().lower()
        return value if value in {"low", "normal", "high"} else "normal"

    def _initialize_webrtc(self) -> None:
        if self.preferred_engine == "adaptive_rms":
            self._vad = None
            return
        module = self._webrtcvad_module
        if module is None:
            try:
                import webrtcvad  # type: ignore

                module = webrtcvad
            except Exception:
                module = None
        self._webrtcvad_module = module
        if module is None:
            self._vad = None
            return
        try:
            self._vad = module.Vad(self._MODE_BY_SENSITIVITY[self.sensitivity])
        except Exception:
            self._vad = None

    @property
    def engine_name(self) -> str:
        return "webrtc" if self._vad is not None else "adaptive_rms"

    def set_preferred_engine(self, value: str) -> None:
        self.preferred_engine = self._normalize_engine(value)
        self._vad = None
        self._initialize_webrtc()

    def set_sensitivity(self, value: str) -> None:
        self.sensitivity = self._normalize_sensitivity(value)
        if self._vad is not None:
            try:
                self._vad.set_mode(self._MODE_BY_SENSITIVITY[self.sensitivity])
            except Exception:
                self._initialize_webrtc()

    def decide(self, pcm_bytes: bytes, calibrated_threshold: float) -> VadDecision:
        rms = pcm16_rms(pcm_bytes)
        threshold = max(0.001, float(calibrated_threshold))

        if self._vad is not None and pcm_bytes:
            # 20 ms at 16 kHz, 16-bit mono = 640 bytes.
            frame_bytes = int(self.sample_rate * 0.02) * 2
            votes = 0
            frames = 0
            for offset in range(0, len(pcm_bytes) - frame_bytes + 1, frame_bytes):
                frame = pcm_bytes[offset : offset + frame_bytes]
                try:
                    frames += 1
                    if self._vad.is_speech(frame, self.sample_rate):
                        votes += 1
                except Exception:
                    frames = 0
                    break
            if frames:
                ratio = votes / frames
                required = {"low": 0.60, "normal": 0.40, "high": 0.20}[self.sensitivity]
                # Require a small acoustic floor even when WebRTC votes speech.
                floor = threshold * {"low": 0.85, "normal": 0.65, "high": 0.45}[self.sensitivity]
                return VadDecision(
                    is_speech=ratio >= required and rms >= floor,
                    score=max(ratio, min(1.0, rms / max(threshold, 1e-6))),
                    engine="webrtc",
                )

        multiplier = self._RMS_MULTIPLIER[self.sensitivity]
        score = min(1.0, rms / max(threshold * multiplier, 1e-6))
        return VadDecision(
            is_speech=rms >= threshold * multiplier,
            score=score,
            engine="adaptive_rms",
        )
