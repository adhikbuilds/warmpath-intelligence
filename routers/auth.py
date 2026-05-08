"""
Auth endpoints used by the Next.js Credentials provider.
POST /auth/login    verify email/password, return user info
POST /auth/register create user + workspace, return user info
GET  /auth/me       return user info from X-User-Id header
"""

import uuid
from datetime import datetime, timezone

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.all_models import User, Workspace, WorkspaceMember

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    id: str
    email: str
    password: str
    name: str | None = None
    company_name: str | None = None
    workspace_id: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    role: str

    model_config = {"from_attributes": True}


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.password or not _bcrypt.checkpw(body.password.encode(), user.password.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    now = datetime.now(timezone.utc)
    hashed = _bcrypt.hashpw(body.password.encode(), _bcrypt.gensalt()).decode()

    user = User(
        id=body.id,
        email=body.email,
        name=body.name,
        password=hashed,
        role="owner",
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()

    ws_id = body.workspace_id or f"ws-{body.id}"
    workspace = Workspace(
        id=ws_id,
        name=body.company_name or (body.name or body.email.split("@")[0]),
        owner_id=body.id,
        plan="growth",
        onboarding_stage="onboarding",
        health_score=50,
        created_at=now,
        updated_at=now,
    )
    db.add(workspace)
    db.flush()

    member = WorkspaceMember(
        id=f"wm-{body.id}",
        workspace_id=ws_id,
        user_id=body.id,
        role="owner",
        relationship_score=50,
        joined_at=now,
    )
    db.add(member)
    db.commit()

    return user


@router.get("/me")
def me(user_id: str, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)
