"""
Router for Message (generated outreach messages).
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
from models.all_models import Message

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class MessageOut(BaseModel):
    id: str
    workspace_id: str
    campaign_id: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    warm_path_id: Optional[str] = None
    signal_id: Optional[str] = None
    channel: str
    subject: Optional[str] = None
    body: str
    status: str
    approval_status: str
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    generated_by_ai: bool
    confidence_score: int
    personalization_reason: Optional[str] = None
    intro_request: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    channel: str
    body: str
    campaign_id: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    warm_path_id: Optional[str] = None
    signal_id: Optional[str] = None
    subject: Optional[str] = None
    status: Optional[str] = "draft"
    approval_status: Optional[str] = "pending"
    scheduled_at: Optional[datetime] = None
    generated_by_ai: Optional[bool] = True
    confidence_score: Optional[int] = 0
    personalization_reason: Optional[str] = None
    intro_request: Optional[str] = None


class MessageUpdate(BaseModel):
    channel: Optional[str] = None
    body: Optional[str] = None
    campaign_id: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    warm_path_id: Optional[str] = None
    signal_id: Optional[str] = None
    subject: Optional[str] = None
    status: Optional[str] = None
    approval_status: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    confidence_score: Optional[int] = None
    personalization_reason: Optional[str] = None
    intro_request: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[MessageOut])
def list_messages(
    campaign_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    approval_status: Optional[str] = None,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    q = db.query(Message).filter(Message.workspace_id == ctx["workspace_id"])
    if campaign_id:
        q = q.filter(Message.campaign_id == campaign_id)
    if contact_id:
        q = q.filter(Message.contact_id == contact_id)
    if approval_status:
        q = q.filter(Message.approval_status == approval_status)
    return q.order_by(Message.created_at.desc()).all()


@router.post("", response_model=MessageOut, status_code=201)
def create_message(
    body: MessageCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    message = Message(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        **body.model_dump(),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/{id}", response_model=MessageOut)
def get_message(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Message)
        .filter(Message.id == id, Message.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Message not found")
    return obj


@router.put("/{id}", response_model=MessageOut)
def update_message(
    id: str,
    body: MessageUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Message)
        .filter(Message.id == id, Message.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Message not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj
