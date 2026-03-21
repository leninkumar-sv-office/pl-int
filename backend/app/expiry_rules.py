"""
Expiry/maturity alert rules for FD, RD, PPF, NPS, and Standing Instructions.

Per-user rules stored in backend/data/expiry_rules.json.
Background evaluation checks instruments against rules and sends notifications.
"""
import os
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_RULES_FILE = _DATA_DIR / "expiry_rules.json"

# Valid categories and their rule types
RULE_TYPES = {
    "fd": [
        {"type": "days_before_maturity", "label": "Days before maturity", "needs_days": True},
        {"type": "on_maturity", "label": "On maturity day", "needs_days": False},
    ],
    "rd": [
        {"type": "days_before_maturity", "label": "Days before maturity", "needs_days": True},
        {"type": "on_maturity", "label": "On maturity day", "needs_days": False},
    ],
    "ppf": [
        {"type": "days_before_maturity", "label": "Days before maturity", "needs_days": True},
        {"type": "on_maturity", "label": "On maturity day", "needs_days": False},
    ],
    "nps": [
        {"type": "contribution_reminder", "label": "Contribution reminder", "needs_days": False},
    ],
    "si": [
        {"type": "days_before_expiry", "label": "Days before expiry", "needs_days": True},
        {"type": "on_expiry", "label": "On expiry day", "needs_days": False},
    ],
    "insurance": [
        {"type": "days_before_expiry", "label": "Days before expiry", "needs_days": True},
        {"type": "on_expiry", "label": "On expiry day", "needs_days": False},
    ],
}


# ── Persistence ──────────────────────────────────────────

def _load_all() -> dict:
    try:
        with open(_RULES_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_all(data: dict):
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_RULES_FILE, "w") as f:
        json.dump(data, f, indent=2)
    try:
        from app import drive_service
        drive_service.sync_data_file("expiry_rules.json")
    except Exception:
        pass


def _user_key(email: str, user_id: str) -> str:
    return f"{email}:{user_id}"


# ── Public API ───────────────────────────────────────────

def get_rules(email: str, user_id: str, category: str = None) -> List[dict]:
    """Get expiry alert rules for a user, optionally filtered by category."""
    all_data = _load_all()
    key = _user_key(email, user_id)
    rules = all_data.get(key, [])
    if category:
        rules = [r for r in rules if r.get("category") == category]
    return rules


def save_rule(email: str, user_id: str, rule_data: dict) -> dict:
    """Create or update an expiry alert rule. Returns the saved rule."""
    all_data = _load_all()
    key = _user_key(email, user_id)
    rules = all_data.get(key, [])
    now = datetime.now().isoformat(timespec="seconds")

    rule_id = rule_data.get("id", "").strip()
    if rule_id:
        # Update existing
        for i, r in enumerate(rules):
            if r["id"] == rule_id:
                rules[i] = {**r, **rule_data, "updated_at": now}
                all_data[key] = rules
                _save_all(all_data)
                return rules[i]

    # Create new
    rule = {
        "id": str(uuid.uuid4())[:8],
        "category": rule_data.get("category", ""),
        "rule_type": rule_data.get("rule_type", ""),
        "days": rule_data.get("days", 30),
        "enabled": rule_data.get("enabled", True),
        "created_at": now,
        "updated_at": now,
    }
    rules.append(rule)
    all_data[key] = rules
    _save_all(all_data)
    logger.info(f"[ExpiryRules] Created rule: {rule['category']}/{rule['rule_type']} for {user_id}")
    return rule


def delete_rule(email: str, user_id: str, rule_id: str) -> bool:
    """Delete an expiry alert rule. Returns True if found and deleted."""
    all_data = _load_all()
    key = _user_key(email, user_id)
    rules = all_data.get(key, [])
    original_len = len(rules)
    rules = [r for r in rules if r["id"] != rule_id]
    if len(rules) < original_len:
        all_data[key] = rules
        _save_all(all_data)
        logger.info(f"[ExpiryRules] Deleted rule: {rule_id}")
        return True
    return False


def get_rule_types() -> dict:
    """Return available rule types for each category."""
    return RULE_TYPES


# ── Evaluator (called by alert_service background thread) ──

