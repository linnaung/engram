"""Context provider: pluggable domain ontology for grounding facts.

A ContextProvider gives Engram domain knowledge:
  - What types of entities exist (Protein, Gene, Language)
  - How types relate (Protein is_a Molecule is_a Entity)
  - What predicates are valid (inhibits: Molecule -> Molecule)
  - Entity aliases (TP53 -> p53, python3 -> Python)

Without a context, Engram still extracts untyped triples.
With a context, triples get grounded, validated, and disambiguated.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EntityInfo:
    """Known entity with its canonical name, type, and aliases."""
    canonical: str
    type: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class PredicateInfo:
    """Known predicate with domain and range type constraints."""
    name: str
    domain: str  # subject must be this type (or subtype)
    range: str   # object must be this type (or subtype)


class ContextProvider(ABC):
    """Abstract interface for domain ontology providers."""

    @abstractmethod
    def resolve_entity(self, text: str) -> EntityInfo | None:
        """Resolve a text mention to a canonical entity.

        Handles aliases: "TP53" -> EntityInfo("p53", "Protein", ["TP53", ...])
        Returns None if entity is not in the ontology.
        """

    @abstractmethod
    def get_predicate(self, name: str) -> PredicateInfo | None:
        """Look up a predicate by name. Returns None if unknown."""

    @abstractmethod
    def is_subtype(self, child: str, parent: str) -> bool:
        """Check if child type is a subtype of (or equal to) parent type.

        Example: is_subtype("Protein", "Molecule") -> True
        """

    @abstractmethod
    def validate_triple(self, subject_type: str, predicate: str, object_type: str) -> bool:
        """Check if a triple is valid given the ontology constraints.

        Verifies subject type matches predicate domain,
        and object type matches predicate range.
        """

    @abstractmethod
    def list_types(self) -> list[str]:
        """List all known types."""

    @abstractmethod
    def list_predicates(self) -> list[str]:
        """List all known predicates."""

    @abstractmethod
    def get_type_hierarchy(self, type_name: str) -> list[str]:
        """Get the type hierarchy from the given type up to root.

        Example: get_type_hierarchy("Protein") -> ["Protein", "Molecule", "Entity"]
        """


class SimpleContext(ContextProvider):
    """In memory context provider loaded from a dictionary.

    This is the Phase 1 implementation. It loads a flat vocabulary
    from a JSON structure and provides type checking, entity resolution,
    and predicate validation.
    """

    def __init__(self) -> None:
        self._types: dict[str, str | None] = {}   # type -> parent_type
        self._predicates: dict[str, PredicateInfo] = {}
        self._entities: dict[str, EntityInfo] = {}
        self._alias_map: dict[str, str] = {}  # lowercase alias -> canonical name

    def add_type(self, name: str, parent: str | None = None) -> None:
        """Register a type in the hierarchy."""
        self._types[name] = parent

    def add_predicate(self, name: str, domain: str, range_type: str) -> None:
        """Register a predicate with domain/range constraints."""
        self._predicates[name] = PredicateInfo(name=name, domain=domain, range=range_type)

    def add_entity(self, canonical: str, type_name: str, aliases: list[str] | None = None) -> None:
        """Register a known entity with optional aliases."""
        aliases = aliases or []
        info = EntityInfo(canonical=canonical, type=type_name, aliases=aliases)
        self._entities[canonical.lower()] = info
        self._alias_map[canonical.lower()] = canonical
        for alias in aliases:
            self._alias_map[alias.lower()] = canonical

    def resolve_entity(self, text: str) -> EntityInfo | None:
        key = text.lower().strip()
        canonical = self._alias_map.get(key)
        if canonical is None:
            return None
        return self._entities.get(canonical.lower())

    def get_predicate(self, name: str) -> PredicateInfo | None:
        return self._predicates.get(name.lower()) or self._predicates.get(name)

    def is_subtype(self, child: str, parent: str) -> bool:
        if child == parent:
            return True
        current = child
        visited = set()
        while current in self._types:
            if current in visited:
                break  # cycle protection
            visited.add(current)
            parent_type = self._types[current]
            if parent_type is None:
                return False
            if parent_type == parent:
                return True
            current = parent_type
        return False

    def validate_triple(self, subject_type: str, predicate: str, object_type: str) -> bool:
        pred_info = self.get_predicate(predicate)
        if pred_info is None:
            return True  # unknown predicate, allow by default

        domain_ok = self.is_subtype(subject_type, pred_info.domain) if subject_type else True
        range_ok = self.is_subtype(object_type, pred_info.range) if object_type else True
        return domain_ok and range_ok

    def list_types(self) -> list[str]:
        return sorted(self._types.keys())

    def list_predicates(self) -> list[str]:
        return sorted(self._predicates.keys())

    def get_type_hierarchy(self, type_name: str) -> list[str]:
        hierarchy = []
        current = type_name
        visited = set()
        while current and current not in visited:
            hierarchy.append(current)
            visited.add(current)
            current = self._types.get(current)
        return hierarchy
