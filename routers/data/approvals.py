"""
Router for Approval workflow list, create, approve, reject.
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
from models.all_models import Approval

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class ApprovalOut(BaseModel):
    id: str
    workspace_id: str
    asset_id: Optional[str] = None
    message_id: Optional[str] = None
    user_id: str
    status: str
    edited_body: Optional[str] = None
    feedback: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalCreate(BaseModel):
    asset_id: Optional[str] = None
    message_id: Optional[str] = None
    # user_id taken from context


class ApproveBody(BaseModel):
    edited_body: Optional[str] = None


class RejectBody(BaseModel):
    feedback: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ApprovalOut])
def list_approvals(
    status: Optional[str] = None,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    q = db.query(Approval).filter(Approval.workspace_id == ctx["workspace_id"])
    if status:
        q = q.filter(Approval.status == status)
    return q.order_by(Approval.created_at.desc()).all()


@router.post("", response_model=ApprovalOut, status_code=201)
def create_approval(
    body: ApprovalCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    approval = Approval(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        user_id=ctx["user_id"],
        asset_id=body.asset_id,
        message_id=body.message_id,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


@router.get("/{id}", response_model=ApprovalOut)
def get_approval(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Approval)
        .filter(Approval.id == id, Approval.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Approval not found")
    return obj


@router.post("/{id}/approve", response_model=ApprovalOut)
def approve(
    id: str,
    body: ApproveBody,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    approval = (
        db.query(Approval)
        .filter(Approval.id == id, Approval.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval.status = "approved"
    approval.decided_at = datetime.now(timezone.utc)
    if body.edited_body is not None:
        approval.edited_body = body.edited_body
    db.commit()
    db.refresh(approval)
    return approval


@router.post("/{id}/reject", response_model=ApprovalOut)
def reject(
    id: str,
    body: RejectBody,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    approval = (
        db.query(Approval)
        .filter(Approval.id == id, Approval.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval.status = "rejected"
    approval.decided_at = datetime.now(timezone.utc)
    if body.feedback is not None:
        approval.feedback = body.feedback
    db.commit()
    db.refresh(approval)
    return approval
