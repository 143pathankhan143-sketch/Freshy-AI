from __future__ import annotations

import logging
import os
import tempfile
import threading
import wave
from typing import Any, Optional

logger = logging.getLogger("FreshyWhisper")


class WhisperTranscriber:
    """Lazy, CPU-friendly faster-whisper wrapper for 16 kHz mono PCM."""

    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        module: Optional[Any] = None,
        model: Optional[Any] = None,
    ) -> None:
        self.model_name = str(model_name or "base").strip()
        self.device = str(device or "cpu").strip()
        self.compute_type = str(compute_type or "int8").strip()
        self._module = module
        self._model = model
        self._lock = threading.RLock()
        self._initialization_error = ""
        self._loading = False

    @property
    def initialization_error(self) -> str:
        return self._initialization_error

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    @property
    def loading(self) -> bool:
        return self._loading

    def dependency_available(self) -> bool:
        if self._model is not None or self._module is not None:
            return True
        try:
            import faster_whisper  # type: ignore

            self._module = faster_whisper
            return True
        except Exception as exc:
            self._initialization_error = f"faster-whisper unavailable: {exc}"
            return False

    def load(self) -> bool:
        with self._lock:
            if self._model is not None:
                return True
            if self._loading:
                return False
            self._loading = True
            try:
                if not self.dependency_available():
                    return False
                factory = getattr(self._module, "WhisperModel", None)
                if factory is None:
                    raise RuntimeError("faster_whisper.WhisperModel is unavailable")
                self._model = factory(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=max(1, min(4, os.cpu_count() or 2)),
                    num_workers=1,
                )
                self._initialization_error = ""
                return True
            except Exception as exc:
                self._initialization_error = str(exc)[:300]
                logger.warning("Whisper model could not load: %s", self._initialization_error)
                self._model = None
                return False
            finally:
                self._loading = False

    @staticmethod
    def _language_code(language: str) -> Optional[str]:
        value = str(language or "auto").strip().lower()
        if value in {"hi", "hi-in", "hindi", "hinglish"}:
            return "hi"
        if value in {"en", "en-in", "english"}:
            return "en"
        return None

    @staticmethod
    def _write_wav(pcm_bytes: bytes, sample_rate: int) -> str:
        temp = tempfile.NamedTemporaryFile(
            prefix="freshy-whisper-", suffix=".wav", delete=False
        )
        path = temp.name
        temp.close()
        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return path

    def transcribe_pcm(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16_000,
        language: str = "auto",
        beam_size: int = 1,
    ) -> str:
        if not pcm_bytes:
            return ""
        if not self.load():
            raise RuntimeError(
                self._initialization_error or "Whisper model is unavailable"
            )

        path = self._write_wav(pcm_bytes, sample_rate)
        try:
            segments, _info = self._model.transcribe(
                path,
                language=self._language_code(language),
                beam_size=max(1, min(5, int(beam_size))),
                vad_filter=False,
                condition_on_previous_text=False,
                temperature=0.0,
            )
            parts = []
            for segment in segments:
                text = str(getattr(segment, "text", "") or "").strip()
                if text:
                    parts.append(text)
            return " ".join(parts).strip()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
