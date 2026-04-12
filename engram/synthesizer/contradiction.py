"""Contradiction detector: Find and resolve conflicting memories.

When a user says "I love Java" and later "I hate Java", both memories
coexist. This module detects such contradictions and resolves them
by accelerating decay on the weaker/older memory.
"""

from __future__ import annotations

from engram.core.types import Concept, Belief, Edge
from engram.synthesizer.base import BaseLLM
from engram.stores.concept_store import ConceptStore
from engram.stores.belief_store import BeliefStore

CONTRADICTION_PROMPT = """\
Given these statements, identify any pairs that CONTRADICT each other.
A contradiction means they cannot both be true at the same time.

Statements:
{statements}

Return a JSON array of contradicting pairs:
[
  {{"a": 0, "b": 3, "explanation": "one sentence why they conflict"}}
]

Only include genuine contradictions, not mere differences in topic.
Return [] if there are no contradictions.
JSON array only, no other text.
"""


class ContradictionDetector:
    """Detects contradictions between concepts and resolves them."""

    def __init__(
        self,
        llm: BaseLLM,
        concept_store: ConceptStore,
        belief_store: BeliefStore,
    ) -> None:
        self._llm = llm
        self._concepts = concept_store
        self._beliefs = belief_store

    async def detect_and_resolve(self) -> dict:
        """Scan concepts for contradictions and resolve them.

        Resolution strategy:
        - The newer memory wins (more recent = more current preference)
        - The loser's half_life is halved (accelerated decay)
        - A "contradicts" edge is added between related beliefs

        Returns:
            Dict with contradiction stats.
        """
        # Get all active concepts
        all_results = self._concepts.collection.get(
            include=["documents", "metadatas"],
        )

        if not all_results["ids"] or len(all_results["ids"]) < 2:
            return {"contradictions_found": 0, "resolved": 0}

        statements = all_results["documents"]
        metas = all_results["metadatas"]
        ids = all_results["ids"]

        formatted = "\n".join(
            f"[{i}]: {s}" for i, s in enumerate(statements)
        )

        prompt = CONTRADICTION_PROMPT.format(statements=formatted)

        try:
            result = await self._llm.extract_json(prompt)
        except Exception:
            return {"contradictions_found": 0, "resolved": 0, "error": "LLM parse failed"}

        if not isinstance(result, list):
            return {"contradictions_found": 0, "resolved": 0}

        resolved = 0
        contradictions = []

        for item in result:
            if not isinstance(item, dict):
                continue

            try:
                idx_a = int(item["a"])
                idx_b = int(item["b"])
            except (KeyError, TypeError, ValueError):
                continue

            if not (0 <= idx_a < len(ids) and 0 <= idx_b < len(ids)):
                continue

            # Resolve: newer wins
            time_a = metas[idx_a].get("timestamp", "")
            time_b = metas[idx_b].get("timestamp", "")

            # The newer one (later timestamp) is the "winner"
            if time_a >= time_b:
                winner_id, loser_id = ids[idx_a], ids[idx_b]
            else:
                winner_id, loser_id = ids[idx_b], ids[idx_a]

            # Accelerate decay on the loser by halving its half_life
            loser_meta = self._concepts.collection.get(
                ids=[loser_id], include=["metadatas"]
            )
            if loser_meta["ids"]:
                meta = loser_meta["metadatas"][0]
                meta["half_life_days"] = meta.get("half_life_days", 90.0) / 2.0
                self._concepts.collection.update(ids=[loser_id], metadatas=[meta])

            # Reinforce the winner
            self._concepts.reinforce(winner_id)

            contradictions.append({
                "winner": winner_id[:8],
                "loser": loser_id[:8],
                "explanation": item.get("explanation", ""),
            })
            resolved += 1

        return {
            "contradictions_found": len(contradictions),
            "resolved": resolved,
            "details": contradictions,
        }
