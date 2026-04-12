"""Extractor: L1 Episodes → L2 Concepts.

Takes raw episodic memories and compresses them into
conceptual summaries with semantic embeddings.
"""

from __future__ import annotations

from engram.core.types import Episode, Concept
from engram.synthesizer.base import BaseLLM

EXTRACTION_PROMPT = """\
You are a memory compression engine. Given a batch of raw memory episodes,
extract the key concepts — factual claims, preferences, decisions, or patterns.

Rules:
- Each concept should be a standalone, self-contained statement.
- Merge overlapping episodes into a single concept.
- Preserve specifics (names, tools, dates) when they matter.
- Discard filler, greetings, and ephemeral chatter.
- Return 1-10 concepts depending on how much substance is in the input.

Input episodes:
{episodes}

Respond with a JSON array of objects, each with:
- "summary": a concise concept statement (1-2 sentences)
- "source_indices": list of episode indices (0-based) this concept came from
- "confidence": float 0.0-1.0, how certain this concept is based on the evidence

Example response:
[
  {{"summary": "User prefers Python for backend development due to readability", "source_indices": [0, 2], "confidence": 0.9}},
  {{"summary": "Project uses PostgreSQL as the primary database", "source_indices": [1], "confidence": 0.95}}
]

Return ONLY the JSON array, no other text.
"""


class Extractor:
    """Compresses L1 Episodes into L2 Concepts using an LLM."""

    def __init__(self, llm: BaseLLM) -> None:
        self._llm = llm

    async def extract(self, episodes: list[Episode]) -> list[Concept]:
        """Extract concepts from a batch of episodes.

        Args:
            episodes: List of raw episodic memories to compress.

        Returns:
            List of new Concept objects distilled from the episodes.
        """
        if not episodes:
            return []

        # Format episodes for the prompt
        formatted = "\n".join(
            f"[{i}] ({ep.source}, {ep.timestamp.strftime('%Y-%m-%d %H:%M')}): {ep.content}"
            for i, ep in enumerate(episodes)
        )

        prompt = EXTRACTION_PROMPT.format(episodes=formatted)
        raw_concepts = await self._llm.extract_json(prompt)

        if not isinstance(raw_concepts, list):
            return []

        concepts = []
        for item in raw_concepts:
            if not isinstance(item, dict) or "summary" not in item:
                continue

            source_indices = item.get("source_indices", [])
            source_ids = [
                episodes[i].id
                for i in source_indices
                if isinstance(i, int) and 0 <= i < len(episodes)
            ]

            concept = Concept(
                summary=item["summary"],
                source_episode_ids=source_ids,
                confidence=min(1.0, max(0.0, float(item.get("confidence", 0.8)))),
            )
            concepts.append(concept)

        return concepts
