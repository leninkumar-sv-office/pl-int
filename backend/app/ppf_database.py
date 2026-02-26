"""
PPF (Public Provident Fund) database layer.

Reads xlsx metadata from dumps/PPF/ (rows 1-4 only) and computes ALL
installments in Python -- never trusts cached formula values from xlsx.

Also supports migration from legacy JSON format and creates xlsx files
for new entries.

xlsx layout (matches FD/RD format):
    Row 1: [_, start_date(B), _, _, total_invested(E), _, _, maturity_years(H), _, _, bank(K)]
    Row 2: [_, end_date(B), _, _, interest_earned(E), _, _, "Annually"(H), _, _, sip_frequency(K)]
    Row 3: [_, rate_decimal(B), _, _, maturity_amount(E), _, _, sip_amount(H), _, _, account_number(K)]
    Row 4: [_, sip_end_date(B), _, _, remarks(E)]
    Row 5: headers [S.No, _, #, Date, Amount Invested, Interest Earned, Interest to be Earned]
    Row 6+: monthly data rows

Interest logic (PPF annual compounding):
    - PPF rate is annual (e.g. 7.1%)
    - Interest compounds annually: each year, interest = balance * rate
    - SIP deposits occur at sip_frequency intervals during SIP period
    - After SIP ends, no more deposits, but compounding continues until maturity
    - is_compound_month = True every 12th month from start (annual compounding)
"""

import json
import hashlib
import threading
import uuid
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from pathlib import Path
import openpyxl

from app.config import DUMPS_DIR


# ===================================================================
#  FILE PATHS
# ===================================================================

PPF_DIR = DUMPS_DIR / "PPF"
PPF_JSON_FILE = DUMPS_DIR / "ppf_accounts.json"  # legacy, for migration

_lock = threading.Lock()

# PPF constants
PPF_DEFAULT_RATE = 7.1   # current rate (%)
PPF_TENURE_YEARS = 15
PPF_YEARLY_MAX = 150000
PPF_YEARLY_MIN = 500


# ===================================================================
#  HELPERS
# ===================================================================

def _gen_ppf_id(name: str) -> str:
    """Deterministic ID from PPF account name (filename stem)."""
    return hashlib.md5(name.encode()).hexdigest()[:8]


