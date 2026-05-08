"""
WarmPath Intelligence Service FastAPI

Handles signal scoring, graph computation, AI generation, enrichment,
and (as of v0.2) owns the full SQL data layer for the Next.js frontend.

All routes require X-Service-Secret header (shared secret auth).
Data CRUD routes additionally require X-User-Id for workspace scoping.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import agents, auth, classify, discovery, enrich, graph, scoring, sequences, signals
from routers.data import (
    accounts,
    ai_usage,
    approvals,
    audit_log,
    campaigns,
    contacts,
    dashboard,
    integrations,
    knowledge_base,
    messages,
    relationship_edges,
    signals as data_signals,
    tasks,
    warm_paths,
    workspace,
)
from scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    from database import init_db

    init_db()
    start_scheduler()
    print("WarmPath intelligence service starting up")
    yield
    stop_scheduler()
    print("WarmPath intelligence service shutting down")


app = FastAPI(
    title="WarmPath Intelligence Service",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS only Next.js origin in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Shared secret auth middleware ────────────────────────────────────────────

SERVICE_SECRET = os.getenv("INTELLIGENCE_SERVICE_SECRET", "")


@app.middleware("http")
async def require_service_secret(request: Request, call_next):
    # Skip auth on health and docs endpoints
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    if SERVICE_SECRET:
        provided = request.headers.get("X-Service-Secret", "")
        if provided != SERVICE_SECRET:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

    return await call_next(request)


# ─── Intelligence routers (existing) ─────────────────────────────────────────

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(signals.router, prefix="/signals", tags=["signals"])
app.include_router(graph.router, prefix="/graph", tags=["graph"])
app.include_router(enrich.router, prefix="/enrich", tags=["enrich"])
app.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
app.include_router(sequences.router, prefix="/sequences", tags=["sequences"])
app.include_router(classify.router, prefix="/classify", tags=["classify"])
app.include_router(discovery.router, prefix="/discovery", tags=["discovery"])

# ─── Data CRUD routers ────────────────────────────────────────────────────────
# All mounted under /api/ to avoid collision with intelligence routers.

app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["contacts"])
app.include_router(data_signals.router, prefix="/api/signals", tags=["data-signals"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(messages.router, prefix="/api/messages", tags=["messages"])
app.include_router(knowledge_base.router, prefix="/api/knowledge-base", tags=["knowledge-base"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(relationship_edges.router, prefix="/api/relationship-edges", tags=["relationship-edges"])
app.include_router(warm_paths.router, prefix="/api/warm-paths", tags=["warm-paths"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(ai_usage.router, prefix="/api/ai-usage", tags=["ai-usage"])
app.include_router(audit_log.router, prefix="/api/audit-log", tags=["audit-log"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(workspace.router, prefix="/api/workspaces", tags=["workspaces"])


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "service": "warmpath-intelligence", "version": "0.2.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8001")), reload=True)
