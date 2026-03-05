"""
Parse SBI bank statement PDFs to extract CEMTEX DEP dividend entries.

Dividend rows in SBI statements have descriptions starting with "CEMTEX DEP".
Company names are truncated (~14-20 chars) and resolved to NSE symbols via:
  1. Direct symbol match (bank descriptions often contain NSE symbols like TATAMOTORSDIV2)
  2. Exact name match against symbol_cache.json `name` section (12,364 entries)
  3. Prefix matching for truncated names
  4. Fuzzy matching via rapidfuzz for mid-word truncation
  5. Portfolio name map for user's actual holdings
"""
import re
import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Words to strip during normalization
_STRIP_WORDS = {"LIMITED", "LTD", "INDIA", "CORPORATION", "CORP", "PVT", "PRIVATE", "THE"}

# Common bank-statement abbreviations → NSE symbol overrides.
# Short names / concatenated symbols from CEMTEX DEP descriptions that
# fuzzy matching gets wrong or can't resolve.
_KNOWN_ABBREVIATIONS = {
    "SBI": "SBIN",
    "STATE BANK": "SBIN",
    "STATE BANK OF": "SBIN",
    "ONGC": "ONGC",
    "LIC": "LICI",
    "IOCL": "IOC",
    "IOC": "IOC",
    "NHPC": "NHPC",
    "OIL": "OIL",
    "BEL": "BEL",
    "HAL": "HAL",
    "IRFC": "IRFC",
    "IRFC LTD": "IRFC",
    "RVNL": "RVNL",
    "IREDA": "IREDA",
    "TPOWER": "TATAPOWER",
    "GRAPHIND": "GRAPHITE",
    "THEBOMBAYBURMA": "BBTC",
    "THE BOMBAY BUR": "BBTC",
    "THE BOMBAY BURMA": "BBTC",
    "BOMBAY BURMAH": "BBTC",
    "BOMBAY BUR": "BBTC",
    "HEROMOTOCORPLT": "HEROMOTOCO",
    "BIOCONLIMITED": "BIOCON",
    "COALINDIALTD": "COALINDIA",
    "WIPROLIMITED": "WIPRO",
    "IRBINFRASTRUCT": "IRB",
    "LARSENTOUBROLI": "LT",
    "LARSEN & TOUBR": "LT",
    "LARSEN AND TOU": "LT",
    "RALLISFIN": "RALLIS",
    "RALLIS": "RALLIS",
    "GRAPHIND": "GRAPHITE",
    "TPOWER": "TATAPOWER",
    "UBIFINAL": "UNIONBANK",
    "UBI": "UNIONBANK",
    "UNION BANK OF": "UNIONBANK",
    "VTW": "WABAG",
    "VTW FIN": "WABAG",
    "PNC": "PNCINFRA",
    "PNC FIN": "PNCINFRA",
    "BEL FIN": "BEL",
    "CENTRAL BK": "CENTRALBK",
    "ASHOK LEYLTD": "ASHOKLEY",
    "ASHOK LEYLTD I": "ASHOKLEY",
    "ASHOK LEYLAND": "ASHOKLEY",
    # "INDIAN RAILWAY" handled by prefix match → IRFC (Indian Railway Finance) in name index
    "RAILTEL CORP O": "RAILTEL",
    "OIL AND NATURA": "ONGC",
    "OIL INDIA": "OIL",
    "OIL INDIA LIMI": "OIL",
    "SYNGENE INTERN": "SYNGENE",
    "SYNGENE": "SYNGENE",
    "AFCON": "AFCONS",
    "AFCON INFRASTRUCTURE": "AFCONS",
    "RITES": "RITES",
    "MANAPPURAM": "MANAPPURAM",
    "MANAPPURAM FIN": "MANAPPURAM",
    "SBI LIFE INSUR": "SBILIFE",
    "SBI LIFE": "SBILIFE",
    "KAJARIA CERAMI": "KAJARIACER",
    "SUN TV NETWORK": "SUNTV",
    "IRCON INTERNAT": "IRCON",
    "RAIL VIKAS NIG": "RVNL",
    "TATAMOTORS": "TMCV",
    "TATA MOTORS": "TMCV",
    "TTL": "TATATECH",
    "TTLFIN": "TATATECH",
    "2ND INTM": "RITES",
}

# ── Persistent user overrides (saved when user edits symbols in preview modal)
_OVERRIDES_FILE = DATA_DIR / "dividend_symbol_overrides.json"


def _load_user_overrides() -> dict:
    """Load user-supplied raw_company → symbol overrides."""
    if _OVERRIDES_FILE.exists():
        try:
            return json.loads(_OVERRIDES_FILE.read_text())
        except Exception:
            pass
    return {}


