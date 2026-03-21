"""
Notification channels: Email (Gmail SMTP) and Telegram Bot API.

Email uses Gmail SMTP with an App Password (not OAuth).
Telegram uses the Bot API HTTP endpoint.
Per-user notification email preferences stored in backend/data/notification_prefs.json.
"""
import os
import json
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
from typing import List
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
logger = logging.getLogger(__name__)

# Config — SMTP sender credentials (global, from .env)
_EMAIL_ADDRESS = os.getenv("NOTIFICATION_EMAIL", "").strip()
_EMAIL_APP_PASSWORD = os.getenv("NOTIFICATION_EMAIL_APP_PASSWORD", "").strip()
_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Per-user notification preferences
from .config import DUMPS_BASE

# Legacy shared file (for migration)
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LEGACY_PREFS_FILE = _DATA_DIR / "notification_prefs.json"


# ── Per-user notification preferences ────────────────────
# Stored at: dumps/{email}/settings/notification_prefs.json

def _prefs_file(user_email: str) -> Path:
    d = DUMPS_BASE / user_email / "settings"
    d.mkdir(parents=True, exist_ok=True)
    return d / "notification_prefs.json"


def _sync_prefs_to_drive(user_email: str):
    try:
        from app import drive_service
        rel_path = f"{user_email}/settings/notification_prefs.json"
        drive_service.sync_dumps_file(rel_path, email=user_email)
    except Exception:
        pass


def _migrate_legacy_prefs(user_email: str) -> dict:
    """Migrate prefs from legacy shared file to per-user file."""
    if not _LEGACY_PREFS_FILE.exists():
        return {"emails": [], "updated_at": ""}
    try:
        with open(_LEGACY_PREFS_FILE) as f:
            all_prefs = json.load(f)
        user_prefs = all_prefs.get(user_email, {})
        if user_prefs:
            # Save to new location
            fp = _prefs_file(user_email)
            with open(fp, "w") as f:
                json.dump(user_prefs, f, indent=2)
            _sync_prefs_to_drive(user_email)
            # Remove from legacy
            del all_prefs[user_email]
            if all_prefs:
                with open(_LEGACY_PREFS_FILE, "w") as f:
                    json.dump(all_prefs, f, indent=2)
            else:
                _LEGACY_PREFS_FILE.unlink(missing_ok=True)
            logger.info(f"[Notify] Migrated notification prefs for {user_email} to per-user file")
        return user_prefs or {"emails": [], "updated_at": ""}
    except Exception as e:
        logger.error(f"[Notify] Legacy prefs migration failed: {e}")
        return {"emails": [], "updated_at": ""}


def get_user_prefs(user_email: str) -> dict:
    """Get notification preferences for a user (by login email)."""
    fp = _prefs_file(user_email)
    try:
        with open(fp) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return _migrate_legacy_prefs(user_email)


def save_user_prefs(user_email: str, emails: List[str]) -> dict:
    """Save notification email addresses for a user. Returns saved prefs."""
    clean_emails = []
    seen = set()
    for e in emails:
        e = e.strip().lower()
        if e and "@" in e and e not in seen:
            clean_emails.append(e)
            seen.add(e)

    prefs = {
        "emails": clean_emails,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    fp = _prefs_file(user_email)
    with open(fp, "w") as f:
        json.dump(prefs, f, indent=2)
    _sync_prefs_to_drive(user_email)
    logger.info(f"[Notify] Saved {len(clean_emails)} notification email(s) for {user_email}")
    return prefs


def get_user_notification_emails(user_email: str) -> List[str]:
    """Get notification recipient emails for a user.
    Falls back to the SMTP sender email if no per-user emails configured."""
    user_prefs = get_user_prefs(user_email)
    emails = user_prefs.get("emails", [])
    if emails:
        return emails
    # Fallback: send to the SMTP sender address
    return [_EMAIL_ADDRESS] if _EMAIL_ADDRESS else []


# ── Channel status ───────────────────────────────────────

def email_configured() -> bool:
    return bool(_EMAIL_ADDRESS and _EMAIL_APP_PASSWORD)


def telegram_configured() -> bool:
    return bool(_TELEGRAM_BOT_TOKEN and _TELEGRAM_CHAT_ID)


def get_channel_status() -> dict:
    return {
        "email": {
            "configured": email_configured(),
            "address": (_EMAIL_ADDRESS[:3] + "***" + _EMAIL_ADDRESS[_EMAIL_ADDRESS.index("@"):]) if email_configured() else "",
        },
        "telegram": {
            "configured": telegram_configured(),
            "chat_id": (_TELEGRAM_CHAT_ID[:3] + "***") if telegram_configured() else "",
        },
    }


# ── Send functions ───────────────────────────────────────

def send_email(subject: str, body: str, html_body: str = None, recipients: List[str] = None) -> bool:
    """Send email via Gmail SMTP to specified recipients (or self).
    Returns True on success."""
    if not email_configured():
        logger.warning("[Notify] Email not configured — skipping")
        return False

    to_addrs = recipients or [_EMAIL_ADDRESS]
    if not to_addrs:
        logger.warning("[Notify] No recipient emails — skipping")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = _EMAIL_ADDRESS
        msg["To"] = ", ".join(to_addrs)
        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(_EMAIL_ADDRESS, _EMAIL_APP_PASSWORD)
            server.sendmail(_EMAIL_ADDRESS, to_addrs, msg.as_string())
        logger.info(f"[Notify] Email sent to {len(to_addrs)} recipient(s): {subject}")
        return True
    except Exception as e:
        logger.error(f"[Notify] Email failed: {e}")
        return False


def send_telegram(message: str) -> bool:
    """Send message via Telegram Bot API. Returns True on success."""
    if not telegram_configured():
        logger.warning("[Notify] Telegram not configured — skipping")
        return False
    try:
        url = f"https://api.telegram.org/bot{_TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": _TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        if resp.status_code == 200:
            logger.info("[Notify] Telegram message sent")
            return True
        else:
            logger.error(f"[Notify] Telegram API error: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"[Notify] Telegram failed: {e}")
        return False


def notify(channel: str, subject: str, message: str, html_body: str = None,
           user_email: str = None) -> bool:
    """Send notification via specified channel ('email', 'telegram', 'all').
    If user_email provided, sends to that user's configured email addresses.
    Returns True if at least one channel succeeded."""
    results = []
    if channel in ("email", "all"):
        recipients = get_user_notification_emails(user_email) if user_email else None
        results.append(send_email(subject, message, html_body, recipients=recipients))
    if channel in ("telegram", "all"):
        full_msg = f"<b>{subject}</b>\n\n{message}" if subject else message
        results.append(send_telegram(full_msg))
    return any(results)
