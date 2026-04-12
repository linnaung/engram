"""Engram Engine: the unified interface that ties all layers together."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from engram.core.config import EngineConfig, get_config
from engram.core.types import Episode, Fact, RecallResult
from engram.stores.episode_store import EpisodeStore
from engram.stores.concept_store import ConceptStore
from engram.stores.fact_store import FactStore
from engram.stores.belief_store import BeliefStore
from engram.stores.session_store import SessionStore
from engram.synthesizer.base import BaseLLM
from engram.synthesizer.extractor import Extractor
from engram.synthesizer.fact_extractor import FactExtractor
from engram.synthesizer.distiller import Distiller
from engram.context.provider import ContextProvider
from engram.context.loader import load_ontology
from engram.retrieval.mixer import RetrievalMixer


class Engram:
    """The main Engram engine: ingest, synthesize, recall."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or get_config()

        # Stores
        self.episodes = EpisodeStore(self.config.sqlite_path, self.config.chroma_path)
        self.concepts = ConceptStore(self.config.chroma_path)
        self.facts = FactStore(self.config.sqlite_path, self.config.chroma_path)
        self.beliefs = BeliefStore(self.config.graph_path)
        self.sessions = SessionStore(self.config.sqlite_path)

        # Context (optional domain ontology)
        self._context: ContextProvider | None = None

        # LLM (lazy init)
        self._llm: BaseLLM | None = None
        self._extractor: Extractor | None = None
        self._fact_extractor: FactExtractor | None = None
        self._distiller: Distiller | None = None

        # Retrieval
        self._mixer: RetrievalMixer | None = None

    def initialize(self) -> None:
        """Initialize all stores and components."""
        self.episodes.initialize()
        self.concepts.initialize()
        self.facts.initialize()
        self.beliefs.initialize()
        self.sessions.initialize()

        # Load context: check saved ontology first, then config
        saved_ontology = self.config.data_dir / "ontology.ttl"
        if saved_ontology.exists():
            self._context = load_ontology(str(saved_ontology))
        elif self.config.context_file:
            self._context = load_ontology(self.config.context_file)

        self._mixer = RetrievalMixer(
            episode_store=self.episodes,
            concept_store=self.concepts,
            fact_store=self.facts,
            belief_store=self.beliefs,
            vector_weight=self.config.vector_weight,
            graph_weight=self.config.graph_weight,
            fact_weight=self.config.fact_weight,
            recency_weight=self.config.recency_weight,
        )

    def close(self) -> None:
        """Clean up all resources."""
        self.episodes.close()
        self.concepts.close()
        self.facts.close()
        self.beliefs.close()
        self.sessions.close()

    @property
    def context(self) -> ContextProvider | None:
        return self._context

    def load_context(self, path: str) -> None:
        """Load a domain ontology and persist it to the data directory.

        The ontology is saved as ontology.ttl in the data dir so it
        auto-loads on next startup without needing the original file.
        """
        from pathlib import Path
        import shutil
        self._context = load_ontology(path)
        # Reset fact extractor so it picks up the new context
        self._fact_extractor = None
        # Persist: copy the ontology file to data dir (skip if already there)
        saved_path = self.config.data_dir / "ontology.ttl"
        source = Path(path).resolve()
        if source != saved_path.resolve():
            shutil.copy2(path, str(saved_path))

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
    def fact_extractor(self) -> FactExtractor:
        if self._fact_extractor is None:
            self._fact_extractor = FactExtractor(self.llm, self._context)
        return self._fact_extractor

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
        """Ingest raw text as an L1 Episode."""
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
        """Hybrid recall across all memory layers."""
        threshold = min_confidence if min_confidence is not None else self.config.min_confidence
        return self.mixer.recall(query, top_k=top_k, min_confidence=threshold)

    def chat(
        self,
        message: str,
        session_id: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict:
        """Send a message to Ollama with memory augmented context.

        1. Ingests the user message as an episode
        2. Recalls relevant memories
        3. Loads session history from DB if session_id provided
        4. Builds a system prompt with memory context
        5. Calls Ollama for a response
        6. Saves both messages to session with memory provenance
        7. Returns the response and which memories were used
        """
        import ollama as _ollama

        # 1. Ingest user message
        self.ingest(message, source="conversation:user")

        # 2. Recall relevant memories
        memories = self.recall(message, top_k=5)

        memories_used = [
            {
                "content": m.content,
                "layer": m.layer,
                "score": round(m.score, 4),
                "confidence": round(m.confidence, 4),
            }
            for m in memories
        ]

        # 3. Build system prompt with memory context
        memory_lines = []
        for m in memories:
            layer_tag = {"episode": "memory", "concept": "understanding", "fact": "fact", "belief": "belief"}.get(m.layer, m.layer)
            memory_lines.append(f"[{layer_tag}] {m.content}")
        memory_context = "\n".join(memory_lines)

        system_prompt = "You are a helpful assistant with persistent memory. "
        system_prompt += "Your memory naturally decays over time, but important things are remembered longer. "
        system_prompt += "Use the following recalled memories as context when relevant, but do not repeat them verbatim.\n\n"

        # Inject ontology context so LLM knows the domain
        if self._context:
            types = self._context.list_types()
            predicates = self._context.list_predicates()
            system_prompt += "Domain ontology is loaded. You have knowledge of these entity types and relationships:\n"
            if types:
                system_prompt += f"Entity types: {', '.join(types[:30])}\n"
            if predicates:
                system_prompt += f"Relationships: {', '.join(predicates[:30])}\n"
            system_prompt += "Use this domain knowledge to give precise, typed answers when relevant.\n\n"

        # Inject relevant structured facts
        try:
            relevant_facts = self.facts.query_similar(message, n_results=5)
            if relevant_facts:
                fact_lines = [f.triple_text for f, _ in relevant_facts]
                system_prompt += f"Known facts:\n" + "\n".join(f"  {fl}" for fl in fact_lines) + "\n\n"
        except Exception:
            pass

        if memory_context:
            system_prompt += f"Recalled memories:\n{memory_context}\n"
        else:
            system_prompt += "No relevant memories recalled yet.\n"

        # 4. Build messages for Ollama
        ollama_messages = [{"role": "system", "content": system_prompt}]

        # Load history from session DB if available
        if session_id:
            db_messages = self.sessions.get_messages(session_id, limit=20)
            for m in db_messages[-10:]:
                ollama_messages.append({"role": m.role, "content": m.content})
        elif history:
            for h in history[-10:]:
                ollama_messages.append({"role": h["role"], "content": h["content"]})

        ollama_messages.append({"role": "user", "content": message})

        # 5. Call Ollama
        response = _ollama.chat(
            model=self.config.ollama_model,
            messages=ollama_messages,
        )
        assistant_text = response.message.content

        # 6. Ingest assistant response
        self.ingest(assistant_text, source="conversation:assistant")

        # 7. Save to session if provided
        if session_id:
            self.sessions.add_message(session_id, "user", message)
            self.sessions.add_message(session_id, "assistant", assistant_text, memories_used)

            # Auto-title on first message
            session = self.sessions.get_session(session_id)
            if session and session.message_count <= 2:
                title = message[:50] + ("..." if len(message) > 50 else "")
                self.sessions.update_session_title(session_id, title)

        return {
            "response": assistant_text,
            "memories_used": memories_used,
        }

    async def synthesize(self) -> dict:
        """Run the full synthesis loop: Episodes > Concepts > Facts > Beliefs.

        Returns dict with counts of new items created at each layer.
        """
        now = datetime.now(timezone.utc)

        # Step 1: Get active episodes
        active_episodes = self.episodes.list_active(
            min_confidence=self.config.min_confidence,
            limit=50,
            now=now,
        )

        if not active_episodes:
            return {
                "episodes_processed": 0, "concepts_created": 0, "facts_created": 0,
                "concepts_merged": 0, "beliefs_created": 0, "edges_created": 0,
                "contradictions_resolved": 0, "episodes_garbage_collected": 0,
            }

        # Step 2: Extract concepts from episodes (L1 > L2)
        new_concepts = await self.extractor.extract(active_episodes)

        for concept in new_concepts:
            concept.half_life_days = self.config.concept_half_life_days
            self.concepts.add(concept)

        # Step 2.5: Extract facts from concepts (L2 > L2.5)
        new_facts = await self.fact_extractor.extract(new_concepts)

        for fact in new_facts:
            fact.half_life_days = self.config.fact_half_life_days

            # Check for contradictions at the fact level (cheap, no LLM needed)
            contradictions = self.facts.find_contradictions(fact)
            for old_fact in contradictions:
                # Newer wins: halve the old fact's half life
                row = self.facts.conn.execute(
                    "SELECT half_life_days FROM facts WHERE id = ?", (old_fact.id,)
                ).fetchone()
                if row:
                    self.facts.conn.execute(
                        "UPDATE facts SET half_life_days = ? WHERE id = ?",
                        (row["half_life_days"] / 2.0, old_fact.id),
                    )
                    self.facts.conn.commit()

            self.facts.add(fact)

        fact_contradictions = sum(
            len(self.facts.find_contradictions(f)) for f in new_facts
        )

        # Step 3: Distill beliefs from concepts (L2 > L3)
        existing_beliefs = self.beliefs.list_beliefs(
            min_confidence=self.config.min_confidence, now=now
        )

        if new_concepts:
            new_beliefs, new_edges = await self.distiller.distill(
                concepts=new_concepts,
                existing_beliefs=existing_beliefs,
            )

            for belief in new_beliefs:
                belief.half_life_days = self.config.belief_half_life_days
                self.beliefs.add_belief(belief)

            for edge in new_edges:
                try:
                    self.beliefs.add_edge(edge)
                except ValueError:
                    pass
        else:
            new_beliefs, new_edges = [], []

        # Step 4: Deduplicate concepts
        from engram.synthesizer.deduplicator import Deduplicator
        dedup = Deduplicator(self.concepts)
        dedup_result = dedup.deduplicate()

        # Step 5: Detect text level contradictions (LLM fallback)
        from engram.synthesizer.contradiction import ContradictionDetector
        detector = ContradictionDetector(self.llm, self.concepts, self.beliefs)
        contradiction_result = await detector.detect_and_resolve()

        # Step 6: Garbage collect decayed memories
        gc_episodes = self.episodes.garbage_collect(threshold=self.config.min_confidence, now=now)
        self.facts.garbage_collect(threshold=self.config.min_confidence, now=now)

        return {
            "episodes_processed": len(active_episodes),
            "concepts_created": len(new_concepts),
            "facts_created": len(new_facts),
            "fact_contradictions": fact_contradictions,
            "concepts_merged": dedup_result.get("merged", 0),
            "beliefs_created": len(new_beliefs),
            "edges_created": len(new_edges),
            "contradictions_resolved": contradiction_result.get("resolved", 0),
            "episodes_garbage_collected": gc_episodes,
        }

    def synthesize_sync(self) -> dict:
        """Synchronous wrapper for synthesize()."""
        return asyncio.run(self.synthesize())

    def status(self) -> dict:
        """Get current memory statistics."""
        return {
            "episodes": self.episodes.count(),
            "concepts": self.concepts.count(),
            "facts": self.facts.count(),
            "beliefs": self.beliefs.count(),
            "edges": self.beliefs.edge_count(),
            "sessions": self.sessions.session_count(),
            "context_loaded": self._context is not None,
            "data_dir": str(self.config.data_dir),
        }

    def forget(self, memory_id: str) -> bool:
        """Remove a memory by ID from any layer."""
        if self.episodes.delete(memory_id):
            return True
        if self.concepts.delete(memory_id):
            return True
        if self.facts.delete(memory_id):
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
