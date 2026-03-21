"""
Per-user settings stored in dumps/{email}/{Name}/settings/user_settings.json.
Synced to Google Drive on every change.
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import DUMPS_BASE, get_user_dumps_dir

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "page_refresh_interval": 600,  # 10 min default
}


def _settings_file(user_id: str, email: str) -> Path:
    dumps_dir = get_user_dumps_dir(user_id, email)
    d = dumps_dir / "settings"
    d.mkdir(parents=True, exist_ok=True)
    return d / "user_settings.json"


def _sync_to_drive(user_id: str, email: str):
    """Synchronous Drive upload — no background thread."""
    try:
        from app import drive_service
        dumps_dir = get_user_dumps_dir(user_id, email)
        rel_path = str(dumps_dir.relative_to(DUMPS_BASE) / "settings" / "user_settings.json")
        # Use direct upload instead of threaded sync_dumps_file
        local_path = Path(DUMPS_BASE) / rel_path
        if local_path.exists():
            parts = Path(rel_path).parts
            subfolder = "dumps/" + "/".join(parts[:-1])
            drive_service.upload_file(local_path, subfolder=subfolder, email=email)
    except Exception as e:
        logger.error(f"[UserSettings] Drive sync failed: {e}")


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
    """Merge updates into user settings, save, and sync to Drive."""
    settings = get_settings(user_id, email)
    settings.update(updates)
    settings["updated_at"] = datetime.now().isoformat(timespec="seconds")

    fp = _settings_file(user_id, email)
    with open(fp, "w") as f:
        json.dump(settings, f, indent=2)

    _sync_to_drive(user_id, email)
    logger.info(f"[UserSettings] Saved settings for {user_id}: {list(updates.keys())}")
    return settings
