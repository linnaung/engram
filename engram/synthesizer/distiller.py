"""Distiller: L2 Concepts → L3 Beliefs + Graph Edges.

Synthesizes abstract principles from concept patterns
and identifies relationships between beliefs.

Uses a two-pass approach:
  Pass 1: Extract beliefs from concepts
  Pass 2: Identify edges between all beliefs (new + existing)
"""

from __future__ import annotations

from engram.core.types import Concept, Belief, Edge
from engram.synthesizer.base import BaseLLM

BELIEF_PROMPT = """\
Given these factual observations about a user, extract 1-5 higher-level principles.

A principle is NOT a fact. It's an abstraction:
  Fact: "User uses Python" → Principle: "User values readability over raw performance"
  Fact: "User dislikes monoliths" → Principle: "User favors composability and simplicity"

Observations:
{concepts}

Already known principles (do NOT duplicate these):
{existing_beliefs}

Return a JSON array:
[
  {{"principle": "one sentence", "source_indices": [0, 2], "confidence": 0.8}}
]

JSON array only, no other text.
"""

EDGE_PROMPT = """\
Given these beliefs about a user, identify relationships between them.

Beliefs:
{beliefs}

For each pair that has a meaningful relationship, output an edge.
Relation types:
- "supports": A reinforces or provides evidence for B
- "contradicts": A conflicts with or undermines B
- "reminds_of": A is thematically analogous to B (different domain, same pattern)

Return a JSON array of edges:
[
  {{"source": 0, "target": 1, "relation": "supports", "weight": 0.8}},
  {{"source": 2, "target": 0, "relation": "reminds_of", "weight": 0.6}}
]

source and target are belief indices from the list above.
weight is 0.0-1.0 (how strong the relationship is).
Return at least 1 edge. Return [] ONLY if there are fewer than 2 beliefs.
JSON array only, no other text.
"""


class Distiller:
    """Synthesizes L3 Beliefs from L2 Concepts using an LLM.

    Two-pass approach for better results with smaller models:
      Pass 1: Concepts → Beliefs (simpler task)
      Pass 2: All Beliefs → Edges (focused on relationships only)
    """

    def __init__(self, llm: BaseLLM) -> None:
        self._llm = llm

    async def distill(
        self,
        concepts: list[Concept],
        existing_beliefs: list[Belief] | None = None,
    ) -> tuple[list[Belief], list[Edge]]:
        """Distill beliefs and relationships from concepts.

        Args:
            concepts: List of L2 concepts to synthesize from.
            existing_beliefs: Current beliefs to avoid duplication
                and to allow cross-referencing in edges.

        Returns:
            Tuple of (new_beliefs, new_edges).
        """
        if not concepts:
            return [], []

        existing = existing_beliefs or []

        # Pass 1: Extract beliefs
        new_beliefs = await self._extract_beliefs(concepts, existing)

        # Pass 2: Find edges between ALL beliefs (new + existing)
        all_beliefs = existing + new_beliefs
        new_edges = await self._find_edges(all_beliefs) if len(all_beliefs) >= 2 else []

        return new_beliefs, new_edges

    async def _extract_beliefs(
        self,
        concepts: list[Concept],
        existing_beliefs: list[Belief],
    ) -> list[Belief]:
        """Pass 1: Extract beliefs from concepts."""
        formatted_concepts = "\n".join(
            f"[{i}]: {c.summary}"
            for i, c in enumerate(concepts)
        )

        formatted_existing = "\n".join(
            f"- {b.principle}"
            for b in existing_beliefs
        ) if existing_beliefs else "(none yet)"

        prompt = BELIEF_PROMPT.format(
            concepts=formatted_concepts,
            existing_beliefs=formatted_existing,
        )

        result = await self._llm.extract_json(prompt)
        if not isinstance(result, list):
            return []

        beliefs: list[Belief] = []
        for item in result:
            if not isinstance(item, dict) or "principle" not in item:
                continue

            source_indices = item.get("source_indices", [])
            source_ids = [
                concepts[i].id
                for i in source_indices
                if isinstance(i, int) and 0 <= i < len(concepts)
            ]

            belief = Belief(
                principle=item["principle"],
                supporting_concept_ids=source_ids,
                confidence=min(1.0, max(0.0, float(item.get("confidence", 0.7)))),
            )
            beliefs.append(belief)

        return beliefs

    async def _find_edges(self, all_beliefs: list[Belief]) -> list[Edge]:
        """Pass 2: Find relationships between all beliefs."""
        formatted = "\n".join(
            f"[{i}]: {b.principle}"
            for i, b in enumerate(all_beliefs)
        )

        prompt = EDGE_PROMPT.format(beliefs=formatted)

        try:
            result = await self._llm.extract_json(prompt)
        except Exception:
            return []

        if not isinstance(result, list):
            return []

        edges: list[Edge] = []
        for item in result:
            if not isinstance(item, dict):
                continue

            try:
                src_idx = int(item.get("source", -1))
                tgt_idx = int(item.get("target", -1))
            except (TypeError, ValueError):
                continue

            if (
                0 <= src_idx < len(all_beliefs)
                and 0 <= tgt_idx < len(all_beliefs)
                and src_idx != tgt_idx
            ):
                edge = Edge(
                    source_id=all_beliefs[src_idx].id,
                    target_id=all_beliefs[tgt_idx].id,
                    relation=item.get("relation", "related"),
                    weight=min(1.0, max(0.0, float(item.get("weight", 0.5)))),
                )
                edges.append(edge)

        return edges
