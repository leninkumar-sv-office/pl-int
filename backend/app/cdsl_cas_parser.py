"""
CDSL CAS (Consolidated Account Statement) PDF parser for Mutual Funds.

Extracts fund sections and transaction lines from CDSL CAS PDFs
covering all AMCs (ICICI, Nippon, SBI, Tata, etc.) using pdfplumber
table extraction with text-regex fallback.
"""

import io
import re
from datetime import datetime
from typing import Optional

import pdfplumber

from .mf_xlsx_database import mf_db, _safe_float


# ── Regex patterns ────────────────────────────────────────

# AMC header: "AMC Name : ICICI Prudential Mutual Fund"
_AMC_HEADER_RE = re.compile(r"AMC\s+Name\s*:\s*(.+)", re.IGNORECASE)

# Scheme header: "9453 - ICICI Prudential India Opportunities Fund ..."
_SCHEME_HEADER_RE = re.compile(r"^(\d{3,6})\s*[-–]\s*(.+)")

# ISIN line: "ISIN : INF109KC1RH9   UCC : ..."
_ISIN_RE = re.compile(r"ISIN\s*:\s*(\S+)", re.IGNORECASE)

# Folio line: "Folio : 15877031/78" or "Folio No : 15877031/78"
_FOLIO_RE = re.compile(r"Folio(?:\s*No)?\s*:\s*(\S+)", re.IGNORECASE)

# CAS ID line: e.g. "CAS Id : AA00604621"
_CAS_ID_RE = re.compile(r"CAS\s+Id\s*:\s*(\S+)", re.IGNORECASE)

# Statement period: "Statement Period : 01-01-2026 to 31-01-2026"
_PERIOD_RE = re.compile(r"Statement\s+Period\s*:\s*(.+?)$", re.IGNORECASE | re.MULTILINE)

# Transaction line (text fallback):
# DD-MM-YYYY  Description  Amount  NAV  Price  Units  StampDuty  ...
_TX_LINE_RE = re.compile(
    r"^(\d{2}-\d{2}-\d{4})\s+"       # date DD-MM-YYYY
    r"(.+?)\s+"                        # description
    r"([\d,]+\.\d{2})\s+"             # amount
    r"([\d,]+\.\d{2,4})\s+"           # NAV
    r"([\d,]+\.\d{2,4})\s+"           # price
    r"([\d,.]+)\s+"                    # units
    r"([\d.]+)"                        # stamp duty
)

# Lines to skip in transaction tables
_SKIP_DESCRIPTIONS = {
    "opening balance", "opening bal", "closing balance", "closing bal",
    "stt", "total tax", "net assets",
}


def _parse_number(s: str) -> float:
    """Parse a number string, removing commas and whitespace."""
    if not s:
        return 0.0
    return float(s.replace(",", "").strip())


