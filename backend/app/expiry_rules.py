"""
Expiry/maturity alert rules for FD, RD, PPF, NPS, SI, and Insurance.

Per-user rules stored in dumps/{email}/settings/expiry_rules_{userId}.json.
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

from .config import DUMPS_BASE

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

# Legacy file (for migration)
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LEGACY_RULES_FILE = _DATA_DIR / "expiry_rules.json"


# ── Per-user file paths ─────────────────────────────────

def _settings_dir(email: str) -> Path:
    """Get the settings directory for a user: dumps/{email}/settings/"""
    d = DUMPS_BASE / email / "settings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _rules_file(email: str, user_id: str) -> Path:
    return _settings_dir(email) / f"expiry_rules_{user_id}.json"


def _sync_to_drive(email: str, user_id: str):
    """Upload user's rules file to Drive under dumps/{email}/settings/."""
    try:
        from app import drive_service
        rel_path = f"{email}/settings/expiry_rules_{user_id}.json"
        drive_service.sync_dumps_file(rel_path, email=email)
    except Exception:
        pass


# ── Persistence ──────────────────────────────────────────

def _load_rules(email: str, user_id: str) -> list:
    fp = _rules_file(email, user_id)
    try:
        with open(fp) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        # Try legacy migration
        return _migrate_legacy(email, user_id)


def _save_rules(email: str, user_id: str, rules: list):
    fp = _rules_file(email, user_id)
    with open(fp, "w") as f:
        json.dump(rules, f, indent=2)
    _sync_to_drive(email, user_id)


def _migrate_legacy(email: str, user_id: str) -> list:
    """Migrate rules from legacy shared file to per-user file."""
    if not _LEGACY_RULES_FILE.exists():
        return []
    try:
        with open(_LEGACY_RULES_FILE) as f:
            all_data = json.load(f)
        key = f"{email}:{user_id}"
        rules = all_data.get(key, [])
        if rules:
            _save_rules(email, user_id, rules)
            # Remove from legacy file
            del all_data[key]
            if all_data:
                with open(_LEGACY_RULES_FILE, "w") as f:
                    json.dump(all_data, f, indent=2)
            else:
                _LEGACY_RULES_FILE.unlink(missing_ok=True)
            logger.info(f"[ExpiryRules] Migrated {len(rules)} rules for {user_id} to per-user file")
        return rules
    except Exception as e:
        logger.error(f"[ExpiryRules] Legacy migration failed: {e}")
        return []


# ── Public API ───────────────────────────────────────────

def get_rules(email: str, user_id: str, category: str = None) -> List[dict]:
    """Get expiry alert rules for a user, optionally filtered by category."""
    rules = _load_rules(email, user_id)
    if category:
        rules = [r for r in rules if r.get("category") == category]
    return rules


def save_rule(email: str, user_id: str, rule_data: dict) -> dict:
    """Create or update an expiry alert rule. Returns the saved rule."""
    rules = _load_rules(email, user_id)
    now = datetime.now().isoformat(timespec="seconds")

    rule_id = rule_data.get("id", "").strip()
    if rule_id:
        for i, r in enumerate(rules):
            if r["id"] == rule_id:
                rules[i] = {**r, **rule_data, "updated_at": now}
                _save_rules(email, user_id, rules)
                return rules[i]

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
    _save_rules(email, user_id, rules)
    logger.info(f"[ExpiryRules] Created rule: {rule['category']}/{rule['rule_type']} for {user_id}")
    return rule


def delete_rule(email: str, user_id: str, rule_id: str) -> bool:
    """Delete an expiry alert rule. Returns True if found and deleted."""
    rules = _load_rules(email, user_id)
    original_len = len(rules)
    rules = [r for r in rules if r["id"] != rule_id]
    if len(rules) < original_len:
        _save_rules(email, user_id, rules)
        logger.info(f"[ExpiryRules] Deleted rule: {rule_id}")
        return True
    return False


def get_rule_types() -> dict:
    """Return available rule types for each category."""
    return RULE_TYPES


# ── Evaluator (called by alert_service background thread) ──

def evaluate_expiry_rules():
    """Check all users' expiry rules against their instrument data."""
    from app.config import get_users
    from app import notification_service

    users = get_users()
    if not users:
        return

    for user in users:
        email = user.get("email", "")
        user_id = user.get("id", "")
        if not email or not user_id:
            continue

        rules = _load_rules(email, user_id)
        enabled_rules = [r for r in rules if r.get("enabled", True)]
        if not enabled_rules:
            continue

        instruments = _load_user_instruments(email, user_id)

        for rule in enabled_rules:
            category = rule.get("category", "")
            rule_type = rule.get("rule_type", "")
            days_threshold = rule.get("days", 30)

            items = instruments.get(category, [])
            for item in items:
                msg = _check_rule(item, category, rule_type, days_threshold)
                if msg:
                    from app import alert_service
                    cooldown_key = f"expiry_{rule['id']}"
                    if not alert_service._check_cooldown(cooldown_key, 1440):
                        continue
                    success = notification_service.notify(
                        "email", f"Portfolio Alert: {rule['category'].upper()}", msg,
                        user_email=email,
                    )
                    alert_service._record_history(
                        cooldown_key, f"Expiry: {rule['category']}/{rule['rule_type']}",
                        "email", msg, success,
                    )


def _load_user_instruments(email: str, user_id: str) -> Dict[str, list]:
    """Load FD/RD/PPF/NPS/SI/Insurance data for a specific user."""
    result = {"fd": [], "rd": [], "ppf": [], "nps": [], "si": [], "insurance": []}
    try:
        from app.config import get_user_dumps_dir
        dumps_dir = get_user_dumps_dir(user_id, email)
        if not dumps_dir:
            return result

        try:
            from app.fd_database import get_all as get_fds
            result["fd"] = get_fds(dumps_dir)
        except Exception:
            pass
        try:
            from app.rd_database import get_all as get_rds
            result["rd"] = get_rds(dumps_dir)
        except Exception:
            pass
        try:
            from app.ppf_database import PPFDatabase
            ppf_db = PPFDatabase(dumps_dir)
            result["ppf"] = ppf_db.get_all()
        except Exception:
            pass
        try:
            from app.nps_database import NPSDatabase
            nps_db = NPSDatabase(dumps_dir)
            result["nps"] = nps_db.get_all()
        except Exception:
            pass
        try:
            from app.si_database import get_all as get_sis
            result["si"] = get_sis(dumps_dir)
        except Exception:
            pass
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
