from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .api_key_models import APIKey
from .security import read_access_token
from .ai_engine import generate_text

router = APIRouter()


def _role_for(email: str) -> str:
    normalized = email.lower().strip()
    owner = os.getenv("SIGMA_OWNER_EMAIL", "").lower().strip()
    admins = {x.strip().lower() for x in os.getenv("SIGMA_ADMIN_EMAILS", "").split(",") if x.strip()}
    if owner and secrets.compare_digest(normalized, owner):
        return "Owner"
    if normalized in admins:
        return "Admin"
    return "User"


def _current_user(request: Request, db: Session) -> User:
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else request.session.get("access_token")
    user_id = read_access_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Please log in to Sigma Developers.")
    user = db.get(User, user_id)
    if not user or not user.email_verified:
        raise HTTPException(status_code=403, detail="A verified account is required.")
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    return _current_user(request, db)


class CreateKeyInput(BaseModel):
    name: str = Field(default="My API key", min_length=1, max_length=80)


class APIMessage(BaseModel):
    role: str = Field(min_length=1, max_length=20)
    content: str = Field(max_length=12000)


class CompletionInput(BaseModel):
    model: str = "sigma-0.1b"
    messages: list[APIMessage] = Field(min_length=1, max_length=40)
    max_tokens: int = Field(default=240, ge=1, le=512)


@router.get("/developers")
def developers_page():
    return FileResponse(Path(__file__).parent / "developers.html")


@router.get("/api/developer/profile")
def developer_profile(user: User = Depends(require_user)):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": _role_for(user.email),
        "email_verified": user.email_verified,
        "model_ready": Path(os.getenv("SIGMA_MODEL_CHECKPOINT", "artifacts/sigma-0.1b.pt")).is_file(),
    }


@router.get("/api/developer/keys")
def list_api_keys(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(APIKey).where(APIKey.user_id == user.id, APIKey.revoked_at.is_(None)).order_by(APIKey.created_at.desc())).all()
    return [{
        "id": row.id,
        "name": row.name,
        "prefix": row.key_prefix,
        "created_at": row.created_at.isoformat(),
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "request_count": row.request_count,
    } for row in rows]


@router.post("/api/developer/keys", status_code=201)
def create_api_key(data: CreateKeyInput, user: User = Depends(require_user), db: Session = Depends(get_db)):
    # 256-bit random secret. Only its SHA-256 digest is stored in the database.
    raw_key = "sigma_sk_live_" + secrets.token_urlsafe(32)
    row = APIKey(
        user_id=user.id,
        name=data.name.strip() or "My API key",
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        key_prefix=raw_key[:20],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "api_key": raw_key, "warning": "Copy this key now. It cannot be displayed again."}


@router.delete("/api/developer/keys/{key_id}")
def revoke_api_key(key_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    row = db.scalar(select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id, APIKey.revoked_at.is_(None)))
    if not row:
        raise HTTPException(status_code=404, detail="API key not found.")
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


def _api_key_user(request: Request, db: Session) -> tuple[User, APIKey]:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Send your Sigma API key as a Bearer token.")
    raw_key = header[7:].strip()
    digest = hashlib.sha256(raw_key.encode()).hexdigest()
    row = db.scalar(select(APIKey).where(APIKey.key_hash == digest, APIKey.revoked_at.is_(None)))
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or revoked Sigma API key.")
    user = db.get(User, row.user_id)
    if not user or not user.email_verified:
        raise HTTPException(status_code=403, detail="Verified account required.")
    return user, row


@router.post("/v1/chat/completions")
def chat_completions(data: CompletionInput, request: Request, db: Session = Depends(get_db)):
    user, key = _api_key_user(request, db)
    if data.model not in ("sigma-0.1b", "Sigma-0.1B"):
        raise HTTPException(status_code=404, detail="Unknown Sigma model.")
    messages = [item.model_dump() for item in data.messages]
    try:
        answer = generate_text(messages, system_prompt="You are Sigma AI. Be helpful, accurate, respectful, and text-only.", max_new_tokens=data.max_tokens)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    key.request_count += 1
    key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(datetime.now(timezone.utc).timestamp()),
        "model": "sigma-0.1b",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
    }


@router.get("/api/admin/overview")
def admin_overview(user: User = Depends(require_user), db: Session = Depends(get_db)):
    role = _role_for(user.email)
    if role not in ("Admin", "Owner"):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    users = db.scalar(select(func.count()).select_from(User)) or 0
    keys = db.scalar(select(func.count()).select_from(APIKey).where(APIKey.revoked_at.is_(None))) or 0
    return {"role": role, "users": users, "active_api_keys": keys}
