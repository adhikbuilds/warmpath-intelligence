"""
Contact and account enrichment endpoints.
POST /enrich/contact  enrich a contact via Proxycurl (stub)
POST /enrich/account  enrich an account via Clearbit/Apollo (stub)
POST /enrich/batch    batch enrich up to 25 contacts
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ContactEnrichRequest(BaseModel):
    linkedin_url: str | None = None
    email: str | None = None
    name: str | None = None
    company: str | None = None


class AccountEnrichRequest(BaseModel):
    domain: str | None = None
    name: str | None = None
    linkedin_url: str | None = None


class BatchEnrichRequest(BaseModel):
    contacts: list[ContactEnrichRequest]
    workspace_id: str


def _stub_contact_enrichment(req: ContactEnrichRequest) -> dict[str, Any]:
    """
    Stub enrichment in production: Proxycurl People API.
    Returns a realistic-looking enriched contact profile.
    """
    name = req.name or "Unknown Contact"
    company = req.company or "Unknown Company"
    return {
        "name": name,
        "title": "VP of Sales",
        "company": company,
        "linkedin_url": req.linkedin_url,
        "email": req.email,
        "location": "San Francisco, CA",
        "connections": 847,
        "headline": f"VP of Sales at {company} | Revenue Leader",
        "summary": f"Experienced sales leader at {company} focused on enterprise growth.",
        "skills": ["Enterprise Sales", "SaaS", "Revenue Operations", "Go-to-Market"],
        "education": [{"school": "Stanford University", "degree": "MBA", "year": 2015}],
        "experience": [
            {"company": company, "title": "VP of Sales", "duration_months": 24},
            {"company": "Previous Corp", "title": "Director of Sales", "duration_months": 36},
        ],
        "enriched": True,
        "source": "proxycurl_stub",
    }


def _stub_account_enrichment(req: AccountEnrichRequest) -> dict[str, Any]:
    """
    Stub enrichment in production: Clearbit Company API + Apollo.io.
    """
    name = req.name or "Unknown Company"
    domain = req.domain or f"{name.lower().replace(' ', '')}.com"
    return {
        "name": name,
        "domain": domain,
        "linkedin_url": req.linkedin_url,
        "description": f"{name} is a B2B SaaS company focused on enterprise solutions.",
        "industry": "Software & Technology",
        "employee_count": 250,
        "employee_range": "201-500",
        "founded_year": 2018,
        "location": "San Francisco, CA",
        "technologies": ["Salesforce", "HubSpot", "AWS", "Slack", "Notion"],
        "funding": {
            "total_raised_usd": 45_000_000,
            "last_round": "Series B",
            "last_round_date": "2024-03-15",
        },
        "metrics": {
            "alexa_rank": 125_000,
            "g2_rating": 4.3,
            "g2_reviews": 87,
        },
        "enriched": True,
        "source": "clearbit_stub",
    }


@router.post("/contact")
async def enrich_contact(req: ContactEnrichRequest):
    """
    Enrich a single contact.
    Requires at least one of: linkedin_url, email, or (name + company).
    """
    if not req.linkedin_url and not req.email and not (req.name and req.company):
        raise HTTPException(
            status_code=422,
            detail="Provide linkedin_url, email, or both name and company.",
        )
    return _stub_contact_enrichment(req)


@router.post("/account")
async def enrich_account(req: AccountEnrichRequest):
    """Enrich a single account by domain or name."""
    if not req.domain and not req.name:
        raise HTTPException(status_code=422, detail="Provide domain or name.")
    return _stub_account_enrichment(req)


@router.post("/batch")
async def batch_enrich(req: BatchEnrichRequest):
    """
    Batch enrich up to 25 contacts.
    In production: parallel Proxycurl requests with rate-limit handling.
    """
    if len(req.contacts) > 25:
        raise HTTPException(status_code=422, detail="Batch limit is 25 contacts.")

    results = []
    errors = []
    for i, contact in enumerate(req.contacts):
        try:
            enriched = _stub_contact_enrichment(contact)
            results.append({"index": i, "status": "ok", "data": enriched})
        except Exception as e:
            errors.append({"index": i, "status": "error", "detail": str(e)})

    return {
        "results": results,
        "errors": errors,
        "enriched_count": len(results),
        "error_count": len(errors),
        "workspace_id": req.workspace_id,
    }
