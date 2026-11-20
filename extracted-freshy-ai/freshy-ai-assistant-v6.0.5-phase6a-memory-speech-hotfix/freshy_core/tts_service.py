import os
import sys
import json
import queue
import logging
import re
import threading
import collections
import time
import uuid
from typing import List, Dict, Any, Optional, Callable, Literal
from pydantic import BaseModel, Field

try:
    from natural_tts_service import (
        GeminiNaturalTTS,
        NATURAL_VOICE_PROFILES,
        WindowsWavPlayer,
    )
except ImportError:
    from freshy_core.natural_tts_service import (
        GeminiNaturalTTS,
        NATURAL_VOICE_PROFILES,
        WindowsWavPlayer,
    )

try:
    from audio_output import StableAudioPlayer
    from human_tts_service import XTTSHumanTTS, HumanVoiceProfileStore
except ImportError:
    from freshy_core.audio_output import StableAudioPlayer
    from freshy_core.human_tts_service import XTTSHumanTTS, HumanVoiceProfileStore

logger = logging.getLogger("FreshyTTS")

try:
    from config import config
except ImportError:
    try:
        from freshy_core.config import config
    except ImportError:
        class ConfigFallback:
            TTS_ENABLED = True
            TTS_PROVIDER = "gemini"
            TTS_NATURAL_VOICE = "hindi_female"
            TTS_SPEECH_LANGUAGE = "auto"
            TTS_GEMINI_TIMEOUT_SECONDS = 30
            GEMINI_API_KEY = ""
            GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
            TTS_RATE = 175
            TTS_VOLUME = 1.0
            TTS_SELECTED_VOICE = ""
            TTS_STARTUP_GREETING = True
            TTS_FAST_START_ENABLED = True
            TTS_PREPARE_DURING_SILENCE = True
            TTS_FAST_CHUNK_CHARACTERS = 260
            TTS_FIRST_CHUNK_CHARACTERS = 150
            TTS_VOICE_STYLE = "natural"
            TTS_FAILURE_BEHAVIOR = "silent"
            TTS_FALLBACK_PROVIDER = "none"
            TTS_HUMAN_VOICE_PROFILE = ""
            TTS_STABLE_AUDIO_ENABLED = True
            TTS_TRIM_BOUNDARY_SILENCE = True
            XTTS_MODE = "disabled"
            XTTS_SERVER_URL = "http://127.0.0.1:8020"
            XTTS_SERVER_TOKEN = ""
            XTTS_TIMEOUT_SECONDS = 45
            XTTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
            XTTS_USE_GPU = True
        config = ConfigFallback()

class TTSSettings(BaseModel):
    enabled: bool = Field(default_factory=lambda: getattr(config, "TTS_ENABLED", True))
    provider: Literal["system", "gemini", "xtts", "text_only"] = Field(
        default_factory=lambda: getattr(config, "TTS_PROVIDER", "gemini")
    )
    natural_voice: Literal["hindi_female", "hindi_male"] = Field(
        default_factory=lambda: getattr(config, "TTS_NATURAL_VOICE", "hindi_female")
    )
    human_voice_profile: str = Field(
        default_factory=lambda: getattr(config, "TTS_HUMAN_VOICE_PROFILE", "")
    )
    speech_language: Literal["auto", "hi-IN", "en-IN"] = Field(
        default_factory=lambda: getattr(config, "TTS_SPEECH_LANGUAGE", "auto")
    )
    voice_style: Literal["natural", "warm", "calm", "professional", "cinematic"] = Field(
        default_factory=lambda: getattr(config, "TTS_VOICE_STYLE", "natural")
    )
    selected_voice: str = Field(default_factory=lambda: getattr(config, "TTS_SELECTED_VOICE", ""))
    rate: int = Field(default_factory=lambda: getattr(config, "TTS_RATE", 175), ge=50, le=400)
    volume: float = Field(default_factory=lambda: getattr(config, "TTS_VOLUME", 1.0), ge=0.0, le=1.0)
    startup_greeting: bool = Field(default_factory=lambda: getattr(config, "TTS_STARTUP_GREETING", True))
    fast_start_enabled: bool = Field(default_factory=lambda: getattr(config, "TTS_FAST_START_ENABLED", True))
    prepare_during_silence: bool = Field(default_factory=lambda: getattr(config, "TTS_PREPARE_DURING_SILENCE", True))
    fast_chunk_characters: int = Field(default_factory=lambda: getattr(config, "TTS_FAST_CHUNK_CHARACTERS", 260), ge=120, le=600)
    first_chunk_characters: int = Field(default_factory=lambda: getattr(config, "TTS_FIRST_CHUNK_CHARACTERS", 150), ge=80, le=300)
    stable_audio_enabled: bool = Field(default_factory=lambda: getattr(config, "TTS_STABLE_AUDIO_ENABLED", True))
    trim_boundary_silence: bool = Field(default_factory=lambda: getattr(config, "TTS_TRIM_BOUNDARY_SILENCE", True))
    failure_behavior: Literal["silent", "retry_once", "selected_fallback"] = Field(
        default_factory=lambda: getattr(config, "TTS_FAILURE_BEHAVIOR", "silent")
    )
    fallback_provider: Literal["none", "system", "gemini", "xtts"] = Field(
        default_factory=lambda: getattr(config, "TTS_FALLBACK_PROVIDER", "none")
    )

