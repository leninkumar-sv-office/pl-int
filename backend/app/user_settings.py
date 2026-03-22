"""
Per-user settings stored in dumps/{email}/{Name}/settings/user_settings.json.
Files live on Google Drive mount — changes auto-sync via Google Drive desktop.
"""
import json
import logging
from pathlib import Path
from datetime import datetime

from .config import get_user_dumps_dir

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "page_refresh_interval": 600,  # 10 min default
}


def _settings_file(user_id: str, email: str) -> Path:
    dumps_dir = get_user_dumps_dir(user_id, email)
    d = dumps_dir / "settings"
    d.mkdir(parents=True, exist_ok=True)
    return d / "user_settings.json"


def get_settings(user_id: str, email: str) -> dict:
    """Load user settings, returning defaults for missing keys."""
    fp = _settings_file(user_id, email)
    settings = dict(_DEFAULTS)
    try:
        with open(fp) as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            settings.update(saved)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return settings


def save_settings(user_id: str, email: str, updates: dict) -> dict:
    """Merge updates into user settings and save."""
    settings = get_settings(user_id, email)
    settings.update(updates)
    settings["updated_at"] = datetime.now().isoformat(timespec="seconds")

    fp = _settings_file(user_id, email)
    with open(fp, "w") as f:
        json.dump(settings, f, indent=2)

    logger.info(f"[UserSettings] Saved settings for {user_id}: {list(updates.keys())}")
    return settings
