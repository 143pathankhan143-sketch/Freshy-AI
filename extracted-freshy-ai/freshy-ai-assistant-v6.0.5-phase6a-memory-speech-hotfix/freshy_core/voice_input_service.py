from __future__ import annotations

import collections
import inspect
import json
import logging
import os
import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional

try:
    from voice_activity import AdaptiveVoiceActivityDetector, pcm16_rms
    from whisper_service import WhisperTranscriber
except ImportError:
    from freshy_core.voice_activity import AdaptiveVoiceActivityDetector, pcm16_rms
    from freshy_core.whisper_service import WhisperTranscriber

logger = logging.getLogger("FreshyVoiceInput")

try:
    from config import config as _freshy_config
except Exception:
    _freshy_config = None

SAMPLE_RATE = 16_000
CHUNK_MILLISECONDS = 100
PRE_ROLL_CHUNKS = 10
WAKE_WORD = "hello freshy"
WAKE_FIRST_WORDS = {"hello", "hallo", "helo"}
WAKE_SECOND_WORDS = {
    "freshy",
    "fresh",
    "freshly",
    "freshee",
    "frashi",
    "freddy",
    "crashy",
    "crazy",
}


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default


def _choice(value: Any, default: str, allowed: set[str]) -> str:
    normalized = str(value or default).strip().lower()
    return normalized if normalized in allowed else default


