"""
Dashboard summary and analytics endpoints.
Returns aggregate counts and rich analytics for the requesting user's workspace.
"""

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth_context import get_workspace_context
from database import get_db
from models.all_models import (
    Approval,
    BizAccount,
    Campaign,
    Contact,
    Message,
    Signal,
    Task,
    User,
    WarmPath,
    WorkspaceMember,
)

router = APIRouter()


@router.get("/summary")
def get_dashboard_summary(
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    """Return aggregate counts scoped to the requesting user's workspace."""
    ws_id = ctx["workspace_id"]
    now = datetime.now(timezone.utc)

    accounts_count = db.query(BizAccount).filter(BizAccount.workspace_id == ws_id).count()

    contacts_count = db.query(Contact).filter(Contact.workspace_id == ws_id).count()

    signals_count = db.query(Signal).filter(Signal.workspace_id == ws_id).count()

    urgent_signals_count = (
        db.query(Signal)
        .filter(Signal.workspace_id == ws_id, Signal.urgency_score >= 80)
        .count()
    )

    pending_approvals_count = (
        db.query(Approval)
        .filter(Approval.workspace_id == ws_id, Approval.status == "pending")
        .count()
    )

    campaigns_count = db.query(Campaign).filter(Campaign.workspace_id == ws_id).count()

    warm_paths_count = db.query(WarmPath).filter(WarmPath.workspace_id == ws_id).count()

    tasks_overdue_count = (
        db.query(Task)
        .filter(
            Task.workspace_id == ws_id,
            Task.due_at < now,
            Task.status != "completed",
        )
        .count()
    )

    return {
        "accounts_count": accounts_count,
        "contacts_count": contacts_count,
        "signals_count": signals_count,
        "urgent_signals_count": urgent_signals_count,
        "pending_approvals_count": pending_approvals_count,
        "campaigns_count": campaigns_count,
        "warm_paths_count": warm_paths_count,
        "tasks_overdue_count": tasks_overdue_count,
    }


# ── Signal type → human-readable display name mapping ─────────────────────────

SIGNAL_DISPLAY_NAMES: dict[str, str] = {
    "funding": "Funding announcement",
    "job_posting": "Job posting",
    "champion_job_change": "Champion job change",
    "leadership_change": "Leadership change",
    "g2_review": "G2 review spike",
    "intent_topic_surge": "Intent surge",
    "tech_stack_change": "Tech stack change",
    "linkedin_post": "LinkedIn post",
    "pricing_page_visit": "Pricing page visit",
    "website_visit": "Website visit",
}


@router.get("/analytics")
def get_dashboard_analytics(
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    """Return rich analytics data computed from real DB records, scoped to the workspace."""
    ws_id = ctx["workspace_id"]

    # ── Signal attribution ────────────────────────────────────────────────────
    all_signals = (
        db.query(Signal)
        .filter(Signal.workspace_id == ws_id)
        .all()
    )

    signal_buckets: dict[str, list[int]] = defaultdict(list)
    for sig in all_signals:
        signal_buckets[sig.type].append(sig.urgency_score)

    signal_attribution = sorted(
        [
            {
                "signal_type": stype,
                "display_name": SIGNAL_DISPLAY_NAMES.get(stype, stype.replace("_", " ").title()),
                "count": len(scores),
                "urgency_avg": round(sum(scores) / len(scores)) if scores else 0,
            }
            for stype, scores in signal_buckets.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )[:7]

    # ── Messages funnel ───────────────────────────────────────────────────────
    all_messages = (
        db.query(Message)
        .filter(Message.workspace_id == ws_id)
        .all()
    )

    funnel_counts: dict[str, int] = defaultdict(int)
    for msg in all_messages:
        funnel_counts[msg.approval_status] += 1

    messages_funnel = {
        "total": len(all_messages),
        "pending": funnel_counts.get("pending", 0),
        "approved": funnel_counts.get("approved", 0),
        "sent": funnel_counts.get("sent", 0),
        "rejected": funnel_counts.get("rejected", 0),
    }

    # ── Channel breakdown ─────────────────────────────────────────────────────
    channel_buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "approved": 0})
    for msg in all_messages:
        channel_buckets[msg.channel]["total"] += 1
        if msg.approval_status == "approved":
            channel_buckets[msg.channel]["approved"] += 1

    channel_breakdown = [
        {
            "channel": ch,
            "count": counts["total"],
            "approved_count": counts["approved"],
        }
        for ch, counts in channel_buckets.items()
    ]

    # ── Warm path coverage ────────────────────────────────────────────────────
    total_accounts = (
        db.query(BizAccount)
        .filter(BizAccount.workspace_id == ws_id)
        .count()
    )

    # Distinct account_ids that have at least one WarmPath
    warm_path_account_ids = (
        db.query(WarmPath.account_id)
        .filter(
            WarmPath.workspace_id == ws_id,
            WarmPath.account_id.isnot(None),
        )
        .distinct()
        .all()
    )
    accounts_with_paths = len(warm_path_account_ids)

    coverage_pct = (
        round(accounts_with_paths / total_accounts * 100)
        if total_accounts > 0
        else 0
    )

    warm_path_coverage = {
        "accounts_with_paths": accounts_with_paths,
        "total_accounts": total_accounts,
        "coverage_pct": coverage_pct,
    }

    # ── Team stats ────────────────────────────────────────────────────────────
    members = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == ws_id)
        .all()
    )

    team_stats = []
    for member in members:
        user = db.get(User, member.user_id)
        team_stats.append(
            {
                "user_id": member.user_id,
                "name": user.name if user else "Unknown",
                "role": member.role,
                "relationship_score": member.relationship_score,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
            }
        )

    # ── Top signals ───────────────────────────────────────────────────────────
    top_signal_rows = (
        db.query(Signal)
        .filter(Signal.workspace_id == ws_id)
        .order_by(Signal.urgency_score.desc())
        .limit(5)
        .all()
    )

    top_signals = []
    for sig in top_signal_rows:
        account_name = None
        if sig.account_id:
            acct = db.get(BizAccount, sig.account_id)
            account_name = acct.name if acct else None
        top_signals.append(
            {
                "id": sig.id,
                "type": sig.type,
                "title": sig.title,
                "account_name": account_name,
                "urgency_score": sig.urgency_score,
                "detected_at": sig.detected_at.isoformat() if sig.detected_at else None,
            }
        )

    return {
        "signal_attribution": signal_attribution,
        "messages_funnel": messages_funnel,
        "channel_breakdown": channel_breakdown,
        "warm_path_coverage": warm_path_coverage,
        "team_stats": team_stats,
        "top_signals": top_signals,
    }
