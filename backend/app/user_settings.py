"""
Per-user settings stored directly on Google Drive.
No local files — reads/writes go directly to Drive with in-memory cache.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "page_refresh_interval": 600,  # 10 min default
}

_SETTINGS_FILE = "user_settings.json"


def get_settings(user_id: str, email: str) -> dict:
    """Load user settings from Google Drive, returning defaults for missing keys."""
    from . import drive_settings
    settings = dict(_DEFAULTS)
    saved = drive_settings.read_json(email, user_id, _SETTINGS_FILE, default={})
    if isinstance(saved, dict):
        settings.update(saved)
    return settings


def save_settings(user_id: str, email: str, updates: dict) -> dict:
    """Merge updates into user settings and save directly to Google Drive."""
    settings = get_settings(user_id, email)
    settings.update(updates)
    settings["updated_at"] = datetime.now().isoformat(timespec="seconds")

    from . import drive_settings
    drive_settings.write_json(email, user_id, _SETTINGS_FILE, settings)
    logger.info(f"[UserSettings] Saved settings for {user_id}: {list(updates.keys())}")
    return settings
