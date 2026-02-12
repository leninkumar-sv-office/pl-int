"""
SBICAP Securities Contract Note PDF Parser.

Parses contract notes from SBICAP Securities to extract buy/sell transactions.

Supports two PDF formats:
  A. "Equity Segment" format — transaction data between "Equity Segment :" header
     and "Obligation details :" boundary (tried FIRST)
  B. "Annexure B" format — Scrip Wise Summary (legacy fallback)

Effective buy price  = Net Total (After Levies) / Bought Qty
Effective sell price = |Net Total (After Levies)| / Sold Qty

This ensures the per-share price includes all charges: brokerage, GST, STT,
exchange charges, SEBI fees, stamp duty, and other statutory levies.

Extraction strategies (tried in order):
  1. pdfplumber direct table extraction (most reliable for structured PDFs)
  2. Text parsing with layout mode (pdfplumber layout=True or pdftotext -layout)
  3. Text parsing without layout mode (pdfplumber plain extract_text)

Each strategy tries "Equity Segment" section first, then "Annexure B" as fallback.
"""

import os
import re
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# Symbol resolution uses the shared symbol_resolver module
# (no hardcoded maps — all lookups go through Zerodha + NSE dynamically)
from . import symbol_resolver as _sym_resolver


# ═══════════════════════════════════════════════════════════
#  SHARED HELPERS
# ═══════════════════════════════════════════════════════════

# Flexible pattern: allows optional spaces around hyphens in "-Cash-"
_SEC_PATTERN = re.compile(r'(.+?)\s*-\s*Cash\s*-\s*((?:INE|INF)\w+)')

# Equity Segment pattern: line starts with ISIN, followed by company name, then numbers
# e.g. "INE783E01023       HIGH ENERGY            10.00      560.975..."
_EQ_SEG_PATTERN = re.compile(r'^((?:INE|INF)\w{9,})\s+(.+?)\s{2,}([\d.]+)')

# Number pattern that handles commas (e.g., 24,550.00)
_NUM_PATTERN = re.compile(r'-?[\d,]+\.[\d]+|-?[\d,]+')


def _resolve_symbol(isin: str, sec_name: str,
                    exchange_map: Dict[str, str]) -> Tuple[str, str, str]:
    """Resolve symbol, exchange, and company name from ISIN.

    Uses the shared symbol_resolver module (call _sym_resolver.ensure_loaded()
    once before any batch of calls to this function).

    Lookup order:
      1. ISIN → symbol from NSE equity list (primary, has ISIN column)
      2. Name → symbol from Zerodha instruments (secondary, fuzzy name match)
      3. Fallback: derive from security name heuristic
    """
    # 1. ISIN map (NSE equity list — has ISIN NUMBER + SYMBOL)
    isin_info = _sym_resolver.resolve_by_isin(isin)
    if isin_info:
        symbol, default_exchange, company_name = isin_info
        exchange = exchange_map.get(isin, default_exchange)
        return symbol, exchange, company_name

    # 2. Zerodha name → symbol fallback
    zerodha_symbol = _sym_resolver.resolve_by_name(sec_name)
    if zerodha_symbol:
        exchange = exchange_map.get(isin, "NSE")
        print(f"[ContractNote] Resolved '{sec_name}' → {zerodha_symbol} via Zerodha name match")
        return zerodha_symbol, exchange, sec_name.title()

    # 3. Last resort: derive from security name
    symbol = _sym_resolver.derive_symbol(sec_name)
    default_exchange = "NSE"
    company_name = sec_name.title()
    exchange = exchange_map.get(isin, default_exchange)
    print(f"[ContractNote] WARNING: Could not resolve ISIN {isin}, derived symbol: {symbol}")
    return symbol, exchange, company_name


