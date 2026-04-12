"""L2.5 Fact Store: structured triples in SQLite + ChromaDB for semantic search."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import chromadb

from engram.core.types import Fact
from engram.core.decay import compute_confidence, should_garbage_collect
from engram.stores.base import BaseStore


class FactStore(BaseStore):
    """SQLite + ChromaDB store for structured fact triples (L2.5).

    SQLite provides exact triple queries (subject, predicate, object).
    ChromaDB provides semantic search over the triple text representation.
    """

    COLLECTION_NAME = "facts"

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
            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                subject_type TEXT NOT NULL DEFAULT '',
                object_type TEXT NOT NULL DEFAULT '',
                source_concept_ids TEXT NOT NULL DEFAULT '[]',
                timestamp TEXT NOT NULL,
                initial_confidence REAL NOT NULL DEFAULT 0.85,
                half_life_days REAL NOT NULL DEFAULT 180.0,
                reinforcement_count INTEGER NOT NULL DEFAULT 0,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_facts_predicate ON facts(predicate)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_facts_object ON facts(object)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_facts_spo
            ON facts(subject, predicate, object)
        """)
        self._conn.commit()

        # ChromaDB
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
            raise RuntimeError("Store not initialized.")
        return self._conn

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            raise RuntimeError("Store not initialized.")
        return self._collection

    def add(self, fact: Fact) -> Fact:
        """Insert a fact into both SQLite and ChromaDB."""
        self.conn.execute(
            """INSERT OR REPLACE INTO facts
               (id, subject, predicate, object, subject_type, object_type,
                source_concept_ids, timestamp, initial_confidence, half_life_days, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fact.id,
                fact.subject,
                fact.predicate,
                fact.object,
                fact.subject_type,
                fact.object_type,
                json.dumps(fact.source_concept_ids),
                fact.timestamp.isoformat(),
                fact.confidence,
                fact.half_life_days,
                json.dumps(fact.metadata),
            ),
        )
        self.conn.commit()

        # ChromaDB: index the human readable triple text
        self.collection.upsert(
            ids=[fact.id],
            documents=[fact.triple_text],
            metadatas=[{
                "subject": fact.subject,
                "predicate": fact.predicate,
                "object": fact.object,
                "timestamp": fact.timestamp.isoformat(),
            }],
        )

        return fact

    def get(self, fact_id: str) -> Fact | None:
        """Retrieve a fact by ID."""
        row = self.conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_fact(row)

    def query(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,
        min_confidence: float = 0.05,
        now: datetime | None = None,
    ) -> list[Fact]:
        """Exact triple query. Any combination of subject/predicate/object."""
        if now is None:
            now = datetime.now(timezone.utc)

        conditions = []
        params = []
        if subject is not None:
            conditions.append("subject = ?")
            params.append(subject)
        if predicate is not None:
            conditions.append("predicate = ?")
            params.append(predicate)
        if object is not None:
            conditions.append("object = ?")
            params.append(object)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self.conn.execute(
            f"SELECT * FROM facts WHERE {where} ORDER BY timestamp DESC", params
        ).fetchall()

        results = []
        for row in rows:
            fact = self._row_to_fact(row)
            conf = compute_confidence(
                initial_confidence=row["initial_confidence"],
                created_at=fact.timestamp,
                half_life=fact.half_life,
                reinforcement_count=row["reinforcement_count"],
                now=now,
            )
            if conf >= min_confidence:
                fact.confidence = conf
                results.append(fact)

        return results

    def query_by_type(
        self,
        subject_type: str | None = None,
        predicate: str | None = None,
        object_type: str | None = None,
        min_confidence: float = 0.05,
        now: datetime | None = None,
    ) -> list[Fact]:
        """Query facts by entity types."""
        if now is None:
            now = datetime.now(timezone.utc)

        conditions = []
        params = []
        if subject_type is not None:
            conditions.append("subject_type = ?")
            params.append(subject_type)
        if predicate is not None:
            conditions.append("predicate = ?")
            params.append(predicate)
        if object_type is not None:
            conditions.append("object_type = ?")
            params.append(object_type)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self.conn.execute(
            f"SELECT * FROM facts WHERE {where} ORDER BY timestamp DESC", params
        ).fetchall()

        results = []
        for row in rows:
            fact = self._row_to_fact(row)
            conf = compute_confidence(
                initial_confidence=row["initial_confidence"],
                created_at=fact.timestamp,
                half_life=fact.half_life,
                reinforcement_count=row["reinforcement_count"],
                now=now,
            )
            if conf >= min_confidence:
                fact.confidence = conf
                results.append(fact)

        return results

    def query_similar(
        self,
        query_text: str,
        n_results: int = 10,
        min_confidence: float = 0.05,
        now: datetime | None = None,
    ) -> list[tuple[Fact, float]]:
        """Semantic search over fact triple text."""
        if now is None:
            now = datetime.now(timezone.utc)

        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results * 2,
            include=["distances"],
        )

        output = []
        for i in range(len(results["ids"][0])):
            fact_id = results["ids"][0][i]
            fact = self.get(fact_id)
            if fact is None:
                continue

            row = self.conn.execute(
                "SELECT reinforcement_count FROM facts WHERE id = ?", (fact_id,)
            ).fetchone()

            conf = compute_confidence(
                initial_confidence=fact.confidence,
                created_at=fact.timestamp,
                half_life=fact.half_life,
                reinforcement_count=row["reinforcement_count"] if row else 0,
                now=now,
            )

            if conf >= min_confidence:
                fact.confidence = conf
                distance = results["distances"][0][i]
                similarity = 1.0 - distance
                output.append((fact, similarity))

            if len(output) >= n_results:
                break

        return output

    def find_contradictions(self, fact: Fact) -> list[Fact]:
        """Find facts that contradict the given fact.

        A contradiction is: same subject, same or opposite predicate, different object.
        """
        # Same subject, same predicate, different object
        same_pred = self.query(subject=fact.subject, predicate=fact.predicate)
        contradictions = [f for f in same_pred if f.object != fact.object and f.id != fact.id]

        # Known opposite predicates
        opposites = {
            "inhibits": "activates",
            "activates": "inhibits",
            "upregulates": "downregulates",
            "downregulates": "upregulates",
            "prefers": "dislikes",
            "dislikes": "prefers",
        }

        opposite_pred = opposites.get(fact.predicate)
        if opposite_pred:
            opp = self.query(subject=fact.subject, predicate=opposite_pred, object=fact.object)
            contradictions.extend(opp)

        return contradictions

    def reinforce(self, fact_id: str) -> None:
        """Increment reinforcement count."""
        self.conn.execute(
            "UPDATE facts SET reinforcement_count = reinforcement_count + 1 WHERE id = ?",
            (fact_id,),
        )
        self.conn.commit()

    def delete(self, fact_id: str) -> bool:
        """Delete a fact by ID."""
        cursor = self.conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        self.conn.commit()
        try:
            self.collection.delete(ids=[fact_id])
        except Exception:
            pass
        return cursor.rowcount > 0

    def garbage_collect(self, threshold: float = 0.05, now: datetime | None = None) -> int:
        """Remove facts below confidence threshold."""
        if now is None:
            now = datetime.now(timezone.utc)

        rows = self.conn.execute("SELECT * FROM facts").fetchall()
        to_delete = []

        for row in rows:
            conf = compute_confidence(
                initial_confidence=row["initial_confidence"],
                created_at=datetime.fromisoformat(row["timestamp"]),
                half_life=timedelta(days=row["half_life_days"]),
                reinforcement_count=row["reinforcement_count"],
                now=now,
            )
            if should_garbage_collect(conf, threshold):
                to_delete.append(row["id"])

        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            self.conn.execute(f"DELETE FROM facts WHERE id IN ({placeholders})", to_delete)
            self.conn.commit()
            try:
                self.collection.delete(ids=to_delete)
            except Exception:
                pass

        return len(to_delete)

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM facts").fetchone()
        return row["cnt"]

    def _row_to_fact(self, row: sqlite3.Row) -> Fact:
        return Fact(
            id=row["id"],
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            subject_type=row["subject_type"],
            object_type=row["object_type"],
            source_concept_ids=json.loads(row["source_concept_ids"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            confidence=row["initial_confidence"],
            half_life_days=row["half_life_days"],
            metadata=json.loads(row["metadata"]),
        )
