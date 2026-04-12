"""Conversation Streaming Mode — auto-ingest and background synthesis.

Provides a session that silently captures conversation turns,
batches them as episodes, and runs synthesis on a configurable interval.
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone

from engram.engine import Engram
from engram.core.config import EngineConfig, get_config


class EngramSession:
    """A live session that auto-ingests conversation and synthesizes in the background.

    Usage:
        session = EngramSession()
        session.start()

        # As conversation happens:
        session.user("I prefer functional programming")
        session.assistant("Noted! Functional programming emphasizes...")
        session.user("Yes, immutability is key for me")

        # Query anytime:
        results = session.recall("programming style")

        # When done:
        session.stop()
    """

    def __init__(
        self,
        config: EngineConfig | None = None,
        synthesis_interval: float = 300.0,  # 5 minutes
        auto_synthesize: bool = True,
    ) -> None:
        self._config = config or get_config()
        self._engine = Engram(self._config)
        self._synthesis_interval = synthesis_interval
        self._auto_synthesize = auto_synthesize
        self._running = False
        self._synth_thread: threading.Thread | None = None
        self._turn_count = 0

    def start(self) -> None:
        """Initialize the engine and start background synthesis."""
        self._engine.initialize()
        self._running = True

        if self._auto_synthesize:
            self._synth_thread = threading.Thread(
                target=self._synthesis_loop,
                daemon=True,
                name="engram-synthesizer",
            )
            self._synth_thread.start()

    def stop(self) -> None:
        """Stop background synthesis and close the engine."""
        self._running = False
        if self._synth_thread and self._synth_thread.is_alive():
            self._synth_thread.join(timeout=5.0)
        self._engine.close()

    def user(self, text: str) -> None:
        """Record a user message."""
        self._turn_count += 1
        self._engine.ingest(
            text,
            source="conversation:user",
        )

    def assistant(self, text: str) -> None:
        """Record an assistant message."""
        self._engine.ingest(
            text,
            source="conversation:assistant",
        )

    def note(self, text: str, source: str = "note") -> None:
        """Record an arbitrary note or document chunk."""
        self._engine.ingest(text, source=source)

    def recall(self, query: str, top_k: int = 5) -> list:
        """Recall memories relevant to the query."""
        return self._engine.recall(query, top_k=top_k)

    def synthesize_now(self) -> dict:
        """Manually trigger synthesis."""
        return self._engine.synthesize_sync()

    def status(self) -> dict:
        """Get memory stats plus session info."""
        stats = self._engine.status()
        stats["session_turns"] = self._turn_count
        stats["auto_synthesize"] = self._auto_synthesize
        stats["synthesis_interval_sec"] = self._synthesis_interval
        return stats

    @property
    def engine(self) -> Engram:
        """Direct access to the underlying engine."""
        return self._engine

    def _synthesis_loop(self) -> None:
        """Background loop that runs synthesis periodically."""
        while self._running:
            time.sleep(self._synthesis_interval)
            if not self._running:
                break
            try:
                asyncio.run(self._engine.synthesize())
            except Exception as e:
                # Log but don't crash the background thread
                print(f"[engram] synthesis error: {e}")