def _build_transaction(action: str, symbol: str, exchange: str,
                       company_name: str, isin: str, quantity: int,
                       avg_rate: float, net_after: float,
                       brokerage: float, gst: float, stt: float,
                       other_levies: float, trade_date: str) -> dict:
    """Build a standardized transaction dict."""
    if action == "Buy":
        effective_price = net_after / quantity
        net_val = round(net_after, 2)
    else:  # Sell
        effective_price = abs(net_after) / quantity
        net_val = round(abs(net_after), 2)

    add_charges = brokerage + gst + other_levies
    return {
        "action": action,
        "symbol": symbol,
        "exchange": exchange,
        "name": company_name,
        "isin": isin,
        "quantity": quantity,
        "wap": avg_rate,
        "effective_price": round(effective_price, 4),
        "net_total_after_levies": net_val,
        "brokerage": round(brokerage, 4),
        "gst": round(gst, 4),
        "stt": round(stt, 4),
        "other_levies": round(other_levies, 4),
        "add_charges": round(add_charges, 4),
        "trade_date": trade_date,
    }


def _parse_nums_from_row(numbers: list, sec_name: str, isin: str,
                         exchange_map: Dict[str, str],
                         trade_date: str,
                         transactions: list) -> bool:
    """Parse 10 numeric fields into Buy/Sell transactions. Returns True on success."""
    try:
        bought_qty = int(float(numbers[0]))
        sold_qty = int(float(numbers[1]))
        avg_rate = abs(float(numbers[2]))
        # numbers[3] = gross_total (unused)
        brokerage = float(numbers[4])
        # numbers[5] = net_before (unused)
        gst = float(numbers[6])
        stt = float(numbers[7])
        other_levies = float(numbers[8])
        net_after = float(numbers[9])
    except (ValueError, IndexError) as e:
        print(f"[ContractNote] Parse error for {sec_name}: {e}")
        return False

    symbol, exchange, company_name = _resolve_symbol(isin, sec_name, exchange_map)

    if bought_qty > 0:
        transactions.append(_build_transaction(
            "Buy", symbol, exchange, company_name, isin, bought_qty,
            avg_rate, net_after, brokerage, gst, stt, other_levies, trade_date,
        ))
    if sold_qty > 0:
        transactions.append(_build_transaction(
            "Sell", symbol, exchange, company_name, isin, sold_qty,
            avg_rate, net_after, brokerage, gst, stt, other_levies, trade_date,
        ))
    return True


def _parse_equity_segment_row(isin: str, sec_name: str, numbers: List[float],
                               exchange_map: Dict[str, str],
                               trade_date: str,
                               transactions: list) -> bool:
    """Parse an Equity Segment row into Buy/Sell transactions.

    Equity Segment columns (14 numbers):
      BUY_QTY | WAP | BROKERAGE/SHARE | WAP_AFTER_BROK | TOTAL_BUY_VALUE |
      SELL_QTY | WAP | BROKERAGE/SHARE | WAP_AFTER_BROK | TOTAL_SELL_VALUE |
      NET_QTY | NET_OBLIGATION

    Note: Equity Segment does NOT break down GST/STT/other levies per-scrip.
    Those are only available as totals in the Obligation Details section.
    We use WAP as avg_rate and TOTAL_VALUE as net_after (value after brokerage,
    before exchange levies). The effective_price is TOTAL_VALUE / QTY.
    """
    try:
        buy_qty = int(float(numbers[0]))
        buy_wap = abs(float(numbers[1]))
        buy_brokerage_per_share = abs(float(numbers[2]))
        # numbers[3] = WAP after brokerage (unused — we compute effective_price)
        buy_total_value = abs(float(numbers[4]))

        sell_qty = int(float(numbers[5]))
        sell_wap = abs(float(numbers[6]))
        sell_brokerage_per_share = abs(float(numbers[7]))
        # numbers[8] = WAP after brokerage for sell (unused)
        sell_total_value = abs(float(numbers[9]))

        # numbers[10] = net_qty, numbers[11] = net_obligation (unused)
    except (ValueError, IndexError) as e:
        print(f"[ContractNote] Equity Segment parse error for {sec_name}: {e} | nums={numbers}")
        return False

    symbol, exchange, company_name = _resolve_symbol(isin, sec_name, exchange_map)

    if buy_qty > 0:
        brokerage = buy_brokerage_per_share * buy_qty
        transactions.append(_build_transaction(
            "Buy", symbol, exchange, company_name, isin, buy_qty,
            buy_wap, buy_total_value, brokerage,
            gst=0.0, stt=0.0, other_levies=0.0, trade_date=trade_date,
        ))
    if sell_qty > 0:
        brokerage = sell_brokerage_per_share * sell_qty
        transactions.append(_build_transaction(
            "Sell", symbol, exchange, company_name, isin, sell_qty,
            sell_wap, sell_total_value, brokerage,
            gst=0.0, stt=0.0, other_levies=0.0, trade_date=trade_date,
        ))
    return True


