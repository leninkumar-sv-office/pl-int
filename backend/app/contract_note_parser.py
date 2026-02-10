"""
SBICAP Securities Contract Note PDF Parser.

Parses contract notes from SBICAP Securities to extract buy/sell transactions.
Uses Annexure B (Scrip Wise Summary) as the primary data source.

Effective buy price  = Net Total (After Levies) / Bought Qty
Effective sell price = |Net Total (After Levies)| / Sold Qty

This ensures the per-share price includes all charges: brokerage, GST, STT,
exchange charges, SEBI fees, stamp duty, and other statutory levies.

Extraction strategies (tried in order):
  1. pdfplumber direct table extraction (most reliable for structured PDFs)
  2. Text parsing with layout mode (pdfplumber layout=True or pdftotext -layout)
  3. Text parsing without layout mode (pdfplumber plain extract_text)
"""

import os
import re
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════
#  ISIN → NSE/BSE Symbol Mapping
# ═══════════════════════════════════════════════════════════

ISIN_MAP: Dict[str, Tuple[str, str, str]] = {
    # ISIN: (symbol, exchange, company_name)
    # ── A ──
    "INE018A01030": ("ADANIENT", "NSE", "Adani Enterprises Ltd"),
    "INE814H01029": ("ADANIPOWER", "NSE", "Adani Power Ltd"),
    "INE101I01011": ("AFCONS", "NSE", "Afcons Infrastructure Ltd"),
    "INE437A01024": ("APOLLOHOSP", "NSE", "Apollo Hospitals Enterprise Ltd"),
    "INE871C01038": ("AVANTIFEED", "NSE", "Avanti Feeds Ltd"),
    "INE04Z101016": ("AWL", "BSE", "Asian Warehousing Limited"),
    # ── B ──
    "INE05XR01022": ("BCCL", "NSE", "Bharat Coking Coal Ltd"),
    "INE397D01024": ("BHARTIARTL", "NSE", "Bharti Airtel Limited"),
    "INE050A01025": ("BBTC", "NSE", "Bombay Burmah Trading Corporation Ltd"),
    "INE522F01014": ("COALINDIA", "NSE", "Coal India Ltd"),
    "INE483A01010": ("CENTRALBK", "NSE", "Central Bank of India"),
    # ── G-H ──
    "INE158A01026": ("HEROMOTOCO", "NSE", "Hero MotoCorp Ltd"),
    # ── I ──
    "INE335Y01020": ("IRCTC", "NSE", "Indian Rail Tour Corp Ltd"),
    "INE379A01028": ("ITCHOTELS", "NSE", "ITC Hotels Ltd"),
    "INE154A01025": ("ITC", "NSE", "ITC Ltd"),
    "INE053F01010": ("IOC", "NSE", "Indian Oil Corporation Ltd"),
    # ── J ──
    "INE758E01017": ("JIOFIN", "NSE", "Jio Financial Services Ltd"),
    "INE209L01016": ("JWL", "NSE", "Jupiter Wagons Limited"),
    # ── K ──
    "INE217B01036": ("KAJARIACER", "NSE", "Kajaria Ceramics Ltd"),
    # ── L ──
    "INE324D01010": ("LGEELECTRO", "NSE", "LG Electronics India"),
    "INE0J1Y01017": ("LICI", "NSE", "Life Insurance Corp of India"),
    # ── P ──
    "INE603J01030": ("PIIND", "NSE", "PI Industries Ltd"),
    # ── R ──
    "INE415G01027": ("RVNL", "NSE", "Rail Vikas Nigam"),
    "INE0DD101019": ("RAILTEL", "NSE", "Railtel Corporation of India Ltd"),
    "INE613A01020": ("RALLIS", "NSE", "Rallis India Ltd"),
    "INE002A01018": ("RELIANCE", "NSE", "Reliance Industries Ltd"),
    "INE320J01015": ("RITES", "NSE", "Rites Ltd"),
    # ── S ──
    "INF200KA16D8": ("SETFGOLD", "NSE", "SBI ETF Gold"),
    "INE062A01020": ("SBIN", "NSE", "State Bank of India"),
    "INE123W01016": ("SBILIFE", "NSE", "SBI Life Insurance Company Ltd"),
    "INE398R01022": ("SYNGENE", "NSE", "Syngene International Ltd"),
    # ── T ──
    "INE092A01019": ("TATACHEM", "NSE", "Tata Chemicals"),
    "INE615H01020": ("TITAGARH", "NSE", "Titagarh Rail Systems Ltd"),
    "INE849A01020": ("TRENT", "NSE", "Trent"),
    "INE155A01022": ("TATAMOTORS", "NSE", "Tata Motors Ltd"),
    "INE081A01012": ("TATASTEEL", "NSE", "Tata Steel Ltd"),
}


