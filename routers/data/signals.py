"""
CRUD router for Signal (buying signals, job postings, funding rounds, etc.).
Mounted at /api/signals separate from the intelligence /signals/ingest endpoint.
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
from models.all_models import Signal

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class SignalOut(BaseModel):
    id: str
    workspace_id: str
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    type: str
    title: str
    description: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    urgency_score: int
    confidence_score: int
    detected_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalCreate(BaseModel):
    type: str
    title: str
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    urgency_score: Optional[int] = 50
    confidence_score: Optional[int] = 70
    detected_at: Optional[datetime] = None


class SignalUpdate(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    urgency_score: Optional[int] = None
    confidence_score: Optional[int] = None
    detected_at: Optional[datetime] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[SignalOut])
def list_signals(
    account_id: Optional[str] = None,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    q = db.query(Signal).filter(Signal.workspace_id == ctx["workspace_id"])
    if account_id:
        q = q.filter(Signal.account_id == account_id)
    return q.order_by(Signal.detected_at.desc()).all()


@router.post("", response_model=SignalOut, status_code=201)
def create_signal(
    body: SignalCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    data = body.model_dump()
    if data.get("detected_at") is None:
        data["detected_at"] = datetime.now(timezone.utc)
    signal = Signal(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        **data,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


@router.get("/{id}", response_model=SignalOut)
def get_signal(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Signal)
        .filter(Signal.id == id, Signal.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Signal not found")
    return obj


@router.put("/{id}", response_model=SignalOut)
def update_signal(
    id: str,
    body: SignalUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Signal)
        .filter(Signal.id == id, Signal.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Signal not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}")
def delete_signal(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Signal)
        .filter(Signal.id == id, Signal.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Signal not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
