"""
SBICAP Securities Contract Note PDF Parser.

Parses contract notes from SBICAP Securities to extract buy/sell transactions.
Uses Annexure B (Scrip Wise Summary) as the primary data source.

Effective buy price  = Net Total (After Levies) / Bought Qty
Effective sell price = |Net Total (After Levies)| / Sold Qty

This ensures the per-share price includes all charges: brokerage, GST, STT,
exchange charges, SEBI fees, stamp duty, and other statutory levies.
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


def _derive_symbol(name: str) -> str:
    """Derive a stock symbol from the contract note security name.

    Uses common abbreviation rules for NSE/BSE symbols.
    """
    # Remove common suffixes
    cleaned = name.upper()
    for suffix in [" LIMITED", " LTD", " ENTER. L", " CORP", " OF INDIA"]:
        cleaned = cleaned.replace(suffix, "")
    # Remove extra spaces and special chars
    cleaned = re.sub(r'[^A-Z0-9 ]', '', cleaned).strip()
    # Take first word or join if short
    parts = cleaned.split()
    if len(parts) == 1:
        return parts[0][:15]
    # Join first few words
    return "".join(parts)[:15]


# ═══════════════════════════════════════════════════════════
#  PDF TEXT EXTRACTION
# ═══════════════════════════════════════════════════════════

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber (primary) or pdftotext CLI (fallback).

    pdfplumber provides layout-aware text extraction as a pure Python library,
    so it works on all platforms without requiring external CLI tools.
    """
    # Primary: pdfplumber (pure Python, works everywhere)
    try:
        import pdfplumber
        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=True)
                if text:
                    pages_text.append(text)
        if pages_text:
            return "\n".join(pages_text)
    except ImportError:
        pass  # pdfplumber not installed, try fallback
    except Exception as e:
        print(f"[ContractNote] pdfplumber failed: {e}, trying pdftotext CLI...")

    # Fallback: pdftotext CLI (requires poppler-utils)
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except FileNotFoundError:
        pass  # pdftotext not installed
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
    # Pattern: TRADE DATE followed by DD-MON-YY
    match = re.search(r'TRADE\s+DATE\s+(\d{2}-[A-Z]{3}-\d{2,4})', text)
    if match:
        date_str = match.group(1)
        # Try DD-MON-YY (e.g., 09-FEB-26 → 2026-02-09)
        for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d-%B-%y", "%d-%B-%Y"):
            try:
                dt = datetime.strptime(date_str, fmt)
                # Correct century for 2-digit years
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def _extract_contract_no(text: str) -> Optional[str]:
    """Extract contract note number."""
    match = re.search(r'CONTRACT\s+NOTE\s+NO\.\s+(\d+)', text)
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
        # Look for ISIN in the line
        isin_match = re.search(r'(INE\w{9}|INF\w{9})', line)
        if isin_match:
            isin = isin_match.group(1)
            # Only set if in BSE section (NSE is default)
            if current_exchange == "BSE":
                exchange_map[isin] = "BSE"

    return exchange_map


# ═══════════════════════════════════════════════════════════
#  ANNEXURE B PARSING
# ═══════════════════════════════════════════════════════════

