"""Standalone Sigma AI web application entry point."""
from __future__ import annotations

import os
import json
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Generator
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from sigma_app.database import Base, engine, get_db
from sigma_app.emailer import send_verification_email
from sigma_app.models import User, EmailVerification, Conversation, Message, Memory
from sigma_app.developer_routes import router as developers_router
from sigma_app.ai_engine import generate_text
from sigma_app.security import (
    create_access_token, hash_password, verify_password,
    new_verification_token, hash_token, read_access_token,
)

APP_URL = os.getenv("SIGMA_APP_URL", "http://localhost:8000").rstrip("/")
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sigma AI", version="0.1.0")
app.include_router(developers_router)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SIGMA_AUTH_SECRET", "development-only-change-this-before-deploying"), same_site="lax", https_only=os.getenv("COOKIE_HTTPS_ONLY", "true").lower() == "true")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("SIGMA_ALLOWED_ORIGINS", "").split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


class RegisterInput(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=20)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=20)


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=12000)


class RenameInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


def current_user(request: Request, db: Session) -> User:
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else request.session.get("access_token")
    user_id = read_access_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Please log in.")
    user = db.get(User, user_id)
    if not user or not user.email_verified:
        raise HTTPException(status_code=401, detail="Account unavailable or email not verified.")
    return user


def get_user(request: Request, db: Session = Depends(get_db)) -> User:
    return current_user(request, db)


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(Path(__file__).parent / "sigma_app" / "index.html")


@app.get("/health")
def health():
    return {"ok": True, "app": "Sigma AI"}


@app.post("/api/auth/register", status_code=201)
def register(data: RegisterInput, db: Session = Depends(get_db)):
    email = str(data.email).lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=email, username=data.username.strip(), password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    raw_token, token_digest = new_verification_token()
    db.add(EmailVerification(
        user_id=user.id,
        token_hash=token_digest,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    ))
    db.commit()
    verify_url = f"{APP_URL}/api/auth/verify?token={raw_token}"
    try:
        send_verification_email(email, user.username, verify_url)
    except Exception as exc:
        db.query(EmailVerification).filter(EmailVerification.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.commit()
        raise HTTPException(status_code=503, detail="Could not send verification email. Email delivery is not configured.") from exc
    return {"message": "Verification email sent. Open the button in the email to activate your account."}


@app.get("/api/auth/verify")
def verify_email(token: str, db: Session = Depends(get_db)):
    record = db.scalar(select(EmailVerification).where(EmailVerification.token_hash == hash_token(token), EmailVerification.used.is_(False)))
    now = datetime.now(timezone.utc)
    if not record or record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=400, detail="This verification link is invalid or expired. Request a new one.")
    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Account not found.")
    record.used = True
    user.email_verified = True
    db.commit()
    return RedirectResponse(url=f"{APP_URL}/?verified=1", status_code=303)


@app.post("/api/auth/login")
def login(data: LoginInput, request: Request, db: Session = Depends(get_db)):
    email = str(data.email).lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first.")
    access = create_access_token(user.id)
    request.session["access_token"] = access
    return {"access_token": access, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "username": user.username}}


@app.post("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(user: User = Depends(get_user)):
    return {"id": user.id, "email": user.email, "username": user.username, "email_verified": user.email_verified}


@app.get("/api/chats")
def list_chats(user: User = Depends(get_user), db: Session = Depends(get_db)):
    chats = db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())).all()
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at.isoformat()} for c in chats]


@app.post("/api/chats", status_code=201)
def create_chat(user: User = Depends(get_user), db: Session = Depends(get_db)):
    chat = Conversation(user_id=user.id)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return {"id": chat.id, "title": chat.title}