@dataclass
class VoiceSettings:
    """Persistent Phase 4.2 hybrid speech-input settings."""

    device_index: Optional[int] = None
    recognition_engine: str = "auto"
    whisper_model: str = "base"
    speech_language: str = "auto"
    vad_engine: str = "auto"
    wake_word_enabled: bool = True
    continuous_listening: bool = False
    hotkey_enabled: bool = True
    interrupt_while_speaking: bool = True
    interruption_sensitivity: str = "normal"
    adaptive_silence: bool = True
    response_silence_seconds: float = 3.0
    partial_processing: bool = True
    fast_response_preparation: bool = True
    listening_timeout: float = 12.0
    muted: bool = False
    noise_threshold: float = 0.02

    def __post_init__(self) -> None:
        if isinstance(self.device_index, bool) or (
            self.device_index is not None and not isinstance(self.device_index, int)
        ):
            self.device_index = None
        self.recognition_engine = _choice(
            self.recognition_engine, "auto", {"auto", "vosk", "whisper"}
        )
        self.whisper_model = _choice(
            self.whisper_model, "base", {"tiny", "base", "small"}
        )
        raw_language = str(self.speech_language or "auto").strip()
        self.speech_language = (
            raw_language if raw_language in {"auto", "hi-IN", "en-IN"} else "auto"
        )
        self.vad_engine = _choice(
            self.vad_engine, "auto", {"auto", "webrtc", "adaptive_rms"}
        )
        self.interruption_sensitivity = _choice(
            self.interruption_sensitivity, "normal", {"low", "normal", "high"}
        )
        self.listening_timeout = max(3.0, min(30.0, float(self.listening_timeout)))
        self.response_silence_seconds = max(
            1.0, min(5.0, float(self.response_silence_seconds))
        )
        self.noise_threshold = max(0.001, min(0.5, float(self.noise_threshold)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_index": self.device_index,
            "recognition_engine": self.recognition_engine,
            "whisper_model": self.whisper_model,
            "speech_language": self.speech_language,
            "vad_engine": self.vad_engine,
            "wake_word_enabled": self.wake_word_enabled,
            "continuous_listening": self.continuous_listening,
            "hotkey_enabled": self.hotkey_enabled,
            "interrupt_while_speaking": self.interrupt_while_speaking,
            "interruption_sensitivity": self.interruption_sensitivity,
            "adaptive_silence": self.adaptive_silence,
            "response_silence_seconds": self.response_silence_seconds,
            "partial_processing": self.partial_processing,
            "fast_response_preparation": self.fast_response_preparation,
            "listening_timeout": self.listening_timeout,
            "muted": self.muted,
            "noise_threshold": self.noise_threshold,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceSettings":
        raw_device = data.get("device_index", data.get("selected_device"))
        device_index = (
            raw_device
            if isinstance(raw_device, int) and not isinstance(raw_device, bool)
            else None
        )
        return cls(
            device_index=device_index,
            recognition_engine=data.get("recognition_engine", "auto"),
            whisper_model=data.get("whisper_model", "base"),
            speech_language=data.get("speech_language", "auto"),
            vad_engine=data.get("vad_engine", "auto"),
            wake_word_enabled=_as_bool(data.get("wake_word_enabled"), True),
            continuous_listening=_as_bool(data.get("continuous_listening"), False),
            hotkey_enabled=_as_bool(data.get("hotkey_enabled"), True),
            interrupt_while_speaking=_as_bool(
                data.get("interrupt_while_speaking"), True
            ),
            interruption_sensitivity=data.get("interruption_sensitivity", "normal"),
            adaptive_silence=_as_bool(data.get("adaptive_silence"), True),
            response_silence_seconds=data.get("response_silence_seconds", 3.0),
            partial_processing=_as_bool(data.get("partial_processing"), True),
            fast_response_preparation=_as_bool(
                data.get("fast_response_preparation"), True
            ),
            listening_timeout=data.get("listening_timeout", 12.0),
            muted=_as_bool(data.get("muted"), False),
            noise_threshold=data.get("noise_threshold", 0.02),
        )

    def updated(self, updates: Dict[str, Any]) -> "VoiceSettings":
        values = self.to_dict()
        for key, value in updates.items():
            if key == "selected_device":
                key = "device_index"
            if key not in values:
                continue
            if key == "device_index":
                if value is None:
                    values[key] = None
                elif isinstance(value, int) and not isinstance(value, bool):
                    values[key] = value
                else:
                    raise ValueError("device_index must be an integer or null")
            else:
                values[key] = value
        return VoiceSettings.from_dict(values)


def compute_pcm_rms(pcm_bytes: bytes) -> float:
    return pcm16_rms(pcm_bytes)


def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Keep Devanagari/Urdu letters for transcript comparison while still
    # normalizing punctuation and Latin wake words.
    cleaned = re.sub(r"[^\w\s\u0900-\u097F\u0600-\u06FF]", " ", str(text).casefold())
    return " ".join(cleaned.split())


def split_wake_phrase(text: str) -> Optional[str]:
    tokens = normalize_text(text).split()
    if len(tokens) < 2:
        return None
    first, second = tokens[0], tokens[1]
    first_matches = first in WAKE_FIRST_WORDS or (
        SequenceMatcher(None, first, "hello").ratio() >= 0.8
    )
    second_matches = second in WAKE_SECOND_WORDS or (
        SequenceMatcher(None, second, "freshy").ratio() >= 0.66
    )
    if not (first_matches and second_matches):
        return None
    return " ".join(tokens[2:])


class VoiceInputService:
    """
    Hybrid Vosk/Whisper speech pipeline with VAD, true barge-in, pre-roll,
    adaptive endpointing and one-token-safe speculative response preparation.

    PortAudio callbacks only enqueue PCM. Recognition, settings, state changes,
    action dispatch and cancellation stay outside the callback thread.
    """

    def __init__(
        self,
        settings_file: Optional[str] = None,
        model_dir: Optional[str] = None,
        whisper_model_name: Optional[str] = None,
        chat_callback: Optional[Callable[..., Any]] = None,
        prepare_callback: Optional[Callable[..., Any]] = None,
        tts_stop_callback: Optional[Callable[[], Any]] = None,
        tts_status_callback: Optional[Callable[[], Dict[str, Any]]] = None,
        vosk_module: Optional[Any] = None,
        whisper_module: Optional[Any] = None,
        sounddevice_module: Optional[Any] = None,
        pynput_module: Optional[Any] = None,
        webrtcvad_module: Optional[Any] = None,
        auto_start_worker: bool = True,
    ) -> None:
        core_dir = os.path.dirname(os.path.abspath(__file__))
        self.settings_file = settings_file or os.path.join(core_dir, "voice_settings.json")
        self.chat_callback = chat_callback
        self.prepare_callback = prepare_callback
        self.tts_stop_callback = tts_stop_callback
        self.tts_status_callback = tts_status_callback

        self._lock = threading.RLock()
        self._cmd_queue: queue.Queue = queue.Queue()
        self._audio_queue: queue.Queue = queue.Queue(maxsize=96)
        self._whisper_queue: queue.Queue = queue.Queue(maxsize=4)
        self._worker_ready = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._whisper_thread: Optional[threading.Thread] = None

        self._vosk = vosk_module
        self._sounddevice = sounddevice_module
        self._pynput = pynput_module
        self._vosk_model: Optional[Any] = None
        self._recognizer: Optional[Any] = None
        self._mic_stream: Optional[Any] = None
        self._stream_device_index: Optional[int] = None
        self._hotkey_listener: Optional[Any] = None

        self.settings = self._load_settings()
        if whisper_model_name:
            self.settings = self.settings.updated({"whisper_model": whisper_model_name})
        self.resolved_model_dir = self._resolve_model_dir(core_dir, model_dir)
        self._whisper = WhisperTranscriber(
            model_name=self.settings.whisper_model,
            module=whisper_module,
        )
        self._vad = AdaptiveVoiceActivityDetector(
            SAMPLE_RATE,
            sensitivity=self.settings.interruption_sensitivity,
            webrtcvad_module=webrtcvad_module,
            preferred_engine=self.settings.vad_engine,
        )

        self._running = False
        self._accepting_requests = False
        self._shutdown_state = "not_started"
        self._model_initializing = False
        self._vosk_model_loaded = False
        self._whisper_dependency_available = False
        self._whisper_load_failed = False
        self._mic_available = False
        self._error_status = ""

        self._is_listening = False
        self._listen_request_pending = False
        self._is_calibrating = False
        self._voice_mode = "idle"
        self._freshy_status = "idle"
        self._session_id = ""
        self._session_started_at = 0.0
        self._last_voice_activity = 0.0
        self._speech_started_at = 0.0
        self._resume_continuous_after_tts = False
        self._tts_was_busy = False
        self._tts_started_at = 0.0
        self._tts_echo_rms = 0.0
        self._barge_in_candidate_started = 0.0

        self._input_level = 0.0
        self._vad_score = 0.0
        self._vad_engine_active = self._vad.engine_name
        self._pre_roll: collections.deque[bytes] = collections.deque(maxlen=PRE_ROLL_CHUNKS)
        self._vosk_final_parts: List[str] = []
        self._whisper_audio: List[bytes] = []
        self._whisper_generation = 0
        self._last_whisper_partial_at = 0.0

        self._result_id = 0
        self._result_token = ""
        self._partial_transcript = ""
        self._final_transcript = ""
        self._assistant_reply = ""
        self._intent_name = ""
        self._action_executed = False
        self._command_success = False
        self._action_result: Dict[str, Any] = {}

        self._calibration_id = 0
        self._calibration_result: Dict[str, Any] = {}

        self._last_processed_text = ""
        self._last_processed_time = 0.0
        self._cooldown_seconds = 1.2

        self._partial_changed_at = 0.0
        self._speculation_started = False
        self._preparing_response = False
        self._prepared_transcript = ""
        self._prepared_result: Optional[Dict[str, Any]] = None
        self._prepare_generation = 0

        self._import_optional_dependencies()
        if auto_start_worker:
            self._start_worker()

    @staticmethod
    def _resolve_model_dir(core_dir: str, requested_dir: Optional[str]) -> Optional[str]:
        candidates = [
            requested_dir,
            os.path.join(core_dir, "models", "vosk-model-small-en-in-0.4"),
            os.path.join(core_dir, "models", "vosk-model"),
        ]
        for candidate in candidates:
            if candidate and os.path.isdir(candidate):
                return os.path.abspath(candidate)
        return None

    def _import_optional_dependencies(self) -> None:
        errors: List[str] = []
        if self._vosk is None:
            try:
                import vosk  # type: ignore

                self._vosk = vosk
                vosk.SetLogLevel(-1)
            except Exception as exc:
                errors.append(f"Vosk unavailable: {exc}")
        if self._sounddevice is None:
            try:
                import sounddevice  # type: ignore

                self._sounddevice = sounddevice
            except Exception as exc:
                errors.append(f"SoundDevice unavailable: {exc}")
        if self._pynput is None:
            try:
                import pynput  # type: ignore

                self._pynput = pynput
            except Exception as exc:
                logger.warning("[Freshy Voice] Global hotkey unavailable: %s", exc)
        if errors:
            self._error_status = "; ".join(errors)

    def _load_settings(self) -> VoiceSettings:
        try:
            with open(self.settings_file, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            if isinstance(value, dict):
                return VoiceSettings.from_dict(value)
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.warning("[Freshy Voice] Settings load failed: %s", exc)
        settings = VoiceSettings(
            recognition_engine=getattr(_freshy_config, "VOICE_RECOGNITION_ENGINE", "auto"),
            whisper_model=getattr(_freshy_config, "WHISPER_MODEL", "base"),
            response_silence_seconds=getattr(
                _freshy_config, "VOICE_RESPONSE_SILENCE_SECONDS", 3.0
            ),
        )
        try:
            self._save_settings(settings)
        except Exception:
            pass
        return settings

    def _save_settings(self, settings: VoiceSettings) -> None:
        directory = os.path.dirname(self.settings_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        temp_path = f"{self.settings_file}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(settings.to_dict(), handle, indent=2)
            os.replace(temp_path, self.settings_file)
        except Exception as exc:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise RuntimeError(f"Could not save voice settings: {exc}") from exc

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._error_status = str(message)[:500]

    def _clear_audio_queue(self) -> None:
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                return

    def _clear_whisper_queue(self) -> None:
        while True:
            try:
                self._whisper_queue.get_nowait()
            except queue.Empty:
                return

    def _start_worker(self) -> None:
        with self._lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return
            if self._shutdown_state in {"shutting_down", "shut_down"}:
                raise RuntimeError("Voice service has already been shut down")
            self._running = True
            self._accepting_requests = True
            self._shutdown_state = "starting"
            self._worker_thread = threading.Thread(
                target=self._worker_entry,
                daemon=True,
                name="FreshyVoiceWorker",
            )
            self._whisper_thread = threading.Thread(
                target=self._whisper_worker_entry,
                daemon=True,
                name="FreshyWhisperWorker",
            )
            self._whisper_thread.start()
            self._worker_thread.start()

    def _worker_entry(self) -> None:
        unexpected_error = ""
        try:
            self._worker_loop()
        except Exception as exc:
            unexpected_error = f"Voice worker terminated unexpectedly: {exc}"
            logger.exception("[Freshy Voice] %s", unexpected_error)
        finally:
            self._close_stream()
            self._stop_hotkey_listener()
            with self._lock:
                self._running = False
                self._accepting_requests = False
                self._is_listening = False
                self._listen_request_pending = False
                self._is_calibrating = False
                self._freshy_status = "idle"
                self._voice_mode = "disabled"
                if unexpected_error:
                    self._error_status = unexpected_error
                    self._shutdown_state = "failed"
                elif self._shutdown_state != "shutdown_timeout":
                    self._shutdown_state = "shut_down"
            self._worker_ready.set()

    def _worker_loop(self) -> None:
        logger.info("[Freshy Voice] Phase 4.2 hybrid audio worker starting")
        self._initialize_models_worker()
        self._refresh_devices_worker()
        self._open_stream_worker()
        self._apply_hotkey_setting_worker()
        with self._lock:
            if self._shutdown_state == "starting":
                self._shutdown_state = "active"
        self._worker_ready.set()

        while True:
            with self._lock:
                if not self._running:
                    break
            self._process_control_commands_worker(limit=16)
            self._sync_tts_state_worker()
            self._update_session_timeout_worker()
            self._maybe_start_fast_preparation_worker()
            self._maybe_resume_continuous_worker()
            try:
                pcm_chunk = self._audio_queue.get(timeout=0.04)
            except queue.Empty:
                continue
            self._process_audio_worker(pcm_chunk)

    def _whisper_worker_entry(self) -> None:
        while True:
            try:
                item = self._whisper_queue.get(timeout=0.1)
            except queue.Empty:
                with self._lock:
                    if not self._running and self._shutdown_state != "starting":
                        return
                continue
            action = item.get("action")
            if action == "SHUTDOWN":
                return
            if action == "WARMUP":
                loaded = self._whisper.load()
                with self._lock:
                    self._whisper_load_failed = not loaded
                    requested = self.settings.recognition_engine
                if not loaded:
                    error = self._whisper.initialization_error or "Whisper model is unavailable"
                    if requested == "auto" and self._vosk_model_loaded:
                        self._set_error(
                            f"Whisper unavailable; Auto mode is using Vosk fallback: {error}"
                        )
                    else:
                        self._set_error(f"Whisper model could not load: {error}")
                continue
            generation = int(item.get("generation", 0) or 0)
            final = bool(item.get("final"))
            pcm = item.get("pcm") or b""
            try:
                text = self._whisper.transcribe_pcm(
                    pcm,
                    sample_rate=SAMPLE_RATE,
                    language=item.get("language", "auto"),
                    beam_size=2 if final else 1,
                )
                with self._lock:
                    self._whisper_load_failed = False
            except Exception as exc:
                with self._lock:
                    if not self._whisper.model_loaded:
                        self._whisper_load_failed = True
                    auto_fallback = (
                        final
                        and self.settings.recognition_engine == "auto"
                        and self._vosk_model_loaded
                    )
                self._set_error(f"Whisper transcription failed: {exc}")
                text = self._transcribe_pcm_with_vosk(pcm) if auto_fallback else ""
            with self._lock:
                current = generation == self._whisper_generation
                running = self._running
            if not current or not running:
                continue
            if final:
                if text:
                    self._accept_final_transcript(text)
                else:
                    self._finish_empty_transcription()
            elif text:
                self._update_partial_text(text)

    def _initialize_models_worker(self) -> None:
        with self._lock:
            self._model_initializing = True
        try:
            if self._vosk is not None and self.resolved_model_dir:
                try:
                    self._vosk_model = self._vosk.Model(self.resolved_model_dir)
                    self._vosk_model_loaded = True
                except Exception as exc:
                    self._set_error(f"Vosk model initialization failed: {exc}")
            self._whisper_dependency_available = self._whisper.dependency_available()
            self._reset_recognizer_worker(wake_only=True)
            self._queue_whisper_warmup_worker()
        finally:
            with self._lock:
                self._model_initializing = False

    def _queue_whisper_warmup_worker(self) -> None:
        with self._lock:
            should_warm = (
                self._whisper_dependency_available
                and self.settings.recognition_engine in {"auto", "whisper"}
                and not self._whisper.model_loaded
                and not self._whisper.loading
                and not self._whisper_load_failed
            )
        if not should_warm:
            return
        try:
            self._whisper_queue.put_nowait({"action": "WARMUP"})
        except queue.Full:
            pass

    def _transcribe_pcm_with_vosk(self, pcm: bytes) -> str:
        """Best-effort final transcription when Auto mode loses Whisper."""
        if not pcm or not self._vosk_model_loaded:
            return ""
        try:
            recognizer = self._new_vosk_recognizer(wake_only=False)
            if recognizer is None:
                return ""
            if recognizer.AcceptWaveform(pcm):
                result = json.loads(recognizer.Result() or "{}")
                text = str(result.get("text", "") or "").strip()
                if text:
                    return text
            final = json.loads(recognizer.FinalResult() or "{}")
            return str(final.get("text", "") or "").strip()
        except Exception as exc:
            self._set_error(f"Vosk fallback transcription failed: {exc}")
            return ""

    def _new_vosk_recognizer(self, wake_only: bool = False) -> Optional[Any]:
        if self._vosk is None or self._vosk_model is None:
            return None
        if wake_only:
            grammar = json.dumps(
                [
                    "hello freshy",
                    "hello fresh",
                    "hello freshly",
                    "hello frashi",
                    "hello freddy",
                    "hello crashy",
                    "hello crazy",
                    "[unk]",
                ]
            )
            try:
                return self._vosk.KaldiRecognizer(self._vosk_model, SAMPLE_RATE, grammar)
            except TypeError:
                pass
        return self._vosk.KaldiRecognizer(self._vosk_model, SAMPLE_RATE)

    def _resolved_engine(self) -> str:
        requested = self.settings.recognition_engine
        whisper_can_run = (
            self._whisper_dependency_available and not self._whisper_load_failed
        )
        if requested == "vosk":
            return "vosk" if self._vosk_model_loaded else "unavailable"
        if requested == "whisper":
            return "whisper" if whisper_can_run else "unavailable"
        # Auto stays immediately usable with Vosk while the heavier Whisper
        # model warms in the background, then switches when it is ready.
        if self._whisper.model_loaded:
            return "whisper"
        if self._vosk_model_loaded:
            return "vosk"
        if whisper_can_run:
            return "whisper"
        return "unavailable"

    def _reset_recognizer_worker(self, wake_only: bool) -> None:
        engine = self._resolved_engine()
        # Vosk remains a lightweight wake-word detector even when Whisper is
        # selected. Command recognition itself still follows the selected engine.
        if wake_only and self._vosk_model_loaded:
            self._recognizer = self._new_vosk_recognizer(wake_only=True)
        elif engine == "vosk":
            self._recognizer = self._new_vosk_recognizer(wake_only=False)
        else:
            self._recognizer = None

    @staticmethod
    def _device_to_dict(device: Any) -> Dict[str, Any]:
        if isinstance(device, dict):
            return dict(device)
        try:
            return dict(device)
        except Exception:
            return {}

    def get_devices(self) -> List[Dict[str, Any]]:
        if self._sounddevice is None:
            return []
        try:
            raw_devices = self._sounddevice.query_devices()
            try:
                default_value = self._sounddevice.default.device
                default_input = (
                    default_value[0]
                    if isinstance(default_value, (list, tuple))
                    else int(default_value)
                )
            except Exception:
                default_input = None
            devices: List[Dict[str, Any]] = []
            for index, raw_device in enumerate(raw_devices):
                device = self._device_to_dict(raw_device)
                channels = int(device.get("max_input_channels", 0) or 0)
                if channels <= 0:
                    continue
                devices.append(
                    {
                        "id": index,
                        "name": str(device.get("name", f"Microphone {index}")),
                        "channels": channels,
                        "sample_rate": int(
                            float(device.get("default_samplerate", SAMPLE_RATE))
                        ),
                        "is_default": index == default_input,
                    }
                )
            return devices
        except Exception as exc:
            self._set_error(f"Microphone query failed: {exc}")
            return []

    def _refresh_devices_worker(self) -> None:
        devices = self.get_devices()
        valid_ids = {device["id"] for device in devices}
        with self._lock:
            self._mic_available = bool(devices)
            selected = self.settings.device_index
        if selected is not None and selected not in valid_ids:
            with self._lock:
                self.settings = self.settings.updated({"device_index": None})
                repaired = self.settings
            try:
                self._save_settings(repaired)
            except RuntimeError:
                pass
        if not devices:
            self._set_error("No microphone input device was detected")

    def _open_stream_worker(self) -> None:
        self._close_stream()
        with self._lock:
            can_open = (
                self._sounddevice is not None
                and self._resolved_engine() != "unavailable"
                and self._mic_available
                and self._running
            )
            selected_device = self.settings.device_index
        if not can_open:
            return
        try:
            stream = self._sounddevice.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=1600,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
                device=selected_device,
                latency="low",
            )
            stream.start()
            self._mic_stream = stream
            self._stream_device_index = selected_device
        except Exception as exc:
            with self._lock:
                self._mic_available = False
            self._set_error(f"Microphone stream failed to open: {exc}")

    def _close_stream(self) -> None:
        stream = self._mic_stream
        self._mic_stream = None
        self._stream_device_index = None
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

    def _audio_callback(self, indata: Any, frames: int, time_info: Any, status: Any) -> None:
        del frames, time_info
        if status:
            logger.debug("[Freshy Voice] PortAudio status: %s", status)
        with self._lock:
            accept_audio = self._running and not self.settings.muted and self._mic_available
        if not accept_audio:
            return
        try:
            data = bytes(indata)
            self._audio_queue.put_nowait(data)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.put_nowait(data)
            except queue.Empty:
                pass
            except queue.Full:
                pass
        except Exception:
            pass

    def _process_control_commands_worker(self, limit: int) -> None:
        for _ in range(limit):
            try:
                command, payload = self._cmd_queue.get_nowait()
            except queue.Empty:
                return
            if command == "SHUTDOWN":
                with self._lock:
                    self._running = False
                self._whisper_queue.put({"action": "SHUTDOWN"})
                return
            if command == "START_LISTEN":
                self._begin_listening_worker(
                    payload.get("session_id", ""), payload.get("origin", "api")
                )
            elif command == "STOP_LISTEN":
                self._cancel_listening_worker()
            elif command == "APPLY_SETTINGS":
                self._apply_settings_worker(payload)
            elif command == "CALIBRATE":
                self._calibrate_worker(payload)

    def _reset_utterance_state(self) -> None:
        self._vosk_final_parts = []
        self._whisper_audio = []
        self._speech_started_at = 0.0
        self._partial_transcript = ""
        self._partial_changed_at = time.monotonic()
        self._speculation_started = False
        self._preparing_response = False
        self._prepared_transcript = ""
        self._prepared_result = None
        self._prepare_generation += 1
        self._whisper_generation += 1
        self._clear_whisper_queue()

    def _begin_listening_worker(self, session_id: str, origin: str) -> None:
        with self._lock:
            self._listen_request_pending = False
            if (
                not self._running
                or self.settings.muted
                or self._resolved_engine() == "unavailable"
                or not self._mic_available
            ):
                return
        self._clear_audio_queue()
        self._reset_utterance_state()
        self._reset_recognizer_worker(wake_only=False)
        now = time.monotonic()
        with self._lock:
            self._is_listening = True
            self._session_id = session_id or uuid.uuid4().hex
            self._session_started_at = now
            self._last_voice_activity = now
            self._freshy_status = "listening"
            self._voice_mode = "continuous" if origin == "continuous" else "push_to_talk"
            self._resume_continuous_after_tts = False

    def _cancel_listening_worker(self) -> None:
        self._clear_audio_queue()
        self._reset_utterance_state()
        self._reset_recognizer_worker(wake_only=True)
        with self._lock:
            self._is_listening = False
            self._listen_request_pending = False
            self._freshy_status = "idle"
            self._voice_mode = "wake" if self.settings.wake_word_enabled else "idle"

    def _apply_settings_worker(self, payload: Dict[str, Any]) -> None:
        old_device = payload.get("old_device")
        new_device = payload.get("new_device")
        old_engine = payload.get("old_engine")
        new_engine = payload.get("new_engine")
        old_whisper_model = payload.get("old_whisper_model")
        new_whisper_model = payload.get("new_whisper_model")
        old_vad_engine = payload.get("old_vad_engine")
        new_vad_engine = payload.get("new_vad_engine")

        with self._lock:
            muted = self.settings.muted
            sensitivity = self.settings.interruption_sensitivity
        self._vad.set_sensitivity(sensitivity)
        if old_vad_engine != new_vad_engine:
            self._vad.set_preferred_engine(self.settings.vad_engine)
        if muted:
            self._cancel_listening_worker()
        if old_whisper_model != new_whisper_model:
            self._whisper = WhisperTranscriber(model_name=self.settings.whisper_model)
            self._whisper_dependency_available = self._whisper.dependency_available()
            self._whisper_load_failed = False
        if old_engine != new_engine:
            self._whisper_load_failed = False
        self._queue_whisper_warmup_worker()
        if old_device != new_device or old_engine != new_engine:
            self._cancel_listening_worker()
            self._refresh_devices_worker()
            self._open_stream_worker()
        self._apply_hotkey_setting_worker()

    def _apply_hotkey_setting_worker(self) -> None:
        with self._lock:
            should_enable = (
                self._running
                and self._accepting_requests
                and self.settings.hotkey_enabled
                and not self.settings.muted
                and self._resolved_engine() != "unavailable"
                and self._mic_stream is not None
            )
        if not should_enable or self._pynput is None:
            self._stop_hotkey_listener()
            return
        if self._hotkey_listener is not None:
            return
        try:
            keyboard = getattr(self._pynput, "keyboard")

            def trigger_hotkey() -> None:
                self.start_listening(origin="hotkey")

            self._hotkey_listener = keyboard.GlobalHotKeys({"<cmd>+j": trigger_hotkey})
            self._hotkey_listener.start()
        except Exception as exc:
            self._hotkey_listener = None
            logger.warning("[Freshy Voice] Win+J registration failed: %s", exc)

    def _stop_hotkey_listener(self) -> None:
        listener = self._hotkey_listener
        self._hotkey_listener = None
        if listener is None:
            return
        try:
            listener.stop()
        except Exception:
            pass

    def _update_input_level(self, rms: float, vad_score: float, engine: str) -> None:
        with self._lock:
            self._input_level = (self._input_level * 0.72) + (min(1.0, rms * 12.0) * 0.28)
            self._vad_score = (self._vad_score * 0.65) + (vad_score * 0.35)
            self._vad_engine_active = engine

    def _process_audio_worker(self, pcm_chunk: bytes) -> None:
        with self._lock:
            muted = self.settings.muted
            calibrating = self._is_calibrating
            listening = self._is_listening
            wake_enabled = self.settings.wake_word_enabled
            threshold = self.settings.noise_threshold
            tts_busy = self._tts_was_busy
            interrupt_enabled = self.settings.interrupt_while_speaking
            active_engine = self._resolved_engine()

        if muted or calibrating:
            return
        self._pre_roll.append(pcm_chunk)
        decision = self._vad.decide(pcm_chunk, threshold)
        rms = compute_pcm_rms(pcm_chunk)
        self._update_input_level(rms, decision.score, decision.engine)

        # VAD-level barge-in stops playback before STT finishes. The pre-roll
        # buffer keeps the first words for the new utterance.
        if tts_busy and interrupt_enabled and not listening:
            now = time.monotonic()
            sensitivity = self.settings.interruption_sensitivity
            warmup = {"low": 0.48, "normal": 0.34, "high": 0.14}[sensitivity]
            # Learn the speaker echo floor slowly, and never let a sudden loud
            # user onset immediately raise that floor. This avoids Freshy
            # interpreting its own output as an interrupt and repeatedly
            # stopping/restarting the audio stream.
            if self._tts_echo_rms <= 0:
                self._tts_echo_rms = rms
            else:
                baseline_cap = max(self._tts_echo_rms * 1.22, threshold * 1.45)
                if rms <= baseline_cap:
                    alpha = 0.035 if now - self._tts_started_at > warmup else 0.12
                    self._tts_echo_rms = (
                        self._tts_echo_rms * (1.0 - alpha)
                    ) + (rms * alpha)
            ratio = {"low": 2.00, "normal": 1.55, "high": 1.28}[sensitivity]
            energy_gate = max(
                threshold * {"low": 2.2, "normal": 1.65, "high": 1.18}[sensitivity],
                self._tts_echo_rms * ratio,
            )
            score_gate = {"low": 0.75, "normal": 0.62, "high": 0.50}[sensitivity]
            likely_user_onset = (
                decision.is_speech
                and decision.score >= score_gate
                and now - self._tts_started_at >= warmup
                and rms >= energy_gate
            )
            if likely_user_onset:
                if self._barge_in_candidate_started <= 0:
                    self._barge_in_candidate_started = now
                hold = {"low": 0.34, "normal": 0.22, "high": 0.12}[sensitivity]
                if now - self._barge_in_candidate_started >= hold:
                    self._activate_barge_in_worker("")
                    listening = True
                    tts_busy = False
                    active_engine = self._resolved_engine()
            else:
                self._barge_in_candidate_started = 0.0

        if not listening:
            if wake_enabled and self._recognizer is not None and rms >= threshold:
                self._process_vosk_wake_audio(pcm_chunk)
            return

        if decision.is_speech:
            now = time.monotonic()
            with self._lock:
                self._last_voice_activity = now
                if self._speech_started_at <= 0:
                    self._speech_started_at = now

        if active_engine == "vosk":
            self._process_vosk_command_audio(pcm_chunk)
        elif active_engine == "whisper":
            self._process_whisper_audio(pcm_chunk, decision.is_speech)

    def _process_vosk_wake_audio(self, pcm_chunk: bytes) -> None:
        try:
            if self._recognizer.AcceptWaveform(pcm_chunk):
                result = json.loads(self._recognizer.Result() or "{}")
                text = str(result.get("text", "")).strip()
                if text:
                    self._handle_wake_text(text)
            else:
                partial = json.loads(self._recognizer.PartialResult() or "{}")
                partial_text = str(partial.get("partial", "")).strip()
                if (
                    partial_text
                    and len(normalize_text(partial_text).split()) == 2
                    and split_wake_phrase(partial_text) == ""
                ):
                    self._activate_wake_worker()
        except Exception as exc:
            self._set_error(f"Vosk wake recognizer runtime error: {exc}")

    def _process_vosk_command_audio(self, pcm_chunk: bytes) -> None:
        if self._recognizer is None:
            return
        try:
            if self._recognizer.AcceptWaveform(pcm_chunk):
                result = json.loads(self._recognizer.Result() or "{}")
                text = str(result.get("text", "")).strip()
                if text:
                    self._vosk_final_parts.append(text)
                    self._update_partial_text(" ".join(self._vosk_final_parts))
                    with self._lock:
                        self._last_voice_activity = time.monotonic()
            else:
                partial = json.loads(self._recognizer.PartialResult() or "{}")
                partial_text = str(partial.get("partial", "")).strip()
                combined = " ".join([*self._vosk_final_parts, partial_text]).strip()
                if combined:
                    self._update_partial_text(combined)
                    with self._lock:
                        self._last_voice_activity = time.monotonic()
        except Exception as exc:
            self._set_error(f"Vosk recognizer runtime error: {exc}")

    def _process_whisper_audio(self, pcm_chunk: bytes, is_speech: bool) -> None:
        if is_speech and not self._whisper_audio:
            self._whisper_audio.extend(list(self._pre_roll))
        if self._whisper_audio:
            self._whisper_audio.append(pcm_chunk)
        now = time.monotonic()
        duration = len(self._whisper_audio) * CHUNK_MILLISECONDS / 1000.0
        if (
            self.settings.partial_processing
            and duration >= 1.0
            and now - self._last_whisper_partial_at >= 1.25
        ):
            self._last_whisper_partial_at = now
            self._enqueue_whisper(bytes().join(self._whisper_audio), final=False)

    def _enqueue_whisper(self, pcm: bytes, final: bool) -> None:
        with self._lock:
            generation = self._whisper_generation
            language = self.settings.speech_language
        item = {
            "action": "TRANSCRIBE",
            "generation": generation,
            "pcm": pcm,
            "final": final,
            "language": language,
        }
        try:
            self._whisper_queue.put_nowait(item)
        except queue.Full:
            if final:
                self._clear_whisper_queue()
                self._whisper_queue.put(item)

    def _get_tts_status(self) -> Dict[str, Any]:
        if self.tts_status_callback is None:
            return {}
        try:
            return self.tts_status_callback() or {}
        except Exception:
            return {}

    def _sync_tts_state_worker(self) -> None:
        status = self._get_tts_status()
        # Barge-in must react only to audio that is actually playing. Treating
        # neural generation/queued chunks as "speaking" caused false stops and
        # audible cut-cut playback before any sound had reached the speakers.
        tts_busy = bool(
            status.get("is_audio_playing", status.get("is_speaking", False))
        )
        if tts_busy == self._tts_was_busy:
            return
        self._tts_was_busy = tts_busy
        self._barge_in_candidate_started = 0.0
        if tts_busy:
            self._tts_started_at = time.monotonic()
            self._tts_echo_rms = 0.0
        else:
            self._tts_started_at = 0.0
            self._tts_echo_rms = 0.0
        with self._lock:
            listening = self._is_listening
        if listening:
            return
        try:
            self._reset_recognizer_worker(wake_only=True)
        except Exception as exc:
            self._set_error(f"Barge-in recognizer switch failed: {exc}")

    # Backward-compatible name used by existing tests.
    def _sync_tts_recognizer_mode_worker(self) -> None:
        self._sync_tts_state_worker()

    def _is_probable_user_barge_in(self, transcript: str) -> bool:
        normalized = normalize_text(transcript)
        words = normalized.split()
        if len(words) < 2:
            return False
        status = self._get_tts_status()
        spoken = normalize_text(str(status.get("current_text") or ""))
        if not spoken:
            return True
        if normalized in spoken:
            return False
        spoken_words = set(spoken.split())
        overlap = sum(1 for word in words if word in spoken_words)
        return overlap / len(words) < 0.70

    def _activate_barge_in_worker(self, partial_text: str) -> None:
        self._interrupt_tts()
        self._reset_utterance_state()
        self._reset_recognizer_worker(wake_only=False)
        now = time.monotonic()
        with self._lock:
            self._is_listening = True
            self._listen_request_pending = False
            self._freshy_status = "listening"
            self._voice_mode = "barge_in"
            self._session_id = uuid.uuid4().hex
            self._session_started_at = now
            self._last_voice_activity = now
            if partial_text:
                self._partial_transcript = partial_text
        if self._resolved_engine() == "whisper":
            self._whisper_audio.extend(list(self._pre_roll))
        self._tts_was_busy = False
        self._barge_in_candidate_started = 0.0

    def _activate_wake_worker(self) -> None:
        self._interrupt_tts()
        self._begin_listening_worker(uuid.uuid4().hex, origin="wake_word")

    def _handle_wake_text(self, raw_text: str) -> None:
        normalized = normalize_text(raw_text)
        wake_command = split_wake_phrase(normalized)
        if wake_command is None:
            return
        self._interrupt_tts()
        if wake_command:
            with self._lock:
                self._session_id = uuid.uuid4().hex
            self._accept_final_transcript(wake_command)
        else:
            self._begin_listening_worker(uuid.uuid4().hex, origin="wake_word")

    def _handle_recognized_speech_worker(self, raw_text: str) -> None:
        """Backward-compatible direct transcript entry used by tests."""
        normalized = normalize_text(raw_text)
        if not normalized:
            return
        with self._lock:
            listening = self._is_listening
            wake_enabled = self.settings.wake_word_enabled
        if not listening:
            if wake_enabled:
                self._handle_wake_text(raw_text)
            return
        self._accept_final_transcript(raw_text.strip())

    def _update_partial_text(self, text: str) -> None:
        clean = " ".join(str(text or "").split()).strip()
        if not clean:
            return
        with self._lock:
            if clean != self._partial_transcript:
                self._partial_transcript = clean
                self._partial_changed_at = time.monotonic()
            self._last_voice_activity = time.monotonic()

    def _effective_silence_seconds(self) -> float:
        with self._lock:
            base = self.settings.response_silence_seconds
            adaptive = self.settings.adaptive_silence
            text = self._partial_transcript.strip().lower()
        if not adaptive or not text:
            return base
        words = text.split()
        if words[-1:] and words[-1] in {
            "and", "or", "because", "aur", "ya", "ki", "lekin", "but", "then"
        }:
            return min(5.0, base + 1.2)
        if len(words) <= 4 or text.endswith(("?", "क्या", "कौन", "कब", "कैसे")):
            return max(1.8, base - 0.5)
        return base

    def _update_session_timeout_worker(self) -> None:
        with self._lock:
            if not self._is_listening:
                return
            started = self._session_started_at
            last_activity = self._last_voice_activity
            has_speech = bool(
                self._partial_transcript or self._vosk_final_parts or self._whisper_audio
            )
            timeout = self.settings.listening_timeout
            engine = self._resolved_engine()
        now = time.monotonic()
        if not has_speech and now - started >= timeout:
            self._cancel_listening_worker()
            return
        if not has_speech or now - last_activity < self._effective_silence_seconds():
            return

        if engine == "vosk":
            final_text = ""
            try:
                if self._recognizer is not None:
                    final = json.loads(self._recognizer.FinalResult() or "{}")
                    final_text = str(final.get("text", "")).strip()
            except Exception as exc:
                self._set_error(f"Vosk finalization error: {exc}")
            combined = " ".join([*self._vosk_final_parts, final_text]).strip()
            if not combined:
                combined = self._partial_transcript.strip()
            if combined:
                self._accept_final_transcript(combined)
            else:
                self._cancel_listening_worker()
        elif engine == "whisper":
            pcm = b"".join(self._whisper_audio)
            with self._lock:
                self._is_listening = False
                self._freshy_status = "thinking"
                self._voice_mode = "transcribing"
                self._partial_transcript = self._partial_transcript or "Transcribing…"
            if pcm:
                self._enqueue_whisper(pcm, final=True)
            else:
                self._finish_empty_transcription()

    def _finish_empty_transcription(self) -> None:
        with self._lock:
            self._is_listening = False
            self._freshy_status = "idle"
            self._voice_mode = "wake" if self.settings.wake_word_enabled else "idle"
            self._partial_transcript = ""
        self._reset_recognizer_worker(wake_only=True)

    @staticmethod
    def _is_safe_to_prepare(text: str) -> bool:
        normalized = normalize_text(text)
        if len(normalized.split()) < 4:
            return False
        dangerous_or_action = re.search(
            r"\b(open|launch|start|close|delete|remove|install|run|execute|search|"
            r"notepad|calculator|youtube|google|website|remind|shutdown|restart|khol|kholo)\b",
            normalized,
        )
        return dangerous_or_action is None

    def _maybe_start_fast_preparation_worker(self) -> None:
        with self._lock:
            enabled = self.settings.fast_response_preparation
            partial_enabled = self.settings.partial_processing
            listening = self._is_listening
            partial = self._partial_transcript
            stable_for = time.monotonic() - self._partial_changed_at
            already = self._speculation_started
        if (
            not enabled
            or not partial_enabled
            or not listening
            or already
            or self.prepare_callback is None
            or stable_for < 0.75
            or not self._is_safe_to_prepare(partial)
        ):
            return
        with self._lock:
            if self._speculation_started:
                return
            self._speculation_started = True
            self._preparing_response = True
            generation = self._prepare_generation
            prepared_text = partial

        def prepare() -> None:
            result: Optional[Dict[str, Any]] = None
            try:
                callback_result = self._invoke_callback(
                    self.prepare_callback, prepared_text, "voice-session"
                )
                if isinstance(callback_result, dict):
                    result = callback_result
            except Exception as exc:
                logger.debug("[Freshy Voice] Speculative preparation skipped: %s", exc)
            with self._lock:
                if generation == self._prepare_generation:
                    self._prepared_transcript = prepared_text
                    self._prepared_result = result
                    self._preparing_response = False

        threading.Thread(
            target=prepare,
            daemon=True,
            name="FreshyResponsePreparer",
        ).start()

    @staticmethod
    def _invoke_callback(callback: Callable[..., Any], *args: Any) -> Any:
        try:
            signature = inspect.signature(callback)
            parameters = list(signature.parameters.values())
            accepts_varargs = any(p.kind == p.VAR_POSITIONAL for p in parameters)
            if accepts_varargs or len(parameters) >= len(args):
                return callback(*args)
        except (TypeError, ValueError):
            pass
        return callback(args[0])

    def _prepared_matches(self, final_text: str) -> bool:
        with self._lock:
            prepared_text = self._prepared_transcript
            prepared_result = self._prepared_result
        if not prepared_text or not prepared_result:
            return False
        final_norm = normalize_text(final_text)
        prepared_norm = normalize_text(prepared_text)
        if not final_norm or not prepared_norm:
            return False
        ratio = SequenceMatcher(None, final_norm, prepared_norm).ratio()
        length_delta = abs(len(final_norm.split()) - len(prepared_norm.split()))
        return ratio >= 0.88 and length_delta <= 4

    def _accept_final_transcript(self, command_text: str) -> None:
        normalized = normalize_text(command_text)
        if not normalized:
            self._finish_empty_transcription()
            return
        now = time.monotonic()
        if (
            normalized == self._last_processed_text
            and now - self._last_processed_time < self._cooldown_seconds
        ):
            return

        with self._lock:
            self._last_processed_text = normalized
            self._last_processed_time = now
            self._is_listening = False
            self._freshy_status = "thinking"
            self._partial_transcript = ""
            self._voice_mode = "thinking"
            prepared = self._prepared_result if self._prepared_matches(command_text) else None

        result: Dict[str, Any] = {}
        if self.chat_callback is not None:
            try:
                if prepared is not None:
                    callback_result = self._invoke_callback(
                        self.chat_callback, command_text, prepared
                    )
                else:
                    callback_result = self._invoke_callback(self.chat_callback, command_text)
                if isinstance(callback_result, dict):
                    result = callback_result
            except Exception as exc:
                logger.exception("[Freshy Voice] Voice command failed")
                result = {
                    "reply": "Freshy could not process that voice command.",
                    "intent_name": "ERROR",
                    "success": False,
                    "action_executed": False,
                    "details": {"error": "voice_command_failed"},
                }

        action_executed = bool(result.get("action_executed", result.get("success", False)))
        command_success = bool(result.get("success", False))
        details = result.get("details") if isinstance(result.get("details"), dict) else {}
        with self._lock:
            self._result_id += 1
            self._result_token = uuid.uuid4().hex
            self._final_transcript = command_text
            self._assistant_reply = str(result.get("reply", ""))
            self._intent_name = str(result.get("intent_name", "UNKNOWN"))
            self._action_executed = action_executed
            self._command_success = command_success
            self._action_result = details
            self._freshy_status = "idle"
            self._voice_mode = "wake" if self.settings.wake_word_enabled else "idle"
            self._resume_continuous_after_tts = bool(self.settings.continuous_listening)
        self._reset_utterance_state()
        self._clear_audio_queue()
        self._reset_recognizer_worker(wake_only=True)

    # Backward-compatible alias.
    def _process_command_transcript_worker(self, command_text: str) -> None:
        self._accept_final_transcript(command_text)

    def _maybe_resume_continuous_worker(self) -> None:
        with self._lock:
            should_resume = (
                self._resume_continuous_after_tts
                and self._running
                and not self.settings.muted
                and not self._is_listening
            )
        if not should_resume:
            return
        status = self._get_tts_status()
        if bool(status.get("is_speaking")) or int(status.get("queue_size", 0) or 0) > 0:
            return
        with self._lock:
            self._resume_continuous_after_tts = False
        self._begin_listening_worker(uuid.uuid4().hex, origin="continuous")

    def _calibrate_worker(self, payload: Dict[str, Any]) -> None:
        event: threading.Event = payload["event"]
        result_box: Dict[str, Any] = payload["result"]
        timeout = max(1.0, min(10.0, float(payload.get("timeout", 4.0))))
        with self._lock:
            if self._is_calibrating:
                result_box.update({"success": False, "reason": "Calibration already running"})
                event.set()
                return
            self._is_calibrating = True
            self._freshy_status = "listening"
            self._voice_mode = "calibrating"
        self._clear_audio_queue()
        samples: List[float] = []
        deadline = time.monotonic() + min(timeout - 0.2, 3.5)
        while time.monotonic() < deadline:
            with self._lock:
                if not self._running:
                    break
            try:
                pcm = self._audio_queue.get(timeout=0.08)
            except queue.Empty:
                continue
            samples.append(compute_pcm_rms(pcm))
        if samples:
            sorted_samples = sorted(samples)
            percentile = sorted_samples[min(len(sorted_samples) - 1, int(len(sorted_samples) * 0.85))]
            threshold = max(0.005, min(0.25, percentile * 2.2))
            with self._lock:
                self.settings = self.settings.updated({"noise_threshold": threshold})
                settings = self.settings
            try:
                self._save_settings(settings)
            except RuntimeError as exc:
                result_box.update({"success": False, "reason": str(exc)})
            else:
                result_box.update(
                    {
                        "success": True,
                        "calibrated_threshold": threshold,
                        "sample_count": len(samples),
                    }
                )
        else:
            result_box.update({"success": False, "reason": "No microphone audio was captured"})
        with self._lock:
            self._calibration_id += 1
            self._is_calibrating = False
            self._freshy_status = "idle"
            self._voice_mode = "wake" if self.settings.wake_word_enabled else "idle"
            self._calibration_result = dict(result_box)
        event.set()

    def _interrupt_tts(self) -> None:
        if self.tts_stop_callback is None:
            return
        try:
            self.tts_stop_callback()
        except Exception as exc:
            logger.warning("[Freshy Voice] TTS interruption failed: %s", exc)

    def update_settings(self, updates: Dict[str, Any]) -> VoiceSettings:
        with self._lock:
            if not self._accepting_requests:
                raise RuntimeError("Voice service is not accepting settings")
            old = self.settings
            candidate = old.updated(updates)
        if candidate.device_index is not None:
            valid_ids = {device["id"] for device in self.get_devices()}
            if candidate.device_index not in valid_ids:
                raise ValueError(f"Microphone device {candidate.device_index} is unavailable")
        self._save_settings(candidate)
        with self._lock:
            self.settings = candidate
        self._cmd_queue.put(
            (
                "APPLY_SETTINGS",
                {
                    "old_device": old.device_index,
                    "new_device": candidate.device_index,
                    "old_engine": old.recognition_engine,
                    "new_engine": candidate.recognition_engine,
                    "old_whisper_model": old.whisper_model,
                    "new_whisper_model": candidate.whisper_model,
                    "old_vad_engine": old.vad_engine,
                    "new_vad_engine": candidate.vad_engine,
                },
            )
        )
        return VoiceSettings.from_dict(candidate.to_dict())

    def start_listening(self, origin: str = "api") -> Dict[str, Any]:
        with self._lock:
            if not self._accepting_requests or self._shutdown_state != "active":
                return {"accepted": False, "reason": "Voice service is not ready"}
            if self.settings.muted:
                return {"accepted": False, "reason": "Microphone is muted"}
            if self._resolved_engine() == "unavailable":
                return {
                    "accepted": False,
                    "reason": "Selected speech engine is unavailable. Install faster-whisper or prepare the Vosk model.",
                }
            if not self._mic_available or self._mic_stream is None:
                return {"accepted": False, "reason": "No working microphone is available"}
            if self._is_calibrating:
                return {"accepted": False, "reason": "Noise calibration is running"}
            if self._is_listening or self._listen_request_pending:
                return {"accepted": True, "reason": "Already listening"}
            session_id = uuid.uuid4().hex
            self._listen_request_pending = True
        self._interrupt_tts()
        self._cmd_queue.put(("START_LISTEN", {"session_id": session_id, "origin": origin}))
        return {
            "accepted": True,
            "reason": "Listening started",
            "session_id": session_id,
            "recognition_engine": self._resolved_engine(),
        }

    def stop_listening(self) -> Dict[str, Any]:
        with self._lock:
            if not self._accepting_requests:
                return {"accepted": False, "reason": "Voice service is unavailable"}
        self._cmd_queue.put(("STOP_LISTEN", {}))
        return {"accepted": True, "reason": "Listening stopped"}

    def calibrate_noise(self, timeout: float = 4.0) -> Dict[str, Any]:
        with self._lock:
            if not self._accepting_requests or not self._mic_available:
                return {"success": False, "reason": "Microphone is unavailable"}
            if self._is_calibrating:
                return {"success": False, "reason": "Calibration already running"}
        event = threading.Event()
        result: Dict[str, Any] = {}
        self._cmd_queue.put(("CALIBRATE", {"event": event, "result": result, "timeout": timeout}))
        if not event.wait(max(1.0, timeout + 1.0)):
            return {"success": False, "reason": "Calibration timed out"}
        return result

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            active_engine = self._resolved_engine()
            worker_alive = self._worker_thread.is_alive() if self._worker_thread else False
            whisper_worker_alive = self._whisper_thread.is_alive() if self._whisper_thread else False
            model_loaded = (
                self._vosk_model_loaded if active_engine == "vosk" else self._whisper_dependency_available
            )
            if self.settings.muted:
                voice_mode = "muted"
            else:
                voice_mode = self._voice_mode
            return {
                "is_listening": self._is_listening,
                "listen_request_pending": self._listen_request_pending,
                "is_calibrating": self._is_calibrating,
                "freshy_status": self._freshy_status,
                "voice_mode": voice_mode,
                "session_id": self._session_id,
                "result_id": self._result_id,
                "result_token": self._result_token,
                "partial_transcript": self._partial_transcript,
                "final_transcript": self._final_transcript,
                "assistant_reply": self._assistant_reply,
                "intent": self._intent_name,
                "action_executed": self._action_executed,
                "success": self._command_success,
                "action_result": dict(self._action_result),
                "model_loaded": model_loaded,
                "vosk_model_loaded": self._vosk_model_loaded,
                "whisper_available": self._whisper_dependency_available,
                "whisper_model_loaded": self._whisper.model_loaded,
                "whisper_loading": self._whisper.loading,
                "whisper_load_failed": self._whisper_load_failed,
                "whisper_error": self._whisper.initialization_error,
                "whisper_initialization_error": self._whisper.initialization_error,
                "recognition_engine_requested": self.settings.recognition_engine,
                "recognition_engine_active": active_engine,
                "wake_word_available": self._vosk_model_loaded,
                "mic_available": self._mic_available,
                "input_level": round(self._input_level, 4),
                "vad_score": round(self._vad_score, 4),
                "vad_engine": self._vad_engine_active,
                "echo_guard_level": round(self._tts_echo_rms, 4),
                "preparing_response": self._preparing_response,
                "prepared_response_ready": self._prepared_result is not None,
                "adaptive_silence_seconds": round(self._effective_silence_seconds(), 2),
                "error_status": self._error_status,
                "settings": self.settings.to_dict(),
                "calibration_id": self._calibration_id,
                "calibration_result": dict(self._calibration_result),
                "running": self._running,
                "worker_alive": worker_alive,
                "whisper_worker_alive": whisper_worker_alive,
                "shutdown_state": self._shutdown_state,
            }

    def wait_until_ready(self, timeout: float = 5.0) -> bool:
        return self._worker_ready.wait(max(0.0, float(timeout)))

    def shutdown(self, timeout: float = 3.0) -> Dict[str, Any]:
        with self._lock:
            if self._shutdown_state in {"shutting_down", "shut_down"}:
                return {"accepted": False, "reason": "Already shut down or shutting down"}
            self._shutdown_state = "shutting_down"
            self._accepting_requests = False
        self._cmd_queue.put(("SHUTDOWN", {}))
        current = threading.current_thread()
        deadline = max(0.0, float(timeout))
        for worker in (self._worker_thread, self._whisper_thread):
            if worker and worker.is_alive() and worker is not current:
                worker.join(timeout=deadline)
        alive = bool(
            (self._worker_thread and self._worker_thread.is_alive())
            or (self._whisper_thread and self._whisper_thread.is_alive())
        )
        with self._lock:
            if alive:
                self._shutdown_state = "shutdown_timeout"
                return {"accepted": False, "reason": "Voice worker termination timed out"}
            self._shutdown_state = "shut_down"
            self._running = False
            return {"accepted": True, "reason": "Voice service shut down cleanly"}


class UnavailableVoiceInputService:
    def __init__(self, reason: str):
        self._reason = str(reason)
        self.settings = VoiceSettings()

    def get_devices(self) -> List[Dict[str, Any]]:
        return []

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_listening": False,
            "listen_request_pending": False,
            "is_calibrating": False,
            "freshy_status": "idle",
            "voice_mode": "disabled",
            "session_id": "",
            "result_id": 0,
            "result_token": "",
            "partial_transcript": "",
            "final_transcript": "",
            "assistant_reply": "",
            "intent": "",
            "action_executed": False,
            "success": False,
            "action_result": {},
            "model_loaded": False,
            "vosk_model_loaded": False,
            "whisper_available": False,
            "whisper_model_loaded": False,
            "whisper_loading": False,
            "whisper_load_failed": True,
            "whisper_error": self._reason,
            "recognition_engine_requested": self.settings.recognition_engine,
            "recognition_engine_active": "unavailable",
            "wake_word_available": False,
            "mic_available": False,
            "input_level": 0.0,
            "vad_score": 0.0,
            "vad_engine": "unavailable",
            "preparing_response": False,
            "prepared_response_ready": False,
            "adaptive_silence_seconds": self.settings.response_silence_seconds,
            "error_status": self._reason,
            "settings": self.settings.to_dict(),
            "calibration_id": 0,
            "calibration_result": {},
            "running": False,
            "worker_alive": False,
            "whisper_worker_alive": False,
            "shutdown_state": "failed",
        }

    def update_settings(self, updates: Dict[str, Any]) -> VoiceSettings:
        del updates
        raise RuntimeError(self._reason)

    def start_listening(self, origin: str = "api") -> Dict[str, Any]:
        del origin
        return {"accepted": False, "reason": self._reason}

    def stop_listening(self) -> Dict[str, Any]:
        return {"accepted": False, "reason": self._reason}

    def calibrate_noise(self, timeout: float = 0.0) -> Dict[str, Any]:
        del timeout
        return {"success": False, "reason": self._reason}

    def wait_until_ready(self, timeout: float = 0.0) -> bool:
        del timeout
        return True

    def shutdown(self, timeout: float = 0.0) -> Dict[str, Any]:
        del timeout
        return {"accepted": True, "reason": "Fallback voice service has no worker"}