def _parse_annexure_b(text: str, trade_date: str,
                       exchange_map: Dict[str, str]) -> List[dict]:
    """Parse Annexure B (Scrip Wise Summary) to extract per-stock transactions.

    Each data row in Annexure B contains:
      Segment | Security Description | Bought Qty | Sold Qty | Average Rate |
      Gross Total | Brokerage | Net Total(Before Levies) | GST on Brokerage |
      Total STT | Other Statutory Levies | Net Total(After Levies)

    Returns list of transaction dicts:
      {action, symbol, exchange, name, isin, quantity, wap, effective_price,
       net_total_after_levies, brokerage, gst, stt, other_levies, trade_date}
    """
    transactions = []

    # Find Annexure B section
    annexure_b_start = text.find("ANNEXURE B")
    if annexure_b_start < 0:
        return transactions

    annexure_text = text[annexure_b_start:]
    lines = annexure_text.split("\n")

    # Pattern to match security description with ISIN
    # e.g., "ADANI POWER LTD-Cash-INE814H01029"
    sec_pattern = re.compile(r'(.+?)-Cash-((?:INE|INF)\w+)')

    for line in lines:
        # Skip Sub Total lines, header lines, page breaks, footer
        if "Sub Total" in line:
            continue
        if "Segment" in line and "Security Description" in line:
            continue
        if "Page " in line and " / " in line:
            continue
        if "CGST" in line or "SGST" in line or "IGST" in line:
            continue
        if "Description of Service" in line:
            break  # End of Annexure B

        # Try to find a security description
        sec_match = sec_pattern.search(line)
        if not sec_match:
            continue

        sec_name = sec_match.group(1).strip()
        # Remove leading "Equity" segment label
        if sec_name.startswith("Equity"):
            sec_name = sec_name[len("Equity"):].strip()
        isin = sec_match.group(2).strip()

        # Extract all numbers after the security description
        rest = line[sec_match.end():]
        numbers = re.findall(r'-?[\d]+\.[\d]+|-?[\d]+', rest)

        if len(numbers) < 10:
            continue  # Need at least 10 numeric fields

        try:
            bought_qty = int(float(numbers[0]))
            sold_qty = int(float(numbers[1]))
            avg_rate = abs(float(numbers[2]))       # WAP (absolute)
            gross_total = float(numbers[3])
            brokerage = float(numbers[4])
            net_before = float(numbers[5])
            gst = float(numbers[6])
            stt = float(numbers[7])
            other_levies = float(numbers[8])
            net_after = float(numbers[9])
        except (ValueError, IndexError) as e:
            print(f"[ContractNote] Parse error for {sec_name}: {e}")
            continue

        # Look up symbol from ISIN
        isin_info = ISIN_MAP.get(isin)
        if isin_info:
            symbol, default_exchange, company_name = isin_info
        else:
            symbol = _derive_symbol(sec_name)
            default_exchange = "NSE"
            company_name = sec_name.title()

        # Exchange from Annexure A, or ISIN map, or default
        exchange = exchange_map.get(isin, default_exchange)

        # Determine action: BUY if bought_qty > 0, SELL if sold_qty > 0
        if bought_qty > 0:
            # BUY: net_after is positive
            effective_price = net_after / bought_qty
            add_charges = brokerage + gst + other_levies
            transactions.append({
                "action": "Buy",
                "symbol": symbol,
                "exchange": exchange,
                "name": company_name,
                "isin": isin,
                "quantity": bought_qty,
                "wap": avg_rate,
                "effective_price": round(effective_price, 4),
                "net_total_after_levies": round(net_after, 2),
                "brokerage": round(brokerage, 4),
                "gst": round(gst, 4),
                "stt": round(stt, 4),
                "other_levies": round(other_levies, 4),
                "add_charges": round(add_charges, 4),
                "trade_date": trade_date,
            })

        if sold_qty > 0:
            # SELL: net_after is negative, effective price = |net_after| / qty
            effective_price = abs(net_after) / sold_qty
            add_charges = brokerage + gst + other_levies
            transactions.append({
                "action": "Sell",
                "symbol": symbol,
                "exchange": exchange,
                "name": company_name,
                "isin": isin,
                "quantity": sold_qty,
                "wap": avg_rate,
                "effective_price": round(effective_price, 4),
                "net_total_after_levies": round(abs(net_after), 2),
                "brokerage": round(brokerage, 4),
                "gst": round(gst, 4),
                "stt": round(stt, 4),
                "other_levies": round(other_levies, 4),
                "add_charges": round(add_charges, 4),
                "trade_date": trade_date,
            })

    return transactions


# ═══════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

def parse_contract_note(pdf_path: str) -> dict:
    """Parse an SBICAP Securities contract note PDF.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        {
            "trade_date": "2026-02-09",
            "contract_no": "252611665409",
            "transactions": [...],
            "summary": {"buys": 25, "sells": 3, "total": 28},
        }
    """
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_path)

    # Extract metadata
    trade_date = _extract_trade_date(text)
    if not trade_date:
        raise ValueError("Could not extract trade date from contract note")

    contract_no = _extract_contract_no(text)

    # Build exchange map from Annexure A
    exchange_map = _extract_exchange_map(text)

    # Parse Annexure B
    transactions = _parse_annexure_b(text, trade_date, exchange_map)

    buys = sum(1 for t in transactions if t["action"] == "Buy")
    sells = sum(1 for t in transactions if t["action"] == "Sell")

    return {
        "trade_date": trade_date,
        "contract_no": contract_no,
        "transactions": transactions,
        "summary": {
            "buys": buys,
            "sells": sells,
            "total": buys + sells,
        },
    }


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
