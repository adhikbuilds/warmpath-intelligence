"""
Router for Workspace current workspace info and settings update.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_context import get_workspace_context
from database import get_db
from models.all_models import User, Workspace, WorkspaceMember

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────


class MemberOut(BaseModel):
    id: str
    user_id: str
    role: str
    title: Optional[str] = None
    relationship_score: int
    joined_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceOut(BaseModel):
    id: str
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    region: Optional[str] = None
    selling_motion: Optional[str] = None
    primary_goal: Optional[str] = None
    plan: str
    onboarding_stage: str
    health_score: int
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceWithMembersOut(WorkspaceOut):
    members: list[MemberOut] = []
    current_member_role: Optional[str] = None


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    region: Optional[str] = None
    selling_motion: Optional[str] = None
    primary_goal: Optional[str] = None
    plan: Optional[str] = None
    onboarding_stage: Optional[str] = None
    health_score: Optional[int] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/current", response_model=WorkspaceWithMembersOut)
def get_current_workspace(
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    workspace = db.query(Workspace).filter(Workspace.id == ctx["workspace_id"]).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Fetch current member's role
    current_member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == ctx["workspace_id"],
            WorkspaceMember.user_id == ctx["user_id"],
        )
        .first()
    )

    result = WorkspaceWithMembersOut.model_validate(workspace)
    result.members = list(workspace.members)
    result.current_member_role = current_member.role if current_member else None
    return result


@router.patch("/current", response_model=WorkspaceOut)
@router.put("/current", response_model=WorkspaceOut)
def update_current_workspace(
    body: WorkspaceUpdate,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    workspace = db.query(Workspace).filter(Workspace.id == ctx["workspace_id"]).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(workspace, k, v)
    workspace.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(workspace)
    return workspace
