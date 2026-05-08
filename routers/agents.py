"""
AI agent endpoints.
POST /agents/research  prospect research pipeline (hooks, pain points, company events)
POST /agents/generate  generate outreach message via Claude with prompt caching
"""

import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.ai_client import generate_with_cache

router = APIRouter()

RESEARCH_SYSTEM_PROMPT = """You are a B2B sales research analyst. Given a contact and company,
identify specific, verifiable personalization hooks for outreach.

Return ONLY valid JSON:
{
  "hooks": [
    {"text": "specific hook", "source": "LinkedIn|TechCrunch|G2|etc", "date": "X days ago", "confidence": 0.0-1.0}
  ],
  "pain_points": ["list of inferred pain points based on signals"],
  "company_events": ["recent company events relevant to outreach"],
  "recommended_approach": "one sentence on best outreach angle"
}

Rules:
- Only include verifiable facts from the provided context
- Confidence reflects how certain you are this is accurate
- Do not fabricate specific numbers or quotes
- Focus on hooks that are genuinely relevant to a GTM/sales intelligence tool"""


class ResearchRequest(BaseModel):
    contact_name: str
    contact_title: str
    account_name: str
    account_industry: str
    account_description: str | None = None
    recent_signals: list[dict[str, Any]] = []
    kb_items: list[dict[str, Any]] = []


class GenerateRequest(BaseModel):
    contact_name: str
    contact_title: str
    contact_department: str | None = None
    contact_persona: str | None = None
    account_name: str
    account_industry: str
    account_employee_count: int | None = None
    account_location: str | None = None
    account_description: str | None = None
    signal_type: str | None = None
    signal_title: str | None = None
    signal_description: str | None = None
    warm_path: list[str] | None = None  # list of names in path order
    intro_person: str | None = None
    channel: str = "email"
    tone: str = "direct and friendly"
    kb_items: list[dict[str, Any]] = []
    research_hooks: list[dict[str, Any]] = []


@router.post("/research")
async def research_prospect(req: ResearchRequest):
    """
    Run prospect research pipeline and return personalization hooks.
    In production: calls Proxycurl, Google News, G2, Crunchbase in parallel.
    Currently: uses Claude to synthesize from provided signals + context.
    """
    kb_context = ""
    if req.kb_items:
        approved = [k for k in req.kb_items if k.get("approved_for_ai")][:4]
        kb_context = "\n".join(
            f"[{k['type'].upper()}] {k['title']}: {k['content'][:200]}" for k in approved
        )

    signal_context = ""
    if req.recent_signals:
        signal_context = "\n".join(
            f"- {s['type']}: {s['title']} ({s.get('description', '')})"
            for s in req.recent_signals[:5]
        )

    user_prompt = f"""Research contact for B2B outreach:

CONTACT: {req.contact_name} | {req.contact_title}
COMPANY: {req.account_name} ({req.account_industry})
{f'DESCRIPTION: {req.account_description}' if req.account_description else ''}
{f'RECENT SIGNALS:\n{signal_context}' if signal_context else ''}
{f'OUR PRODUCT CONTEXT:\n{kb_context}' if kb_context else ''}

Find 2-4 specific personalization hooks. Focus on recent, verifiable activity."""

    try:
        result = generate_with_cache(RESEARCH_SYSTEM_PROMPT, user_prompt, max_tokens=512)
        content = result["content"]
        # Strip markdown fences if present
        content = content.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(content)
        return {**parsed, "usage": result["usage"], "cost_usd": result["cost_usd"]}
    except json.JSONDecodeError:
        return {
            "hooks": [],
            "pain_points": [],
            "company_events": [],
            "recommended_approach": "Unable to parse research results. Using signal data directly.",
            "error": "parse_error",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


GENERATE_SYSTEM_PROMPT_TEMPLATE = """You are WarmPath's AI sales writer. Write personalized, warm B2B outbound messages.

{kb_context}

RULES:
- Body under 130 words
- End with exactly one specific, low-friction question
- Sound like a real person, not a template
- Never use: synergy, leverage, paradigm, game-changer, cutting-edge, revolutionary
- Reference the signal or trigger if provided
- If warm path exists, mention the intro person naturally
- No placeholders like [COMPANY] or [NAME]

RESPOND ONLY with valid JSON:
{{
  "subject": "string (email only, omit for other channels)",
  "body": "string (full message body, plain text)",
  "intro_request": "string or null (warm_intro channel only)",
  "confidence_score": number (0.75-0.97),
  "personalization_reason": "string (1 sentence on the main personalization hook)",
  "factual_claims": ["verifiable claims made in the message"],
  "risk_flags": []
}}"""


@router.post("/generate")
async def generate_message(req: GenerateRequest):
    """Generate a personalized outreach message via Claude Sonnet 4.6."""
    # Build KB system prompt (cached)
    kb_context = ""
    if req.kb_items:
        approved = [k for k in req.kb_items if k.get("approved_for_ai")][:6]
        if approved:
            kb_context = "KNOWLEDGE BASE (cite these facts only):\n" + "\n".join(
                f"[{k['type'].upper()}] {k['title']}: {k['content'][:250]}" for k in approved
            )

    system_prompt = GENERATE_SYSTEM_PROMPT_TEMPLATE.format(kb_context=kb_context)

    # Build user prompt (per-request, not cached)
    channel_label = {
        "warm_intro": "warm intro request email",
        "linkedin": "LinkedIn DM",
        "phone": "phone call script",
        "email": "cold email",
    }.get(req.channel, "cold email")

    lines = [
        f"Write a {channel_label}.",
        "",
        f"CONTACT: {req.contact_name} | {req.contact_title}"
        + (f" | {req.contact_department}" if req.contact_department else "")
        + (f" | Persona: {req.contact_persona}" if req.contact_persona else ""),
        f"COMPANY: {req.account_name} ({req.account_industry}"
        + (f", {req.account_employee_count} employees" if req.account_employee_count else "")
        + (f", {req.account_location}" if req.account_location else "")
        + ")",
    ]

    if req.account_description:
        lines.append(f"DESCRIPTION: {req.account_description}")

    if req.signal_type and req.signal_title:
        lines.append(f"SIGNAL: {req.signal_type.upper()} {req.signal_title}")
        if req.signal_description:
            lines.append(f"SIGNAL DETAIL: {req.signal_description}")

    if req.warm_path:
        lines.append(f"WARM PATH: {' → '.join(req.warm_path)}")
        if req.intro_person:
            lines.append(f"INTRO PERSON: {req.intro_person}")

    if req.research_hooks:
        hook_lines = [f"- {h['text']} (source: {h.get('source', '?')})" for h in req.research_hooks[:3]]
        lines.append(f"RESEARCH HOOKS (weave these in naturally):\n" + "\n".join(hook_lines))

    lines.append(f"TONE: {req.tone}")
    user_prompt = "\n".join(lines)

    try:
        result = generate_with_cache(system_prompt, user_prompt, max_tokens=800, temperature=0.72)
        content = result["content"].strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(content)
        return {**parsed, "usage": result["usage"], "cost_usd": result["cost_usd"], "model": result["model"]}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Model returned non-JSON: {str(e)}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
