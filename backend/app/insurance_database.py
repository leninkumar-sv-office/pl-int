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


def _sync_to_drive(filepath: Path):
    try:
        from .config import DUMPS_BASE
        from . import drive_service
        rel = filepath.resolve().relative_to(DUMPS_BASE.resolve())
        drive_service.sync_dumps_file(str(rel))
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
#  LOAD / SAVE
# ═══════════════════════════════════════════════════════════

def _load(json_file: Path = None) -> list:
    json_file = json_file or INSURANCE_FILE
    if not json_file.exists():
        return []
    with open(json_file, "r") as f:
        return json.load(f)


def _save(data: list, json_file: Path = None):
    json_file = json_file or INSURANCE_FILE
    json_file.parent.mkdir(parents=True, exist_ok=True)
    with open(json_file, "w") as f:
        json.dump(data, f, indent=2)
    _sync_to_drive(json_file)


# ═══════════════════════════════════════════════════════════
#  CRUD
# ═══════════════════════════════════════════════════════════

def get_all(base_dir=None) -> list:
    """Return all policies with computed fields."""
    json_file = (Path(base_dir) / "insurance_policies.json") if base_dir else INSURANCE_FILE
    with _lock:
        items = _load(json_file)
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


def get_dashboard(base_dir=None) -> dict:
    """Aggregate insurance summary for dashboard."""
    items = get_all(base_dir=base_dir)
    active = [i for i in items if i.get("status") == "Active"]

    expiring_soon = sum(1 for i in active if 0 < i.get("days_to_expiry", 0) <= 90)

    return {
        "total_annual_premium": sum(i.get("annual_premium", 0) for i in active),
        "total_coverage": sum(i.get("coverage_amount", 0) for i in active),
        "active_count": len(active),
        "total_count": len(items),
        "expiring_soon": expiring_soon,
    }


def add(data: dict, base_dir=None) -> dict:
    """Add a new insurance policy."""
    json_file = (Path(base_dir) / "insurance_policies.json") if base_dir else INSURANCE_FILE
    with _lock:
        items = _load(json_file)

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
        _save(items, json_file)
        return policy


def update(policy_id: str, data: dict, base_dir=None) -> dict:
    """Update an existing insurance policy."""
    json_file = (Path(base_dir) / "insurance_policies.json") if base_dir else INSURANCE_FILE
    with _lock:
        items = _load(json_file)
        idx = next((i for i, x in enumerate(items) if x["id"] == policy_id), None)
        if idx is None:
            raise ValueError(f"Insurance policy {policy_id} not found")

        item = items[idx]
        for key, val in data.items():
            if val is not None and key in item:
                item[key] = val

        items[idx] = item
        _save(items, json_file)
        return item


def delete(policy_id: str, base_dir=None) -> dict:
    """Delete an insurance policy."""
    json_file = (Path(base_dir) / "insurance_policies.json") if base_dir else INSURANCE_FILE
    with _lock:
        items = _load(json_file)
        idx = next((i for i, x in enumerate(items) if x["id"] == policy_id), None)
        if idx is None:
            raise ValueError(f"Insurance policy {policy_id} not found")
        removed = items.pop(idx)
        _save(items, json_file)
        return {"message": f"Policy {policy_id} deleted", "item": removed}
