import threading
from typing import Any, Dict, List, Optional

from ai.schemas import ChatMessage, ConversationSession
from config import config


class ConversationStore:
    def __init__(
        self,
        max_messages: Optional[int] = None,
        max_characters: Optional[int] = None,
        persistence: Optional[Any] = None,
    ):
        self.max_messages = max_messages or config.AI_MAX_HISTORY_MESSAGES
        self.max_characters = max_characters or config.AI_MAX_HISTORY_CHARACTERS
        self.persistence = persistence
        self._sessions: Dict[str, ConversationSession] = {}
        self._loaded_sessions: set[str] = set()
        self._lock = threading.RLock()

    @staticmethod
    def _normalize_session_id(session_id: str) -> str:
        value = str(session_id or "default-session").strip()[:128]
        return value or "default-session"

    def _load_persisted(self, session_id: str) -> None:
        key = self._normalize_session_id(session_id)
        if key in self._loaded_sessions:
            return
        self._loaded_sessions.add(key)
        if self.persistence is None:
            return
        loader = getattr(self.persistence, "load_conversation_messages", None)
        if not callable(loader):
            return
        try:
            rows = loader(key, self.max_messages, self.max_characters)
        except Exception:
            return
        if not rows:
            return
        session = self._sessions.setdefault(key, ConversationSession(session_id=key))
        for row in rows:
            try:
                session.history.append(
                    ChatMessage(
                        role=str(row.get("role", "user")),
                        content=str(row.get("content", "")),
                        name=row.get("name"),
                    )
                )
            except Exception:
                continue
        self._prune(session)

    def _get_or_create(self, session_id: str) -> ConversationSession:
        key = self._normalize_session_id(session_id)
        self._load_persisted(key)
        if key not in self._sessions:
            self._sessions[key] = ConversationSession(session_id=key)
        return self._sessions[key]

    def _prune(self, session: ConversationSession) -> None:
        while len(session.history) > self.max_messages:
            session.history.pop(0)
        total = sum(len(item.content) for item in session.history)
        while session.history and total > self.max_characters:
            removed = session.history.pop(0)
            total -= len(removed.content)

    def get_history(self, session_id: str) -> List[ChatMessage]:
        with self._lock:
            session = self._get_or_create(session_id)
            return [item.model_copy(deep=True) for item in session.history]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        name: Optional[str] = None,
    ) -> None:
        clean = str(content or "").strip()
        if not clean:
            return
        if len(clean) > self.max_characters:
            clean = clean[-self.max_characters :]
        key = self._normalize_session_id(session_id)
        with self._lock:
            session = self._get_or_create(key)
            session.history.append(ChatMessage(role=role, content=clean, name=name))
            self._prune(session)
            if self.persistence is not None:
                writer = getattr(self.persistence, "add_conversation_message", None)
                if callable(writer):
                    try:
                        try:
                            writer(
                                key,
                                role,
                                clean,
                                name,
                                self.max_messages,
                                self.max_characters,
                            )
                        except TypeError:
                            writer(key, role, clean, name)
                    except Exception:
                        pass

    def clear_session(self, session_id: str) -> bool:
        with self._lock:
            key = self._normalize_session_id(session_id)
            removed_memory = self._sessions.pop(key, None) is not None
            self._loaded_sessions.discard(key)
            removed_persistent = False
            if self.persistence is not None:
                clearer = getattr(self.persistence, "clear_conversation", None)
                if callable(clearer):
                    try:
                        removed_persistent = bool(clearer(key))
                    except Exception:
                        removed_persistent = False
            return removed_memory or removed_persistent

    def clear_all(self) -> int:
        with self._lock:
            count = len(self._sessions)
            keys = list(self._sessions)
            self._sessions.clear()
            self._loaded_sessions.clear()
            if self.persistence is not None:
                clearer = getattr(self.persistence, "clear_conversation", None)
                if callable(clearer):
                    for key in keys:
                        try:
                            clearer(key)
                        except Exception:
                            pass
            return count

    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)
