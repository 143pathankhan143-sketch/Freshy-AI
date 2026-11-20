from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LiveSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    conversation_mode: Literal["standard", "live"] = "standard"
    model: str = "gemini-3.1-flash-live-preview"
    voice_name: str = "Kore"
    language_hint: Literal["auto", "hi-IN", "en-IN"] = "auto"
    auto_start: bool = False
    tools_enabled: bool = True
    memory_context_enabled: bool = True
    input_transcription: bool = True
    output_transcription: bool = True
    automatic_activity_detection: bool = True
    interruption_enabled: bool = True
    local_barge_in: bool = True
    echo_guard_enabled: bool = True
    start_sensitivity: Literal["low", "normal", "high"] = "normal"
    end_sensitivity: Literal["low", "normal", "high"] = "normal"
    prefix_padding_ms: int = Field(default=120, ge=20, le=1000)
    silence_duration_ms: int = Field(default=700, ge=200, le=5000)
    microphone_chunk_ms: int = Field(default=40, ge=20, le=200)
    input_sample_rate: int = Field(default=16000, ge=8000, le=48000)
    output_sample_rate: int = Field(default=24000, ge=8000, le=48000)
    output_buffer_ms: int = Field(default=80, ge=20, le=1000)
    session_resumption: bool = True
    context_compression: bool = True
    reconnect_attempts: int = Field(default=3, ge=0, le=10)
    reconnect_delay_seconds: float = Field(default=1.0, ge=0.1, le=30.0)
    fallback_mode: Literal["standard", "text_only"] = "standard"
    noise_threshold: float = Field(default=0.018, ge=0.001, le=0.5)

    @field_validator("model", "voice_name", mode="before")
    @classmethod
    def _non_empty(cls, value: Any) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("Live model and voice name cannot be empty.")
        return cleaned


class LiveMetrics(BaseModel):
    speech_started_at: Optional[float] = None
    speech_ended_at: Optional[float] = None
    first_audio_sent_at: Optional[float] = None
    first_model_event_at: Optional[float] = None
    first_audio_received_at: Optional[float] = None
    playback_started_at: Optional[float] = None
    interruption_detected_at: Optional[float] = None
    playback_stopped_at: Optional[float] = None
    input_audio_chunks: int = 0
    output_audio_chunks: int = 0
    output_buffer_underruns: int = 0
    reconnect_count: int = 0
    tool_call_count: int = 0
    last_turn_complete_at: Optional[float] = None

    def durations(self) -> Dict[str, Optional[float]]:
        def delta(end: Optional[float], start: Optional[float]) -> Optional[float]:
            if end is None or start is None:
                return None
            return max(0.0, round(end - start, 4))

        return {
            "speech_to_first_model_seconds": delta(self.first_model_event_at, self.speech_ended_at),
            "speech_to_first_audio_seconds": delta(self.first_audio_received_at, self.speech_ended_at),
            "audio_to_playback_seconds": delta(self.playback_started_at, self.first_audio_received_at),
            "barge_in_stop_seconds": delta(self.playback_stopped_at, self.interruption_detected_at),
        }


class LiveStatus(BaseModel):
    configured: bool = False
    enabled: bool = True
    conversation_mode: str = "standard"
    state: str = "idle"
    connected: bool = False
    connecting: bool = False
    microphone_active: bool = False
    microphone_muted: bool = False
    output_playing: bool = False
    model: str = ""
    voice_name: str = ""
    session_id: str = ""
    session_resumable: bool = False
    last_input_transcript: str = ""
    last_output_transcript: str = ""
    partial_input_transcript: str = ""
    last_error: str = ""
    fallback_mode: str = "standard"
    active_tool: Optional[str] = None
    last_tool: Optional[str] = None
    last_tool_success: bool = False
    last_action_executed: bool = False
    result_id: int = 0
    result_token: str = ""
    input_level: float = 0.0
    output_level: float = 0.0
    metrics: Dict[str, Any] = Field(default_factory=dict)
