"""
CRUD router for BizAccount (target accounts).
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
from models.all_models import BizAccount

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class AccountOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    stage: str
    fit_score: int
    intent_score: int
    warmth_score: int
    logo_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[str] = "prospect"
    fit_score: Optional[int] = 0
    intent_score: Optional[int] = 0
    warmth_score: Optional[int] = 0
    logo_url: Optional[str] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[str] = None
    fit_score: Optional[int] = None
    intent_score: Optional[int] = None
    warmth_score: Optional[int] = None
    logo_url: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[AccountOut])
def list_accounts(
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    return (
        db.query(BizAccount)
        .filter(BizAccount.workspace_id == ctx["workspace_id"])
        .order_by(BizAccount.name)
        .all()
    )


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    body: AccountCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    account = BizAccount(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        **body.model_dump(),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/{id}", response_model=AccountOut)
def get_account(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(BizAccount)
        .filter(BizAccount.id == id, BizAccount.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Account not found")
    return obj


@router.put("/{id}", response_model=AccountOut)
def update_account(
    id: str,
    body: AccountUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(BizAccount)
        .filter(BizAccount.id == id, BizAccount.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Account not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}")
def delete_account(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(BizAccount)
        .filter(BizAccount.id == id, BizAccount.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
