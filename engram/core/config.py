"""Engram configuration management."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field


class EngineConfig(BaseSettings):
    """Core engine configuration."""

    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".engram",
        description="Root directory for all Engram data",
    )

    # LLM backend (Ollama — local, open-source)
    ollama_model: str = Field(default="llama3.2", description="Ollama model name")
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama server URL")

    # Decay defaults
    episode_half_life_days: float = Field(default=7.0)
    concept_half_life_days: float = Field(default=90.0)
    belief_half_life_days: float = Field(default=365.0)

    # Retrieval weights
    vector_weight: float = Field(default=0.60)
    graph_weight: float = Field(default=0.25)
    recency_weight: float = Field(default=0.15)

    # Confidence thresholds
    min_confidence: float = Field(default=0.05, description="Below this, memory is garbage-collected")

    # API
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8420)

    model_config = {
        "env_prefix": "ENGRAM_",
        "env_file": ".env",
    }

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "engram.db"

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def graph_path(self) -> Path:
        return self.data_dir / "graph.json"

    def ensure_dirs(self) -> None:
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)


def get_config() -> EngineConfig:
    """Load configuration from environment / .env file."""
    config = EngineConfig()
    config.ensure_dirs()
    return config
