"""Fact Extractor: L2 Concepts -> L2.5 Facts (structured triples).

Takes concept summaries and extracts structured (subject, predicate, object) triples.
When a ContextProvider is available, entities are resolved and typed,
predicates are validated, and aliases are normalized.
"""

from __future__ import annotations

from engram.core.types import Concept, Fact
from engram.synthesizer.base import BaseLLM
from engram.context.provider import ContextProvider

FACT_EXTRACTION_PROMPT = """\
Extract structured facts from these statements as (subject, predicate, object) triples.

Rules:
  Each fact must be a concrete assertion, not an opinion or abstraction.
  Good: {{"subject": "p53", "predicate": "inhibits", "object": "MDM2"}}
  Good: {{"subject": "User", "predicate": "prefers", "object": "Python"}}
  Bad:  {{"subject": "User", "predicate": "values", "object": "simplicity"}} (too abstract, that's a belief)
  Use simple, lowercase predicates: "prefers", "knows", "uses", "inhibits", "treats"

Statements:
{concepts}

{context_hint}

Return a JSON array:
[
  {{"subject": "...", "predicate": "...", "object": "...", "source_index": 0, "confidence": 0.9}}
]

Return ONLY the JSON array.
"""


class FactExtractor:
    """Extracts structured triples from concepts, optionally grounded by ontology."""

    def __init__(self, llm: BaseLLM, context: ContextProvider | None = None) -> None:
        self._llm = llm
        self._context = context

    async def extract(self, concepts: list[Concept]) -> list[Fact]:
        """Extract facts from a batch of concepts.

        If a ContextProvider is set, entities are resolved to canonical names,
        typed, and predicates are validated.
        """
        if not concepts:
            return []

        formatted = "\n".join(
            f"[{i}]: {c.summary}"
            for i, c in enumerate(concepts)
        )

        context_hint = ""
        if self._context:
            types = ", ".join(self._context.list_types()[:15])
            preds = ", ".join(self._context.list_predicates()[:15])
            context_hint = (
                f"Known entity types: {types}\n"
                f"Known predicates: {preds}\n"
                "Use these when they fit the data."
            )

        prompt = FACT_EXTRACTION_PROMPT.format(
            concepts=formatted,
            context_hint=context_hint,
        )

        # Try up to 2 attempts (small models are inconsistent with JSON)
        result = None
        for _attempt in range(2):
            try:
                result = await self._llm.extract_json(prompt)
                if isinstance(result, list):
                    break
            except Exception:
                continue

        if not isinstance(result, list):
            return []

        facts = []
        for item in result:
            if not isinstance(item, dict):
                continue

            subject = str(item.get("subject", "")).strip()
            predicate = str(item.get("predicate", "")).strip()
            obj = str(item.get("object", "")).strip()

            if not subject or not predicate or not obj:
                continue

            source_idx = item.get("source_index")
            source_ids = []
            if isinstance(source_idx, int) and 0 <= source_idx < len(concepts):
                source_ids = [concepts[source_idx].id]

            # Ground against ontology if available
            subject_type = ""
            object_type = ""

            if self._context:
                subject, subject_type = self._resolve(subject)
                obj, object_type = self._resolve(obj)

                # Validate predicate domain/range
                if subject_type and object_type:
                    if not self._context.validate_triple(subject_type, predicate, object_type):
                        continue  # Skip invalid triples

            fact = Fact(
                subject=subject,
                predicate=predicate,
                object=obj,
                subject_type=subject_type,
                object_type=object_type,
                source_concept_ids=source_ids,
                confidence=min(1.0, max(0.0, float(item.get("confidence", 0.8)))),
            )
            facts.append(fact)

        return facts

    def _resolve(self, text: str) -> tuple[str, str]:
        """Resolve text to (canonical_name, type) via the context provider."""
        if not self._context:
            return text, ""

        entity = self._context.resolve_entity(text)
        if entity:
            return entity.canonical, entity.type
        return text, ""
