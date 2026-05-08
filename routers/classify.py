"""
Reply classification agent SalesGPT-inspired.

Classifies inbound message replies by intent, sentiment, and conversation stage.
Recommends the next sales action.
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.ai_client import generate_with_cache

router = APIRouter()

# ─── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a B2B sales reply classifier. Analyze an email/message reply and classify it.

Return ONLY valid JSON:
{
  "intent": "positive" | "negative" | "neutral" | "question" | "objection" | "referral" | "meeting_request" | "out_of_office",
  "sentiment_score": number between -1.0 and 1.0,
  "stage": "interested" | "evaluating" | "not_now" | "not_interested" | "closed",
  "key_points": ["list of key points"],
  "objections": ["any objections raised"],
  "next_action": "specific recommended next action as a single sentence",
  "urgency": "immediate" | "this_week" | "next_week" | "low",
  "summary": "1-2 sentence summary of the reply"
}"""

# ─── Pydantic models ──────────────────────────────────────────────────────────


class ClassifyRequest(BaseModel):
    reply_body: str
    original_subject: Optional[str] = None
    original_body: Optional[str] = None
    contact_name: Optional[str] = None
    account_name: Optional[str] = None
    channel: str = "email"


class ClassifyResult(BaseModel):
    intent: str
    sentiment_score: float
    stage: str
    key_points: list[str]
    objections: list[str]
    next_action: str
    urgency: str
    summary: str


class BatchClassifyResponse(BaseModel):
    results: list[ClassifyResult]
    count: int


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_user_prompt(req: ClassifyRequest) -> str:
    """Construct the user prompt from the classify request fields."""
    parts: list[str] = []

    if req.original_subject:
        parts.append(f"ORIGINAL SUBJECT: {req.original_subject}")

    if req.original_body:
        truncated = req.original_body[:300]
        if len(req.original_body) > 300:
            truncated += "..."
        parts.append(f"ORIGINAL MESSAGE:\n{truncated}")

    parts.append(f"REPLY:\n{req.reply_body}")

    sender_parts: list[str] = []
    if req.contact_name:
        sender_parts.append(req.contact_name)
    if req.account_name:
        sender_parts.append(f"({req.account_name})")
    if sender_parts:
        parts.append(f"FROM: {' '.join(sender_parts)}")

    parts.append(f"CHANNEL: {req.channel}")

    return "\n\n".join(parts)


def _parse_classify_result(content: str) -> ClassifyResult:
    """Parse the AI response JSON into a ClassifyResult, with graceful fallback."""
    try:
        # Strip markdown code fences if present
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop the opening fence line and closing fence
            inner = [l for l in lines[1:] if not l.strip().startswith("```")]
            text = "\n".join(inner).strip()

        data = json.loads(text)
        return ClassifyResult(
            intent=data.get("intent", "neutral"),
            sentiment_score=float(data.get("sentiment_score", 0.0)),
            stage=data.get("stage", "not_now"),
            key_points=data.get("key_points", []),
            objections=data.get("objections", []),
            next_action=data.get("next_action", "Review reply and determine next action."),
            urgency=data.get("urgency", "low"),
            summary=data.get("summary", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI returned unparseable response: {exc}. Raw: {content[:200]}",
        ) from exc


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/reply", response_model=ClassifyResult)
async def classify_reply(req: ClassifyRequest) -> ClassifyResult:
    """
    Classify a single inbound reply.

    Does not require workspace auth the endpoint is workspace-agnostic.
    """
    user_prompt = _build_user_prompt(req)
    result = generate_with_cache(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=400,
        temperature=0.3,
    )
    return _parse_classify_result(result["content"])


@router.post("/batch", response_model=BatchClassifyResponse)
async def classify_batch(requests: list[ClassifyRequest]) -> BatchClassifyResponse:
    """
    Classify up to 20 replies in one call.

    Each reply is classified independently using the same cached system prompt.
    Does not require workspace auth.
    """
    if len(requests) > 20:
        raise HTTPException(
            status_code=422,
            detail="Batch size exceeds the maximum of 20 replies per request.",
        )

    results: list[ClassifyResult] = []
    for req in requests:
        user_prompt = _build_user_prompt(req)
        raw = generate_with_cache(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=400,
            temperature=0.3,
        )
        results.append(_parse_classify_result(raw["content"]))

    return BatchClassifyResponse(results=results, count=len(results))
