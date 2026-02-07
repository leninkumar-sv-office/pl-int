"""
Stock data service using Yahoo Finance + manual price fallback.

Includes:
- TTL-based cache (5 min) to avoid hammering Yahoo Finance
- Batch download via yf.download() for current prices
- Circuit breaker: if Yahoo returns 429, stop all calls for a cooldown
- Graceful fallback to xlsx Index sheet data when Yahoo is unavailable
"""
import time
import threading
import yfinance as yf
from typing import Optional, Dict, List, Tuple
from .models import StockLiveData
from .xlsx_database import xlsx_db as db

# ═══════════════════════════════════════════════════════════
#  TTL CACHE  (5-minute default)
# ═══════════════════════════════════════════════════════════

CACHE_TTL_SECONDS = 300  # 5 minutes

_price_cache: Dict[str, Tuple[float, StockLiveData]] = {}  # key → (timestamp, data)
_cache_lock = threading.Lock()


def _cache_get(key: str) -> Optional[StockLiveData]:
    """Get from cache if not expired."""
    with _cache_lock:
        if key in _price_cache:
            ts, data = _price_cache[key]
            if time.time() - ts < CACHE_TTL_SECONDS:
                return data
            del _price_cache[key]
    return None


def _cache_set(key: str, data: StockLiveData):
    """Store in cache with current timestamp."""
    with _cache_lock:
        _price_cache[key] = (time.time(), data)


# ═══════════════════════════════════════════════════════════
#  CIRCUIT BREAKER  (stop calling Yahoo after 429 errors)
# ═══════════════════════════════════════════════════════════

_CIRCUIT_COOLDOWN = 120  # seconds to wait after a 429
_circuit_open_until = 0.0  # timestamp when circuit breaker closes
_circuit_lock = threading.Lock()


def _is_circuit_open() -> bool:
    """Check if circuit breaker is tripped (Yahoo is rate-limiting us)."""
    with _circuit_lock:
        return time.time() < _circuit_open_until


def _trip_circuit():
    """Trip the circuit breaker after a 429 error."""
    global _circuit_open_until
    with _circuit_lock:
        _circuit_open_until = time.time() + _CIRCUIT_COOLDOWN
        print(f"[StockService] Circuit breaker tripped — pausing Yahoo calls for {_CIRCUIT_COOLDOWN}s")


# ═══════════════════════════════════════════════════════════
#  XLSX INDEX SHEET FALLBACK
# ═══════════════════════════════════════════════════════════

# Cache for xlsx Index sheet data (populated once at startup)
_xlsx_index_cache: Dict[str, dict] = {}  # symbol → {current_price, week_52_high, week_52_low}
_xlsx_cache_built = False


def _build_xlsx_index_cache():
    """Read all xlsx Index sheets once and cache the data."""
    global _xlsx_cache_built
    if _xlsx_cache_built:
        return

    import openpyxl
    from .xlsx_database import _extract_index_data

    for symbol, filepath in db._file_map.items():
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True)
            idx = _extract_index_data(wb)
            wb.close()
            _xlsx_index_cache[symbol] = {
                "current_price": float(idx.get("current_price", 0) or 0),
                "week_52_high": float(idx.get("week_52_high", 0) or 0),
                "week_52_low": float(idx.get("week_52_low", 0) or 0),
            }
        except Exception:
            _xlsx_index_cache[symbol] = {"current_price": 0, "week_52_high": 0, "week_52_low": 0}

    _xlsx_cache_built = True
    prices_found = sum(1 for v in _xlsx_index_cache.values() if v["current_price"] > 0)
    print(f"[StockService] Loaded xlsx Index data for {len(_xlsx_index_cache)} stocks ({prices_found} with prices)")


def _get_xlsx_fallback(symbol: str, exchange: str) -> Optional[StockLiveData]:
    """Build StockLiveData from xlsx Index sheet data."""
    _build_xlsx_index_cache()
    idx = _xlsx_index_cache.get(symbol, {})
    price = idx.get("current_price", 0)

    # Also try manual price
    if price <= 0:
        manual_price = db.get_manual_price(symbol, exchange)
        if manual_price and manual_price > 0:
            price = manual_price

    if price <= 0:
        return None

    data = StockLiveData(
        symbol=symbol,
        exchange=exchange,
        name=db._name_map.get(symbol, symbol),
        current_price=round(price, 2),
        week_52_high=idx.get("week_52_high", 0),
        week_52_low=idx.get("week_52_low", 0),
        day_change=0,
        day_change_pct=0,
        volume=0,
        previous_close=0,
        is_manual=True,
    )
    return data


