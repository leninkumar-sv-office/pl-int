"""
Stock data service — multi-source with retry.

Priority order:
  1. Zerodha Kite Connect (primary — fast, reliable, Indian market)
  2. yfinance (batched, with retry + exponential backoff)
  3. Google Finance scraping (fallback)
  4. Saved JSON prices (offline fallback)
  5. xlsx Index sheet data (last resort)

All sources feed into a unified cache.  Manual push via bulk_update_prices()
also writes to the JSON file so data survives restarts.
"""
import os
import json
import re
import time
import threading
import random
import requests as _requests
import yfinance as yf
from typing import Optional, Dict, List, Tuple
from .models import StockLiveData
from .xlsx_database import xlsx_db as db
from . import zerodha_service

# ═══════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════

CACHE_TTL = 300           # 5 min cache
BATCH_SIZE = 5            # tickers per yf.download()
BATCH_DELAY = (2.0, 3.5)  # random delay between batches
REFRESH_INTERVAL = 300    # background refresh every 5 min
MAX_RETRIES = 3           # retry attempts per source

# Fallback toggle — Yahoo/Google are OFF by default.
# Enable via: python -m uvicorn app.main:app --port 8000 --reload
#   with env var: ENABLE_FALLBACK=1
# Or at runtime via POST /api/settings/fallback
ENABLE_YAHOO_GOOGLE = os.getenv("ENABLE_FALLBACK", "").strip().lower() in ("1", "true", "yes")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_PRICES_FILE = os.path.join(_DATA_DIR, "stock_prices.json")

# ═══════════════════════════════════════════════════════════
#  CACHE
# ═══════════════════════════════════════════════════════════

_cache: Dict[str, Tuple[float, StockLiveData]] = {}
_cache_lock = threading.Lock()


def _cache_get(key: str) -> Optional[StockLiveData]:
    with _cache_lock:
        if key in _cache:
            ts, data = _cache[key]
            if time.time() - ts < CACHE_TTL:
                return data
    return None


def _cache_set(key: str, data: StockLiveData):
    with _cache_lock:
        _cache[key] = (time.time(), data)


def _cache_get_stale(key: str) -> Optional[StockLiveData]:
    with _cache_lock:
        if key in _cache:
            return _cache[key][1]
    return None


# ═══════════════════════════════════════════════════════════
#  JSON FILE PERSISTENCE (survives restarts)
# ═══════════════════════════════════════════════════════════

