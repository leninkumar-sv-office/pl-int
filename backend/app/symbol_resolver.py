"""
Shared symbol resolution: company name → NSE/BSE trading symbol.

Downloads Zerodha instruments CSV and NSE EQUITY_L.csv to build
two lookup maps:
  1. ISIN → (symbol, exchange, name)   — for contract note parsing
  2. Normalized name → symbol           — for xlsx filename resolution

Results are cached to disk (data/symbol_cache.json) so subsequent
startups are instant. Cache is refreshed every 24 hours.

Usage:
    from app.symbol_resolver import ensure_loaded, resolve_by_name, resolve_by_isin

    ensure_loaded()                        # call once at startup
    sym = resolve_by_name("Afcons Infrastructure Ltd")  # → "AFCONS"
    info = resolve_by_isin("INE05XR01022")              # → ("BHARATCOAL", "NSE", "...")
"""

import csv
import io
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── State ──
_ISIN_MAP: Dict[str, Tuple[str, str, str]] = {}  # ISIN → (symbol, exchange, name)
_NAME_MAP: Dict[str, str] = {}                     # normalized name → symbol
_LOADED_OK: bool = False
_LOADED_AT: float = 0
_TTL = 86400  # 24 hours

_DATA_DIR = Path(__file__).parent.parent / "data"
_CACHE_FILE = _DATA_DIR / "symbol_cache.json"

_NSE_EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
_ZERODHA_URL = "https://api.kite.trade/instruments"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ═══════════════════════════════════════════════════════════
#  NAME NORMALIZATION
# ═══════════════════════════════════════════════════════════

_STRIP_SUFFIXES = [
    " LIMITED", " LTD", " LTD.", " PRIVATE", " PVT", " PVT.",
    " INC", " INC.", " CORP", " CORP.", " CORPORATION",
]

_STRIP_ANYWHERE = [
    " - ARCHIVE", "ARCHIVE_",
]


def _normalize(name: str) -> str:
    """Normalize a company name for matching.

    Uppercases, strips common suffixes, removes non-alphanumeric chars.
    """
    n = name.upper().strip()
    # Strip archive prefixes/suffixes
    for s in _STRIP_ANYWHERE:
        n = n.replace(s, "")
    n = n.strip()
    # Strip legal suffixes from end
    for suffix in _STRIP_SUFFIXES:
        if n.endswith(suffix):
            n = n[:-len(suffix)].strip()
    return n


def _normalize_variants(name: str) -> List[str]:
    """Generate multiple normalized variants for matching.

    Returns a list of names to try, from most specific to least.
    """
    base = _normalize(name)
    variants = [base]

    # Also try without parenthetical content: "DIXON TECHNO (INDIA)" → "DIXON TECHNO"
    no_parens = re.sub(r'\s*\(.*?\)', '', base).strip()
    if no_parens != base:
        variants.append(no_parens)

    return variants


# ═══════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════

