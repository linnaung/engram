"""Tests for the three memory stores."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from engram.core.types import Episode, Concept, Belief, Edge
from engram.stores.episode_store import EpisodeStore
from engram.stores.concept_store import ConceptStore
from engram.stores.belief_store import BeliefStore


def _now():
    return datetime.now(timezone.utc)


# ── Episode Store ──


@pytest.fixture
def episode_store(tmp_path):
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    store = EpisodeStore(tmp_path / "test.db", chroma_dir)
    store.initialize()
    yield store
    store.close()


class TestEpisodeStore:
    def test_add_and_get(self, episode_store):
        ep = Episode(content="hello world", source="test")
        episode_store.add(ep)

        result = episode_store.get(ep.id)
        assert result is not None
        assert result.content == "hello world"
        assert result.source == "test"

    def test_count(self, episode_store):
        assert episode_store.count() == 0
        episode_store.add(Episode(content="one"))
        episode_store.add(Episode(content="two"))
        assert episode_store.count() == 2

    def test_delete(self, episode_store):
        ep = Episode(content="to delete")
        episode_store.add(ep)
        assert episode_store.count() == 1

        result = episode_store.delete(ep.id)
        assert result is True
        assert episode_store.count() == 0
        assert episode_store.get(ep.id) is None

    def test_delete_nonexistent(self, episode_store):
        assert episode_store.delete("nonexistent") is False

    def test_list_active(self, episode_store):
        episode_store.add(Episode(content="recent"))
        results = episode_store.list_active()
        assert len(results) == 1
        assert results[0].content == "recent"

    def test_list_active_filters_decayed(self, episode_store):
        ep = Episode(content="old", half_life_days=1.0)
        episode_store.add(ep)

        # Check now (should be active)
        assert len(episode_store.list_active()) == 1

        # Check far in the future (should be decayed)
        future = _now() + timedelta(days=100)
        assert len(episode_store.list_active(now=future)) == 0

    def test_reinforce(self, episode_store):
        ep = Episode(content="reinforce me")
        episode_store.add(ep)
        episode_store.reinforce(ep.id)

        row = episode_store.conn.execute(
            "SELECT reinforcement_count FROM episodes WHERE id = ?", (ep.id,)
        ).fetchone()
        assert row["reinforcement_count"] == 1

    def test_garbage_collect(self, episode_store):
        ep = Episode(content="will decay", half_life_days=1.0)
        episode_store.add(ep)

        future = _now() + timedelta(days=100)
        gc_count = episode_store.garbage_collect(now=future)
        assert gc_count == 1
        assert episode_store.count() == 0

    def test_query_similar(self, episode_store):
        episode_store.add(Episode(content="Python is a great programming language"))
        episode_store.add(Episode(content="I had pizza for lunch today"))

        results = episode_store.query_similar("coding in Python", n_results=2)
        assert len(results) > 0
        # The Python episode should rank higher than the pizza one
        assert "Python" in results[0][0].content


# ── Concept Store ──


@pytest.fixture
def concept_store(tmp_path):
    store = ConceptStore(tmp_path / "chroma_concepts")
    store.initialize()
    yield store
    store.close()


class TestConceptStore:
    def test_add_and_get(self, concept_store):
        c = Concept(summary="User prefers Python")
        concept_store.add(c)

        result = concept_store.get(c.id)
        assert result is not None
        assert result.summary == "User prefers Python"

    def test_count(self, concept_store):
        assert concept_store.count() == 0
        concept_store.add(Concept(summary="one"))
        concept_store.add(Concept(summary="two"))
        assert concept_store.count() == 2

    def test_delete(self, concept_store):
        c = Concept(summary="to delete")
        concept_store.add(c)
        assert concept_store.delete(c.id) is True
        assert concept_store.count() == 0

    def test_query_similar(self, concept_store):
        concept_store.add(Concept(summary="User prefers Python for backend development"))
        concept_store.add(Concept(summary="The weather is sunny today"))

        results = concept_store.query_similar("programming language preferences")
        assert len(results) > 0
        assert "Python" in results[0][0].summary

    def test_query_similar_filters_decayed(self, concept_store):
        c = Concept(summary="old concept", half_life_days=1.0)
        concept_store.add(c)

        future = _now() + timedelta(days=100)
        results = concept_store.query_similar("old concept", now=future)
        assert len(results) == 0

    def test_reinforce(self, concept_store):
        c = Concept(summary="reinforce me")
        concept_store.add(c)
        concept_store.reinforce(c.id)

        result = concept_store.get(c.id)
        assert result is not None
        assert result.reinforcement_count == 1


# ── Belief Store ──


@pytest.fixture
def belief_store(tmp_path):
    store = BeliefStore(tmp_path / "graph.json")
    store.initialize()
    yield store
    store.close()


class TestBeliefStore:
    def test_add_and_get(self, belief_store):
        b = Belief(principle="User values simplicity")
        belief_store.add_belief(b)

        result = belief_store.get_belief(b.id)
        assert result is not None
        assert result.principle == "User values simplicity"

    def test_count(self, belief_store):
        assert belief_store.count() == 0
        belief_store.add_belief(Belief(principle="one"))
        belief_store.add_belief(Belief(principle="two"))
        assert belief_store.count() == 2

    def test_delete(self, belief_store):
        b = Belief(principle="to delete")
        belief_store.add_belief(b)
        assert belief_store.delete_belief(b.id) is True
        assert belief_store.count() == 0

    def test_delete_nonexistent(self, belief_store):
        assert belief_store.delete_belief("nonexistent") is False

    def test_add_edge(self, belief_store):
        b1 = Belief(principle="simplicity matters")
        b2 = Belief(principle="readability matters")
        belief_store.add_belief(b1)
        belief_store.add_belief(b2)

        edge = Edge(source_id=b1.id, target_id=b2.id, relation="supports", weight=0.8)
        belief_store.add_edge(edge)

        assert belief_store.edge_count() == 1

    def test_add_edge_missing_node(self, belief_store):
        b1 = Belief(principle="exists")
        belief_store.add_belief(b1)

        edge = Edge(source_id=b1.id, target_id="nonexistent", relation="supports")
        with pytest.raises(ValueError):
            belief_store.add_edge(edge)

    def test_get_related(self, belief_store):
        b1 = Belief(principle="simplicity")
        b2 = Belief(principle="readability")
        b3 = Belief(principle="composability")
        belief_store.add_belief(b1)
        belief_store.add_belief(b2)
        belief_store.add_belief(b3)

        belief_store.add_edge(Edge(source_id=b1.id, target_id=b2.id, relation="supports", weight=0.8))
        belief_store.add_edge(Edge(source_id=b2.id, target_id=b3.id, relation="reminds_of", weight=0.6))

        # Depth 1: b1 should find b2
        related = belief_store.get_related(b1.id, max_depth=1)
        assert len(related) == 1
        assert related[0][0].principle == "readability"
        assert related[0][1] == "supports"

        # Depth 2: b1 should find b2 and b3
        related = belief_store.get_related(b1.id, max_depth=2)
        assert len(related) == 2

    def test_get_related_by_relation(self, belief_store):
        b1 = Belief(principle="a")
        b2 = Belief(principle="b")
        b3 = Belief(principle="c")
        belief_store.add_belief(b1)
        belief_store.add_belief(b2)
        belief_store.add_belief(b3)

        belief_store.add_edge(Edge(source_id=b1.id, target_id=b2.id, relation="supports"))
        belief_store.add_edge(Edge(source_id=b1.id, target_id=b3.id, relation="contradicts"))

        supports = belief_store.get_related(b1.id, relation="supports")
        assert len(supports) == 1
        assert supports[0][1] == "supports"

    def test_list_beliefs_filters_decayed(self, belief_store):
        b = Belief(principle="old belief", half_life_days=1.0)
        belief_store.add_belief(b)

        assert len(belief_store.list_beliefs()) == 1

        future = _now() + timedelta(days=100)
        assert len(belief_store.list_beliefs(now=future)) == 0

    def test_reinforce(self, belief_store):
        b = Belief(principle="reinforce me")
        belief_store.add_belief(b)
        belief_store.reinforce(b.id)

        data = belief_store.graph.nodes[b.id]
        assert data["reinforcement_count"] == 1

    def test_persistence(self, tmp_path):
        path = tmp_path / "graph.json"

        # Write
        store1 = BeliefStore(path)
        store1.initialize()
        store1.add_belief(Belief(principle="persisted"))
        store1.close()

        # Read back
        store2 = BeliefStore(path)
        store2.initialize()
        assert store2.count() == 1
        beliefs = store2.list_beliefs()
        assert beliefs[0].principle == "persisted"
        store2.close()
