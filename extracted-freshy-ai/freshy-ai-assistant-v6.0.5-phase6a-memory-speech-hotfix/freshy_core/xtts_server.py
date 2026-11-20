"""Optional isolated XTTS server for Freshy.

Run this in the separate .venv-xtts environment. It keeps the heavy
Coqui model outside the main Freshy backend and exposes only installed profile
IDs; clients cannot supply arbitrary speaker-file paths.
"""

from __future__ import annotations

import io
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

try:
    from human_tts_service import HumanVoiceProfileStore, _scale_wav_volume
except ImportError:
    from freshy_core.human_tts_service import HumanVoiceProfileStore, _scale_wav_volume

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(title="Freshy XTTS Voice Server", version="1.1")
_store = HumanVoiceProfileStore()
_model = None
_model_device = "not_loaded"
_model_lock = threading.Lock()

MODEL_NAME = os.getenv(
    "XTTS_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2"
).strip()
USE_GPU = os.getenv("XTTS_USE_GPU", "true").strip().lower() in {"1", "true", "yes", "on"}
SERVER_TOKEN = os.getenv("XTTS_SERVER_TOKEN", "").strip()


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1800)
    profile_id: str = Field(min_length=2, max_length=48)
    language: str = Field(default="hi", min_length=2, max_length=8)
    speed: float = Field(default=1.0, ge=0.65, le=1.35)
    volume: float = Field(default=1.0, ge=0.0, le=1.0)
    style: str = Field(default="natural", max_length=32)


def _authorize(token: Optional[str]) -> None:
    if SERVER_TOKEN and token != SERVER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid XTTS server token")


def _get_model():
    global _model, _model_device
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            try:
                from TTS.api import TTS  # type: ignore
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Coqui TTS is not installed in the XTTS environment",
                ) from exc
            try:
                import torch  # type: ignore

                _model_device = "cuda" if USE_GPU and torch.cuda.is_available() else "cpu"
            except Exception:
                _model_device = "cpu"
            try:
                model = TTS(MODEL_NAME)
            except TypeError:
                model = TTS(model_name=MODEL_NAME, gpu=USE_GPU)
            mover = getattr(model, "to", None)
            if callable(mover):
                try:
                    moved = mover(_model_device)
                    if moved is not None:
                        model = moved
                except Exception as exc:
                    raise HTTPException(
                        status_code=503,
                        detail=f"XTTS could not initialize on {_model_device}: {str(exc)[:160]}",
                    ) from exc
            _model = model
    return _model


@app.get("/health")
def health(x_freshy_xtts_token: Optional[str] = Header(default=None)):
    _authorize(x_freshy_xtts_token)
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "gpu_requested": USE_GPU,
        "model_loaded": _model is not None,
        "device": _model_device,
        "profiles": len(_store.list_profiles()),
    }


@app.get("/voices")
def voices(x_freshy_xtts_token: Optional[str] = Header(default=None)):
    _authorize(x_freshy_xtts_token)
    return {"voices": [item.to_public_dict(True) for item in _store.list_profiles()]}


@app.post("/synthesize")
def synthesize(
    request: SynthesisRequest,
    x_freshy_xtts_token: Optional[str] = Header(default=None),
):
    _authorize(x_freshy_xtts_token)
    profile = _store.get(request.profile_id)
    model = _get_model()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
        output_path = temp.name
    try:
        kwargs = {
            "text": " ".join(request.text.split()),
            "speaker_wav": profile.speaker_wav,
            "language": request.language,
            "file_path": output_path,
            "speed": request.speed,
        }
        try:
            model.tts_to_file(**kwargs)
        except TypeError as exc:
            if "speed" not in str(exc).lower():
                raise
            kwargs.pop("speed", None)
            model.tts_to_file(**kwargs)
        payload = _scale_wav_volume(Path(output_path).read_bytes(), request.volume)
        if len(payload) < 44 or payload[:4] != b"RIFF":
            raise HTTPException(status_code=502, detail="XTTS generated invalid WAV audio")
        return Response(content=payload, media_type="audio/wav")
    finally:
        try:
            os.remove(output_path)
        except OSError:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8020)
