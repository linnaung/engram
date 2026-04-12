"""Engram Engine — the unified interface that ties all layers together."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from engram.core.config import EngineConfig, get_config
from engram.core.types import Episode, RecallResult
from engram.stores.episode_store import EpisodeStore
from engram.stores.concept_store import ConceptStore
from engram.stores.belief_store import BeliefStore
from engram.synthesizer.base import BaseLLM
from engram.synthesizer.extractor import Extractor
from engram.synthesizer.distiller import Distiller
from engram.retrieval.mixer import RetrievalMixer


class Engram:
    """The main Engram engine — ingest, synthesize, recall."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or get_config()

        # Stores
        self.episodes = EpisodeStore(self.config.sqlite_path, self.config.chroma_path)
        self.concepts = ConceptStore(self.config.chroma_path)
        self.beliefs = BeliefStore(self.config.graph_path)

        # LLM (lazy init)
        self._llm: BaseLLM | None = None
        self._extractor: Extractor | None = None
        self._distiller: Distiller | None = None

        # Retrieval
        self._mixer: RetrievalMixer | None = None

    def initialize(self) -> None:
        """Initialize all stores and components."""
        self.episodes.initialize()
        self.concepts.initialize()
        self.beliefs.initialize()

        self._mixer = RetrievalMixer(
            episode_store=self.episodes,
            concept_store=self.concepts,
            belief_store=self.beliefs,
            vector_weight=self.config.vector_weight,
            graph_weight=self.config.graph_weight,
            recency_weight=self.config.recency_weight,
        )

    def close(self) -> None:
        """Clean up all resources."""
        self.episodes.close()
        self.concepts.close()
        self.beliefs.close()

    @property
    def llm(self) -> BaseLLM:
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm

    @property
    def extractor(self) -> Extractor:
        if self._extractor is None:
            self._extractor = Extractor(self.llm)
        return self._extractor

    @property
    def distiller(self) -> Distiller:
        if self._distiller is None:
            self._distiller = Distiller(self.llm)
        return self._distiller

    @property
    def mixer(self) -> RetrievalMixer:
        if self._mixer is None:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        return self._mixer

    def ingest(self, text: str, source: str = "conversation") -> Episode:
        """Ingest raw text as an L1 Episode.

        Args:
            text: The raw text to store.
            source: Origin label (e.g., "conversation", "document").

        Returns:
            The created Episode.
        """
        episode = Episode(
            content=text,
            source=source,
            half_life_days=self.config.episode_half_life_days,
        )
        return self.episodes.add(episode)

    def recall(
        self,
        query: str,
        top_k: int = 10,
        min_confidence: float | None = None,
    ) -> list[RecallResult]:
        """Hybrid recall across all memory layers.

        Args:
            query: Natural language query.
            top_k: Max results.
            min_confidence: Minimum confidence (defaults to config value).

        Returns:
            Ranked list of recall results.
        """
        threshold = min_confidence if min_confidence is not None else self.config.min_confidence
        return self.mixer.recall(query, top_k=top_k, min_confidence=threshold)

    async def synthesize(self) -> dict:
        """Run the full synthesis loop: Episodes → Concepts → Beliefs.

        Returns dict with counts of new concepts and beliefs created.
        """
        now = datetime.now(timezone.utc)

        # Step 1: Get active episodes
        active_episodes = self.episodes.list_active(
            min_confidence=self.config.min_confidence,
            limit=50,
            now=now,
        )

        if not active_episodes:
            return {"concepts_created": 0, "beliefs_created": 0, "edges_created": 0}

        # Step 2: Extract concepts from episodes (L1 → L2)
        new_concepts = await self.extractor.extract(active_episodes)

        for concept in new_concepts:
            concept.half_life_days = self.config.concept_half_life_days
            self.concepts.add(concept)

        # Step 3: Distill beliefs from all concepts (L2 → L3)
        existing_beliefs = self.beliefs.list_beliefs(
            min_confidence=self.config.min_confidence, now=now
        )

        # Get recent concepts for distillation
        all_concepts_with_scores = []
        if new_concepts:
            # Use the first new concept's summary as a broad query
            for concept in new_concepts:
                all_concepts_with_scores.append(concept)

        if all_concepts_with_scores:
            new_beliefs, new_edges = await self.distiller.distill(
                concepts=all_concepts_with_scores,
                existing_beliefs=existing_beliefs,
            )

            for belief in new_beliefs:
                belief.half_life_days = self.config.belief_half_life_days
                self.beliefs.add_belief(belief)

            for edge in new_edges:
                try:
                    self.beliefs.add_edge(edge)
                except ValueError:
                    pass  # Skip edges referencing missing beliefs

        else:
            new_beliefs, new_edges = [], []

        # Step 4: Deduplicate concepts
        from engram.synthesizer.deduplicator import Deduplicator
        dedup = Deduplicator(self.concepts)
        dedup_result = dedup.deduplicate()

        # Step 5: Detect and resolve contradictions
        from engram.synthesizer.contradiction import ContradictionDetector
        detector = ContradictionDetector(self.llm, self.concepts, self.beliefs)
        contradiction_result = await detector.detect_and_resolve()

        # Step 6: Garbage collect decayed memories
        gc_count = self.episodes.garbage_collect(
            threshold=self.config.min_confidence, now=now
        )

        return {
            "episodes_processed": len(active_episodes),
            "concepts_created": len(new_concepts),
            "concepts_merged": dedup_result.get("merged", 0),
            "beliefs_created": len(new_beliefs),
            "edges_created": len(new_edges),
            "contradictions_resolved": contradiction_result.get("resolved", 0),
            "episodes_garbage_collected": gc_count,
        }

    def synthesize_sync(self) -> dict:
        """Synchronous wrapper for synthesize()."""
        return asyncio.run(self.synthesize())

    def status(self) -> dict:
        """Get current memory statistics."""
        return {
            "episodes": self.episodes.count(),
            "concepts": self.concepts.count(),
            "beliefs": self.beliefs.count(),
            "edges": self.beliefs.edge_count(),
            "data_dir": str(self.config.data_dir),
        }

    def forget(self, memory_id: str) -> bool:
        """Remove a memory by ID from any layer."""
        if self.episodes.delete(memory_id):
            return True
        if self.concepts.delete(memory_id):
            return True
        if self.beliefs.delete_belief(memory_id):
            return True
        return False

    def _create_llm(self) -> BaseLLM:
        from engram.synthesizer.ollama import OllamaLLM
        return OllamaLLM(
            model=self.config.ollama_model,
            host=self.config.ollama_host,
        )