@app.get("/api/chats/{chat_id}/messages")
def chat_messages(chat_id: int, user: User = Depends(get_user), db: Session = Depends(get_db)):
    chat = db.scalar(select(Conversation).where(Conversation.id == chat_id, Conversation.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return [{"id": m.id, "role": m.role, "content": _display_content(m.content), "created_at": m.created_at.isoformat()} for m in chat.messages]


def _model_content(raw: str):
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return value
    except (TypeError, json.JSONDecodeError):
        pass
    return raw


def _display_content(raw: str):
    return _model_content(raw)


def retrieve_older_messages(db: Session, user_id: int, query: str, exclude_ids: set[int]) -> list[str]:
    """Keyword retrieval over up to 2,000 stored messages, including very old turns."""
    terms = {word.lower() for word in re.findall(r"[a-zA-Z0-9_а-яА-ЯёЁ]{3,}", query)}
    if not terms:
        return []
    rows = db.scalars(
        select(Message).join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .order_by(Message.id.desc()).limit(2000)
    ).all()
    scored = []
    for row in rows:
        if row.id in exclude_ids:
            continue
        text_value = row.content
        try:
            parsed = json.loads(text_value)
            if isinstance(parsed, list):
                text_value = " ".join(p.get("text", "") for p in parsed if isinstance(p, dict) and p.get("type") == "text")
        except (TypeError, json.JSONDecodeError):
            pass
        words = {w.lower() for w in re.findall(r"[a-zA-Z0-9_а-яА-ЯёЁ]{3,}", text_value)}
        score = len(terms & words)
        if score:
            title = row.conversation.title if row.conversation else "Previous chat"
            excerpt = re.sub(r"\s+", " ", text_value).strip()[:500]
            scored.append((score, row.id, "[" + title + " · " + row.role + "] " + excerpt))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored[:8]]


def call_model(history: list[dict], memories: list[str], recalled: list[str] | None = None) -> str:
    memory_text = "\\n".join(f"- {item}" for item in memories)
    recalled_text = "\\n".join("- " + item for item in (recalled or []))
    system = (
        "You are Sigma AI, a text-only assistant powered by the original Sigma-0.1B model. "
        "Be respectful, accurate, and concise. Keep the user's chosen response language; "
        "do not switch languages just because code, quotes, or pasted text use another language. "
        "Only change the response language when the user clearly asks you to. "
        "Do not claim knowledge that is not present in the conversation or your training.\\n\\n"
        "Saved user memory:\\n" + (memory_text or "(none)") +
        "\\n\\nRelevant older conversation excerpts:\\n" + (recalled_text or "(none)")
    )
    try:
        return generate_text(history, system_prompt=system)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/chats/{chat_id}/messages")
def send_message(chat_id: int, data: ChatInput, user: User = Depends(get_user), db: Session = Depends(get_db)):
    chat = db.scalar(select(Conversation).where(Conversation.id == chat_id, Conversation.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    message_text = data.message.strip()
    if not message_text:
        raise HTTPException(status_code=422, detail="Write a text message.")
    user_message = Message(conversation_id=chat.id, role="user", content=message_text)
    db.add(user_message)
    db.flush()
    recent_rows = db.scalars(select(Message).where(Message.conversation_id == chat.id).order_by(Message.id.desc()).limit(100)).all()
    history = [{"role": m.role, "content": _display_content(m.content)} for m in reversed(recent_rows)]
    memories = db.scalars(select(Memory).where(Memory.user_id == user.id).order_by(Memory.created_at.desc()).limit(50)).all()
    recalled = retrieve_older_messages(db, user.id, message_text, {m.id for m in recent_rows})
    try:
        answer = call_model(history, [m.content for m in memories], recalled)
    except Exception:
        db.rollback()
        raise
    db.add(Message(conversation_id=chat.id, role="assistant", content=answer))
    if chat.title == "New chat":
        chat.title = message_text[:60]
    chat.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"answer": answer}


@app.patch("/api/chats/{chat_id}")
def rename_chat(chat_id: int, data: RenameInput, user: User = Depends(get_user), db: Session = Depends(get_db)):
    chat = db.scalar(select(Conversation).where(Conversation.id == chat_id, Conversation.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    chat.title = data.title.strip()
    db.commit()
    return {"ok": True}


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: int, user: User = Depends(get_user), db: Session = Depends(get_db)):
    chat = db.scalar(select(Conversation).where(Conversation.id == chat_id, Conversation.user_id == user.id))
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    db.delete(chat)
    db.commit()
    return {"ok": True}


@app.get("/api/memory")
def list_memory(user: User = Depends(get_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Memory).where(Memory.user_id == user.id).order_by(Memory.created_at.desc())).all()
    return [{"id": m.id, "content": m.content, "source": m.source, "created_at": m.created_at.isoformat()} for m in items]


@app.post("/api/memory", status_code=201)
def add_memory(data: MemoryInput, user: User = Depends(get_user), db: Session = Depends(get_db)):
    item = Memory(user_id=user.id, content=data.content.strip(), source="user")
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "content": item.content}


@app.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: int, user: User = Depends(get_user), db: Session = Depends(get_db)):
    item = db.scalar(select(Memory).where(Memory.id == memory_id, Memory.user_id == user.id))
    if not item:
        raise HTTPException(status_code=404, detail="Memory not found.")
    db.delete(item)
    db.commit()
    return {"ok": True}
