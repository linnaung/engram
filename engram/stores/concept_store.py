"""L2 Concept Store — compressed memories in ChromaDB with vector search."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import chromadb

from engram.core.types import Concept
from engram.core.decay import compute_confidence
from engram.stores.base import BaseStore


class ConceptStore(BaseStore):
    """ChromaDB-backed store for conceptual memories (L2).

    Concepts are compressed summaries of episode clusters.
    They carry vector embeddings for semantic similarity search.
    """

    COLLECTION_NAME = "concepts"

    def __init__(self, persist_dir: Path) -> None:
        self.persist_dir = persist_dir
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def initialize(self) -> None:
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def close(self) -> None:
        self._client = None
        self._collection = None

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")
        return self._collection

    def add(self, concept: Concept) -> Concept:
        """Insert a new concept with its embedding."""
        metadata = {
            "summary": concept.summary,
            "timestamp": concept.timestamp.isoformat(),
            "initial_confidence": concept.confidence,
            "half_life_days": concept.half_life_days,
            "reinforcement_count": concept.reinforcement_count,
            "source_episode_ids": json.dumps(concept.source_episode_ids),
            "extra": json.dumps(concept.metadata),
        }

        kwargs: dict = {
            "ids": [concept.id],
            "documents": [concept.summary],
            "metadatas": [metadata],
        }

        # Use provided embedding if available, otherwise let ChromaDB's
        # default embedding function handle it
        if concept.embedding:
            kwargs["embeddings"] = [concept.embedding]

        self.collection.add(**kwargs)
        return concept

    def get(self, concept_id: str) -> Concept | None:
        """Retrieve a single concept by ID."""
        result = self.collection.get(ids=[concept_id], include=["documents", "metadatas", "embeddings"])
        if not result["ids"]:
            return None
        return self._result_to_concept(result, 0)

    def query_similar(
        self,
        query_text: str,
        n_results: int = 10,
        min_confidence: float = 0.05,
        now: datetime | None = None,
    ) -> list[tuple[Concept, float]]:
        """Find concepts semantically similar to query text.

        Returns list of (concept, similarity_score) tuples,
        filtered by current confidence after decay.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results * 2,  # over-fetch to account for decay filtering
            include=["documents", "metadatas", "embeddings", "distances"],
        )

        output = []
        for i in range(len(results["ids"][0])):
            concept = self._result_to_concept_from_query(results, i)
            meta = results["metadatas"][0][i]

            current_conf = compute_confidence(
                initial_confidence=meta["initial_confidence"],
                created_at=datetime.fromisoformat(meta["timestamp"]),
                half_life=concept.half_life,
                reinforcement_count=meta["reinforcement_count"],
                now=now,
            )

            if current_conf >= min_confidence:
                concept.confidence = current_conf
                # ChromaDB returns distances; convert to similarity
                distance = results["distances"][0][i]
                similarity = 1.0 - distance  # cosine distance → similarity
                output.append((concept, similarity))

            if len(output) >= n_results:
                break

        return output

    def reinforce(self, concept_id: str) -> None:
        """Increment reinforcement count for a concept."""
        result = self.collection.get(ids=[concept_id], include=["metadatas"])
        if not result["ids"]:
            return
        meta = result["metadatas"][0]
        meta["reinforcement_count"] = meta.get("reinforcement_count", 0) + 1
        self.collection.update(ids=[concept_id], metadatas=[meta])

    def delete(self, concept_id: str) -> bool:
        """Delete a concept by ID."""
        try:
            self.collection.delete(ids=[concept_id])
            return True
        except Exception:
            return False

    def count(self) -> int:
        """Total number of concepts."""
        return self.collection.count()

    def _result_to_concept(self, result: dict, idx: int) -> Concept:
        meta = result["metadatas"][idx]
        raw_embedding = result["embeddings"][idx] if result.get("embeddings") else None
        embedding = list(raw_embedding) if raw_embedding is not None else []
        return Concept(
            id=result["ids"][idx],
            summary=result["documents"][idx],
            embedding=embedding,
            source_episode_ids=json.loads(meta.get("source_episode_ids", "[]")),
            timestamp=datetime.fromisoformat(meta["timestamp"]),
            confidence=meta["initial_confidence"],
            half_life_days=meta["half_life_days"],
            reinforcement_count=meta.get("reinforcement_count", 0),
            metadata=json.loads(meta.get("extra", "{}")),
        )

    def _result_to_concept_from_query(self, results: dict, idx: int) -> Concept:
        meta = results["metadatas"][0][idx]
        raw_embedding = results["embeddings"][0][idx] if results.get("embeddings") else None
        embedding = list(raw_embedding) if raw_embedding is not None else []
        return Concept(
            id=results["ids"][0][idx],
            summary=results["documents"][0][idx],
            embedding=embedding,
            source_episode_ids=json.loads(meta.get("source_episode_ids", "[]")),
            timestamp=datetime.fromisoformat(meta["timestamp"]),
            confidence=meta["initial_confidence"],
            half_life_days=meta["half_life_days"],
            reinforcement_count=meta.get("reinforcement_count", 0),
            metadata=json.loads(meta.get("extra", "{}")),
        )
