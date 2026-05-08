"""
Sequence execution engine Mautic-inspired drip campaign automation.

Checks active campaigns, finds enrolled accounts (those with at least one message sent),
determines which CampaignStep is next based on step_number and delay_days,
and creates Task records for the rep to execute.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_context import get_workspace_context
from database import get_db
from models.all_models import BizAccount, Campaign, CampaignStep, Message, Task

router = APIRouter()

# ─── Pydantic models ──────────────────────────────────────────────────────────


class TaskDetail(BaseModel):
    task_id: str
    campaign_id: str
    campaign_name: str
    account_id: str
    account_name: str
    step_number: int
    channel: str
    title: str
    due_at: datetime


class AdvanceResponse(BaseModel):
    tasks_created: int
    details: list[TaskDetail]


class CampaignStatus(BaseModel):
    campaign_id: str
    campaign_name: str
    status: str
    enrolled_accounts: int
    total_steps: int


class StatusResponse(BaseModel):
    active_campaigns: list[CampaignStatus]
    total: int


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _action_label(action_type: str, channel: str, step_number: int) -> str:
    """Build a human-readable action label for the task title."""
    if action_type == "send_message":
        return f"Send {channel} Step {step_number}"
    if action_type == "call":
        return f"Make call Step {step_number}"
    if action_type == "connect_request":
        return f"LinkedIn connect Step {step_number}"
    return f"Step {step_number}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_dt(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware (SQLite stores naive UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/advance", response_model=AdvanceResponse)
def advance_sequences(
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> AdvanceResponse:
    """
    Advance all active campaigns for the workspace.

    For each active campaign, finds accounts that have at least one approved/sent
    message, determines the next step, checks if the delay has elapsed, and creates
    a Task for the rep if so. Duplicate tasks are skipped.
    """
    workspace_id = ctx["workspace_id"]
    now = _utcnow()
    tasks_created: list[TaskDetail] = []

    active_campaigns = (
        db.query(Campaign)
        .filter(Campaign.workspace_id == workspace_id, Campaign.status == "active")
        .all()
    )

    for campaign in active_campaigns:
        if not campaign.steps:
            continue

        # Find all accounts that have engaged with this campaign (at least one sent/approved msg)
        sent_message_rows = (
            db.query(Message.account_id)
            .filter(
                Message.campaign_id == campaign.id,
                Message.workspace_id == workspace_id,
                Message.approval_status.in_(["approved", "sent"]),
                Message.account_id.isnot(None),
            )
            .distinct()
            .all()
        )
        enrolled_account_ids = [row[0] for row in sent_message_rows]

        for account_id in enrolled_account_ids:
            # All sent messages for this campaign+account, oldest first
            sent_messages = (
                db.query(Message)
                .filter(
                    Message.campaign_id == campaign.id,
                    Message.account_id == account_id,
                    Message.workspace_id == workspace_id,
                    Message.approval_status.in_(["approved", "sent"]),
                )
                .order_by(Message.created_at.asc())
                .all()
            )

            next_step_number = len(sent_messages) + 1

            # Find the matching step
            matching_step: Optional[CampaignStep] = next(
                (s for s in campaign.steps if s.step_number == next_step_number),
                None,
            )
            if matching_step is None:
                # No more steps sequence complete for this account
                continue

            # Check delay from last sent message
            last_message = sent_messages[-1]
            last_sent_at = _normalise_dt(last_message.created_at)
            due_after = last_sent_at + timedelta(days=matching_step.delay_days)
            if now < due_after:
                # Delay not yet elapsed skip
                continue

            step_label = _action_label(
                matching_step.action_type, matching_step.channel, next_step_number
            )

            # Dedup: skip if a pending task already exists for this campaign+account+step
            existing_task = (
                db.query(Task)
                .filter(
                    Task.workspace_id == workspace_id,
                    Task.campaign_id == campaign.id,
                    Task.account_id == account_id,
                    Task.status == "pending",
                    Task.title.contains(f"Step {next_step_number}"),
                )
                .first()
            )
            if existing_task:
                continue

            # Resolve account name for the task title
            account = db.get(BizAccount, account_id)
            account_name = account.name if account else account_id

            task_title = f"{campaign.name}: {step_label} for {account_name}"
            task_description = (
                f"Campaign: {campaign.name}\n"
                f"Step {next_step_number} of {len(campaign.steps)}\n"
                f"Channel: {matching_step.channel}\n"
                f"Action: {matching_step.action_type}\n"
                f"Account: {account_name}"
            )

            new_task = Task(
                id=uuid.uuid4().hex,
                workspace_id=workspace_id,
                campaign_id=campaign.id,
                account_id=account_id,
                type=matching_step.channel,
                title=task_title,
                description=task_description,
                priority="medium",
                status="pending",
                due_at=now + timedelta(hours=2),
            )
            db.add(new_task)
            db.flush()  # get the id without committing yet

            tasks_created.append(
                TaskDetail(
                    task_id=new_task.id,
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    account_id=account_id,
                    account_name=account_name,
                    step_number=next_step_number,
                    channel=matching_step.channel,
                    title=task_title,
                    due_at=new_task.due_at,
                )
            )

    db.commit()

    return AdvanceResponse(tasks_created=len(tasks_created), details=tasks_created)


@router.get("/status", response_model=StatusResponse)
def sequences_status(
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> StatusResponse:
    """
    Return all active campaigns with their enrolled account count and total step count.

    An account is considered enrolled once it has at least one approved or sent message
    for the campaign.
    """
    workspace_id = ctx["workspace_id"]

    active_campaigns = (
        db.query(Campaign)
        .filter(Campaign.workspace_id == workspace_id, Campaign.status == "active")
        .all()
    )

    statuses: list[CampaignStatus] = []
    for campaign in active_campaigns:
        enrolled_count = (
            db.query(Message.account_id)
            .filter(
                Message.campaign_id == campaign.id,
                Message.workspace_id == workspace_id,
                Message.approval_status.in_(["approved", "sent"]),
                Message.account_id.isnot(None),
            )
            .distinct()
            .count()
        )

        statuses.append(
            CampaignStatus(
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                status=campaign.status,
                enrolled_accounts=enrolled_count,
                total_steps=len(campaign.steps),
            )
        )

    return StatusResponse(active_campaigns=statuses, total=len(statuses))
