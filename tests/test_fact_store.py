"""Tests for the L2.5 Fact Store."""

from datetime import datetime, timedelta, timezone

import pytest

from engram.core.types import Fact
from engram.stores.fact_store import FactStore


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
def fact_store(tmp_path):
    chroma_dir = tmp_path / "chroma_facts"
    chroma_dir.mkdir()
    store = FactStore(tmp_path / "test.db", chroma_dir)
    store.initialize()
    yield store
    store.close()


class TestFactStore:
    def test_add_and_get(self, fact_store):
        f = Fact(subject="p53", predicate="inhibits", object="MDM2",
                 subject_type="Protein", object_type="Gene")
        fact_store.add(f)

        result = fact_store.get(f.id)
        assert result is not None
        assert result.subject == "p53"
        assert result.predicate == "inhibits"
        assert result.object == "MDM2"
        assert result.subject_type == "Protein"

    def test_count(self, fact_store):
        assert fact_store.count() == 0
        fact_store.add(Fact(subject="a", predicate="rel", object="b"))
        fact_store.add(Fact(subject="c", predicate="rel", object="d"))
        assert fact_store.count() == 2

    def test_delete(self, fact_store):
        f = Fact(subject="a", predicate="rel", object="b")
        fact_store.add(f)
        assert fact_store.delete(f.id) is True
        assert fact_store.count() == 0

    def test_query_by_subject(self, fact_store):
        fact_store.add(Fact(subject="p53", predicate="inhibits", object="MDM2"))
        fact_store.add(Fact(subject="p53", predicate="binds_to", object="DNA"))
        fact_store.add(Fact(subject="BRCA1", predicate="repairs", object="DNA"))

        results = fact_store.query(subject="p53")
        assert len(results) == 2

    def test_query_by_predicate(self, fact_store):
        fact_store.add(Fact(subject="p53", predicate="inhibits", object="MDM2"))
        fact_store.add(Fact(subject="BRCA1", predicate="inhibits", object="cell_growth"))

        results = fact_store.query(predicate="inhibits")
        assert len(results) == 2

    def test_query_by_object(self, fact_store):
        fact_store.add(Fact(subject="p53", predicate="inhibits", object="MDM2"))
        fact_store.add(Fact(subject="ARF", predicate="activates", object="MDM2"))

        results = fact_store.query(object="MDM2")
        assert len(results) == 2

    def test_query_exact_triple(self, fact_store):
        fact_store.add(Fact(subject="p53", predicate="inhibits", object="MDM2"))
        fact_store.add(Fact(subject="p53", predicate="activates", object="BAX"))

        results = fact_store.query(subject="p53", predicate="inhibits", object="MDM2")
        assert len(results) == 1

    def test_query_by_type(self, fact_store):
        fact_store.add(Fact(subject="p53", predicate="inhibits", object="MDM2",
                           subject_type="Protein", object_type="Gene"))
        fact_store.add(Fact(subject="aspirin", predicate="treats", object="pain",
                           subject_type="Drug", object_type="Disease"))

        results = fact_store.query_by_type(subject_type="Protein")
        assert len(results) == 1
        assert results[0].subject == "p53"

    def test_query_similar(self, fact_store):
        fact_store.add(Fact(subject="p53", predicate="inhibits", object="MDM2",
                           subject_type="Protein", object_type="Gene"))
        fact_store.add(Fact(subject="User", predicate="prefers", object="Python",
                           subject_type="", object_type="Language"))

        results = fact_store.query_similar("protein gene interaction")
        assert len(results) > 0
        # The p53/MDM2 fact should rank higher
        assert "p53" in results[0][0].subject

    def test_find_contradictions_same_predicate(self, fact_store):
        f1 = Fact(subject="User", predicate="prefers", object="Python")
        f2 = Fact(subject="User", predicate="prefers", object="Go")
        fact_store.add(f1)
        fact_store.add(f2)

        contradictions = fact_store.find_contradictions(f2)
        assert len(contradictions) == 1
        assert contradictions[0].object == "Python"

    def test_find_contradictions_opposite_predicate(self, fact_store):
        f1 = Fact(subject="p53", predicate="inhibits", object="MDM2")
        f2 = Fact(subject="p53", predicate="activates", object="MDM2")
        fact_store.add(f1)
        fact_store.add(f2)

        contradictions = fact_store.find_contradictions(f2)
        assert len(contradictions) == 1
        assert contradictions[0].predicate == "inhibits"

    def test_find_no_contradictions(self, fact_store):
        f1 = Fact(subject="p53", predicate="inhibits", object="MDM2")
        f2 = Fact(subject="BRCA1", predicate="repairs", object="DNA")
        fact_store.add(f1)
        fact_store.add(f2)

        contradictions = fact_store.find_contradictions(f2)
        assert len(contradictions) == 0

    def test_reinforce(self, fact_store):
        f = Fact(subject="a", predicate="rel", object="b")
        fact_store.add(f)
        fact_store.reinforce(f.id)

        row = fact_store.conn.execute(
            "SELECT reinforcement_count FROM facts WHERE id = ?", (f.id,)
        ).fetchone()
        assert row["reinforcement_count"] == 1

    def test_garbage_collect(self, fact_store):
        f = Fact(subject="a", predicate="rel", object="b", half_life_days=1.0)
        fact_store.add(f)

        future = _now() + timedelta(days=100)
        gc_count = fact_store.garbage_collect(now=future)
        assert gc_count == 1
        assert fact_store.count() == 0

    def test_decay_filters_query(self, fact_store):
        f = Fact(subject="a", predicate="rel", object="b", half_life_days=1.0)
        fact_store.add(f)

        future = _now() + timedelta(days=100)
        results = fact_store.query(subject="a", now=future)
        assert len(results) == 0

    def test_triple_text(self, fact_store):
        f = Fact(subject="p53", predicate="inhibits", object="MDM2",
                 subject_type="Protein", object_type="Gene")
        assert f.triple_text == "p53 [Protein] inhibits MDM2 [Gene]"

    def test_triple_text_no_types(self, fact_store):
        f = Fact(subject="User", predicate="prefers", object="Python")
        assert f.triple_text == "User prefers Python"
