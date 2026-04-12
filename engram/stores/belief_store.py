"""L3 Belief Store — abstract principles in a NetworkX graph with SQLite persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from engram.core.types import Belief, Edge
from engram.core.decay import compute_confidence
from engram.stores.base import BaseStore


class BeliefStore(BaseStore):
    """NetworkX + JSON file store for belief-level memories (L3).

    Beliefs are high-level principles synthesized from concept patterns.
    They form a directed graph where edges represent relationships
    like "supports", "contradicts", "reminds_of", "derived_from".
    """

    def __init__(self, graph_path: Path) -> None:
        self.graph_path = graph_path
        self._graph: nx.DiGraph | None = None

    def initialize(self) -> None:
        if self.graph_path.exists():
            self._graph = self._load_graph()
        else:
            self._graph = nx.DiGraph()

    def close(self) -> None:
        self._persist()
        self._graph = None

    @property
    def graph(self) -> nx.DiGraph:
        if self._graph is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")
        return self._graph

    def add_belief(self, belief: Belief) -> Belief:
        """Add a belief as a node in the graph."""
        self.graph.add_node(
            belief.id,
            principle=belief.principle,
            supporting_concept_ids=belief.supporting_concept_ids,
            contradicting_concept_ids=belief.contradicting_concept_ids,
            timestamp=belief.timestamp.isoformat(),
            initial_confidence=belief.confidence,
            half_life_days=belief.half_life_days,
            reinforcement_count=0,
            metadata=belief.metadata,
        )
        self._persist()
        return belief

    def add_edge(self, edge: Edge) -> Edge:
        """Add a relationship between two beliefs."""
        if edge.source_id not in self.graph:
            raise ValueError(f"Source belief {edge.source_id} not found")
        if edge.target_id not in self.graph:
            raise ValueError(f"Target belief {edge.target_id} not found")

        self.graph.add_edge(
            edge.source_id,
            edge.target_id,
            id=edge.id,
            relation=edge.relation,
            weight=edge.weight,
            timestamp=edge.timestamp.isoformat(),
        )
        self._persist()
        return edge

    def get_belief(self, belief_id: str) -> Belief | None:
        """Retrieve a single belief by ID."""
        if belief_id not in self.graph:
            return None
        return self._node_to_belief(belief_id)

    def get_related(
        self,
        belief_id: str,
        relation: str | None = None,
        max_depth: int = 2,
    ) -> list[tuple[Belief, str, float]]:
        """Find beliefs related to a given belief via graph traversal.

        Returns list of (belief, relation_type, edge_weight) tuples.
        Traverses up to max_depth hops.
        """
        if belief_id not in self.graph:
            return []

        visited: set[str] = {belief_id}
        results: list[tuple[Belief, str, float]] = []
        frontier = [(belief_id, 0)]

        while frontier:
            current_id, depth = frontier.pop(0)
            if depth >= max_depth:
                continue

            # Check outgoing edges
            for _, target_id, edge_data in self.graph.edges(current_id, data=True):
                if target_id in visited:
                    continue
                edge_relation = edge_data.get("relation", "related")
                if relation is not None and edge_relation != relation:
                    continue

                visited.add(target_id)
                belief = self._node_to_belief(target_id)
                if belief:
                    results.append((belief, edge_relation, edge_data.get("weight", 1.0)))
                frontier.append((target_id, depth + 1))

            # Check incoming edges too (beliefs that point to this one)
            for source_id, _, edge_data in self.graph.in_edges(current_id, data=True):
                if source_id in visited:
                    continue
                edge_relation = edge_data.get("relation", "related")
                if relation is not None and edge_relation != relation:
                    continue

                visited.add(source_id)
                belief = self._node_to_belief(source_id)
                if belief:
                    results.append((belief, edge_relation, edge_data.get("weight", 1.0)))
                frontier.append((source_id, depth + 1))

        return results

    def list_beliefs(
        self,
        min_confidence: float = 0.05,
        now: datetime | None = None,
    ) -> list[Belief]:
        """List all beliefs above the confidence threshold."""
        if now is None:
            now = datetime.now(timezone.utc)

        results = []
        for node_id in self.graph.nodes:
            belief = self._node_to_belief(node_id)
            if belief is None:
                continue
            data = self.graph.nodes[node_id]
            current_conf = compute_confidence(
                initial_confidence=data["initial_confidence"],
                created_at=datetime.fromisoformat(data["timestamp"]),
                half_life=belief.half_life,
                reinforcement_count=data.get("reinforcement_count", 0),
                now=now,
            )
            if current_conf >= min_confidence:
                belief.confidence = current_conf
                results.append(belief)

        return results

    def reinforce(self, belief_id: str) -> None:
        """Increment reinforcement count for a belief."""
        if belief_id in self.graph:
            data = self.graph.nodes[belief_id]
            data["reinforcement_count"] = data.get("reinforcement_count", 0) + 1
            self._persist()

    def delete_belief(self, belief_id: str) -> bool:
        """Remove a belief and all its edges."""
        if belief_id not in self.graph:
            return False
        self.graph.remove_node(belief_id)
        self._persist()
        return True

    def count(self) -> int:
        """Total number of beliefs."""
        return self.graph.number_of_nodes()

    def edge_count(self) -> int:
        """Total number of edges."""
        return self.graph.number_of_edges()

    def _node_to_belief(self, node_id: str) -> Belief | None:
        data = self.graph.nodes.get(node_id)
        if data is None:
            return None
        return Belief(
            id=node_id,
            principle=data["principle"],
            supporting_concept_ids=data.get("supporting_concept_ids", []),
            contradicting_concept_ids=data.get("contradicting_concept_ids", []),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            confidence=data["initial_confidence"],
            half_life_days=data["half_life_days"],
            metadata=data.get("metadata", {}),
        )

    def _persist(self) -> None:
        """Save graph to JSON file."""
        if self._graph is None:
            return
        data = nx.node_link_data(self._graph)
        with open(self.graph_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _load_graph(self) -> nx.DiGraph:
        """Load graph from JSON file."""
        with open(self.graph_path) as f:
            data = json.load(f)
        return nx.node_link_graph(data, directed=True)