def _load_from_network() -> Tuple[Dict, Dict]:
    """Download ISIN and name maps from NSE + Zerodha. Returns (isin_map, name_map)."""
    isin_map: Dict[str, Tuple[str, str, str]] = {}
    name_map: Dict[str, str] = {}

    # ── Source 1: NSE EQUITY_L.csv (ISIN → symbol) ──
    try:
        print("[SymbolResolver] Downloading NSE equity list...")
        req = urllib.request.Request(_NSE_EQUITY_URL, headers={
            "User-Agent": _UA,
            "Accept": "text/csv,text/plain,*/*",
            "Referer": "https://www.nseindia.com/",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            isin = symbol = comp_name = ""
            for k, v in row.items():
                kl = k.strip().upper()
                if "ISIN" in kl:
                    isin = (v or "").strip()
                elif kl == "SYMBOL":
                    symbol = (v or "").strip()
                elif "NAME" in kl and "COMPANY" in kl:
                    comp_name = (v or "").strip()

            if not isin or not symbol:
                continue
            if not (isin.startswith("INE") or isin.startswith("INF")):
                continue

            isin_map[isin] = (symbol, "NSE", comp_name)

            # Also populate name_map from NSE data
            norm = _normalize(comp_name)
            if norm:
                name_map[norm] = symbol

        print(f"[SymbolResolver] NSE: {len(isin_map)} ISIN mappings")
    except Exception as e:
        print(f"[SymbolResolver] NSE download failed: {e}")

    # ── Source 2: Zerodha instruments (name → symbol) ──
    try:
        print("[SymbolResolver] Downloading Zerodha instruments...")
        req = urllib.request.Request(_ZERODHA_URL, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")

        reader = csv.DictReader(io.StringIO(raw))
        zcount = 0
        for row in reader:
            instrument_type = (row.get("instrument_type") or "").strip()
            exchange = (row.get("exchange") or "").strip()
            if instrument_type != "EQ" or exchange not in ("NSE", "BSE"):
                continue
            tradingsymbol = (row.get("tradingsymbol") or "").strip()
            name = (row.get("name") or "").strip()
            if not tradingsymbol or not name:
                continue

            norm = _normalize(name)
            # Prefer NSE over BSE
            if exchange == "NSE" or norm not in name_map:
                name_map[norm] = tradingsymbol
            zcount += 1

        print(f"[SymbolResolver] Zerodha: {zcount} equity entries, "
              f"total name mappings: {len(name_map)}")
    except Exception as e:
        print(f"[SymbolResolver] Zerodha download failed: {e}")

    return isin_map, name_map


def _save_cache(isin_map: Dict, name_map: Dict):
    """Persist maps to disk for instant startup."""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache = {
            "ts": time.time(),
            "isin": {k: list(v) for k, v in isin_map.items()},
            "name": name_map,
        }
        with open(_CACHE_FILE, "w") as f:
            json.dump(cache, f)
        print(f"[SymbolResolver] Cached {len(isin_map)} ISIN + {len(name_map)} name mappings")
    except Exception as e:
        print(f"[SymbolResolver] Cache write failed: {e}")


def _load_cache() -> Tuple[Optional[Dict], Optional[Dict], float]:
    """Load cached maps from disk. Returns (isin_map, name_map, timestamp)."""
    try:
        if not _CACHE_FILE.exists():
            return None, None, 0
        with open(_CACHE_FILE) as f:
            cache = json.load(f)
        ts = cache.get("ts", 0)
        isin_raw = cache.get("isin", {})
        name_map = cache.get("name", {})
        isin_map = {k: tuple(v) for k, v in isin_raw.items()}
        return isin_map, name_map, ts
    except Exception as e:
        print(f"[SymbolResolver] Cache read failed: {e}")
        return None, None, 0


def _do_load():
    """Load symbol data from cache or network."""
    global _ISIN_MAP, _NAME_MAP, _LOADED_OK, _LOADED_AT

    now = time.time()

    # Try disk cache first (instant)
    cached_isin, cached_name, ts = _load_cache()
    if cached_isin and cached_name and (now - ts) < _TTL:
        _ISIN_MAP.clear()
        _ISIN_MAP.update(cached_isin)
        _NAME_MAP.clear()
        _NAME_MAP.update(cached_name)
        _LOADED_OK = True
        _LOADED_AT = now
        print(f"[SymbolResolver] Loaded from cache: {len(_ISIN_MAP)} ISIN, {len(_NAME_MAP)} names")
        return

    # Download fresh
    _LOADED_AT = now
    isin_map, name_map = _load_from_network()

    if isin_map or name_map:
        _ISIN_MAP.clear()
        _ISIN_MAP.update(isin_map)
        _NAME_MAP.clear()
        _NAME_MAP.update(name_map)
        _LOADED_OK = True
        _save_cache(isin_map, name_map)
    elif cached_isin and cached_name:
        # Network failed but stale cache exists — use it
        _ISIN_MAP.clear()
        _ISIN_MAP.update(cached_isin)
        _NAME_MAP.clear()
        _NAME_MAP.update(cached_name)
        _LOADED_OK = True
        print("[SymbolResolver] Network failed, using stale cache")
    else:
        _LOADED_OK = False
        print("[SymbolResolver] WARNING: No symbol data available")


# ═══════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════

def ensure_loaded():
    """Ensure symbol data is loaded. Call once before batch lookups.

    Safe to call multiple times — will skip if already loaded and fresh.
    """
    now = time.time()
    if _LOADED_OK and (now - _LOADED_AT) < _TTL:
        return
    # Throttle retries on failure
    if not _LOADED_OK and _LOADED_AT and (now - _LOADED_AT) < 60:
        return
    _do_load()


def resolve_by_isin(isin: str) -> Optional[Tuple[str, str, str]]:
    """Look up ISIN → (symbol, exchange, name).

    Returns None if ISIN is not found.
    """
    return _ISIN_MAP.get(isin)


def resolve_by_name(company_name: str) -> Optional[str]:
    """Look up company name → trading symbol.

    Tries exact normalized match first, then partial/substring matching.
    Returns the trading symbol or None.
    """
    if not _NAME_MAP:
        return None

    # Try normalized variants
    for variant in _normalize_variants(company_name):
        if variant in _NAME_MAP:
            return _NAME_MAP[variant]

    # Partial match: contract note/filename may differ from Zerodha name
    norm = _normalize(company_name)
    best_match = None
    best_len = 0
    for zname, zsymbol in _NAME_MAP.items():
        if zname in norm or norm in zname:
            if len(zname) > best_len:
                best_match = zsymbol
                best_len = len(zname)
    return best_match


def derive_symbol(name: str) -> str:
    """Last-resort: derive a symbol from company name heuristic.

    Uses first word of cleaned name (most NSE symbols are the first word).
    """
    cleaned = name.upper()
    for suffix in [" LIMITED", " LTD", " ENTER. L", " CORP", " OF INDIA",
                   " INDUSTRIES", " INFRASTRUCTURE", " TECHNOLOGIES",
                   " PHARMA", " FINANCIAL", " SERVICES", " HOLDINGS"]:
        cleaned = cleaned.replace(suffix, "")
    cleaned = re.sub(r'[^A-Z0-9 ]', '', cleaned).strip()
    parts = cleaned.split()
    if not parts:
        return "UNKNOWN"
    if len(parts) == 1:
        return parts[0][:20]
    if len(parts[0]) > 2:
        return parts[0][:20]
    return (parts[0] + parts[1])[:20]


def get_name_map() -> Dict[str, str]:
    """Return the full normalized name → symbol map (read-only use)."""
    return _NAME_MAP


def get_isin_map() -> Dict[str, Tuple[str, str, str]]:
    """Return the full ISIN → (symbol, exchange, name) map (read-only use)."""
    return _ISIN_MAP