def _parse_date_ddmmyyyy(s: str) -> str:
    """Convert DD-MM-YYYY to YYYY-MM-DD."""
    try:
        return datetime.strptime(s.strip(), "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return s


def _determine_action(description: str) -> str:
    """Determine Buy/Sell from transaction description."""
    desc_upper = description.upper()
    if "REDEMPTION" in desc_upper or "SWITCH OUT" in desc_upper:
        return "Sell"
    return "Buy"


def _should_skip_row(description: str) -> bool:
    """Check if a transaction row should be skipped."""
    desc_lower = description.strip().lower()
    for skip in _SKIP_DESCRIPTIONS:
        if desc_lower.startswith(skip):
            return True
    return False


def _match_fund_code(isin: str, fund_name: str) -> Optional[str]:
    """Try to match a parsed fund's ISIN/name against existing MF database entries.

    Returns the existing fund_code (MUTF_IN:xxx) if matched, else None.
    """
    parsed_upper = fund_name.upper().strip()
    parsed_words = set(parsed_upper.replace("-", " ").split())
    significant_parsed = {w for w in parsed_words if len(w) > 2}

    if not significant_parsed:
        return None

    best_code = None
    best_overlap = 0.0

    for code, name in mf_db._name_map.items():
        name_upper = name.upper().strip()
        existing_words = set(name_upper.replace("-", " ").split())
        significant_existing = {w for w in existing_words if len(w) > 2}
        if not significant_existing:
            continue
        significant_common = significant_parsed & significant_existing
        overlap = len(significant_common) / max(len(significant_parsed), len(significant_existing))
        if overlap > best_overlap:
            best_overlap = overlap
            best_code = code

    return best_code if best_overlap >= 0.7 else None


def _check_duplicate(fund_code: str, tx_date: str, units: float, nav: float) -> bool:
    """Check if a transaction already exists in the fund's xlsx."""
    filepath = mf_db._file_map.get(fund_code)
    if not filepath or not filepath.exists():
        return False

    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, data_only=True)
        ws = wb["Trading History"]
        header_row = mf_db._find_header_row(ws)

        try:
            tx_dt = datetime.strptime(tx_date, "%Y-%m-%d").date()
        except ValueError:
            wb.close()
            return False

        for row in range(header_row + 1, (ws.max_row or 0) + 1):
            row_date = ws.cell(row, 1).value
            row_units = ws.cell(row, 4).value
            row_nav = ws.cell(row, 5).value

            if row_date is None:
                continue

            if isinstance(row_date, datetime):
                row_date = row_date.date()
            elif hasattr(row_date, "date"):
                pass
            elif isinstance(row_date, str):
                try:
                    row_date = datetime.strptime(row_date.strip(), "%Y-%m-%d").date()
                except ValueError:
                    continue
            else:
                continue

            if (row_date == tx_dt
                    and abs(_safe_float(row_units) - units) < 1e-4
                    and abs(_safe_float(row_nav) - nav) < 1e-2):
                wb.close()
                return True

        wb.close()
    except Exception:
        pass

    return False


def _extract_table_transactions(page) -> list[dict]:
    """Extract transactions from pdfplumber table structures on a page."""
    transactions = []
    tables = page.extract_tables()
    if not tables:
        return transactions

    for table in tables:
        for row in table:
            if not row or len(row) < 6:
                continue

            # Clean cells: replace None with empty string
            cells = [str(c).strip() if c else "" for c in row]

            # Must have a date in first column: DD-MM-YYYY
            date_str = cells[0]
            if not re.match(r"\d{2}-\d{2}-\d{4}", date_str):
                continue

            description = cells[1] if len(cells) > 1 else ""
            if _should_skip_row(description):
                continue

            # Try to extract numeric fields
            try:
                amount = _parse_number(cells[2]) if len(cells) > 2 and cells[2] else 0.0
                nav = _parse_number(cells[3]) if len(cells) > 3 and cells[3] else 0.0
                price = _parse_number(cells[4]) if len(cells) > 4 and cells[4] else 0.0
                units = _parse_number(cells[5]) if len(cells) > 5 and cells[5] else 0.0
                stamp_duty = _parse_number(cells[6]) if len(cells) > 6 and cells[6] else 0.0
            except (ValueError, IndexError):
                continue

            if units == 0.0 or nav == 0.0:
                continue

            transactions.append({
                "date": _parse_date_ddmmyyyy(date_str),
                "description": description,
                "action": _determine_action(description),
                "amount": amount,
                "nav": nav,
                "units": round(abs(units), 4),
                "balance_units": 0.0,
                "stamp_duty": stamp_duty,
            })

    return transactions