def _save_prices_file(prices: Dict[str, dict]):
    """Save stock prices to JSON for offline fallback."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    try:
        # Merge with existing
        existing = _load_prices_file()
        existing.update(prices)
        with open(_PRICES_FILE, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        print(f"[StockService] Failed to save prices file: {e}")


def _load_prices_file() -> Dict[str, dict]:
    """Load saved stock prices from JSON."""
    try:
        with open(_PRICES_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _file_fallback(symbol: str, exchange: str) -> Optional[StockLiveData]:
    """Load a single stock price from the saved JSON file."""
    saved = _load_prices_file()
    key = f"{symbol}.{exchange}"
    info = saved.get(key)
    if not info or float(info.get("price", 0)) <= 0:
        return None
    return StockLiveData(
        symbol=symbol, exchange=exchange,
        name=info.get("name", db._name_map.get(symbol, symbol)),
        current_price=round(float(info["price"]), 2),
        week_52_high=float(info.get("week_52_high", 0) or 0),
        week_52_low=float(info.get("week_52_low", 0) or 0),
        day_change=float(info.get("day_change", 0) or 0),
        day_change_pct=float(info.get("day_change_pct", 0) or 0),
        volume=int(info.get("volume", 0) or 0),
        previous_close=float(info.get("previous_close", 0) or 0),
        is_manual=True,
    )


# ═══════════════════════════════════════════════════════════
#  XLSX FALLBACK (last resort — Index sheet data)
# ═══════════════════════════════════════════════════════════

_xlsx_idx: Dict[str, dict] = {}
_xlsx_built = False


def _build_xlsx():
    """Build xlsx Index sheet cache for ALL stocks (expensive — opens every xlsx file)."""
    global _xlsx_built
    if _xlsx_built:
        return
    import openpyxl
    from .xlsx_database import _extract_index_data
    for sym, fp in db._file_map.items():
        if sym in _xlsx_idx:
            continue  # already cached
        try:
            wb = openpyxl.load_workbook(fp, data_only=True)
            idx = _extract_index_data(wb)
            wb.close()
            _xlsx_idx[sym] = {
                "price": float(idx.get("current_price", 0) or 0),
                "w52h": float(idx.get("week_52_high", 0) or 0),
                "w52l": float(idx.get("week_52_low", 0) or 0),
            }
        except Exception:
            _xlsx_idx[sym] = {"price": 0, "w52h": 0, "w52l": 0}
    _xlsx_built = True
    ok = sum(1 for v in _xlsx_idx.values() if v["price"] > 0)
    print(f"[StockService] xlsx fallback: {ok}/{len(_xlsx_idx)} with prices")


def _xlsx_single(symbol: str) -> dict:
    """Load Index sheet data for a single symbol (fast — one file only)."""
    if symbol in _xlsx_idx:
        return _xlsx_idx[symbol]
    fp = db._file_map.get(symbol)
    if not fp:
        return {"price": 0, "w52h": 0, "w52l": 0}
    try:
        import openpyxl
        from .xlsx_database import _extract_index_data
        wb = openpyxl.load_workbook(fp, data_only=True)
        idx = _extract_index_data(wb)
        wb.close()
        _xlsx_idx[symbol] = {
            "price": float(idx.get("current_price", 0) or 0),
            "w52h": float(idx.get("week_52_high", 0) or 0),
            "w52l": float(idx.get("week_52_low", 0) or 0),
        }
    except Exception:
        _xlsx_idx[symbol] = {"price": 0, "w52h": 0, "w52l": 0}
    return _xlsx_idx[symbol]


def _xlsx_fallback(symbol: str, exchange: str) -> Optional[StockLiveData]:
    """Get price from xlsx Index sheet for a single symbol."""
    idx = _xlsx_single(symbol)
    price = idx.get("price", 0)
    if price <= 0:
        mp = db.get_manual_price(symbol, exchange)
        if mp and mp > 0:
            price = mp
    if price <= 0:
        return None
    return StockLiveData(
        symbol=symbol, exchange=exchange,
        name=db._name_map.get(symbol, symbol),
        current_price=round(price, 2),
        week_52_high=idx.get("w52h", 0),
        week_52_low=idx.get("w52l", 0),
        day_change=0, day_change_pct=0,
        volume=0, previous_close=0,
        is_manual=True,
    )


# ═══════════════════════════════════════════════════════════
#  SOURCE 1: YAHOO FINANCE (yfinance with retry)
# ═══════════════════════════════════════════════════════════

def _yahoo_sym(symbol: str, exchange: str) -> str:
    suffix = ".NS" if exchange.upper() == "NSE" else ".BO"
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}{suffix}"


def _download_batch(tickers: List[str]) -> Dict[str, float]:
    """Download a small batch via yf.download(). Returns {yahoo_sym: price}."""
    prices = {}
    if not tickers:
        return prices
    try:
        df = yf.download(
            " ".join(tickers),
            period="5d",
            progress=False,
            threads=False,
            timeout=15,
        )
        if df is None or df.empty:
            return prices

        if len(tickers) == 1:
            t = tickers[0]
            if "Close" in df.columns:
                vals = df["Close"].dropna()
                if len(vals) > 0:
                    p = float(vals.iloc[-1])
                    if p > 0:
                        prices[t] = p
        else:
            if "Close" in df.columns:
                close = df["Close"]
                for t in tickers:
                    try:
                        if t in close.columns:
                            vals = close[t].dropna()
                            if len(vals) > 0:
                                p = float(vals.iloc[-1])
                                if p > 0:
                                    prices[t] = p
                    except Exception:
                        pass
    except Exception as e:
        print(f"[StockService] Batch error: {e}")
    return prices


def _download_batch_with_retry(tickers: List[str]) -> Dict[str, float]:
    """Download with retry + exponential backoff."""
    for attempt in range(MAX_RETRIES):
        prices = _download_batch(tickers)
        if prices:
            return prices
        if attempt < MAX_RETRIES - 1:
            delay = (attempt + 1) * 2 + random.uniform(0, 1)
            print(f"[StockService] Yahoo retry {attempt + 1}/{MAX_RETRIES} "
                  f"for {len(tickers)} tickers, wait {delay:.1f}s...")
            time.sleep(delay)
    return {}


# ═══════════════════════════════════════════════════════════
#  SOURCE 2: GOOGLE FINANCE SCRAPING (fallback)
# ═══════════════════════════════════════════════════════════

_GOOGLE_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_google_finance_price(symbol: str, exchange: str) -> Optional[float]:
    """Scrape current price from Google Finance."""
    suffix = "NSE" if exchange.upper() == "NSE" else "BOM"
    url = f"https://www.google.com/finance/quote/{symbol}:{suffix}"
    for attempt in range(2):
        try:
            resp = _requests.get(url, headers=_GOOGLE_HEADERS, timeout=10)
            if resp.status_code == 200:
                # Google Finance embeds price in data-last-price attribute
                match = re.search(r'data-last-price="([\d,.]+)"', resp.text)
                if match:
                    price_str = match.group(1).replace(",", "")
                    price = float(price_str)
                    if price > 0:
                        return price
        except Exception:
            pass
        if attempt < 1:
            time.sleep(1)
    return None


def _fetch_google_finance_ticker(gf_symbol: str) -> Optional[Tuple[float, float]]:
    """Scrape index/forex/commodity price from Google Finance.
    Returns (price, prev_close) or None."""
    url = f"https://www.google.com/finance/quote/{gf_symbol}"
    for attempt in range(2):
        try:
            resp = _requests.get(url, headers=_GOOGLE_HEADERS, timeout=10)
            if resp.status_code == 200:
                match = re.search(r'data-last-price="([\d,.]+)"', resp.text)
                prev_match = re.search(r'data-previous-close="([\d,.]+)"', resp.text)
                if match:
                    price = float(match.group(1).replace(",", ""))
                    prev = float(prev_match.group(1).replace(",", "")) if prev_match else 0
                    return (price, prev)
        except Exception:
            pass
        if attempt < 1:
            time.sleep(1)
    return None


# ═══════════════════════════════════════════════════════════
#  FETCH MULTIPLE — batched with multi-source fallback
# ═══════════════════════════════════════════════════════════

def _fetch_via_zerodha(symbols: List[Tuple[str, str]]) -> Dict[str, dict]:
    """Try Zerodha Kite Connect for all symbols.
    Returns {sym.exch: {price, day_change, day_change_pct, volume, ...}}."""
    if not zerodha_service.is_session_valid():
        return {}
    try:
        quotes = zerodha_service.fetch_quotes(symbols)
        if quotes:
            ok = sum(1 for v in quotes.values() if v.get("price", 0) > 0)
            print(f"[StockService] Zerodha: {ok}/{len(symbols)} quotes")
        return quotes
    except Exception as e:
        print(f"[StockService] Zerodha error: {e}")
        return {}


def fetch_multiple(symbols: List[Tuple[str, str]]) -> Dict[str, StockLiveData]:
    """Fetch prices: Zerodha → yfinance → Google Finance → saved JSON → xlsx."""
    results: Dict[str, StockLiveData] = {}
    need: List[Tuple[str, str]] = []

    # 1. Serve from cache
    for sym, exch in symbols:
        key = f"{sym}.{exch}"
        c = _cache_get(key)
        if c:
            results[key] = c
        else:
            need.append((sym, exch))

    if not need:
        return results

    # ── SOURCE 1: ZERODHA KITE CONNECT (primary) ──────────
    zerodha_prices: Dict[str, dict] = {}
    still_need: List[Tuple[str, str]] = []

    if zerodha_service.is_session_valid():
        zerodha_prices = _fetch_via_zerodha(need)

    to_save: Dict[str, dict] = {}

    for sym, exch in need:
        key = f"{sym}.{exch}"
        zq = zerodha_prices.get(key)
        if zq and zq.get("price", 0) > 0:
            data = StockLiveData(
                symbol=sym, exchange=exch,
                name=zq.get("name") or db._name_map.get(sym, sym),
                current_price=round(zq["price"], 2),
                week_52_high=float(zq.get("week_52_high", 0) or 0),
                week_52_low=float(zq.get("week_52_low", 0) or 0),
                day_change=float(zq.get("day_change", 0) or 0),
                day_change_pct=float(zq.get("day_change_pct", 0) or 0),
                volume=int(zq.get("volume", 0) or 0),
                previous_close=float(zq.get("close", 0) or 0),
                is_manual=False,
            )
            _cache_set(key, data)
            results[key] = data
            to_save[key] = {
                "price": data.current_price,
                "name": data.name,
                "week_52_high": data.week_52_high,
                "week_52_low": data.week_52_low,
                "day_change": data.day_change,
                "day_change_pct": data.day_change_pct,
                "volume": data.volume,
                "previous_close": data.previous_close,
            }
        else:
            still_need.append((sym, exch))

    # Save Zerodha prices to JSON immediately
    if to_save:
        _save_prices_file(to_save)

    if not still_need:
        zerodha_got = len(need) - len(still_need)
        if zerodha_got > 0:
            print(f"[StockService] All {zerodha_got} prices from Zerodha")
        return results

    # ── SOURCE 2 & 3: YAHOO / GOOGLE (only if ENABLE_YAHOO_GOOGLE) ──
    ymap: Dict[str, Tuple[str, str]] = {}
    all_prices: Dict[str, float] = {}

    if ENABLE_YAHOO_GOOGLE:
        for sym, exch in still_need:
            ys = _yahoo_sym(sym, exch)
            ymap[ys] = (sym, exch)

        all_ys = list(ymap.keys())

        # Yahoo Finance
        total_batches = (len(all_ys) + BATCH_SIZE - 1) // BATCH_SIZE
        for i in range(0, len(all_ys), BATCH_SIZE):
            batch = all_ys[i:i + BATCH_SIZE]
            bnum = (i // BATCH_SIZE) + 1

            prices = _download_batch_with_retry(batch)
            all_prices.update(prices)
            print(f"[StockService] Yahoo batch {bnum}/{total_batches}: "
                  f"{len(prices)}/{len(batch)} OK")

            if i + BATCH_SIZE < len(all_ys):
                time.sleep(random.uniform(*BATCH_DELAY))

        yahoo_got = len(all_prices)
        if yahoo_got > 0:
            print(f"[StockService] Yahoo total: {yahoo_got}/{len(all_ys)}")

        # Google Finance fallback
        missing_from_yahoo = [ys for ys in all_ys if ys not in all_prices]
        if missing_from_yahoo:
            gf_got = 0
            for ys in missing_from_yahoo:
                sym, exch = ymap[ys]
                gf_price = _fetch_google_finance_price(sym, exch)
                if gf_price and gf_price > 0:
                    all_prices[ys] = gf_price
                    gf_got += 1
                time.sleep(random.uniform(0.3, 0.8))
            if gf_got > 0:
                print(f"[StockService] Google Finance: {gf_got}/{len(missing_from_yahoo)}")
    else:
        # Build ymap for the fallback chain below (stale cache / JSON / xlsx)
        for sym, exch in still_need:
            ys = _yahoo_sym(sym, exch)
            ymap[ys] = (sym, exch)
        if still_need:
            missed = [f"{s}.{e}" for s, e in still_need]
            print(f"[StockService] {len(still_need)} stocks not on Zerodha — "
                  f"fallback: {', '.join(missed)}")

    # ── BUILD RESULTS + fallback chain ─────────────────────
    yahoo_save: Dict[str, dict] = {}

    for ys, (sym, exch) in ymap.items():
        key = f"{sym}.{exch}"
        price = all_prices.get(ys)

        if price and price > 0:
            idx = _xlsx_idx.get(sym, {})
            data = StockLiveData(
                symbol=sym, exchange=exch,
                name=db._name_map.get(sym, sym),
                current_price=round(price, 2),
                week_52_high=idx.get("w52h", 0),
                week_52_low=idx.get("w52l", 0),
                day_change=0, day_change_pct=0,
                volume=0, previous_close=0,
                is_manual=False,
            )
            _cache_set(key, data)
            results[key] = data
            yahoo_save[key] = {
                "price": data.current_price,
                "name": data.name,
                "week_52_high": data.week_52_high,
                "week_52_low": data.week_52_low,
            }
        else:
            # Try stale cache → saved JSON → xlsx
            stale = _cache_get_stale(key)
            if stale:
                results[key] = stale
            else:
                fb = _file_fallback(sym, exch) or _xlsx_fallback(sym, exch)
                if fb:
                    _cache_set(key, fb)
                    results[key] = fb

    if yahoo_save:
        _save_prices_file(yahoo_save)

    return results


# ═══════════════════════════════════════════════════════════
#  CACHED-ONLY PRICES (no network — instant)
# ═══════════════════════════════════════════════════════════

def get_cached_prices(symbols: List[Tuple[str, str]]) -> Dict[str, StockLiveData]:
    """Return prices from local sources ONLY: memory cache → JSON file → xlsx.
    Never makes network calls.  Used by GET endpoints to respond instantly."""
    results: Dict[str, StockLiveData] = {}
    need_file: List[Tuple[str, str]] = []

    # ── Pass 1: serve from memory cache (fast, no I/O) ──
    for sym, exch in symbols:
        key = f"{sym}.{exch}"
        # 1. Memory cache (hot)
        c = _cache_get(key)
        if c:
            results[key] = c
            continue
        # 2. Stale cache
        stale = _cache_get_stale(key)
        if stale:
            results[key] = stale
            continue
        need_file.append((sym, exch))

    if not need_file:
        return results

    # ── Pass 2: load JSON file ONCE for all remaining stocks ──
    saved = _load_prices_file()
    need_xlsx: List[Tuple[str, str]] = []

    for sym, exch in need_file:
        key = f"{sym}.{exch}"
        info = saved.get(key)
        if info and float(info.get("price", 0)) > 0:
            data = StockLiveData(
                symbol=sym, exchange=exch,
                name=info.get("name", db._name_map.get(sym, sym)),
                current_price=round(float(info["price"]), 2),
                week_52_high=float(info.get("week_52_high", 0) or 0),
                week_52_low=float(info.get("week_52_low", 0) or 0),
                day_change=float(info.get("day_change", 0) or 0),
                day_change_pct=float(info.get("day_change_pct", 0) or 0),
                volume=int(info.get("volume", 0) or 0),
                previous_close=float(info.get("previous_close", 0) or 0),
                is_manual=True,
            )
            _cache_set(key, data)
            results[key] = data
            continue

        # Try alternate exchange (BSE→NSE or NSE→BSE) from same JSON
        alt_exch = "NSE" if exch.upper() == "BSE" else "BSE"
        alt_key = f"{sym}.{alt_exch}"
        alt_info = saved.get(alt_key)
        if alt_info and float(alt_info.get("price", 0)) > 0:
            data = StockLiveData(
                symbol=sym, exchange=exch,
                name=alt_info.get("name", db._name_map.get(sym, sym)),
                current_price=round(float(alt_info["price"]), 2),
                week_52_high=float(alt_info.get("week_52_high", 0) or 0),
                week_52_low=float(alt_info.get("week_52_low", 0) or 0),
                day_change=float(alt_info.get("day_change", 0) or 0),
                day_change_pct=float(alt_info.get("day_change_pct", 0) or 0),
                volume=int(alt_info.get("volume", 0) or 0),
                previous_close=float(alt_info.get("previous_close", 0) or 0),
                is_manual=True,
            )
            _cache_set(key, data)
            results[key] = data
            continue

        need_xlsx.append((sym, exch))

    # ── Pass 3: xlsx Index sheet fallback (per-symbol, opens only needed file) ──
    for sym, exch in need_xlsx:
        key = f"{sym}.{exch}"
        xf = _xlsx_fallback(sym, exch)
        if xf:
            _cache_set(key, xf)
            results[key] = xf
    return results


# ═══════════════════════════════════════════════════════════
#  SINGLE FETCH
# ═══════════════════════════════════════════════════════════

def fetch_live_data(symbol: str, exchange: str = "NSE") -> Optional[StockLiveData]:
    key = f"{symbol}.{exchange}"
    c = _cache_get(key)
    if c:
        return c
    res = fetch_multiple([(symbol, exchange)])
    return res.get(key)


# ═══════════════════════════════════════════════════════════
#  MARKET TICKER (indices, forex, commodities)
# ═══════════════════════════════════════════════════════════

# Google Finance symbols for market tickers
_GF_TICKER_MAP = {
    "SENSEX":   "SENSEX:INDEXBOM",
    "NIFTY50":  "NIFTY_50:INDEXNSE",
    "SGX":      "STI:INDEXSES",
    "NIKKEI":   "NI225:INDEXNIKKEI",
    "SGDINR":   "SGD-INR",
    "USDINR":   "USD-INR",
    "GOLD":     "GC=F:NYCOMEX",
    "SILVER":   "SI=F:NYCOMEX",
    "CRUDEOIL": "CL=F:NYMEX",
}


def fetch_market_ticker(meta: dict) -> dict:
    """Fetch a single market ticker via Yahoo/Google Finance.
    Only runs if ENABLE_YAHOO_GOOGLE is True, otherwise returns placeholder."""
    from urllib.parse import unquote
    placeholder = {
        "key": meta["key"], "label": meta["label"],
        "type": meta.get("type", "index"), "unit": meta.get("unit", ""),
        "price": 0, "change": 0, "change_pct": 0,
    }

    if not ENABLE_YAHOO_GOOGLE:
        return placeholder

    # Source 1: yfinance with retry
    yf_sym = unquote(meta["yahoo"])
    for attempt in range(MAX_RETRIES):
        try:
            ticker = yf.Ticker(yf_sym)
            hist = ticker.history(period="5d")
            if hist is not None and not hist.empty:
                closes = hist["Close"].dropna()
                if len(closes) > 0:
                    price = float(closes.iloc[-1])
                    prev = float(closes.iloc[-2]) if len(closes) >= 2 else 0
                    change = price - prev if prev > 0 else 0
                    pct = (change / prev * 100) if prev > 0 else 0
                    return {
                        "key": meta["key"], "label": meta["label"],
                        "type": meta.get("type", "index"),
                        "unit": meta.get("unit", ""),
                        "price": round(price, 2),
                        "change": round(change, 2),
                        "change_pct": round(pct, 2),
                    }
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                print(f"[MarketTicker] Yahoo failed for {meta['key']}: {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep((attempt + 1) * 1.5 + random.uniform(0, 0.5))

    # Source 2: Google Finance scraping
    gf_sym = _GF_TICKER_MAP.get(meta["key"])
    if gf_sym:
        result = _fetch_google_finance_ticker(gf_sym)
        if result:
            price, prev = result
            change = price - prev if prev > 0 else 0
            pct = (change / prev * 100) if prev > 0 else 0
            return {
                "key": meta["key"], "label": meta["label"],
                "type": meta.get("type", "index"),
                "unit": meta.get("unit", ""),
                "price": round(price, 2),
                "change": round(change, 2),
                "change_pct": round(pct, 2),
            }

    return placeholder


# ═══════════════════════════════════════════════════════════
#  BULK PRICE UPDATE (external push)
# ═══════════════════════════════════════════════════════════

def bulk_update_prices(prices: Dict[str, dict]):
    updated = 0
    to_save: Dict[str, dict] = {}
    for sym, info in prices.items():
        exch = info.get("exchange", "NSE")
        price = float(info.get("price", 0))
        if price <= 0:
            continue
        key = f"{sym}.{exch}"
        data = StockLiveData(
            symbol=sym, exchange=exch,
            name=info.get("name", db._name_map.get(sym, sym)),
            current_price=round(price, 2),
            week_52_high=float(info.get("week_52_high", 0) or 0),
            week_52_low=float(info.get("week_52_low", 0) or 0),
            day_change=float(info.get("day_change", 0) or 0),
            day_change_pct=float(info.get("day_change_pct", 0) or 0),
            volume=int(info.get("volume", 0) or 0),
            previous_close=float(info.get("previous_close", 0) or 0),
            is_manual=True,
        )
        _cache_set(key, data)
        to_save[key] = {
            "price": data.current_price,
            "name": data.name,
            "week_52_high": data.week_52_high,
            "week_52_low": data.week_52_low,
            "day_change": data.day_change,
            "day_change_pct": data.day_change_pct,
            "volume": data.volume,
            "previous_close": data.previous_close,
        }
        updated += 1
    if to_save:
        _save_prices_file(to_save)
    print(f"[StockService] Bulk updated {updated} prices (saved to file)")
    return updated


# ═══════════════════════════════════════════════════════════
#  BACKGROUND REFRESH
# ═══════════════════════════════════════════════════════════

_bg_thread: Optional[threading.Thread] = None
_bg_running = False
_last_refresh_time = 0.0
_last_refresh_status = "not_started"
_refresh_lock = threading.Lock()


def _bg_loop():
    global _last_refresh_time, _last_refresh_status
    print(f"[StockService] Background refresh started (every {REFRESH_INTERVAL}s)")
    while _bg_running:
        try:
            # Re-scan dumps/ folder for new/modified xlsx files
            db.reindex()
            holdings = db.get_all_holdings()
            if not holdings:
                with _refresh_lock:
                    _last_refresh_status = "no_holdings"
                    _last_refresh_time = time.time()
            else:
                syms = list(set((h.symbol, h.exchange) for h in holdings))
                with _refresh_lock:
                    _last_refresh_status = "refreshing"
                # Clear cache to force fresh fetch
                with _cache_lock:
                    _cache.clear()
                res = fetch_multiple(syms)
                live_keys = sorted(k for k, v in res.items() if not v.is_manual)
                fb_keys = sorted(k for k, v in res.items() if v.is_manual)
                live = len(live_keys)
                fb = len(fb_keys)
                with _refresh_lock:
                    _last_refresh_time = time.time()
                    _last_refresh_status = (
                        f"ok: {live} live, {fb} fallback / {len(syms)}")
                print(f"[StockService] Refresh: {live} zerodha, {fb} cached / {len(syms)} stocks")
                if fb_keys:
                    print(f"[StockService] Cached stocks: {', '.join(fb_keys)}")
        except Exception as e:
            print(f"[StockService] Refresh error: {e}")
            with _refresh_lock:
                _last_refresh_status = f"error: {e}"
                _last_refresh_time = time.time()

        for _ in range(REFRESH_INTERVAL):
            if not _bg_running:
                break
            time.sleep(1)


def start_background_refresh():
    global _bg_thread, _bg_running
    if _bg_running:
        return
    _bg_running = True
    _bg_thread = threading.Thread(target=_bg_loop, daemon=True)
    _bg_thread.start()


def stop_background_refresh():
    global _bg_running
    _bg_running = False


def get_refresh_status() -> dict:
    with _refresh_lock:
        return {
            "status": _last_refresh_status,
            "last_refresh": _last_refresh_time,
            "seconds_ago": (round(time.time() - _last_refresh_time, 1)
                            if _last_refresh_time > 0 else None),
            "cache_size": len(_cache),
            "refresh_interval": REFRESH_INTERVAL,
        }


def _reset_circuit():
    pass


def search_stock(query: str, exchange: str = "NSE") -> list:
    ys = _yahoo_sym(query, exchange)
    try:
        t = yf.Ticker(ys)
        info = t.info
        if info and info.get("shortName"):
            return [{"symbol": query.upper(),
                      "name": info["shortName"],
                      "exchange": exchange}]
    except Exception:
        pass
    return []


def clear_cache():
    with _cache_lock:
        _cache.clear()
