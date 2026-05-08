"""
Router for AuditLog read-only list + append-only create.
All endpoints are scoped to the requesting user's workspace.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_context import get_workspace_context
from database import get_db
from models.all_models import AuditLog

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class AuditLogOut(BaseModel):
    id: str
    workspace_id: str
    actor_user_id: Optional[str] = None
    actor_name: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogCreate(BaseModel):
    action: str
    actor_name: Optional[str] = None  # defaults to context user name
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    metadata_json: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    entity_type: Optional[str] = None,
    limit: int = 100,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog).filter(AuditLog.workspace_id == ctx["workspace_id"])
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    return q.order_by(AuditLog.created_at.desc()).limit(limit).all()


@router.post("", response_model=AuditLogOut, status_code=201)
def create_audit_log(
    body: AuditLogCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    entry = AuditLog(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        actor_user_id=ctx["user_id"],
        actor_name=body.actor_name or ctx["user_name"],
        action=body.action,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        entity_name=body.entity_name,
        metadata_json=body.metadata_json,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