def save_user_overrides(overrides: dict):
    """Persist user-supplied raw_company → symbol mappings.

    Called from the confirm endpoint when user has edited symbols.
    """
    existing = _load_user_overrides()
    existing.update(overrides)
    _OVERRIDES_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))


def _normalize(name: str) -> str:
    """Normalize company name for matching: uppercase, remove noise words, strip punctuation."""
    s = name.upper().strip()
    # Remove trailing hyphens, dots, numbers (like "LIMITED-", "LTD.", "2")
    s = re.sub(r"[-.,]+$", "", s)
    s = re.sub(r"[^A-Z0-9\s&]", " ", s)
    tokens = [t for t in s.split() if t not in _STRIP_WORDS]
    return " ".join(tokens).strip()


def _strip_dividend_suffix(raw: str) -> str:
    """Strip DIV/Dividend/FIN/FNL suffixes that banks append to company names/symbols.

    Examples: TATAMOTORSDIV2 → TATAMOTORS, TATASTEELDIV 2 → TATASTEEL,
              TTLFINDIV26062 → TTLFIN, RAILTEL-2 INT → RAILTEL,
              RALLISFINDIV24 → RALLIS, GRAPHINDFNL202 → GRAPHIND
    """
    s = raw.strip()
    # Remove trailing date/year-like patterns (2024, 2025, 20xx)
    s = re.sub(r"\s*20\d{2}\s*$", "", s)
    # Remove trailing " INT", " Interim", " Final", " 2", " 3", numeric suffixes
    s = re.sub(r"\s+(?:INT(?:ERIM)?|FINAL|FIN|FNL|2ND|3RD|1ST)\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+\d+\s*$", "", s)
    # Remove trailing -2, -3, - FINDIV, - INT-DI etc.
    s = re.sub(r"\s*-\s*(?:FINDIV|INT[\s-]*DI\w*|\d+)\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"-\d+\s*$", "", s)
    # Remove "DIV" + optional digits at the end (TATAMOTORSDIV2, TTLFINDIV26062, TATASTEELDIV20)
    s = re.sub(r"DIV\d*\s*$", "", s, flags=re.IGNORECASE)
    # Remove trailing "FNL" + digits (GRAPHINDFNL202)
    s = re.sub(r"FNL\d*\s*$", "", s, flags=re.IGNORECASE)
    # Remove "FINDIV" + digits (RALLISFINDIV24)
    s = re.sub(r"FINDIV\d*\s*$", "", s, flags=re.IGNORECASE)
    # Remove "FIN" + optional "DIV" + digits (standalone FIN at end)
    s = re.sub(r"FIN\s*$", "", s, flags=re.IGNORECASE)
    # Remove trailing "Dividend" or "DIVIDEND" with optional number
    s = re.sub(r"\s*Dividend\s*\d*\s*$", "", s, flags=re.IGNORECASE)
    # Remove trailing " LTD", " LIMIT", " LIMI" etc (truncated)
    s = re.sub(r"\s+LTD\.?\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+LIMI(?:TED?)?\s*$", "", s, flags=re.IGNORECASE)
    # Remove trailing word fragments after company name like "1stintdi", "intdiv", "3IN"
    s = re.sub(r"\s+\d*(?:st|nd|rd|th)?int(?:m|erim)?(?:di(?:v)?)?\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+\d+IN\s*$", "", s)  # "3IN" = "3rd Interim" abbreviation
    return s.strip()


def _build_lookup_tables(symbol_cache_path: Path, portfolio_name_map: dict) -> tuple:
    """Build lookup tables for symbol resolution.

    Returns:
        (name_to_symbol, symbol_set, symbol_aliases)
        - name_to_symbol: {normalized_name: symbol} from cache `name` section + portfolio
        - symbol_set: set of all known NSE symbols
        - symbol_aliases: {alias_symbol: canonical_symbol} for portfolio overrides
    """
    name_to_symbol = {}
    symbol_set = set()
    symbol_aliases = {}

    if symbol_cache_path.exists():
        try:
            cache = json.loads(symbol_cache_path.read_text())

            # Use the `name` section (12,364 entries) — pre-normalized names → symbols
            for raw_name, symbol in cache.get("name", {}).items():
                norm = _normalize(raw_name)
                if norm:
                    # Don't overwrite if already present (first entry wins)
                    if norm not in name_to_symbol:
                        name_to_symbol[norm] = symbol
                    symbol_set.add(symbol)

            # Also use `isin` section for additional full names
            for _isin, entry in cache.get("isin", {}).items():
                if len(entry) >= 3:
                    symbol = entry[0]
                    full_name = entry[2]
                    symbol_set.add(symbol)
                    norm = _normalize(full_name)
                    if norm and norm not in name_to_symbol:
                        name_to_symbol[norm] = symbol
        except Exception:
            pass

    # Portfolio name_map: symbol → company_name (these take highest priority)
    for symbol, company_name in portfolio_name_map.items():
        symbol_set.add(symbol)
        norm = _normalize(company_name)
        if norm:
            name_to_symbol[norm] = symbol  # overwrite: portfolio names win

    return name_to_symbol, symbol_set, symbol_aliases


def _resolve_symbol(raw_company: str, name_to_symbol: dict, symbol_set: set,
                    portfolio_symbols: set = None,
                    user_overrides: dict = None) -> tuple:
    """Resolve a company name/symbol from bank statement to an NSE symbol.

    Strategy (in order):
    0. User overrides (persisted from previous manual edits)
    1. Known abbreviations
    2. Direct symbol match (the raw text IS an NSE symbol, possibly with DIV suffix)
    3. Exact normalized name match
    4. Prefix match — longest match wins (handles truncated names)
    5. Fuzzy match via rapidfuzz (handles mid-word truncation)

    Returns (symbol, matched: bool).
    """
    if not raw_company or not raw_company.strip():
        return "", False

    portfolio_symbols = portfolio_symbols or set()
    user_overrides = user_overrides or {}

    # Step -1: Check user overrides (highest priority — from previous manual edits)
    raw_upper = raw_company.upper().strip()
    if raw_upper in user_overrides:
        return user_overrides[raw_upper], True

    # Step 0: Clean up the raw input — strip DIV suffixes
    cleaned = _strip_dividend_suffix(raw_company)
    cleaned_upper = cleaned.upper().strip()

    # Also check cleaned form against user overrides
    if cleaned_upper in user_overrides:
        return user_overrides[cleaned_upper], True

    # Step 0.5: Check known abbreviations first (SBI → SBIN, LIC → LICI, etc.)
    # Check cleaned, raw, and normalized forms
    for candidate in [cleaned_upper, raw_upper, _normalize(cleaned)]:
        if candidate in _KNOWN_ABBREVIATIONS:
            return _KNOWN_ABBREVIATIONS[candidate], True

    # Step 1: Direct symbol match — check if cleaned text is an NSE symbol
    # Prefer portfolio symbols over random NSE symbols
    if cleaned_upper in portfolio_symbols:
        return cleaned_upper, True
    if cleaned_upper in symbol_set:
        return cleaned_upper, True

    # First token as symbol — only for multi-word inputs where first word is the symbol
    # (e.g. "RAILTEL CORP" → RAILTEL, "COALINDIA Div" → COALINDIA)
    # Skip if cleaned_upper has multiple meaningful words (let name matching handle it)
    tokens = cleaned_upper.split()
    first_token = tokens[0] if tokens else ""
    if first_token and len(tokens) == 1:
        # Single word: already checked above
        pass
    elif first_token and len(first_token) >= 4:
        # Multi-word: only use first token if it's a portfolio symbol
        # (avoid matching "ASIAN" from "ASIAN PAINTS LIMITED" to ASIAN WAREHOUSING)
        if first_token in portfolio_symbols:
            return first_token, True

    # Step 2: Exact normalized name match
    norm = _normalize(cleaned)
    if not norm:
        return first_token or cleaned_upper, False

    if norm in name_to_symbol:
        return name_to_symbol[norm], True

    # Step 2.5: For single-word inputs that look like concatenated symbols (e.g. TATAMOTORS,
    # COALINDIA, APOLLOHOSP), try fuzzy-matching them directly against known NSE symbols
    if len(norm.split()) == 1 and len(norm) >= 6:
        try:
            from rapidfuzz import fuzz, process
            sym_results = process.extract(
                norm, list(symbol_set) + list(portfolio_symbols),
                scorer=fuzz.ratio,
                limit=3,
                score_cutoff=75,
            )
            if sym_results:
                # Prefer portfolio symbols
                for sym, score, _ in sym_results:
                    if sym in portfolio_symbols and score >= 75:
                        return sym, True
                best_sym, best_score, _ = sym_results[0]
                if best_score >= 80:
                    return best_sym, True
        except ImportError:
            pass

    # Step 3: Prefix match — longest overlap wins
    # This handles truncated names: "ASIAN PAINTS" matches "ASIAN PAINTS" (exact=12)
    # better than "ASIAN" matches "ASIAN WAREHOUSING" (overlap=5)
    best_prefix = None
    best_overlap = 0
    for cached_name, symbol in name_to_symbol.items():
        if cached_name.startswith(norm) or norm.startswith(cached_name):
            # Use the overlap length (shorter of the two)
            overlap = min(len(norm), len(cached_name))
            if overlap > best_overlap and overlap >= 4:
                # Prefer portfolio symbols on ties
                is_portfolio = symbol in portfolio_symbols
                if overlap > best_overlap or (overlap == best_overlap and is_portfolio):
                    best_prefix = symbol
                    best_overlap = overlap

    if best_prefix and best_overlap >= 4:
        return best_prefix, True

    # Step 4: Fuzzy match using rapidfuzz
    try:
        from rapidfuzz import fuzz, process

        # Use WRatio which combines multiple strategies (ratio, partial_ratio,
        # token_sort_ratio, token_set_ratio) and picks the best
        results = process.extract(
            norm, name_to_symbol.keys(),
            scorer=fuzz.WRatio,
            limit=5,
            score_cutoff=75,
        )
        if results:
            # Among top results, prefer portfolio symbols
            best_name, best_score = results[0][0], results[0][1]
            for name, score, _ in results:
                if name_to_symbol[name] in portfolio_symbols and score >= best_score - 5:
                    best_name = name
                    best_score = score
                    break

            min_score = 85 if len(norm) < 6 else 75
            if best_score >= min_score:
                return name_to_symbol[best_name], True
    except ImportError:
        pass

    # Step 5: Two-word prefix match as last resort
    norm_tokens = norm.split()
    if len(norm_tokens) >= 2:
        partial = " ".join(norm_tokens[:2])
        best_name = None
        best_len = 0
        for cached_name, symbol in name_to_symbol.items():
            if cached_name.startswith(partial) and len(cached_name) > best_len:
                best_name = symbol
                best_len = len(cached_name)
        if best_name:
            return best_name, True

    # Unmatched — return first word as best guess
    return first_token or (norm.split()[0] if norm.split() else ""), False


def _extract_company_name(description: str) -> str:
    """Extract company name from CEMTEX DEP description.

    Handles multiple SBI bank statement formats:
    - ACHCr: "CEMTEX DEP ACHCr <bank_ref> <company_name> Dividend [N]"
    - C-number: "CEMTEX DEP C<digits> <digits><company_name>[UNPAID DIVIDEND]"
    - NACH: "CEMTEX DEP ACHCr NACH<digits> <company_name>"
    """
    desc = description.strip()

    # ── C-number pattern: CEMTEX DEP C<digits> <digits><COMPANY NAME>
    # The digits run directly into the company name with no space
    m = re.search(
        r"CEMTEX\s+DEP\s+C\d+\s+\d+([A-Z][A-Z\s&.,'-]+)",
        desc,
        re.IGNORECASE,
    )
    if m:
        raw = m.group(1).strip()
        # Clean up: remove trailing "UNPAID DIVIDEND", "DIVIDEND", "-"
        raw = re.sub(r"\s*[-]?\s*UNPAID\s+DIVIDEND.*$", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s+DIVIDEND\s*\d*\s*$", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"[-]+$", "", raw).strip()
        return raw

    # ── ACHCr pattern: CEMTEX DEP ACHCr <ref_token> <company_name> [Dividend [N]]
    m = re.search(
        r"CEMTEX\s+DEP\s+ACHCr\s+\S+\s+(.+?)$",
        desc,
        re.IGNORECASE,
    )
    if m:
        raw = m.group(1).strip()
        # Remove trailing "Dividend N", "DIV", "INT", number
        raw = re.sub(r"\s+Dividend\s*\d*\s*$", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s+DIV\s*\d*\s*$", "", raw, flags=re.IGNORECASE)
        return raw.strip()

    # ── Generic fallback: everything after CEMTEX DEP and two tokens
    m = re.search(r"CEMTEX\s+DEP\s+\S+\s+\S+\s+(.+?)$", desc, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        raw = re.sub(r"\s+Dividend\s*\d*\s*$", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s+UNPAID\s+DIVIDEND.*$", "", raw, flags=re.IGNORECASE)
        return raw.strip()

    # Ultra-fallback: everything after CEMTEX DEP
    m = re.search(r"CEMTEX\s+DEP\s+(.+?)$", desc, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        # Strip leading transaction codes
        raw = re.sub(r"^(?:ACHCr|NACH|NEFT|C\d+)\s*", "", raw)
        raw = re.sub(r"^\S+\s+", "", raw)  # remove ref number
        raw = re.sub(r"\s+Dividend\s*\d*\s*$", "", raw, flags=re.IGNORECASE)
        return raw.strip()

    return ""


def _parse_date(raw: str) -> str:
    """Parse DD/MM/YYYY or DD-MM-YYYY to YYYY-MM-DD."""
    raw = raw.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _parse_amount(raw) -> float:
    """Parse amount string: remove commas, convert to float."""
    if isinstance(raw, (int, float)):
        return float(raw)
    if not raw:
        return 0.0
    s = str(raw).replace(",", "").replace(" ", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _is_dividend_entry(description: str) -> bool:
    """Check if a CEMTEX DEP entry is actually a dividend (not a reversal etc.)."""
    desc_upper = description.upper()
    if "CEMTEX DEP" not in desc_upper:
        return False
    skip_patterns = ["IMPS", "REVERSAL", "REV ", "RETURN", "BOUNCE", "REJECT"]
    for pat in skip_patterns:
        if pat in desc_upper:
            return False
    return True


def _extract_statement_period(pages_text: list) -> str:
    """Try to extract statement period from first page text."""
    if not pages_text:
        return ""
    first_page = pages_text[0] if pages_text else ""
    m = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+to\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", first_page)
    if m:
        return f"{m.group(1)} to {m.group(2)}"
    return ""


def parse_dividend_statement(pdf_bytes: bytes, portfolio_name_map: dict,
                              existing_fingerprints_fn=None) -> dict:
    """Parse SBI bank statement PDF, extract CEMTEX DEP dividend entries.

    Args:
        pdf_bytes: Raw PDF file bytes
        portfolio_name_map: {symbol: company_name} from xlsx database
        existing_fingerprints_fn: callable(symbol) -> set of (date, amount) tuples

    Returns dict with keys: statement_period, source, dividends, summary
    """
    import pdfplumber
    import io

    symbol_cache_path = DATA_DIR / "symbol_cache.json"
    name_to_symbol, symbol_set, _ = _build_lookup_tables(symbol_cache_path, portfolio_name_map)
    portfolio_symbols = set(portfolio_name_map.keys())

    # Load user overrides (persisted from previous manual symbol edits)
    user_overrides = {k.upper(): v for k, v in _load_user_overrides().items()}

    dividends = []
    pages_text = []

    with pdfplumber.open(io.BytesIO(pdf_bytes) if isinstance(pdf_bytes, bytes) else pdf_bytes) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            pages_text.append(page_text)

            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                if not table:
                    continue

                for row in table:
                    if not row or len(row) < 6:
                        continue

                    # SBI statement: ValueDate, PostDate, Details, RefNo, Debit, Credit, Balance
                    # Collapse newlines — pdfplumber preserves line breaks within cells
                    if len(row) >= 7:
                        val_date = str(row[0] or "").replace("\n", " ").strip()
                        details = str(row[2] or "").replace("\n", " ").strip()
                        credit = str(row[5] or "").replace("\n", " ").strip()
                    elif len(row) == 6:
                        val_date = str(row[0] or "").replace("\n", " ").strip()
                        details = str(row[1] or "").replace("\n", " ").strip()
                        credit = str(row[4] or "").replace("\n", " ").strip()
                    else:
                        continue

                    if not _is_dividend_entry(details):
                        continue

                    amount = _parse_amount(credit)
                    if amount <= 0:
                        continue

                    date_str = _parse_date(val_date)
                    company_raw = _extract_company_name(details)
                    symbol, matched = _resolve_symbol(
                        company_raw, name_to_symbol, symbol_set, portfolio_symbols,
                        user_overrides
                    )

                    # Duplicate detection
                    is_dup = False
                    if existing_fingerprints_fn and symbol and matched:
                        try:
                            fps = existing_fingerprints_fn(symbol)
                            fp = (date_str, round(amount, 2))
                            if fp in fps:
                                is_dup = True
                        except Exception:
                            pass

                    dividends.append({
                        "date": date_str,
                        "company_raw": company_raw,
                        "symbol": symbol,
                        "symbol_matched": matched,
                        "amount": round(amount, 2),
                        "description": details,
                        "isDuplicate": is_dup,
                    })

    statement_period = _extract_statement_period(pages_text)
    matched_count = sum(1 for d in dividends if d["symbol_matched"])
    unmatched_count = len(dividends) - matched_count
    total_amount = sum(d["amount"] for d in dividends)

    return {
        "statement_period": statement_period,
        "source": "SBI Bank Statement",
        "dividends": dividends,
        "summary": {
            "count": len(dividends),
            "total_amount": round(total_amount, 2),
            "matched": matched_count,
            "unmatched": unmatched_count,
        },
    }