# ═══════════════════════════════════════════════════════════
#  YAHOO FINANCE HELPERS
# ═══════════════════════════════════════════════════════════

_RATE_LIMIT_DELAY = 0.5  # seconds between individual calls
_last_call_time = 0.0
_rate_lock = threading.Lock()


def _rate_limit():
    """Enforce minimum delay between Yahoo Finance calls."""
    global _last_call_time
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_call_time
        if elapsed < _RATE_LIMIT_DELAY:
            time.sleep(_RATE_LIMIT_DELAY - elapsed)
        _last_call_time = time.time()


def _get_yahoo_symbol(symbol: str, exchange: str) -> str:
    """Convert symbol + exchange to Yahoo Finance format."""
    suffix = ".NS" if exchange.upper() == "NSE" else ".BO"
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}{suffix}"


# ═══════════════════════════════════════════════════════════
#  SINGLE STOCK FETCH
# ═══════════════════════════════════════════════════════════

def fetch_live_data(symbol: str, exchange: str = "NSE") -> Optional[StockLiveData]:
    """
    Fetch live stock data from Yahoo Finance.
    Respects circuit breaker. Falls back to xlsx/manual price.
    """
    cache_key = f"{symbol}.{exchange}"

    # Check cache first
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # If circuit breaker is open, skip Yahoo entirely
    if _is_circuit_open():
        return _get_xlsx_fallback(symbol, exchange)

    yahoo_symbol = _get_yahoo_symbol(symbol, exchange)
    _rate_limit()

    try:
        ticker = yf.Ticker(yahoo_symbol)
        info = ticker.info

        if not info or "regularMarketPrice" not in info or info.get("regularMarketPrice") is None:
            try:
                fast = ticker.fast_info
                current_price = float(fast.get("lastPrice", 0) or fast.get("last_price", 0))
                if current_price <= 0:
                    raise ValueError("No price data")

                data = StockLiveData(
                    symbol=symbol,
                    exchange=exchange,
                    name=info.get("shortName", info.get("longName", symbol)),
                    current_price=current_price,
                    week_52_high=float(fast.get("yearHigh", fast.get("year_high", 0)) or 0),
                    week_52_low=float(fast.get("yearLow", fast.get("year_low", 0)) or 0),
                    day_change=0,
                    day_change_pct=0,
                    volume=int(fast.get("lastVolume", fast.get("last_volume", 0)) or 0),
                    previous_close=float(fast.get("previousClose", fast.get("previous_close", 0)) or 0),
                    is_manual=False,
                )
                _cache_set(cache_key, data)
                return data
            except Exception:
                pass

            return _get_xlsx_fallback(symbol, exchange)

        current_price = float(info.get("regularMarketPrice", 0) or info.get("currentPrice", 0))
        previous_close = float(info.get("regularMarketPreviousClose", 0) or info.get("previousClose", 0))
        day_change = current_price - previous_close if previous_close else 0
        day_change_pct = (day_change / previous_close * 100) if previous_close else 0

        live_data = StockLiveData(
            symbol=symbol,
            exchange=exchange,
            name=info.get("shortName", info.get("longName", symbol)),
            current_price=current_price,
            week_52_high=float(info.get("fiftyTwoWeekHigh", 0) or 0),
            week_52_low=float(info.get("fiftyTwoWeekLow", 0) or 0),
            day_change=round(day_change, 2),
            day_change_pct=round(day_change_pct, 2),
            volume=int(info.get("regularMarketVolume", 0) or 0),
            previous_close=previous_close,
            is_manual=False,
        )

        _cache_set(cache_key, live_data)
        return live_data

    except Exception as e:
        err_str = str(e)
        print(f"Yahoo Finance error for {yahoo_symbol}: {e}")

        # Detect 429 and trip circuit breaker
        if "429" in err_str or "Too Many Requests" in err_str:
            _trip_circuit()

        return _get_xlsx_fallback(symbol, exchange)


# ═══════════════════════════════════════════════════════════
#  BATCH FETCH  (the big performance win)
# ═══════════════════════════════════════════════════════════