def evaluate_expiry_rules():
    """Check all users' expiry rules against their instrument data.
    Returns list of (user_email, message) tuples for triggered alerts."""
    from app.config import get_users
    from app import notification_service

    all_data = _load_all()
    if not all_data:
        return

    triggered = []

    for user_key, rules in all_data.items():
        if not rules:
            continue

        parts = user_key.split(":", 1)
        if len(parts) != 2:
            continue
        email, user_id = parts

        enabled_rules = [r for r in rules if r.get("enabled", True)]
        if not enabled_rules:
            continue

        # Load instrument data for this user
        instruments = _load_user_instruments(email, user_id)

        for rule in enabled_rules:
            category = rule.get("category", "")
            rule_type = rule.get("rule_type", "")
            days_threshold = rule.get("days", 30)

            items = instruments.get(category, [])
            for item in items:
                msg = _check_rule(item, category, rule_type, days_threshold)
                if msg:
                    triggered.append((email, user_id, rule, msg))

    # Send notifications for triggered rules
    for email, user_id, rule, message in triggered:
        # Check cooldown (use rule ID + item info as dedup key)
        from app import alert_service
        cooldown_key = f"expiry_{rule['id']}"
        if not alert_service._check_cooldown(cooldown_key, 1440):  # 24h cooldown
            continue

        success = notification_service.notify(
            "email", f"Portfolio Alert: {rule['category'].upper()}", message,
            user_email=email,
        )
        alert_service._record_history(
            cooldown_key, f"Expiry: {rule['category']}/{rule['rule_type']}",
            "email", message, success,
        )


def _load_user_instruments(email: str, user_id: str) -> Dict[str, list]:
    """Load FD/RD/PPF/NPS/SI data for a specific user."""
    result = {"fd": [], "rd": [], "ppf": [], "nps": [], "si": [], "insurance": []}
    try:
        from app.config import get_user_dumps_dir
        dumps_dir = get_user_dumps_dir(user_id, email)
        if not dumps_dir:
            return result

        # FD
        try:
            from app.fd_database import get_all as get_fds
            result["fd"] = get_fds(dumps_dir)
        except Exception:
            pass

        # RD
        try:
            from app.rd_database import get_all as get_rds
            result["rd"] = get_rds(dumps_dir)
        except Exception:
            pass

        # PPF
        try:
            from app.ppf_database import PPFDatabase
            ppf_db = PPFDatabase(dumps_dir)
            result["ppf"] = ppf_db.get_all()
        except Exception:
            pass

        # NPS
        try:
            from app.nps_database import NPSDatabase
            nps_db = NPSDatabase(dumps_dir)
            result["nps"] = nps_db.get_all()
        except Exception:
            pass

        # SI
        try:
            from app.si_database import get_all as get_sis
            result["si"] = get_sis(dumps_dir)
        except Exception:
            pass

        # Insurance
        try:
            from app.insurance_database import get_all as get_insurance
            result["insurance"] = get_insurance(dumps_dir)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[ExpiryRules] Failed to load instruments for {user_id}: {e}")

    return result


def _check_rule(item: dict, category: str, rule_type: str, days_threshold: int) -> Optional[str]:
    """Check if an instrument triggers a rule. Returns alert message or None."""
    status = item.get("status", "").lower()
    if status not in ("active",):
        return None

    name = item.get("name", "") or item.get("account_name", "") or item.get("bank", "") or item.get("beneficiary", "")

    if category in ("fd", "rd", "ppf"):
        days_left = item.get("days_to_maturity", -1)
        maturity_date = item.get("maturity_date", "")

        if rule_type == "on_maturity" and days_left == 0:
            return f"{category.upper()} '{name}' matures today ({maturity_date})!"

        if rule_type == "days_before_maturity" and 0 < days_left <= days_threshold:
            return f"{category.upper()} '{name}' matures in {days_left} day(s) on {maturity_date}."

    elif category in ("si", "insurance"):
        days_left = item.get("days_to_expiry", -1)
        expiry_date = item.get("expiry_date", "")
        label = "Insurance" if category == "insurance" else "Standing Instruction"

        if rule_type == "on_expiry" and days_left == 0:
            return f"{label} '{name}' expires today ({expiry_date})!"

        if rule_type == "days_before_expiry" and 0 < days_left <= days_threshold:
            return f"{label} '{name}' expires in {days_left} day(s) on {expiry_date}."

    elif category == "nps":
        if rule_type == "contribution_reminder":
            # Check if no contribution this month
            contributions = item.get("contributions", [])
            today = datetime.now()
            current_month = today.strftime("%Y-%m")
            has_this_month = any(
                c.get("date", "").startswith(current_month)
                for c in contributions
            )
            if not has_this_month and today.day >= 25:
                return f"NPS '{name}': No contribution recorded for {today.strftime('%B %Y')}."

    return None
