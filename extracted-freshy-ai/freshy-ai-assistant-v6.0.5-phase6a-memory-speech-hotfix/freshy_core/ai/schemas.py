from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system", "tool"]
    content: str
    name: Optional[str] = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str
    session_id: str = "default-session"
    allow_web_search: bool = True

    @field_validator("session_id", mode="before")
    @classmethod
    def normalize_session_id(cls, value: Any) -> str:
        text = str(value or "default-session").strip()
        return text[:128] or "default-session"


class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: Optional[float] = None


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    call_id: Optional[str] = None


class ToolResult(BaseModel):
    success: bool
    output: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProviderAttempt(BaseModel):
    provider: str
    status: str


class ProviderError(BaseModel):
    code: str
    safe_message: str


class AssistantResponse(BaseModel):
    reply: str
    intent: str
    action: str = "none"
    action_executed: bool = False
    success: bool
    provider: str
    model: Optional[str] = None
    used_web_search: bool = False
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    fallback_chain: List[Dict[str, Any]] = Field(default_factory=list)
    tool_used: Optional[str] = None
    speech_text: Optional[str] = None
    tts_requested: bool = True
    error_code: Optional[str] = None
    user_safe_error: Optional[str] = None
    memory_used: bool = False
    memory_count: int = 0
    memory_pending: bool = False


class ProviderResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: List[ToolRequest] = Field(default_factory=list)
    provider_name: str
    model_name: str
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ConversationSession(BaseModel):
    session_id: str
    history: List[ChatMessage] = Field(default_factory=list)
