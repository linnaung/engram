"""L1 Episode Store — raw memories in SQLite + ChromaDB for semantic search."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import chromadb

from engram.core.types import Episode
from engram.core.decay import compute_confidence, should_garbage_collect
from engram.stores.base import BaseStore


class EpisodeStore(BaseStore):
    """SQLite + ChromaDB store for raw episodic memories (L1).

    SQLite is the source of truth for metadata and decay.
    ChromaDB provides the semantic vector index for similarity search.
    """

    COLLECTION_NAME = "episodes"

    def __init__(self, db_path: Path, chroma_dir: Path) -> None:
        self.db_path = db_path
        self.chroma_dir = chroma_dir
        self._conn: sqlite3.Connection | None = None
        self._chroma_client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def initialize(self) -> None:
        # SQLite
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'conversation',
                timestamp TEXT NOT NULL,
                initial_confidence REAL NOT NULL DEFAULT 1.0,
                half_life_days REAL NOT NULL DEFAULT 7.0,
                reinforcement_count INTEGER NOT NULL DEFAULT 0,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_episodes_timestamp
            ON episodes(timestamp)
        """)
        self._conn.commit()

        # ChromaDB for semantic search
        self._chroma_client = chromadb.PersistentClient(path=str(self.chroma_dir))
        self._collection = self._chroma_client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
        self._chroma_client = None
        self._collection = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")
        return self._conn

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")
        return self._collection

    def add(self, episode: Episode) -> Episode:
        """Insert a new episode into both SQLite and ChromaDB."""
        # SQLite (source of truth)
        self.conn.execute(
            """INSERT INTO episodes
               (id, content, source, timestamp, initial_confidence, half_life_days, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                episode.id,
                episode.content,
                episode.source,
                episode.timestamp.isoformat(),
                episode.confidence,
                episode.half_life_days,
                json.dumps(episode.metadata),
            ),
        )
        self.conn.commit()

        # ChromaDB (semantic index)
        self.collection.add(
            ids=[episode.id],
            documents=[episode.content],
            metadatas=[{
                "source": episode.source,
                "timestamp": episode.timestamp.isoformat(),
            }],
        )

        return episode

    def get(self, episode_id: str) -> Episode | None:
        """Retrieve a single episode by ID."""
        row = self.conn.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_episode(row)

    def query_similar(
        self,
        query_text: str,
        n_results: int = 10,
        min_confidence: float = 0.05,
        now: datetime | None = None,
    ) -> list[tuple[Episode, float]]:
        """Find episodes semantically similar to query text.

        Returns list of (episode, similarity_score) tuples,
        filtered by current confidence after decay.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results * 2,  # over-fetch for decay filtering
            include=["distances"],
        )

        output = []
        for i in range(len(results["ids"][0])):
            episode_id = results["ids"][0][i]
            episode = self.get(episode_id)
            if episode is None:
                continue

            row = self.conn.execute(
                "SELECT reinforcement_count FROM episodes WHERE id = ?",
                (episode_id,),
            ).fetchone()

            current_conf = compute_confidence(
                initial_confidence=episode.confidence,
                created_at=episode.timestamp,
                half_life=episode.half_life,
                reinforcement_count=row["reinforcement_count"] if row else 0,
                now=now,
            )

            if current_conf >= min_confidence:
                episode.confidence = current_conf
                distance = results["distances"][0][i]
                similarity = 1.0 - distance
                output.append((episode, similarity))

            if len(output) >= n_results:
                break

        return output

    def list_active(
        self,
        min_confidence: float = 0.05,
        limit: int = 100,
        now: datetime | None = None,
    ) -> list[Episode]:
        """List episodes whose current confidence is above the threshold."""
        if now is None:
            now = datetime.now(timezone.utc)

        rows = self.conn.execute(
            "SELECT * FROM episodes ORDER BY timestamp DESC"
        ).fetchall()

        results = []
        for row in rows:
            episode = self._row_to_episode(row)
            current_conf = compute_confidence(
                initial_confidence=episode.confidence,
                created_at=episode.timestamp,
                half_life=episode.half_life,
                reinforcement_count=row["reinforcement_count"],
                now=now,
            )
            if current_conf >= min_confidence:
                episode.confidence = current_conf
                results.append(episode)
            if len(results) >= limit:
                break

        return results

    def reinforce(self, episode_id: str) -> None:
        """Increment reinforcement count for an episode."""
        self.conn.execute(
            "UPDATE episodes SET reinforcement_count = reinforcement_count + 1 WHERE id = ?",
            (episode_id,),
        )
        self.conn.commit()

    def delete(self, episode_id: str) -> bool:
        """Delete an episode from both SQLite and ChromaDB."""
        cursor = self.conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
        self.conn.commit()

        try:
            self.collection.delete(ids=[episode_id])
        except Exception:
            pass

        return cursor.rowcount > 0

    def garbage_collect(self, threshold: float = 0.05, now: datetime | None = None) -> int:
        """Remove episodes that have decayed below the confidence threshold."""
        if now is None:
            now = datetime.now(timezone.utc)

        rows = self.conn.execute("SELECT * FROM episodes").fetchall()
        to_delete = []

        for row in rows:
            current_conf = compute_confidence(
                initial_confidence=row["initial_confidence"],
                created_at=datetime.fromisoformat(row["timestamp"]),
                half_life=timedelta(days=row["half_life_days"]),
                reinforcement_count=row["reinforcement_count"],
                now=now,
            )
            if should_garbage_collect(current_conf, threshold):
                to_delete.append(row["id"])

        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            self.conn.execute(
                f"DELETE FROM episodes WHERE id IN ({placeholders})", to_delete
            )
            self.conn.commit()

            # Also remove from ChromaDB
            try:
                self.collection.delete(ids=to_delete)
            except Exception:
                pass

        return len(to_delete)

    def count(self) -> int:
        """Total number of episodes."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM episodes").fetchone()
        return row["cnt"]

    def _row_to_episode(self, row: sqlite3.Row) -> Episode:
        return Episode(
            id=row["id"],
            content=row["content"],
            source=row["source"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            confidence=row["initial_confidence"],
            half_life_days=row["half_life_days"],
            metadata=json.loads(row["metadata"]),
        )