def split_speech_chunks(
    text: str,
    max_characters: int = 260,
    first_chunk_characters: Optional[int] = None,
) -> List[str]:
    """Split on sentence/clause boundaries without ever cutting inside a word.

    The first chunk can be shorter for low latency; continuation chunks are
    larger so the generator has enough playback time to prepare the next audio.
    """
    clean = " ".join(str(text or "").split()).strip()
    if not clean:
        return []
    max_characters = max(120, min(600, int(max_characters)))
    first_limit = max(80, min(max_characters, int(first_chunk_characters or max_characters)))
    sentences = [part.strip() for part in re.split(r"(?<=[.!?।])\s+", clean) if part.strip()] or [clean]
    pieces: List[str] = []
    for sentence in sentences:
        if len(sentence) <= max_characters:
            pieces.append(sentence)
            continue
        clause_parts = [p.strip() for p in re.split(r"(?<=[,;:])\s+", sentence) if p.strip()] or [sentence]
        for clause in clause_parts:
            remaining = clause
            while len(remaining) > max_characters:
                cut = remaining.rfind(" ", 0, max_characters + 1)
                if cut < 40:
                    cut = remaining.find(" ", max_characters)
                if cut < 0:
                    cut = len(remaining)
                pieces.append(remaining[:cut].strip())
                remaining = remaining[cut:].strip()
            if remaining:
                pieces.append(remaining)
    chunks: List[str] = []
    current = ""
    for piece in pieces:
        limit = first_limit if not chunks else max_characters
        candidate = f"{current} {piece}".strip()
        if current and len(candidate) > limit:
            chunks.append(current)
            current = piece
        else:
            current = candidate
        if not chunks and len(current) >= first_limit and re.search(r"[.!?।,;:]$", current):
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def _default_com_initialize() -> None:
    """Initialize COM on the TTS worker and let the worker report failures."""
    if sys.platform == 'win32':
        import pythoncom
        pythoncom.CoInitialize()

def _default_com_uninitialize() -> None:
    if sys.platform == 'win32':
        import pythoncom
        pythoncom.CoUninitialize()

def _default_engine_factory() -> Any:
    import pyttsx3
    return pyttsx3.init()

