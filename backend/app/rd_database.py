"""
Recurring Deposit database layer.

Reads xlsx metadata from dumps/RD/ (rows 1-3 only) and computes ALL
installments with quarterly compound interest in Python.

Also supports manual CRUD via JSON file and creates xlsx files for new entries.

xlsx layout:
    Row 1: [_, start_date(B), _, _, =SUM(E6:E66), _, _, tenure_months(H), _, _, bank(K)]
    Row 2: [_, =end_date(B), _, _, =interest(E), _, _, payout(H), _, _, frequency(K)]
    Row 3: [_, rate_decimal(B), _, _, =maturity(E), _, _, sip(H)]
    Row 5: headers
    Row 6+: monthly data rows

Compound interest formula (quarterly, freq=4):
    Every 4th month: interest = (SIP * month_num + cumulative_interest) * rate * freq / 12
    This compounds because cumulative_interest includes all previous interest.

Special cases:
    - File 020123343379: E6=10000 (double first payment, hardcoded)
    - All others: E6 formula = IF(D6-NOW()<=0, $H$3, "")
"""

import json
import hashlib
import threading
import uuid
import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from pathlib import Path
import openpyxl
from openpyxl.utils import get_column_letter

from .models import RDItem


# ═══════════════════════════════════════════════════════════
#  FILE PATHS
# ═══════════════════════════════════════════════════════════

DUMPS_DIR = Path(__file__).resolve().parent.parent.parent / "dumps"
RD_XLSX_DIR = DUMPS_DIR / "RD"
RD_JSON_FILE = DUMPS_DIR / "recurring_deposits.json"

_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _gen_rd_id(name: str) -> str:
    """Deterministic ID from RD name."""
    return hashlib.md5(name.encode()).hexdigest()[:8]


def _extract_account_number(filename: str) -> str:
    """Extract account number from filename like 'Post Office RD - 020123343379'."""
    match = re.search(r'(\d{10,})', filename)
    return match.group(1) if match else ""


