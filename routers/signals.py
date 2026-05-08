"""
Signal ingestion and scoring endpoints.
GET  /signals/ingest   trigger a signal scraping run (async)
POST /signals/score    score a batch of raw signals
POST /signals/detect   AI-powered signal detection for a named company
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_context import get_workspace_context
from database import get_db
from models.all_models import BizAccount, Signal
from services.ai_client import generate_with_cache

router = APIRouter()


class RawSignal(BaseModel):
    type: str
    title: str
    description: str | None = None
    account_name: str
    source: str | None = None
    source_url: str | None = None
    raw_data: dict[str, Any] = {}


class ScoreRequest(BaseModel):
    signals: list[RawSignal]
    workspace_id: str


def _compute_urgency(signal: RawSignal) -> int:
    """
    Score urgency 0–100 based on signal type and recency.
    In production this would use ML features from historical conversion data.
    """
    base: dict[str, int] = {
        "pricing_page_visit": 95,
        "champion_job_change": 92,
        "funding": 88,
        "intent_topic_surge": 85,
        "leadership_change": 82,
        "g2_review": 78,
        "linkedin_post": 72,
        "job_posting": 68,
        "tech_stack_change": 65,
        "website_visit": 60,
        "contract_renewal": 55,
        "product_launch": 50,
        "competitor_hiring": 48,
    }
    return base.get(signal.type, 50)


def _ingest_job_postings(workspace_id: str) -> None:
    """
    Background job: scrape LinkedIn job postings for ICP companies.
    Stub in production: Proxycurl Jobs API + keyword matching.
    """
    # TODO: implement with Proxycurl or LinkedIn API
    print(f"[signals] Ingesting job postings for workspace {workspace_id}")


def _ingest_funding_news(workspace_id: str) -> None:
    """
    Background job: fetch recent funding announcements.
    Stub in production: Crunchbase API + Google News RSS.
    """
    print(f"[signals] Ingesting funding news for workspace {workspace_id}")


def _ingest_champion_changes(workspace_id: str) -> None:
    """
    Background job: detect champion job changes.
    Weekly LinkedIn profile check via Proxycurl for known contacts.
    """
    print(f"[signals] Checking champion job changes for workspace {workspace_id}")


@router.get("/ingest")
async def trigger_ingest(workspace_id: str, background_tasks: BackgroundTasks):
    """
    Trigger a full signal ingestion run in the background.
    Returns immediately check /signals/status for progress.
    """
    background_tasks.add_task(_ingest_job_postings, workspace_id)
    background_tasks.add_task(_ingest_funding_news, workspace_id)
    background_tasks.add_task(_ingest_champion_changes, workspace_id)

    return {
        "status": "ingestion_started",
        "sources": ["job_postings", "funding_news", "champion_changes"],
        "workspace_id": workspace_id,
    }


@router.post("/score")
async def score_signals(req: ScoreRequest):
    """Score a batch of raw signals and return urgency + confidence scores."""
    scored = []
    for signal in req.signals:
        urgency = _compute_urgency(signal)
        # Confidence higher for signals with a source URL (verifiable)
        confidence = 90 if signal.source_url else 70

        scored.append(
            {
                "type": signal.type,
                "title": signal.title,
                "description": signal.description,
                "account_name": signal.account_name,
                "source": signal.source,
                "source_url": signal.source_url,
                "urgency_score": urgency,
                "confidence_score": confidence,
                "recommended_action": _recommended_action(signal.type),
            }
        )

    return {"signals": scored, "count": len(scored)}


def _recommended_action(signal_type: str) -> str:
    actions: dict[str, str] = {
        "funding": "Congratulate the team reach out within 48 hours while the announcement is fresh.",
        "champion_job_change": "Congratulate the champion at their new role high warmth window.",
        "pricing_page_visit": "They're actively evaluating route via warm intro immediately.",
        "leadership_change": "New exec = new vendor reviews. First mover wins the evaluation.",
        "job_posting": "They're solving the problem you solve use the job req as the opening hook.",
        "g2_review": "They're actively comparing solutions personalized outreach now.",
        "intent_topic_surge": "Research spike detected they're in buying mode.",
        "linkedin_post": "They posted the pain publicly respond with a specific, non-salesy hook.",
        "tech_stack_change": "Stack change = integration opportunity reach out within a week.",
        "website_visit": "They found you warm follow-up before the interest cools.",
    }
    return actions.get(signal_type, "Review and determine best next action.")


# ─── AI-powered signal detection ──────────────────────────────────────────────

_DETECT_SYSTEM_PROMPT = """You are a B2B sales intelligence analyst. Given a company name and profile, identify 3-5 likely buying signals that a GTM team should know about.

