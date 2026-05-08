"""
Dynamic lead scoring engine.

Recomputes fit_score, intent_score, warmth_score for accounts based on:
  - Signal type weights × recency decay
  - Relationship graph depth and edge strength
  - Contact seniority mix (C-suite → VP → Director → Manager)
  - Warm path coverage
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_context import get_workspace_context
from database import get_db
from models.all_models import BizAccount, Contact, RelationshipEdge, Signal, WarmPath

router = APIRouter()

# ─── Signal type weights (0.0–1.0) ────────────────────────────────────────────

SIGNAL_WEIGHTS: dict[str, float] = {
    "pricing_page_visit": 1.00,
    "champion_job_change": 0.95,
    "funding": 0.90,
    "intent_topic_surge": 0.88,
    "leadership_change": 0.82,
    "g2_review": 0.78,
    "job_posting": 0.65,
    "tech_stack_change": 0.62,
    "website_visit": 0.58,
    "linkedin_post": 0.55,
    "product_launch": 0.50,
    "competitor_hiring": 0.45,
}

# ─── Seniority weights ────────────────────────────────────────────────────────

SENIORITY_WEIGHTS: dict[str, float] = {
    "c_suite": 1.00,
    "vp": 0.85,
    "director": 0.70,
    "manager": 0.50,
    "ic": 0.30,
}

# ─── Pydantic models ──────────────────────────────────────────────────────────


class ScoreResult(BaseModel):
    account_id: str
    account_name: str
    fit_score: int
    intent_score: int
    warmth_score: int
    signal_count: int
    warm_path_count: int
    edge_count: int


class BatchScoreResponse(BaseModel):
    scored: list[ScoreResult]
    total: int


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _recency_decay(detected_at: Optional[datetime]) -> float:
    """Return a recency multiplier based on how old the signal is."""
    if detected_at is None:
        return 0.40

    now = datetime.now(timezone.utc)
    # Normalise naive datetimes coming out of SQLite
    if detected_at.tzinfo is None:
        detected_at = detected_at.replace(tzinfo=timezone.utc)

    age_days = (now - detected_at).days
    if age_days <= 7:
        return 1.00
    if age_days <= 30:
        return 0.85
    if age_days <= 90:
        return 0.65
    return 0.40


def _compute_intent_score(signals: list[Signal]) -> int:
    """
    Intent formula: max(scores)*0.5 + mean(scores)*0.5, capped 0–100.
    Defaults to 30 when no signals are present.
    """
    if not signals:
        return 30

    weighted_scores = [
        SIGNAL_WEIGHTS.get(s.type, 0.40) * _recency_decay(s.detected_at) * 100
        for s in signals
    ]
    max_score = max(weighted_scores)
    mean_score = sum(weighted_scores) / len(weighted_scores)
    raw = max_score * 0.5 + mean_score * 0.5
    return min(100, max(0, round(raw)))


def _compute_warmth_score(warm_paths: list[WarmPath], edges: list[RelationshipEdge]) -> int:
    """
    Warmth formula: base 20 + warm_path avg warmth * 0.5 + edge avg strength * 0.3, capped 0–100.
    """
    base = 20

    path_bonus = 0.0
    if warm_paths:
        avg_warmth = sum(wp.warmth_score for wp in warm_paths) / len(warm_paths)
        path_bonus = avg_warmth * 0.5

    edge_bonus = 0.0
    if edges:
        avg_strength = sum(e.strength_score for e in edges) / len(edges)
        edge_bonus = avg_strength * 0.3

    raw = base + path_bonus + edge_bonus
    return min(100, max(0, round(raw)))


def _compute_fit_score(account: BizAccount, contacts: list[Contact]) -> int:
    """
    Fit formula:
      base 40
      + employee_count ICP bonus (50-500 → +20, 500-2000 → +12, <50 → +8)
      + max_seniority_weight * 25
      + description bonus +5
      + domain bonus +5
    """
    score = 40

    # Employee count ICP bonus
    ec = account.employee_count or 0
    if 50 <= ec <= 500:
        score += 20
    elif 500 < ec <= 2000:
        score += 12
    elif ec < 50 and ec > 0:
        score += 8

    # Max seniority weight from contacts
    max_seniority = 0.0
    for contact in contacts:
        seniority_key = (contact.seniority or "").lower().replace(" ", "_").replace("-", "_")
        weight = SENIORITY_WEIGHTS.get(seniority_key, 0.0)
        if weight > max_seniority:
            max_seniority = weight
    score += round(max_seniority * 25)

    # Description quality bonus
    if account.description and len(account.description.strip()) > 20:
        score += 5

    # Domain bonus
    if account.domain and "." in account.domain:
        score += 5

    return min(100, max(0, score))


def _score_account(
    account: BizAccount,
    db: Session,
    workspace_id: str,
) -> ScoreResult:
    """Compute all three scores for one account and return a ScoreResult."""
    # Signals for this account
    signals = (
        db.query(Signal)
        .filter(Signal.account_id == account.id, Signal.workspace_id == workspace_id)
        .all()
    )

    # Warm paths for this account
    warm_paths = (
        db.query(WarmPath)
        .filter(WarmPath.account_id == account.id, WarmPath.workspace_id == workspace_id)
        .all()
    )

    # Contacts for this account
    contacts = (
        db.query(Contact)
        .filter(Contact.account_id == account.id, Contact.workspace_id == workspace_id)
        .all()
    )

    contact_ids = [c.id for c in contacts]

    # Relationship edges pointing to any of this account's contacts
    edges: list[RelationshipEdge] = []
    if contact_ids:
        edges = (
            db.query(RelationshipEdge)
            .filter(
                RelationshipEdge.workspace_id == workspace_id,
                RelationshipEdge.to_id.in_(contact_ids),
            )
            .all()
        )

    intent = _compute_intent_score(signals)
    warmth = _compute_warmth_score(warm_paths, edges)
    fit = _compute_fit_score(account, contacts)

    return ScoreResult(
        account_id=account.id,
        account_name=account.name,
        fit_score=fit,
        intent_score=intent,
        warmth_score=warmth,
        signal_count=len(signals),
        warm_path_count=len(warm_paths),
        edge_count=len(edges),
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/account/{account_id}", response_model=ScoreResult)
def score_account(
    account_id: str,
    persist: bool = True,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> ScoreResult:
    """
    Recompute fit_score, intent_score, and warmth_score for a single account.

    Set `persist=true` (default) to write the new scores back to the DB.
    """
    workspace_id = ctx["workspace_id"]

    account = db.query(BizAccount).filter(
        BizAccount.id == account_id,
        BizAccount.workspace_id == workspace_id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    result = _score_account(account, db, workspace_id)

    if persist:
        account.fit_score = result.fit_score
        account.intent_score = result.intent_score
        account.warmth_score = result.warmth_score
        db.commit()

    return result


@router.post("/batch", response_model=BatchScoreResponse)
def score_batch(
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> BatchScoreResponse:
    """
    Recompute scores for all accounts in the workspace and persist results.

    Commits once after all accounts are updated for efficiency.
    """
    workspace_id = ctx["workspace_id"]

    accounts = (
        db.query(BizAccount)
        .filter(BizAccount.workspace_id == workspace_id)
        .all()
    )

    results: list[ScoreResult] = []
    for account in accounts:
        result = _score_account(account, db, workspace_id)
        account.fit_score = result.fit_score
        account.intent_score = result.intent_score
        account.warmth_score = result.warmth_score
        results.append(result)

    db.commit()

    return BatchScoreResponse(scored=results, total=len(results))
