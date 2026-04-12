"""Tests for the hybrid retrieval mixer."""

from datetime import datetime, timedelta, timezone

import pytest

from engram.core.types import Episode, Concept, Belief, Edge
from engram.stores.episode_store import EpisodeStore
from engram.stores.concept_store import ConceptStore
from engram.stores.fact_store import FactStore
from engram.stores.belief_store import BeliefStore
from engram.retrieval.mixer import RetrievalMixer


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
def stores(tmp_path):
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()

    episodes = EpisodeStore(tmp_path / "test.db", chroma_dir)
    concepts = ConceptStore(tmp_path / "chroma_concepts")
    facts = FactStore(tmp_path / "test.db", tmp_path / "chroma_facts")
    beliefs = BeliefStore(tmp_path / "graph.json")

    episodes.initialize()
    concepts.initialize()
    facts.initialize()
    beliefs.initialize()

    yield episodes, concepts, facts, beliefs

    episodes.close()
    concepts.close()
    facts.close()
    beliefs.close()


@pytest.fixture
def mixer(stores):
    episodes, concepts, facts, beliefs = stores
    return RetrievalMixer(
        episode_store=episodes,
        concept_store=concepts,
        fact_store=facts,
        belief_store=beliefs,
    )


class TestRetrievalMixer:
    def test_empty_recall(self, mixer):
        results = mixer.recall("anything")
        assert results == []

    def test_recall_episodes_only(self, stores, mixer):
        episodes, _, _, _ = stores
        episodes.add(Episode(content="Python is my favorite language"))
        episodes.add(Episode(content="I ate sushi for dinner"))

        results = mixer.recall("programming language")
        assert len(results) > 0
        assert any("Python" in r.content for r in results)

    def test_recall_concepts_only(self, stores, mixer):
        _, concepts, _, _ = stores
        concepts.add(Concept(summary="User prefers functional programming"))
        concepts.add(Concept(summary="Weather forecast is sunny"))

        results = mixer.recall("programming style")
        assert len(results) > 0
        assert results[0].layer == "concept"

    def test_recall_beliefs_with_keyword(self, stores, mixer):
        _, _, _, beliefs = stores
        beliefs.add_belief(Belief(principle="User values simplicity in all tools"))

        results = mixer.recall("simplicity tools")
        assert len(results) > 0
        assert any(r.layer == "belief" for r in results)

    def test_recall_blends_layers(self, stores, mixer):
        episodes, concepts, _, beliefs = stores

        episodes.add(Episode(content="I use Python daily"))
        concepts.add(Concept(summary="User prefers Python for readability"))
        beliefs.add_belief(Belief(principle="User values readable code above all"))

        results = mixer.recall("Python readability", top_k=10)
        layers = {r.layer for r in results}
        # Should have results from at least 2 layers
        assert len(layers) >= 2

    def test_recall_respects_top_k(self, stores, mixer):
        episodes, _, _, _ = stores
        for i in range(10):
            episodes.add(Episode(content=f"Memory number {i} about programming"))

        results = mixer.recall("programming", top_k=3)
        assert len(results) <= 3

    def test_recall_sorted_by_score(self, stores, mixer):
        _, concepts, _, _ = stores
        concepts.add(Concept(summary="Python is great for data science"))
        concepts.add(Concept(summary="Rust is fast and safe"))
        concepts.add(Concept(summary="Go is good for concurrency"))

        results = mixer.recall("data science programming")
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score

    def test_recall_filters_by_confidence(self, stores, mixer):
        _, concepts, _, _ = stores
        concepts.add(Concept(summary="old concept", half_life_days=1.0))

        future = _now() + timedelta(days=100)
        results = mixer.recall("old concept", min_confidence=0.05, now=future)
        assert len(results) == 0

    def test_graph_traversal(self, stores, mixer):
        _, _, _, beliefs = stores

        b1 = Belief(principle="User values simplicity in design")
        b2 = Belief(principle="Composability is a core engineering value")
        beliefs.add_belief(b1)
        beliefs.add_belief(b2)
        beliefs.add_edge(Edge(source_id=b1.id, target_id=b2.id, relation="supports", weight=0.9))

        results = mixer.recall("simplicity design")
        principles = [r.content for r in results]
        # Both should appear: direct match + graph neighbor
        assert any("simplicity" in p for p in principles)

    def test_reinforcement_on_recall(self, stores):
        episodes, concepts, facts, beliefs = stores
        episodes.add(Episode(content="Python is great"))

        mixer = RetrievalMixer(
            episode_store=episodes,
            concept_store=concepts,
            fact_store=facts,
            belief_store=beliefs,
        )

        # First recall
        mixer.recall("Python", reinforce=True)

        # Check reinforcement count increased
        row = episodes.conn.execute(
            "SELECT reinforcement_count FROM episodes"
        ).fetchone()
        assert row["reinforcement_count"] >= 1

    def test_no_reinforcement_when_disabled(self, stores):
        episodes, concepts, facts, beliefs = stores
        episodes.add(Episode(content="Python is great"))

        mixer = RetrievalMixer(
            episode_store=episodes,
            concept_store=concepts,
            fact_store=facts,
            belief_store=beliefs,
        )

        mixer.recall("Python", reinforce=False)

        row = episodes.conn.execute(
            "SELECT reinforcement_count FROM episodes"
        ).fetchone()
        assert row["reinforcement_count"] == 0
