"""
Relationship graph BFS engine Python port of src/lib/graph/index.ts.

Computes warm paths between team members and target contacts.
Edge warmth = relationship_type_weight × recency_decay × strength_score.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ─── Relationship type base weights ───────────────────────────────────────────

TYPE_WEIGHTS: dict[str, float] = {
    "intro_history": 1.0,
    "coworker_connection": 0.85,
    "calendar_meeting": 0.8,
    "email_history": 0.75,
    "warm_path": 0.7,
    "crm_owner": 0.65,
    "linkedin_connection": 0.55,
}

STALE_DAYS = 90  # edges older than this are considered stale


# ─── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class GraphNode:
    id: str
    name: str
    type: str  # "team_member" | "contact" | "account"


@dataclass
class GraphEdge:
    id: str
    from_id: str
    to_id: str
    from_name: str
    to_name: str
    relationship_type: str
    strength_score: float  # 0–100
    last_interaction_at: str  # ISO datetime string


@dataclass
class PathNode:
    id: str
    name: str
    type: str


@dataclass
class WarmPath:
    nodes: list[PathNode]
    warmth: float  # 0–100 composite score
    hop_count: int
    is_stale: bool


# ─── Warmth computation ───────────────────────────────────────────────────────


def compute_edge_warmth(edge: GraphEdge) -> float:
    type_weight = TYPE_WEIGHTS.get(edge.relationship_type, 0.5)
    strength = edge.strength_score / 100.0

    # Recency decay: full weight if <30 days, linear decay to 0.3 at 90+ days
    try:
        last = datetime.fromisoformat(edge.last_interaction_at.replace("Z", "+00:00"))
    except ValueError:
        last = datetime.now(timezone.utc)

    days = (datetime.now(timezone.utc) - last).days
    if days <= 30:
        recency = 1.0
    elif days >= STALE_DAYS:
        recency = 0.3
    else:
        recency = 1.0 - (0.7 * (days - 30) / 60.0)

    return round(type_weight * recency * strength * 100, 1)


# ─── Graph ────────────────────────────────────────────────────────────────────


class RelationshipGraph:
    def __init__(self) -> None:
        self._adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}

    def add_node(self, node: GraphNode) -> None:
        self._nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        warmth = compute_edge_warmth(edge)
        entry = {
            "edge_id": edge.id,
            "neighbor_id": edge.to_id,
            "neighbor_name": edge.to_name,
            "warmth": warmth,
            "relationship_type": edge.relationship_type,
        }
        reverse_entry = {
            "edge_id": edge.id,
            "neighbor_id": edge.from_id,
            "neighbor_name": edge.from_name,
            "warmth": warmth,
            "relationship_type": edge.relationship_type,
        }
        self._adjacency[edge.from_id].append(entry)
        self._adjacency[edge.to_id].append(reverse_entry)
        self._edges[edge.id] = edge

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 3,
        top_k: int = 3,
        min_warmth: float = 0,
    ) -> list[WarmPath]:
        """BFS from source to target, returning up to top_k paths sorted by warmth."""
        if source_id not in self._nodes or target_id not in self._nodes:
            return []

        found: list[WarmPath] = []
        # State: (current_node_id, path_so_far, min_warmth_on_path)
        queue: list[tuple[str, list[str], float]] = [(source_id, [source_id], 100.0)]
        visited_paths: set[str] = set()

        while queue and len(found) < top_k * 3:
            current_id, path, path_warmth = queue.pop(0)

            if current_id == target_id and len(path) > 1:
                # Length penalty: each extra hop reduces by 10%
                hop_penalty = 0.9 ** (len(path) - 2)
                final_warmth = path_warmth * hop_penalty
                if final_warmth >= min_warmth:
                    path_key = "->".join(path)
                    if path_key not in visited_paths:
                        visited_paths.add(path_key)
                        nodes = [
                            PathNode(
                                id=nid,
                                name=self._nodes[nid].name if nid in self._nodes else nid,
                                type=self._nodes[nid].type if nid in self._nodes else "unknown",
                            )
                            for nid in path
                        ]
                        is_stale = any(
                            self._is_edge_stale(path[i], path[i + 1])
                            for i in range(len(path) - 1)
                        )
                        found.append(
                            WarmPath(
                                nodes=nodes,
                                warmth=round(final_warmth, 1),
                                hop_count=len(path) - 1,
                                is_stale=is_stale,
                            )
                        )
                continue

            if len(path) >= max_hops + 1:
                continue

            for neighbor in self._adjacency.get(current_id, []):
                nid = neighbor["neighbor_id"]
                if nid in path:
                    continue
                new_warmth = min(path_warmth, neighbor["warmth"])
                queue.append((nid, path + [nid], new_warmth))

        # Sort by warmth descending
        found.sort(key=lambda p: p.warmth, reverse=True)
        return found[:top_k]

    def _is_edge_stale(self, from_id: str, to_id: str) -> bool:
        for entry in self._adjacency.get(from_id, []):
            if entry["neighbor_id"] == to_id:
                edge = self._edges.get(entry["edge_id"])
                if edge:
                    try:
                        last = datetime.fromisoformat(
                            edge.last_interaction_at.replace("Z", "+00:00")
                        )
                        return (datetime.now(timezone.utc) - last).days > STALE_DAYS
                    except ValueError:
                        return False
        return False

    def compute_coverage(
        self,
        source_ids: list[str],
        target_ids: list[str],
        max_hops: int = 3,
    ) -> dict[str, Any]:
        """
        For each target, compute best path from any source.
        Returns coverage stats and per-target gap type.
        """
        results = []
        now = datetime.now(timezone.utc)

        for target_id in target_ids:
            best: WarmPath | None = None
            for src_id in source_ids:
                paths = self.find_paths(src_id, target_id, max_hops=max_hops, top_k=1)
                if paths and (best is None or paths[0].warmth > best.warmth):
                    best = paths[0]

            if best is None:
                gap_type = "no_path"
            elif best.is_stale:
                gap_type = "stale_path"
            elif best.warmth < 60:
                gap_type = "cold_path"
            else:
                gap_type = "warm"

            results.append(
                {
                    "target_id": target_id,
                    "best_path": (
                        {
                            "nodes": [
                                {"id": n.id, "name": n.name, "type": n.type}
                                for n in best.nodes
                            ],
                            "warmth": best.warmth,
                            "hop_count": best.hop_count,
                            "is_stale": best.is_stale,
                        }
                        if best
                        else None
                    ),
                    "gap_type": gap_type,
                }
            )

        warm_count = sum(1 for r in results if r["gap_type"] == "warm")
        coverage_pct = round(warm_count / len(target_ids) * 100) if target_ids else 0

        return {
            "coverage_pct": coverage_pct,
            "warm_count": warm_count,
            "total_count": len(target_ids),
            "targets": results,
        }


def build_graph(edges: list[dict[str, Any]], team_nodes: list[dict[str, Any]]) -> RelationshipGraph:
    g = RelationshipGraph()

    for node_data in team_nodes:
        g.add_node(
            GraphNode(
                id=node_data["id"],
                name=node_data["name"],
                type=node_data.get("type", "team_member"),
            )
        )

    for e in edges:
        graph_edge = GraphEdge(
            id=e.get("id", f"{e['fromId']}-{e['toId']}"),
            from_id=e["fromId"],
            to_id=e["toId"],
            from_name=e.get("fromName", ""),
            to_name=e.get("toName", ""),
            relationship_type=e.get("relationshipType", "linkedin_connection"),
            strength_score=float(e.get("strengthScore", 50)),
            last_interaction_at=e.get("lastInteractionAt", datetime.now(timezone.utc).isoformat()),
        )
        # Auto-register from/to nodes if not already in graph
        if graph_edge.from_id not in g._nodes:
            g.add_node(GraphNode(id=graph_edge.from_id, name=graph_edge.from_name, type="contact"))
        if graph_edge.to_id not in g._nodes:
            g.add_node(GraphNode(id=graph_edge.to_id, name=graph_edge.to_name, type="contact"))
        g.add_edge(graph_edge)

    return g
