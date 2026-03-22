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


def get_user_by_id(user_id: str) -> dict | None:
    """Find a user by ID."""
    return next((u for u in get_users() if u["id"] == user_id), None)


def get_user_email(user_id: str) -> str | None:
    """Return the Gmail email for a persona id, or None if not set."""
    user = get_user_by_id(user_id)
    return user.get("email") if user else None


def get_users_for_email(email: str) -> list:
    """Return all persona entries that belong to a given Gmail email."""
    email_lower = email.lower()
    return [u for u in get_users() if u.get("email", "").lower() == email_lower]


def get_user_dumps_dir(user_id: str, email: str | None = None) -> Path:
    """Get the dumps directory for a specific user.

    New layout:  dumps/{email}/{Name}/
    Legacy fallback (no email): dumps/{Name}/
    """
    users = get_users()
    user = next((u for u in users if u["id"] == user_id), None)
    folder_name = user["name"] if user else user_id
    resolved_email = email or (user.get("email") if user else None)

    if resolved_email:
        user_dir = DUMPS_BASE / resolved_email / folder_name
    else:
        user_dir = DUMPS_BASE / folder_name

    for sub in ["Stocks", "Mutual Funds", "FD", "RD", "PPF", "NPS", "Standing Instructions"]:
        (user_dir / sub).mkdir(parents=True, exist_ok=True)
    return user_dir


# Legacy: DUMPS_DIR points to default user's folder for backwards compatibility
DUMPS_DIR = get_user_dumps_dir(_DEFAULT_USERS[0]["id"])