def fetch_multiple(symbols: List[Tuple[str, str]]) -> Dict[str, StockLiveData]:
    """
    Fetch live data for multiple stocks efficiently.

    Strategy:
    1. Return cached data for symbols still within TTL
    2. If circuit breaker open → use xlsx Index sheet data for everything
    3. Batch-download current prices via yf.download()
    4. For anything batch missed → xlsx fallback (NO individual Yahoo calls)
    """
    results: Dict[str, StockLiveData] = {}
    uncached: List[Tuple[str, str]] = []

    # Step 1: serve from cache
    for symbol, exchange in symbols:
        cache_key = f"{symbol}.{exchange}"
        cached = _cache_get(cache_key)
        if cached is not None:
            results[cache_key] = cached
        else:
            uncached.append((symbol, exchange))

    if not uncached:
        return results

    # Step 2: if circuit breaker is open, go straight to xlsx fallback
    if _is_circuit_open():
        print(f"[StockService] Circuit breaker open — using xlsx Index data for {len(uncached)} stocks")
        for symbol, exchange in uncached:
            cache_key = f"{symbol}.{exchange}"
            data = _get_xlsx_fallback(symbol, exchange)
            if data:
                _cache_set(cache_key, data)
                results[cache_key] = data
        return results

    # Step 3: batch download current prices (one HTTP request for all)
    yahoo_symbols = []
    yahoo_map: Dict[str, Tuple[str, str]] = {}
    for symbol, exchange in uncached:
        ys = _get_yahoo_symbol(symbol, exchange)
        yahoo_symbols.append(ys)
        yahoo_map[ys] = (symbol, exchange)

    batch_prices: Dict[str, float] = {}
    batch_failed = False

    try:
        tickers_str = " ".join(yahoo_symbols)
        df = yf.download(tickers_str, period="5d", progress=False, threads=True)

        if df is not None and not df.empty:
            if len(yahoo_symbols) == 1:
                ys = yahoo_symbols[0]
                close_col = df["Close"] if "Close" in df.columns else None
                if close_col is not None and len(close_col) > 0:
                    last_price = float(close_col.dropna().iloc[-1])
                    if last_price > 0:
                        batch_prices[ys] = last_price
            else:
                close_df = df["Close"] if "Close" in df.columns else None
                if close_df is not None:
                    for ys in yahoo_symbols:
                        try:
                            col = close_df[ys] if ys in close_df.columns else None
                            if col is not None and len(col.dropna()) > 0:
                                last_price = float(col.dropna().iloc[-1])
                                if last_price > 0:
                                    batch_prices[ys] = last_price
                        except (KeyError, IndexError):
                            continue

        print(f"[StockService] Batch downloaded {len(batch_prices)}/{len(yahoo_symbols)} prices")

    except Exception as e:
        err_str = str(e)
        print(f"[StockService] Batch download failed: {e}")
        batch_failed = True
        if "429" in err_str or "Too Many Requests" in err_str:
            _trip_circuit()

    # Step 4: build results — batch prices or xlsx fallback (NO individual Yahoo calls)
    _build_xlsx_index_cache()  # ensure xlsx cache is ready

    for ys, (symbol, exchange) in yahoo_map.items():
        cache_key = f"{symbol}.{exchange}"
        price = batch_prices.get(ys)

        if price and price > 0:
            idx = _xlsx_index_cache.get(symbol, {})
            w52_high = idx.get("week_52_high", 0)
            w52_low = idx.get("week_52_low", 0)

            data = StockLiveData(
                symbol=symbol,
                exchange=exchange,
                name=db._name_map.get(symbol, symbol),
                current_price=round(price, 2),
                week_52_high=w52_high,
                week_52_low=w52_low,
                day_change=0,
                day_change_pct=0,
                volume=0,
                previous_close=0,
                is_manual=False,
            )
            _cache_set(cache_key, data)
            results[cache_key] = data
        else:
            # Xlsx fallback — do NOT call Yahoo individually
            data = _get_xlsx_fallback(symbol, exchange)
            if data:
                _cache_set(cache_key, data)
                results[cache_key] = data

    return results


# ═══════════════════════════════════════════════════════════
#  MANUAL PRICE FALLBACK
# ═══════════════════════════════════════════════════════════

def _get_manual_fallback(symbol: str, exchange: str) -> Optional[StockLiveData]:
    """Fall back to manually entered price (legacy, used by fetch_live_data)."""
    return _get_xlsx_fallback(symbol, exchange)


# ═══════════════════════════════════════════════════════════
#  OTHER
# ═══════════════════════════════════════════════════════════

def search_stock(query: str, exchange: str = "NSE") -> list:
    """Search for stocks by name or symbol."""
    if _is_circuit_open():
        return []
    yahoo_symbol = _get_yahoo_symbol(query, exchange)
    _rate_limit()
    try:
        ticker = yf.Ticker(yahoo_symbol)
        info = ticker.info
        if info and info.get("shortName"):
            return [{
                "symbol": query.upper(),
                "name": info.get("shortName", info.get("longName", query)),
                "exchange": exchange,
            }]
    except Exception as e:
        if "429" in str(e):
            _trip_circuit()
    return []


def clear_cache():
    """Clear the price cache."""
    with _cache_lock:
        _price_cache.clear()