# ═══════════════════════════════════════════════════════════
#  SHARED HELPERS
# ═══════════════════════════════════════════════════════════

# Flexible pattern: allows optional spaces around hyphens in "-Cash-"
_SEC_PATTERN = re.compile(r'(.+?)\s*-\s*Cash\s*-\s*((?:INE|INF)\w+)')

# Number pattern that handles commas (e.g., 24,550.00)
_NUM_PATTERN = re.compile(r'-?[\d,]+\.[\d]+|-?[\d,]+')


def _derive_symbol(name: str) -> str:
    """Derive a stock symbol from the contract note security name."""
    cleaned = name.upper()
    for suffix in [" LIMITED", " LTD", " ENTER. L", " CORP", " OF INDIA"]:
        cleaned = cleaned.replace(suffix, "")
    cleaned = re.sub(r'[^A-Z0-9 ]', '', cleaned).strip()
    parts = cleaned.split()
    if len(parts) == 1:
        return parts[0][:15]
    return "".join(parts)[:15]


def _resolve_symbol(isin: str, sec_name: str,
                    exchange_map: Dict[str, str]) -> Tuple[str, str, str]:
    """Resolve symbol, exchange, and company name from ISIN."""
    isin_info = ISIN_MAP.get(isin)
    if isin_info:
        symbol, default_exchange, company_name = isin_info
    else:
        symbol = _derive_symbol(sec_name)
        default_exchange = "NSE"
        company_name = sec_name.title()
    exchange = exchange_map.get(isin, default_exchange)
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

