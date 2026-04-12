"""Core data models for Engram's three memory layers."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class Episode:
    """L1: Raw memory — exact text with fast decay.

    Episodes are the raw input. They decay quickly unless
    they get compressed into higher-level Concepts.
    """

    content: str
    source: str = "conversation"
    id: str = field(default_factory=_uuid)
    timestamp: datetime = field(default_factory=_now)
    confidence: float = 1.0
    half_life_days: float = 7.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def half_life(self) -> timedelta:
        return timedelta(days=self.half_life_days)


@dataclass
class Concept:
    """L2: Compressed understanding — summarized with medium decay.

    Concepts are distilled from clusters of Episodes.
    They carry vector embeddings for semantic search.
    """

    summary: str
    embedding: list[float] = field(default_factory=list)
    source_episode_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=_uuid)
    timestamp: datetime = field(default_factory=_now)
    confidence: float = 0.9
    half_life_days: float = 90.0
    reinforcement_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def half_life(self) -> timedelta:
        return timedelta(days=self.half_life_days)


@dataclass
class Belief:
    """L3: Abstract principle — high-level wisdom with slow decay.

    Beliefs are synthesized from patterns across Concepts.
    They form nodes in the knowledge graph.
    """

    principle: str
    supporting_concept_ids: list[str] = field(default_factory=list)
    contradicting_concept_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=_uuid)
    timestamp: datetime = field(default_factory=_now)
    confidence: float = 0.8
    half_life_days: float = 365.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def half_life(self) -> timedelta:
        return timedelta(days=self.half_life_days)


@dataclass
class Fact:
    """L2.5: Structured triple grounded against an optional ontology.

    Facts sit between Concepts (free text) and Beliefs (abstract principles).
    They represent concrete, typed assertions: (subject, predicate, object).
    When a domain ontology is loaded, entities are typed and predicates validated.
    """

    subject: str
    predicate: str
    object: str
    subject_type: str = ""  # from ontology, e.g. "Protein"
    object_type: str = ""   # from ontology, e.g. "Gene"
    source_concept_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=_uuid)
    timestamp: datetime = field(default_factory=_now)
    confidence: float = 0.85
    half_life_days: float = 180.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def half_life(self) -> timedelta:
        return timedelta(days=self.half_life_days)

    @property
    def triple_text(self) -> str:
        """Human readable representation of the triple."""
        s = f"{self.subject} [{self.subject_type}]" if self.subject_type else self.subject
        o = f"{self.object} [{self.object_type}]" if self.object_type else self.object
        return f"{s} {self.predicate} {o}"


@dataclass
class Edge:
    """Relationship between two beliefs in the knowledge graph."""

    source_id: str
    target_id: str
    relation: str  # "supports", "contradicts", "reminds_of", "derived_from"
    weight: float = 1.0
    id: str = field(default_factory=_uuid)
    timestamp: datetime = field(default_factory=_now)


@dataclass
class RecallResult:
    """A single result from hybrid retrieval, with provenance."""

    content: str
    layer: str  # "episode", "concept", "fact", "belief"
    score: float
    confidence: float
    source_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
