"""
Google SSO authentication module.

When AUTH_MODE=google, all API requests (except /api/auth/*) require a valid
session JWT in the Authorization header. Google login verifies the ID token
and checks the email against ALLOWED_EMAILS.

When AUTH_MODE=local (default), no authentication is required.
"""
import os
import time
import jwt
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Config ─────────────────────────────────────────────
AUTH_MODE = os.getenv("AUTH_MODE", "local").strip().lower()  # "local" or "google"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
# Comma-separated list of allowed Google emails
ALLOWED_EMAILS = [
    e.strip().lower()
    for e in os.getenv("ALLOWED_EMAILS", "").split(",")
    if e.strip()
]
# JWT secret for session tokens (auto-generated if not set)
_JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
if not _JWT_SECRET:
    import secrets
    _JWT_SECRET = secrets.token_hex(32)

JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "168"))  # 7 days default


def is_auth_enabled() -> bool:
    return AUTH_MODE == "google" and bool(GOOGLE_CLIENT_ID)


def verify_google_token(id_token_str: str) -> Optional[dict]:
    """Verify a Google ID token and return user info.
    Returns {email, name, picture} or None on failure."""
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        email = idinfo.get("email", "").lower()
        if not email:
            return None
        # Check allowed emails (if configured)
        if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
            print(f"[Auth] Rejected login from {email} — not in ALLOWED_EMAILS")
            return None
        return {
            "email": email,
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", ""),
        }
    except Exception as e:
        print(f"[Auth] Google token verification failed: {e}")
        return None


def create_session_token(email: str, name: str) -> str:
    """Create a JWT session token."""
    payload = {
        "email": email,
        "name": name,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def verify_session_token(token: str) -> Optional[dict]:
    """Verify a session JWT. Returns {email, name} or None."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
        return {"email": payload["email"], "name": payload["name"]}
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
