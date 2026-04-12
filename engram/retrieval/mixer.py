"""Hybrid retrieval mixer — combines vector, graph, and recency signals.

The core innovation: instead of querying three separate systems and
concatenating results, we blend scores from all three into a single
ranked list weighted by configurable factors.
"""

from __future__ import annotations

from datetime import datetime, timezone

from engram.core.types import RecallResult, Belief
from engram.core.decay import compute_confidence
from engram.stores.episode_store import EpisodeStore
from engram.stores.concept_store import ConceptStore
from engram.stores.belief_store import BeliefStore


class RetrievalMixer:
    """Blends vector similarity, graph traversal, and recency into unified recall.

    Default weights:
        - Vector similarity: 60% (semantic relevance)
        - Graph traversal:   25% (structural relationships)
        - Recency boost:     15% (temporal freshness)
    """

    def __init__(
        self,
        episode_store: EpisodeStore,
        concept_store: ConceptStore,
        belief_store: BeliefStore,
        vector_weight: float = 0.60,
        graph_weight: float = 0.25,
        recency_weight: float = 0.15,
    ) -> None:
        self.episodes = episode_store
        self.concepts = concept_store
        self.beliefs = belief_store
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight
        self.recency_weight = recency_weight

    def recall(
        self,
        query: str,
        top_k: int = 10,
        min_confidence: float = 0.05,
        reinforce: bool = True,
        now: datetime | None = None,
    ) -> list[RecallResult]:
        """Hybrid recall across all three memory layers.

        1. Vector search in ConceptStore for semantic matches
        2. Graph traversal in BeliefStore for related beliefs
        3. Keyword scan in EpisodeStore for raw matches
        4. Blend all scores and return top_k results
        5. Auto-reinforce top results (strengthens useful memories)

        Args:
            query: The recall query (natural language).
            top_k: Maximum results to return.
            min_confidence: Minimum confidence threshold.
            reinforce: If True, auto-reinforce the top results.
            now: Current time for decay calculation.

        Returns:
            Ranked list of RecallResults with blended scores.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        candidates: dict[str, RecallResult] = {}

        # --- Signal 1: Vector similarity from concepts (60%) ---
        self._add_concept_signals(query, candidates, min_confidence, now)

        # --- Signal 2: Graph traversal from beliefs (25%) ---
        self._add_belief_signals(query, candidates, min_confidence, now)

        # --- Signal 3: Recency-weighted episodes (15%) ---
        self._add_episode_signals(query, candidates, min_confidence, now)

        # Sort by blended score, return top_k
        results = sorted(candidates.values(), key=lambda r: r.score, reverse=True)
        results = results[:top_k]

        # Auto-reinforce: accessed memories get stronger
        if reinforce and results:
            self._reinforce_results(results)

        return results

    def _reinforce_results(self, results: list[RecallResult]) -> None:
        """Reinforce the top recalled memories — accessing strengthens them."""
        for r in results[:3]:  # Only reinforce top 3
            try:
                if r.layer == "episode":
                    self.episodes.reinforce(r.source_id)
                elif r.layer == "concept":
                    self.concepts.reinforce(r.source_id)
                elif r.layer == "belief":
                    self.beliefs.reinforce(r.source_id)
            except Exception:
                pass  # Don't let reinforcement errors break recall

    def _add_concept_signals(
        self,
        query: str,
        candidates: dict[str, RecallResult],
        min_confidence: float,
        now: datetime,
    ) -> None:
        """Add vector similarity signals from the concept store."""
        try:
            similar = self.concepts.query_similar(
                query_text=query,
                n_results=20,
                min_confidence=min_confidence,
                now=now,
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
                    content=concept.summary,
                    layer="concept",
                    score=score,
                    confidence=concept.confidence,
                    source_id=concept.id,
                    metadata={"similarity": similarity},
                )

    def _add_belief_signals(
        self,
        query: str,
        candidates: dict[str, RecallResult],
        min_confidence: float,
        now: datetime,
    ) -> None:
        """Add graph traversal signals from the belief store.

        Strategy: find beliefs whose principle text has keyword overlap
        with the query, then traverse their graph neighbors.
        """
        all_beliefs = self.beliefs.list_beliefs(min_confidence=min_confidence, now=now)
        if not all_beliefs:
            return

        query_words = set(query.lower().split())

        # Score beliefs by keyword overlap (simple but effective for v0)
        scored_beliefs: list[tuple[Belief, float]] = []
        for belief in all_beliefs:
            belief_words = set(belief.principle.lower().split())
            overlap = len(query_words & belief_words)
            if overlap > 0:
                relevance = overlap / max(len(query_words), 1)
                scored_beliefs.append((belief, relevance))

        scored_beliefs.sort(key=lambda x: x[1], reverse=True)

        # Take top matches and their graph neighbors
        seen_ids: set[str] = set()
        for belief, relevance in scored_beliefs[:5]:
            if belief.id in seen_ids:
                continue
            seen_ids.add(belief.id)

            score = relevance * self.graph_weight
            key = f"belief:{belief.id}"
            candidates[key] = RecallResult(
                content=belief.principle,
                layer="belief",
                score=score,
                confidence=belief.confidence,
                source_id=belief.id,
                metadata={"relevance": relevance, "via": "direct"},
            )

            # Traverse neighbors
            related = self.beliefs.get_related(belief.id, max_depth=1)
            for related_belief, relation, edge_weight in related:
                if related_belief.id in seen_ids:
                    continue
                seen_ids.add(related_belief.id)

                neighbor_score = relevance * edge_weight * self.graph_weight * 0.5
                key = f"belief:{related_belief.id}"
                candidates[key] = RecallResult(
                    content=related_belief.principle,
                    layer="belief",
                    score=neighbor_score,
                    confidence=related_belief.confidence,
                    source_id=related_belief.id,
                    metadata={
                        "relevance": relevance * edge_weight,
                        "via": f"graph:{relation}",
                    },
                )

    def _add_episode_signals(
        self,
        query: str,
        candidates: dict[str, RecallResult],
        min_confidence: float,
        now: datetime,
    ) -> None:
        """Add semantic + recency signals from raw episodes.

        Uses ChromaDB vector search for semantic matching,
        boosted by recency weighting.
        """
        max_age_seconds = 30 * 24 * 3600  # 30 days normalizer

        try:
            similar = self.episodes.query_similar(
                query_text=query,
                n_results=10,
                min_confidence=min_confidence,
                now=now,
            )
        except Exception:
            return

        for episode, similarity in similar:
            # Recency: newer episodes score higher
            age = (now - episode.timestamp).total_seconds()
            recency = max(0.0, 1.0 - (age / max_age_seconds))

            score = (similarity * 0.7 + recency * 0.3) * self.recency_weight

            key = f"episode:{episode.id}"
            candidates[key] = RecallResult(
                content=episode.content,
                layer="episode",
                score=score,
                confidence=episode.confidence,
                source_id=episode.id,
                metadata={"similarity": similarity, "recency": recency},
            )
