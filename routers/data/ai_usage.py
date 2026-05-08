"""
Router for AIUsageLog read-only list + append-only create.
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
from models.all_models import AIUsageLog

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class AIUsageOut(BaseModel):
    id: str
    workspace_id: str
    user_id: Optional[str] = None
    action_type: str
    provider: Optional[str] = None
    mode: Optional[str] = None
    model: Optional[str] = None
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    status: str
    cache_hit: bool
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AIUsageCreate(BaseModel):
    action_type: str
    provider: Optional[str] = None
    mode: Optional[str] = None
    model: Optional[str] = None
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    estimated_cost: Optional[float] = 0.0
    status: Optional[str] = "success"
    cache_hit: Optional[bool] = False
    latency_ms: Optional[int] = 0


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[AIUsageOut])
def list_ai_usage(
    limit: int = 100,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    return (
        db.query(AIUsageLog)
        .filter(AIUsageLog.workspace_id == ctx["workspace_id"])
        .order_by(AIUsageLog.created_at.desc())
        .limit(limit)
        .all()
    )


@router.post("", response_model=AIUsageOut, status_code=201)
def log_ai_usage(
    body: AIUsageCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    entry = AIUsageLog(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        user_id=ctx["user_id"],
        **body.model_dump(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