def _extract_text_transactions(text_lines: list[str], start_idx: int = 0) -> list[dict]:
    """Fallback: extract transactions from plain text lines using regex."""
    transactions = []

    for i in range(start_idx, len(text_lines)):
        line = text_lines[i].strip()
        if not line:
            continue

        m = _TX_LINE_RE.match(line)
        if m:
            description = m.group(2).strip()
            if _should_skip_row(description):
                continue

            date_str = _parse_date_ddmmyyyy(m.group(1))
            amount = _parse_number(m.group(3))
            nav = _parse_number(m.group(4))
            price = _parse_number(m.group(5))
            units = _parse_number(m.group(6))
            stamp_duty = _parse_number(m.group(7))

            if units == 0.0 or nav == 0.0:
                continue

            transactions.append({
                "date": date_str,
                "description": description,
                "action": _determine_action(description),
                "amount": amount,
                "nav": nav,
                "units": round(abs(units), 4),
                "balance_units": 0.0,
                "stamp_duty": stamp_duty,
            })

    return transactions


def _attach_balance_units(transactions: list[dict], text: str):
    """Try to find closing balance from text and attach to last transaction."""
    # Look for "Closing Bal" or "Closing Balance" followed by units
    m = re.search(r"Closing\s+Bal(?:ance)?\s+.*?([\d,]+\.\d{2,4})", text, re.IGNORECASE)
    if m and transactions:
        try:
            transactions[-1]["balance_units"] = round(_parse_number(m.group(1)), 4)
        except ValueError:
            pass


