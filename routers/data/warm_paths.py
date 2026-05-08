"""
Router for WarmPath (BFS-computed intro paths).
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
from models.all_models import WarmPath

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class WarmPathOut(BaseModel):
    id: str
    workspace_id: str
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    path_json: str
    explanation: Optional[str] = None
    warmth_score: int
    confidence_score: int
    recommended_intro_person: Optional[str] = None
    recommended_channel: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WarmPathCreate(BaseModel):
    path_json: str  # JSON string representing the path nodes
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    explanation: Optional[str] = None
    warmth_score: Optional[int] = 0
    confidence_score: Optional[int] = 0
    recommended_intro_person: Optional[str] = None
    recommended_channel: Optional[str] = None
    status: Optional[str] = "active"


class WarmPathUpdate(BaseModel):
    path_json: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    explanation: Optional[str] = None
    warmth_score: Optional[int] = None
    confidence_score: Optional[int] = None
    recommended_intro_person: Optional[str] = None
    recommended_channel: Optional[str] = None
    status: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[WarmPathOut])
def list_warm_paths(
    account_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    status: Optional[str] = None,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    q = db.query(WarmPath).filter(WarmPath.workspace_id == ctx["workspace_id"])
    if account_id:
        q = q.filter(WarmPath.account_id == account_id)
    if contact_id:
        q = q.filter(WarmPath.contact_id == contact_id)
    if status:
        q = q.filter(WarmPath.status == status)
    return q.order_by(WarmPath.warmth_score.desc()).all()


@router.post("", response_model=WarmPathOut, status_code=201)
def create_warm_path(
    body: WarmPathCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    path = WarmPath(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        **body.model_dump(),
    )
    db.add(path)
    db.commit()
    db.refresh(path)
    return path


@router.get("/{id}", response_model=WarmPathOut)
def get_warm_path(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(WarmPath)
        .filter(WarmPath.id == id, WarmPath.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Warm path not found")
    return obj


@router.put("/{id}", response_model=WarmPathOut)
def update_warm_path(
    id: str,
    body: WarmPathUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(WarmPath)
        .filter(WarmPath.id == id, WarmPath.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Warm path not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj
