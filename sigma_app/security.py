from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

AUTH_SECRET = os.getenv("SIGMA_AUTH_SECRET", "")
if not AUTH_SECRET:
    # Development fallback only. Production must set a long random secret.
    AUTH_SECRET = "development-only-change-this-before-deploying"

serializer = URLSafeTimedSerializer(AUTH_SECRET, salt="sigma-ai-auth-v1")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 310_000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def new_verification_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_access_token(user_id: int) -> str:
    return serializer.dumps({"uid": user_id})


def read_access_token(token: str) -> int | None:
    try:
        data = serializer.loads(token, max_age=60 * 60 * 24 * 30)
        return int(data["uid"])
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None
