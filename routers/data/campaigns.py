"""
CRUD router for Campaign + nested CampaignStep operations.
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
from models.all_models import Campaign, CampaignStep

router = APIRouter()


# ─── Campaign Schemas ─────────────────────────────────────────────────────────


class StepOut(BaseModel):
    id: str
    campaign_id: str
    step_number: int
    channel: str
    action_type: str
    delay_days: int
    asset_type: Optional[str] = None
    approval_required: bool

    model_config = {"from_attributes": True}


class CampaignOut(BaseModel):
    id: str
    workspace_id: str
    owner_id: str
    name: str
    type: str
    goal: Optional[str] = None
    status: str
    target_segment: Optional[str] = None
    channels_json: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    steps: list[StepOut] = []

    model_config = {"from_attributes": True}


class CampaignCreate(BaseModel):
    name: str
    type: str
    goal: Optional[str] = None
    status: Optional[str] = "draft"
    target_segment: Optional[str] = None
    channels_json: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[str] = None
    target_segment: Optional[str] = None
    channels_json: Optional[str] = None


# ─── CampaignStep Schemas ─────────────────────────────────────────────────────


class StepCreate(BaseModel):
    step_number: int
    channel: str
    action_type: str
    delay_days: Optional[int] = 0
    asset_type: Optional[str] = None
    approval_required: Optional[bool] = True


class StepUpdate(BaseModel):
    step_number: Optional[int] = None
    channel: Optional[str] = None
    action_type: Optional[str] = None
    delay_days: Optional[int] = None
    asset_type: Optional[str] = None
    approval_required: Optional[bool] = None


# ─── Campaign Endpoints ───────────────────────────────────────────────────────


@router.get("", response_model=list[CampaignOut])
def list_campaigns(
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    return (
        db.query(Campaign)
        .filter(Campaign.workspace_id == ctx["workspace_id"])
        .order_by(Campaign.created_at.desc())
        .all()
    )


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(
    body: CampaignCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    campaign = Campaign(
        id=uuid.uuid4().hex,
        workspace_id=ctx["workspace_id"],
        owner_id=ctx["user_id"],
        **body.model_dump(),
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/{id}", response_model=CampaignOut)
def get_campaign(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Campaign)
        .filter(Campaign.id == id, Campaign.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return obj


@router.patch("/{id}", response_model=CampaignOut)
@router.put("/{id}", response_model=CampaignOut)
def update_campaign(
    id: str,
    body: CampaignUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Campaign)
        .filter(Campaign.id == id, Campaign.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}")
def delete_campaign(
    id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    obj = (
        db.query(Campaign)
        .filter(Campaign.id == id, Campaign.workspace_id == ctx["workspace_id"])
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}


# ─── Nested CampaignStep Endpoints ───────────────────────────────────────────


def _get_campaign_or_404(campaign_id: str, workspace_id: str, db: Session) -> Campaign:
    obj = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return obj


@router.get("/{campaign_id}/steps", response_model=list[StepOut])
def list_steps(
    campaign_id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    _get_campaign_or_404(campaign_id, ctx["workspace_id"], db)
    return (
        db.query(CampaignStep)
        .filter(CampaignStep.campaign_id == campaign_id)
        .order_by(CampaignStep.step_number)
        .all()
    )


@router.post("/{campaign_id}/steps", response_model=StepOut, status_code=201)
def create_step(
    campaign_id: str,
    body: StepCreate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    _get_campaign_or_404(campaign_id, ctx["workspace_id"], db)
    step = CampaignStep(
        id=uuid.uuid4().hex,
        campaign_id=campaign_id,
        **body.model_dump(),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@router.put("/{campaign_id}/steps/{step_id}", response_model=StepOut)
def update_step(
    campaign_id: str,
    step_id: str,
    body: StepUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    _get_campaign_or_404(campaign_id, ctx["workspace_id"], db)
    step = (
        db.query(CampaignStep)
        .filter(CampaignStep.id == step_id, CampaignStep.campaign_id == campaign_id)
        .first()
    )
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(step, k, v)
    db.commit()
    db.refresh(step)
    return step


@router.delete("/{campaign_id}/steps/{step_id}")
def delete_step(
    campaign_id: str,
    step_id: str,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    _get_campaign_or_404(campaign_id, ctx["workspace_id"], db)
    step = (
        db.query(CampaignStep)
        .filter(CampaignStep.id == step_id, CampaignStep.campaign_id == campaign_id)
        .first()
    )
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    db.delete(step)
    db.commit()
    return {"ok": True}