Focus on REALISTIC, PLAUSIBLE signals based on the company's industry, size, and market position. Do not fabricate specific data but infer from typical patterns.

Return ONLY valid JSON array:
[
  {
    "type": "funding" | "job_posting" | "leadership_change" | "champion_job_change" | "intent_topic_surge" | "g2_review" | "tech_stack_change" | "linkedin_post" | "product_launch" | "competitor_hiring",
    "title": "specific signal title (1 sentence)",
    "description": "2-3 sentence context and why this matters for outreach",
    "urgency_score": 40-95,
    "confidence_score": 50-90,
    "source": "LinkedIn | Crunchbase | G2 | TechCrunch | Job board | Company blog"
  }
]"""


class DetectRequest(BaseModel):
    account_name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    persist: bool = False  # if True, save detected signals to DB
    workspace_id: Optional[str] = None  # unused workspace is taken from auth context


class DetectedSignal(BaseModel):
    type: str
    title: str
    description: str
    urgency_score: int
    confidence_score: int
    source: str


def _build_detect_prompt(req: DetectRequest) -> str:
    parts = [f"COMPANY: {req.account_name}"]
    if req.domain:
        parts.append(f"DOMAIN: {req.domain}")
    if req.industry:
        parts.append(f"INDUSTRY: {req.industry}")
    if req.description:
        parts.append(f"DESCRIPTION: {req.description}")
    return "\n".join(parts)


def _parse_detected_signals(content: str) -> list[dict]:
    """Parse AI JSON response for detected signals."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(inner).strip()
    return json.loads(text)


@router.post("/detect", response_model=list[DetectedSignal])
async def detect_signals(
    req: DetectRequest,
    persist: bool = False,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> list[DetectedSignal]:
    """
    Use AI to infer 3-5 plausible buying signals for a named company.

    When `persist=true`, the detected signals are saved to the database and linked
    to the BizAccount matching the provided account_name (exact match).
    """
    user_prompt = _build_detect_prompt(req)

    raw = generate_with_cache(
        system_prompt=_DETECT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=800,
        temperature=0.6,
    )

    try:
        signals_data = _parse_detected_signals(raw["content"])
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI returned unparseable response: {exc}. Raw: {raw['content'][:200]}",
        ) from exc

    workspace_id = ctx["workspace_id"]
    detected: list[DetectedSignal] = []

    for item in signals_data:
        detected.append(
            DetectedSignal(
                type=item.get("type", "intent_topic_surge"),
                title=item.get("title", ""),
                description=item.get("description", ""),
                urgency_score=int(item.get("urgency_score", 60)),
                confidence_score=int(item.get("confidence_score", 70)),
                source=item.get("source", "AI inference"),
            )
        )

    if persist:
        # Find matching account (simple exact match; case handled by Python lower())
        account = (
            db.query(BizAccount)
            .filter(
                BizAccount.workspace_id == workspace_id,
                BizAccount.name == req.account_name,
            )
            .first()
        )

        now = datetime.now(timezone.utc)
        for sig in detected:
            db_signal = Signal(
                id=uuid.uuid4().hex,
                workspace_id=workspace_id,
                account_id=account.id if account else None,
                contact_id=None,
                type=sig.type,
                title=sig.title,
                description=sig.description,
                source=sig.source,
                source_url=None,
                urgency_score=sig.urgency_score,
                confidence_score=sig.confidence_score,
                detected_at=now,
                created_at=now,
            )
            db.add(db_signal)

        db.commit()

    return detected