# ═══════════════════════════════════════════════════════════
#  PDF TEXT EXTRACTION
# ═══════════════════════════════════════════════════════════

def extract_text_from_pdf(pdf_path: str, layout: bool = True) -> str:
    """Extract text from PDF using pdfplumber (primary) or pdftotext CLI (fallback).

    Args:
        pdf_path: Path to PDF file.
        layout: If True, use layout-aware extraction that preserves column positions.
    """
    # Primary: pdfplumber (pure Python, works everywhere)
    try:
        import pdfplumber
        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                if layout:
                    text = page.extract_text(layout=True)
                else:
                    text = page.extract_text()
                if text:
                    pages_text.append(text)
        if pages_text:
            return "\n".join(pages_text)
    except ImportError:
        pass
    except Exception as e:
        print(f"[ContractNote] pdfplumber failed (layout={layout}): {e}")

    # Fallback: pdftotext CLI (requires poppler-utils), only for layout mode
    if layout:
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", pdf_path, "-"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[ContractNote] pdftotext CLI failed: {e}")

    raise RuntimeError(
        "PDF text extraction failed. Install pdfplumber (pip install pdfplumber) "
        "or poppler-utils (for pdftotext CLI)."
    )


# ═══════════════════════════════════════════════════════════
#  TRADE DATE EXTRACTION
# ═══════════════════════════════════════════════════════════

def _extract_trade_date(text: str) -> Optional[str]:
    """Extract trade date from the contract note header.

    Looks for 'TRADE DATE' followed by a date like '09-FEB-26'.
    Returns date in YYYY-MM-DD format.
    """
    match = re.search(r'TRADE\s+DATE\s+(\d{2}-[A-Z]{3}-\d{2,4})', text)
    if match:
        date_str = match.group(1)
        for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d-%B-%y", "%d-%B-%Y"):
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def _extract_contract_no(text: str) -> Optional[str]:
    """Extract contract note number."""
    match = re.search(r'CONTRACT\s+NOTE\s+NO\.?\s+(\d+)', text)
    if match:
        return match.group(1)
    return None


# ═══════════════════════════════════════════════════════════
#  EXCHANGE DETECTION (from Annexure A)
# ═══════════════════════════════════════════════════════════

def _extract_exchange_map(text: str) -> Dict[str, str]:
    """Parse Annexure A to determine BSE vs NSE for each ISIN.

    Returns {isin: exchange} mapping.
    Default is NSE for anything not found in BSEM section.
    """
    exchange_map: Dict[str, str] = {}
    current_exchange = "NSE"

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "BSEM":
            current_exchange = "BSE"
            continue
        if stripped == "NSEM":
            current_exchange = "NSE"
            continue
        isin_match = re.search(r'(INE\w{9}|INF\w{9})', line)
        if isin_match:
            isin = isin_match.group(1)
            if current_exchange == "BSE":
                exchange_map[isin] = "BSE"

    return exchange_map


# ═══════════════════════════════════════════════════════════
#  STRATEGY 1: PDFPLUMBER TABLE EXTRACTION
# ═══════════════════════════════════════════════════════════

