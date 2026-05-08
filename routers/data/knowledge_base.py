"""
CRUD router for KnowledgeBaseItem.
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
from models.all_models import KnowledgeBaseItem

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class KBItemOut(BaseModel):
    id: str
    workspace_id: str
    title: str
    type: str
    content: str
    source: Optional[str] = None
    tags_json: Optional[str] = None
    confidence_score: int
    approved_for_ai: bool
    used_in_messages: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBItemCreate(BaseModel):
    title: str
    type: str
    content: str
    source: Optional[str] = None
    tags_json: Optional[str] = None
    confidence_score: Optional[int] = 80
    approved_for_ai: Optional[bool] = True


class KBItemUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    tags_json: Optional[str] = None
    confidence_score: Optional[int] = None
    approved_for_ai: Optional[bool] = None
    used_in_messages: Optional[int] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[KBItemOut])
def list_kb_items(
    type: Optional[str] = None,
    approved_for_ai: Optional[bool] = None,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    q = db.query(KnowledgeBaseItem).filter(KnowledgeBaseItem.workspace_id == ctx["workspace_id"])
    if type:
        q = q.filter(KnowledgeBaseItem.type == type)
    if approved_for_ai is not None:
        q = q.filter(KnowledgeBaseItem.approved_for_ai == approved_for_ai)
    return q.order_by(KnowledgeBaseItem.title).all()


@router.post("", response_model=KBItemOut, status_code=201)
def create_kb_item(
    body: KBItemCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    item = KnowledgeBaseItem(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        **body.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{id}", response_model=KBItemOut)
def get_kb_item(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(KnowledgeBaseItem)
        .filter(KnowledgeBaseItem.id == id, KnowledgeBaseItem.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Knowledge base item not found")
    return obj


@router.put("/{id}", response_model=KBItemOut)
def update_kb_item(
    id: str,
    body: KBItemUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(KnowledgeBaseItem)
        .filter(KnowledgeBaseItem.id == id, KnowledgeBaseItem.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Knowledge base item not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}")
def delete_kb_item(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(KnowledgeBaseItem)
        .filter(KnowledgeBaseItem.id == id, KnowledgeBaseItem.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Knowledge base item not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
