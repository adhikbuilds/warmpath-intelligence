"""
Seed script for WarmPath demo database.

Populates SQLite with realistic demo data mirroring what was previously
in the Next.js static demo-data files. Run once before starting the service:

    python seed.py

Safe to re-run uses upsert (update if exists, insert if not).
"""

import json
import sys
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt

# Initialise DB before importing models
from database import SessionLocal, init_db

init_db()

from models.all_models import (  # noqa: E402
    AIUsageLog,
    AuditLog,
    BizAccount,
    Campaign,
    CampaignAsset,
    Contact,
    IntegrationConnection,
    KnowledgeBaseItem,
    RelationshipEdge,
    Signal,
    Task,
    User,
    WarmPath,
    Workspace,
    WorkspaceMember,
)

def _hash_pw(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return utcnow() - timedelta(days=n)


# ─── Upsert helper ────────────────────────────────────────────────────────────


def upsert(db, Model, id: str, **kwargs):
    """Insert or update a record by primary key."""
    obj = db.get(Model, id)
    if obj:
        for k, v in kwargs.items():
            setattr(obj, k, v)
    else:
        obj = Model(id=id, **kwargs)
        db.add(obj)
    return obj


# ─── Main seed function ───────────────────────────────────────────────────────


def seed():
    db = SessionLocal()
    try:
        print("Seeding database...")

        # ── Users ─────────────────────────────────────────────────────────────

        demo_user = upsert(
            db,
            User,
            "user-1",
            email="demo@warmpath.ai",
            name="Adhik Agarwal",
            password=_hash_pw("demo123"),
            role="owner",
            created_at=days_ago(90),
            updated_at=days_ago(1),
        )

        sarah = upsert(
            db,
            User,
            "tm-2",
            email="sarah@warmpath.ai",
            name="Sarah Chen",
            password=_hash_pw("demo123"),
            role="sales_rep",
            created_at=days_ago(80),
            updated_at=days_ago(2),
        )

        rohan = upsert(
            db,
            User,
            "tm-3",
            email="rohan@warmpath.ai",
            name="Rohan Mehta",
            password=_hash_pw("demo123"),
            role="sales_rep",
            created_at=days_ago(75),
            updated_at=days_ago(3),
        )

        maya = upsert(
            db,
            User,
            "tm-4",
            email="maya@warmpath.ai",
            name="Maya Iyer",
            password=_hash_pw("demo123"),
            role="sales_rep",
            created_at=days_ago(70),
            updated_at=days_ago(4),
        )

        db.flush()
        print("  ✓ Users")

        # ── Workspace ─────────────────────────────────────────────────────────

        workspace = upsert(
            db,
            Workspace,
            "ws-1",
            name="WarmPath Demo",
            domain="warmpath.ai",
            industry="SaaS / Developer Tools",
            company_size="11-50",
            website="https://warmpath.ai",
            description="AI-powered GTM platform for relationship-led outbound.",
            region="North America",
            selling_motion="PLG + Sales Assist",
            primary_goal="Pipeline from warm intros",
            plan="growth",
            onboarding_stage="completed",
            health_score=82,
            owner_id="user-1",
            created_at=days_ago(90),
            updated_at=days_ago(1),
        )

        db.flush()
        print("  ✓ Workspace")

        # ── Workspace Members ──────────────────────────────────────────────────

        upsert(
            db,
            WorkspaceMember,
            "wm_demo_001",
            workspace_id="ws-1",
            user_id="user-1",
            role="owner",
            title="CEO",
            relationship_score=92,
            joined_at=days_ago(90),
        )
        upsert(
            db,
            WorkspaceMember,
            "wm_sarah_001",
            workspace_id="ws-1",
            user_id="tm-2",
            role="sales_rep",
            title="Account Executive",
            relationship_score=78,
            joined_at=days_ago(80),
        )
        upsert(
            db,
            WorkspaceMember,
            "wm_rohan_001",
            workspace_id="ws-1",
            user_id="tm-3",
            role="sales_rep",
            title="SDR",
            relationship_score=65,
            joined_at=days_ago(75),
        )
        upsert(
            db,
            WorkspaceMember,
            "wm_maya_001",
            workspace_id="ws-1",
            user_id="tm-4",
            role="sales_rep",
            title="Senior AE",
            relationship_score=84,
            joined_at=days_ago(70),
        )

        db.flush()
        print("  ✓ Workspace Members")

        # ── BizAccounts ───────────────────────────────────────────────────────

        accounts_data = [
            dict(
                id="acct_stripe_001",
                name="Stripe",
                domain="stripe.com",
                industry="Fintech / Payments",
                employee_count=8000,
                location="San Francisco, CA",
                description="Global payment infrastructure for the internet economy.",
                stage="qualified",
                fit_score=94,
                intent_score=88,
                warmth_score=76,
                logo_url="https://logo.clearbit.com/stripe.com",
            ),
            dict(
                id="acct_notion_001",
                name="Notion",
                domain="notion.so",
                industry="Productivity / SaaS",
                employee_count=500,
                location="San Francisco, CA",
                description="All-in-one workspace for notes, tasks, wikis, and databases.",
                stage="intro_sent",
                fit_score=91,
                intent_score=82,
                warmth_score=83,
                logo_url="https://logo.clearbit.com/notion.so",
            ),
            dict(
                id="acct_figma_001",
                name="Figma",
                domain="figma.com",
                industry="Design Tools / SaaS",
                employee_count=1200,
                location="San Francisco, CA",
                description="Collaborative interface design and prototyping platform.",
                stage="engaged",
                fit_score=89,
                intent_score=75,
                warmth_score=71,
                logo_url="https://logo.clearbit.com/figma.com",
            ),
            dict(
                id="acct_linear_001",
                name="Linear",
                domain="linear.app",
                industry="Developer Tools / SaaS",
                employee_count=90,
                location="San Francisco, CA",
                description="Issue tracking and project management for high-performance teams.",
                stage="engaged",
                fit_score=87,
                intent_score=79,
                warmth_score=68,
                logo_url="https://logo.clearbit.com/linear.app",
            ),
            dict(
                id="acct_vercel_001",
                name="Vercel",
                domain="vercel.com",
                industry="Cloud / Developer Tools",
                employee_count=600,
                location="Remote-first",
                description="Platform for frontend developers deploy, scale, and ship faster.",
                stage="prospect",
                fit_score=92,
                intent_score=70,
                warmth_score=55,
                logo_url="https://logo.clearbit.com/vercel.com",
            ),
            dict(
                id="acct_supabase_001",
                name="Supabase",
                domain="supabase.com",
                industry="Developer Tools / Database",
                employee_count=150,
                location="Remote-first",
                description="Open source Firebase alternative PostgreSQL database, auth, and storage.",
                stage="prospect",
                fit_score=88,
                intent_score=65,
                warmth_score=62,
                logo_url="https://logo.clearbit.com/supabase.com",
            ),
            dict(
                id="acct_planetscale_001",
                name="PlanetScale",
                domain="planetscale.com",
                industry="Database / Developer Tools",
                employee_count=200,
                location="San Francisco, CA",
                description="Serverless MySQL platform built for developers.",
                stage="prospect",
                fit_score=85,
                intent_score=60,
                warmth_score=48,
                logo_url="https://logo.clearbit.com/planetscale.com",
            ),
            dict(
                id="acct_railway_001",
                name="Railway",
                domain="railway.app",
                industry="Cloud / Developer Tools",
                employee_count=40,
                location="Remote-first",
                description="Instant deployments, no DevOps required. Modern PaaS.",
                stage="prospect",
                fit_score=82,
                intent_score=55,
                warmth_score=44,
                logo_url="https://logo.clearbit.com/railway.app",
            ),
        ]

        for a in accounts_data:
            upsert(
                db,
                BizAccount,
                a.pop("id"),
                workspace_id="ws-1",
                created_at=days_ago(60),
                updated_at=days_ago(2),
                **a,
            )

        db.flush()
        print("  ✓ BizAccounts (8)")

        # ── Contacts ──────────────────────────────────────────────────────────

        contacts_data = [
            dict(
                id="ctct_stripe_vp_001",
                account_id="acct_stripe_001",
                name="James Park",
                email="james.park@stripe.com",
                title="VP of Sales",
                linkedin_url="https://linkedin.com/in/jamespark",
                seniority="VP",
                department="Sales",
                persona="economic_buyer",
                fit_score=95,
                warmth_score=72,
                engagement_score=68,
            ),
            dict(
                id="ctct_stripe_eng_001",
                account_id="acct_stripe_001",
                name="Priya Krishnan",
                email="priya.k@stripe.com",
                title="Head of Engineering",
                linkedin_url="https://linkedin.com/in/priyakrishnan",
                seniority="Director",
                department="Engineering",
                persona="technical_champion",
                fit_score=88,
                warmth_score=85,
                engagement_score=79,
            ),
            dict(
                id="ctct_notion_cto_001",
                account_id="acct_notion_001",
                name="Ivan Chen",
                email="ivan@notion.so",
                title="CTO",
                linkedin_url="https://linkedin.com/in/ivanchen",
                seniority="C-Suite",
                department="Engineering",
                persona="technical_buyer",
                fit_score=93,
                warmth_score=88,
                engagement_score=82,
            ),
            dict(
                id="ctct_notion_ops_001",
                account_id="acct_notion_001",
                name="Leila Nouri",
                email="leila@notion.so",
                title="Head of Revenue Operations",
                linkedin_url="https://linkedin.com/in/leilanouri",
                seniority="Director",
                department="Operations",
                persona="champion",
                fit_score=90,
                warmth_score=79,
                engagement_score=74,
            ),
            dict(
                id="ctct_figma_vp_001",
                account_id="acct_figma_001",
                name="Tom Reyes",
                email="tom.reyes@figma.com",
                title="VP of Product",
                linkedin_url="https://linkedin.com/in/tomreyes",
                seniority="VP",
                department="Product",
                persona="influencer",
                fit_score=87,
                warmth_score=66,
                engagement_score=58,
            ),
            dict(
                id="ctct_linear_ceo_001",
                account_id="acct_linear_001",
                name="Karri Saarinen",
                email="karri@linear.app",
                title="CEO & Co-founder",
                linkedin_url="https://linkedin.com/in/karrisaarinen",
                seniority="C-Suite",
                department="Leadership",
                persona="economic_buyer",
                fit_score=91,
                warmth_score=73,
                engagement_score=70,
            ),
            dict(
                id="ctct_vercel_cmo_001",
                account_id="acct_vercel_001",
                name="Lee Robinson",
                email="lee@vercel.com",
                title="VP of Developer Experience",
                linkedin_url="https://linkedin.com/in/leeerob",
                seniority="VP",
                department="Product",
                persona="champion",
                fit_score=89,
                warmth_score=60,
                engagement_score=55,
            ),
            dict(
                id="ctct_supabase_cto_001",
                account_id="acct_supabase_001",
                name="Ant Wilson",
                email="ant@supabase.com",
                title="CTO & Co-founder",
                linkedin_url="https://linkedin.com/in/antwilson",
                seniority="C-Suite",
                department="Engineering",
                persona="technical_buyer",
                fit_score=86,
                warmth_score=57,
                engagement_score=52,
            ),
            dict(
                id="ctct_planetscale_vp_001",
                account_id="acct_planetscale_001",
                name="Sammy Larbi",
                email="sammy@planetscale.com",
                title="Head of Sales",
                linkedin_url="https://linkedin.com/in/sammylarbi",
                seniority="Director",
                department="Sales",
                persona="economic_buyer",
                fit_score=84,
                warmth_score=50,
                engagement_score=45,
            ),
            dict(
                id="ctct_railway_ceo_001",
                account_id="acct_railway_001",
                name="Jake Cooper",
                email="jake@railway.app",
                title="CEO & Co-founder",
                linkedin_url="https://linkedin.com/in/jakecooper",
                seniority="C-Suite",
                department="Leadership",
                persona="economic_buyer",
                fit_score=82,
                warmth_score=46,
                engagement_score=40,
            ),
        ]

        for c in contacts_data:
            upsert(
                db,
                Contact,
                c.pop("id"),
                workspace_id="ws-1",
                consent_status="implied",
                created_at=days_ago(55),
                updated_at=days_ago(3),
                **c,
            )

        db.flush()
        print("  ✓ Contacts (10)")

        # ── Relationship Edges ────────────────────────────────────────────────

        edges_data = [
            dict(
                id="edge_001",
                from_type="team_member",
                from_id="user-1",
                from_name="Adhik Agarwal",
                to_type="contact",
                to_id="ctct_stripe_vp_001",
                to_name="James Park",
                relationship_type="worked_together",
                strength_score=88,
                evidence="Worked together at Rippling 2020-2022. James led Sales Ops.",
                source="linkedin",
                last_interaction_at=days_ago(45),
            ),
            dict(
                id="edge_002",
                from_type="team_member",
                from_id="user-1",
                from_name="Adhik Agarwal",
                to_type="contact",
                to_id="ctct_notion_cto_001",
                to_name="Ivan Chen",
                relationship_type="conference_met",
                strength_score=72,
                evidence="Met at SaaStr 2023. Had 30-min coffee chat about PLG.",
                source="manual",
                last_interaction_at=days_ago(120),
            ),
            dict(
                id="edge_003",
                from_type="team_member",
                from_id="tm-2",
                from_name="Sarah Chen",
                to_type="contact",
                to_id="ctct_stripe_eng_001",
                to_name="Priya Krishnan",
                relationship_type="colleague",
                strength_score=95,
                evidence="College roommates at Stanford CS. Still meet monthly.",
                source="linkedin",
                last_interaction_at=days_ago(12),
            ),
            dict(
                id="edge_004",
                from_type="team_member",
                from_id="tm-2",
                from_name="Sarah Chen",
                to_type="contact",
                to_id="ctct_notion_ops_001",
                to_name="Leila Nouri",
                relationship_type="linkedin_connection",
                strength_score=58,
                evidence="Connected after Leila's RevOps conference talk.",
                source="linkedin",
                last_interaction_at=days_ago(90),
            ),
            dict(
                id="edge_005",
                from_type="team_member",
                from_id="tm-3",
                from_name="Rohan Mehta",
                to_type="contact",
                to_id="ctct_figma_vp_001",
                to_name="Tom Reyes",
                relationship_type="conference_met",
                strength_score=65,
                evidence="Met at Config 2024 (Figma's conference). Exchanged ideas on design systems.",
                source="manual",
                last_interaction_at=days_ago(60),
            ),
            dict(
                id="edge_006",
                from_type="team_member",
                from_id="tm-3",
                from_name="Rohan Mehta",
                to_type="contact",
                to_id="ctct_linear_ceo_001",
                to_name="Karri Saarinen",
                relationship_type="linkedin_connection",
                strength_score=48,
                evidence="Twitter/X mutual. Engage on product building threads.",
                source="twitter",
                last_interaction_at=days_ago(30),
            ),
            dict(
                id="edge_007",
                from_type="team_member",
                from_id="tm-4",
                from_name="Maya Iyer",
                to_type="contact",
                to_id="ctct_vercel_cmo_001",
                to_name="Lee Robinson",
                relationship_type="worked_together",
                strength_score=82,
                evidence="Both at Netlify 2019-2021. Maya was on Lee's team.",
                source="linkedin",
                last_interaction_at=days_ago(25),
            ),
            dict(
                id="edge_008",
                from_type="team_member",
                from_id="tm-4",
                from_name="Maya Iyer",
                to_type="contact",
                to_id="ctct_supabase_cto_001",
                to_name="Ant Wilson",
                relationship_type="conference_met",
                strength_score=61,
                evidence="Panel together at YC SaaS Summit 2023.",
                source="manual",
                last_interaction_at=days_ago(80),
            ),
            dict(
                id="edge_009",
                from_type="team_member",
                from_id="user-1",
                from_name="Adhik Agarwal",
                to_type="contact",
                to_id="ctct_planetscale_vp_001",
                to_name="Sammy Larbi",
                relationship_type="linkedin_connection",
                strength_score=44,
                evidence="LinkedIn mutual. Commented on each other's posts.",
                source="linkedin",
                last_interaction_at=days_ago(150),
            ),
            dict(
                id="edge_010",
                from_type="team_member",
                from_id="tm-2",
                from_name="Sarah Chen",
                to_type="contact",
                to_id="ctct_railway_ceo_001",
                to_name="Jake Cooper",
                relationship_type="linkedin_connection",
                strength_score=42,
                evidence="Connected after Jake's PH launch post. DM'd congratulations.",
                source="linkedin",
                last_interaction_at=days_ago(200),
            ),
            # Cross-contact edges (contact→contact, for graph depth)
            dict(
                id="edge_011",
                from_type="contact",
                from_id="ctct_stripe_vp_001",
                from_name="James Park",
                to_type="contact",
                to_id="ctct_notion_cto_001",
                to_name="Ivan Chen",
                relationship_type="conference_met",
                strength_score=55,
                evidence="Both spoke at SaaStr Annual 2023.",
                source="public",
                last_interaction_at=days_ago(120),
            ),
            dict(
                id="edge_012",
                from_type="contact",
                from_id="ctct_stripe_eng_001",
                from_name="Priya Krishnan",
                to_type="contact",
                to_id="ctct_figma_vp_001",
                to_name="Tom Reyes",
                relationship_type="colleague",
                strength_score=70,
                evidence="Both at Google 2016-2018.",
                source="linkedin",
                last_interaction_at=days_ago(365),
            ),
        ]

        for e in edges_data:
            upsert(
                db,
                RelationshipEdge,
                e.pop("id"),
                workspace_id="ws-1",
                created_at=days_ago(50),
                **e,
            )

        db.flush()
        print("  ✓ Relationship Edges (12)")

        # ── Signals ───────────────────────────────────────────────────────────

        signals_data = [
            dict(
                id="sig_stripe_funding_001",
                account_id="acct_stripe_001",
                contact_id=None,
                type="funding_round",
                title="Stripe Series I at $65B valuation",
                description="Stripe raised $694M in a Series I round, signalling major expansion push into APAC and enterprise.",
                source="TechCrunch",
                source_url="https://techcrunch.com/stripe-series-i",
                urgency_score=92,
                confidence_score=98,
                detected_at=days_ago(3),
            ),
            dict(
                id="sig_notion_champion_001",
                account_id="acct_notion_001",
                contact_id="ctct_notion_ops_001",
                type="champion_job_change",
                title="Leila Nouri promoted to VP Revenue Operations at Notion",
                description="Our champion Leila moved from Head to VP RevOps higher budget authority, perfect timing.",
                source="LinkedIn",
                source_url="https://linkedin.com/in/leilanouri",
                urgency_score=95,
                confidence_score=90,
                detected_at=days_ago(5),
            ),
            dict(
                id="sig_figma_job_001",
                account_id="acct_figma_001",
                contact_id=None,
                type="job_posting",
                title="Figma hiring Head of GTM Tools & Automation",
                description="Figma posted for a Head of GTM Tools buying signal for our outreach automation platform.",
                source="Greenhouse",
                source_url="https://boards.greenhouse.io/figma",
                urgency_score=78,
                confidence_score=88,
                detected_at=days_ago(7),
            ),
            dict(
                id="sig_linear_leadership_001",
                account_id="acct_linear_001",
                contact_id=None,
                type="leadership_change",
                title="Linear appoints first VP of Sales",
                description="Linear hired Sarah Guo as VP Sales new exec means new vendor evaluations starting now.",
                source="LinkedIn",
                source_url="https://linkedin.com/company/linear",
                urgency_score=85,
                confidence_score=92,
                detected_at=days_ago(10),
            ),
            dict(
                id="sig_vercel_intent_001",
                account_id="acct_vercel_001",
                contact_id=None,
                type="intent_spike",
                title="Vercel team surge on 'sales automation' intent topics",
                description="6 Vercel employees researched sales automation tools in the past 14 days 3x normal baseline.",
                source="G2 Intent",
                source_url=None,
                urgency_score=82,
                confidence_score=75,
                detected_at=days_ago(4),
            ),
            dict(
                id="sig_supabase_funding_001",
                account_id="acct_supabase_001",
                contact_id=None,
                type="funding_round",
                title="Supabase raises $80M Series C",
                description="Supabase closed $80M Series C. Budget unlocked for tooling expansion.",
                source="Crunchbase",
                source_url="https://crunchbase.com/supabase-series-c",
                urgency_score=88,
                confidence_score=96,
                detected_at=days_ago(14),
            ),
            dict(
                id="sig_planetscale_job_001",
                account_id="acct_planetscale_001",
                contact_id=None,
                type="job_posting",
                title="PlanetScale hiring 5 AEs for enterprise segment",
                description="Aggressive sales hiring signals a push into enterprise they need GTM tooling at scale.",
                source="LinkedIn Jobs",
                source_url="https://linkedin.com/jobs/planetscale",
                urgency_score=68,
                confidence_score=82,
                detected_at=days_ago(20),
            ),
            dict(
                id="sig_railway_product_001",
                account_id="acct_railway_001",
                contact_id=None,
                type="product_launch",
                title="Railway launches enterprise tier with SSO",
                description="Railway announced enterprise features maturity signal, they're moving upmarket.",
                source="Railway Blog",
                source_url="https://blog.railway.app/enterprise",
                urgency_score=55,
                confidence_score=85,
                detected_at=days_ago(25),
            ),
        ]

        for s in signals_data:
            detected = s.pop("detected_at")
            upsert(
                db,
                Signal,
                s.pop("id"),
                workspace_id="ws-1",
                detected_at=detected,
                created_at=detected,
                **s,
            )

        db.flush()
        print("  ✓ Signals (8)")

        # ── Warm Paths ────────────────────────────────────────────────────────

        warm_paths_data = [
            dict(
                id="wp_stripe_james_001",
                account_id="acct_stripe_001",
                contact_id="ctct_stripe_vp_001",
                path_json=json.dumps([
                    {"type": "team_member", "id": "user-1", "name": "Adhik Agarwal", "role": "Sender"},
                    {"type": "contact", "id": "ctct_stripe_vp_001", "name": "James Park", "role": "Target", "connection": "worked_together"},
                ]),
                explanation="Direct warm path Adhik and James worked together at Rippling. 1-hop intro, highest confidence.",
                warmth_score=88,
                confidence_score=92,
                recommended_intro_person="Adhik Agarwal",
                recommended_channel="email",
                status="active",
            ),
            dict(
                id="wp_stripe_priya_001",
                account_id="acct_stripe_001",
                contact_id="ctct_stripe_eng_001",
                path_json=json.dumps([
                    {"type": "team_member", "id": "tm-2", "name": "Sarah Chen", "role": "Sender"},
                    {"type": "contact", "id": "ctct_stripe_eng_001", "name": "Priya Krishnan", "role": "Target", "connection": "colleague"},
                ]),
                explanation="Sarah and Priya are college friends strongest possible intro path into Stripe Engineering.",
                warmth_score=95,
                confidence_score=96,
                recommended_intro_person="Sarah Chen",
                recommended_channel="email",
                status="active",
            ),
            dict(
                id="wp_notion_ivan_001",
                account_id="acct_notion_001",
                contact_id="ctct_notion_cto_001",
                path_json=json.dumps([
                    {"type": "team_member", "id": "user-1", "name": "Adhik Agarwal", "role": "Sender"},
                    {"type": "contact", "id": "ctct_notion_cto_001", "name": "Ivan Chen", "role": "Target", "connection": "conference_met"},
                ]),
                explanation="Adhik met Ivan at SaaStr 2023. Reference the PLG conversation to re-open the loop.",
                warmth_score=72,
                confidence_score=78,
                recommended_intro_person="Adhik Agarwal",
                recommended_channel="linkedin",
                status="active",
            ),
            dict(
                id="wp_vercel_lee_001",
                account_id="acct_vercel_001",
                contact_id="ctct_vercel_cmo_001",
                path_json=json.dumps([
                    {"type": "team_member", "id": "tm-4", "name": "Maya Iyer", "role": "Sender"},
                    {"type": "contact", "id": "ctct_vercel_cmo_001", "name": "Lee Robinson", "role": "Target", "connection": "worked_together"},
                ]),
                explanation="Maya and Lee worked together at Netlify. Strong relationship Lee is very reachable via email.",
                warmth_score=82,
                confidence_score=87,
                recommended_intro_person="Maya Iyer",
                recommended_channel="email",
                status="active",
            ),
            dict(
                id="wp_figma_tom_001",
                account_id="acct_figma_001",
                contact_id="ctct_figma_vp_001",
                path_json=json.dumps([
                    {"type": "team_member", "id": "tm-3", "name": "Rohan Mehta", "role": "Sender"},
                    {"type": "contact", "id": "ctct_figma_vp_001", "name": "Tom Reyes", "role": "Target", "connection": "conference_met"},
                    {"type": "contact", "id": "ctct_stripe_eng_001", "name": "Priya Krishnan", "role": "Mutual Connection"},
                ]),
                explanation="2-hop via Rohan → Tom (Config 2024) with Priya as mutual connection. Warm but not direct.",
                warmth_score=65,
                confidence_score=70,
                recommended_intro_person="Rohan Mehta",
                recommended_channel="linkedin",
                status="active",
            ),
        ]

        for wp in warm_paths_data:
            upsert(
                db,
                WarmPath,
                wp.pop("id"),
                workspace_id="ws-1",
                created_at=days_ago(30),
                **wp,
            )

        db.flush()
        print("  ✓ Warm Paths (5)")

        # ── Campaigns ─────────────────────────────────────────────────────────

        upsert(
            db,
            Campaign,
            "camp_stripe_001",
            workspace_id="ws-1",
            owner_id="user-1",
            name="Stripe Post-Funding Outreach",
            type="outbound",
            goal="Land intro with VP Sales or CTO within 2 weeks of funding announcement.",
            status="active",
            target_segment="Stripe leadership (VP+)",
            channels_json=json.dumps(["email", "linkedin"]),
            created_at=days_ago(3),
            updated_at=days_ago(1),
        )

        upsert(
            db,
            Campaign,
            "camp_notion_001",
            workspace_id="ws-1",
            owner_id="tm-2",
            name="Notion Champion Nurture",
            type="nurture",
            goal="Re-engage Ivan Chen + support Leila's new VP role with relevant content.",
            status="active",
            target_segment="Notion CTO + VP RevOps",
            channels_json=json.dumps(["email", "linkedin", "slack"]),
            created_at=days_ago(10),
            updated_at=days_ago(2),
        )

        upsert(
            db,
            Campaign,
            "camp_q1_review_001",
            workspace_id="ws-1",
            owner_id="user-1",
            name="Q1 2026 Outbound Blitz",
            type="outbound",
            goal="Hit 50 warm intros across top 10 ICP accounts by end of Q1.",
            status="completed",
            target_segment="Series B+ SaaS, 100-2000 employees",
            channels_json=json.dumps(["email", "linkedin", "phone"]),
            created_at=days_ago(90),
            updated_at=days_ago(30),
        )

        db.flush()
        print("  ✓ Campaigns (3)")

        # ── Campaign Assets ───────────────────────────────────────────────────

        assets_data = [
            dict(
                id="asset_stripe_email_001",
                campaign_id="camp_stripe_001",
                account_id="acct_stripe_001",
                contact_id="ctct_stripe_vp_001",
                channel="email",
                type="email_body",
                title="Stripe Post-funding personalised email to James Park",
                content=(
                    "Hi James,\n\n"
                    "Congrats on the Series I the $65B valuation reflects the incredible GTM engine "
                    "you've built. I remember when we were figuring out pipeline velocity together at "
                    "Rippling seems like a lifetime ago.\n\n"
                    "Given the expansion push, I wanted to share how WarmPath has helped teams like "
                    "yours map relationship graphs to warm intro paths cutting cold outbound by 60%.\n\n"
                    "Worth a 20-minute catch-up? Happy to flex around your schedule.\n\n"
                    "Warm regards,\nAdhik"
                ),
                subject="Congrats on the Series I quick catch-up?",
                headline="Post-funding outreach leveraging shared Rippling history",
                preview="Re: your Series I + something that might be useful",
                approval_status="approved",
                launch_status="sent",
                quality_score=91,
                confidence_score=88,
                generated_by_ai=True,
            ),
            dict(
                id="asset_notion_linkedin_001",
                campaign_id="camp_notion_001",
                account_id="acct_notion_001",
                contact_id="ctct_notion_cto_001",
                channel="linkedin",
                type="linkedin_message",
                title="Notion CTO LinkedIn DM re: PLG scaling",
                content=(
                    "Ivan great to connect at SaaStr last year. "
                    "Saw Notion just crossed 4M paid users, impressive growth. "
                    "We've been helping PLG teams map warm paths to enterprise buyers "
                    "the results are pretty surprising. "
                    "Would love to show you the graph we've built for Notion's network. "
                    "15 minutes this week?"
                ),
                subject=None,
                headline="Referencing SaaStr meeting + Notion PLG milestone",
                preview=None,
                approval_status="pending",
                launch_status="pending",
                quality_score=84,
                confidence_score=80,
                generated_by_ai=True,
            ),
            dict(
                id="asset_stripe_linkedin_001",
                campaign_id="camp_stripe_001",
                account_id="acct_stripe_001",
                contact_id="ctct_stripe_eng_001",
                channel="linkedin",
                type="linkedin_message",
                title="Stripe Engineering LinkedIn intro via Sarah",
                content=(
                    "Priya! Sarah Chen from our team mentioned you might be exploring "
                    "outreach automation tools for the engineering org. "
                    "WarmPath was built for exactly this relationship-first GTM. "
                    "Can I grab 15 minutes to walk you through what Sarah's team has seen?"
                ),
                subject=None,
                headline="Warm intro via Sarah Chen (college connection)",
                preview=None,
                approval_status="approved",
                launch_status="pending",
                quality_score=89,
                confidence_score=93,
                generated_by_ai=True,
            ),
            dict(
                id="asset_figma_email_001",
                campaign_id=None,
                account_id="acct_figma_001",
                contact_id="ctct_figma_vp_001",
                channel="email",
                type="email_body",
                title="Figma Job posting hook email to Tom Reyes",
                content=(
                    "Tom,\n\n"
                    "Noticed Figma is hiring a Head of GTM Tools & Automation that role "
                    "essentially owns what WarmPath does out-of-the-box.\n\n"
                    "Instead of hiring for it, some teams use us to get 80% of the outcome "
                    "in 2 weeks. Happy to share benchmarks.\n\n"
                    "Rohan Mehta"
                ),
                subject="Re: your GTM Tools hiring an alternative worth 15 min",
                headline="Job posting as conversation opener",
                preview=None,
                approval_status="draft",
                launch_status="pending",
                quality_score=78,
                confidence_score=74,
                generated_by_ai=True,
            ),
            dict(
                id="asset_vercel_email_001",
                campaign_id=None,
                account_id="acct_vercel_001",
                contact_id="ctct_vercel_cmo_001",
                channel="email",
                type="email_body",
                title="Vercel Re-activation email from Maya to Lee",
                content=(
                    "Lee,\n\n"
                    "Miss the Netlify days! Saw what Vercel's been doing with DX "
                    "incredible momentum.\n\n"
                    "We've been building something I think you'd find interesting: "
                    "WarmPath maps your team's relationship graph to find the warmest "
                    "path to any buyer. Given Vercel's community-led growth, your graph "
                    "is probably extraordinary.\n\n"
                    "Coffee (virtual) soon?\n\nMaya"
                ),
                subject="Netlify alumni catching up plus something cool",
                headline="Relationship-first re-activation via shared Netlify history",
                preview=None,
                approval_status="pending",
                launch_status="pending",
                quality_score=86,
                confidence_score=84,
                generated_by_ai=True,
            ),
        ]

        for a in assets_data:
            upsert(
                db,
                CampaignAsset,
                a.pop("id"),
                workspace_id="ws-1",
                extra_json=None,
                created_at=days_ago(5),
                updated_at=days_ago(1),
                **a,
            )

        db.flush()
        print("  ✓ Campaign Assets (5)")

        # ── Knowledge Base Items ───────────────────────────────────────────────

        kb_data = [
            dict(
                id="kb_onepager_001",
                title="WarmPath Product One-Pager",
                type="one_pager",
                content=(
                    "WarmPath is an AI-first GTM platform that maps your team's relationship graph "
                    "and finds the warmest intro path to any prospect. We combine LinkedIn data, "
                    "email history, and CRM signals to score every relationship 0-100, then generate "
                    "personalised multi-channel outreach sequences. Teams using WarmPath see 3x reply "
                    "rates and 60% reduction in cold outbound within 90 days."
                ),
                source="Internal",
                tags_json=json.dumps(["product", "overview", "one_pager"]),
                confidence_score=95,
                approved_for_ai=True,
            ),
            dict(
                id="kb_case_study_rippling_001",
                title="Case Study: How Rippling Hit 40% Warm Intro Rate",
                type="case_study",
                content=(
                    "Rippling's outbound team used WarmPath to map 2,400 relationship edges across "
                    "their 35-person sales org. Result: 40% of new opportunities now start with a "
                    "warm intro up from 12%. Average deal cycle shortened by 28 days. "
                    "Key insight: their engineering network had 3x more connections to target buyers "
                    "than the sales team alone."
                ),
                source="Customer Story",
                tags_json=json.dumps(["case_study", "rippling", "results", "HR-tech"]),
                confidence_score=92,
                approved_for_ai=True,
            ),
            dict(
                id="kb_pricing_001",
                title="WarmPath Pricing Growth & Enterprise",
                type="pricing",
                content=(
                    "Growth: $2,000/month up to 10 seats, 500 accounts tracked, unlimited warm path "
                    "computations, email + LinkedIn channels.\n"
                    "Enterprise: Custom pricing unlimited seats, all channels (phone, WhatsApp, "
                    "Telegram), Salesforce bi-directional sync, dedicated CSM, SLA 99.9%.\n"
                    "ROI benchmark: customers report $180K average annual value from reduced SDR hours "
                    "and faster deal velocity."
                ),
                source="Pricing Page",
                tags_json=json.dumps(["pricing", "growth", "enterprise", "ROI"]),
                confidence_score=98,
                approved_for_ai=True,
            ),
            dict(
                id="kb_objection_security_001",
                title="Objection Handling: Data Security & Privacy",
                type="faq",
                content=(
                    "Q: How does WarmPath handle GDPR and CCPA compliance?\n"
                    "A: WarmPath processes only publicly-available relationship data and signals "
                    "the user explicitly imports. All PII is encrypted at rest (AES-256) and in transit "
                    "(TLS 1.3). We are SOC 2 Type II certified and offer DPA agreements for EU customers. "
                    "Consent tracking is built into every contact record."
                ),
                source="Security FAQ",
                tags_json=json.dumps(["security", "GDPR", "CCPA", "compliance", "objection"]),
                confidence_score=90,
                approved_for_ai=True,
            ),
            dict(
                id="kb_competitor_outreach_001",
                title="Competitive Positioning vs. Outreach.io & SalesLoft",
                type="competitive",
                content=(
                    "WarmPath vs Outreach/SalesLoft: Those platforms automate sequences; "
                    "WarmPath finds the *right* path before you send a single message. "
                    "Key differentiators: (1) Relationship graph BFS engine no competitor has this. "
                    "(2) AI generates intros from the actual relationship context, not templates. "
                    "(3) Works alongside existing SEPs doesn't replace them. "
                    "Positioning: 'The layer that makes your Outreach sequences actually land.'"
                ),
                source="Sales Playbook",
                tags_json=json.dumps(["competitive", "outreach", "salesloft", "positioning"]),
                confidence_score=87,
                approved_for_ai=True,
            ),
        ]

        for k in kb_data:
            upsert(
                db,
                KnowledgeBaseItem,
                k.pop("id"),
                workspace_id="ws-1",
                used_in_messages=0,
                created_at=days_ago(45),
                updated_at=days_ago(10),
                **k,
            )

        db.flush()
        print("  ✓ Knowledge Base Items (5)")

        # ── Integrations ──────────────────────────────────────────────────────

        integrations_data = [
            dict(
                id="intg_gmail_001",
                provider="gmail",
                channel="email",
                display_name="Gmail",
                description="Send and track emails directly from your Google Workspace inbox.",
                status="disconnected",
                auth_type="oauth2",
                capabilities_json=json.dumps(["send", "track_opens", "track_clicks", "inbox_sync"]),
                icon_color="#EA4335",
                demo_mode=False,
            ),
            dict(
                id="intg_linkedin_001",
                provider="linkedin",
                channel="social",
                display_name="LinkedIn Sales Navigator",
                description="Sync connections, send InMails, and track profile views.",
                status="disconnected",
                auth_type="oauth2",
                capabilities_json=json.dumps(["connection_sync", "inmail", "profile_view_alerts", "lead_lists"]),
                icon_color="#0A66C2",
                demo_mode=False,
            ),
            dict(
                id="intg_slack_001",
                provider="slack",
                channel="messaging",
                display_name="Slack",
                description="Get approval notifications and send intro requests via Slack.",
                status="disconnected",
                auth_type="oauth2",
                capabilities_json=json.dumps(["notifications", "approval_workflow", "intro_requests"]),
                icon_color="#4A154B",
                demo_mode=False,
            ),
            dict(
                id="intg_hubspot_001",
                provider="hubspot",
                channel="crm",
                display_name="HubSpot CRM",
                description="Bi-directional sync of contacts, accounts, and deal stages.",
                status="disconnected",
                auth_type="oauth2",
                capabilities_json=json.dumps(["contact_sync", "account_sync", "deal_sync", "activity_log"]),
                icon_color="#FF7A59",
                demo_mode=False,
            ),
        ]

        for i in integrations_data:
            upsert(
                db,
                IntegrationConnection,
                i.pop("id"),
                workspace_id="ws-1",
                sync_status=None,
                last_sync_at=None,
                health_score=None,
                created_at=days_ago(60),
                updated_at=days_ago(60),
                **i,
            )

        db.flush()
        print("  ✓ Integrations (4)")

        # ── Audit Logs ────────────────────────────────────────────────────────

        audit_entries = [
            dict(id="audit_001", actor_name="Adhik Agarwal", actor_user_id="user-1", action="workspace.created", entity_type="workspace", entity_id="ws-1", entity_name="WarmPath Demo", created_at=days_ago(90)),
            dict(id="audit_002", actor_name="Adhik Agarwal", actor_user_id="user-1", action="account.created", entity_type="account", entity_id="acct_stripe_001", entity_name="Stripe", created_at=days_ago(60)),
            dict(id="audit_003", actor_name="Sarah Chen", actor_user_id="tm-2", action="account.created", entity_type="account", entity_id="acct_notion_001", entity_name="Notion", created_at=days_ago(58)),
            dict(id="audit_004", actor_name="Adhik Agarwal", actor_user_id="user-1", action="campaign.created", entity_type="campaign", entity_id="camp_stripe_001", entity_name="Stripe Post-Funding Outreach", created_at=days_ago(3)),
            dict(id="audit_005", actor_name="Sarah Chen", actor_user_id="tm-2", action="campaign.created", entity_type="campaign", entity_id="camp_notion_001", entity_name="Notion Champion Nurture", created_at=days_ago(10)),
            dict(id="audit_006", actor_name="Adhik Agarwal", actor_user_id="user-1", action="asset.approved", entity_type="campaign_asset", entity_id="asset_stripe_email_001", entity_name="Stripe Post-funding personalised email to James Park", created_at=days_ago(2)),
            dict(id="audit_007", actor_name="System", actor_user_id=None, action="signal.detected", entity_type="signal", entity_id="sig_stripe_funding_001", entity_name="Stripe Series I at $65B valuation", created_at=days_ago(3)),
            dict(id="audit_008", actor_name="System", actor_user_id=None, action="signal.detected", entity_type="signal", entity_id="sig_notion_champion_001", entity_name="Leila Nouri promoted to VP Revenue Operations", created_at=days_ago(5)),
            dict(id="audit_009", actor_name="Rohan Mehta", actor_user_id="tm-3", action="contact.created", entity_type="contact", entity_id="ctct_figma_vp_001", entity_name="Tom Reyes", created_at=days_ago(55)),
            dict(id="audit_010", actor_name="Maya Iyer", actor_user_id="tm-4", action="warm_path.computed", entity_type="warm_path", entity_id="wp_vercel_lee_001", entity_name="Vercel → Lee Robinson", created_at=days_ago(30)),
        ]

        for entry in audit_entries:
            created = entry.pop("created_at")
            upsert(
                db,
                AuditLog,
                entry.pop("id"),
                workspace_id="ws-1",
                created_at=created,
                metadata_json=None,
                **entry,
            )

        db.flush()
        print("  ✓ Audit Logs (10)")

        # ── Tasks ─────────────────────────────────────────────────────────────

        tasks_data = [
            dict(
                id="task_001",
                owner_id="user-1",
                account_id="acct_stripe_001",
                contact_id="ctct_stripe_vp_001",
                campaign_id="camp_stripe_001",
                type="email",
                title="Send post-funding email to James Park",
                description="Asset approved send the personalised email referencing Rippling history.",
                priority="high",
                status="pending",
                due_at=utcnow() + timedelta(days=1),
            ),
            dict(
                id="task_002",
                owner_id="tm-2",
                account_id="acct_notion_001",
                contact_id="ctct_notion_cto_001",
                campaign_id="camp_notion_001",
                type="linkedin",
                title="Send LinkedIn DM to Ivan Chen",
                description="Review and send the LinkedIn message referencing SaaStr 2023.",
                priority="high",
                status="pending",
                due_at=utcnow() + timedelta(days=2),
            ),
            dict(
                id="task_003",
                owner_id="tm-4",
                account_id="acct_vercel_001",
                contact_id="ctct_vercel_cmo_001",
                campaign_id=None,
                type="email",
                title="Follow up with Lee Robinson Netlify angle",
                description="Draft personalised email using Netlify shared history. Asset ready for review.",
                priority="medium",
                status="pending",
                due_at=utcnow() - timedelta(days=1),  # Overdue tests overdue count
            ),
        ]

        for t in tasks_data:
            due = t.pop("due_at")
            upsert(
                db,
                Task,
                t.pop("id"),
                workspace_id="ws-1",
                due_at=due,
                created_at=days_ago(5),
                updated_at=days_ago(1),
                **t,
            )

        db.flush()
        print("  ✓ Tasks (3)")

        # ── Commit everything ─────────────────────────────────────────────────

        db.commit()
        print("\nSeed complete. Database ready.")

    except Exception as e:
        db.rollback()
        print(f"\nSeed failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
