"""Natural online speech generation for Freshy.

This module is intentionally isolated from the existing SAPI5 worker so local
Windows speech remains available offline. Gemini is imported lazily and no key
is logged or persisted here.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
import sys
import tempfile
import threading
import time
import wave
from array import array
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("FreshyNaturalTTS")

DEFAULT_SAMPLE_RATE = 24_000
MAX_TTS_TEXT_LENGTH = 1_500
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_ -]?key|authorization|bearer)(\s*[:=]?\s*)[^\s,;]+"
)


@dataclass(frozen=True)
class NaturalVoiceProfile:
    id: str
    label: str
    voice_name: str
    persona: str


NATURAL_VOICE_PROFILES: Dict[str, NaturalVoiceProfile] = {
    "hindi_female": NaturalVoiceProfile(
        id="hindi_female",
        label="Hindi / Hinglish — Female (Natural)",
        voice_name="Kore",
        persona="a warm, natural adult Indian female assistant",
    ),
    "hindi_male": NaturalVoiceProfile(
        id="hindi_male",
        label="Hindi / Hinglish — Male (Natural)",
        voice_name="Charon",
        persona="a calm, natural adult Indian male assistant",
    ),
}


VOICE_STYLE_GUIDANCE = {
    "natural": "warm, clear, conversational, expressive, and human; avoid a robotic cadence",
    "warm": "warm, friendly, reassuring, and naturally expressive",
    "calm": "calm, measured, confident, and softly conversational",
    "professional": "professional, concise, articulate, and composed",
    "cinematic": "deeply composed, intelligent, cinematic, and controlled without exaggeration",
}
LANGUAGE_GUIDANCE = {
    "auto": (
        "Detect the transcript language automatically. Use natural Indian pronunciation "
        "for Hindi, Urdu, Hinglish, and Indian English."
    ),
    "hi-IN": (
        "Use natural Indian Hindi/Hinglish pronunciation. Pronounce English technical "
        "terms clearly without translating them."
    ),
    "en-IN": "Use clear, natural Indian English pronunciation.",
}


def _safe_error(value: object, limit: int = 240) -> str:
    return _SECRET_PATTERN.sub(r"\1\2[REDACTED]", str(value))[:limit]


def _rate_guidance(rate: int) -> str:
    if rate <= 120:
        return "slow and relaxed"
    if rate <= 190:
        return "natural conversational speed"
    if rate <= 260:
        return "slightly fast but clear"
    return "fast but still clearly understandable"


def _parse_sample_rate(mime_type: str) -> int:
    match = re.search(r"(?:^|[;\s])rate=(\d{4,6})(?:$|[;\s])", mime_type or "", re.I)
    parsed = int(match.group(1)) if match else DEFAULT_SAMPLE_RATE
    return parsed if 8_000 <= parsed <= 96_000 else DEFAULT_SAMPLE_RATE


def _scale_pcm16(pcm: bytes, volume: float) -> bytes:
    if not pcm or volume >= 0.999:
        return pcm
    safe_volume = max(0.0, min(1.0, float(volume)))
    even_length = len(pcm) - (len(pcm) % 2)
    samples = array("h")
    samples.frombytes(pcm[:even_length])
    if sys.byteorder != "little":
        samples.byteswap()
    for index, sample in enumerate(samples):
        scaled = int(sample * safe_volume)
        samples[index] = max(-32768, min(32767, scaled))
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def wrap_pcm16_mono_as_wav(
    pcm: bytes,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    volume: float = 1.0,
) -> bytes:
    pcm = _scale_pcm16(pcm, volume)
    if not pcm:
        raise RuntimeError("Gemini TTS returned empty PCM audio.")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return output.getvalue()


def _scale_wav_volume(wav_bytes: bytes, volume: float) -> bytes:
    if volume >= 0.999:
        return wav_bytes
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as source:
            params = source.getparams()
            frames = source.readframes(source.getnframes())
        if params.sampwidth != 2:
            return wav_bytes
        scaled = _scale_pcm16(frames, volume)
        output = io.BytesIO()
        with wave.open(output, "wb") as target:
            target.setparams(params)
            target.writeframes(scaled)
        return output.getvalue()
    except Exception:
        return wav_bytes


def ensure_wav(audio: bytes, mime_type: str, volume: float = 1.0) -> bytes:
    if not audio:
        raise RuntimeError("Gemini TTS returned empty audio.")
    if len(audio) >= 12 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE":
        return _scale_wav_volume(audio, volume)
    return wrap_pcm16_mono_as_wav(
        audio,
        sample_rate=_parse_sample_rate(mime_type),
        volume=volume,
    )


class GeminiNaturalTTS:
    """Generates natural Hindi/Hinglish WAV speech through Gemini TTS."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: int = 30,
        client: Optional[Any] = None,
    ) -> None:
        self._api_key = str(api_key or "").strip()
        self.model = str(model or "gemini-2.5-flash-preview-tts").strip()
        self.timeout_seconds = max(5, min(90, int(timeout_seconds)))
        self._client = client
        self._types: Optional[Any] = None
        self._initialization_error = ""

        if self._client is None and self.is_configured():
            try:
                from google import genai
                from google.genai import types

                self._types = types
                try:
                    http_options = types.HttpOptions(timeout=self.timeout_seconds * 1000)
                    self._client = genai.Client(
                        api_key=self._api_key,
                        http_options=http_options,
                    )
                except Exception:
                    self._client = genai.Client(api_key=self._api_key)
            except Exception as exc:  # optional runtime dependency
                self._initialization_error = _safe_error(exc)
                logger.warning(
                    "Gemini natural TTS could not initialize: %s",
                    self._initialization_error,
                )

    def is_configured(self) -> bool:
        dummy = {"", "my_gemini_api_key", "your_gemini_key", "your_actual_gemini_api_key_here"}
        return self._api_key.lower() not in dummy and bool(self.model)

    def is_available(self) -> bool:
        return self.is_configured() and self._client is not None

    @property
    def initialization_error(self) -> str:
        return self._initialization_error

    @staticmethod
    def voice_profiles() -> list[dict[str, str]]:
        return [
            {
                "id": item.id,
                "label": item.label,
                "voice_name": item.voice_name,
            }
            for item in NATURAL_VOICE_PROFILES.values()
        ]

    def _generation_config(self, voice_name: str) -> Any:
        config_dict: Dict[str, Any] = {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": voice_name}
                }
            },
        }
        if self._types is None:
            return config_dict
        try:
            return self._types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=self._types.SpeechConfig(
                    voice_config=self._types.VoiceConfig(
                        prebuilt_voice_config=self._types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
            )
        except Exception:
            return config_dict

    @staticmethod
    def _extract_audio(response: Any) -> tuple[bytes, str]:
        candidates = list(getattr(response, "candidates", None) or [])
        if not candidates:
            raise RuntimeError("Gemini TTS returned no audio candidate.")
        content = getattr(candidates[0], "content", None)
        parts = list(getattr(content, "parts", None) or [])
        for part in parts:
            inline = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
            if inline is None:
                continue
            data = getattr(inline, "data", None)
            mime_type = str(
                getattr(inline, "mime_type", None)
                or getattr(inline, "mimeType", None)
                or "audio/L16;rate=24000"
            )
            if isinstance(data, bytes):
                return data, mime_type
            if isinstance(data, bytearray):
                return bytes(data), mime_type
            if isinstance(data, str) and data:
                try:
                    return base64.b64decode(data, validate=True), mime_type
                except Exception:
                    return data.encode("latin-1", errors="ignore"), mime_type
        raise RuntimeError("Gemini TTS returned no inline audio data.")

    def generate_wav(
        self,
        text: str,
        voice_profile: str = "hindi_female",
        speech_language: str = "auto",
        rate: int = 175,
        volume: float = 1.0,
        voice_style: str = "natural",
    ) -> bytes:
        clean_text = " ".join(str(text or "").split()).strip()[:MAX_TTS_TEXT_LENGTH]
        if not clean_text:
            raise ValueError("Speech text is required.")
        if not self.is_available():
            reason = self._initialization_error or "GEMINI_API_KEY is not configured."
            raise RuntimeError(f"Gemini natural TTS is unavailable: {reason}")

        profile = NATURAL_VOICE_PROFILES.get(
            voice_profile,
            NATURAL_VOICE_PROFILES["hindi_female"],
        )
        language_note = LANGUAGE_GUIDANCE.get(
            speech_language,
            LANGUAGE_GUIDANCE["auto"],
        )
        style_note = VOICE_STYLE_GUIDANCE.get(voice_style, VOICE_STYLE_GUIDANCE["natural"])
        prompt = (
            "Generate speech audio only.\n"
            f"Voice persona: {profile.persona}.\n"
            f"Language and accent: {language_note}\n"
            f"Style: {style_note}.\n"
            f"Pacing: {_rate_guidance(rate)}.\n"
            "Critical rule: Speak the transcript exactly. Do not translate, summarize, add, "
            "remove, or explain any words.\n"
            "--- TRANSCRIPT START ---\n"
            f"{clean_text}\n"
            "--- TRANSCRIPT END ---"
        )

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config=self._generation_config(profile.voice_name),
            )
            raw_audio, mime_type = self._extract_audio(response)
            return ensure_wav(raw_audio, mime_type, volume=volume)
        except Exception as exc:
            safe = _safe_error(exc)
            logger.warning("Gemini natural TTS generation failed: %s", safe)
            raise RuntimeError(f"Gemini natural TTS failed: {safe}") from exc