def _parse_pdfplumber_tables(pdf_path: str, trade_date: str,
                              exchange_map: Dict[str, str]) -> List[dict]:
    """Parse transaction tables using pdfplumber's direct table extraction API.

    This is the most reliable strategy because it reads the underlying
    PDF table structure rather than relying on text layout alignment.

    Tries "Equity Segment" section first, then falls back to "Annexure B".
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    transactions: List[dict] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            in_section = False
            section_type = None  # 'equity_segment' or 'annexure_b'

            for page in pdf.pages:
                page_text = (page.extract_text() or "").upper()

                # Detect section start — prefer Equity Segment over Annexure B
                if not in_section:
                    if "EQUITY SEGMENT" in page_text:
                        in_section = True
                        section_type = "equity_segment"
                        print("[ContractNote] Table extraction: found 'Equity Segment' section")
                    elif "ANNEXURE B" in page_text:
                        in_section = True
                        section_type = "annexure_b"
                        print("[ContractNote] Table extraction: found 'Annexure B' section")
                else:
                    # If we were in equity_segment and this page has Equity Segment, keep going
                    if section_type == "equity_segment" and "EQUITY SEGMENT" in page_text:
                        pass  # still in section
                    elif section_type == "annexure_b" and "ANNEXURE B" in page_text:
                        pass  # still in section

                if not in_section:
                    continue

                # Stop conditions based on section type
                if section_type == "equity_segment":
                    if "OBLIGATION DETAILS" in page_text and "EQUITY SEGMENT" not in page_text:
                        break
                elif section_type == "annexure_b":
                    if "DESCRIPTION OF SERVICE" in page_text and "ANNEXURE B" not in page_text:
                        break

                # Try table extraction with default settings (line-based)
                tables = page.extract_tables()

                # If no tables found, try text-based strategy
                if not tables:
                    tables = page.extract_tables({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    })

                if not tables:
                    continue

                for table in tables:
                    if not table:
                        continue

                    for row in table:
                        if not row or len(row) < 3:
                            continue

                        cells = [str(c).strip() if c else "" for c in row]
                        row_text = " ".join(cells)

                        # Skip non-data rows
                        row_upper = row_text.upper()
                        if "SUB TOTAL" in row_upper:
                            continue
                        if "SEGMENT" in row_upper and "SECURITY" in row_upper:
                            continue
                        if "CGST" in row_upper or "SGST" in row_upper:
                            continue

                        # Detect ISIN and security name based on section type
                        isin = None
                        sec_name = None

                        if section_type == "equity_segment":
                            # Equity Segment: ISIN is in the first cell(s)
                            isin_match = re.search(r'((?:INE|INF)\w{9,})', row_text)
                            if not isin_match:
                                continue
                            isin = isin_match.group(1)
                            # Security name: text between ISIN and the first number
                            after_isin = row_text[isin_match.end():].strip()
                            name_part = re.split(r'\s{2,}|\s+(?=\d)', after_isin, maxsplit=1)
                            sec_name = name_part[0].strip() if name_part else ""
                            if not sec_name:
                                # Try from cells: find cell after ISIN cell
                                for ci, cell in enumerate(cells):
                                    if isin in cell and ci + 1 < len(cells):
                                        sec_name = cells[ci + 1].strip()
                                        break
                        else:
                            # Annexure B: "SecurityName - Cash - ISIN"
                            sec_match = _SEC_PATTERN.search(row_text)
                            if not sec_match:
                                continue
                            sec_name = sec_match.group(1).strip()
                            sec_name = re.sub(r'^.*?(?:Equity|EQUITY)\s*', '', sec_name).strip()
                            isin = sec_match.group(2).strip()

                        if not isin:
                            continue

                        # Extract all numbers from the row
                        nums = []
                        past_isin = False
                        for cell in cells:
                            if isin in cell:
                                past_isin = True
                                # For equity segment, ISIN cell may also have numbers — skip
                                continue
                            if not past_isin and section_type == "annexure_b":
                                continue
                            if past_isin or section_type == "equity_segment":
                                cleaned = cell.replace(",", "").replace(" ", "").strip()
                                if not cleaned:
                                    continue
                                # Skip text-only cells (security name fragments)
                                if re.match(r'^[A-Za-z()\s\-&.]+$', cleaned):
                                    continue
                                if cleaned.startswith("(") and cleaned.endswith(")"):
                                    cleaned = "-" + cleaned[1:-1]
                                try:
                                    nums.append(float(cleaned))
                                except ValueError:
                                    continue

                        # Fallback: gather all numbers from row text AFTER the ISIN
                        if len(nums) < 10 and isin:
                            isin_pos = row_text.find(isin)
                            text_after_isin = row_text[isin_pos + len(isin):] if isin_pos >= 0 else row_text
                            # Further skip past the security name (text before first number group)
                            name_skip = re.split(r'\s{2,}(?=\d)', text_after_isin, maxsplit=1)
                            numeric_text = name_skip[1] if len(name_skip) > 1 else text_after_isin
                            all_num_strs = _NUM_PATTERN.findall(numeric_text)
                            fallback_nums = []
                            for n in all_num_strs:
                                cleaned = n.replace(",", "")
                                try:
                                    fallback_nums.append(float(cleaned))
                                except ValueError:
                                    continue
                            if len(fallback_nums) >= 10:
                                nums = fallback_nums

                        # Route to the correct row parser
                        if section_type == "equity_segment":
                            if len(nums) >= 10:
                                _parse_equity_segment_row(
                                    isin, sec_name or "", nums,
                                    exchange_map, trade_date, transactions,
                                )
                        else:
                            if len(nums) < 10:
                                continue
                            numbers = [str(n) for n in nums]
                            _parse_nums_from_row(
                                numbers, sec_name or "", isin, exchange_map,
                                trade_date, transactions,
                            )

    except Exception as e:
        print(f"[ContractNote] pdfplumber table extraction error: {e}")
        import traceback
        traceback.print_exc()
        return []

    print(f"[ContractNote] Strategy 1 (table extraction, section={section_type}): {len(transactions)} transactions")
    return transactions


# ═══════════════════════════════════════════════════════════
#  STRATEGY 2 & 3: TEXT-BASED PARSING
# ═══════════════════════════════════════════════════════════

def _parse_text_section(text: str, trade_date: str,
                         exchange_map: Dict[str, str]) -> List[dict]:
    """Parse transaction data via text-based line matching.

    Tries "Equity Segment" section first, then "Annexure B" as fallback.

    Each data row contains:
      Segment | Security Description | Bought Qty | Sold Qty | Average Rate |
      Gross Total | Brokerage | Net Total(Before Levies) | GST on Brokerage |
      Total STT | Other Statutory Levies | Net Total(After Levies)

    Handles both layout-mode text (column-aligned with spaces) and
    plain-mode text (sequential reading order).
    """
    transactions: List[dict] = []

    upper_text = text.upper()

    # Try "Equity Segment" first, then "Annexure B" as fallback
    section_start = -1
    section_end_marker = None
    section_type = None

    eq_idx = upper_text.find("EQUITY SEGMENT")
    if eq_idx >= 0:
        section_start = eq_idx
        section_end_marker = "OBLIGATION DETAILS"
        section_type = "equity_segment"
        print(f"[ContractNote] Text parser: found 'Equity Segment' at pos {eq_idx}")
    else:
        ann_idx = upper_text.find("ANNEXURE B")
        if ann_idx >= 0:
            section_start = ann_idx
            section_end_marker = "DESCRIPTION OF SERVICE"
            section_type = "annexure_b"
            print(f"[ContractNote] Text parser: found 'Annexure B' at pos {ann_idx}")

    if section_start < 0:
        print("[ContractNote] Text parser: neither 'Equity Segment' nor 'Annexure B' found")
        return transactions

    section_text = text[section_start:]
    raw_lines = section_text.split("\n")
    print(f"[ContractNote] Text parser: section={section_type}, {len(raw_lines)} lines to scan")

    # ── Determine which pattern to use for line detection ──
    # Equity Segment: lines start with ISIN (e.g. "INE783E01023   HIGH ENERGY   10.00 ...")
    # Annexure B: lines have "Name - Cash - ISIN" format
    _ISIN_START_RE = re.compile(r'^\s*((?:INE|INF)\w{9,})\s+(.+)')

    def _has_data_line(line):
        """Check if a line contains a data row (ISIN-bearing) for either format."""
        if section_type == "equity_segment":
            return bool(_ISIN_START_RE.match(line))
        else:
            return bool(_SEC_PATTERN.search(line))

    # ── Merge continuation lines ──
    # Some PDF extractors split table rows across multiple lines.
    # If a line has a data pattern but < 10 numbers, and the next
    # line does NOT have its own data pattern, join them.
    merged_lines: List[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if (merged_lines
                and _has_data_line(merged_lines[-1])
                and len(_NUM_PATTERN.findall(merged_lines[-1])) < 10
                and not _has_data_line(stripped)):
            merged_lines[-1] = merged_lines[-1] + "  " + stripped
        else:
            merged_lines.append(line)

    skip_upper = {"SUB TOTAL", "CGST", "SGST", "IGST"}

    for line in merged_lines:
        line_upper = line.upper()

        # Skip non-data lines
        if any(kw in line_upper for kw in skip_upper):
            continue
        if "SEGMENT" in line_upper and "SECURITY" in line_upper:
            continue
        if "PAGE " in line_upper and " / " in line_upper:
            continue
        if "EXCHANGE-WISE" in line_upper:
            continue
        # End-of-section markers
        if section_end_marker and section_end_marker in line_upper:
            break
        if "DESCRIPTION OF SERVICE" in line_upper:
            break

        if section_type == "equity_segment":
            # Equity Segment: ISIN at start of line
            isin_match = _ISIN_START_RE.match(line)
            if not isin_match:
                continue

            isin = isin_match.group(1).strip()
            rest_after_isin = isin_match.group(2).strip()

            # Split into name part and numeric part
            # The name ends where numbers begin (2+ spaces then digits)
            name_nums = re.split(r'\s{2,}(?=\d)', rest_after_isin, maxsplit=1)
            sec_name = name_nums[0].strip() if name_nums else ""
            numeric_part = name_nums[1] if len(name_nums) > 1 else ""

            # Extract numbers ONLY from the numeric part (after the name)
            # This avoids capturing digits from the ISIN
            all_nums_raw = _NUM_PATTERN.findall(numeric_part)
            numbers = [float(n.replace(',', '')) for n in all_nums_raw]

            if len(numbers) >= 10:
                _parse_equity_segment_row(
                    isin, sec_name, numbers,
                    exchange_map, trade_date, transactions,
                )

        else:
            # Annexure B: "SecurityName - Cash - ISIN"
            sec_match = _SEC_PATTERN.search(line)
            if not sec_match:
                continue

            sec_name = sec_match.group(1).strip()
            if sec_name.upper().startswith("EQUITY"):
                sec_name = sec_name[len("Equity"):].strip()
            isin = sec_match.group(2).strip()

            rest = line[sec_match.end():]
            numbers_raw = _NUM_PATTERN.findall(rest)
            numbers = [n.replace(',', '') for n in numbers_raw]

            if len(numbers) < 10:
                all_nums = _NUM_PATTERN.findall(line)
                all_nums = [n.replace(',', '') for n in all_nums]
                if len(all_nums) >= 10 and len(numbers) < 10:
                    numbers = all_nums[-10:]

            if len(numbers) < 10:
                continue

            _parse_nums_from_row(
                numbers, sec_name, isin, exchange_map,
                trade_date, transactions,
            )

    print(f"[ContractNote] Text parser ({section_type}): {len(transactions)} transactions")
    return transactions


# ═══════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

def parse_contract_note(pdf_path: str) -> dict:
    """Parse an SBICAP Securities contract note PDF.

    Tries multiple extraction strategies:
      1. pdfplumber table extraction (most reliable)
      2. Text parsing with layout mode
      3. Text parsing without layout mode (plain reading order)

    Returns:
        {
            "trade_date": "2026-02-09",
            "contract_no": "252611665409",
            "transactions": [...],
            "summary": {"buys": 25, "sells": 3, "total": 28},
        }
    """
    # Load symbol data ONCE upfront (NSE equity list + Zerodha instruments)
    _sym_resolver.ensure_loaded()

    # Extract text with layout mode for metadata
    text = extract_text_from_pdf(pdf_path, layout=True)

    # Extract metadata (works with both layout and non-layout text)
    trade_date = _extract_trade_date(text)
    if not trade_date:
        raise ValueError("Could not extract trade date from contract note")

    contract_no = _extract_contract_no(text)
    exchange_map = _extract_exchange_map(text)

    # ── Strategy 1: pdfplumber direct table extraction ──
    print("[ContractNote] Trying Strategy 1: pdfplumber table extraction...")
    transactions = _parse_pdfplumber_tables(
        pdf_path, trade_date, exchange_map)

    # ── Strategy 2: text-based parsing with layout mode ──
    if not transactions:
        print("[ContractNote] Trying Strategy 2: layout-mode text parsing...")
        transactions = _parse_text_section(text, trade_date, exchange_map)

    # ── Strategy 3: text-based parsing without layout mode ──
    if not transactions:
        print("[ContractNote] Trying Strategy 3: plain-text parsing (no layout)...")
        try:
            plain_text = extract_text_from_pdf(pdf_path, layout=False)
            transactions = _parse_text_section(plain_text, trade_date, exchange_map)
        except Exception as e:
            print(f"[ContractNote] Plain text fallback failed: {e}")

    # ── Deduplicate transactions within same PDF ──
    # Same stock can appear in both Equity Segment tables and text fallback,
    # or pdfplumber might extract the same row from overlapping table regions.
    seen_fps: set = set()
    unique_transactions: List[dict] = []
    dups_removed = 0
    for t in transactions:
        fp = (t.get("isin", ""), t.get("action", ""), t.get("quantity", 0),
              round(t.get("wap", 0), 4))
        if fp in seen_fps:
            dups_removed += 1
            continue
        seen_fps.add(fp)
        unique_transactions.append(t)
    if dups_removed > 0:
        print(f"[ContractNote] Removed {dups_removed} duplicate transaction(s) within same PDF")
    transactions = unique_transactions

    buys = sum(1 for t in transactions if t["action"] == "Buy")
    sells = sum(1 for t in transactions if t["action"] == "Sell")

    result = {
        "trade_date": trade_date,
        "contract_no": contract_no,
        "transactions": transactions,
        "summary": {
            "buys": buys,
            "sells": sells,
            "total": buys + sells,
        },
    }

    # If all strategies failed, include debug info for troubleshooting
    if not transactions:
        upper = text.upper()
        idx = upper.find("EQUITY SEGMENT")
        if idx < 0:
            idx = upper.find("ANNEXURE B")
        if idx >= 0:
            snippet = text[idx:idx + 1500]
        else:
            snippet = "Neither 'Equity Segment' nor 'Annexure B' found in extracted text. First 1500 chars:\n" + text[:1500]

        result["_debug_text"] = snippet

        # Dump full text to temp files for manual inspection
        for debug_path in ["/tmp/contract_note_debug.txt",
                           os.path.join(os.path.dirname(__file__), "..", "..", "contract_note_debug.txt")]:
            try:
                with open(debug_path, "w") as f:
                    f.write("=== LAYOUT MODE TEXT ===\n")
                    f.write(text)
                    f.write("\n\n=== PLAIN MODE TEXT ===\n")
                    try:
                        plain = extract_text_from_pdf(pdf_path, layout=False)
                        f.write(plain)
                    except Exception:
                        f.write("(plain text extraction failed)")
                print(f"[ContractNote] Debug text saved to: {debug_path}")
            except Exception:
                pass

    return result


def parse_contract_note_from_bytes(pdf_bytes: bytes) -> dict:
    """Parse contract note from in-memory PDF bytes.

    Writes to a temp file, parses, and cleans up.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        return parse_contract_note(tmp_path)
    finally:
        os.unlink(tmp_path)
