import os
from typing import List

from dotenv import load_dotenv

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CORE_DIR)

# Load only the project-local secret file. This remains optional and is ignored by Git.
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)


def _env_path(name: str, default: str) -> str:
    raw = os.getenv(name, "").strip()
    if not raw:
        return os.path.abspath(default)
    if os.path.isabs(raw):
        return os.path.normpath(raw)
    return os.path.abspath(os.path.join(PROJECT_ROOT, raw))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return default


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return value if minimum <= value <= maximum else default


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return value if minimum <= value <= maximum else default


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    return value if value in allowed else default


def _provider_order() -> List[str]:
    supported = {"groq", "mistral", "gemini", "sambanova"}
    raw = os.getenv("AI_PROVIDER_ORDER", "groq,mistral,gemini,sambanova")
    ordered: List[str] = []
    for item in raw.split(","):
        name = item.strip().lower()
        if name in supported and name not in ordered:
            ordered.append(name)
    return ordered or ["groq", "mistral", "gemini", "sambanova"]


class Config:
    HOST: str = os.getenv("FRESHY_CORE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    PORT: int = _env_int("FRESHY_CORE_PORT", 8000, 1, 65535)
    DEBUG: bool = _env_bool("DEBUG", False)
    APP_NAME: str = "Freshy AI Core"
    VERSION: str = "6.0.5 - Phase 6A Memory Speech Hotfix"

    # Phase 4 AI routing
    AI_ENABLED: bool = _env_bool("AI_ENABLED", True)
    AI_PROVIDER_ORDER: List[str] = _provider_order()

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()

    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "").strip()
    MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest").strip()
    MISTRAL_BASE_URL: str = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1").strip()

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    GEMINI_TTS_MODEL: str = os.getenv(
        "GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"
    ).strip() or "gemini-2.5-flash-preview-tts"

    SAMBANOVA_API_KEY: str = os.getenv("SAMBANOVA_API_KEY", "").strip()
    SAMBANOVA_MODEL: str = os.getenv("SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct").strip()
    SAMBANOVA_BASE_URL: str = os.getenv("SAMBANOVA_BASE_URL", "https://api.sambanova.ai/v1").strip()

    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "").strip()

    AI_REQUEST_TIMEOUT_SECONDS: int = _env_int("AI_REQUEST_TIMEOUT_SECONDS", 25, 1, 300)
    AI_MAX_RETRIES: int = _env_int("AI_MAX_RETRIES", 1, 0, 3)
    AI_PROVIDER_COOLDOWN_SECONDS: int = _env_int("AI_PROVIDER_COOLDOWN_SECONDS", 60, 1, 3600)
    AI_MAX_HISTORY_MESSAGES: int = _env_int("AI_MAX_HISTORY_MESSAGES", 16, 2, 100)
    AI_MAX_HISTORY_CHARACTERS: int = _env_int("AI_MAX_HISTORY_CHARACTERS", 24000, 1000, 100000)
    AI_MAX_INPUT_CHARACTERS: int = _env_int("AI_MAX_INPUT_CHARACTERS", 12000, 100, 50000)
    AI_MAX_OUTPUT_TOKENS: int = _env_int("AI_MAX_OUTPUT_TOKENS", 1200, 64, 10000)
    AI_TEMPERATURE: float = _env_float("AI_TEMPERATURE", 0.3, 0.0, 2.0)

    WEB_SEARCH_ENABLED: bool = _env_bool("WEB_SEARCH_ENABLED", True)
    TAVILY_SEARCH_DEPTH: str = _env_choice("TAVILY_SEARCH_DEPTH", "basic", {"basic", "advanced"})
    TAVILY_MAX_RESULTS: int = _env_int("TAVILY_MAX_RESULTS", 5, 1, 20)
    TAVILY_TIMEOUT_SECONDS: int = _env_int("TAVILY_TIMEOUT_SECONDS", 15, 1, 60)

    # Phase 5 persistent memory and personalization
    MEMORY_ENABLED: bool = _env_bool("MEMORY_ENABLED", True)
    MEMORY_MODE: str = _env_choice(
        "MEMORY_MODE",
        "ask_before_saving",
        {"ask_before_saving", "auto_safe", "manual_only", "disabled"},
    )
    MEMORY_DATABASE_PATH: str = _env_path(
        "MEMORY_DATABASE_PATH",
        os.path.join(CORE_DIR, "data", "freshy_memory.db"),
    )
    MEMORY_MAX_ITEMS: int = _env_int("MEMORY_MAX_ITEMS", 500, 10, 5000)
    MEMORY_MAX_ITEM_CHARACTERS: int = _env_int(
        "MEMORY_MAX_ITEM_CHARACTERS", 2000, 100, 10000
    )
    MEMORY_RECALL_LIMIT: int = _env_int("MEMORY_RECALL_LIMIT", 6, 1, 20)
    MEMORY_RECALL_CHARACTERS: int = _env_int(
        "MEMORY_RECALL_CHARACTERS", 2500, 250, 12000
    )
    MEMORY_PERSIST_CONVERSATIONS: bool = _env_bool(
        "MEMORY_PERSIST_CONVERSATIONS", True
    )
    MEMORY_CONVERSATION_RETENTION_DAYS: int = _env_int(
        "MEMORY_CONVERSATION_RETENTION_DAYS", 30, 1, 3650
    )
    MEMORY_AUTO_PROFILE_DETECTION: bool = _env_bool(
        "MEMORY_AUTO_PROFILE_DETECTION", True
    )

    # Phase 6 real-time Gemini Live voice agent. Standard mode remains available.
    LIVE_VOICE_ENABLED: bool = _env_bool("LIVE_VOICE_ENABLED", True)
    LIVE_CONVERSATION_MODE: str = _env_choice(
        "LIVE_CONVERSATION_MODE", "standard", {"standard", "live"}
    )
    GEMINI_LIVE_MODEL: str = os.getenv(
        "GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview"
    ).strip() or "gemini-3.1-flash-live-preview"
    GEMINI_LIVE_VOICE: str = os.getenv("GEMINI_LIVE_VOICE", "Kore").strip() or "Kore"
    LIVE_AUTO_START: bool = _env_bool("LIVE_AUTO_START", False)
    LIVE_SILENCE_DURATION_MS: int = _env_int("LIVE_SILENCE_DURATION_MS", 700, 200, 5000)
    LIVE_PREFIX_PADDING_MS: int = _env_int("LIVE_PREFIX_PADDING_MS", 120, 20, 1000)
    LIVE_MICROPHONE_CHUNK_MS: int = _env_int("LIVE_MICROPHONE_CHUNK_MS", 40, 20, 200)
    LIVE_OUTPUT_BUFFER_MS: int = _env_int("LIVE_OUTPUT_BUFFER_MS", 80, 20, 1000)
    LIVE_FALLBACK_MODE: str = _env_choice(
        "LIVE_FALLBACK_MODE", "standard", {"standard", "text_only"}
    )
    LIVE_SETTINGS_FILE: str = _env_path(
        "LIVE_SETTINGS_FILE", os.path.join(CORE_DIR, "live_settings.json")
    )

    # TTS Environment Defaults
    TTS_ENABLED: bool = _env_bool("TTS_ENABLED", True)
    TTS_PROVIDER: str = _env_choice(
        "TTS_PROVIDER", "gemini", {"system", "gemini", "xtts", "text_only"}
    )
    TTS_NATURAL_VOICE: str = _env_choice(
        "TTS_NATURAL_VOICE", "hindi_female", {"hindi_female", "hindi_male"}
    )
    _TTS_LANGUAGE_RAW: str = os.getenv("TTS_SPEECH_LANGUAGE", "auto").strip() or "auto"
    TTS_SPEECH_LANGUAGE: str = (
        _TTS_LANGUAGE_RAW if _TTS_LANGUAGE_RAW in {"auto", "hi-IN", "en-IN"} else "auto"
    )
    TTS_GEMINI_TIMEOUT_SECONDS: int = _env_int("TTS_GEMINI_TIMEOUT_SECONDS", 30, 5, 90)
    TTS_RATE: int = _env_int("TTS_RATE", 175, 50, 400)
    TTS_VOLUME: float = _env_float("TTS_VOLUME", 1.0, 0.0, 1.0)
    TTS_SELECTED_VOICE: str = os.getenv("TTS_SELECTED_VOICE", "").strip()
    TTS_STARTUP_GREETING: bool = _env_bool("TTS_STARTUP_GREETING", True)
    TTS_FAST_START_ENABLED: bool = _env_bool("TTS_FAST_START_ENABLED", True)
    TTS_PREPARE_DURING_SILENCE: bool = _env_bool("TTS_PREPARE_DURING_SILENCE", True)
    TTS_FAST_CHUNK_CHARACTERS: int = _env_int("TTS_FAST_CHUNK_CHARACTERS", 260, 120, 600)
    TTS_FIRST_CHUNK_CHARACTERS: int = _env_int("TTS_FIRST_CHUNK_CHARACTERS", 150, 80, 300)
    TTS_VOICE_STYLE: str = _env_choice(
        "TTS_VOICE_STYLE", "natural", {"natural", "warm", "calm", "professional", "cinematic"}
    )
    TTS_FAILURE_BEHAVIOR: str = _env_choice(
        "TTS_FAILURE_BEHAVIOR", "silent", {"silent", "retry_once", "selected_fallback"}
    )
    TTS_FALLBACK_PROVIDER: str = _env_choice(
        "TTS_FALLBACK_PROVIDER", "none", {"none", "system", "gemini", "xtts"}
    )
    TTS_HUMAN_VOICE_PROFILE: str = os.getenv("TTS_HUMAN_VOICE_PROFILE", "").strip()
    TTS_STABLE_AUDIO_ENABLED: bool = _env_bool("TTS_STABLE_AUDIO_ENABLED", True)
    TTS_TRIM_BOUNDARY_SILENCE: bool = _env_bool("TTS_TRIM_BOUNDARY_SILENCE", True)

    # Optional human/cloned XTTS voice. The isolated server keeps its heavy
    # model dependencies separate from the main Freshy environment.
    XTTS_MODE: str = _env_choice("XTTS_MODE", "disabled", {"disabled", "server", "local"})
    XTTS_SERVER_URL: str = os.getenv("XTTS_SERVER_URL", "http://127.0.0.1:8020").strip()
    XTTS_SERVER_TOKEN: str = os.getenv("XTTS_SERVER_TOKEN", "").strip()
    XTTS_TIMEOUT_SECONDS: int = _env_int("XTTS_TIMEOUT_SECONDS", 45, 5, 180)
    XTTS_MODEL_NAME: str = os.getenv(
        "XTTS_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2"
    ).strip()
    XTTS_USE_GPU: bool = _env_bool("XTTS_USE_GPU", True)

    # Phase 4.2 hybrid voice-input defaults
    VOICE_RECOGNITION_ENGINE: str = _env_choice("VOICE_RECOGNITION_ENGINE", "auto", {"auto", "vosk", "whisper"})
    WHISPER_MODEL: str = _env_choice("WHISPER_MODEL", "base", {"tiny", "base", "small"})
    VOICE_RESPONSE_SILENCE_SECONDS: float = _env_float("VOICE_RESPONSE_SILENCE_SECONDS", 3.0, 1.0, 5.0)

    # Phase 3/4.2 voice-input paths
    VOICE_SETTINGS_FILE: str = _env_path(
        "VOICE_SETTINGS_FILE",
        os.path.join(CORE_DIR, "voice_settings.json"),
    )
    VOICE_MODEL_DIR: str = _env_path(
        "VOICE_MODEL_DIR",
        os.path.join(CORE_DIR, "models", "vosk-model-small-en-in-0.4"),
    )


config = Config()