def _to_date(val) -> date | None:
    """Convert openpyxl cell value to date."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return None


def _to_str(val, default=""):
    """Safely convert cell value to string."""
    if val is None:
        return default
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    return str(val).strip()


def _to_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _sip_freq_to_months(freq: str) -> int:
    """Convert SIP frequency string to interval in months.
    monthly -> 1, quarterly -> 3, yearly -> 12.
    """
    f = (freq or "monthly").strip().lower()
    if "month" in f:
        return 1
    if "quarter" in f:
        return 3
    if "year" in f or "annual" in f:
        return 12
    return 1  # default monthly


def _get_financial_year(dt: date) -> str:
    """Get financial year string like '2023-24' for a given date."""
    if dt.month >= 4:
        return f"{dt.year}-{str(dt.year + 1)[-2:]}"
    else:
        return f"{dt.year - 1}-{str(dt.year)[-2:]}"


# ===================================================================
#  XLSX PARSER -- Python-computed installments
# ===================================================================

def _parse_ppf_xlsx(filepath: Path) -> dict:
    """Parse a single PPF xlsx file.

    Reads ONLY metadata from rows 1-4.
    Computes ALL monthly installments and totals in Python.
    """
    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    ws = wb["Index"]
    name = filepath.stem

    # -- Metadata rows 1-4 --
    start_date_raw = ws.cell(1, 2).value                          # B1: start date
    maturity_years = _to_float(ws.cell(1, 8).value, PPF_TENURE_YEARS)  # H1: years
    bank = _to_str(ws.cell(1, 11).value, "Post Office")          # K1: bank

    # H2: interest payout type (always "Annually" for PPF)
    sip_frequency = _to_str(ws.cell(2, 11).value, "monthly")     # K2: sip_frequency

    rate_decimal = _to_float(ws.cell(3, 2).value, 0)             # B3: rate as decimal
    sip_amount = _to_float(ws.cell(3, 8).value, 0)               # H3: SIP amount
    account_number = _to_str(ws.cell(3, 11).value)               # K3: account number

    sip_end_date_raw = ws.cell(4, 2).value                        # B4: sip end date
    remarks = _to_str(ws.cell(4, 5).value)                        # E4: remarks

    wb.close()

    # -- Convert & derive --
    start_dt = _to_date(start_date_raw) or date.today()
    rate_decimal = float(rate_decimal)
    sip_amount = float(sip_amount)
    maturity_years = float(maturity_years)
    tenure_months = int(maturity_years * 12)
    rate_pct = round(rate_decimal * 100, 4) if rate_decimal < 1 else round(rate_decimal, 4)
    rate_for_calc = rate_decimal if rate_decimal < 1 else rate_decimal / 100

    end_dt = start_dt + relativedelta(months=tenure_months)

    sip_end_dt = _to_date(sip_end_date_raw)
    sip_end_str = sip_end_dt.strftime("%Y-%m-%d") if sip_end_dt else None

    sip_interval = _sip_freq_to_months(sip_frequency)

    # -- Generate monthly installments --
    today = date.today()
    installments = []
    running_balance = 0.0
    total_deposited = 0.0
    total_interest_earned = 0.0
    total_interest_projected = 0.0
    cumulative_interest = 0.0

    lockin_months = int(maturity_years) * 12   # typically 180 (15 years)
    partial_months = 7 * 12                     # partial withdrawal from year 7 (month 84)

    for m in range(1, tenure_months + 1):
        inst_date = start_dt + relativedelta(months=m - 1)
        is_past = inst_date <= today

        # SIP deposit: occurs on months aligned to sip_interval (month 1, 1+interval, ...)
        invested = 0.0
        sip_active = sip_amount > 0
        if sip_end_dt and inst_date > sip_end_dt:
            sip_active = False

        if sip_active and ((m - 1) % sip_interval == 0):
            invested = sip_amount

        running_balance += invested
        total_deposited += invested

        # Annual compounding: interest credited every 12 months from start
        is_compound_month = (m % 12 == 0)
        interest = 0.0
        if is_compound_month:
            interest = round(running_balance * rate_for_calc, 2)
            running_balance += interest
            cumulative_interest += interest

        if is_past:
            total_interest_earned += interest
        else:
            total_interest_projected += interest

        # Lock-in status for this month
        if m > lockin_months:
            lock_status = "free"
        elif m > partial_months:
            lock_status = "partial"
        else:
            lock_status = "locked"

        installments.append({
            "month": m,
            "date": inst_date.strftime("%Y-%m-%d"),
            "amount_invested": round(invested, 2),
            "interest_earned": round(interest, 2) if is_past else 0.0,
            "interest_projected": round(interest, 2) if not is_past else 0.0,
            "cumulative_interest": round(cumulative_interest, 2),
            "cumulative_amount": round(running_balance, 2),
            "is_compound_month": is_compound_month,
            "is_past": is_past,
            "lock_status": lock_status,
        })

    # -- Totals --
    maturity_amount = round(running_balance, 2)
    status = "Matured" if end_dt <= today else "Active"
    days_to_maturity = max(0, (end_dt - today).days)

    installments_paid = sum(1 for i in installments if i["is_past"])

    return {
        "id": _gen_ppf_id(name),
        "name": name,
        "account_name": name,
        "bank": bank,
        "account_number": account_number,
        "interest_rate": rate_pct,
        "interest_payout": "Annually",
        "sip_amount": round(sip_amount, 2),
        "sip_frequency": sip_frequency,
        "sip_end_date": sip_end_str,
        "tenure_years": int(maturity_years),
        "tenure_months": tenure_months,
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "maturity_date": end_dt.strftime("%Y-%m-%d"),
        "maturity_amount": maturity_amount,
        "total_deposited": round(total_deposited, 2),
        "total_interest_accrued": round(total_interest_earned, 2),
        "interest_earned": round(total_interest_earned, 2),
        "interest_projected": round(total_interest_projected, 2),
        "status": status,
        "days_to_maturity": days_to_maturity,
        "source": "xlsx",
        "remarks": remarks,
        "installments": installments,
        "installments_paid": installments_paid,
        "installments_total": len(installments),
    }


def _parse_all_xlsx() -> list:
    """Parse all xlsx files from dumps/PPF/ directory."""
    results = []
    if not PPF_DIR.exists():
        return results

    for f in sorted(PPF_DIR.glob("*.xlsx")):
        if f.name.startswith("~$"):
            continue
        try:
            parsed = _parse_ppf_xlsx(f)
            results.append(parsed)
        except Exception as e:
            print(f"[PPF] Error parsing {f.name}: {e}")
    return results


# ===================================================================
#  XLSX CREATION (for new entries from UI)
# ===================================================================

def _create_ppf_xlsx(name: str, bank: str, sip_amount: float,
                     rate_pct: float, maturity_years: int,
                     start_date: str, sip_frequency: str = "monthly",
                     sip_end_date: str = None, account_number: str = "",
                     remarks: str = "", overwrite: bool = False):
    """Create an xlsx file following the FD template structure for PPF.

    If overwrite=False (default for new entries) and a file with the same name
    already exists, a numeric suffix is appended to avoid clobbering.
    If overwrite=True (used by update/contribution), the existing file is replaced.
    """
    PPF_DIR.mkdir(parents=True, exist_ok=True)
    filepath = PPF_DIR / f"{name}.xlsx"

    if not overwrite:
        # Avoid overwriting existing files -- append suffix
        counter = 2
        while filepath.exists():
            filepath = PPF_DIR / f"{name} ({counter}).xlsx"
            counter += 1
        name = filepath.stem

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Index"

    rate_dec = rate_pct / 100
    tenure_months = maturity_years * 12
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = start_dt + relativedelta(months=tenure_months)

    sip_interval = _sip_freq_to_months(sip_frequency)

    sip_end_dt = None
    if sip_end_date:
        try:
            sip_end_dt = datetime.strptime(sip_end_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    # -- Compute installments for xlsx data rows --
    running_balance = 0.0
    total_deposited = 0.0
    cumulative_interest = 0.0
    row_data = []

    for m in range(1, tenure_months + 1):
        inst_date = start_dt + relativedelta(months=m - 1)

        invested = 0.0
        sip_active = sip_amount > 0
        if sip_end_dt and inst_date > sip_end_dt:
            sip_active = False
        if sip_active and ((m - 1) % sip_interval == 0):
            invested = sip_amount

        running_balance += invested
        total_deposited += invested

        is_compound_month = (m % 12 == 0)
        interest = 0.0
        if is_compound_month:
            interest = round(running_balance * rate_dec, 2)
            running_balance += interest
            cumulative_interest += interest

        row_data.append((m, inst_date, invested, interest))

    maturity_amount = round(running_balance, 2)

    # -- Row 1: start_date, total_invested, maturity_years, bank --
    ws.cell(1, 2, start_dt)                     # B1
    ws.cell(1, 5, total_deposited)              # E1
    ws.cell(1, 8, float(maturity_years))        # H1
    ws.cell(1, 11, bank)                        # K1

    # -- Row 2: end_date, interest_earned, "Annually", sip_frequency --
    ws.cell(2, 2, end_dt)                       # B2
    ws.cell(2, 5, cumulative_interest)          # E2
    ws.cell(2, 8, "Annually")                   # H2
    ws.cell(2, 11, sip_frequency)               # K2

    # -- Row 3: rate_decimal, maturity_amount, sip_amount, account_number --
    ws.cell(3, 2, rate_dec)                     # B3
    ws.cell(3, 5, maturity_amount)              # E3
    ws.cell(3, 8, sip_amount)                   # H3
    ws.cell(3, 11, account_number)              # K3

    # -- Row 4: sip_end_date, remarks (extra PPF fields) --
    if sip_end_dt:
        ws.cell(4, 2, sip_end_dt)              # B4
    ws.cell(4, 5, remarks)                      # E4

    # -- Row 5: Headers --
    headers = ['S.No', '', '#', 'Date', 'Amount Invested', 'Interest Earned', 'Interest to be Earned']
    for i, h in enumerate(headers, 1):
        ws.cell(5, i, h)

    # -- Row 6+: Monthly data rows --
    for m, inst_date, invested, interest in row_data:
        row = m + 5
        ws.cell(row, 1, m)
        ws.cell(row, 3, m)
        ws.cell(row, 4, inst_date)
        ws.cell(row, 5, invested)
        ws.cell(row, 6, interest)
        ws.cell(row, 7, interest)

    wb.save(str(filepath))
    wb.close()
    return filepath


# ===================================================================
#  LEGACY JSON MIGRATION
# ===================================================================

def _migrate_json_to_xlsx():
    """One-time migration: convert legacy ppf_accounts.json to xlsx files."""
    if not PPF_JSON_FILE.exists():
        return
    try:
        with open(PPF_JSON_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, list) or len(data) == 0:
            return
        PPF_DIR.mkdir(parents=True, exist_ok=True)
        for account in data:
            name = account.get("account_name", "PPF Account")
            bank = account.get("bank", "Post Office")
            rate = account.get("interest_rate", PPF_DEFAULT_RATE)
            tenure = account.get("tenure_years", PPF_TENURE_YEARS)
            start_date = account.get("start_date", date.today().strftime("%Y-%m-%d"))
            sip_amount = account.get("sip_amount", 0) or 0
            sip_frequency = account.get("sip_frequency", "monthly")
            sip_end_date = account.get("sip_end_date")
            account_number = account.get("account_number", "")
            remarks_val = account.get("remarks", "")

            # If there were one-time contributions in old format but no sip,
            # sum them into the sip_amount as a yearly equivalent
            contributions = account.get("contributions", [])
            if sip_amount == 0 and contributions:
                total_contrib = sum(c.get("amount", 0) for c in contributions)
                # Treat total contributions as yearly deposit
                years_elapsed = max(1, (date.today() - datetime.strptime(start_date, "%Y-%m-%d").date()).days // 365)
                sip_amount = round(total_contrib / years_elapsed / 12, 2)  # monthly equivalent
                sip_frequency = "monthly"

            _create_ppf_xlsx(
                name=name,
                bank=bank,
                sip_amount=sip_amount,
                rate_pct=rate,
                maturity_years=tenure,
                start_date=start_date,
                sip_frequency=sip_frequency,
                sip_end_date=sip_end_date,
                account_number=account_number,
                remarks=remarks_val,
                overwrite=True,
            )
            print(f"[PPF] Migrated '{name}' to xlsx")

        # Rename old file so migration doesn't run again
        PPF_JSON_FILE.rename(PPF_JSON_FILE.with_suffix(".json.bak"))
        print("[PPF] Migration complete, renamed old JSON to .json.bak")
    except Exception as e:
        print(f"[PPF] Migration error: {e}")


def _migrate_old_xlsx():
    """Migrate old-format PPF xlsx files (with separate Index/Contributions sheets)
    to the new FD-style format. Detects old format by checking for 'Account Name' in A1."""
    if not PPF_DIR.exists():
        return
    for f in sorted(PPF_DIR.glob("*.xlsx")):
        if f.name.startswith("~$"):
            continue
        try:
            wb = openpyxl.load_workbook(str(f), data_only=True)
            ws = wb["Index"]
            a1_val = _to_str(ws.cell(1, 1).value)
            # Old format has "Account Name" label in A1
            if a1_val != "Account Name":
                wb.close()
                continue

            # Read old-format metadata
            account_name = _to_str(ws.cell(1, 2).value, "PPF Account")
            bank = _to_str(ws.cell(1, 4).value, "Post Office")
            account_number = _to_str(ws.cell(1, 6).value)
            interest_rate = _to_float(ws.cell(1, 8).value, PPF_DEFAULT_RATE)

            start_date = _to_str(ws.cell(2, 2).value)
            tenure_years = int(_to_float(ws.cell(2, 4).value, PPF_TENURE_YEARS))
            sip_amount = _to_float(ws.cell(2, 8).value, 0)

            sip_frequency = _to_str(ws.cell(3, 2).value, "monthly")
            sip_end_date = _to_str(ws.cell(3, 4).value) or None
            remarks_val = _to_str(ws.cell(3, 6).value)

            wb.close()

            print(f"[PPF] Migrating old-format xlsx: {f.name}")

            # Remove old file and create new-format xlsx
            f.unlink()

            _create_ppf_xlsx(
                name=account_name,
                bank=bank,
                sip_amount=sip_amount,
                rate_pct=interest_rate,
                maturity_years=tenure_years,
                start_date=start_date,
                sip_frequency=sip_frequency,
                sip_end_date=sip_end_date if sip_end_date else None,
                account_number=account_number,
                remarks=remarks_val,
                overwrite=True,
            )
            print(f"[PPF] Migrated '{account_name}' to new xlsx format")

        except Exception as e:
            print(f"[PPF] Error migrating {f.name}: {e}")


# ===================================================================
#  PUBLIC API
# ===================================================================

def get_all() -> list:
    """Return all PPF accounts with computed monthly installments."""
    with _lock:
        _migrate_json_to_xlsx()
        _migrate_old_xlsx()
        items = _parse_all_xlsx()

    today = date.today()
    for item in items:
        try:
            start = datetime.strptime(item["start_date"], "%Y-%m-%d").date()
            item["years_completed"] = max(0, (today - start).days // 365)
        except (ValueError, KeyError):
            item["years_completed"] = 0

        # -- Withdrawal eligibility --
        yc = item["years_completed"]
        installments = item.get("installments", [])

        if yc >= item.get("tenure_years", 15):
            # Matured: full balance withdrawable
            # Current balance = deposits + interest earned so far
            past_insts = [i for i in installments if i["is_past"]]
            current_balance = (
                sum(i["amount_invested"] for i in past_insts)
                + sum(i["interest_earned"] for i in past_insts)
            )
            item["withdrawable_amount"] = round(current_balance, 2)
            item["withdrawal_status"] = "full"
            item["withdrawal_note"] = "Fully withdrawable — lock-in complete"
        elif yc >= 7:
            # Partial withdrawal from 7th FY: up to 50% of balance
            # at end of 4th preceding financial year
            preceding_year = yc - 4
            # Balance at end of preceding_year = sum of invested + interest
            # for first (preceding_year * 12) months
            months_cutoff = preceding_year * 12
            balance_at_cutoff = 0.0
            for inst in installments[:months_cutoff]:
                balance_at_cutoff += inst.get("amount_invested", 0)
                balance_at_cutoff += inst.get("interest_earned", 0)
            withdrawable = round(balance_at_cutoff * 0.5, 2)
            item["withdrawable_amount"] = withdrawable
            item["withdrawal_status"] = "partial"
            item["withdrawal_note"] = (
                f"Partial withdrawal eligible — up to 50% of balance "
                f"at end of year {preceding_year}"
            )
        else:
            # Locked
            unlock_year = 7
            unlock_date = datetime.strptime(item["start_date"], "%Y-%m-%d").date() + relativedelta(years=unlock_year)
            item["withdrawable_amount"] = 0
            item["withdrawal_status"] = "locked"
            item["withdrawal_note"] = (
                f"Locked — partial withdrawal from year 7 "
                f"({unlock_date.strftime('%b %Y')})"
            )

    return items


def get_dashboard() -> dict:
    """Aggregate PPF summary for dashboard."""
    items = get_all()
    active = [i for i in items if i.get("status") == "Active"]

    return {
        "total_deposited": round(sum(i.get("total_deposited", 0) for i in active), 2),
        "total_interest": round(sum(i.get("total_interest_accrued", 0) for i in active), 2),
        "current_balance": round(sum(i.get("maturity_amount", 0) for i in active), 2),
        "active_count": len(active),
        "total_count": len(items),
    }


def add(data: dict) -> dict:
    """Add a new PPF account -- creates xlsx file."""
    account_name = data.get("account_name", "PPF Account")
    bank = data.get("bank", "Post Office")
    rate = data.get("interest_rate", PPF_DEFAULT_RATE)
    tenure = data.get("tenure_years", PPF_TENURE_YEARS)
    start_date = data["start_date"]
    sip_amount = data.get("sip_amount", 0) or 0
    sip_frequency = data.get("sip_frequency", "monthly")
    sip_end_date = data.get("sip_end_date")
    account_number = data.get("account_number", "")
    remarks_val = data.get("remarks", "")

    # If one-time payment, deposit once on start date then stop
    payment_type = data.get("payment_type", "sip")
    initial_amount = data.get("amount_added", 0) or 0
    if payment_type == "one_time" and initial_amount > 0:
        sip_amount = initial_amount
        sip_frequency = "yearly"
        sip_end_date = start_date  # only deposit on month 1, then stop

    name = account_name

    filepath = _create_ppf_xlsx(
        name=name,
        bank=bank,
        sip_amount=sip_amount,
        rate_pct=rate,
        maturity_years=tenure,
        start_date=start_date,
        sip_frequency=sip_frequency,
        sip_end_date=sip_end_date,
        account_number=account_number,
        remarks=remarks_val,
    )

    # Return the freshly parsed result
    return _parse_ppf_xlsx(filepath)


def update(ppf_id: str, data: dict) -> dict:
    """Update an existing PPF account -- rewrites xlsx file."""
    with _lock:
        filepath = _find_xlsx(ppf_id)
        if filepath is None:
            raise ValueError(f"PPF account {ppf_id} not found")

        # Parse current values
        current = _parse_ppf_xlsx(filepath)
        old_name = current["name"]

        # Apply updates
        account_name = data.get("account_name", current["account_name"])
        bank = data.get("bank", current["bank"])
        rate = data.get("interest_rate", current["interest_rate"])
        tenure = data.get("tenure_years", current["tenure_years"])
        start_date = data.get("start_date", current["start_date"])
        sip_amount = data.get("sip_amount", current["sip_amount"])
        sip_frequency = data.get("sip_frequency", current["sip_frequency"])
        sip_end_date = data.get("sip_end_date", current.get("sip_end_date"))
        account_number = data.get("account_number", current["account_number"])
        remarks_val = data.get("remarks", current["remarks"])

        # Handle payment_type toggle from edit form
        payment_type = data.get("payment_type")
        if payment_type == "one_time":
            initial_amount = data.get("amount_added", 0) or 0
            if initial_amount > 0:
                sip_amount = initial_amount
                sip_frequency = "yearly"
                sip_end_date = start_date  # single deposit on start date
        elif payment_type == "sip":
            sip_end_date = data.get("sip_end_date") or None

        # If name changed, delete old file
        new_name = account_name
        if new_name != old_name:
            filepath.unlink()

        _create_ppf_xlsx(
            name=new_name,
            bank=bank,
            sip_amount=sip_amount,
            rate_pct=rate,
            maturity_years=tenure,
            start_date=start_date,
            sip_frequency=sip_frequency,
            sip_end_date=sip_end_date,
            account_number=account_number,
            remarks=remarks_val,
            overwrite=True,
        )

        new_filepath = PPF_DIR / f"{new_name}.xlsx"
        return _parse_ppf_xlsx(new_filepath)


def delete(ppf_id: str) -> dict:
    """Delete a PPF account -- removes xlsx file."""
    with _lock:
        filepath = _find_xlsx(ppf_id)
        if filepath is None:
            raise ValueError(f"PPF account {ppf_id} not found")

        account = _parse_ppf_xlsx(filepath)
        filepath.unlink()
        return {"message": f"PPF {ppf_id} deleted", "item": account}


def add_contribution(ppf_id: str, contribution: dict) -> dict:
    """Add a contribution to a PPF account.

    For the new format, this adjusts the SIP amount or adds a lump-sum
    by rewriting the xlsx. The contribution is validated against yearly limits.
    """
    with _lock:
        filepath = _find_xlsx(ppf_id)
        if filepath is None:
            raise ValueError(f"PPF account {ppf_id} not found")

        account = _parse_ppf_xlsx(filepath)

        amount = contribution.get("amount", 0)
        contrib_date = contribution.get("date", datetime.now().strftime("%Y-%m-%d"))

        try:
            c_date = datetime.strptime(contrib_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Invalid date format")

        # Validate yearly limit by checking projected deposits for this FY
        fy = _get_financial_year(c_date)
        sip_amount = account["sip_amount"]
        sip_freq = account["sip_frequency"]
        sip_interval = _sip_freq_to_months(sip_freq)

        # Calculate deposits already scheduled for this FY
        start_dt = datetime.strptime(account["start_date"], "%Y-%m-%d").date()
        fy_start_year = c_date.year if c_date.month >= 4 else c_date.year - 1
        fy_start = date(fy_start_year, 4, 1)
        fy_end = date(fy_start_year + 1, 3, 31)

        # Sum up SIP deposits in this FY from installment schedule
        fy_deposits = sum(
            i["amount_invested"] for i in account["installments"]
            if fy_start.strftime("%Y-%m-%d") <= i["date"] <= fy_end.strftime("%Y-%m-%d")
        )

        if fy_deposits + amount > PPF_YEARLY_MAX:
            raise ValueError(
                f"Exceeds yearly limit of Rs.{PPF_YEARLY_MAX:,.0f}. "
                f"Already deposited/projected Rs.{fy_deposits:,.0f} in FY {fy}"
            )

        # Store contribution in remarks for record keeping
        existing_remarks = account.get("remarks", "")
        contrib_note = f"[{contrib_date}: +{amount}]"
        if existing_remarks:
            new_remarks = f"{existing_remarks} {contrib_note}"
        else:
            new_remarks = contrib_note

        _create_ppf_xlsx(
            name=account["name"],
            bank=account["bank"],
            sip_amount=sip_amount,
            rate_pct=account["interest_rate"],
            maturity_years=account["tenure_years"],
            start_date=account["start_date"],
            sip_frequency=sip_freq,
            sip_end_date=account.get("sip_end_date"),
            account_number=account["account_number"],
            remarks=new_remarks,
            overwrite=True,
        )

        return _parse_ppf_xlsx(filepath)


# ===================================================================
#  INTERNAL HELPERS (file lookup)
# ===================================================================

def _find_xlsx(ppf_id: str) -> Path | None:
    """Find the xlsx file for a given PPF ID (based on filename hash)."""
    if not PPF_DIR.exists():
        return None
    for f in PPF_DIR.glob("*.xlsx"):
        if f.name.startswith("~$"):
            continue
        if _gen_ppf_id(f.stem) == ppf_id:
            return f
    return None
