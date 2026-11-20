import logging
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
from typing import Dict, Any, List, Optional

from config import config
from executor import CommandExecutor
from gemini_client import GeminiIntentAnalyzer
from intents import RuleBasedIntentParser
from tts_service import TTSService, TTSSettings
from voice_input_service import VoiceInputService, UnavailableVoiceInputService
from ai.assistant_orchestrator import AssistantOrchestrator
from ai.schemas import ChatRequest as AIChatRequest, AssistantResponse
from memory.schemas import (
    MemoryClearRequest, MemoryCreateRequest, MemoryImportRequest, MemoryListResponse,
    MemorySettingsUpdateRequest, MemoryUpdateRequest, MemoryCandidate,
)
from memory.safety import inspect_memory_text
from live import LiveSessionManager, LiveSettings
from live.tool_bridge import LiveToolBridge

logger = logging.getLogger("FreshyMain")

executor = CommandExecutor()
gemini_analyzer = GeminiIntentAnalyzer()
orchestrator = AssistantOrchestrator()

_tts_lock = threading.Lock()
tts_service: Optional[Any] = None

_voice_lock = threading.Lock()
voice_service: Optional[Any] = None

_live_lock = threading.Lock()
live_service: Optional[Any] = None

def _live_memory_context() -> str:
    try:
        items, _total = orchestrator.memory_service.store.list_memories(limit=12)
    except Exception:
        return ""
    lines = []
    for item in items:
        if item.category not in {"profile", "preference", "project"} and not item.pinned:
            continue
        lines.append(f"- {item.key.replace('_', ' ')}: {item.value}")
    return "\n".join(lines[:10])[:3000]

def _persist_live_turn(user_text: str, assistant_text: str) -> None:
    session_id = "live-voice-session"
    orchestrator.conversation_store.add_message(session_id, "user", user_text)
    orchestrator.conversation_store.add_message(session_id, "assistant", assistant_text)


def _handle_live_fallback(mode: str) -> None:
    if mode != "text_only":
        return
    try:
        get_tts_service().stop_speaking()
        get_tts_service().update_settings({"provider": "text_only"})
    except Exception:
        logger.debug("Could not switch Standard TTS to text-only fallback", exc_info=True)


def get_live_service() -> Any:
    global live_service
    with _live_lock:
        if live_service is None:
            live_service = LiveSessionManager(
                settings_file=config.LIVE_SETTINGS_FILE,
                tool_bridge=LiveToolBridge(orchestrator.tool_registry, orchestrator.memory_service),
                memory_context_provider=_live_memory_context,
                turn_persistence_callback=_persist_live_turn,
                fallback_callback=_handle_live_fallback,
            )
        return live_service

def set_live_service(service: Optional[Any]) -> None:
    global live_service
    old_service = None
    with _live_lock:
        old_service = live_service
        live_service = service
    if old_service is not None and old_service is not service:
        try:
            old_service.stop()
        except Exception:
            pass

def prepare_voice_chat_message(
    message: str, session_id: str = "voice-session"
) -> Dict[str, Any]:
    """Create a non-tool speculative draft for a stable partial transcript."""
    try:
        prepared = orchestrator.prepare_draft(
            AIChatRequest(
                message=message,
                session_id=session_id or "voice-session",
                allow_web_search=False,
            )
        )
        if prepared is None:
            return {}
        payload = prepared.model_dump()
        try:
            prefetch = getattr(get_tts_service(), "prepare_speech", None)
            if callable(prefetch):
                prepared_audio = prefetch(prepared.speech_text or prepared.reply)
                token = str(prepared_audio.get("token", "") or "")
                if prepared_audio.get("accepted") and token:
                    payload["_voice_audio_token"] = token
        except Exception as audio_exc:
            logger.debug("[Freshy Core] Voice audio prefetch skipped: %s", audio_exc)
        return payload
    except Exception as exc:
        logger.debug("[Freshy Core] Voice preflight skipped: %s", exc)
        return {}


