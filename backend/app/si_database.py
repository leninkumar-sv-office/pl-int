"""
XLSX-based database layer for Standing Instructions (NACH/ECS mandates).

Stores all SIs in a single xlsx file:
    dumps/Standing Instructions/Standing Instructions.xlsx

xlsx layout:
    Row 1: Headers
        A=ID, B=Bank, C=Beneficiary, D=Amount, E=Frequency, F=Purpose,
        G=Mandate Type, H=Account Number, I=Start Date, J=Expiry Date,
        K=Alert Days, L=Status, M=Remarks
    Row 2+: Data rows (one per SI)
"""

import hashlib
import threading
import uuid
from datetime import datetime, date
from pathlib import Path

import openpyxl

from .models import SIItem


# ═══════════════════════════════════════════════════════════
#  FILE PATH
# ═══════════════════════════════════════════════════════════

from app.config import DUMPS_DIR
SI_DIR = DUMPS_DIR / "Standing Instructions"
SI_FILE = SI_DIR / "Standing Instructions.xlsx"

_lock = threading.Lock()

# Column mapping (1-indexed for openpyxl)
_COLS = {
    "id": 1,
    "bank": 2,
    "beneficiary": 3,
    "amount": 4,
    "frequency": 5,
    "purpose": 6,
    "mandate_type": 7,
    "account_number": 8,
    "start_date": 9,
    "expiry_date": 10,
    "alert_days": 11,
    "status": 12,
    "remarks": 13,
}

_HEADERS = ["ID", "Bank", "Beneficiary", "Amount", "Frequency", "Purpose",
            "Mandate Type", "Account Number", "Start Date", "Expiry Date",
            "Alert Days", "Status", "Remarks"]


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _to_date_str(val) -> str:
    """Convert openpyxl cell value to YYYY-MM-DD string."""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return ""


def _ensure_file():
    """Create the xlsx file with headers if it doesn't exist."""
    SI_DIR.mkdir(parents=True, exist_ok=True)
    if SI_FILE.exists():
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Standing Instructions"
    for i, h in enumerate(_HEADERS, 1):
        ws.cell(1, i, h)
    wb.save(str(SI_FILE))
    wb.close()


# ═══════════════════════════════════════════════════════════
#  LOAD / SAVE
# ═══════════════════════════════════════════════════════════

def _load() -> list:
    """Read all SI rows from the xlsx file."""
    if not SI_FILE.exists():
        return []
    try:
        wb = openpyxl.load_workbook(str(SI_FILE), data_only=True)
    except Exception as e:
        print(f"[SI] Error loading {SI_FILE}: {e}")
        return []

    ws = wb.active
    items = []
    for row in range(2, ws.max_row + 1):
        row_id = ws.cell(row, _COLS["id"]).value
        if not row_id:
            continue
        items.append({
            "id": str(row_id),
            "bank": str(ws.cell(row, _COLS["bank"]).value or ""),
            "beneficiary": str(ws.cell(row, _COLS["beneficiary"]).value or ""),
            "amount": float(ws.cell(row, _COLS["amount"]).value or 0),
            "frequency": str(ws.cell(row, _COLS["frequency"]).value or "Monthly"),
            "purpose": str(ws.cell(row, _COLS["purpose"]).value or "SIP"),
            "mandate_type": str(ws.cell(row, _COLS["mandate_type"]).value or "NACH"),
            "account_number": str(ws.cell(row, _COLS["account_number"]).value or ""),
            "start_date": _to_date_str(ws.cell(row, _COLS["start_date"]).value),
            "expiry_date": _to_date_str(ws.cell(row, _COLS["expiry_date"]).value),
            "alert_days": int(ws.cell(row, _COLS["alert_days"]).value or 30),
            "status": str(ws.cell(row, _COLS["status"]).value or "Active"),
            "remarks": str(ws.cell(row, _COLS["remarks"]).value or ""),
        })
    wb.close()
    return items


