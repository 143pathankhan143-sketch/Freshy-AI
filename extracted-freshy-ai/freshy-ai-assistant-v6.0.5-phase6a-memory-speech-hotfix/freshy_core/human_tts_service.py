"""Optional XTTS human/cloned voice support for Freshy Phase 4.3.

The main Freshy environment does not require the heavy Coqui stack. Recommended
mode is an isolated XTTS server. Local mode remains available
when the compatible ``TTS`` package is already installed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import requests

logger = logging.getLogger("FreshyHumanTTS")
_PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,47}$")


@dataclass(frozen=True)
class HumanVoiceProfile:
    id: str
    label: str
    reference_wavs: tuple[str, ...]
    language: str = "hi"
    description: str = "Custom consented XTTS voice"

    @property
    def reference_wav(self) -> str:
        return self.reference_wavs[0]

    @property
    def speaker_wav(self) -> Union[str, List[str]]:
        references = list(self.reference_wavs)
        return references[0] if len(references) == 1 else references

    def to_public_dict(self, available: bool = True) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "language": self.language,
            "description": self.description,
            "reference_count": len(self.reference_wavs),
            "available": available,
        }


class HumanVoiceProfileStore:
    def __init__(self, root: Optional[str] = None) -> None:
        base = root or os.path.join(os.path.dirname(__file__), "voice_profiles")
        self.root = Path(base).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_profile_id(profile_id: str) -> str:
        value = str(profile_id or "").strip().lower()
        if not _PROFILE_ID.fullmatch(value):
            raise ValueError("Voice profile id must use 2–48 lowercase letters, numbers, _ or -")
        return value

    def _profile_dir(self, profile_id: str) -> Path:
        safe = self.validate_profile_id(profile_id)
        path = (self.root / safe).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid voice profile path")
        return path

    def list_profiles(self) -> List[HumanVoiceProfile]:
        profiles: List[HumanVoiceProfile] = []
        for manifest in sorted(self.root.glob("*/manifest.json")):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                profile_id = self.validate_profile_id(data.get("id", manifest.parent.name))
                names = data.get("reference_wavs")
                if not isinstance(names, list) or not names:
                    names = [data.get("reference_wav", "reference.wav")]
                references: List[str] = []
                for raw_name in names[:8]:
                    reference_name = str(raw_name or "").strip()
                    if not reference_name:
                        continue
                    reference = (manifest.parent / reference_name).resolve()
                    if manifest.parent.resolve() not in reference.parents:
                        continue
                    if reference.is_file():
                        references.append(str(reference))
                if not references:
                    continue
                profiles.append(
                    HumanVoiceProfile(
                        id=profile_id,
                        label=str(data.get("label", profile_id)).strip() or profile_id,
                        reference_wavs=tuple(references),
                        language=str(data.get("language", "hi")).strip() or "hi",
                        description=str(
                            data.get("description", "Custom consented XTTS voice")
                        ).strip(),
                    )
                )
            except Exception as exc:
                logger.warning("Ignoring invalid voice profile %s: %s", manifest, str(exc)[:160])
        return profiles

    def get(self, profile_id: str) -> HumanVoiceProfile:
        wanted = self.validate_profile_id(profile_id)
        for profile in self.list_profiles():
            if profile.id == wanted:
                return profile
        raise ValueError(f"XTTS voice profile '{wanted}' is not installed")

    @staticmethod
    def _validate_wav(path: Path) -> None:
        if path.suffix.lower() != ".wav":
            raise ValueError("Reference audio must be a WAV file")
        if not path.is_file():
            raise ValueError("Reference WAV does not exist")
        if path.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("Reference WAV is larger than 100 MB")
        with wave.open(str(path), "rb") as source:
            duration = source.getnframes() / max(1, source.getframerate())
            if duration < 3.0:
                raise ValueError("Reference voice should contain at least 3 seconds of clean speech")
            if duration > 600:
                raise ValueError("Reference WAV must be shorter than 10 minutes")

    def install_profile(
        self,
        profile_id: str,
        label: str,
        reference_wav: Optional[str] = None,
        reference_wavs: Optional[Sequence[str]] = None,
        language: str = "hi",
        description: str = "Custom consented XTTS voice",
    ) -> HumanVoiceProfile:
        safe = self.validate_profile_id(profile_id)
        raw_sources = list(reference_wavs or [])
        if reference_wav:
            raw_sources.insert(0, reference_wav)
        # Preserve order while removing duplicate paths. Multiple clean clips can
        # improve cloning consistency, but cap the profile to keep it manageable.
        sources: List[Path] = []
        seen = set()
        for raw in raw_sources:
            source = Path(raw).expanduser().resolve()
            key = str(source).lower()
            if key in seen:
                continue
            seen.add(key)
            self._validate_wav(source)
            sources.append(source)
            if len(sources) >= 8:
                break
        if not sources:
            raise ValueError("At least one clean consented reference WAV is required")

        target_dir = self._profile_dir(safe)
        target_dir.mkdir(parents=True, exist_ok=True)
        # Remove old copied references while preserving unrelated documentation.
        for old_reference in target_dir.glob("reference_*.wav"):
            old_reference.unlink(missing_ok=True)
        (target_dir / "reference.wav").unlink(missing_ok=True)

        names: List[str] = []
        for index, source in enumerate(sources, start=1):
            target_name = f"reference_{index}.wav"
            shutil.copy2(source, target_dir / target_name)
            names.append(target_name)
        manifest = {
            "id": safe,
            "label": str(label or safe).strip() or safe,
            "reference_wav": names[0],
            "reference_wavs": names,
            "language": str(language or "hi").strip() or "hi",
            "description": str(description or "Custom consented XTTS voice").strip(),
            "consent_required": True,
        }
        (target_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return self.get(safe)

    def remove_profile(self, profile_id: str) -> None:
        target = self._profile_dir(profile_id)
        if target.is_dir():
            shutil.rmtree(target)


def _scale_wav_volume(wav_bytes: bytes, volume: float) -> bytes:
    safe_volume = max(0.0, min(1.0, float(volume)))
    if safe_volume >= 0.999:
        return wav_bytes
    import io
    import sys

    with wave.open(io.BytesIO(wav_bytes), "rb") as source:
        params = source.getparams()
        frames = source.readframes(source.getnframes())
    if params.sampwidth != 2:
        return wav_bytes
    samples = array("h")
    samples.frombytes(frames[: len(frames) - (len(frames) % 2)])
    if sys.byteorder != "little":
        samples.byteswap()
    for index, sample in enumerate(samples):
        samples[index] = max(-32768, min(32767, int(sample * safe_volume)))
    if sys.byteorder != "little":
        samples.byteswap()
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setparams(params)
        target.writeframes(samples.tobytes())
    return output.getvalue()


class XTTSHumanTTS:
    def __init__(
        self,
        mode: str = "disabled",
        server_url: str = "http://127.0.0.1:8020",
        server_token: str = "",
        timeout_seconds: int = 45,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        use_gpu: bool = True,
        profile_store: Optional[HumanVoiceProfileStore] = None,
        requests_module: Any = requests,
    ) -> None:
        self.mode = str(mode or "disabled").strip().lower()
        if self.mode not in {"disabled", "server", "local"}:
            self.mode = "disabled"
        self.server_url = str(server_url or "").rstrip("/")
        self.server_token = str(server_token or "")
        self.timeout_seconds = max(5, min(180, int(timeout_seconds)))
        self.model_name = str(model_name or "").strip()
        self.use_gpu = bool(use_gpu)
        self.profile_store = profile_store or HumanVoiceProfileStore()
        self._requests = requests_module
        self._local_model: Optional[Any] = None
        self._last_error = ""

    @property
    def last_error(self) -> str:
        return self._last_error

    def voice_profiles(self) -> List[Dict[str, Any]]:
        return [profile.to_public_dict(True) for profile in self.profile_store.list_profiles()]

    def is_configured(self) -> bool:
        if self.mode == "disabled":
            return False
        if not self.profile_store.list_profiles():
            return False
        if self.mode == "server":
            return bool(self.server_url)
        return bool(self.model_name)

    def health_check(self) -> Dict[str, Any]:
        if self.mode == "disabled":
            return {"available": False, "mode": self.mode, "reason": "XTTS is disabled"}
        if self.mode == "server":
            try:
                response = self._requests.get(
                    f"{self.server_url}/health",
                    headers=self._headers(),
                    timeout=min(5, self.timeout_seconds),
                )
                return {
                    "available": response.status_code == 200,
                    "mode": self.mode,
                    "status_code": response.status_code,
                }
            except Exception as exc:
                return {"available": False, "mode": self.mode, "reason": str(exc)[:180]}
        try:
            self._ensure_local_model()
            return {"available": True, "mode": self.mode}
        except Exception as exc:
            return {"available": False, "mode": self.mode, "reason": str(exc)[:180]}

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "audio/wav"}
        if self.server_token:
            headers["X-Freshy-XTTS-Token"] = self.server_token
        return headers

    def _ensure_local_model(self) -> Any:
        if self._local_model is not None:
            return self._local_model
        try:
            from TTS.api import TTS  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Coqui TTS is not installed in this Python environment. Use XTTS_MODE=server "
                "with the isolated XTTS server, or install a compatible TTS build."
            ) from exc
        try:
            model = TTS(self.model_name)
        except TypeError:
            # Compatibility with older Coqui APIs that still accept the model as
            # a keyword or expose the legacy gpu constructor flag.
            model = TTS(model_name=self.model_name, gpu=self.use_gpu)
        try:
            import torch  # type: ignore

            device = "cuda" if self.use_gpu and torch.cuda.is_available() else "cpu"
            mover = getattr(model, "to", None)
            if callable(mover):
                moved = mover(device)
                if moved is not None:
                    model = moved
        except Exception as exc:
            logger.info("XTTS device selection fell back to the model default: %s", str(exc)[:120])
        self._local_model = model
        return self._local_model

    @staticmethod
    def _language_code(speech_language: str, profile_language: str) -> str:
        requested = str(speech_language or "auto")
        if requested == "en-IN":
            return "en"
        if requested == "hi-IN":
            return "hi"
        return profile_language or "hi"

    def generate_wav(
        self,
        text: str,
        voice_profile: str,
        speech_language: str = "auto",
        rate: int = 175,
        volume: float = 1.0,
        voice_style: str = "natural",
    ) -> bytes:
        clean = " ".join(str(text or "").split()).strip()
        if not clean:
            raise ValueError("Speech text is required")
        profile = self.profile_store.get(voice_profile)
        language = self._language_code(speech_language, profile.language)
        try:
            if self.mode == "server":
                response = self._requests.post(
                    f"{self.server_url}/synthesize",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json={
                        "text": clean,
                        "profile_id": profile.id,
                        "language": language,
                        "speed": max(0.65, min(1.35, rate / 175.0)),
                        "volume": max(0.0, min(1.0, volume)),
                        "style": voice_style,
                    },
                    timeout=self.timeout_seconds,
                )
                if response.status_code != 200:
                    raise RuntimeError(f"XTTS server returned HTTP {response.status_code}")
                data = bytes(response.content)
            elif self.mode == "local":
                model = self._ensure_local_model()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
                    path = temp.name
                try:
                    kwargs = {
                        "text": clean,
                        "speaker_wav": profile.speaker_wav,
                        "language": language,
                        "file_path": path,
                        "speed": max(0.65, min(1.35, rate / 175.0)),
                    }
                    try:
                        model.tts_to_file(**kwargs)
                    except TypeError as exc:
                        # Older compatible APIs may not accept speed at this level.
                        if "speed" not in str(exc).lower():
                            raise
                        kwargs.pop("speed", None)
                        model.tts_to_file(**kwargs)
                    data = Path(path).read_bytes()
                finally:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            else:
                raise RuntimeError("XTTS is disabled")
            if len(data) < 44 or data[:4] != b"RIFF":
                raise RuntimeError("XTTS returned invalid WAV audio")
            data = _scale_wav_volume(data, volume)
            self._last_error = ""
            return data
        except Exception as exc:
            self._last_error = str(exc)[:240]
            logger.warning("XTTS human voice generation failed: %s", self._last_error)
            raise RuntimeError(f"XTTS human voice failed: {self._last_error}") from exc
