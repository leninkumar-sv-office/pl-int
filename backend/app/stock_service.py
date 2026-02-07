"""
Stock data service — yfinance with small-batch downloads (5 tickers per call).

Key fix: instead of downloading 60+ tickers in one shot (which triggers Yahoo
throttling), we break into batches of 5 with 2-3s delays between batches.
"""
import time
import threading
import random
import yfinance as yf
from typing import Optional, Dict, List, Tuple
from .models import StockLiveData
from .xlsx_database import xlsx_db as db

# ═══════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════

CACHE_TTL = 300           # 5 min cache
BATCH_SIZE = 5            # tickers per yf.download()
BATCH_DELAY = (2.0, 3.5)  # random delay between batches (min, max)
REFRESH_INTERVAL = 300    # background refresh every 5 min

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
#  XLSX FALLBACK (last resort)
# ═══════════════════════════════════════════════════════════

_xlsx_idx: Dict[str, dict] = {}
_xlsx_built = False


def _build_xlsx():
    global _xlsx_built
    if _xlsx_built:
        return
    import openpyxl
    from .xlsx_database import _extract_index_data
    for sym, fp in db._file_map.items():
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


def _xlsx_fallback(symbol: str, exchange: str) -> Optional[StockLiveData]:
    _build_xlsx()
    idx = _xlsx_idx.get(symbol, {})
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
#  YAHOO HELPERS
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


# ═══════════════════════════════════════════════════════════
#  FETCH MULTIPLE — batched
# ═══════════════════════════════════════════════════════════

def fetch_multiple(symbols: List[Tuple[str, str]]) -> Dict[str, StockLiveData]:
    """Fetch prices in batches of BATCH_SIZE with delays."""
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

    # 2. Build yahoo map
    ymap: Dict[str, Tuple[str, str]] = {}
    for sym, exch in need:
        ys = _yahoo_sym(sym, exch)
        ymap[ys] = (sym, exch)

    all_ys = list(ymap.keys())
    all_prices: Dict[str, float] = {}

    # 3. Batch download
    total_batches = (len(all_ys) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(all_ys), BATCH_SIZE):
        batch = all_ys[i:i + BATCH_SIZE]
        bnum = (i // BATCH_SIZE) + 1

        prices = _download_batch(batch)
        all_prices.update(prices)
        print(f"[StockService] Batch {bnum}/{total_batches}: {len(prices)}/{len(batch)} OK")

        # Delay between batches
        if i + BATCH_SIZE < len(all_ys):
            time.sleep(random.uniform(*BATCH_DELAY))

    got = len(all_prices)
    print(f"[StockService] Total: {got}/{len(all_ys)} from Yahoo")

    # 4. Build results
    _build_xlsx()
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
        else:
            stale = _cache_get_stale(key)
            if stale:
                results[key] = stale
            else:
                fb = _xlsx_fallback(sym, exch)
                if fb:
                    _cache_set(key, fb)
                    results[key] = fb

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

def fetch_market_ticker(meta: dict) -> dict:
    """Fetch a single market ticker via yfinance."""
    from urllib.parse import unquote
    placeholder = {
        "key": meta["key"], "label": meta["label"],
        "type": meta.get("type", "index"), "unit": meta.get("unit", ""),
        "price": 0, "change": 0, "change_pct": 0,
    }
    yf_sym = unquote(meta["yahoo"])
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
                    "type": meta.get("type", "index"), "unit": meta.get("unit", ""),
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "change_pct": round(pct, 2),
                }
    except Exception as e:
        print(f"[MarketTicker] {meta['key']}: {e}")
    return placeholder


# ═══════════════════════════════════════════════════════════
#  BULK PRICE UPDATE (external push)
# ═══════════════════════════════════════════════════════════

def bulk_update_prices(prices: Dict[str, dict]):
    updated = 0
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
        updated += 1
    print(f"[StockService] Bulk updated {updated} prices")
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
            holdings = db.get_all_holdings()
            if not holdings:
                with _refresh_lock:
                    _last_refresh_status = "no_holdings"
                    _last_refresh_time = time.time()
            else:
                syms = list(set((h.symbol, h.exchange) for h in holdings))
                with _refresh_lock:
                    _last_refresh_status = "refreshing"
                # Clear cache
                with _cache_lock:
                    _cache.clear()
                res = fetch_multiple(syms)
                live = sum(1 for v in res.values() if not v.is_manual)
                fb = sum(1 for v in res.values() if v.is_manual)
                with _refresh_lock:
                    _last_refresh_time = time.time()
                    _last_refresh_status = f"ok: {live} live, {fb} fallback / {len(syms)}"
                print(f"[StockService] Refresh: {live} live, {fb} fallback")
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
            "seconds_ago": round(time.time() - _last_refresh_time, 1) if _last_refresh_time > 0 else None,
            "cache_size": len(_cache),
            "refresh_interval": REFRESH_INTERVAL,
        }


def _reset_circuit():
    pass  # No circuit breaker in simplified version


def search_stock(query: str, exchange: str = "NSE") -> list:
    ys = _yahoo_sym(query, exchange)
    try:
        t = yf.Ticker(ys)
        info = t.info
        if info and info.get("shortName"):
            return [{"symbol": query.upper(), "name": info["shortName"], "exchange": exchange}]
    except Exception:
        pass
    return []


def clear_cache():
    with _cache_lock:
        _cache.clear()
