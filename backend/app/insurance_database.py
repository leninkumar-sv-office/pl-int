"""
JSON-based database layer for Insurance Policies.

Stores all policies in a single JSON file: dumps/insurance_policies.json
"""

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from .models import InsurancePolicy


# ═══════════════════════════════════════════════════════════
#  FILE PATH
# ═══════════════════════════════════════════════════════════

from app.config import DUMPS_DIR
INSURANCE_FILE = DUMPS_DIR / "insurance_policies.json"

_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════
#  LOAD / SAVE
# ═══════════════════════════════════════════════════════════

def _load() -> list:
    if not INSURANCE_FILE.exists():
        return []
    with open(INSURANCE_FILE, "r") as f:
        return json.load(f)


def _save(data: list):
    DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    with open(INSURANCE_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ═══════════════════════════════════════════════════════════
#  CRUD
# ═══════════════════════════════════════════════════════════

def get_all() -> list:
    """Return all policies with computed fields."""
    with _lock:
        items = _load()
    today = datetime.now().date()
    for item in items:
        try:
            expiry = datetime.strptime(item["expiry_date"], "%Y-%m-%d").date()
            item["days_to_expiry"] = (expiry - today).days
        except (ValueError, KeyError):
            item["days_to_expiry"] = 0
        # Annualized premium
        freq = item.get("payment_frequency", "Annual")
        premium = item.get("premium", 0)
        if freq == "Monthly":
            item["annual_premium"] = premium * 12
        elif freq == "Quarterly":
            item["annual_premium"] = premium * 4
        else:
            item["annual_premium"] = premium
    return items


def get_dashboard() -> dict:
    """Aggregate insurance summary for dashboard."""
    items = get_all()
    active = [i for i in items if i.get("status") == "Active"]

    expiring_soon = sum(1 for i in active if 0 < i.get("days_to_expiry", 0) <= 90)

    return {
        "total_annual_premium": sum(i.get("annual_premium", 0) for i in active),
        "total_coverage": sum(i.get("coverage_amount", 0) for i in active),
        "active_count": len(active),
        "total_count": len(items),
        "expiring_soon": expiring_soon,
    }


def add(data: dict) -> dict:
    """Add a new insurance policy."""
    with _lock:
        items = _load()

        policy = {
            "id": str(uuid.uuid4())[:8],
            "policy_name": data["policy_name"],
            "provider": data["provider"],
            "type": data.get("type", "Health"),
            "policy_number": data.get("policy_number", ""),
            "premium": data["premium"],
            "coverage_amount": data.get("coverage_amount", 0),
            "start_date": data["start_date"],
            "expiry_date": data["expiry_date"],
            "payment_frequency": data.get("payment_frequency", "Annual"),
            "status": data.get("status", "Active"),
            "remarks": data.get("remarks", ""),
        }

        items.append(policy)
        _save(items)
        return policy


def update(policy_id: str, data: dict) -> dict:
    """Update an existing insurance policy."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == policy_id), None)
        if idx is None:
            raise ValueError(f"Insurance policy {policy_id} not found")

        item = items[idx]
        for key, val in data.items():
            if val is not None and key in item:
                item[key] = val

        items[idx] = item
        _save(items)
        return item


def delete(policy_id: str) -> dict:
    """Delete an insurance policy."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == policy_id), None)
        if idx is None:
            raise ValueError(f"Insurance policy {policy_id} not found")
        removed = items.pop(idx)
        _save(items)
        return {"message": f"Policy {policy_id} deleted", "item": removed}
