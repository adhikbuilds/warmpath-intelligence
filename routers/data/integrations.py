"""
Router for IntegrationConnection (Gmail, LinkedIn, Slack, HubSpot, etc.).
GET list, PUT update status, POST /{id}/connect-demo for demo mode toggle.
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
from models.all_models import IntegrationConnection

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class IntegrationOut(BaseModel):
    id: str
    workspace_id: str
    provider: str
    channel: Optional[str] = None
    display_name: str
    description: Optional[str] = None
    status: str
    auth_type: Optional[str] = None
    capabilities_json: Optional[str] = None
    icon_color: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    sync_status: Optional[str] = None
    demo_mode: bool
    health_score: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IntegrationUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    auth_type: Optional[str] = None
    capabilities_json: Optional[str] = None
    icon_color: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    sync_status: Optional[str] = None
    demo_mode: Optional[bool] = None
    health_score: Optional[int] = None


class IntegrationCreate(BaseModel):
    provider: str
    display_name: str
    channel: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = "disconnected"
    auth_type: Optional[str] = None
    capabilities_json: Optional[str] = None
    icon_color: Optional[str] = None
    demo_mode: Optional[bool] = False


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[IntegrationOut])
def list_integrations(
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    return (
        db.query(IntegrationConnection)
        .filter(IntegrationConnection.workspace_id == ctx["workspace_id"])
        .order_by(IntegrationConnection.display_name)
        .all()
    )


@router.post("", response_model=IntegrationOut, status_code=201)
def create_integration(
    body: IntegrationCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    # Check for existing integration with same provider
    existing = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.workspace_id == ctx["workspace_id"],
            IntegrationConnection.provider == body.provider,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Integration for provider '{body.provider}' already exists")

    integration = IntegrationConnection(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        **body.model_dump(),
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


@router.get("/{id}", response_model=IntegrationOut)
def get_integration(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.id == id,
            IntegrationConnection.workspace_id == ctx["workspace_id"],
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Integration not found")
    return obj


@router.put("/{id}", response_model=IntegrationOut)
def update_integration(
    id: str,
    body: IntegrationUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.id == id,
            IntegrationConnection.workspace_id == ctx["workspace_id"],
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Integration not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{id}/connect-demo", response_model=IntegrationOut)
def connect_demo(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    """Toggle an integration into demo mode (simulated connection)."""
    obj = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.id == id,
            IntegrationConnection.workspace_id == ctx["workspace_id"],
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Integration not found")
    obj.demo_mode = True
    obj.status = "connected"
    obj.sync_status = "synced"
    obj.last_sync_at = datetime.now(timezone.utc)
    obj.health_score = 100
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{id}/disconnect", response_model=IntegrationOut)
def disconnect_integration(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    """Disconnect an integration (set status to disconnected, clear demo mode)."""
    obj = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.id == id,
            IntegrationConnection.workspace_id == ctx["workspace_id"],
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Integration not found")
    obj.status = "disconnected"
    obj.demo_mode = False
    obj.sync_status = None
    obj.last_sync_at = None
    obj.health_score = None
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj
