"""
PPF (Public Provident Fund) database layer.

JSON-based storage for PPF accounts with yearly contributions.
PPF: 15-year lock-in, annual compounding, max 1.5L/year, tax-free under 80C.
Current rate: 7.1% p.a. (can change quarterly by GOI).
"""

import json
import threading
import uuid
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from pathlib import Path


# ═══════════════════════════════════════════════════════════
#  FILE PATHS
# ═══════════════════════════════════════════════════════════

DUMPS_DIR = Path(__file__).resolve().parent.parent.parent / "dumps"
PPF_FILE = DUMPS_DIR / "ppf_accounts.json"

_lock = threading.Lock()

# PPF constants
PPF_DEFAULT_RATE = 7.1  # current rate (%)
PPF_TENURE_YEARS = 15
PPF_YEARLY_MAX = 150000
PPF_YEARLY_MIN = 500


# ═══════════════════════════════════════════════════════════
#  LOAD / SAVE
# ═══════════════════════════════════════════════════════════

def _load() -> list:
    if not PPF_FILE.exists():
        return []
    try:
        with open(PPF_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, Exception):
        return []


def _save(data: list):
    DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PPF_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ═══════════════════════════════════════════════════════════
#  CALCULATIONS
# ═══════════════════════════════════════════════════════════

def _get_financial_year(dt: date) -> str:
    """Get financial year string like '2023-24' for a given date."""
    if dt.month >= 4:  # April onwards = new FY
        return f"{dt.year}-{str(dt.year + 1)[-2:]}"
    else:
        return f"{dt.year - 1}-{str(dt.year)[-2:]}"


def _compute_ppf_schedule(account: dict) -> dict:
    """Compute yearly breakdown with interest and balances."""
    contributions = account.get("contributions", [])
    rate = account.get("interest_rate", PPF_DEFAULT_RATE)
    start_date_str = account.get("start_date", "")

    try:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_dt = date.today()

    today = date.today()
    maturity_dt = start_dt + relativedelta(years=PPF_TENURE_YEARS)

    # Group contributions by financial year
    contrib_by_fy = {}
    for c in contributions:
        try:
            c_date = datetime.strptime(c["date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        fy = _get_financial_year(c_date)
        if fy not in contrib_by_fy:
            contrib_by_fy[fy] = 0
        contrib_by_fy[fy] += c.get("amount", 0)

    # Build yearly schedule
    yearly_schedule = []
    opening_balance = 0
    total_deposited = 0
    total_interest = 0

    # Generate all FYs from start to min(maturity, today + some years)
    fy_start_year = start_dt.year if start_dt.month >= 4 else start_dt.year - 1
    end_year = max(maturity_dt.year, today.year + 1)

    for year in range(fy_start_year, end_year + 1):
        fy = f"{year}-{str(year + 1)[-2:]}"
        fy_end_date = date(year + 1, 3, 31)  # March 31
        fy_start_date = date(year, 4, 1)  # April 1

        # Skip FYs before account opened
        if fy_end_date < start_dt:
            continue
        # Stop after maturity + extension
        if fy_start_date > maturity_dt + relativedelta(years=5):
            break

        deposit = contrib_by_fy.get(fy, 0)
        # Interest = (opening_balance + deposit) * rate / 100 (annual compounding)
        interest = round((opening_balance + deposit) * rate / 100, 2)
        closing_balance = round(opening_balance + deposit + interest, 2)

        is_past = fy_end_date <= today
        year_num = year - fy_start_year + 1

        yearly_schedule.append({
            "year": year_num,
            "financial_year": fy,
            "opening_balance": round(opening_balance, 2),
            "deposit": round(deposit, 2),
            "interest_earned": interest,
            "closing_balance": closing_balance,
            "is_past": is_past,
        })

        total_deposited += deposit
        total_interest += interest
        opening_balance = closing_balance

        # Only show future years if there's still deposits possible or maturity pending
        if not is_past and deposit == 0 and fy_start_date > maturity_dt:
            break

    return {
        "yearly_schedule": yearly_schedule,
        "total_deposited": round(total_deposited, 2),
        "total_interest_earned": round(total_interest, 2),
        "current_balance": round(opening_balance, 2),
        "maturity_date": maturity_dt.strftime("%Y-%m-%d"),
    }


# ═══════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════

def get_all() -> list:
    """Return all PPF accounts with computed schedules."""
    with _lock:
        items = _load()

    today = date.today()
    for item in items:
        computed = _compute_ppf_schedule(item)
        item["yearly_schedule"] = computed["yearly_schedule"]
        item["total_deposited"] = computed["total_deposited"]
        item["total_interest_earned"] = computed["total_interest_earned"]
        item["current_balance"] = computed["current_balance"]
        item["maturity_date"] = computed["maturity_date"]

        try:
            mat = datetime.strptime(item["maturity_date"], "%Y-%m-%d").date()
            item["days_to_maturity"] = max(0, (mat - today).days)
            item["status"] = "Matured" if mat <= today else "Active"
        except (ValueError, KeyError):
            item["days_to_maturity"] = 0
            item["status"] = "Active"

        # Years completed
        try:
            start = datetime.strptime(item["start_date"], "%Y-%m-%d").date()
            item["years_completed"] = max(0, (today - start).days // 365)
        except (ValueError, KeyError):
            item["years_completed"] = 0

    return items


def get_dashboard() -> dict:
    """Aggregate PPF summary for dashboard."""
    items = get_all()
    active = [i for i in items if i.get("status") == "Active"]

    return {
        "total_deposited": round(sum(i.get("total_deposited", 0) for i in active), 2),
        "total_interest": round(sum(i.get("total_interest_earned", 0) for i in active), 2),
        "current_balance": round(sum(i.get("current_balance", 0) for i in active), 2),
        "active_count": len(active),
        "total_count": len(items),
    }


def add(data: dict) -> dict:
    """Add a new PPF account."""
    with _lock:
        items = _load()

        account = {
            "id": str(uuid.uuid4())[:8],
            "account_name": data.get("account_name", "PPF Account"),
            "bank": data.get("bank", "Post Office"),
            "account_number": data.get("account_number", ""),
            "interest_rate": data.get("interest_rate", PPF_DEFAULT_RATE),
            "start_date": data["start_date"],
            "tenure_years": data.get("tenure_years", PPF_TENURE_YEARS),
            "remarks": data.get("remarks", ""),
            "contributions": [],
        }

        items.append(account)
        _save(items)
        return account


def update(ppf_id: str, data: dict) -> dict:
    """Update a PPF account."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == ppf_id), None)
        if idx is None:
            raise ValueError(f"PPF account {ppf_id} not found")

        item = items[idx]
        for key, val in data.items():
            if val is not None and key in item and key != "contributions":
                item[key] = val

        items[idx] = item
        _save(items)
        return item


def delete(ppf_id: str) -> dict:
    """Delete a PPF account."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == ppf_id), None)
        if idx is None:
            raise ValueError(f"PPF account {ppf_id} not found")
        removed = items.pop(idx)
        _save(items)
        return {"message": f"PPF {ppf_id} deleted", "item": removed}


def add_contribution(ppf_id: str, contribution: dict) -> dict:
    """Add a yearly contribution to a PPF account."""
    with _lock:
        items = _load()
        idx = next((i for i, x in enumerate(items) if x["id"] == ppf_id), None)
        if idx is None:
            raise ValueError(f"PPF account {ppf_id} not found")

        item = items[idx]
        if "contributions" not in item:
            item["contributions"] = []

        amount = contribution.get("amount", 0)
        contrib_date = contribution.get("date", datetime.now().strftime("%Y-%m-%d"))

        # Validate yearly limit
        try:
            c_date = datetime.strptime(contrib_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid date format")

        fy = _get_financial_year(c_date)
        existing_fy_total = sum(
            c.get("amount", 0) for c in item["contributions"]
            if _get_financial_year(datetime.strptime(c["date"], "%Y-%m-%d").date()) == fy
        )

        if existing_fy_total + amount > PPF_YEARLY_MAX:
            raise ValueError(f"Exceeds yearly limit of ₹{PPF_YEARLY_MAX:,.0f}. "
                           f"Already deposited ₹{existing_fy_total:,.0f} in FY {fy}")

        item["contributions"].append({
            "date": contrib_date,
            "amount": amount,
            "remarks": contribution.get("remarks", ""),
        })

        items[idx] = item
        _save(items)
        return item