def _save(items: list):
    """Write all SI rows to the xlsx file (full rewrite)."""
    _ensure_file()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Standing Instructions"

    # Header row
    for i, h in enumerate(_HEADERS, 1):
        ws.cell(1, i, h)

    # Data rows
    for r, item in enumerate(items, 2):
        ws.cell(r, _COLS["id"], item["id"])
        ws.cell(r, _COLS["bank"], item["bank"])
        ws.cell(r, _COLS["beneficiary"], item["beneficiary"])
        ws.cell(r, _COLS["amount"], item["amount"])
        ws.cell(r, _COLS["frequency"], item["frequency"])
        ws.cell(r, _COLS["purpose"], item["purpose"])
        ws.cell(r, _COLS["mandate_type"], item["mandate_type"])
        ws.cell(r, _COLS["account_number"], item["account_number"])
        # Write dates as date objects for proper Excel formatting
        try:
            ws.cell(r, _COLS["start_date"], datetime.strptime(item["start_date"], "%Y-%m-%d"))
        except (ValueError, TypeError):
            ws.cell(r, _COLS["start_date"], item["start_date"])
        try:
            ws.cell(r, _COLS["expiry_date"], datetime.strptime(item["expiry_date"], "%Y-%m-%d"))
        except (ValueError, TypeError):
            ws.cell(r, _COLS["expiry_date"], item["expiry_date"])
        ws.cell(r, _COLS["alert_days"], item["alert_days"])
        ws.cell(r, _COLS["status"], item["status"])
        ws.cell(r, _COLS["remarks"], item.get("remarks", ""))

    wb.save(str(SI_FILE))
    wb.close()


# ═══════════════════════════════════════════════════════════
#  CRUD
# ═══════════════════════════════════════════════════════════

def get_all() -> list:
    """Return all SIs with computed fields."""
    with _lock:
        items = _load()
    today = datetime.now().date()
    for item in items:
        try:
            expiry = datetime.strptime(item["expiry_date"], "%Y-%m-%d").date()
            item["days_to_expiry"] = (expiry - today).days
        except (ValueError, KeyError):
            item["days_to_expiry"] = 0
    return items


def get_dashboard() -> dict:
    """Aggregate SI summary for dashboard."""
    items = get_all()
    active = [i for i in items if i.get("status") == "Active"]

    # Normalize all frequencies to monthly equivalent
    total_monthly = 0.0
    for i in active:
        amt = i.get("amount", 0)
        freq = i.get("frequency", "Monthly")
        if freq == "Monthly":
            total_monthly += amt
        elif freq == "Quarterly":
            total_monthly += amt / 3
        elif freq == "Half-Yearly":
            total_monthly += amt / 6
        elif freq == "Annually":
            total_monthly += amt / 12
        else:
            total_monthly += amt  # default to monthly

    expiring_soon = sum(
        1 for i in active
        if 0 < i.get("days_to_expiry", 0) <= i.get("alert_days", 30)
    )

    return {
        "active_count": len(active),
        "total_count": len(items),
        "total_monthly_outflow": round(total_monthly, 2),
        "expiring_soon": expiring_soon,
    }


def add(data: dict) -> dict:
    """Add a new standing instruction."""
    with _lock:
        items = _load()

        si = {
            "id": str(uuid.uuid4())[:8],
            "bank": data["bank"],
            "beneficiary": data["beneficiary"],
            "amount": data["amount"],
            "frequency": data.get("frequency", "Monthly"),
            "purpose": data.get("purpose", "SIP"),
            "mandate_type": data.get("mandate_type", "NACH"),
            "account_number": data.get("account_number", ""),
            "start_date": data["start_date"],
            "expiry_date": data["expiry_date"],
            "alert_days": data.get("alert_days", 30),
            "status": data.get("status", "Active"),
            "remarks": data.get("remarks", ""),
        }

        items.append(si)
        _save(items)
        return si


def update(si_id: str, data: dict) -> dict:
    """Update an existing standing instruction."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == si_id), None)
        if idx is None:
            raise ValueError(f"Standing instruction {si_id} not found")

        item = items[idx]
        for key, val in data.items():
            if val is not None and key in item:
                item[key] = val

        items[idx] = item
        _save(items)
        return item


def delete(si_id: str) -> dict:
    """Delete a standing instruction."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == si_id), None)
        if idx is None:
            raise ValueError(f"Standing instruction {si_id} not found")
        removed = items.pop(idx)
        _save(items)
        return {"message": f"SI {si_id} deleted", "item": removed}
