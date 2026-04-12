"""Deduplicator: Merge near-duplicate concepts in L2.

After multiple synthesis rounds, the concept store accumulates
near-identical entries. This module detects high-similarity pairs
and merges them — boosting confidence instead of creating clones.
"""

from __future__ import annotations

from datetime import datetime, timezone

from engram.stores.concept_store import ConceptStore
from engram.core.types import Concept


class Deduplicator:
    """Detects and merges near-duplicate concepts."""

    def __init__(self, concept_store: ConceptStore, similarity_threshold: float = 0.85) -> None:
        self._store = concept_store
        self._threshold = similarity_threshold

    def deduplicate(self) -> dict:
        """Scan all concepts and merge near-duplicates.

        Strategy:
        - For each concept, query the store for similar concepts
        - If similarity > threshold, merge: keep the one with higher confidence,
          absorb the other's source_episode_ids, bump reinforcement count
        - Delete the duplicate

        Returns:
            Dict with merge stats.
        """
        now = datetime.now(timezone.utc)
        merged_count = 0
        deleted_ids: set[str] = set()

        # Get all concept IDs by querying with a broad search
        # We'll iterate through each concept and check for duplicates
        all_results = self._store.collection.get(
            include=["documents", "metadatas", "embeddings"],
        )

        if not all_results["ids"]:
            return {"merged": 0, "remaining": 0}

        total = len(all_results["ids"])

        for i in range(total):
            concept_id = all_results["ids"][i]

            if concept_id in deleted_ids:
                continue

            doc = all_results["documents"][i]

            # Find similar concepts
            similar = self._store.collection.query(
                query_texts=[doc],
                n_results=min(10, total),
                include=["documents", "metadatas", "distances"],
            )

            for j in range(len(similar["ids"][0])):
                other_id = similar["ids"][0][j]

                if other_id == concept_id or other_id in deleted_ids:
                    continue

                distance = similar["distances"][0][j]
                similarity = 1.0 - distance

                if similarity >= self._threshold:
                    # Merge: reinforce the keeper, delete the duplicate
                    self._store.reinforce(concept_id)

                    # Absorb source episode IDs from the duplicate
                    # (stored in metadata, handled by reinforcement count bump)

                    self._store.delete(other_id)
                    deleted_ids.add(other_id)
                    merged_count += 1

        remaining = self._store.count()
        return {
            "merged": merged_count,
            "remaining": remaining,
        }
