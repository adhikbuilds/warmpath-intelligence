"""
Workspace context extractor for data endpoints.

Reads X-User-Id from the request header, looks up the user's workspace
membership, and returns a dict with user_id, workspace_id, and user_name.
Raises 401 if the header is missing or the user is not in any workspace.
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models.all_models import User, WorkspaceMember


def get_workspace_context(request: Request, db: Session = Depends(get_db)) -> dict:
    """
    Extract workspace context from X-User-Id header.
    FastAPI injects db via Depends(get_db) and request automatically.
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")

    member = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user_id).first()
    if not member:
        raise HTTPException(status_code=401, detail="User not in any workspace")

    user = db.get(User, user_id)

    return {
        "user_id": user_id,
        "workspace_id": member.workspace_id,
        "user_name": user.name if user else "Unknown",
    }
