"""
Google SSO authentication module.

When AUTH_MODE=google, all API requests (except /api/auth/*) require a valid
session JWT in the Authorization header. Google login verifies the ID token
and checks the email against ALLOWED_EMAILS.

Supports OAuth 2.0 authorization code flow for Google Drive access.

When AUTH_MODE=local (default), no authentication is required.
"""
import os
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
import time
import json
import jwt
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Config ─────────────────────────────────────────────
AUTH_MODE = os.getenv("AUTH_MODE", "local").strip().lower()  # "local" or "google"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "postmessage")
# Comma-separated list of allowed Google emails
ALLOWED_EMAILS = [
    e.strip().lower()
    for e in os.getenv("ALLOWED_EMAILS", "").split(",")
    if e.strip()
]
# JWT secret for session tokens (persisted to file so sessions survive restarts)
_JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
if not _JWT_SECRET:
    _JWT_SECRET_FILE = Path(__file__).resolve().parent.parent / "data" / ".jwt_secret"
    if _JWT_SECRET_FILE.exists():
        _JWT_SECRET = _JWT_SECRET_FILE.read_text().strip()
    if not _JWT_SECRET:
        import secrets
        _JWT_SECRET = secrets.token_hex(32)
        _JWT_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        _JWT_SECRET_FILE.write_text(_JWT_SECRET)

JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "168"))  # 7 days default

# Drive OAuth scopes
DRIVE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive",
]

# Token storage — prefer dumps/{email}/settings/ (persists with Docker volume)
# Falls back to data/google_tokens.json for legacy/migration
_LEGACY_TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "google_tokens.json"


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
            logger.warning(f"[Auth] Rejected login from {email} — not in ALLOWED_EMAILS")
            return None
        return {
            "email": email,
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", ""),
        }
    except Exception as e:
        logger.error(f"[Auth] Google token verification failed: {e}")
        return None


def exchange_auth_code(auth_code: str) -> dict:
    """Exchange authorization code for access + refresh tokens.
    Returns {email, name, picture, access_token, refresh_token}."""
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=DRIVE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )
    flow.fetch_token(code=auth_code)
    creds = flow.credentials

    # Get user info from ID token
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    idinfo = id_token.verify_oauth2_token(
        creds.id_token, google_requests.Request(), GOOGLE_CLIENT_ID
    )
    email = idinfo.get("email", "").lower()

    # Check allowed emails
    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        raise ValueError(f"Email {email} not in allowed list")

    # Store refresh token (per-email)
    _save_tokens(email, {
        "refresh_token": creds.refresh_token,
        "access_token": creds.token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
    })

    return {
        "email": email,
        "name": idinfo.get("name", ""),
        "picture": idinfo.get("picture", ""),
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
    }


def get_drive_credentials(email: str = ""):
    """Get valid Drive API credentials for an email, refreshing if needed."""
    from google.oauth2.credentials import Credentials
    tokens = _load_tokens(email)
    if not tokens or not tokens.get("refresh_token"):
        return None
    creds = Credentials(
        token=tokens.get("access_token"),
        refresh_token=tokens["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=tokens.get("client_id", GOOGLE_CLIENT_ID),
        client_secret=tokens.get("client_secret", GOOGLE_CLIENT_SECRET),
        scopes=DRIVE_SCOPES,
    )
    if creds.expired or not creds.valid:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        tokens["access_token"] = creds.token
        _save_tokens(email, tokens)
    return creds


def get_any_drive_credentials():
    """Return credentials for any stored email (fallback for non-email-scoped calls)."""
    all_tokens = _load_all_tokens()
    for email in all_tokens:
        creds = get_drive_credentials(email)
        if creds:
            return creds, email
    return None, None


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


def _token_file_for_email(email: str) -> Path:
    """Get token file path in dumps/{email}/settings/google_tokens.json (email-scoped)."""
    from .config import DUMPS_BASE
    if email:
        d = DUMPS_BASE / email / "settings"
        d.mkdir(parents=True, exist_ok=True)
        return d / "google_tokens.json"
    return _LEGACY_TOKEN_FILE


def _load_all_tokens() -> dict:
    """Load tokens from per-email dumps paths + legacy file."""
    result = {}
    # Load from per-email dumps paths: dumps/{email}/settings/google_tokens.json
    from .config import DUMPS_BASE
    if DUMPS_BASE.exists():
        for email_dir in DUMPS_BASE.iterdir():
            if email_dir.is_dir() and "@" in email_dir.name:
                tf = email_dir / "settings" / "google_tokens.json"
                if tf.exists():
                    try:
                        data = json.loads(tf.read_text())
                        if isinstance(data, dict) and data.get("refresh_token"):
                            result[email_dir.name] = data
                    except Exception:
                        pass
    # Migrate from legacy file
    if _LEGACY_TOKEN_FILE.exists():
        try:
            legacy = json.loads(_LEGACY_TOKEN_FILE.read_text())
            for email, tokens in legacy.items():
                if email and "@" in email and email not in result:
                    # Migrate to per-email path
                    _save_tokens(email, tokens)
                    result[email] = tokens
                elif not email and tokens.get("refresh_token") and not result:
                    result[""] = tokens
            # Remove legacy file after migration
            if all("@" in k for k in legacy if k):
                _LEGACY_TOKEN_FILE.unlink(missing_ok=True)
                logger.info("[Auth] Migrated tokens from legacy file to per-email dumps paths")
        except Exception:
            pass
    return result


def _save_tokens(email: str, tokens: dict):
    """Persist tokens for one email in dumps/{email}/settings/."""
    fp = _token_file_for_email(email)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(tokens, indent=2))
    # Also keep legacy file as backup
    try:
        all_legacy = {}
        if _LEGACY_TOKEN_FILE.exists():
            all_legacy = json.loads(_LEGACY_TOKEN_FILE.read_text())
        all_legacy[email] = tokens
        _LEGACY_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LEGACY_TOKEN_FILE.write_text(json.dumps(all_legacy, indent=2))
    except Exception:
        pass


def _load_tokens(email: str = "") -> dict | None:
    """Load tokens for a specific email."""
    if email:
        fp = _token_file_for_email(email)
        if fp.exists():
            try:
                data = json.loads(fp.read_text())
                if data.get("refresh_token"):
                    return data
            except Exception:
                pass
    # Fallback to all tokens
    all_tokens = _load_all_tokens()
    if email:
        return all_tokens.get(email)
    for v in all_tokens.values():
        return v
    return None


def get_drive_folder_id(email: str) -> str:
    """Get the stored Drive dumps folder ID for an email."""
    tokens = _load_tokens(email)
    if tokens:
        return tokens.get("drive_folder_id", "")
    return ""


def set_drive_folder_id(email: str, folder_id: str):
    """Store the Drive dumps folder ID for an email."""
    tokens = _load_tokens(email) or {}
    tokens["drive_folder_id"] = folder_id
    _save_tokens(email, tokens)
