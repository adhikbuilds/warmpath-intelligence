"""
Router for RelationshipEdge (graph edges used by BFS pathfinding).
All endpoints are scoped to the requesting user's workspace.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_context import get_workspace_context
from database import get_db
from models.all_models import RelationshipEdge

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class EdgeOut(BaseModel):
    id: str
    workspace_id: str
    from_type: str
    from_id: str
    from_name: str
    to_type: str
    to_id: str
    to_name: str
    relationship_type: str
    strength_score: int
    evidence: Optional[str] = None
    source: Optional[str] = None
    last_interaction_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EdgeCreate(BaseModel):
    from_type: str
    from_id: str
    from_name: str
    to_type: str
    to_id: str
    to_name: str
    relationship_type: str
    strength_score: Optional[int] = 50
    evidence: Optional[str] = None
    source: Optional[str] = None
    last_interaction_at: Optional[datetime] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[EdgeOut])
def list_edges(
    from_id: Optional[str] = None,
    to_id: Optional[str] = None,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    q = db.query(RelationshipEdge).filter(RelationshipEdge.workspace_id == ctx["workspace_id"])
    if from_id:
        q = q.filter(RelationshipEdge.from_id == from_id)
    if to_id:
        q = q.filter(RelationshipEdge.to_id == to_id)
    return q.order_by(RelationshipEdge.strength_score.desc()).all()


@router.post("", response_model=EdgeOut, status_code=201)
def create_edge(
    body: EdgeCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    edge = RelationshipEdge(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        **body.model_dump(),
    )
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge


@router.get("/{id}", response_model=EdgeOut)
def get_edge(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(RelationshipEdge)
        .filter(
            RelationshipEdge.id == id,
            RelationshipEdge.workspace_id == ctx["workspace_id"],
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Edge not found")
    return obj


@router.delete("/{id}")
def delete_edge(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(RelationshipEdge)
        .filter(
            RelationshipEdge.id == id,
            RelationshipEdge.workspace_id == ctx["workspace_id"],
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Edge not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
