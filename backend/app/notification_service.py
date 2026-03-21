"""
Notification channels: Email (Gmail SMTP) and Telegram Bot API.

Email uses Gmail SMTP with an App Password (not OAuth).
Telegram uses the Bot API HTTP endpoint.
"""
import os
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
logger = logging.getLogger(__name__)

# Config
_EMAIL_ADDRESS = os.getenv("NOTIFICATION_EMAIL", "").strip()
_EMAIL_APP_PASSWORD = os.getenv("NOTIFICATION_EMAIL_APP_PASSWORD", "").strip()
_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


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


def send_email(subject: str, body: str, html_body: str = None) -> bool:
    """Send email via Gmail SMTP. Returns True on success."""
    if not email_configured():
        logger.warning("[Notify] Email not configured — skipping")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = _EMAIL_ADDRESS
        msg["To"] = _EMAIL_ADDRESS
        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(_EMAIL_ADDRESS, _EMAIL_APP_PASSWORD)
            server.send_message(msg)
        logger.info(f"[Notify] Email sent: {subject}")
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


def notify(channel: str, subject: str, message: str, html_body: str = None) -> bool:
    """Send notification via specified channel ('email', 'telegram', 'all').
    Returns True if at least one channel succeeded."""
    results = []
    if channel in ("email", "all"):
        results.append(send_email(subject, message, html_body))
    if channel in ("telegram", "all"):
        full_msg = f"<b>{subject}</b>\n\n{message}" if subject else message
        results.append(send_telegram(full_msg))
    return any(results)
