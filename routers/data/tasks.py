"""
CRUD router for Task.
All endpoints are scoped to the requesting user's workspace.
Supports optional ?status filter on the list endpoint.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_context import get_workspace_context
from database import get_db
from models.all_models import Task

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class TaskOut(BaseModel):
    id: str
    workspace_id: str
    owner_id: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    campaign_id: Optional[str] = None
    type: str
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    due_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    type: str
    title: str
    owner_id: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    campaign_id: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    status: Optional[str] = "pending"
    due_at: Optional[datetime] = None


class TaskUpdate(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    owner_id: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    campaign_id: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_at: Optional[datetime] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[TaskOut])
def list_tasks(
    status: Optional[str] = None,
    owner_id: Optional[str] = None,
    account_id: Optional[str] = None,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    q = db.query(Task).filter(Task.workspace_id == ctx["workspace_id"])
    if status:
        q = q.filter(Task.status == status)
    if owner_id:
        q = q.filter(Task.owner_id == owner_id)
    if account_id:
        q = q.filter(Task.account_id == account_id)
    return q.order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc()).all()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    body: TaskCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    task = Task(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        **body.model_dump(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{id}", response_model=TaskOut)
def get_task(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Task)
        .filter(Task.id == id, Task.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Task not found")
    return obj


@router.put("/{id}", response_model=TaskOut)
def update_task(
    id: str,
    body: TaskUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Task)
        .filter(Task.id == id, Task.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Task not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{id}", response_model=TaskOut)
def patch_task(
    id: str,
    body: TaskUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Task)
        .filter(Task.id == id, Task.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Task not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}")
def delete_task(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Task)
        .filter(Task.id == id, Task.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