def _parse_annexure_b_pdfplumber_tables(pdf_path: str, trade_date: str,
                                         exchange_map: Dict[str, str]) -> List[dict]:
    """Parse Annexure B using pdfplumber's direct table extraction API.

    This is the most reliable strategy because it reads the underlying
    PDF table structure rather than relying on text layout alignment.
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    transactions: List[dict] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            in_annexure_b = False

            for page in pdf.pages:
                page_text = (page.extract_text() or "").upper()

                if "ANNEXURE B" in page_text:
                    in_annexure_b = True
                if not in_annexure_b:
                    continue

                # Stop if we've clearly passed Annexure B
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

                        sec_match = _SEC_PATTERN.search(row_text)
                        if not sec_match:
                            continue

                        sec_name = sec_match.group(1).strip()
                        sec_name = re.sub(r'^.*?(?:Equity|EQUITY)\s*', '', sec_name).strip()
                        isin = sec_match.group(2).strip()

                        # Extract numeric values from cells after the ISIN cell
                        nums = []
                        past_desc = False
                        for cell in cells:
                            if isin in cell:
                                past_desc = True
                                continue
                            if past_desc and cell:
                                cleaned = cell.replace(",", "").replace(" ", "").strip()
                                if not cleaned:
                                    continue
                                # Handle parenthetical negatives: (1234.56) → -1234.56
                                if cleaned.startswith("(") and cleaned.endswith(")"):
                                    cleaned = "-" + cleaned[1:-1]
                                try:
                                    nums.append(float(cleaned))
                                except ValueError:
                                    continue

                        # Fallback: gather all numbers from the entire row
                        if len(nums) < 10:
                            nums = []
                            for cell in cells:
                                if "-Cash-" in cell or isin in cell:
                                    continue
                                cleaned = cell.replace(",", "").replace(" ", "").strip()
                                if not cleaned:
                                    continue
                                if cleaned.startswith("(") and cleaned.endswith(")"):
                                    cleaned = "-" + cleaned[1:-1]
                                try:
                                    nums.append(float(cleaned))
                                except ValueError:
                                    continue

                        if len(nums) < 10:
                            continue

                        numbers = [str(n) for n in nums]
                        _parse_nums_from_row(
                            numbers, sec_name, isin, exchange_map,
                            trade_date, transactions,
                        )

    except Exception as e:
        print(f"[ContractNote] pdfplumber table extraction error: {e}")
        import traceback
        traceback.print_exc()
        return []

    print(f"[ContractNote] Strategy 1 (table extraction): {len(transactions)} transactions")
    return transactions


# ═══════════════════════════════════════════════════════════
#  STRATEGY 2 & 3: TEXT-BASED PARSING
# ═══════════════════════════════════════════════════════════

def _parse_annexure_b(text: str, trade_date: str,
                       exchange_map: Dict[str, str]) -> List[dict]:
    """Parse Annexure B (Scrip Wise Summary) via text-based line matching.

    Each data row in Annexure B contains:
      Segment | Security Description | Bought Qty | Sold Qty | Average Rate |
      Gross Total | Brokerage | Net Total(Before Levies) | GST on Brokerage |
      Total STT | Other Statutory Levies | Net Total(After Levies)

    Handles both layout-mode text (column-aligned with spaces) and
    plain-mode text (sequential reading order).
    """
    transactions: List[dict] = []

    # Find Annexure B section (case-insensitive)
    upper_text = text.upper()
    annexure_b_start = upper_text.find("ANNEXURE B")
    if annexure_b_start < 0:
        print("[ContractNote] Text parser: 'ANNEXURE B' not found")
        return transactions

    annexure_text = text[annexure_b_start:]
    raw_lines = annexure_text.split("\n")
    print(f"[ContractNote] Text parser: found ANNEXURE B, {len(raw_lines)} lines to scan")

    # ── Merge continuation lines ──
    # Some PDF extractors split table rows across multiple lines.
    # If a line has a security description but < 10 numbers, and the next
    # line does NOT have its own security description, join them.
    merged_lines: List[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if (merged_lines
                and _SEC_PATTERN.search(merged_lines[-1])
                and len(_NUM_PATTERN.findall(merged_lines[-1])) < 10
                and not _SEC_PATTERN.search(stripped)):
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
        if "DESCRIPTION OF SERVICE" in line_upper:
            break  # End of Annexure B

        sec_match = _SEC_PATTERN.search(line)
        if not sec_match:
            continue

        sec_name = sec_match.group(1).strip()
        if sec_name.upper().startswith("EQUITY"):
            sec_name = sec_name[len("Equity"):].strip()
        isin = sec_match.group(2).strip()

        # Extract all numbers after the security description
        rest = line[sec_match.end():]
        numbers_raw = _NUM_PATTERN.findall(rest)
        numbers = [n.replace(',', '') for n in numbers_raw]

        if len(numbers) < 10:
            # Also try extracting numbers from the entire line
            # (for cases where numbers appear before and after the description)
            all_nums = _NUM_PATTERN.findall(line)
            all_nums = [n.replace(',', '') for n in all_nums]
            # Remove any numbers that are part of the ISIN/security name
            if len(all_nums) >= 10 and len(numbers) < 10:
                numbers = all_nums[-10:]  # Take the last 10 numbers

        if len(numbers) < 10:
            continue

        _parse_nums_from_row(
            numbers, sec_name, isin, exchange_map,
            trade_date, transactions,
        )

    print(f"[ContractNote] Text parser: {len(transactions)} transactions")
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
    transactions = _parse_annexure_b_pdfplumber_tables(
        pdf_path, trade_date, exchange_map)

    # ── Strategy 2: text-based parsing with layout mode ──
    if not transactions:
        print("[ContractNote] Trying Strategy 2: layout-mode text parsing...")
        transactions = _parse_annexure_b(text, trade_date, exchange_map)

    # ── Strategy 3: text-based parsing without layout mode ──
    if not transactions:
        print("[ContractNote] Trying Strategy 3: plain-text parsing (no layout)...")
        try:
            plain_text = extract_text_from_pdf(pdf_path, layout=False)
            transactions = _parse_annexure_b(plain_text, trade_date, exchange_map)
        except Exception as e:
            print(f"[ContractNote] Plain text fallback failed: {e}")

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
        idx = text.upper().find("ANNEXURE B")
        if idx >= 0:
            snippet = text[idx:idx + 1500]
        else:
            snippet = "ANNEXURE B not found in extracted text. First 1500 chars:\n" + text[:1500]

        result["_debug_text"] = snippet

        # Also dump full text to a temp file for manual inspection
        debug_path = "/tmp/contract_note_debug.txt"
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
