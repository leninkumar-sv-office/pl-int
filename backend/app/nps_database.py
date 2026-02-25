"""
NPS (National Pension System) database layer.

JSON-based storage for NPS accounts with contributions.
NPS: Market-linked pension scheme, current_value is user-editable (no free NAV API).
Tax benefits under 80CCD(1), 80CCD(1B), 80CCD(2).
"""

import json
import threading
import uuid
from datetime import datetime, date
from pathlib import Path


# ═══════════════════════════════════════════════════════════
#  FILE PATHS
# ═══════════════════════════════════════════════════════════

from app.config import DUMPS_DIR
NPS_FILE = DUMPS_DIR / "nps_accounts.json"

_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════
#  LOAD / SAVE
# ═══════════════════════════════════════════════════════════

def _load() -> list:
    if not NPS_FILE.exists():
        return []
    try:
        with open(NPS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, Exception):
        return []


def _save(data: list):
    DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    with open(NPS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ═══════════════════════════════════════════════════════════
#  ENRICH
# ═══════════════════════════════════════════════════════════

def _enrich(account: dict) -> dict:
    """Compute derived fields for an NPS account."""
    contributions = account.get("contributions", [])
    total_contributed = sum(c.get("amount", 0) for c in contributions)
    current_value = account.get("current_value", 0)
    gain = round(current_value - total_contributed, 2)
    gain_pct = round((gain / total_contributed) * 100, 2) if total_contributed > 0 else 0

    today = date.today()
    try:
        start = datetime.strptime(account.get("start_date", ""), "%Y-%m-%d").date()
        years_active = max(0, round((today - start).days / 365.25, 1))
    except (ValueError, TypeError):
        years_active = 0

    # Status: if explicitly set, keep it; otherwise Active
    status = account.get("status", "Active")

    account["total_contributed"] = round(total_contributed, 2)
    account["gain"] = gain
    account["gain_pct"] = gain_pct
    account["years_active"] = years_active
    account["status"] = status
    return account


# ═══════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════

def get_all() -> list:
    """Return all NPS accounts with computed fields."""
    with _lock:
        items = _load()

    for item in items:
        _enrich(item)
    return items


def get_dashboard() -> dict:
    """Aggregate NPS summary for dashboard."""
    items = get_all()
    active = [i for i in items if i.get("status") == "Active"]

    total_contributed = round(sum(i.get("total_contributed", 0) for i in active), 2)
    current_value = round(sum(i.get("current_value", 0) for i in active), 2)
    total_gain = round(current_value - total_contributed, 2)
    gain_pct = round((total_gain / total_contributed) * 100, 2) if total_contributed > 0 else 0

    return {
        "total_contributed": total_contributed,
        "current_value": current_value,
        "total_gain": total_gain,
        "gain_pct": gain_pct,
        "active_count": len(active),
        "total_count": len(items),
    }


def add(data: dict) -> dict:
    """Add a new NPS account."""
    with _lock:
        items = _load()

        account = {
            "id": str(uuid.uuid4())[:8],
            "account_name": data.get("account_name", "NPS Account"),
            "pran": data.get("pran", ""),
            "tier": data.get("tier", "Tier I"),
            "fund_manager": data.get("fund_manager", ""),
            "scheme_preference": data.get("scheme_preference", "Auto Choice"),
            "start_date": data["start_date"],
            "current_value": data.get("current_value", 0),
            "status": data.get("status", "Active"),
            "remarks": data.get("remarks", ""),
            "contributions": [],
        }

        items.append(account)
        _save(items)
        return account


def update(nps_id: str, data: dict) -> dict:
    """Update an NPS account."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == nps_id), None)
        if idx is None:
            raise ValueError(f"NPS account {nps_id} not found")

        item = items[idx]
        for key, val in data.items():
            if val is not None and key in item and key != "contributions":
                item[key] = val

        items[idx] = item
        _save(items)
        return item


def delete(nps_id: str) -> dict:
    """Delete an NPS account."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == nps_id), None)
        if idx is None:
            raise ValueError(f"NPS account {nps_id} not found")
        removed = items.pop(idx)
        _save(items)
        return {"message": f"NPS {nps_id} deleted", "item": removed}


def add_contribution(nps_id: str, contribution: dict) -> dict:
    """Add a contribution to an NPS account."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == nps_id), None)
        if idx is None:
            raise ValueError(f"NPS account {nps_id} not found")

        item = items[idx]
        if "contributions" not in item:
            item["contributions"] = []

        amount = contribution.get("amount", 0)
        contrib_date = contribution.get("date", datetime.now().strftime("%Y-%m-%d"))

        try:
            datetime.strptime(contrib_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format")

        item["contributions"].append({
            "date": contrib_date,
            "amount": amount,
            "remarks": contribution.get("remarks", ""),
        })

        items[idx] = item
        _save(items)
        return item