def process_voice_chat_message(
    message: str, prepared_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Handle a final voice transcript, optionally reusing a validated draft."""
    logger.info("[Freshy Core] Processing final voice transcript")
    try:
        prepared_audio_token = ""
        if prepared_result:
            prepared_audio_token = str(
                prepared_result.get("_voice_audio_token", "") or ""
            )
            prepared_payload = {
                key: value
                for key, value in prepared_result.items()
                if not str(key).startswith("_voice_")
            }
            prepared = AssistantResponse.model_validate(prepared_payload)
            ai_res = orchestrator.commit_prepared(
                AIChatRequest(
                    message=message,
                    session_id="voice-session",
                    allow_web_search=False,
                ),
                prepared,
            )
            res = _assistant_response_to_chat_response(
                ai_res, prepared_audio_token=prepared_audio_token or None
            )
        else:
            res = handle_chat(
                ChatRequest(
                    message=message,
                    session_id="voice-session",
                    allow_web_search=True,
                )
            )
        return {
            "reply": res.reply,
            "intent_name": res.intent_name,
            "success": res.success,
            "action_executed": res.action_executed,
            "freshy_status": res.freshy_status,
            "details": res.details,
        }
    except Exception as exc:
        logger.error("[Freshy Core] Error executing voice transcript chat: %s", exc)
        return {
            "reply": "Freshy could not process that voice command.",
            "intent_name": "ERROR",
            "success": False,
            "action_executed": False,
            "freshy_status": "idle",
            "details": {"error": "voice_command_failed"},
        }

def get_voice_service() -> Any:
    global voice_service
    with _voice_lock:
        if voice_service is None:
            try:
                def stop_tts_callback():
                    try:
                        get_tts_service().stop_speaking()
                    except Exception:
                        pass

                def get_tts_status_callback():
                    try:
                        return get_tts_service().get_status()
                    except Exception:
                        return {
                            "is_speaking": False,
                            "queue_size": 0,
                        }

                voice_service = VoiceInputService(
                    settings_file=config.VOICE_SETTINGS_FILE,
                    model_dir=config.VOICE_MODEL_DIR,
                    chat_callback=process_voice_chat_message,
                    prepare_callback=prepare_voice_chat_message,
                    tts_stop_callback=stop_tts_callback,
                    tts_status_callback=get_tts_status_callback,
                )
            except Exception as ve:
                logger.error(f"[Freshy Core] VoiceInputService initialization error: {ve}")
                voice_service = UnavailableVoiceInputService(str(ve))
        return voice_service

def set_voice_service(service: Optional[Any]) -> None:
    global voice_service
    old_service = None
    with _voice_lock:
        old_service = voice_service
        voice_service = service
    if old_service is not None and old_service is not service:
        try:
            old_service.shutdown()
        except Exception:
            pass

class UnavailableTTSService:
    """No-thread fallback that keeps Freshy Core usable if TTS cannot start."""

    def __init__(self, reason: str):
        self.settings = TTSSettings()
        self._reason = f"TTS service unavailable: {reason}"

    def speak(
        self, text: str, prepared_token: Optional[str] = None
    ) -> Dict[str, Any]:
        del text, prepared_token
        return {"accepted": False, "reason": self._reason}

    def prepare_speech(self, text: str) -> Dict[str, Any]:
        del text
        return {"accepted": False, "reason": self._reason}

    def test_voice(self, phrase: str = "") -> Dict[str, Any]:
        return {"accepted": False, "reason": self._reason}

    def stop_speaking(self) -> Dict[str, Any]:
        return {"accepted": False, "reason": self._reason}

    def get_voices(self) -> List[Dict[str, Any]]:
        return []

    def get_human_voices(self) -> List[Dict[str, Any]]:
        return []

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_speaking": False,
            "queue_size": 0,
            "enabled": self.settings.enabled,
            "provider": self.settings.provider,
            "natural_voice": self.settings.natural_voice,
            "human_voice_profile": self.settings.human_voice_profile,
            "speech_language": self.settings.speech_language,
            "voice_style": self.settings.voice_style,
            "is_audio_playing": False,
            "is_generating_audio": False,
            "active_backend": "none",
            "selected_backend_available": False,
            "natural_tts_configured": False,
            "human_tts_configured": False,
            "human_voice_count": 0,
            "engine_available": False,
            "engine_initializing": False,
            "error_status": self._reason,
            "current_text": None,
            "running": False,
            "worker_alive": False,
            "shutdown_state": "failed",
        }

    def update_settings(self, updates: Dict[str, Any]) -> TTSSettings:
        raise RuntimeError(self._reason)

    def shutdown(self, timeout: float = 0.0) -> Dict[str, Any]:
        return {"accepted": True, "reason": "Fallback TTS service has no worker"}

def get_tts_service() -> Any:
    global tts_service
    with _tts_lock:
        if tts_service is None:
            try:
                tts_service = TTSService()
            except Exception as e:
                logger.error(f"[Freshy Core] TTSService initialization error: {e}")
                tts_service = UnavailableTTSService(str(e))
        return tts_service

def set_tts_service(service: Optional[Any]) -> None:
    global tts_service
    old_service = None
    with _tts_lock:
        old_service = tts_service
        tts_service = service
    if old_service is not None and old_service is not service:
        try:
            old_service.shutdown()
        except Exception:
            pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Optionally play startup greeting
    tts = get_tts_service()
    live = get_live_service()
    live_auto_start = live.settings.auto_start and live.settings.conversation_mode == "live"
    voice = None if live_auto_start else get_voice_service()
    if live_auto_start:
        try:
            live.start()
        except Exception as exc:
            logger.warning("[Freshy Core] Live voice auto-start skipped: %s", exc)
    try:
        if (not live_auto_start) and tts.settings.enabled and tts.settings.startup_greeting:
            provider = getattr(tts.settings, "provider", "system")
            language = getattr(tts.settings, "speech_language", "auto")
            if language == "hi-IN":
                greeting = "नमस्ते, फ्रेशी एआई ऑनलाइन है। मैं आपकी मदद के लिए तैयार हूँ।"
            elif language == "en-IN":
                greeting = "Freshy AI is online. I am ready to help you."
            else:
                greeting = "नमस्ते, Freshy AI online है। Main aapki madad ke liye taiyar hoon."
            # Text-only mode intentionally stays silent; the selected engine is
            # the only engine allowed to receive this greeting.
            if provider != "text_only":
                tts.speak(greeting)
    except Exception as e:
        logger.warning(f"[Freshy Core] Startup greeting skipped: {e}")
    yield
    # Stop streaming/live workers before standard voice/TTS workers.
    set_live_service(None)
    set_voice_service(None)
    set_tts_service(None)

app = FastAPI(
    title=config.APP_NAME,
    version=config.VERSION,
    description="Freshy AI Core - Lightweight FastAPI backend for Windows Desktop Assistant",
    lifespan=lifespan
)

# Enable CORS for Flutter desktop and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default-session"
    allow_web_search: Optional[bool] = True

class TTSSettingsUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    natural_voice: Optional[str] = None
    human_voice_profile: Optional[str] = None
    speech_language: Optional[str] = None
    voice_style: Optional[str] = None
    selected_voice: Optional[str] = None
    rate: Optional[int] = None
    volume: Optional[float] = None
    startup_greeting: Optional[bool] = None
    fast_start_enabled: Optional[bool] = None
    prepare_during_silence: Optional[bool] = None
    fast_chunk_characters: Optional[int] = None
    first_chunk_characters: Optional[int] = None
    stable_audio_enabled: Optional[bool] = None
    trim_boundary_silence: Optional[bool] = None
    failure_behavior: Optional[str] = None
    fallback_provider: Optional[str] = None

class TTSTestRequest(BaseModel):
    text: Optional[str] = "This is a Freshy AI offline voice test."

class VoiceSettingsUpdateRequest(BaseModel):
    device_index: Optional[int] = None
    recognition_engine: Optional[str] = None
    whisper_model: Optional[str] = None
    speech_language: Optional[str] = None
    vad_engine: Optional[str] = None
    wake_word_enabled: Optional[bool] = None
    continuous_listening: Optional[bool] = None
    hotkey_enabled: Optional[bool] = None
    interrupt_while_speaking: Optional[bool] = None
    interruption_sensitivity: Optional[str] = None
    adaptive_silence: Optional[bool] = None
    response_silence_seconds: Optional[float] = None
    partial_processing: Optional[bool] = None
    fast_response_preparation: Optional[bool] = None
    listening_timeout: Optional[float] = None
    muted: Optional[bool] = None
    noise_threshold: Optional[float] = None

class ChatResponse(BaseModel):
    # Old fields for backward compatibility with Flutter app
    success: bool
    reply: str
    intent_name: str
    confidence: float
    action_executed: bool
    freshy_status: str  # "idle" | "speaking"
    details: Dict[str, Any]

    # New Phase 4 fields
    provider: str
    model: Optional[str] = None
    used_web_search: bool = False
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    fallback_chain: List[Dict[str, Any]] = Field(default_factory=list)
    tool_used: Optional[str] = None
    tts_requested: bool = True
    error_code: Optional[str] = None
    user_safe_error: Optional[str] = None
    memory_used: bool = False
    memory_count: int = 0
    memory_pending: bool = False

@app.get("/health")
def health_check():
    """
    Health check endpoint for connection indicator in Flutter UI.
    """
    return {
        "status": "ok",
        "app": config.APP_NAME,
        "version": config.VERSION,
        "host": config.HOST,
        "port": config.PORT
    }

@app.get("/api/status")
def get_system_status():
    """
    Returns core backend state, active mode, and Gemini key availability.
    """
    gemini_active = bool(config.GEMINI_API_KEY and config.GEMINI_API_KEY != "MY_GEMINI_API_KEY")
    return {
        "status": "online",
        "mode": "Phase 5 - Persistent Memory, Personalization, and Stable Voice",
        "gemini_configured": gemini_active,
        "allowlisted_apps": list(CommandExecutor.ALLOWLISTED_APPS.keys()),
        "freshy_version": config.VERSION,
        "tts": get_tts_service().get_status(),
        "voice": get_voice_service().get_status()
    }

@app.get("/api/commands")
def list_commands():
    """
    Returns list of allowlisted commands supported by Freshy.
    """
    return {
        "commands": [
            {"phrase": "Hello Freshy", "intent": "WAKE_WORD", "description": "Starts offline command listening"},
            {"phrase": "Hi / Hey / Namaste", "intent": "GREETING", "description": "Greets Freshy assistant"},
            {"phrase": "What time is it / What is today's date?", "intent": "TIME_DATE", "description": "Returns current local time and date"},
            {"phrase": "Open Notepad", "intent": "OPEN_APP", "description": "Launches Windows Notepad"},
            {"phrase": "Open Calculator", "intent": "OPEN_APP", "description": "Launches Windows Calculator"},
            {"phrase": "Open website (e.g. Open Google / Open YouTube)", "intent": "OPEN_WEBSITE", "description": "Opens website URL in default browser"}
        ]
    }

@app.get("/api/tts/settings")
def get_tts_settings():
    """Returns current TTS configuration settings."""
    return get_tts_service().settings.model_dump()

@app.post("/api/tts/settings")
def update_tts_settings(request: TTSSettingsUpdateRequest):
    """Updates TTS settings and persists them to disk."""
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    try:
        updated = get_tts_service().update_settings(updates)
        return updated.model_dump()
    except (ValueError, ValidationError) as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=503, detail=str(re))

@app.get("/api/tts/voices")
def get_tts_voices():
    """Returns installed SAPI5 voices and built-in natural voice profiles."""
    try:
        try:
            from natural_tts_service import GeminiNaturalTTS
        except ImportError:
            from freshy_core.natural_tts_service import GeminiNaturalTTS
        service = get_tts_service()
        return {
            "voices": service.get_voices(),
            "natural_voices": GeminiNaturalTTS.voice_profiles(),
            "human_voices": service.get_human_voices(),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.get("/api/tts/status")
def get_tts_status():
    """Returns current speech status (is_speaking, queue_size, enabled)."""
    try:
        return get_tts_service().get_status()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.post("/api/tts/test")
def test_tts_voice(request: TTSTestRequest):
    """Enqueues a test phrase for speech output."""
    phrase = request.text if (request.text is not None and request.text.strip()) else ""
    try:
        result = get_tts_service().test_voice(phrase)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {
        "status": "ok" if result.get("accepted") else "rejected",
        "accepted": result.get("accepted", False),
        "reason": result.get("reason", ""),
        "text": phrase
    }

@app.post("/api/tts/stop")
def stop_tts():
    """Stops current speech playback immediately and clears the queue."""
    try:
        result = get_tts_service().stop_speaking()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    accepted = result.get("accepted", False)
    return {
        "status": "ok" if accepted else "error",
        "accepted": accepted,
        "reason": result.get("reason", "Speech playback stopped and queue cleared")
    }

@app.get("/api/voice/settings")
def get_voice_settings():
    """Returns current voice input configuration settings."""
    try:
        return get_voice_service().settings.to_dict()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@app.post("/api/voice/settings")
def update_voice_settings(request: VoiceSettingsUpdateRequest):
    """Updates voice input settings and persists them to disk."""
    # exclude_unset preserves an explicit JSON null for device_index, allowing
    # the Flutter "System Default Microphone" option to clear a saved device.
    updates = request.model_dump(exclude_unset=True)
    try:
        updated = get_voice_service().update_settings(updates)
        return updated.to_dict()
    except (ValueError, ValidationError) as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@app.get("/api/voice/devices")
def get_voice_devices():
    """Returns available audio input microphone devices."""
    try:
        return {"devices": get_voice_service().get_devices()}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@app.get("/api/voice/status")
def get_voice_status():
    """Return one truthful state composed from Live or standard voice workers."""
    live_status = get_live_service().status()
    if live_status.connected or live_status.connecting or live_status.conversation_mode == "live":
        mapped_state = live_status.state if live_status.state in {"idle", "listening", "thinking", "speaking"} else ("thinking" if live_status.connecting else "idle")
        return {
            "backend_available": True,
            "is_listening": live_status.microphone_active and not live_status.microphone_muted,
            "is_calibrating": False,
            "freshy_status": mapped_state,
            "partial_transcript": live_status.partial_input_transcript,
            "final_transcript": live_status.last_input_transcript,
            "assistant_reply": live_status.last_output_transcript,
            "input_level": live_status.input_level,
            "tts_is_speaking": live_status.output_playing,
            "tts_is_generating": live_status.connected and live_status.state == "thinking",
            "tts_queue_size": 0,
            "tts_active_backend": "gemini_live_native_audio",
            "recognition_engine_active": "gemini_live",
            "vad_engine": "gemini_live_aad+local_barge_in",
            "conversation_mode": "live",
            "live_connected": live_status.connected,
            "live_model": live_status.model,
            "live_voice": live_status.voice_name,
            "live_metrics": live_status.metrics,
            "result_id": live_status.result_id,
            "result_token": live_status.result_token,
            "intent": "LIVE_TOOL" if live_status.last_tool else "LIVE_CONVERSATION",
            "action_executed": live_status.last_action_executed,
            "tool_used": live_status.last_tool,
            "tool_success": live_status.last_tool_success,
            "error_status": live_status.last_error,
        }
    try:
        status = dict(get_voice_service().get_status())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        tts_status = get_tts_service().get_status()
    except Exception:
        tts_status = {"is_speaking": False, "queue_size": 0}

    audio_playing = bool(
        tts_status.get("is_audio_playing", tts_status.get("is_speaking", False))
    )
    audio_preparing = bool(tts_status.get("is_generating_audio")) or int(
        tts_status.get("queue_size", 0) or 0
    ) > 0
    if status.get("is_calibrating") or status.get("is_listening"):
        merged_state = "listening"
    elif audio_playing:
        merged_state = "speaking"
    elif status.get("freshy_status") == "thinking" or audio_preparing:
        merged_state = "thinking"
    else:
        merged_state = "idle"

    status["freshy_status"] = merged_state
    status["tts_is_speaking"] = audio_playing
    status["tts_is_generating"] = bool(tts_status.get("is_generating_audio"))
    status["tts_queue_size"] = int(tts_status.get("queue_size", 0) or 0)
    status["tts_active_backend"] = str(tts_status.get("active_backend", "none"))
    return status

@app.post("/api/voice/listen/start")
def start_voice_listening():
    """Triggers push-to-talk speech listening and interrupts active TTS."""
    res = get_voice_service().start_listening()
    if not res.get("accepted", False):
        raise HTTPException(status_code=503, detail=res.get("reason", "Listening failed to start"))
    return res

@app.post("/api/voice/listen/stop")
def stop_voice_listening():
    """Stops active voice listening."""
    result = get_voice_service().stop_listening()
    if not result.get("accepted", False):
        raise HTTPException(
            status_code=503,
            detail=result.get("reason", "Voice service is unavailable"),
        )
    return result

@app.post("/api/voice/calibrate")
def calibrate_voice_noise():
    """Run worker-owned calibration and return the completed threshold."""
    res = get_voice_service().calibrate_noise()
    if not res.get("success", False):
        reason = res.get("reason", "Calibration failed")
        status_code = 409 if "already" in reason.lower() else 503
        raise HTTPException(status_code=status_code, detail=reason)
    return res

def _assistant_response_to_chat_response(
    ai_res: AssistantResponse, prepared_audio_token: Optional[str] = None
) -> ChatResponse:
    """Enqueue TTS once and map the common assistant response to the API contract."""
    tts_res = {"accepted": False, "reason": "No response text"}
    spoken_text = str(ai_res.speech_text or ai_res.reply or "").strip()
    if ai_res.tts_requested and spoken_text:
        try:
            tts = get_tts_service()
            try:
                tts_res = tts.speak(spoken_text, prepared_audio_token)
            except TypeError:
                tts_res = tts.speak(spoken_text)
        except Exception as exc:
            logger.warning("[Freshy Core] Speech enqueue failed: %s", exc)
            tts_res = {"accepted": False, "reason": f"TTS unavailable: {exc}"}
    freshy_status = "speaking" if tts_res.get("accepted", False) else "idle"
    return ChatResponse(
        success=ai_res.success,
        reply=ai_res.reply,
        intent_name=ai_res.intent.upper(),
        confidence=1.0 if ai_res.success else 0.0,
        action_executed=ai_res.action_executed,
        freshy_status=freshy_status,
        details={
            "action": ai_res.action,
            "provider": ai_res.provider,
            "model": ai_res.model,
            "used_web_search": ai_res.used_web_search,
            "sources": ai_res.sources,
            "fallback_chain": ai_res.fallback_chain,
            "tool_used": ai_res.tool_used,
            "memory_used": ai_res.memory_used,
            "memory_count": ai_res.memory_count,
            "memory_pending": ai_res.memory_pending,
        },
        provider=ai_res.provider,
        model=ai_res.model,
        used_web_search=ai_res.used_web_search,
        sources=ai_res.sources,
        fallback_chain=ai_res.fallback_chain,
        tool_used=ai_res.tool_used,
        tts_requested=ai_res.tts_requested,
        error_code=ai_res.error_code,
        user_safe_error=ai_res.user_safe_error,
        memory_used=ai_res.memory_used,
        memory_count=ai_res.memory_count,
        memory_pending=ai_res.memory_pending,
    )


@app.post("/api/chat", response_model=ChatResponse)
def handle_chat(request: ChatRequest):
    """
    Processes incoming text from Flutter UI, routes via AssistantOrchestrator, and speaks response.
    """
    user_msg = request.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Process request using AssistantOrchestrator
    ai_request = AIChatRequest(
        message=user_msg,
        session_id=request.session_id or "default-session",
        allow_web_search=True if request.allow_web_search is None else request.allow_web_search,
    )
    ai_res = orchestrator.handle_request(ai_request)

    return _assistant_response_to_chat_response(ai_res)

@app.get("/api/ai/status")
def get_ai_status():
    status = orchestrator.provider_router.status()
    status.update({
        "tavily_search_configured": orchestrator.search_service.is_configured(),
        "web_search_enabled": orchestrator.web_search_enabled,
        "memory": orchestrator.memory_service.status().model_dump(),
        "live_voice": get_live_service().status().model_dump(),
    })
    return status


@app.get("/api/live/settings")
def get_live_settings():
    return get_live_service().settings.model_dump()


@app.post("/api/live/settings")
def update_live_settings(request: LiveSettings):
    try:
        return get_live_service().update_settings(request.model_dump()).model_dump()
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/live/status")
def get_live_status():
    return get_live_service().status().model_dump()


@app.get("/api/live/diagnostics")
def get_live_diagnostics():
    status = get_live_service().status()
    return {
        "state": status.state,
        "connected": status.connected,
        "configured": status.configured,
        "model": status.model,
        "voice_name": status.voice_name,
        "metrics": status.metrics,
        "last_error": status.last_error,
    }


@app.post("/api/live/session/start")
def start_live_session():
    service = get_live_service()
    if service.settings.conversation_mode != "live":
        service.update_settings({"conversation_mode": "live"})
    if not service.settings.enabled:
        raise HTTPException(status_code=503, detail="Live voice is disabled.")
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured.")
    try:
        get_voice_service().stop_listening()
    except Exception:
        pass
    # The standard STT service keeps a PortAudio input stream open. Shut it
    # down before Live mode opens its continuous microphone stream.
    set_voice_service(None)
    try:
        get_tts_service().stop_speaking()
    except Exception:
        pass
    result = service.start()
    if not result.get("accepted", False):
        raise HTTPException(status_code=503, detail=result.get("reason", "Live session could not start."))
    return result


@app.post("/api/live/session/stop")
def stop_live_session():
    return get_live_service().stop()


class LiveMuteRequest(BaseModel):
    muted: bool = True


@app.post("/api/live/mute")
def mute_live_session(request: LiveMuteRequest):
    return get_live_service().set_muted(request.muted)


class LiveTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)


@app.post("/api/live/text")
def send_live_text(request: LiveTextRequest):
    result = get_live_service().send_text(request.text)
    if not result.get("accepted", False):
        raise HTTPException(status_code=409, detail=result.get("reason", "Live session is unavailable."))
    return result


@app.post("/api/live/interrupt")
def interrupt_live_session():
    return get_live_service().interrupt()


@app.get("/api/memory/status")
def get_memory_status():
    return orchestrator.memory_service.status().model_dump()


@app.get("/api/memory/settings")
def get_memory_settings():
    return orchestrator.memory_service.settings.model_dump()


@app.post("/api/memory/settings")
def update_memory_settings(request: MemorySettingsUpdateRequest):
    updates = request.model_dump(exclude_unset=True)
    try:
        settings = orchestrator.memory_service.update_settings(updates)
        # Conversation persistence changes apply to new orchestrator sessions.
        orchestrator.conversation_store.persistence = (
            orchestrator.memory_service.store if settings.persist_conversations else None
        )
        return settings.model_dump()
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/memory", response_model=MemoryListResponse)
def list_memories(
    query: str = "",
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    if category not in {None, "profile", "preference", "project", "note"}:
        raise HTTPException(status_code=400, detail="Invalid memory category.")
    items, total = orchestrator.memory_service.store.list_memories(
        query=query, category=category, limit=limit, offset=offset
    )
    return MemoryListResponse(items=items, total=total)


@app.post("/api/memory")
def create_memory(request: MemoryCreateRequest):
    candidate = MemoryCandidate(
        category=request.category,
        key=request.key,
        value=request.value,
        tags=request.tags,
        importance=request.importance,
        source="memory_center",
    )
    decision = inspect_memory_text(f"{candidate.key}\n{candidate.value}")
    if not decision.safe:
        raise HTTPException(status_code=400, detail=decision.reason)
    if len(candidate.value) > orchestrator.memory_service.settings.max_item_characters:
        raise HTTPException(status_code=400, detail="Memory is too long.")
    item, created = orchestrator.memory_service.store.add_memory(
        candidate, pinned=request.pinned
    )
    return {"item": item.model_dump(), "created": created}


@app.put("/api/memory/{memory_id}")
def update_memory(memory_id: str, request: MemoryUpdateRequest):
    updates = request.model_dump(exclude_unset=True)
    text = "\n".join(str(updates.get(key, "")) for key in ("key", "value"))
    if text.strip():
        decision = inspect_memory_text(text)
        if not decision.safe:
            raise HTTPException(status_code=400, detail=decision.reason)
    try:
        item = orchestrator.memory_service.store.update_memory(memory_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if item is None:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return item.model_dump()


@app.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: str):
    if not orchestrator.memory_service.store.delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"status": "ok", "deleted": True, "memory_id": memory_id}


@app.post("/api/memory/{memory_id}/pin")
def pin_memory(memory_id: str, pinned: bool = True):
    item = orchestrator.memory_service.store.set_pinned(memory_id, pinned)
    if item is None:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return item.model_dump()


@app.post("/api/memory/clear")
def clear_all_memories(request: MemoryClearRequest):
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required.")
    count = orchestrator.memory_service.store.clear_memories()
    return {"status": "ok", "deleted_count": count}


@app.post("/api/memory/conversations/clear")
def clear_all_memory_conversations(request: MemoryClearRequest):
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required.")
    sessions, messages = orchestrator.memory_service.store.clear_all_conversations()
    orchestrator.conversation_store.clear_all()
    return {
        "status": "ok",
        "deleted_sessions": sessions,
        "deleted_messages": messages,
    }


@app.get("/api/memory/export")
def export_memories():
    return orchestrator.memory_service.store.export_memories()


@app.post("/api/memory/import")
def import_memories(request: MemoryImportRequest):
    if request.replace_existing:
        orchestrator.memory_service.store.clear_memories()
    imported = 0
    skipped = 0
    for item in request.items:
        candidate = MemoryCandidate(
            category=item.category,
            key=item.key,
            value=item.value,
            tags=item.tags,
            importance=item.importance,
            source="import",
        )
        decision = inspect_memory_text(f"{candidate.key}\n{candidate.value}")
        if not decision.safe:
            skipped += 1
            continue
        _, created = orchestrator.memory_service.store.add_memory(
            candidate, pinned=item.pinned
        )
        imported += int(created)
        skipped += int(not created)
    return {"status": "ok", "imported": imported, "skipped": skipped}


@app.get("/api/memory/audit")
def memory_audit(limit: int = 100):
    return {
        "items": [item.model_dump() for item in orchestrator.memory_service.store.audit_entries(limit)]
    }


class ClearConversationRequest(BaseModel):
    session_id: str = "default-session"


@app.post("/api/conversation/clear")
def clear_conversation(
    request: Optional[ClearConversationRequest] = None,
    session_id: Optional[str] = None,
):
    resolved_session = (
        session_id
        or (request.session_id if request is not None else None)
        or "default-session"
    )
    orchestrator.conversation_store.clear_session(resolved_session)
    return {
        "status": "ok",
        "session_id": resolved_session,
        "message": "Conversation history has been cleared.",
    }

if __name__ == "__main__":
    import uvicorn

    print(f"Starting {config.APP_NAME} on http://{config.HOST}:{config.PORT}...")
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)
