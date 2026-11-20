from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MemoryMode = Literal[
    "ask_before_saving",
    "auto_safe",
    "manual_only",
    "disabled",
]
MemoryCategory = Literal["profile", "preference", "project", "note"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MemorySettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    mode: MemoryMode = "ask_before_saving"
    persist_conversations: bool = True
    auto_profile_detection: bool = True
    max_items: int = Field(default=500, ge=10, le=5000)
    max_item_characters: int = Field(default=2000, ge=100, le=10000)
    recall_limit: int = Field(default=6, ge=1, le=20)
    recall_characters: int = Field(default=2500, ge=250, le=12000)
    conversation_retention_days: int = Field(default=30, ge=1, le=3650)


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: MemoryCategory = "note"
    key: str = "note"
    value: str
    tags: List[str] = Field(default_factory=list)
    importance: int = Field(default=3, ge=1, le=5)
    source: str = "user"

    @field_validator("key", "value", mode="before")
    @classmethod
    def clean_text(cls, value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, value: Any) -> List[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        output: List[str] = []
        for item in items:
            tag = str(item or "").strip().lower()[:40]
            if tag and tag not in output:
                output.append(tag)
        return output[:12]


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    category: MemoryCategory
    key: str
    value: str
    tags: List[str] = Field(default_factory=list)
    importance: int = 3
    pinned: bool = False
    source: str = "user"
    session_id: Optional[str] = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    last_accessed_at: Optional[str] = None
    access_count: int = 0


class MemoryStatus(BaseModel):
    enabled: bool
    mode: MemoryMode
    database_ready: bool
    memory_count: int
    pinned_count: int
    pending_count: int
    conversation_session_count: int
    conversation_message_count: int
    persist_conversations: bool
    database_path: str


class MemoryCommandResult(BaseModel):
    handled: bool = False
    reply: str = ""
    intent: str = "memory"
    success: bool = True
    pending_confirmation: bool = False
    memory_count: int = 0
    memory_id: Optional[str] = None
    speech_text: Optional[str] = None
    error_code: Optional[str] = None


class MemoryListResponse(BaseModel):
    items: List[MemoryRecord] = Field(default_factory=list)
    total: int = 0


class MemoryCreateRequest(BaseModel):
    category: MemoryCategory = "note"
    key: str = "note"
    value: str
    tags: List[str] = Field(default_factory=list)
    importance: int = Field(default=3, ge=1, le=5)
    pinned: bool = False


class MemoryUpdateRequest(BaseModel):
    category: Optional[MemoryCategory] = None
    key: Optional[str] = None
    value: Optional[str] = None
    tags: Optional[List[str]] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    pinned: Optional[bool] = None


class MemorySettingsUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    mode: Optional[MemoryMode] = None
    persist_conversations: Optional[bool] = None
    auto_profile_detection: Optional[bool] = None
    max_items: Optional[int] = Field(default=None, ge=10, le=5000)
    max_item_characters: Optional[int] = Field(default=None, ge=100, le=10000)
    recall_limit: Optional[int] = Field(default=None, ge=1, le=20)
    recall_characters: Optional[int] = Field(default=None, ge=250, le=12000)
    conversation_retention_days: Optional[int] = Field(default=None, ge=1, le=3650)


class MemoryImportRequest(BaseModel):
    items: List[MemoryCreateRequest] = Field(default_factory=list)
    replace_existing: bool = False


class MemoryClearRequest(BaseModel):
    confirm: bool = False


class MemoryAuditEntry(BaseModel):
    id: int
    action: str
    memory_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
