"""Integration tests for the Engram engine."""

import os
from datetime import timedelta

import pytest

from engram.core.config import EngineConfig
from engram.engine import Engram


@pytest.fixture
def engine(tmp_path):
    config = EngineConfig(
        data_dir=tmp_path / "engram_test",
        ollama_model="llama3.2",
    )
    config.ensure_dirs()

    eng = Engram(config)
    eng.initialize()
    yield eng
    eng.close()


class TestEngineIngest:
    def test_ingest_creates_episode(self, engine):
        ep = engine.ingest("hello world")
        assert ep.content == "hello world"
        assert ep.source == "conversation"
        assert engine.episodes.count() == 1

    def test_ingest_custom_source(self, engine):
        ep = engine.ingest("from a doc", source="document")
        assert ep.source == "document"

    def test_ingest_multiple(self, engine):
        engine.ingest("one")
        engine.ingest("two")
        engine.ingest("three")
        assert engine.episodes.count() == 3


class TestEngineRecall:
    def test_recall_empty(self, engine):
        results = engine.recall("anything")
        assert results == []

    def test_recall_finds_ingested(self, engine):
        engine.ingest("Python is my favorite programming language")
        results = engine.recall("programming language")
        assert len(results) > 0
        assert "Python" in results[0].content

    def test_recall_ranks_relevant_higher(self, engine):
        engine.ingest("Python is great for data science")
        engine.ingest("I had pasta for dinner last night")

        results = engine.recall("programming and data analysis")
        assert len(results) > 0
        assert "Python" in results[0].content


class TestEngineForget:
    def test_forget_episode(self, engine):
        ep = engine.ingest("forget me")
        assert engine.forget(ep.id) is True
        assert engine.episodes.count() == 0

    def test_forget_nonexistent(self, engine):
        assert engine.forget("nonexistent") is False


class TestEngineStatus:
    def test_status_empty(self, engine):
        stats = engine.status()
        assert stats["episodes"] == 0
        assert stats["concepts"] == 0
        assert stats["beliefs"] == 0
        assert stats["edges"] == 0

    def test_status_after_ingest(self, engine):
        engine.ingest("one")
        engine.ingest("two")
        stats = engine.status()
        assert stats["episodes"] == 2


class TestEngineSynthesize:
    """Synthesis tests that require Ollama running.

    These are skipped if Ollama is not available.
    """

    @pytest.fixture(autouse=True)
    def check_ollama(self):
        try:
            import ollama
            ollama.chat(model="llama3.2", messages=[{"role": "user", "content": "hi"}])
        except Exception:
            pytest.skip("Ollama not running or llama3.2 not available")

    def test_synthesize_creates_concepts(self, engine):
        engine.ingest("I prefer Python for its readability")
        engine.ingest("Rust has excellent memory safety")
        engine.ingest("I value simplicity over performance")

        result = engine.synthesize_sync()

        assert result["episodes_processed"] == 3
        assert result["concepts_created"] > 0
        assert engine.concepts.count() > 0

    def test_synthesize_empty(self, engine):
        result = engine.synthesize_sync()
        assert result["concepts_created"] == 0

    def test_full_pipeline(self, engine):
        # Ingest
        engine.ingest("Python is great for rapid prototyping")
        engine.ingest("I dislike verbose boilerplate code")
        engine.ingest("Simple tools that compose well are better than monoliths")

        # Synthesize
        result = engine.synthesize_sync()
        assert result["concepts_created"] > 0

        # Recall should now find concepts
        results = engine.recall("programming preferences")
        layers = {r.layer for r in results}
        assert "concept" in layers or "episode" in layers