class TTSService:
    def __init__(
        self,
        settings_file: Optional[str] = None,
        engine_factory: Optional[Callable[[], Any]] = None,
        com_initialize: Optional[Callable[[], None]] = None,
        com_uninitialize: Optional[Callable[[], None]] = None,
        natural_tts_factory: Optional[Callable[[], Any]] = None,
        human_tts_factory: Optional[Callable[[], Any]] = None,
        natural_audio_player: Optional[Any] = None,
    ):
        if settings_file is None:
            settings_file = os.path.join(os.path.dirname(__file__), "tts_settings.json")
        self.settings_file = settings_file

        self._engine_factory = engine_factory or _default_engine_factory
        self._com_initialize = com_initialize or _default_com_initialize
        self._com_uninitialize = com_uninitialize or _default_com_uninitialize
        self._natural_tts_factory = natural_tts_factory or self._default_natural_tts_factory
        self._human_tts_factory = human_tts_factory or self._default_human_tts_factory
        self._natural_audio_player = natural_audio_player or StableAudioPlayer(
            fallback_player=WindowsWavPlayer(),
            trim_silence=getattr(config, "TTS_TRIM_BOUNDARY_SILENCE", True),
            stream_enabled=getattr(config, "TTS_STABLE_AUDIO_ENABLED", True),
        )
        self._natural_tts: Optional[Any] = None
        self._human_tts: Optional[Any] = None
        self._natural_stop_event = threading.Event()
        self._natural_cutoff_seq = 0
        self._natural_last_error = ""
        self._active_backend = "none"
        self._prepared_audio: Dict[str, Dict[str, Any]] = {}
        self._speech_epoch = 0
        self._generation_busy = False

        self._lock = threading.RLock()
        self.settings = TTSSettings()

        self._is_speaking = False
        self._current_text: Optional[str] = None
        self._active_utt_id: Optional[str] = None
        self._active_seq: Optional[int] = None
        self._pending_count = 0

        self._engine_initializing = True
        self._engine_available = False
        self._error_status = "Initializing"
        self._voices_cache: List[Dict[str, Any]] = []

        self._seq_counter = 0

        self._cmd_queue: queue.Queue = queue.Queue()
        self._natural_cmd_queue: queue.Queue = queue.Queue()
        self._playback_queue: queue.Queue = queue.Queue(maxsize=12)
        self._running = True
        self._shutdown_requested = False
        self._shutdown_state = "running"

        self.load_settings()
        set_trim = getattr(self._natural_audio_player, "set_trim_silence", None)
        if callable(set_trim):
            set_trim(self.settings.trim_boundary_silence)
        set_stream = getattr(self._natural_audio_player, "set_stream_enabled", None)
        if callable(set_stream):
            set_stream(self.settings.stable_audio_enabled)

        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="FreshyTTSWorker")
        self._natural_worker_thread = threading.Thread(
            target=self._natural_worker_loop,
            daemon=True,
            name="FreshyNaturalTTSGenerator",
        )
        self._playback_worker_thread = threading.Thread(
            target=self._playback_worker_loop,
            daemon=True,
            name="FreshyStableAudioPlayer",
        )
        self._worker_thread.start()
        self._natural_worker_thread.start()
        self._playback_worker_thread.start()

    def _default_natural_tts_factory(self) -> GeminiNaturalTTS:
        return GeminiNaturalTTS(
            api_key=getattr(config, "GEMINI_API_KEY", ""),
            model=getattr(config, "GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
            timeout_seconds=getattr(config, "TTS_GEMINI_TIMEOUT_SECONDS", 30),
        )

    def _get_natural_tts(self) -> Any:
        if self._natural_tts is None:
            self._natural_tts = self._natural_tts_factory()
        return self._natural_tts

    def _default_human_tts_factory(self) -> XTTSHumanTTS:
        return XTTSHumanTTS(
            mode=getattr(config, "XTTS_MODE", "disabled"),
            server_url=getattr(config, "XTTS_SERVER_URL", "http://127.0.0.1:8020"),
            server_token=getattr(config, "XTTS_SERVER_TOKEN", ""),
            timeout_seconds=getattr(config, "XTTS_TIMEOUT_SECONDS", 45),
            model_name=getattr(
                config,
                "XTTS_MODEL_NAME",
                "tts_models/multilingual/multi-dataset/xtts_v2",
            ),
            use_gpu=getattr(config, "XTTS_USE_GPU", True),
        )

    def _get_human_tts(self) -> Any:
        if self._human_tts is None:
            self._human_tts = self._human_tts_factory()
        return self._human_tts

    def _human_is_configured(self) -> bool:
        try:
            human = self._get_human_tts()
            checker = getattr(human, "is_configured", None)
            return bool(checker()) if callable(checker) else True
        except Exception as exc:
            self._natural_last_error = str(exc)[:240]
            return False

    def get_human_voices(self) -> List[Dict[str, Any]]:
        try:
            return list(self._get_human_tts().voice_profiles())
        except Exception:
            return []


    def _natural_is_configured(self) -> bool:
        try:
            natural = self._get_natural_tts()
            checker = getattr(natural, "is_configured", None)
            return bool(checker()) if callable(checker) else True
        except Exception as exc:
            self._natural_last_error = str(exc)[:240]
            return False

    def load_settings(self) -> None:
        """Loads settings from JSON file if present, using safe defaults on failure."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings = TTSSettings(**data)
                    self._load_error = None
            except Exception as e:
                logger.warning(f"[Freshy TTS] Could not load settings from {self.settings_file}: {e}")
                self.settings = TTSSettings()
                self._load_error = f"Settings read failed ({e}); using safe defaults"
                try:
                    self.save_settings()
                except Exception as se:
                    logger.warning(f"[Freshy TTS] Could not save default settings: {se}")
        else:
            try:
                self.save_settings()
                self._load_error = None
            except Exception as se:
                logger.warning(f"[Freshy TTS] Could not save default settings: {se}")
                self._load_error = f"Settings write failed ({se}); using safe defaults"

    def save_settings(self) -> None:
        """Persists settings to disk atomically using a temporary file."""
        try:
            dir_name = os.path.dirname(self.settings_file)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            tmp_file = f"{self.settings_file}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.settings.model_dump(), f, indent=2)
            os.replace(tmp_file, self.settings_file)
            self._load_error = None
        except Exception as e:
            logger.warning(f"[Freshy TTS] Could not save settings to {self.settings_file}: {e}")
            raise RuntimeError(f"Could not save settings to {self.settings_file}: {e}")

    def update_settings(self, new_settings: Dict[str, Any]) -> TTSSettings:
        """Persist settings and enforce a single selected voice backend."""
        with self._lock:
            if not self._running:
                raise RuntimeError("TTS service is shutting down")
            target_provider = str(
                new_settings.get("provider", self.settings.provider) or "gemini"
            ).strip().lower()
            if target_provider not in {"system", "gemini", "xtts", "text_only"}:
                raise ValueError("provider must be system, gemini, xtts, or text_only")

            if target_provider == "system" and not self._engine_available and not self._engine_initializing:
                raise RuntimeError(f"Windows TTS engine is unavailable ({self._error_status})")

            selected_voice = str(
                new_settings.get("selected_voice", self.settings.selected_voice) or ""
            ).strip()
            new_settings["selected_voice"] = selected_voice
            if selected_voice and target_provider == "system":
                if not self._voices_cache:
                    if self._engine_initializing:
                        raise RuntimeError("Windows voices are still initializing")
                    raise RuntimeError(f"Windows voices are unavailable ({self._error_status})")
                valid_ids = {voice["id"] for voice in self._voices_cache}
                if selected_voice not in valid_ids:
                    raise ValueError(f"Selected Windows voice '{selected_voice}' is not installed")

            human_profile = str(
                new_settings.get("human_voice_profile", self.settings.human_voice_profile) or ""
            ).strip()
            new_settings["human_voice_profile"] = human_profile
            if target_provider == "gemini" and not self._natural_is_configured():
                raise RuntimeError("Gemini TTS is not configured. Add GEMINI_API_KEY first.")
            if target_provider == "xtts":
                valid_profiles = {item.get("id") for item in self.get_human_voices()}
                if not human_profile:
                    raise ValueError("Select an installed XTTS human voice profile")
                if human_profile not in valid_profiles:
                    raise ValueError(f"XTTS voice profile '{human_profile}' is not installed")
                if not self._human_is_configured():
                    raise RuntimeError(
                        "XTTS is not ready. Set XTTS_MODE=server or local and start the voice service."
                    )

            fallback_provider = str(
                new_settings.get("fallback_provider", self.settings.fallback_provider) or "none"
            ).strip().lower()
            if fallback_provider not in {"none", "system", "gemini", "xtts"}:
                raise ValueError("fallback_provider must be none, system, gemini, or xtts")
            if fallback_provider == target_provider:
                fallback_provider = "none"
            failure_behavior = str(
                new_settings.get("failure_behavior", self.settings.failure_behavior) or "silent"
            ).strip().lower()
            if failure_behavior == "selected_fallback" and fallback_provider != "none":
                if fallback_provider == "system" and not self._engine_available:
                    raise RuntimeError("The selected Windows fallback voice is unavailable")
                if fallback_provider == "gemini" and not self._natural_is_configured():
                    raise RuntimeError("The selected Gemini fallback is not configured")
                if fallback_provider == "xtts" and not self._human_is_configured():
                    raise RuntimeError("The selected XTTS fallback is not configured")
            new_settings["fallback_provider"] = fallback_provider

            backup = TTSSettings(**self.settings.model_dump())
            previous_provider = self.settings.provider
            was_enabled = self.settings.enabled
            try:
                data = self.settings.model_dump()
                data.update(new_settings)
                self.settings = TTSSettings(**data)
                self.save_settings()
            except Exception:
                self.settings = backup
                raise

            set_trim = getattr(self._natural_audio_player, "set_trim_silence", None)
            if callable(set_trim):
                set_trim(self.settings.trim_boundary_silence)
            set_stream = getattr(self._natural_audio_player, "set_stream_enabled", None)
            if callable(set_stream):
                set_stream(self.settings.stable_audio_enabled)

            voice_output_fields = (
                "provider",
                "natural_voice",
                "human_voice_profile",
                "speech_language",
                "voice_style",
                "selected_voice",
                "rate",
                "volume",
                "fast_start_enabled",
                "fast_chunk_characters",
                "first_chunk_characters",
                "stable_audio_enabled",
                "trim_boundary_silence",
            )
            changed_voice_output = any(
                getattr(backup, field) != getattr(self.settings, field)
                for field in voice_output_fields
            )
            disabled_now = was_enabled and not self.settings.enabled
            if changed_voice_output or disabled_now:
                self._speech_epoch += 1
                cutoff = self._seq_counter
                self._natural_cutoff_seq = max(self._natural_cutoff_seq, cutoff)
                self._pending_count = 0
                self._prepared_audio.clear()
                self._is_speaking = False
                self._current_text = None
                self._active_backend = "none"
                self._natural_stop_event.set()
                try:
                    self._natural_audio_player.stop()
                except Exception:
                    pass
                stop = {"action": "STOP", "cutoff_seq": cutoff, "epoch": self._speech_epoch}
                self._natural_cmd_queue.put(dict(stop))
                self._playback_queue.put(dict(stop))
                self._cmd_queue.put(dict(stop))

            action = "DISABLE" if not self.settings.enabled else (
                "ENABLE" if not was_enabled else "APPLY_SETTINGS"
            )
            self._cmd_queue.put(
                {
                    "action": action,
                    "settings": self.settings.model_dump(),
                    "cutoff_seq": self._seq_counter,
                }
            )
            return self.settings

    @staticmethod
    def _speech_fingerprint(text: str, settings: Dict[str, Any]) -> str:
        clean = " ".join(str(text or "").split()).strip()
        return "|".join(
            [
                clean,
                str(settings.get("provider", "")),
                str(settings.get("natural_voice", "")),
                str(settings.get("human_voice_profile", "")),
                str(settings.get("speech_language", "")),
                str(settings.get("voice_style", "")),
                str(settings.get("rate", "")),
                str(settings.get("volume", "")),
                str(settings.get("fast_chunk_characters", "")),
            ]
        )

    def _generate_voice_wav(
        self,
        provider: str,
        text: str,
        settings: Dict[str, Any],
    ) -> bytes:
        common = {
            "speech_language": settings.get("speech_language", "auto"),
            "rate": int(settings.get("rate", 175)),
            "volume": float(settings.get("volume", 1.0)),
            "voice_style": settings.get("voice_style", "natural"),
        }
        if provider == "gemini":
            return self._get_natural_tts().generate_wav(
                text,
                voice_profile=settings.get("natural_voice", "hindi_female"),
                **common,
            )
        if provider == "xtts":
            return self._get_human_tts().generate_wav(
                text,
                voice_profile=settings.get("human_voice_profile", ""),
                **common,
            )
        raise RuntimeError(f"Provider '{provider}' does not generate WAV audio")

    def _selected_fallback_provider(self, failed_provider: str, settings: Dict[str, Any]) -> str:
        if settings.get("failure_behavior") != "selected_fallback":
            return "none"
        fallback = str(settings.get("fallback_provider", "none") or "none")
        if fallback == failed_provider:
            return "none"
        if fallback == "system" and self._engine_available:
            return fallback
        if fallback == "gemini" and self._natural_is_configured():
            return fallback
        if fallback == "xtts" and self._human_is_configured():
            return fallback
        return "none"

    def _prune_prepared_audio_locked(self) -> None:
        now = time.monotonic()
        expired = [
            token
            for token, item in self._prepared_audio.items()
            if now - float(item.get("created_at", 0.0) or 0.0) > 30.0
        ]
        for token in expired:
            self._prepared_audio.pop(token, None)
        if len(self._prepared_audio) > 2:
            oldest = sorted(
                self._prepared_audio.items(),
                key=lambda pair: float(pair[1].get("created_at", 0.0) or 0.0),
            )
            for token, _item in oldest[: len(self._prepared_audio) - 2]:
                self._prepared_audio.pop(token, None)

    def prepare_speech(self, text: str) -> Dict[str, Any]:
        """Pre-generate the first selected neural voice chunk during final silence."""
        text_str = " ".join(str(text or "").split()).strip()
        if not text_str:
            return {"accepted": False, "reason": "Speech text cannot be empty"}
        with self._lock:
            provider = self.settings.provider
            if not self._running or not self.settings.enabled:
                return {"accepted": False, "reason": "TTS is unavailable"}
            if provider not in {"gemini", "xtts"}:
                return {"accepted": False, "reason": "Prepared audio requires Gemini or XTTS"}
            if not self.settings.prepare_during_silence:
                return {"accepted": False, "reason": "Silence-window preparation is disabled"}
            if provider == "gemini" and not self._natural_is_configured():
                return {"accepted": False, "reason": "Gemini TTS is not configured"}
            if provider == "xtts" and not self._human_is_configured():
                return {"accepted": False, "reason": "XTTS human voice is not configured"}
            settings = self.settings.model_dump()
            chunks = split_speech_chunks(
                text_str,
                settings.get("fast_chunk_characters", 260),
                settings.get("first_chunk_characters", 150),
            )
            first_chunk = chunks[0] if chunks else text_str
            fingerprint = self._speech_fingerprint(text_str, settings)

        try:
            wav_bytes = self._generate_voice_wav(provider, first_chunk, settings)
        except Exception as exc:
            self._natural_last_error = str(exc)[:240]
            return {"accepted": False, "reason": f"{provider} voice preparation failed"}

        with self._lock:
            if not self._running:
                return {"accepted": False, "reason": "TTS is shutting down"}
            if fingerprint != self._speech_fingerprint(text_str, self.settings.model_dump()):
                return {"accepted": False, "reason": "Voice settings changed during preparation"}
            token = uuid.uuid4().hex
            self._prepared_audio[token] = {
                "created_at": time.monotonic(),
                "fingerprint": fingerprint,
                "wav": wav_bytes,
                "first_chunk": first_chunk,
                "provider": provider,
            }
            self._prune_prepared_audio_locked()
        return {"accepted": True, "reason": "First voice chunk prepared", "token": token}

    def speak(self, text: str, prepared_token: Optional[str] = None) -> Dict[str, Any]:
        """Queue speech only on the explicitly selected backend."""
        text_str = " ".join(str(text or "").split()).strip()
        if not text_str:
            return {"accepted": False, "reason": "Speech text cannot be empty"}
        with self._lock:
            if not self._running:
                return {"accepted": False, "reason": "TTS service is shutting down"}
            if not self.settings.enabled:
                return {"accepted": False, "reason": "TTS is disabled in settings"}
            provider = self.settings.provider
            if provider == "text_only":
                return {"accepted": False, "reason": "Text-only mode is selected"}
            if provider == "system" and not (self._engine_available or self._engine_initializing):
                return {"accepted": False, "reason": f"Windows TTS is unavailable ({self._error_status})"}
            if provider == "gemini" and not self._natural_is_configured():
                return {"accepted": False, "reason": "Gemini TTS is not configured; reply remains text-only"}
            if provider == "xtts" and not self._human_is_configured():
                return {"accepted": False, "reason": "XTTS human voice is not configured; reply remains text-only"}

            settings = self.settings.model_dump()
            chunks = [text_str]
            if provider in {"gemini", "xtts"} and self.settings.fast_start_enabled:
                chunks = split_speech_chunks(
                    text_str,
                    self.settings.fast_chunk_characters,
                    self.settings.first_chunk_characters,
                )
            prepared_audio = None
            self._prune_prepared_audio_locked()
            if prepared_token:
                cached = self._prepared_audio.pop(str(prepared_token), None)
                if (
                    cached
                    and cached.get("provider") == provider
                    and cached.get("fingerprint") == self._speech_fingerprint(text_str, settings)
                ):
                    prepared_audio = cached.get("wav")

            epoch = self._speech_epoch
            commands = []
            for index, chunk in enumerate(chunks):
                self._seq_counter += 1
                seq = self._seq_counter
                commands.append(
                    {
                        "action": "SPEAK",
                        "text": chunk,
                        "full_text": text_str,
                        "utt_id": f"utt_{seq}",
                        "seq": seq,
                        "epoch": epoch,
                        "provider": provider,
                        "chunk_index": index,
                        "chunk_count": len(chunks),
                        "settings": settings,
                        "prepared_wav": prepared_audio if index == 0 else None,
                    }
                )
            self._pending_count += len(commands)
            target_queue = self._cmd_queue if provider == "system" else self._natural_cmd_queue
            for command in commands:
                target_queue.put(command)
        return {
            "accepted": True,
            "reason": f"{provider} speech request enqueued",
            "provider": provider,
            "chunk_count": len(commands),
            "prepared_audio_used": prepared_audio is not None,
        }

    def stop_speaking(self) -> Dict[str, Any]:
        """Immediately invalidate generation, playback, and Windows speech queues."""
        with self._lock:
            if not self._running:
                return {"accepted": False, "reason": "TTS service is shutting down"}
            cutoff = self._seq_counter
            self._speech_epoch += 1
            epoch = self._speech_epoch
            self._natural_cutoff_seq = max(self._natural_cutoff_seq, cutoff)
            self._pending_count = 0
            self._prepared_audio.clear()
            self._natural_stop_event.set()
            self._is_speaking = False
            self._current_text = None
            self._active_utt_id = None
            self._active_seq = None
            self._active_backend = "none"
        try:
            self._natural_audio_player.stop()
        except Exception:
            pass
        stop = {"action": "STOP", "cutoff_seq": cutoff, "epoch": epoch}
        self._natural_cmd_queue.put(dict(stop))
        self._playback_queue.put(dict(stop))
        self._cmd_queue.put(dict(stop))
        return {"accepted": True, "reason": "All speech generation and playback stopped"}

    def test_voice(self, phrase: str = "This is a Freshy AI voice test.") -> Dict[str, Any]:
        phrase_str = " ".join(str(phrase or "").split()).strip()
        if not phrase_str:
            return {"accepted": False, "reason": "Test speech phrase cannot be empty"}
        self.stop_speaking()
        return self.speak(phrase_str)

    def get_voices(self) -> List[Dict[str, Any]]:
        """Returns installed SAPI5 voices or empty list if unavailable."""
        with self._lock:
            return list(self._voices_cache)

    def get_status(self) -> Dict[str, Any]:
        """Return truthful generation, playback, selected-engine and queue state."""
        with self._lock:
            worker_alive = self._worker_thread.is_alive() if hasattr(self, "_worker_thread") else False
            natural_worker_alive = self._natural_worker_thread.is_alive() if hasattr(self, "_natural_worker_thread") else False
            playback_worker_alive = self._playback_worker_thread.is_alive() if hasattr(self, "_playback_worker_thread") else False
            natural_configured = self._natural_is_configured()
            human_configured = self._human_is_configured()
            provider = self.settings.provider
            selected_available = {
                "system": self._engine_available,
                "gemini": natural_configured,
                "xtts": human_configured,
                "text_only": True,
            }.get(provider, False)
            audio_status = {}
            status_fn = getattr(self._natural_audio_player, "status", None)
            if callable(status_fn):
                try:
                    audio_status = status_fn()
                except Exception:
                    audio_status = {}
            err_stat = self._error_status
            load_err = getattr(self, "_load_error", None)
            if load_err and err_stat == "Ready":
                err_stat = f"Ready ({load_err})"
            return {
                "is_speaking": self._is_speaking,
                "is_audio_playing": self._is_speaking,
                "is_generating_audio": self._generation_busy,
                "queue_size": self._pending_count,
                "enabled": self.settings.enabled,
                "provider": provider,
                "natural_voice": self.settings.natural_voice,
                "human_voice_profile": self.settings.human_voice_profile,
                "speech_language": self.settings.speech_language,
                "voice_style": self.settings.voice_style,
                "failure_behavior": self.settings.failure_behavior,
                "fallback_provider": self.settings.fallback_provider,
                "fast_start_enabled": self.settings.fast_start_enabled,
                "fast_chunk_characters": self.settings.fast_chunk_characters,
                "first_chunk_characters": self.settings.first_chunk_characters,
                "stable_audio_enabled": self.settings.stable_audio_enabled,
                "trim_boundary_silence": self.settings.trim_boundary_silence,
                "prepare_during_silence": self.settings.prepare_during_silence,
                "prepared_audio_count": len(self._prepared_audio),
                "active_backend": self._active_backend,
                "selected_backend_available": selected_available,
                "natural_tts_configured": natural_configured,
                "human_tts_configured": human_configured,
                "human_voice_count": len(self.get_human_voices()),
                "natural_tts_last_error": self._natural_last_error,
                "voice_last_error": self._natural_last_error,
                "engine_available": self._engine_available,
                "engine_initializing": self._engine_initializing,
                "error_status": err_stat,
                "current_text": self._current_text,
                "running": self._running,
                "worker_alive": worker_alive,
                "natural_worker_alive": natural_worker_alive,
                "playback_worker_alive": playback_worker_alive,
                "audio_output": audio_status,
                "shutdown_state": self._shutdown_state,
            }

    def shutdown(self, timeout: float = 3.0) -> Dict[str, Any]:
        with self._lock:
            if not self._running or self._shutdown_state in {"shutting_down", "shut_down"}:
                return {"accepted": False, "reason": "Already shut down or shutting down"}
            self._shutdown_requested = True
            self._shutdown_state = "shutting_down"
            self._running = False
            self._speech_epoch += 1
            self._pending_count = 0
            self._prepared_audio.clear()
            self._is_speaking = False
            self._generation_busy = False
            self._current_text = None
            self._active_utt_id = None
            self._active_seq = None
            self._active_backend = "none"
            self._engine_available = False
            self._error_status = "Shutting down"
            self._natural_stop_event.set()
        try:
            self._natural_audio_player.stop()
        except Exception:
            pass
        self._cmd_queue.put({"action": "SHUTDOWN"})
        self._natural_cmd_queue.put({"action": "SHUTDOWN"})
        self._playback_queue.put({"action": "SHUTDOWN"})

        current = threading.current_thread()
        workers = (self._worker_thread, self._natural_worker_thread, self._playback_worker_thread)
        for worker in workers:
            if worker.is_alive() and current != worker:
                worker.join(timeout=max(0.0, float(timeout)))
        worker_alive = any(worker.is_alive() for worker in workers)
        if not worker_alive:
            close = getattr(self._natural_audio_player, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        with self._lock:
            if worker_alive:
                self._shutdown_state = "shutdown_timeout"
                self._error_status = "Worker thread termination timed out"
                return {"accepted": False, "reason": "Worker thread termination timed out"}
            self._shutdown_state = "shut_down"
            self._error_status = "Service shut down"
            return {"accepted": True, "reason": "TTS service shut down cleanly"}

    def _natural_worker_loop(self) -> None:
        """Generate neural audio ahead of a separate persistent playback worker."""
        while True:
            try:
                command = self._natural_cmd_queue.get(timeout=0.1)
            except queue.Empty:
                with self._lock:
                    if not self._running and self._shutdown_requested:
                        break
                continue
            action = command.get("action")
            if action == "SHUTDOWN":
                break
            if action == "STOP":
                continue
            if action not in {"SPEAK", "TEST_SPEAK"}:
                continue

            seq = int(command.get("seq", 0) or 0)
            epoch = int(command.get("epoch", -1))
            provider = str(command.get("provider", "gemini"))
            settings = command.get("settings") or {}
            with self._lock:
                stale = (
                    seq <= self._natural_cutoff_seq
                    or epoch != self._speech_epoch
                    or not self._running
                    or not self.settings.enabled
                    or provider not in {self.settings.provider, (self.settings.fallback_provider if self.settings.failure_behavior == "selected_fallback" else "none")}
                )
                if stale:
                    self._pending_count = max(0, self._pending_count - 1)
                    continue
                self._generation_busy = True

            try:
                prepared = command.get("prepared_wav")
                if isinstance(prepared, (bytes, bytearray)) and prepared:
                    wav_bytes = bytes(prepared)
                else:
                    attempts = 2 if settings.get("failure_behavior") == "retry_once" else 1
                    last_error: Optional[Exception] = None
                    wav_bytes = b""
                    for _attempt in range(attempts):
                        try:
                            wav_bytes = self._generate_voice_wav(
                                provider, command.get("text", ""), settings
                            )
                            last_error = None
                            break
                        except Exception as exc:
                            last_error = exc
                    if last_error is not None:
                        raise last_error

                with self._lock:
                    stale = (
                        seq <= self._natural_cutoff_seq
                        or epoch != self._speech_epoch
                        or not self._running
                    )
                if stale:
                    with self._lock:
                        self._pending_count = max(0, self._pending_count - 1)
                    continue
                packet = dict(command)
                packet["action"] = "PLAY"
                packet["wav"] = wav_bytes
                self._playback_queue.put(packet)
                self._natural_last_error = ""
            except Exception as exc:
                self._natural_last_error = str(exc)[:240]
                logger.warning("[Freshy TTS] %s voice failed: %s", provider, self._natural_last_error)
                fallback = self._selected_fallback_provider(provider, settings)
                if fallback == "system":
                    fallback_command = dict(command)
                    fallback_command["provider"] = "system"
                    fallback_command["settings"] = {**settings, "provider": "system"}
                    self._cmd_queue.put(fallback_command)
                elif fallback in {"gemini", "xtts"}:
                    fallback_command = dict(command)
                    fallback_command["provider"] = fallback
                    fallback_command["settings"] = {**settings, "provider": fallback, "failure_behavior": "silent"}
                    self._natural_cmd_queue.put(fallback_command)
                else:
                    with self._lock:
                        self._pending_count = max(0, self._pending_count - 1)
            finally:
                with self._lock:
                    self._generation_busy = False

    def _playback_worker_loop(self) -> None:
        """Play normalized WAV packets serially on one reusable output stream."""
        while True:
            try:
                packet = self._playback_queue.get(timeout=0.1)
            except queue.Empty:
                with self._lock:
                    if not self._running and self._shutdown_requested:
                        break
                continue
            action = packet.get("action")
            if action == "SHUTDOWN":
                break
            if action == "STOP":
                try:
                    self._natural_audio_player.stop()
                except Exception:
                    pass
                continue
            if action != "PLAY":
                continue
            seq = int(packet.get("seq", 0) or 0)
            epoch = int(packet.get("epoch", -1))
            provider = str(packet.get("provider", "gemini"))
            with self._lock:
                stale = (
                    seq <= self._natural_cutoff_seq
                    or epoch != self._speech_epoch
                    or not self._running
                    or provider not in {self.settings.provider, (self.settings.fallback_provider if self.settings.failure_behavior == "selected_fallback" else "none")}
                )
                if stale:
                    self._pending_count = max(0, self._pending_count - 1)
                    continue
                self._is_speaking = True
                self._current_text = str(packet.get("full_text") or packet.get("text") or "")
                self._active_utt_id = packet.get("utt_id")
                self._active_seq = seq
                self._active_backend = provider
            try:
                self._natural_stop_event.clear()
                self._natural_audio_player.play(packet.get("wav", b""))
            except Exception as exc:
                self._natural_last_error = str(exc)[:240]
                logger.warning("[Freshy TTS] Stable playback failed: %s", self._natural_last_error)
            finally:
                with self._lock:
                    self._pending_count = max(0, self._pending_count - 1)
                    if self._active_seq == seq:
                        self._is_speaking = False
                        self._current_text = None
                        self._active_utt_id = None
                        self._active_seq = None
                        self._active_backend = "none"
        try:
            self._natural_audio_player.stop()
        except Exception:
            pass

    def _worker_loop(self) -> None:
        """Dedicated worker/COM thread for pyttsx3 engine operations."""
        engine = None
        _pending_speech_deque = collections.deque()
        latest_cutoff_seq = 0
        com_initialized = False
        system_default_voice_id = ""

        def mark_engine_failed(error_msg: str):
            nonlocal engine
            with self._lock:
                self._engine_available = False
                self._engine_initializing = False
                self._error_status = f"Runtime engine error: {error_msg}"
                self._is_speaking = False
                self._current_text = None
                self._active_utt_id = None
                self._active_seq = None
                self._active_backend = "none"
                self._pending_count = 0

            preserved_shutdown_commands = []
            while True:
                try:
                    queued_command = self._cmd_queue.get_nowait()
                except queue.Empty:
                    break
                if queued_command.get("action") == "SHUTDOWN":
                    preserved_shutdown_commands.append(queued_command)

            for shutdown_command in preserved_shutdown_commands:
                self._cmd_queue.put(shutdown_command)

            if engine:
                try:
                    engine.stop()
                except Exception:
                    pass

            _pending_speech_deque.clear()

        def on_start(name):
            with self._lock:
                if name == self._active_utt_id:
                    self._is_speaking = True
                    self._active_backend = "system"

        def on_end(name, completed):
            with self._lock:
                if name == self._active_utt_id:
                    self._is_speaking = False
                    self._current_text = None
                    self._active_utt_id = None
                    self._active_seq = None
                    self._active_backend = "none"

        def on_error(name, exception):
            logger.warning(f"[Freshy TTS] Speech error callback: {exception}")
            mark_engine_failed(str(exception))

        def normalize_lang(lang_obj: Any) -> str:
            if isinstance(lang_obj, bytes):
                try:
                    return lang_obj.decode("utf-8", errors="ignore").strip()
                except Exception:
                    return str(lang_obj)
            return str(lang_obj) if lang_obj is not None else ""

        try:
            self._com_initialize()
            com_initialized = True
        except Exception as e:
            logger.warning(f"[Freshy TTS] COM init error: {e}")
            mark_engine_failed(f"COM initialization failed: {e}")

        try:
            if not com_initialized:
                with self._lock:
                    com_error = self._error_status
                raise RuntimeError(com_error)
            engine = self._engine_factory()
            if hasattr(engine, 'startLoop'):
                engine.startLoop(False)

            try:
                system_default_voice_id = str(engine.getProperty('voice') or '')
            except Exception as de:
                logger.warning(f"[Freshy TTS] Could not read system default voice: {de}")

            try:
                engine.connect('started-utterance', on_start)
                engine.connect('finished-utterance', on_end)
                engine.connect('error', on_error)
            except Exception as ce:
                raise RuntimeError(f"Callback connection failed: {ce}")

            with self._lock:
                self._engine_available = True
                self._engine_initializing = False
                self._error_status = "Ready"
                try:
                    voices = engine.getProperty('voices')
                    if voices:
                        cache = []
                        for v in voices:
                            raw_langs = getattr(v, 'languages', []) or []
                            normalized_langs = [normalize_lang(l) for l in raw_langs if l is not None]
                            cache.append({
                                "id": str(getattr(v, 'id', '') or ''),
                                "name": str(getattr(v, 'name', 'Unknown Voice') or 'Unknown Voice'),
                                "languages": normalized_langs
                            })
                        self._voices_cache = cache
                        if not system_default_voice_id and cache:
                            system_default_voice_id = cache[0]["id"]

                        # Validate persisted selected_voice against installed voices
                        if self.settings.selected_voice:
                            valid_ids = {voice_dict["id"] for voice_dict in self._voices_cache}
                            if self.settings.selected_voice not in valid_ids:
                                logger.warning(
                                    f"[Freshy TTS] Persisted selected_voice '{self.settings.selected_voice}' not found in installed voices. Fallback to default."
                                )
                                self.settings.selected_voice = ""
                                self.save_settings()
                except Exception as ve:
                    logger.warning(f"[Freshy TTS] Error fetching voices: {ve}")
                    self._voices_cache = []
        except Exception as e:
            logger.warning(f"[Freshy TTS] Engine init failed: {e}")
            if com_initialized:
                mark_engine_failed(str(e))

        def apply_engine_properties(settings_dict: Optional[Dict[str, Any]] = None) -> bool:
            if not engine:
                return False
            try:
                if settings_dict is None:
                    with self._lock:
                        rate = self.settings.rate
                        volume = self.settings.volume
                        voice = self.settings.selected_voice
                else:
                    rate = settings_dict.get("rate", 175)
                    volume = settings_dict.get("volume", 1.0)
                    voice = settings_dict.get("selected_voice", "")

                engine.setProperty('rate', rate)
                engine.setProperty('volume', volume)
                target_voice = voice or system_default_voice_id
                if target_voice:
                    engine.setProperty('voice', target_voice)
                return True
            except Exception as se:
                logger.warning(f"[Freshy TTS] Error applying engine properties: {se}")
                mark_engine_failed(f"Failed to set engine property: {se}")
                return False

        if engine and self._engine_available:
            apply_engine_properties()

        def clear_speech_before_cutoff(cutoff_seq: int):
            nonlocal engine, latest_cutoff_seq
            latest_cutoff_seq = max(latest_cutoff_seq, cutoff_seq)

            with self._lock:
                active_seq = self._active_seq
            if active_seq is not None and active_seq <= cutoff_seq:
                if engine:
                    try:
                        engine.stop()
                    except Exception as se:
                        logger.warning(f"[Freshy TTS] Engine stop warning: {se}")
                        mark_engine_failed(f"Engine stop failed: {se}")
                        return
                with self._lock:
                    self._is_speaking = False
                    self._current_text = None
                    self._active_utt_id = None
                    self._active_seq = None
                    self._active_backend = "none"

            cleared_from_deque = 0
            new_deque = collections.deque()
            for item in _pending_speech_deque:
                if item["seq"] <= cutoff_seq:
                    cleared_from_deque += 1
                else:
                    new_deque.append(item)
            _pending_speech_deque.clear()
            _pending_speech_deque.extend(new_deque)

            if cleared_from_deque > 0:
                with self._lock:
                    self._pending_count = max(0, self._pending_count - cleared_from_deque)

        try:
            while True:
                try:
                    cmd = self._cmd_queue.get(timeout=0.01)
                except queue.Empty:
                    cmd = None

                if cmd:
                    action = cmd.get("action")
                    if action == "SHUTDOWN":
                        break
                    elif action == "STOP":
                        cutoff_seq = cmd.get("cutoff_seq", 0)
                        clear_speech_before_cutoff(cutoff_seq)
                    elif action == "DISABLE":
                        cutoff_seq = cmd.get("cutoff_seq", 0)
                        apply_engine_properties(cmd.get("settings"))
                        clear_speech_before_cutoff(cutoff_seq)
                    elif action in ("ENABLE", "APPLY_SETTINGS"):
                        apply_engine_properties(cmd.get("settings"))
                    elif action in ("SPEAK", "TEST_SPEAK"):
                        seq = cmd.get("seq", 0)
                        cutoff_seq = cmd.get("cutoff_seq", None)

                        # If command is at or before a cutoff, discard it
                        if seq <= latest_cutoff_seq:
                            with self._lock:
                                self._pending_count = max(0, self._pending_count - 1)
                        else:
                            if cutoff_seq is not None:
                                clear_speech_before_cutoff(cutoff_seq)

                            text = cmd.get("text", "").strip()
                            utt_id = cmd.get("utt_id")
                            with self._lock:
                                enabled = self.settings.enabled
                                engine_ok = self._engine_available
                                service_running = self._running
                            if text and enabled and engine_ok and service_running:
                                _pending_speech_deque.append({"text": text, "utt_id": utt_id, "seq": seq})
                            else:
                                with self._lock:
                                    self._pending_count = max(0, self._pending_count - 1)

                with self._lock:
                    can_speak = (
                        self._running
                        and (not self._is_speaking)
                        and (self._active_utt_id is None)
                        and self._engine_available
                        and self.settings.enabled
                    )

                if can_speak and _pending_speech_deque and engine:
                    next_item = _pending_speech_deque.popleft()
                    properties_applied = apply_engine_properties()
                    with self._lock:
                        ready_after_properties = (
                            properties_applied
                            and self._running
                            and self._engine_available
                            and self.settings.enabled
                        )

                    if not ready_after_properties:
                        with self._lock:
                            self._pending_count = max(0, self._pending_count - 1)
                    else:
                        with self._lock:
                            self._is_speaking = True
                            self._current_text = next_item["text"]
                            self._active_utt_id = next_item["utt_id"]
                            self._active_seq = next_item["seq"]
                            self._active_backend = "system"
                            self._pending_count = max(0, self._pending_count - 1)
                        try:
                            engine.say(next_item["text"], name=next_item["utt_id"])
                        except Exception as se:
                            logger.warning(f"[Freshy TTS] engine.say failed: {se}")
                            mark_engine_failed(f"Speech output failed: {se}")

                if engine and self._engine_available:
                    try:
                        engine.iterate()
                    except Exception as ie:
                        logger.warning(f"[Freshy TTS] engine.iterate error: {ie}")
                        mark_engine_failed(f"Engine iteration failed: {ie}")

        except Exception as le:
            logger.warning(f"[Freshy TTS] Worker loop exception: {le}")
        finally:
            if engine:
                try:
                    engine.stop()
                except Exception:
                    pass
                try:
                    if hasattr(engine, 'endLoop'):
                        engine.endLoop()
                except Exception:
                    pass

            if com_initialized:
                try:
                    self._com_uninitialize()
                except Exception as ce:
                    logger.warning(f"[Freshy TTS] COM uninit error: {ce}")

            with self._lock:
                self._engine_available = False
                self._engine_initializing = False
                self._is_speaking = False
                self._current_text = None
                self._active_utt_id = None
                self._active_seq = None
                self._active_backend = "none"
                self._pending_count = 0
                if not self._shutdown_requested:
                    self._running = False
                    self._shutdown_state = "failed"
                    self._error_status = "Worker loop terminated unexpectedly"
                else:
                    # A previous join timeout describes only that instant.
                    # Once the worker exits, the final state is shut_down.
                    self._shutdown_state = "shut_down"
                    self._error_status = "Service shut down"
