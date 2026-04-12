"""Session store: persistent chat sessions and messages in SQLite."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from engram.stores.base import BaseStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class Session:
    id: str
    title: str
    created_at: str
    ontology_path: str | None = None
    last_message: str | None = None
    message_count: int = 0


@dataclass
class Message:
    id: str
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    created_at: str
    memories_used: list[dict] = field(default_factory=list)


class SessionStore(BaseStore):
    """SQLite store for chat sessions and messages."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                ontology_path TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                memories_used TEXT NOT NULL DEFAULT '[]'
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, created_at)
        """)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Store not initialized.")
        return self._conn

    def create_session(self, title: str = "New Chat", ontology_path: str | None = None) -> Session:
        session_id = _uuid()
        now = _now()
        self.conn.execute(
            "INSERT INTO sessions (id, title, created_at, ontology_path) VALUES (?, ?, ?, ?)",
            (session_id, title, now, ontology_path),
        )
        self.conn.commit()
        return Session(id=session_id, title=title, created_at=now, ontology_path=ontology_path)

    def list_sessions(self) -> list[Session]:
        rows = self.conn.execute("""
            SELECT s.id, s.title, s.created_at, s.ontology_path,
                   (SELECT content FROM messages WHERE session_id = s.id ORDER BY created_at DESC LIMIT 1) as last_message,
                   (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as message_count
            FROM sessions s
            ORDER BY s.created_at DESC
        """).fetchall()
        return [
            Session(
                id=r["id"], title=r["title"], created_at=r["created_at"],
                ontology_path=r["ontology_path"],
                last_message=r["last_message"], message_count=r["message_count"],
            )
            for r in rows
        ]

    def get_session(self, session_id: str) -> Session | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        count = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?", (session_id,)
        ).fetchone()["cnt"]
        return Session(
            id=row["id"], title=row["title"], created_at=row["created_at"],
            ontology_path=row["ontology_path"], message_count=count,
        )

    def update_session_title(self, session_id: str, title: str) -> None:
        self.conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ?", (title, session_id)
        )
        self.conn.commit()

    def delete_session(self, session_id: str) -> bool:
        cursor = self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        memories_used: list[dict] | None = None,
    ) -> Message:
        msg_id = _uuid()
        now = _now()
        memories = memories_used or []
        self.conn.execute(
            "INSERT INTO messages (id, session_id, role, content, created_at, memories_used) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, now, json.dumps(memories)),
        )
        self.conn.commit()
        return Message(
            id=msg_id, session_id=session_id, role=role,
            content=content, created_at=now, memories_used=memories,
        )

    def get_messages(self, session_id: str, limit: int = 100) -> list[Message]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [
            Message(
                id=r["id"], session_id=r["session_id"], role=r["role"],
                content=r["content"], created_at=r["created_at"],
                memories_used=json.loads(r["memories_used"]),
            )
            for r in rows
        ]

    def session_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()["cnt"]
