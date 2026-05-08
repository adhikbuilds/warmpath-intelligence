"""
CRUD router for Contact.
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
from models.all_models import Contact

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class ContactOut(BaseModel):
    id: str
    workspace_id: str
    account_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    seniority: Optional[str] = None
    department: Optional[str] = None
    persona: Optional[str] = None
    fit_score: int
    warmth_score: int
    engagement_score: int
    consent_status: str
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactCreate(BaseModel):
    name: str
    account_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    seniority: Optional[str] = None
    department: Optional[str] = None
    persona: Optional[str] = None
    fit_score: Optional[int] = 0
    warmth_score: Optional[int] = 0
    engagement_score: Optional[int] = 0
    consent_status: Optional[str] = "unknown"
    avatar_url: Optional[str] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    account_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    seniority: Optional[str] = None
    department: Optional[str] = None
    persona: Optional[str] = None
    fit_score: Optional[int] = None
    warmth_score: Optional[int] = None
    engagement_score: Optional[int] = None
    consent_status: Optional[str] = None
    avatar_url: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ContactOut])
def list_contacts(
    account_id: Optional[str] = None,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    q = db.query(Contact).filter(Contact.workspace_id == ctx["workspace_id"])
    if account_id:
        q = q.filter(Contact.account_id == account_id)
    return q.order_by(Contact.name).all()


@router.post("", response_model=ContactOut, status_code=201)
def create_contact(
    body: ContactCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    contact = Contact(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        **body.model_dump(),
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("/{id}", response_model=ContactOut)
def get_contact(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Contact)
        .filter(Contact.id == id, Contact.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Contact not found")
    return obj


@router.put("/{id}", response_model=ContactOut)
def update_contact(
    id: str,
    body: ContactUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Contact)
        .filter(Contact.id == id, Contact.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Contact not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}")
def delete_contact(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Contact)
        .filter(Contact.id == id, Contact.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
