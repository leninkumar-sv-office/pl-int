from pathlib import Path
import json
import os

# Base dumps directory (local — synced from/to Google Drive via API)
DUMPS_BASE = Path(os.path.dirname(__file__)).resolve().parent / "dumps"

# Users config file
_USERS_FILE = Path(os.path.dirname(__file__)) / ".." / "data" / "users.json"

# Default users (bootstrap)
_DEFAULT_USERS = [
    {"id": "lenin", "name": "Lenin", "avatar": "L", "color": "#4e7cff"},
]


def get_users() -> list:
    """Load user list from users.json, creating with defaults if missing."""
    if _USERS_FILE.exists():
        try:
            return json.loads(_USERS_FILE.read_text())
        except Exception:
            pass
    # Bootstrap with defaults
    save_users(_DEFAULT_USERS)
    return _DEFAULT_USERS


def save_users(users: list):
    """Persist user list to users.json."""
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(json.dumps(users, indent=2))
    try:
        from . import drive_service
        drive_service.sync_data_file("users.json")
    except Exception:
        pass


def get_user_dumps_dir(user_id: str) -> Path:
    """Get the dumps directory for a specific user.

    Each user's data lives at: dumps/{Name}/
    The folder name is the user's display name (from users.json).
    """
    users = get_users()
    user = next((u for u in users if u["id"] == user_id), None)
    folder_name = user["name"] if user else user_id

    user_dir = DUMPS_BASE / folder_name
    # Create subdirectories if they don't exist
    for sub in ["Stocks", "Mutual Funds", "FD", "RD", "PPF", "NPS", "Standing Instructions"]:
        (user_dir / sub).mkdir(parents=True, exist_ok=True)
    return user_dir


# Legacy: DUMPS_DIR points to default user's folder for backwards compatibility
# (used by modules that haven't been migrated to per-user yet)
DUMPS_DIR = get_user_dumps_dir(_DEFAULT_USERS[0]["id"])