class WindowsWavPlayer:
    """Small interruptible WAV player using the Windows standard library."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._play_lock = threading.Lock()

    def stop(self) -> None:
        self._stop_event.set()
        if sys.platform == "win32":
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    @staticmethod
    def _duration_seconds(wav_bytes: bytes) -> float:
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
                frame_rate = max(1, wav_file.getframerate())
                return wav_file.getnframes() / frame_rate
        except Exception:
            return 30.0

    def play(self, wav_bytes: bytes) -> bool:
        if sys.platform != "win32":
            raise RuntimeError("Natural WAV playback is supported on Windows only.")
        import winsound

        self._stop_event.clear()
        temp_path = ""
        with self._play_lock:
            try:
                with tempfile.NamedTemporaryFile(
                    prefix="freshy-natural-",
                    suffix=".wav",
                    delete=False,
                ) as temp_file:
                    temp_file.write(wav_bytes)
                    temp_path = temp_file.name

                duration = min(300.0, max(0.2, self._duration_seconds(wav_bytes)))
                winsound.PlaySound(
                    temp_path,
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
                deadline = time.monotonic() + duration + 0.35
                while time.monotonic() < deadline:
                    if self._stop_event.wait(0.03):
                        break
                winsound.PlaySound(None, winsound.SND_PURGE)
                return not self._stop_event.is_set()
            finally:
                if temp_path:
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
