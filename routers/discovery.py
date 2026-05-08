"""
Lead discovery engine inspired by Omkarcloud/google-maps-scraper and Gosom/google-maps-scraper.

Searches for businesses matching a query (industry + location) and returns
structured lead records ready to import into the workspace as BizAccount entries.

Two modes:
  API mode: calls Google Maps Places API (requires GOOGLE_MAPS_API_KEY)
  AI stub: generates realistic results via Claude (demo / no-key mode)
"""

import json
import os
import uuid
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth_context import get_workspace_context
from database import get_db
from models.all_models import BizAccount, Contact
from services.ai_client import generate_with_cache

router = APIRouter()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


# ─── Request / Response Models ───────────────────────────────────────────────


class DiscoverySearchRequest(BaseModel):
    query: str  # e.g. "SaaS project management tools"
    location: str = "United States"  # city, state, or country
    industry: Optional[str] = None  # filter hint for AI mode
    limit: int = 10  # max results, 1-20


class DiscoveredLead(BaseModel):
    name: str
    domain: Optional[str] = None  # extracted from website URL
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    employee_count_estimate: Optional[int] = None
    rating: Optional[float] = None  # Google Maps star rating
    review_count: Optional[int] = None
    technologies: list[str] = []  # tech stack detected (Gosom-inspired)
    emails_found: list[str] = []  # emails discovered via website enrichment
    linkedin_url: Optional[str] = None
    fit_score_estimate: int = 50  # AI-estimated ICP fit 0-100
    source: str = "google_maps"


class DiscoverySearchResponse(BaseModel):
    leads: list[DiscoveredLead]
    total: int
    query: str
    location: str
    mode: str  # "api" | "ai_stub"


class ImportLeadsRequest(BaseModel):
    leads: list[DiscoveredLead]
    stage: str = "prospect"  # default stage for imported accounts


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _extract_domain(website: Optional[str]) -> Optional[str]:
    """Strip scheme, www, and path from a website URL to get the bare domain."""
    if not website:
        return None
    try:
        return urlparse(website).netloc.replace("www.", "") or None
    except Exception:
        return None


# ─── Google Maps API mode ────────────────────────────────────────────────────


