"""Hybrid retrieval mixer: combines vector, graph, fact, and recency signals.

Blends four independent signals into a single ranked list:
  vector similarity (50%), graph traversal (20%), fact triples (15%), recency (15%).
"""

from __future__ import annotations

from datetime import datetime, timezone

from engram.core.types import RecallResult, Belief
from engram.core.decay import compute_confidence
from engram.stores.episode_store import EpisodeStore
from engram.stores.concept_store import ConceptStore
from engram.stores.fact_store import FactStore
from engram.stores.belief_store import BeliefStore


class RetrievalMixer:
    """Blends vector similarity, graph traversal, facts, and recency into unified recall."""

    def __init__(
        self,
        episode_store: EpisodeStore,
        concept_store: ConceptStore,
        fact_store: FactStore,
        belief_store: BeliefStore,
        vector_weight: float = 0.50,
        graph_weight: float = 0.20,
        fact_weight: float = 0.15,
        recency_weight: float = 0.15,
    ) -> None:
        self.episodes = episode_store
        self.concepts = concept_store
        self.facts = fact_store
        self.beliefs = belief_store
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight
        self.fact_weight = fact_weight
        self.recency_weight = recency_weight

    def recall(
        self,
        query: str,
        top_k: int = 10,
        min_confidence: float = 0.05,
        reinforce: bool = True,
        now: datetime | None = None,
    ) -> list[RecallResult]:
        """Hybrid recall across all four memory layers."""
        if now is None:
            now = datetime.now(timezone.utc)

        candidates: dict[str, RecallResult] = {}

        # Signal 1: Vector similarity from concepts (50%)
        self._add_concept_signals(query, candidates, min_confidence, now)

        # Signal 2: Graph traversal from beliefs (20%)
        self._add_belief_signals(query, candidates, min_confidence, now)

        # Signal 3: Structured fact triples (15%)
        self._add_fact_signals(query, candidates, min_confidence, now)

        # Signal 4: Recency weighted episodes (15%)
        self._add_episode_signals(query, candidates, min_confidence, now)

        # Sort by blended score, return top_k
        results = sorted(candidates.values(), key=lambda r: r.score, reverse=True)
        results = results[:top_k]

        # Auto reinforce: accessed memories get stronger
        if reinforce and results:
            self._reinforce_results(results)

        return results

    def _reinforce_results(self, results: list[RecallResult]) -> None:
        """Reinforce the top recalled memories."""
        for r in results[:3]:
            try:
                if r.layer == "episode":
                    self.episodes.reinforce(r.source_id)
                elif r.layer == "concept":
                    self.concepts.reinforce(r.source_id)
                elif r.layer == "fact":
                    self.facts.reinforce(r.source_id)
                elif r.layer == "belief":
                    self.beliefs.reinforce(r.source_id)
            except Exception:
                pass

    def _add_concept_signals(
        self, query: str, candidates: dict[str, RecallResult],
        min_confidence: float, now: datetime,
    ) -> None:
        """Add vector similarity signals from the concept store."""
        try:
            similar = self.concepts.query_similar(
                query_text=query, n_results=20, min_confidence=min_confidence, now=now,
            )
        except Exception:
            return

        for concept, similarity in similar:
            score = similarity * self.vector_weight
            key = f"concept:{concept.id}"
            if key in candidates:
                candidates[key].score += score
            else:
                candidates[key] = RecallResult(
                    content=concept.summary, layer="concept", score=score,
                    confidence=concept.confidence, source_id=concept.id,
                    metadata={"similarity": similarity},
                )

    def _add_belief_signals(
        self, query: str, candidates: dict[str, RecallResult],
        min_confidence: float, now: datetime,
    ) -> None:
        """Add graph traversal signals from the belief store."""
        all_beliefs = self.beliefs.list_beliefs(min_confidence=min_confidence, now=now)
        if not all_beliefs:
            return

        query_words = set(query.lower().split())

        scored_beliefs: list[tuple[Belief, float]] = []
        for belief in all_beliefs:
            belief_words = set(belief.principle.lower().split())
            overlap = len(query_words & belief_words)
            if overlap > 0:
                relevance = overlap / max(len(query_words), 1)
                scored_beliefs.append((belief, relevance))

        scored_beliefs.sort(key=lambda x: x[1], reverse=True)

        seen_ids: set[str] = set()
        for belief, relevance in scored_beliefs[:5]:
            if belief.id in seen_ids:
                continue
            seen_ids.add(belief.id)

            score = relevance * self.graph_weight
            key = f"belief:{belief.id}"
            candidates[key] = RecallResult(
                content=belief.principle, layer="belief", score=score,
                confidence=belief.confidence, source_id=belief.id,
                metadata={"relevance": relevance, "via": "direct"},
            )

            related = self.beliefs.get_related(belief.id, max_depth=1)
            for related_belief, relation, edge_weight in related:
                if related_belief.id in seen_ids:
                    continue
                seen_ids.add(related_belief.id)

                neighbor_score = relevance * edge_weight * self.graph_weight * 0.5
                key = f"belief:{related_belief.id}"
                candidates[key] = RecallResult(
                    content=related_belief.principle, layer="belief",
                    score=neighbor_score, confidence=related_belief.confidence,
                    source_id=related_belief.id,
                    metadata={"relevance": relevance * edge_weight, "via": f"graph:{relation}"},
                )

    def _add_fact_signals(
        self, query: str, candidates: dict[str, RecallResult],
        min_confidence: float, now: datetime,
    ) -> None:
        """Add structured fact signals via semantic search + exact match."""
        # Semantic search over fact triples
        try:
            similar = self.facts.query_similar(
                query_text=query, n_results=10, min_confidence=min_confidence, now=now,
            )
        except Exception:
            similar = []

        for fact, similarity in similar:
            score = similarity * self.fact_weight
            key = f"fact:{fact.id}"
            candidates[key] = RecallResult(
                content=fact.triple_text, layer="fact", score=score,
                confidence=fact.confidence, source_id=fact.id,
                metadata={
                    "subject": fact.subject, "predicate": fact.predicate,
                    "object": fact.object, "similarity": similarity,
                },
            )

        # Also try exact entity match on query words
        query_words = query.lower().split()
        for word in query_words:
            if len(word) < 2:
                continue
            try:
                # Search as subject
                exact = self.facts.query(subject=word, min_confidence=min_confidence, now=now)
                for fact in exact[:3]:
                    key = f"fact:{fact.id}"
                    if key not in candidates:
                        candidates[key] = RecallResult(
                            content=fact.triple_text, layer="fact",
                            score=self.fact_weight * 0.8,
                            confidence=fact.confidence, source_id=fact.id,
                            metadata={"subject": fact.subject, "predicate": fact.predicate,
                                      "object": fact.object, "via": "exact_subject"},
                        )
            except Exception:
                pass

    def _add_episode_signals(
        self, query: str, candidates: dict[str, RecallResult],
        min_confidence: float, now: datetime,
    ) -> None:
        """Add semantic + recency signals from raw episodes."""
        max_age_seconds = 30 * 24 * 3600

        try:
            similar = self.episodes.query_similar(
                query_text=query, n_results=10, min_confidence=min_confidence, now=now,
            )
        except Exception:
            return

        for episode, similarity in similar:
            age = (now - episode.timestamp).total_seconds()
            recency = max(0.0, 1.0 - (age / max_age_seconds))
            score = (similarity * 0.7 + recency * 0.3) * self.recency_weight

            key = f"episode:{episode.id}"
            candidates[key] = RecallResult(
                content=episode.content, layer="episode", score=score,
                confidence=episode.confidence, source_id=episode.id,
                metadata={"similarity": similarity, "recency": recency},
            )
