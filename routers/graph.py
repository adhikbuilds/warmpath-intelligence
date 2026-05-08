"""Graph computation endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.graph_engine import build_graph

router = APIRouter()


class ComputePathsRequest(BaseModel):
    edges: list[dict[str, Any]]
    team_nodes: list[dict[str, Any]]
    source_ids: list[str]
    target_id: str
    max_hops: int = 3
    top_k: int = 3
    min_warmth: float = 0


class CoverageRequest(BaseModel):
    edges: list[dict[str, Any]]
    team_nodes: list[dict[str, Any]]
    source_ids: list[str]
    target_ids: list[str]
    max_hops: int = 3


@router.post("/compute-paths")
async def compute_paths(req: ComputePathsRequest):
    """Find warm paths from any team member to a specific target contact."""
    g = build_graph(req.edges, req.team_nodes)

    all_paths = []
    for src_id in req.source_ids:
        paths = g.find_paths(
            src_id, req.target_id, max_hops=req.max_hops, top_k=req.top_k, min_warmth=req.min_warmth
        )
        all_paths.extend(paths)

    # Sort all found paths by warmth and deduplicate
    all_paths.sort(key=lambda p: p.warmth, reverse=True)
    seen: set[str] = set()
    unique = []
    for p in all_paths:
        key = "->".join(n.id for n in p.nodes)
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return {
        "paths": [
            {
                "nodes": [{"id": n.id, "name": n.name, "type": n.type} for n in p.nodes],
                "warmth": p.warmth,
                "hop_count": p.hop_count,
                "is_stale": p.is_stale,
            }
            for p in unique[: req.top_k]
        ],
        "count": len(unique[: req.top_k]),
    }


@router.post("/coverage")
async def compute_coverage(req: CoverageRequest):
    """Compute warm path coverage across all target accounts/contacts."""
    g = build_graph(req.edges, req.team_nodes)
    return g.compute_coverage(req.source_ids, req.target_ids, max_hops=req.max_hops)