async def _search_via_google_maps_api(req: DiscoverySearchRequest) -> list[DiscoveredLead]:
    """
    Call the Google Maps Places API (Text Search + Details) to fetch real leads.
    Falls back to an empty list on any HTTP / parsing error.
    """
    limit = max(1, min(req.limit, 20))
    leads: list[DiscoveredLead] = []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Text search
            search_resp = await client.get(
                PLACES_TEXT_SEARCH_URL,
                params={
                    "query": f"{req.query} {req.location}",
                    "type": "establishment",
                    "key": GOOGLE_MAPS_API_KEY,
                },
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()

            results = search_data.get("results", [])[:limit]

            for place in results:
                place_id = place.get("place_id")
                name = place.get("name", "Unknown")
                rating = place.get("rating")
                review_count = place.get("user_ratings_total")

                # 2. Place details for phone, website, address, categories
                website: Optional[str] = None
                phone: Optional[str] = None
                address: Optional[str] = None
                industry: Optional[str] = None

                if place_id:
                    try:
                        details_resp = await client.get(
                            PLACES_DETAILS_URL,
                            params={
                                "place_id": place_id,
                                "fields": (
                                    "name,website,formatted_phone_number,"
                                    "formatted_address,rating,user_ratings_total,types"
                                ),
                                "key": GOOGLE_MAPS_API_KEY,
                            },
                        )
                        details_resp.raise_for_status()
                        detail = details_resp.json().get("result", {})

                        website = detail.get("website")
                        phone = detail.get("formatted_phone_number")
                        address = detail.get("formatted_address")
                        types = detail.get("types", [])
                        if types:
                            # Convert underscore-separated type to title case label
                            industry = types[0].replace("_", " ").title()
                        # Prefer detail-level rating if available
                        rating = detail.get("rating") or rating
                        review_count = detail.get("user_ratings_total") or review_count
                    except Exception:
                        pass  # best-effort details; continue with partial data

                leads.append(
                    DiscoveredLead(
                        name=name,
                        domain=_extract_domain(website),
                        website=website,
                        phone=phone,
                        address=address,
                        industry=industry or req.industry,
                        rating=rating,
                        review_count=review_count,
                        source="google_maps",
                    )
                )
    except Exception:
        return []

    return leads


# ─── AI stub mode ────────────────────────────────────────────────────────────

_AI_SYSTEM_PROMPT = """\
You are a B2B sales intelligence tool. Generate realistic lead data for a Google Maps search.
Return ONLY valid JSON array of business leads matching the search query.
Each lead should be a realistic company with plausible data.

Return format:
[
  {
    "name": "Company Name",
    "domain": "company.com",
    "website": "https://company.com",
    "phone": "+1-555-000-0000",
    "address": "123 Main St, San Francisco, CA 94105",
    "city": "San Francisco",
    "country": "United States",
    "industry": "Software / SaaS",
    "description": "2-sentence company description",
    "employee_count_estimate": 150,
    "rating": 4.3,
    "review_count": 47,
    "technologies": ["Salesforce", "AWS", "Slack"],
    "emails_found": ["sales@company.com"],
    "linkedin_url": "https://linkedin.com/company/...",
    "fit_score_estimate": 78,
    "source": "google_maps_ai"
  }
]\
"""


def _demo_leads(query: str, location: str, limit: int) -> list[DiscoveredLead]:
    """
    Fully static demo leads used when no Google Maps key AND no Anthropic key are present.
    Returns realistic B2B SaaS companies representative of a typical outbound pipeline.
    """
    pool = [
        DiscoveredLead(name="Coda", domain="coda.io", website="https://coda.io", phone="+1-415-555-0101", address="325 Pacific Ave, San Francisco, CA 94111", city="San Francisco", country="United States", industry="Productivity / SaaS", description="All-in-one doc platform that blends spreadsheets, documents, and apps.", employee_count_estimate=350, rating=4.6, review_count=312, technologies=["AWS", "Segment", "Intercom"], emails_found=["sales@coda.io"], linkedin_url="https://linkedin.com/company/coda-hq", fit_score_estimate=87, source="google_maps_demo"),
        DiscoveredLead(name="Retool", domain="retool.com", website="https://retool.com", phone="+1-415-555-0202", address="548 Market St, San Francisco, CA 94104", city="San Francisco", country="United States", industry="Developer Tools / SaaS", description="Low-code platform for building internal tools fast.", employee_count_estimate=420, rating=4.7, review_count=198, technologies=["AWS", "Salesforce", "Stripe", "PagerDuty"], emails_found=["growth@retool.com"], linkedin_url="https://linkedin.com/company/tryretool", fit_score_estimate=91, source="google_maps_demo"),
        DiscoveredLead(name="Hex", domain="hex.tech", website="https://hex.tech", phone="+1-415-555-0303", address="340 Pine St, San Francisco, CA 94104", city="San Francisco", country="United States", industry="Data Analytics / SaaS", description="Collaborative data workspace for analytics and ML.", employee_count_estimate=180, rating=4.5, review_count=87, technologies=["Snowflake", "dbt", "AWS", "Slack"], emails_found=["hello@hex.tech"], linkedin_url="https://linkedin.com/company/hex-technologies", fit_score_estimate=84, source="google_maps_demo"),
        DiscoveredLead(name="Loom", domain="loom.com", website="https://loom.com", phone="+1-415-555-0404", address="222 Kearny St, San Francisco, CA 94108", city="San Francisco", country="United States", industry="Video Communication / SaaS", description="Async video messaging for teams reduces meeting load.", employee_count_estimate=280, rating=4.4, review_count=445, technologies=["AWS", "Segment", "HubSpot", "Intercom"], emails_found=["business@loom.com"], linkedin_url="https://linkedin.com/company/loom-inc", fit_score_estimate=79, source="google_maps_demo"),
        DiscoveredLead(name="Descript", domain="descript.com", website="https://descript.com", phone="+1-415-555-0505", address="55 Second St, San Francisco, CA 94105", city="San Francisco", country="United States", industry="Content Creation / SaaS", description="AI-powered podcast and video editing platform.", employee_count_estimate=150, rating=4.3, review_count=203, technologies=["AWS", "Stripe", "Intercom"], emails_found=["team@descript.com"], linkedin_url="https://linkedin.com/company/descript-team", fit_score_estimate=73, source="google_maps_demo"),
        DiscoveredLead(name="Cal.com", domain="cal.com", website="https://cal.com", phone="+1-415-555-0606", address="340 Pine St Ste 800, San Francisco, CA 94104", city="San Francisco", country="United States", industry="Scheduling / SaaS", description="Open-source scheduling infrastructure for individuals and teams.", employee_count_estimate=75, rating=4.8, review_count=134, technologies=["Vercel", "PostgreSQL", "Stripe"], emails_found=["sales@cal.com"], linkedin_url="https://linkedin.com/company/calcom", fit_score_estimate=68, source="google_maps_demo"),
        DiscoveredLead(name="Brex", domain="brex.com", website="https://brex.com", phone="+1-415-555-0707", address="405 Howard St, San Francisco, CA 94105", city="San Francisco", country="United States", industry="FinTech / SaaS", description="Corporate cards, expense management, and banking for startups.", employee_count_estimate=1100, rating=4.2, review_count=512, technologies=["AWS", "Salesforce", "Snowflake", "Segment"], emails_found=["partnerships@brex.com"], linkedin_url="https://linkedin.com/company/brex-hq", fit_score_estimate=82, source="google_maps_demo"),
        DiscoveredLead(name="Rippling", domain="rippling.com", website="https://rippling.com", phone="+1-415-555-0808", address="55 Second St, San Francisco, CA 94105", city="San Francisco", country="United States", industry="HR / SaaS", description="Unified platform for HR, IT, and Finance operations.", employee_count_estimate=2200, rating=4.6, review_count=892, technologies=["AWS", "Okta", "Salesforce", "Stripe"], emails_found=["sales@rippling.com"], linkedin_url="https://linkedin.com/company/rippling", fit_score_estimate=88, source="google_maps_demo"),
        DiscoveredLead(name="Vanta", domain="vanta.com", website="https://vanta.com", phone="+1-415-555-0909", address="369 Pine St, San Francisco, CA 94104", city="San Francisco", country="United States", industry="Security & Compliance / SaaS", description="Automated security compliance for SOC 2, ISO 27001, HIPAA.", employee_count_estimate=320, rating=4.7, review_count=267, technologies=["AWS", "Salesforce", "Segment", "Intercom"], emails_found=["hello@vanta.com"], linkedin_url="https://linkedin.com/company/vanta", fit_score_estimate=90, source="google_maps_demo"),
        DiscoveredLead(name="Merge", domain="merge.dev", website="https://merge.dev", phone="+1-415-555-1010", address="450 Mission St, San Francisco, CA 94105", city="San Francisco", country="United States", industry="Integration / SaaS", description="Unified API for product integrations one endpoint for HRIS, ATS, CRM.", employee_count_estimate=90, rating=4.5, review_count=78, technologies=["AWS", "Heroku", "Stripe", "Intercom"], emails_found=["sales@merge.dev"], linkedin_url="https://linkedin.com/company/merge-api", fit_score_estimate=86, source="google_maps_demo"),
        DiscoveredLead(name="Replit", domain="replit.com", website="https://replit.com", phone="+1-650-555-1111", address="101 Forest Ave, Palo Alto, CA 94301", city="Palo Alto", country="United States", industry="Developer Tools / SaaS", description="Collaborative browser-based IDE with built-in hosting.", employee_count_estimate=190, rating=4.4, review_count=341, technologies=["AWS", "GCP", "Stripe"], emails_found=["business@replit.com"], linkedin_url="https://linkedin.com/company/replit", fit_score_estimate=77, source="google_maps_demo"),
        DiscoveredLead(name="Clerk", domain="clerk.com", website="https://clerk.com", phone="+1-650-555-1212", address="201 Hamilton Ave, Palo Alto, CA 94301", city="Palo Alto", country="United States", industry="Auth & Identity / SaaS", description="Authentication and user management for modern web apps.", employee_count_estimate=85, rating=4.6, review_count=156, technologies=["Vercel", "AWS", "Stripe"], emails_found=["sales@clerk.com"], linkedin_url="https://linkedin.com/company/clerk-dev", fit_score_estimate=80, source="google_maps_demo"),
        DiscoveredLead(name="Trigger.dev", domain="trigger.dev", website="https://trigger.dev", phone="+1-650-555-1313", address="500 University Ave, Palo Alto, CA 94301", city="Palo Alto", country="United States", industry="Background Jobs / SaaS", description="Open-source background jobs and workflows for developers.", employee_count_estimate=35, rating=4.7, review_count=64, technologies=["AWS", "Vercel", "Stripe"], emails_found=["hello@trigger.dev"], linkedin_url="https://linkedin.com/company/triggerdev", fit_score_estimate=71, source="google_maps_demo"),
        DiscoveredLead(name="Baseten", domain="baseten.co", website="https://baseten.co", phone="+1-415-555-1414", address="185 Berry St, San Francisco, CA 94107", city="San Francisco", country="United States", industry="ML Infrastructure / SaaS", description="Platform for deploying ML models at production scale.", employee_count_estimate=120, rating=4.5, review_count=93, technologies=["AWS", "GCP", "Kubernetes", "Stripe"], emails_found=["sales@baseten.co"], linkedin_url="https://linkedin.com/company/baseten", fit_score_estimate=83, source="google_maps_demo"),
        DiscoveredLead(name="Knock", domain="knock.app", website="https://knock.app", phone="+1-415-555-1515", address="423 Bryant St, San Francisco, CA 94107", city="San Francisco", country="United States", industry="Notifications / SaaS", description="Flexible notification infrastructure for product teams.", employee_count_estimate=45, rating=4.6, review_count=52, technologies=["AWS", "Stripe", "Segment"], emails_found=["hello@knock.app"], linkedin_url="https://linkedin.com/company/knocklabs", fit_score_estimate=76, source="google_maps_demo"),
    ]
    return pool[:limit]


async def _search_via_ai_stub(req: DiscoverySearchRequest) -> list[DiscoveredLead]:
    """
    Generate realistic discovery results using Claude when no API key is available.
    Returns an empty list on any AI / JSON parse failure.
    """
    limit = max(1, min(req.limit, 20))
    industry_hint = req.industry or "any"

    user_prompt = (
        f'Search: "{req.query}" in {req.location}. '
        f"Industry focus: {industry_hint}. "
        f"Return {limit} realistic B2B companies as potential sales leads. "
        f"Focus on companies that would be good prospects for a B2B SaaS sales intelligence tool. "
        f"Make names, domains, and data feel real and varied."
    )

    try:
        result = generate_with_cache(
            system_prompt=_AI_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=2000,
            temperature=0.8,
        )
        raw = result.get("content", "")

        # Strip markdown fences if Claude wraps the JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        items: list[dict] = json.loads(raw)
        leads: list[DiscoveredLead] = []
        for item in items:
            leads.append(
                DiscoveredLead(
                    name=item.get("name", "Unknown"),
                    domain=item.get("domain") or _extract_domain(item.get("website")),
                    website=item.get("website"),
                    phone=item.get("phone"),
                    address=item.get("address"),
                    city=item.get("city"),
                    country=item.get("country"),
                    industry=item.get("industry"),
                    description=item.get("description"),
                    employee_count_estimate=item.get("employee_count_estimate"),
                    rating=item.get("rating"),
                    review_count=item.get("review_count"),
                    technologies=item.get("technologies") or [],
                    emails_found=item.get("emails_found") or [],
                    linkedin_url=item.get("linkedin_url"),
                    fit_score_estimate=item.get("fit_score_estimate", 50),
                    source=item.get("source", "google_maps_ai"),
                )
            )
        return leads
    except Exception:
        # Fall back to curated demo leads when no API key is available
        return _demo_leads(req.query, req.location, limit)


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/search", response_model=DiscoverySearchResponse)
async def search_leads(req: DiscoverySearchRequest):
    """
    Search for businesses matching query + location.

    Uses the Google Maps Places API when GOOGLE_MAPS_API_KEY is set;
    otherwise falls back to an AI-generated stub (demo / no-key mode).
    """
    if req.limit < 1 or req.limit > 20:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 20.")

    use_api = bool(GOOGLE_MAPS_API_KEY)

    if use_api:
        leads = await _search_via_google_maps_api(req)
        # If the API call failed entirely, fall back to AI stub
        if not leads:
            leads = await _search_via_ai_stub(req)
            mode = "ai_stub"
        else:
            mode = "api"
    else:
        leads = await _search_via_ai_stub(req)
        if not leads:
            leads = _demo_leads(req.query, req.location, req.limit)
        mode = "ai_stub"

    return DiscoverySearchResponse(
        leads=leads,
        total=len(leads),
        query=req.query,
        location=req.location,
        mode=mode,
    )


@router.post("/import")
async def import_leads(
    req: ImportLeadsRequest,
    ctx: dict = Depends(get_workspace_context),
    db: Session = Depends(get_db),
):
    """
    Import discovered leads as BizAccount (and optional Contact) records.

    Skips any lead whose name already exists in the workspace to avoid duplicates.
    Returns counts and the new account IDs.
    """
    workspace_id: str = ctx["workspace_id"]

    # Fetch existing account names in this workspace for duplicate detection
    existing_names: set[str] = {
        row[0]
        for row in db.query(BizAccount.name)
        .filter(BizAccount.workspace_id == workspace_id)
        .all()
    }

    imported = 0
    skipped = 0
    account_ids: list[str] = []

    for lead in req.leads:
        if lead.name in existing_names:
            skipped += 1
            continue

        account_id = uuid.uuid4().hex

        # Determine a human-readable location string
        location: Optional[str] = lead.address or lead.city or None

        account = BizAccount(
            id=account_id,
            workspace_id=workspace_id,
            name=lead.name,
            domain=lead.domain,
            industry=lead.industry,
            employee_count=lead.employee_count_estimate,
            location=location,
            description=lead.description,
            stage=req.stage,
            fit_score=lead.fit_score_estimate,
            intent_score=50,
            warmth_score=20,
        )
        db.add(account)

        # Create a seed Contact if emails were harvested
        if lead.emails_found:
            contact = Contact(
                id=uuid.uuid4().hex,
                workspace_id=workspace_id,
                account_id=account_id,
                name=f"{lead.name} Contact",
                email=lead.emails_found[0],
                title="Unknown",
                fit_score=50,
                warmth_score=20,
                engagement_score=0,
                seniority="manager",
            )
            db.add(contact)

        existing_names.add(lead.name)  # prevent intra-batch duplicates
        account_ids.append(account_id)
        imported += 1

    db.commit()

    return {
        "imported": imported,
        "skipped": skipped,
        "account_ids": account_ids,
    }