def parse_cdsl_cas(pdf_bytes: bytes) -> dict:
    """Parse a CDSL CAS PDF and return structured fund/transaction data.

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        dict with keys: cas_id, statement_period, source, funds, summary
    """
    pdf = pdfplumber.open(io.BytesIO(pdf_bytes))

    # ── Phase 1: Extract all text and detect MF section ──
    all_text = ""
    page_texts = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        all_text += text + "\n"
        page_texts.append(text)

    lines = all_text.split("\n")

    # Extract CAS ID
    cas_id = ""
    m = _CAS_ID_RE.search(all_text[:3000])
    if m:
        cas_id = m.group(1).strip()

    # Extract statement period
    statement_period = ""
    m = _PERIOD_RE.search(all_text[:3000])
    if m:
        statement_period = m.group(1).strip()

    # ── Phase 2: Parse fund sections ──
    funds = []
    current_amc = ""
    current_scheme_name = ""
    current_scheme_code = ""
    current_isin = ""
    current_folio = ""
    current_fund = None

    # Track which pages we've extracted tables from
    page_table_cache = {}

    def _finalize_fund():
        """Save current fund if it has transactions."""
        nonlocal current_fund
        if current_fund and current_fund["transactions"]:
            funds.append(current_fund)
        current_fund = None

    for line_idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        # ── AMC header ──
        m = _AMC_HEADER_RE.match(line)
        if m:
            _finalize_fund()
            current_amc = m.group(1).strip()
            continue

        # ── Scheme header (e.g. "9453 - ICICI Prudential ...") ──
        m = _SCHEME_HEADER_RE.match(line)
        if m:
            _finalize_fund()
            current_scheme_code = m.group(1).strip()
            current_scheme_name = m.group(2).strip()
            current_isin = ""
            current_folio = ""
            continue

        # ── ISIN line ──
        m = _ISIN_RE.search(line)
        if m and current_scheme_name:
            current_isin = m.group(1).strip()
            continue

        # ── Folio line ──
        m = _FOLIO_RE.search(line)
        if m and current_scheme_name:
            current_folio = m.group(1).strip()

            # We have all fund metadata now — create the fund entry
            # and try table extraction on relevant pages
            matched_code = _match_fund_code(current_isin, current_scheme_name)

            current_fund = {
                "fund_code": matched_code or current_isin,
                "fund_name": current_scheme_name,
                "isin": current_isin,
                "amc": current_amc,
                "scheme_code": current_scheme_code,
                "folio": current_folio,
                "is_new_fund": matched_code is None,
                "transactions": [],
            }
            continue

        # ── Transaction lines (text-based fallback) ──
        if current_fund is not None:
            m = _TX_LINE_RE.match(line)
            if m:
                description = m.group(2).strip()
                if _should_skip_row(description):
                    continue

                date_str = _parse_date_ddmmyyyy(m.group(1))
                amount = _parse_number(m.group(3))
                nav = _parse_number(m.group(4))
                price = _parse_number(m.group(5))
                units = _parse_number(m.group(6))
                stamp_duty = _parse_number(m.group(7))

                if units == 0.0 or nav == 0.0:
                    continue

                current_fund["transactions"].append({
                    "date": date_str,
                    "description": description,
                    "action": _determine_action(description),
                    "amount": amount,
                    "nav": nav,
                    "units": round(abs(units), 4),
                    "balance_units": 0.0,
                    "stamp_duty": stamp_duty,
                })
                continue

            # Check for closing balance to capture balance_units
            closing_match = re.match(
                r"(?:Closing\s+Bal(?:ance)?)\s+.*?([\d,]+\.\d{2,4})",
                line, re.IGNORECASE
            )
            if closing_match and current_fund["transactions"]:
                try:
                    current_fund["transactions"][-1]["balance_units"] = round(
                        _parse_number(closing_match.group(1)), 4
                    )
                except ValueError:
                    pass

    # Finalize last fund
    _finalize_fund()

    # ── Phase 3: If text regex found no transactions, try table extraction ──
    if not any(f["transactions"] for f in funds):
        # Reset and try table-based extraction
        funds_meta = funds[:]  # keep metadata
        funds = []

        # Re-parse to find fund sections mapped to pages
        for fund_meta in funds_meta:
            fund_meta["transactions"] = []

        # Extract tables from all pages
        all_table_txns = []
        for page_idx, page in enumerate(pdf.pages):
            table_txns = _extract_table_transactions(page)
            for tx in table_txns:
                tx["_page"] = page_idx
            all_table_txns.extend(table_txns)

        # Assign table transactions to funds based on page order
        if all_table_txns and funds_meta:
            # Simple assignment: assign all transactions to funds
            # based on text position analysis
            _assign_table_txns_to_funds(funds_meta, all_table_txns, page_texts)
            funds = [f for f in funds_meta if f["transactions"]]

    pdf.close()

    # ── Phase 4: Dedup check and fund code matching ──
    for fund in funds:
        for tx in fund["transactions"]:
            tx["isDuplicate"] = _check_duplicate(
                fund["fund_code"], tx["date"], tx["units"], tx["nav"]
            )

    # Filter out funds with no transactions
    funds = [f for f in funds if len(f["transactions"]) > 0]

    # ── Build summary ──
    total_purchases = sum(
        1 for f in funds for t in f["transactions"] if t["action"] == "Buy"
    )
    total_redemptions = sum(
        1 for f in funds for t in f["transactions"] if t["action"] == "Sell"
    )

    return {
        "cas_id": cas_id,
        "statement_period": statement_period,
        "source": "CDSL",
        "funds": funds,
        "summary": {
            "total_purchases": total_purchases,
            "total_redemptions": total_redemptions,
            "funds_count": len(funds),
        },
    }


def _assign_table_txns_to_funds(funds_meta: list, table_txns: list, page_texts: list):
    """Assign table-extracted transactions to fund metadata entries.

    Uses page text to determine which fund each transaction belongs to,
    based on the position of scheme headers in the text.
    """
    # Build a map of page → fund indices by scanning page text for scheme codes
    page_fund_map = {}
    for fi, fund in enumerate(funds_meta):
        scheme_code = fund.get("scheme_code", "")
        if not scheme_code:
            continue
        for pi, ptext in enumerate(page_texts):
            if scheme_code in ptext:
                page_fund_map[pi] = fi
                break

    # Assign each transaction to the most recent fund by page
    current_fund_idx = 0
    sorted_fund_pages = sorted(page_fund_map.items())

    for tx in table_txns:
        tx_page = tx.pop("_page", 0)
        # Find which fund this page belongs to
        for page_num, fund_idx in sorted_fund_pages:
            if tx_page >= page_num:
                current_fund_idx = fund_idx
        if current_fund_idx < len(funds_meta):
            funds_meta[current_fund_idx]["transactions"].append(tx)
