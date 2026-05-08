"""
All SQLAlchemy ORM models for WarmPath in one file.

Keeping them together avoids circular import complexity and makes
relationships easy to trace. Follows the multi-tenant pattern: every
entity (except User) is scoped to a workspace_id.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── User ─────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=new_id)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    password = Column(String, nullable=True)  # bcrypt hash
    role = Column(String, default="owner", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    owned_workspaces = relationship("Workspace", back_populates="owner", foreign_keys="Workspace.owner_id")
    workspace_members = relationship("WorkspaceMember", back_populates="user", foreign_keys="WorkspaceMember.user_id")
    campaigns = relationship("Campaign", back_populates="owner", foreign_keys="Campaign.owner_id")
    approvals = relationship("Approval", back_populates="user", foreign_keys="Approval.user_id")
    audit_logs = relationship("AuditLog", back_populates="actor", foreign_keys="AuditLog.actor_user_id")
    ai_usage_logs = relationship("AIUsageLog", back_populates="user", foreign_keys="AIUsageLog.user_id")
    tasks = relationship("Task", back_populates="owner", foreign_keys="Task.owner_id")


# ─── Workspace ────────────────────────────────────────────────────────────────


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    company_size = Column(String, nullable=True)
    website = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    region = Column(String, nullable=True)
    selling_motion = Column(String, nullable=True)
    primary_goal = Column(String, nullable=True)
    plan = Column(String, default="free", nullable=False)
    onboarding_stage = Column(String, default="not_started", nullable=False)
    health_score = Column(Integer, default=75, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="owned_workspaces", foreign_keys=[owner_id])
    members = relationship("WorkspaceMember", back_populates="workspace")
    biz_accounts = relationship("BizAccount", back_populates="workspace")
    contacts = relationship("Contact", back_populates="workspace")
    relationship_edges = relationship("RelationshipEdge", back_populates="workspace")
    warm_paths = relationship("WarmPath", back_populates="workspace")
    signals = relationship("Signal", back_populates="workspace")
    campaigns = relationship("Campaign", back_populates="workspace")
    campaign_assets = relationship("CampaignAsset", back_populates="workspace")
    messages = relationship("Message", back_populates="workspace")
    approvals = relationship("Approval", back_populates="workspace")
    kb_items = relationship("KnowledgeBaseItem", back_populates="workspace")
    integrations = relationship("IntegrationConnection", back_populates="workspace")
    ai_usage_logs = relationship("AIUsageLog", back_populates="workspace")
    audit_logs = relationship("AuditLog", back_populates="workspace")
    tasks = relationship("Task", back_populates="workspace")


# ─── WorkspaceMember ──────────────────────────────────────────────────────────


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),)

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, default="sales_rep", nullable=False)
    title = Column(String, nullable=True)
    relationship_score = Column(Integer, default=0, nullable=False)
    joined_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="workspace_members", foreign_keys=[user_id])


# ─── BizAccount ───────────────────────────────────────────────────────────────


class BizAccount(Base):
    __tablename__ = "biz_accounts"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    stage = Column(String, default="prospect", nullable=False)
    fit_score = Column(Integer, default=0, nullable=False)
    intent_score = Column(Integer, default=0, nullable=False)
    warmth_score = Column(Integer, default=0, nullable=False)
    logo_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="biz_accounts")
    contacts = relationship("Contact", back_populates="account")
    signals = relationship("Signal", back_populates="account")
    warm_paths = relationship("WarmPath", back_populates="account")
    campaign_assets = relationship("CampaignAsset", back_populates="account")
    messages = relationship("Message", back_populates="account")
    tasks = relationship("Task", back_populates="account")


# ─── Contact ──────────────────────────────────────────────────────────────────


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("biz_accounts.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    title = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    seniority = Column(String, nullable=True)
    department = Column(String, nullable=True)
    persona = Column(String, nullable=True)
    fit_score = Column(Integer, default=0, nullable=False)
    warmth_score = Column(Integer, default=0, nullable=False)
    engagement_score = Column(Integer, default=0, nullable=False)
    consent_status = Column(String, default="unknown", nullable=False)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="contacts")
    account = relationship("BizAccount", back_populates="contacts")
    signals = relationship("Signal", back_populates="contact")
    warm_paths = relationship("WarmPath", back_populates="contact")
    campaign_assets = relationship("CampaignAsset", back_populates="contact")
    messages = relationship("Message", back_populates="contact")
    tasks = relationship("Task", back_populates="contact")


# ─── RelationshipEdge ─────────────────────────────────────────────────────────


class RelationshipEdge(Base):
    __tablename__ = "relationship_edges"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    from_type = Column(String, nullable=False)  # "team_member" | "contact"
    from_id = Column(String, nullable=False)
    from_name = Column(String, nullable=False)
    to_type = Column(String, nullable=False)
    to_id = Column(String, nullable=False)
    to_name = Column(String, nullable=False)
    relationship_type = Column(String, nullable=False)  # colleague, conference_met, etc.
    strength_score = Column(Integer, default=50, nullable=False)
    evidence = Column(Text, nullable=True)
    source = Column(String, nullable=True)
    last_interaction_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="relationship_edges")


# ─── WarmPath ─────────────────────────────────────────────────────────────────


class WarmPath(Base):
    __tablename__ = "warm_paths"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("biz_accounts.id"), nullable=True)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=True)
    path_json = Column(Text, nullable=False)  # JSON array of path node objects
    explanation = Column(Text, nullable=True)
    warmth_score = Column(Integer, default=0, nullable=False)
    confidence_score = Column(Integer, default=0, nullable=False)
    recommended_intro_person = Column(String, nullable=True)
    recommended_channel = Column(String, nullable=True)
    status = Column(String, default="active", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="warm_paths")
    account = relationship("BizAccount", back_populates="warm_paths")
    contact = relationship("Contact", back_populates="warm_paths")
    messages = relationship("Message", back_populates="warm_path")


# ─── Signal ───────────────────────────────────────────────────────────────────


class Signal(Base):
    __tablename__ = "signals"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("biz_accounts.id"), nullable=True, index=True)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    urgency_score = Column(Integer, default=50, nullable=False)
    confidence_score = Column(Integer, default=70, nullable=False)
    detected_at = Column(DateTime, default=utcnow, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="signals")
    account = relationship("BizAccount", back_populates="signals")
    contact = relationship("Contact", back_populates="signals")
    messages = relationship("Message", back_populates="signal")


# ─── Campaign ─────────────────────────────────────────────────────────────────


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # e.g. "outbound", "nurture"
    goal = Column(Text, nullable=True)
    status = Column(String, default="draft", nullable=False)
    target_segment = Column(Text, nullable=True)
    channels_json = Column(Text, nullable=True)  # JSON array of channel strings
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="campaigns")
    owner = relationship("User", back_populates="campaigns", foreign_keys=[owner_id])
    assets = relationship("CampaignAsset", back_populates="campaign")
    steps = relationship("CampaignStep", back_populates="campaign", order_by="CampaignStep.step_number")
    messages = relationship("Message", back_populates="campaign")
    tasks = relationship("Task", back_populates="campaign")


# ─── CampaignStep ─────────────────────────────────────────────────────────────


class CampaignStep(Base):
    __tablename__ = "campaign_steps"

    id = Column(String, primary_key=True, default=new_id)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    channel = Column(String, nullable=False)  # email, linkedin, phone, etc.
    action_type = Column(String, nullable=False)  # send_message, call, connect_request
    delay_days = Column(Integer, default=0, nullable=False)
    asset_type = Column(String, nullable=True)
    approval_required = Column(Boolean, default=True, nullable=False)

    # Relationships
    campaign = relationship("Campaign", back_populates="steps")


# ─── CampaignAsset ────────────────────────────────────────────────────────────


class CampaignAsset(Base):
    __tablename__ = "campaign_assets"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True)
    account_id = Column(String, ForeignKey("biz_accounts.id"), nullable=True)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=True)
    channel = Column(String, nullable=False)
    type = Column(String, nullable=False)  # email_body, linkedin_message, call_script, etc.
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    subject = Column(String, nullable=True)
    headline = Column(String, nullable=True)
    preview = Column(String, nullable=True)
    approval_status = Column(String, default="draft", nullable=False)
    launch_status = Column(String, default="pending", nullable=False)
    quality_score = Column(Integer, default=0, nullable=False)
    confidence_score = Column(Integer, default=0, nullable=False)
    generated_by_ai = Column(Boolean, default=True, nullable=False)
    extra_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="campaign_assets")
    campaign = relationship("Campaign", back_populates="assets")
    account = relationship("BizAccount", back_populates="campaign_assets")
    contact = relationship("Contact", back_populates="campaign_assets")
    approvals = relationship("Approval", back_populates="asset")


# ─── Message ──────────────────────────────────────────────────────────────────


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True)
    account_id = Column(String, ForeignKey("biz_accounts.id"), nullable=True)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=True)
    warm_path_id = Column(String, ForeignKey("warm_paths.id"), nullable=True)
    signal_id = Column(String, ForeignKey("signals.id"), nullable=True)
    channel = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    status = Column(String, default="draft", nullable=False)
    approval_status = Column(String, default="pending", nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    generated_by_ai = Column(Boolean, default=True, nullable=False)
    confidence_score = Column(Integer, default=0, nullable=False)
    personalization_reason = Column(Text, nullable=True)
    intro_request = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="messages")
    campaign = relationship("Campaign", back_populates="messages")
    account = relationship("BizAccount", back_populates="messages")
    contact = relationship("Contact", back_populates="messages")
    warm_path = relationship("WarmPath", back_populates="messages")
    signal = relationship("Signal", back_populates="messages")
    approvals = relationship("Approval", back_populates="message")


# ─── Approval ─────────────────────────────────────────────────────────────────


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    asset_id = Column(String, ForeignKey("campaign_assets.id"), nullable=True)
    message_id = Column(String, ForeignKey("messages.id"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending", nullable=False)
    edited_body = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="approvals")
    asset = relationship("CampaignAsset", back_populates="approvals")
    message = relationship("Message", back_populates="approvals")
    user = relationship("User", back_populates="approvals", foreign_keys=[user_id])


# ─── KnowledgeBaseItem ────────────────────────────────────────────────────────


class KnowledgeBaseItem(Base):
    __tablename__ = "knowledge_base_items"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    type = Column(String, nullable=False)  # one_pager, case_study, pricing, faq, etc.
    content = Column(Text, nullable=False)
    source = Column(String, nullable=True)
    tags_json = Column(Text, nullable=True)  # JSON array of tag strings
    confidence_score = Column(Integer, default=80, nullable=False)
    approved_for_ai = Column(Boolean, default=True, nullable=False)
    used_in_messages = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="kb_items")


# ─── IntegrationConnection ────────────────────────────────────────────────────


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (UniqueConstraint("workspace_id", "provider", name="uq_workspace_provider"),)

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    provider = Column(String, nullable=False)  # gmail, linkedin, slack, hubspot, etc.
    channel = Column(String, nullable=True)  # email, social, crm, etc.
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="disconnected", nullable=False)
    auth_type = Column(String, nullable=True)  # oauth2, api_key, etc.
    capabilities_json = Column(Text, nullable=True)  # JSON array of capability strings
    icon_color = Column(String, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    sync_status = Column(String, nullable=True)
    demo_mode = Column(Boolean, default=False, nullable=False)
    health_score = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="integrations")


# ─── AIUsageLog ───────────────────────────────────────────────────────────────


class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action_type = Column(String, nullable=False)  # generate_message, enrich_contact, etc.
    provider = Column(String, nullable=True)  # anthropic, openai, etc.
    mode = Column(String, nullable=True)  # mock, local, remote
    model = Column(String, nullable=True)
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    estimated_cost = Column(Float, default=0.0, nullable=False)
    status = Column(String, default="success", nullable=False)
    cache_hit = Column(Boolean, default=False, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="ai_usage_logs")
    user = relationship("User", back_populates="ai_usage_logs", foreign_keys=[user_id])


# ─── AuditLog ─────────────────────────────────────────────────────────────────


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    actor_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    actor_name = Column(String, nullable=False)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    entity_name = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON object of extra context
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="audit_logs")
    actor = relationship("User", back_populates="audit_logs", foreign_keys=[actor_user_id])


# ─── Task ─────────────────────────────────────────────────────────────────────


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=new_id)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    account_id = Column(String, ForeignKey("biz_accounts.id"), nullable=True)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True)
    type = Column(String, nullable=False)  # call, email, linkedin, review, etc.
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String, default="medium", nullable=False)
    status = Column(String, default="pending", nullable=False)
    due_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="tasks")
    owner = relationship("User", back_populates="tasks", foreign_keys=[owner_id])
    account = relationship("BizAccount", back_populates="tasks")
    contact = relationship("Contact", back_populates="tasks")
    campaign = relationship("Campaign", back_populates="tasks")