def _to_date(val) -> date | None:
    """Convert openpyxl cell value to date."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return None


# ═══════════════════════════════════════════════════════════
#  XLSX PARSER — Python-computed installments
# ═══════════════════════════════════════════════════════════

def _parse_rd_xlsx(filepath: Path) -> dict:
    """Parse a single RD xlsx file.

    Reads metadata from rows 1-3 only. Checks row 6 for special
    first-payment overrides (hardcoded values). Computes all
    installments and compound interest in Python.
    """
    name = filepath.stem
    account_number = _extract_account_number(name)

    # ── Read metadata (data_only=True for cached non-formula values) ──
    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    ws = wb["Index"]

    start_date_raw = ws.cell(1, 2).value                     # B1
    maturity_months_raw = ws.cell(1, 8).value or 60           # H1
    bank = ws.cell(1, 11).value or "Post Office"              # K1

    interest_payout = ws.cell(2, 8).value or "Maturity"       # H2
    frequency = ws.cell(2, 11).value or 4                     # K2

    rate_decimal = ws.cell(3, 2).value or 0                   # B3
    sip = ws.cell(3, 8).value or 0                            # H3

    wb.close()

    # ── Check for special first-payment (read WITHOUT data_only) ──
    first_payment = None
    try:
        wb_formula = openpyxl.load_workbook(str(filepath))
        ws_formula = wb_formula["Index"]
        e6_val = ws_formula.cell(6, 5).value
        # If E6 is a number (not a formula string), it's hardcoded
        if isinstance(e6_val, (int, float)):
            first_payment = float(e6_val)
        wb_formula.close()
    except Exception:
        pass

    # ── Convert & derive ─────────────────────────────────
    start_dt = _to_date(start_date_raw) or date.today()
    rate_decimal = float(rate_decimal)
    sip = float(sip)
    freq = int(frequency)
    tenure_months = int(maturity_months_raw)
    rate_pct = round(rate_decimal * 100, 4) if rate_decimal < 1 else round(rate_decimal, 4)
    rate_for_calc = rate_decimal if rate_decimal < 1 else rate_decimal / 100

    end_dt = start_dt + relativedelta(months=tenure_months)

    # If first_payment differs from SIP, use it; otherwise ignore
    if first_payment is not None and abs(first_payment - sip) > 0.01:
        month1_amount = first_payment
    else:
        month1_amount = sip

    # ── Generate installments with compound interest ──────
    today = date.today()
    installments = []
    cumulative_interest = 0.0
    total_deposited_past = 0.0
    total_deposited_all = 0.0
    total_interest_earned = 0.0
    total_interest_projected = 0.0

    for m in range(1, tenure_months + 1):
        inst_date = start_dt + relativedelta(months=m - 1)
        is_past = inst_date <= today

        # Monthly deposit
        invested = month1_amount if m == 1 else sip
        total_deposited_all += invested
        if is_past:
            total_deposited_past += invested

        # Compound interest at every freq-th month
        is_compound_month = (freq > 0 and m % freq == 0)
        compound_interest = 0.0

        if is_compound_month:
            # Formula: (SIP * month + cumulative_interest) * rate * freq / 12
            compound_interest = round(
                (sip * m + cumulative_interest) * rate_for_calc * freq / 12, 2
            )
            cumulative_interest += compound_interest

        if is_past:
            total_interest_earned += compound_interest
        else:
            total_interest_projected += compound_interest

        installments.append({
            "month": m,
            "date": inst_date.strftime("%Y-%m-%d"),
            "amount_invested": round(invested, 2),
            "interest_earned": round(compound_interest, 2) if is_past else 0.0,
            "interest_projected": round(compound_interest, 2) if not is_past else 0.0,
            "is_compound_month": is_compound_month,
            "cumulative_interest": round(cumulative_interest, 2),
            "is_past": is_past,
        })

    # ── Totals ────────────────────────────────────────────
    maturity_amount = round(total_deposited_all + cumulative_interest, 2)
    status = "Matured" if end_dt <= today else "Active"
    days_to_maturity = max(0, (end_dt - today).days)

    installments_paid = sum(1 for i in installments if i["is_past"])

    return {
        "id": _gen_rd_id(name),
        "name": name,
        "account_number": account_number,
        "bank": bank,
        "monthly_amount": round(sip, 2),
        "interest_rate": rate_pct,
        "compounding_frequency": freq,
        "interest_payout": interest_payout,
        "tenure_months": tenure_months,
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "maturity_date": end_dt.strftime("%Y-%m-%d"),
        "maturity_amount": maturity_amount,
        "total_deposited": round(total_deposited_past, 2),
        "total_interest_accrued": round(total_interest_earned, 2),
        "total_interest_projected": round(total_interest_projected, 2),
        "interest_earned": round(total_interest_earned, 2),
        "status": status,
        "days_to_maturity": days_to_maturity,
        "source": "xlsx",
        "remarks": "",
        "installments": installments,
        "installments_paid": installments_paid,
        "installments_total": len(installments),
    }


def _parse_all_xlsx() -> list:
    """Parse all xlsx files from dumps/RD/ directory."""
    results = []
    if not RD_XLSX_DIR.exists():
        return results

    for f in sorted(RD_XLSX_DIR.glob("*.xlsx")):
        if f.name.startswith("~$"):
            continue
        if "_Archive" in str(f):
            continue
        try:
            parsed = _parse_rd_xlsx(f)
            results.append(parsed)
        except Exception as e:
            print(f"[RD] Error parsing {f.name}: {e}")
    return results


# ═══════════════════════════════════════════════════════════
#  XLSX CREATION (for new entries from UI)
# ═══════════════════════════════════════════════════════════

def _create_rd_xlsx(name: str, bank: str, monthly_amount: float,
                    rate_pct: float, tenure_months: int, start_date: str,
                    frequency: int = 4):
    """Create an xlsx file following the RD template structure."""
    RD_XLSX_DIR.mkdir(parents=True, exist_ok=True)
    filepath = RD_XLSX_DIR / f"{name}.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Index"

    rate_dec = rate_pct / 100
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")

    # Row 1: Start Date, Latest Amount, Tenure Months, Bank
    ws.cell(1, 2, start_dt)
    ws.cell(1, 8, tenure_months)       # H1
    ws.cell(1, 11, bank)               # K1

    # Row 2: End Date, Payout, Frequency
    end_dt = start_dt + relativedelta(months=tenure_months)
    ws.cell(2, 2, end_dt)
    ws.cell(2, 8, "Maturity")          # H2
    ws.cell(2, 11, float(frequency))   # K2

    # Row 3: Rate (decimal), SIP
    ws.cell(3, 2, rate_dec)            # B3
    ws.cell(3, 8, monthly_amount)      # H3

    # Row 5: Headers
    headers = ['S.No', '', '#', 'Date', 'Amount Invested', 'Interest Earned', 'Interest to be Earned']
    for i, h in enumerate(headers, 1):
        ws.cell(5, i, h)

    # Data rows: compute values
    cumulative_interest = 0.0
    total_deposited = 0.0
    sip = monthly_amount

    for m in range(1, tenure_months + 1):
        row = m + 5
        inst_date = start_dt + relativedelta(months=m - 1)
        ws.cell(row, 1, m)
        ws.cell(row, 3, m)
        ws.cell(row, 4, inst_date)
        ws.cell(row, 5, sip)
        total_deposited += sip

        is_compound = (frequency > 0 and m % frequency == 0)
        interest = 0.0
        if is_compound:
            interest = round((sip * m + cumulative_interest) * rate_dec * frequency / 12, 2)
            cumulative_interest += interest

        ws.cell(row, 6, interest)  # Interest earned
        ws.cell(row, 7, interest)  # Interest projected

    # Set E1 (total deposited) and E3 (maturity amount)
    ws.cell(1, 5, total_deposited)
    ws.cell(2, 5, cumulative_interest)
    ws.cell(3, 5, round(total_deposited + cumulative_interest, 2))

    wb.save(str(filepath))
    wb.close()
    return filepath


# ═══════════════════════════════════════════════════════════
#  JSON LOAD / SAVE (manual entries)
# ═══════════════════════════════════════════════════════════

def _load_json() -> list:
    if not RD_JSON_FILE.exists():
        return []
    try:
        with open(RD_JSON_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, Exception):
        return []


def _save_json(data: list):
    DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RD_JSON_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ═══════════════════════════════════════════════════════════
#  CALCULATIONS (for manual/JSON entries)
# ═══════════════════════════════════════════════════════════

def _compute_rd_installments(monthly_amount: float, rate_pct: float,
                             tenure_months: int, start_date: str,
                             frequency: int = 4) -> list:
    """Generate full installment schedule with compound interest."""
    today = date.today()
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    rate_dec = rate_pct / 100
    cumulative_interest = 0.0
    installments = []

    for m in range(1, tenure_months + 1):
        inst_date = start_dt + relativedelta(months=m - 1)
        is_past = inst_date <= today
        is_compound = (frequency > 0 and m % frequency == 0)

        compound_interest = 0.0
        if is_compound:
            compound_interest = round(
                (monthly_amount * m + cumulative_interest) * rate_dec * frequency / 12, 2
            )
            cumulative_interest += compound_interest

        installments.append({
            "month": m,
            "date": inst_date.strftime("%Y-%m-%d"),
            "amount_invested": round(monthly_amount, 2),
            "interest_earned": round(compound_interest, 2) if is_past else 0.0,
            "interest_projected": round(compound_interest, 2) if not is_past else 0.0,
            "is_compound_month": is_compound,
            "cumulative_interest": round(cumulative_interest, 2),
            "is_past": is_past,
        })

    return installments


def _calc_maturity_date(start_date: str, tenure_months: int) -> str:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        maturity = start + relativedelta(months=tenure_months)
        return maturity.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def _enrich_json_item(item: dict) -> dict:
    """Add computed fields to a JSON-based RD item."""
    today = date.today()
    monthly = item.get("monthly_amount", 0)
    rate = item.get("interest_rate", 0)
    tenure = item.get("tenure_months", 60)
    start_date = item.get("start_date", "")
    freq = item.get("compounding_frequency", 4)

    # Generate installments
    if start_date and monthly > 0:
        installments = _compute_rd_installments(monthly, rate, tenure, start_date, freq)
    else:
        installments = item.get("installments", [])

    total_deposited = sum(i.get("amount_invested", 0) for i in installments if i.get("is_past"))
    total_interest_earned = sum(i.get("interest_earned", 0) for i in installments)
    total_interest_projected = sum(i.get("interest_projected", 0) for i in installments)
    cumulative = max((i.get("cumulative_interest", 0) for i in installments), default=0)
    total_all_deposits = sum(i.get("amount_invested", 0) for i in installments)

    try:
        mat = datetime.strptime(item.get("maturity_date", ""), "%Y-%m-%d").date()
        days_to_maturity = max(0, (mat - today).days)
        status = "Matured" if mat <= today else "Active"
    except (ValueError, KeyError):
        days_to_maturity = 0
        status = item.get("status", "Active")

    item["source"] = "manual"
    item["name"] = item.get("name", f"{item.get('bank', 'RD')} RD")
    item["account_number"] = item.get("account_number", "")
    item["compounding_frequency"] = freq
    item["interest_payout"] = item.get("interest_payout", "Maturity")
    item["total_deposited"] = round(total_deposited, 2)
    item["total_interest_accrued"] = round(total_interest_earned, 2)
    item["total_interest_projected"] = round(total_interest_projected, 2)
    item["interest_earned"] = round(total_interest_earned, 2)
    item["maturity_amount"] = round(total_all_deposits + cumulative, 2)
    item["installments"] = installments
    item["installments_paid"] = sum(1 for i in installments if i.get("is_past"))
    item["installments_total"] = len(installments)
    item["days_to_maturity"] = days_to_maturity
    item["status"] = status
    return item


# ═══════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════

def get_all() -> list:
    """Return all RDs: xlsx-parsed + JSON manual entries."""
    with _lock:
        xlsx_items = _parse_all_xlsx()
        json_items = _load_json()

    for item in json_items:
        _enrich_json_item(item)

    return xlsx_items + json_items


def get_dashboard() -> dict:
    """Aggregate RD summary for dashboard."""
    items = get_all()
    active = [i for i in items if i.get("status") == "Active"]

    monthly_commitment = sum(i.get("monthly_amount", 0) for i in active)
    total_deposited = sum(i.get("total_deposited", 0) for i in active)
    total_maturity = sum(i.get("maturity_amount", 0) for i in active)
    total_interest_accrued = sum(i.get("total_interest_accrued", 0) for i in active)

    return {
        "total_deposited": round(total_deposited, 2),
        "total_maturity_value": round(total_maturity, 2),
        "total_interest_accrued": round(total_interest_accrued, 2),
        "monthly_commitment": round(monthly_commitment, 2),
        "active_count": len(active),
        "total_count": len(items),
    }


def add(data: dict) -> dict:
    """Add a new RD — creates xlsx file + JSON entry."""
    monthly = data["monthly_amount"]
    rate = data["interest_rate"]
    tenure = data["tenure_months"]
    start_date = data["start_date"]
    bank = data["bank"]
    freq = data.get("compounding_frequency", 4)
    name = data.get("name", f"{bank} RD")
    account_number = data.get("account_number", "")

    if account_number:
        name = f"{bank} RD - {account_number}"

    maturity_date = data.get("maturity_date") or _calc_maturity_date(start_date, tenure)

    # Compute maturity
    installments = _compute_rd_installments(monthly, rate, tenure, start_date, freq)
    total_all_deposits = monthly * tenure
    cumulative = max((i.get("cumulative_interest", 0) for i in installments), default=0)
    maturity_amount = round(total_all_deposits + cumulative, 2)

    # Create xlsx file
    try:
        _create_rd_xlsx(
            name=name,
            bank=bank,
            monthly_amount=monthly,
            rate_pct=rate,
            tenure_months=tenure,
            start_date=start_date,
            frequency=freq,
        )
    except Exception as e:
        print(f"[RD] Warning: Could not create xlsx for {name}: {e}")

    # Save to JSON
    with _lock:
        items = _load_json()
        rd = {
            "id": _gen_rd_id(name),
            "name": name,
            "account_number": account_number,
            "bank": bank,
            "monthly_amount": monthly,
            "interest_rate": rate,
            "compounding_frequency": freq,
            "tenure_months": tenure,
            "start_date": start_date,
            "maturity_date": maturity_date,
            "maturity_amount": maturity_amount,
            "total_deposited": 0,
            "status": data.get("status", "Active"),
            "remarks": data.get("remarks", ""),
        }
        items.append(rd)
        _save_json(items)
        return rd


def update(rd_id: str, data: dict) -> dict:
    """Update an existing manual RD."""
    with _lock:
        items = _load_json()
        idx = next((i for i, x in enumerate(items) if x["id"] == rd_id), None)
        if idx is None:
            raise ValueError(f"RD {rd_id} not found")

        item = items[idx]
        for key, val in data.items():
            if val is not None and key in item and key != "installments":
                item[key] = val

        # Recompute maturity
        freq = item.get("compounding_frequency", 4)
        installments = _compute_rd_installments(
            item["monthly_amount"], item["interest_rate"],
            item["tenure_months"], item["start_date"], freq
        )
        total_all_deposits = item["monthly_amount"] * item["tenure_months"]
        cumulative = max((i.get("cumulative_interest", 0) for i in installments), default=0)
        item["maturity_amount"] = round(total_all_deposits + cumulative, 2)

        if "start_date" in data or "tenure_months" in data:
            if not data.get("maturity_date"):
                item["maturity_date"] = _calc_maturity_date(item["start_date"], item["tenure_months"])

        items[idx] = item
        _save_json(items)
        return item


def delete(rd_id: str) -> dict:
    """Delete a manual RD."""
    with _lock:
        items = _load_json()
        idx = next((i for i, x in enumerate(items) if x["id"] == rd_id), None)
        if idx is None:
            raise ValueError(f"RD {rd_id} not found")
        removed = items.pop(idx)
        _save_json(items)
        return {"message": f"RD {rd_id} deleted", "item": removed}


def add_installment(rd_id: str, installment: dict) -> dict:
    """Add an installment to a manual RD (for tracking extra payments)."""
    with _lock:
        items = _load_json()
        idx = next((i for i, x in enumerate(items) if x["id"] == rd_id), None)
        if idx is None:
            raise ValueError(f"RD {rd_id} not found")

        item = items[idx]
        if "extra_installments" not in item:
            item["extra_installments"] = []

        item["extra_installments"].append({
            "date": installment["date"],
            "amount": installment["amount"],
            "remarks": installment.get("remarks", ""),
        })

        items[idx] = item
        _save_json(items)
        return item
