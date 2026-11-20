from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from memory.safety import contains_secret
from memory.schemas import (
    MemoryAuditEntry,
    MemoryCandidate,
    MemoryRecord,
    MemorySettings,
    utc_now_iso,
)


class MemoryStore:
    """Thread-safe SQLite store for permanent memories and bounded chat history."""

    def __init__(self, database_path: str, settings: MemorySettings):
        self.database_path = os.path.abspath(database_path)
        self._settings = settings.model_copy(deep=True)
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        self._initialize()
        self._load_persisted_settings()
        self.cleanup_old_conversations()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def _db(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    importance INTEGER NOT NULL DEFAULT 3,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'user',
                    session_id TEXT,
                    fingerprint TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT,
                    access_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
                CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_pinned ON memories(pinned DESC);

                CREATE TABLE IF NOT EXISTS pending_memories (
                    session_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    name TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES conversation_sessions(session_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_conversation_messages_session
                    ON conversation_messages(session_id, id DESC);

                CREATE TABLE IF NOT EXISTS memory_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    memory_id TEXT,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )
            db.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('schema_version', '1')"
            )

    @property
    def settings(self) -> MemorySettings:
        with self._lock:
            return self._settings.model_copy(deep=True)

    def _load_persisted_settings(self) -> None:
        with self._lock, self._db() as db:
            rows = db.execute("SELECT key, value FROM memory_settings").fetchall()
        if not rows:
            return
        values: Dict[str, Any] = self._settings.model_dump()
        for row in rows:
            key = str(row["key"])
            if key not in values:
                continue
            try:
                values[key] = json.loads(str(row["value"]))
            except json.JSONDecodeError:
                continue
        self._settings = MemorySettings.model_validate(values)

    def update_settings(self, updates: Dict[str, Any]) -> MemorySettings:
        with self._lock:
            merged = self._settings.model_dump()
            merged.update({key: value for key, value in updates.items() if value is not None})
            updated = MemorySettings.model_validate(merged)
            now = utc_now_iso()
            with self._db() as db:
                for key, value in updated.model_dump().items():
                    db.execute(
                        """
                        INSERT INTO memory_settings(key, value, updated_at)
                        VALUES(?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                        """,
                        (key, json.dumps(value), now),
                    )
            self._settings = updated
            self._audit("settings_updated", None, {"keys": sorted(updates)})
            self._enforce_memory_limit()
            self.cleanup_old_conversations()
            return updated.model_copy(deep=True)

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(str(value or "").lower().strip().split())

    @classmethod
    def _fingerprint(cls, category: str, key: str, value: str) -> str:
        raw = "\n".join((cls._normalize(category), cls._normalize(key), cls._normalize(value)))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> MemoryRecord:
        try:
            tags = json.loads(str(row["tags_json"] or "[]"))
        except json.JSONDecodeError:
            tags = []
        return MemoryRecord(
            id=str(row["id"]),
            category=str(row["category"]),
            key=str(row["memory_key"]),
            value=str(row["value"]),
            tags=tags if isinstance(tags, list) else [],
            importance=int(row["importance"]),
            pinned=bool(row["pinned"]),
            source=str(row["source"]),
            session_id=row["session_id"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            last_accessed_at=row["last_accessed_at"],
            access_count=int(row["access_count"]),
        )

    def add_memory(
        self,
        candidate: MemoryCandidate,
        *,
        session_id: Optional[str] = None,
        pinned: bool = False,
    ) -> Tuple[MemoryRecord, bool]:
        settings = self.settings
        value = candidate.value[: settings.max_item_characters].strip()
        key = candidate.key[:120].strip() or "note"
        fingerprint = self._fingerprint(candidate.category, key, value)
        now = utc_now_iso()
        duplicate_record: Optional[MemoryRecord] = None
        with self._lock, self._db() as db:
            existing = db.execute(
                "SELECT * FROM memories WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if existing is not None:
                db.execute(
                    """
                    UPDATE memories
                    SET updated_at = ?, importance = MAX(importance, ?), pinned = MAX(pinned, ?)
                    WHERE id = ?
                    """,
                    (now, candidate.importance, int(pinned), existing["id"]),
                )
                row = db.execute("SELECT * FROM memories WHERE id = ?", (existing["id"],)).fetchone()
                duplicate_record = self._row_to_memory(row)
            else:
                memory_id = uuid.uuid4().hex
                db.execute(
                """
                INSERT INTO memories(
                    id, category, memory_key, value, tags_json, importance, pinned,
                    source, session_id, fingerprint, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        memory_id,
                        candidate.category,
                        key,
                        value,
                        json.dumps(candidate.tags, ensure_ascii=False),
                        candidate.importance,
                        int(pinned),
                        candidate.source,
                        session_id,
                        fingerprint,
                        now,
                        now,
                    ),
                )
                row = db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if duplicate_record is not None:
            self._audit("duplicate_reused", duplicate_record.id, {"category": duplicate_record.category})
            return duplicate_record, False
        record = self._row_to_memory(row)
        self._audit("created", record.id, {"category": record.category, "key": record.key})
        self._enforce_memory_limit()
        return record, True

    def get_memory(self, memory_id: str) -> Optional[MemoryRecord]:
        with self._lock, self._db() as db:
            row = db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return self._row_to_memory(row) if row is not None else None

    def list_memories(
        self,
        *,
        query: str = "",
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[MemoryRecord], int]:
        clauses: List[str] = []
        params: List[Any] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if query.strip():
            like = f"%{query.strip()}%"
            clauses.append("(memory_key LIKE ? OR value LIKE ? OR tags_json LIKE ?)")
            params.extend([like, like, like])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))
        with self._lock, self._db() as db:
            total = int(db.execute(f"SELECT COUNT(*) FROM memories{where}", params).fetchone()[0])
            rows = db.execute(
                f"""
                SELECT * FROM memories{where}
                ORDER BY pinned DESC, importance DESC, updated_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, safe_limit, safe_offset],
            ).fetchall()
        return [self._row_to_memory(row) for row in rows], total

    def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> Optional[MemoryRecord]:
        current = self.get_memory(memory_id)
        if current is None:
            return None
        data = current.model_dump()
        data.update({key: value for key, value in updates.items() if value is not None})
        candidate = MemoryCandidate(
            category=data["category"],
            key=str(data["key"]),
            value=str(data["value"]),
            tags=list(data.get("tags") or []),
            importance=int(data.get("importance", 3)),
            source=str(data.get("source", "user")),
        )
        settings = self.settings
        value = candidate.value[: settings.max_item_characters]
        fingerprint = self._fingerprint(candidate.category, candidate.key, value)
        now = utc_now_iso()
        with self._lock, self._db() as db:
            duplicate = db.execute(
                "SELECT id FROM memories WHERE fingerprint = ? AND id != ?",
                (fingerprint, memory_id),
            ).fetchone()
            if duplicate is not None:
                raise ValueError("An identical memory already exists.")
            db.execute(
                """
                UPDATE memories SET
                    category = ?, memory_key = ?, value = ?, tags_json = ?,
                    importance = ?, pinned = ?, fingerprint = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    candidate.category,
                    candidate.key[:120],
                    value,
                    json.dumps(candidate.tags, ensure_ascii=False),
                    candidate.importance,
                    int(bool(data.get("pinned"))),
                    fingerprint,
                    now,
                    memory_id,
                ),
            )
            row = db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        record = self._row_to_memory(row)
        self._audit("updated", memory_id, {"category": record.category, "key": record.key})
        return record

    def delete_memory(self, memory_id: str) -> bool:
        with self._lock, self._db() as db:
            cursor = db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            deleted = cursor.rowcount > 0
        if deleted:
            self._audit("deleted", memory_id, {})
        return deleted

    def delete_matching(self, query: str, limit: int = 20) -> int:
        items, _ = self.list_memories(query=query, limit=limit)
        count = 0
        for item in items:
            if self.delete_memory(item.id):
                count += 1
        return count

    def set_pinned(self, memory_id: str, pinned: bool) -> Optional[MemoryRecord]:
        with self._lock, self._db() as db:
            db.execute(
                "UPDATE memories SET pinned = ?, updated_at = ? WHERE id = ?",
                (int(pinned), utc_now_iso(), memory_id),
            )
            row = db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            return None
        record = self._row_to_memory(row)
        self._audit("pinned" if pinned else "unpinned", memory_id, {})
        return record

    def clear_memories(self) -> int:
        with self._lock, self._db() as db:
            count = int(db.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            db.execute("DELETE FROM memories")
            db.execute("DELETE FROM pending_memories")
        self._audit("cleared_all", None, {"count": count})
        return count

    def count_memories(self) -> Tuple[int, int]:
        with self._lock, self._db() as db:
            row = db.execute(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN pinned = 1 THEN 1 ELSE 0 END) AS pinned FROM memories"
            ).fetchone()
        return int(row["total"] or 0), int(row["pinned"] or 0)

    def save_pending(self, session_id: str, candidate: MemoryCandidate) -> None:
        key = self.normalize_session_id(session_id)
        with self._lock, self._db() as db:
            db.execute(
                """
                INSERT INTO pending_memories(session_id, payload_json, created_at)
                VALUES(?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    payload_json=excluded.payload_json, created_at=excluded.created_at
                """,
                (key, candidate.model_dump_json(), utc_now_iso()),
            )

    def get_pending(self, session_id: str) -> Optional[MemoryCandidate]:
        key = self.normalize_session_id(session_id)
        with self._lock, self._db() as db:
            row = db.execute(
                "SELECT payload_json FROM pending_memories WHERE session_id = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        try:
            return MemoryCandidate.model_validate_json(str(row["payload_json"]))
        except Exception:
            self.clear_pending(key)
            return None

    def clear_pending(self, session_id: str) -> bool:
        key = self.normalize_session_id(session_id)
        with self._lock, self._db() as db:
            cursor = db.execute("DELETE FROM pending_memories WHERE session_id = ?", (key,))
            return cursor.rowcount > 0

    def pending_count(self) -> int:
        with self._lock, self._db() as db:
            return int(db.execute("SELECT COUNT(*) FROM pending_memories").fetchone()[0])

    @staticmethod
    def normalize_session_id(session_id: str) -> str:
        value = str(session_id or "default-session").strip()[:128]
        return value or "default-session"

    def add_conversation_message(
        self,
        session_id: str,
        role: str,
        content: str,
        name: Optional[str] = None,
        max_messages: int = 100,
        max_characters: int = 100000,
    ) -> None:
        if not self.settings.persist_conversations:
            return
        key = self.normalize_session_id(session_id)
        clean = str(content or "").strip()
        if not clean or contains_secret(clean):
            return
        safe_max_messages = max(2, min(int(max_messages), 500))
        safe_max_characters = max(1000, min(int(max_characters), 500000))
        now = utc_now_iso()
        with self._lock, self._db() as db:
            db.execute(
                """
                INSERT INTO conversation_sessions(session_id, created_at, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET updated_at=excluded.updated_at
                """,
                (key, now, now),
            )
            db.execute(
                """
                INSERT INTO conversation_messages(session_id, role, content, name, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (key, role, clean, name, now),
            )
            db.execute(
                """
                DELETE FROM conversation_messages
                WHERE session_id = ? AND id NOT IN (
                    SELECT id FROM conversation_messages
                    WHERE session_id = ? ORDER BY id DESC LIMIT ?
                )
                """,
                (key, key, safe_max_messages),
            )
            rows = db.execute(
                """
                SELECT id, LENGTH(content) AS size FROM conversation_messages
                WHERE session_id = ? ORDER BY id DESC
                """,
                (key,),
            ).fetchall()
            total = 0
            keep_ids: List[int] = []
            for row in rows:
                size = int(row["size"] or 0)
                if keep_ids and total + size > safe_max_characters:
                    continue
                keep_ids.append(int(row["id"]))
                total += size
            if keep_ids:
                placeholders = ",".join("?" for _ in keep_ids)
                db.execute(
                    f"DELETE FROM conversation_messages WHERE session_id = ? AND id NOT IN ({placeholders})",
                    [key, *keep_ids],
                )

    def load_conversation_messages(
        self, session_id: str, max_messages: int, max_characters: int
    ) -> List[Dict[str, Optional[str]]]:
        if not self.settings.persist_conversations:
            return []
        key = self.normalize_session_id(session_id)
        with self._lock, self._db() as db:
            rows = db.execute(
                """
                SELECT role, content, name FROM conversation_messages
                WHERE session_id = ? ORDER BY id DESC LIMIT ?
                """,
                (key, max(1, int(max_messages))),
            ).fetchall()
        output: List[Dict[str, Optional[str]]] = []
        total = 0
        for row in reversed(rows):
            content = str(row["content"])
            if total + len(content) > max_characters and output:
                continue
            output.append({"role": str(row["role"]), "content": content, "name": row["name"]})
            total += len(content)
        return output

    def clear_conversation(self, session_id: str) -> bool:
        key = self.normalize_session_id(session_id)
        with self._lock, self._db() as db:
            cursor = db.execute("DELETE FROM conversation_sessions WHERE session_id = ?", (key,))
            return cursor.rowcount > 0

    def conversation_counts(self) -> Tuple[int, int]:
        with self._lock, self._db() as db:
            sessions = int(db.execute("SELECT COUNT(*) FROM conversation_sessions").fetchone()[0])
            messages = int(db.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0])
        return sessions, messages

    def clear_all_conversations(self) -> Tuple[int, int]:
        """Delete every persisted conversation without touching permanent memories."""
        with self._lock, self._db() as db:
            sessions = int(db.execute("SELECT COUNT(*) FROM conversation_sessions").fetchone()[0])
            messages = int(db.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0])
            db.execute("DELETE FROM conversation_sessions")
        if sessions or messages:
            self._audit(
                "conversations_cleared",
                None,
                {"sessions": sessions, "messages": messages},
            )
        return sessions, messages

    def cleanup_old_conversations(self) -> int:
        retention = self.settings.conversation_retention_days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention)).isoformat(timespec="seconds")
        with self._lock, self._db() as db:
            cursor = db.execute(
                "DELETE FROM conversation_sessions WHERE updated_at < ?", (cutoff,)
            )
            deleted = cursor.rowcount
        if deleted:
            self._audit("conversation_cleanup", None, {"sessions": deleted})
        return max(0, deleted)

    def recall_candidates(self, limit: int = 200) -> List[MemoryRecord]:
        with self._lock, self._db() as db:
            rows = db.execute(
                """
                SELECT * FROM memories
                ORDER BY pinned DESC, importance DESC, updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 1000)),),
            ).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def mark_accessed(self, memory_ids: Sequence[str]) -> None:
        ids = [value for value in dict.fromkeys(memory_ids) if value]
        if not ids:
            return
        now = utc_now_iso()
        placeholders = ",".join("?" for _ in ids)
        with self._lock, self._db() as db:
            db.execute(
                f"""
                UPDATE memories SET last_accessed_at = ?, access_count = access_count + 1
                WHERE id IN ({placeholders})
                """,
                [now, *ids],
            )

    def export_memories(self) -> Dict[str, Any]:
        items, _ = self.list_memories(limit=5000)
        return {
            "format": "freshy-memory-export-v1",
            "exported_at": utc_now_iso(),
            "settings": self.settings.model_dump(),
            "items": [
                {
                    "category": item.category,
                    "key": item.key,
                    "value": item.value,
                    "tags": item.tags,
                    "importance": item.importance,
                    "pinned": item.pinned,
                }
                for item in items
            ],
        }

    def audit_entries(self, limit: int = 100) -> List[MemoryAuditEntry]:
        with self._lock, self._db() as db:
            rows = db.execute(
                "SELECT * FROM memory_audit_log ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        output: List[MemoryAuditEntry] = []
        for row in rows:
            try:
                details = json.loads(str(row["details_json"] or "{}"))
            except json.JSONDecodeError:
                details = {}
            output.append(
                MemoryAuditEntry(
                    id=int(row["id"]),
                    action=str(row["action"]),
                    memory_id=row["memory_id"],
                    details=details if isinstance(details, dict) else {},
                    created_at=str(row["created_at"]),
                )
            )
        return output

    def _audit(self, action: str, memory_id: Optional[str], details: Dict[str, Any]) -> None:
        with self._lock, self._db() as db:
            db.execute(
                """
                INSERT INTO memory_audit_log(action, memory_id, details_json, created_at)
                VALUES(?, ?, ?, ?)
                """,
                (action, memory_id, json.dumps(details, ensure_ascii=False), utc_now_iso()),
            )
            db.execute(
                """
                DELETE FROM memory_audit_log
                WHERE id NOT IN (
                    SELECT id FROM memory_audit_log ORDER BY id DESC LIMIT 500
                )
                """
            )

    def _enforce_memory_limit(self) -> None:
        limit = self.settings.max_items
        with self._lock, self._db() as db:
            count = int(db.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            overflow = count - limit
            if overflow <= 0:
                return
            rows = db.execute(
                """
                SELECT id FROM memories WHERE pinned = 0
                ORDER BY importance ASC, COALESCE(last_accessed_at, created_at) ASC
                LIMIT ?
                """,
                (overflow,),
            ).fetchall()
            ids = [str(row["id"]) for row in rows]
            if not ids:
                return
            placeholders = ",".join("?" for _ in ids)
            db.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
        self._audit("pruned", None, {"count": len(ids)})
