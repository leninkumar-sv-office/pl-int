"""
Stock Portfolio Dashboard - FastAPI Backend
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict
from datetime import date
import os
import uuid
import time
import threading

from .models import (
    AddStockRequest, SellStockRequest, AddDividendRequest, ManualPriceRequest,
    Holding, SoldPosition, StockLiveData,
    PortfolioSummary, HoldingWithLive, StockSummaryItem,
)
from .xlsx_database import xlsx_db as db
from . import stock_service
from pydantic import BaseModel

app = FastAPI(title="Stock Portfolio Dashboard", version="1.0.0")


# ══════════════════════════════════════════════════════════
#  STARTUP / SHUTDOWN — background price refresh
# ══════════════════════════════════════════════════════════

@app.on_event("startup")
def on_startup():
    """Start background price refresh thread on server boot."""
    stock_service.start_background_refresh()
    print("[App] Background price refresh started")


@app.on_event("shutdown")
def on_shutdown():
    """Stop background refresh cleanly."""
    stock_service.stop_background_refresh()
    print("[App] Background price refresh stopped")

# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════
#  PORTFOLIO ENDPOINTS
# ══════════════════════════════════════════════════════════

@app.get("/api/portfolio", response_model=List[HoldingWithLive])
def get_portfolio():
    """Get all holdings with live price data."""
    holdings = db.get_all_holdings()
    if not holdings:
        return []

    # Fetch live data for all symbols
    symbols = list(set((h.symbol, h.exchange) for h in holdings))
    live_data = stock_service.fetch_multiple(symbols)

    result = []
    for h in holdings:
        key = f"{h.symbol}.{h.exchange}"
        live = live_data.get(key)

        current_price = live.current_price if live else 0
        invested = h.buy_price * h.quantity
        current_value = current_price * h.quantity
        unrealized_pl = current_value - invested
        unrealized_pl_pct = (unrealized_pl / invested * 100) if invested > 0 else 0

        result.append(HoldingWithLive(
            holding=h,
            live=live,
            unrealized_pl=round(unrealized_pl, 2),
            unrealized_pl_pct=round(unrealized_pl_pct, 2),
            current_value=round(current_value, 2),
            is_above_buy_price=current_price > h.buy_price if current_price > 0 else False,
            can_sell=h.quantity > 0,
        ))

    return result


@app.post("/api/portfolio/add", response_model=Holding)
def add_stock(req: AddStockRequest):
    """Add a new stock — inserts a Buy row in the stock's xlsx."""
    # Auto-fetch name if not provided
    name = req.name
    if not name:
        live = stock_service.fetch_live_data(req.symbol, req.exchange)
        name = live.name if live else req.symbol.upper()

    holding = Holding(
        id="temp",
        symbol=req.symbol.upper().replace(".NS", "").replace(".BO", ""),
        exchange=req.exchange.upper(),
        name=name,
        quantity=req.quantity,
        buy_price=req.buy_price,
        buy_date=req.buy_date,
        notes=req.notes,
    )

    return db.add_holding(holding)


@app.post("/api/portfolio/sell")
def sell_stock(req: SellStockRequest):
    """Sell shares from a holding — inserts a Sell row in the stock's xlsx."""
    holding = db.get_holding_by_id(req.holding_id)
    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")

    if req.quantity > holding.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot sell {req.quantity} shares, only {holding.quantity} held"
        )

    sell_date = req.sell_date or str(date.today())
    realized_pl = (req.sell_price - holding.buy_price) * req.quantity
    remaining = holding.quantity - req.quantity

    # Insert a Sell row into the stock's xlsx file
    db.add_sell_transaction(
        symbol=holding.symbol,
        exchange=holding.exchange,
        quantity=req.quantity,
        price=req.sell_price,
        sell_date=sell_date,
    )

    return {
        "message": f"Sold {req.quantity} shares of {holding.symbol}",
        "realized_pl": round(realized_pl, 2),
        "remaining_quantity": remaining,
    }


@app.delete("/api/portfolio/{holding_id}")
def delete_holding(holding_id: str):
    """Delete a holding without recording a sale."""
    if db.remove_holding(holding_id):
        return {"message": "Holding deleted"}
    raise HTTPException(status_code=404, detail="Holding not found")


# ══════════════════════════════════════════════════════════
#  DIVIDEND
# ══════════════════════════════════════════════════════════

@app.post("/api/portfolio/dividend")
def add_dividend(req: AddDividendRequest):
    """Record a dividend received for a stock."""
    dividend_date = req.dividend_date or str(date.today())
    try:
        db.add_dividend(
            symbol=req.symbol.upper(),
            exchange=req.exchange,
            amount=req.amount,
            dividend_date=dividend_date,
            remarks=req.remarks,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No xlsx file found for {req.symbol}")
    return {
        "message": f"Dividend of ₹{req.amount:.2f} recorded for {req.symbol.upper()}",
    }


# ══════════════════════════════════════════════════════════
#  STOCK-LEVEL SUMMARY (held + sold aggregation)
# ══════════════════════════════════════════════════════════

@app.get("/api/portfolio/stock-summary", response_model=List[StockSummaryItem])
def get_stock_summary():
    """Get per-stock aggregated data showing held + sold quantities."""
    holdings = db.get_all_holdings()
    sold_positions = db.get_all_sold()
    dividends_by_symbol = db.get_dividends_by_symbol()

    # Fetch live data
    symbols = list(set((h.symbol, h.exchange) for h in holdings))
    live_data = stock_service.fetch_multiple(symbols) if symbols else {}

    # Group holdings by symbol
    held_by_symbol: dict = {}
    for h in holdings:
        key = h.symbol
        if key not in held_by_symbol:
            held_by_symbol[key] = {"lots": [], "exchange": h.exchange, "name": h.name}
        held_by_symbol[key]["lots"].append(h)

    # Group sold positions by symbol
    sold_by_symbol: dict = {}
    for s in sold_positions:
        key = s.symbol
        if key not in sold_by_symbol:
            sold_by_symbol[key] = {"lots": [], "exchange": s.exchange, "name": s.name}
        sold_by_symbol[key]["lots"].append(s)

    # Combine all symbols
    all_symbols = set(list(held_by_symbol.keys()) + list(sold_by_symbol.keys()))

    result = []
    for sym in all_symbols:
        held_info = held_by_symbol.get(sym, {"lots": [], "exchange": "NSE", "name": sym})
        sold_info = sold_by_symbol.get(sym, {"lots": [], "exchange": "NSE", "name": sym})

        held_lots = held_info["lots"]
        sold_lots = sold_info["lots"]
        exchange = held_info["exchange"] if held_lots else sold_info["exchange"]
        name = held_info["name"] if held_lots else sold_info["name"]

        total_held_qty = sum(h.quantity for h in held_lots)
        total_sold_qty = sum(s.quantity for s in sold_lots)
        # total_invested = sum of column F (COST) for held lots
        total_invested = sum(
            h.buy_cost if h.buy_cost > 0 else (h.buy_price * h.quantity)
            for h in held_lots
        )
        avg_buy_price = (total_invested / total_held_qty) if total_held_qty > 0 else 0
        # avg_price = weighted average of raw transaction price (column E)
        avg_price = (
            sum(h.price * h.quantity for h in held_lots) / total_held_qty
        ) if total_held_qty > 0 else 0
        realized_pl = sum(s.realized_pl for s in sold_lots)

        # Live data
        live_key = f"{sym}.{exchange}"
        live = live_data.get(live_key)
        current_price = live.current_price if live else 0
        current_value = current_price * total_held_qty
        unrealized_pl = current_value - total_invested
        unrealized_pl_pct = (unrealized_pl / total_invested * 100) if total_invested > 0 else 0

        # Per-lot profitability: split into profitable vs loss lots
        profitable_qty = 0
        loss_qty = 0
        unrealized_profit = 0.0  # P&L sum from lots where current > buy
        unrealized_loss = 0.0    # P&L sum from lots where current <= buy
        if current_price > 0:
            for h in held_lots:
                lot_pl = (current_price - h.buy_price) * h.quantity
                if current_price > h.buy_price:
                    profitable_qty += h.quantity
                    unrealized_profit += lot_pl
                else:
                    loss_qty += h.quantity
                    unrealized_loss += lot_pl

        result.append(StockSummaryItem(
            symbol=sym,
            exchange=exchange,
            name=name,
            total_held_qty=total_held_qty,
            total_sold_qty=total_sold_qty,
            avg_price=round(avg_price, 2),
            avg_buy_price=round(avg_buy_price, 2),
            total_invested=round(total_invested, 2),
            current_value=round(current_value, 2),
            unrealized_pl=round(unrealized_pl, 2),
            unrealized_pl_pct=round(unrealized_pl_pct, 2),
            unrealized_profit=round(unrealized_profit, 2),
            unrealized_loss=round(unrealized_loss, 2),
            realized_pl=round(realized_pl, 2),
            total_dividend=round(dividends_by_symbol.get(sym, {}).get("amount", 0), 2),
            dividend_count=dividends_by_symbol.get(sym, {}).get("count", 0),
            dividend_units=dividends_by_symbol.get(sym, {}).get("units", 0),
            num_held_lots=len(held_lots),
            num_sold_lots=len(sold_lots),
            profitable_qty=profitable_qty,
            loss_qty=loss_qty,
            live=live,
            is_above_avg_buy=current_price > avg_buy_price if current_price > 0 and avg_buy_price > 0 else False,
        ))

    # Sort: stocks with held shares first, then by unrealized P&L
    result.sort(key=lambda x: (-x.total_held_qty, -abs(x.unrealized_pl)))
    return result


# ══════════════════════════════════════════════════════════
#  SOLD / TRANSACTIONS
# ══════════════════════════════════════════════════════════

@app.get("/api/transactions", response_model=List[SoldPosition])
def get_transactions():
    """Get all sold positions / transaction history."""
    return db.get_all_sold()


# ══════════════════════════════════════════════════════════
#  LIVE STOCK DATA
# ══════════════════════════════════════════════════════════

@app.get("/api/stock/{symbol}")
def get_stock_live(symbol: str, exchange: str = "NSE"):
    """Get live stock data including 52-week range."""
    data = stock_service.fetch_live_data(symbol, exchange)
    if not data:
        raise HTTPException(status_code=404, detail=f"Could not fetch data for {symbol}")
    return data


@app.get("/api/stock/search/{query}")
def search_stock(query: str, exchange: str = "NSE"):
    """Search for a stock by name or symbol."""
    results = stock_service.search_stock(query, exchange)
    return results


@app.post("/api/stock/manual-price")
def set_manual_price(req: ManualPriceRequest):
    """Manually set a stock price (fallback when Yahoo is unavailable)."""
    db.set_manual_price(req.symbol.upper(), req.exchange.upper(), req.price)
    return {"message": f"Manual price set for {req.symbol}: ₹{req.price}"}


# ══════════════════════════════════════════════════════════
#  PRICE MANAGEMENT (refresh, status, bulk update)
# ══════════════════════════════════════════════════════════

class BulkPriceUpdate(BaseModel):
    prices: dict  # { "SYMBOL": {"exchange": "NSE", "price": 1234.56}, ... }


@app.get("/api/prices/status")
def get_price_status():
    """Get status of the background price refresh system."""
    return stock_service.get_refresh_status()


@app.post("/api/prices/refresh")
def trigger_price_refresh():
    """Manually trigger an immediate price refresh (clears cache)."""
    stock_service.clear_cache()
    stock_service._reset_circuit()  # reset circuit breaker too
    holdings = db.get_all_holdings()
    if not holdings:
        return {"message": "No holdings to refresh", "count": 0}
    symbols = list(set((h.symbol, h.exchange) for h in holdings))
    results = stock_service.fetch_multiple(symbols)
    live_count = sum(1 for v in results.values() if not v.is_manual)
    return {
        "message": f"Refreshed {len(results)} stocks ({live_count} from Yahoo)",
        "total": len(results),
        "live": live_count,
        "fallback": len(results) - live_count,
    }


@app.post("/api/prices/bulk-update")
def bulk_update_prices(req: BulkPriceUpdate):
    """Push prices from external source (useful when Yahoo is down)."""
    updated = stock_service.bulk_update_prices(req.prices)
    return {"message": f"Updated {updated} prices", "count": updated}


# ══════════════════════════════════════════════════════════
#  DASHBOARD SUMMARY
# ══════════════════════════════════════════════════════════

@app.get("/api/dashboard/summary", response_model=PortfolioSummary)
def get_dashboard_summary():
    """Get aggregated portfolio summary for the dashboard."""
    holdings = db.get_all_holdings()
    sold_positions = db.get_all_sold()
    dividends_map = db.get_dividends_by_symbol()

    if not holdings and not sold_positions:
        return PortfolioSummary(
            total_invested=0, current_value=0,
            unrealized_pl=0, unrealized_pl_pct=0,
            realized_pl=0, total_holdings=0,
            stocks_in_profit=0, stocks_in_loss=0,
            total_dividend=0,
        )

    # Fetch live prices
    symbols = list(set((h.symbol, h.exchange) for h in holdings))
    live_data = stock_service.fetch_multiple(symbols) if symbols else {}

    total_invested = 0.0
    current_value = 0.0
    stocks_in_profit = 0
    stocks_in_loss = 0

    for h in holdings:
        invested = h.buy_cost if h.buy_cost > 0 else (h.buy_price * h.quantity)
        total_invested += invested

        key = f"{h.symbol}.{h.exchange}"
        live = live_data.get(key)
        if live:
            cv = live.current_price * h.quantity
            current_value += cv
            if live.current_price > h.buy_price:
                stocks_in_profit += 1
            elif live.current_price < h.buy_price:
                stocks_in_loss += 1

    unrealized_pl = current_value - total_invested
    unrealized_pl_pct = (unrealized_pl / total_invested * 100) if total_invested > 0 else 0

    realized_pl = sum(s.realized_pl for s in sold_positions)
    total_dividend = sum(d["amount"] for d in dividends_map.values())

    return PortfolioSummary(
        total_invested=round(total_invested, 2),
        current_value=round(current_value, 2),
        unrealized_pl=round(unrealized_pl, 2),
        unrealized_pl_pct=round(unrealized_pl_pct, 2),
        realized_pl=round(realized_pl, 2),
        total_holdings=len(holdings),
        stocks_in_profit=stocks_in_profit,
        stocks_in_loss=stocks_in_loss,
        total_dividend=round(total_dividend, 2),
    )


# ══════════════════════════════════════════════════════════
#  MARKET TICKER  (Sensex, Nifty, Gold, Forex, etc.)
# ══════════════════════════════════════════════════════════

MARKET_TICKER_SYMBOLS = [
    {"key": "SENSEX",    "yahoo": "%5EBSESN",    "label": "Sensex",     "type": "index"},
    {"key": "NIFTY50",   "yahoo": "%5ENSEI",     "label": "Nifty 50",   "type": "index"},
    {"key": "GOLD",      "yahoo": "GC%3DF",      "label": "Gold",       "type": "commodity", "unit": "USD/oz"},
    {"key": "SILVER",    "yahoo": "SI%3DF",       "label": "Silver",     "type": "commodity", "unit": "USD/oz"},
    {"key": "SGX",       "yahoo": "%5ESTI",         "label": "SGX STI",    "type": "index"},
    {"key": "NIKKEI",    "yahoo": "%5EN225",      "label": "Nikkei",     "type": "index"},
    {"key": "SGDINR",    "yahoo": "SGDINR%3DX",   "label": "SGD/INR",   "type": "forex"},
    {"key": "USDINR",    "yahoo": "USDINR%3DX",   "label": "USD/INR",   "type": "forex"},
    {"key": "CRUDEOIL",  "yahoo": "CL%3DF",       "label": "Crude Oil", "type": "commodity", "unit": "USD/bbl"},
]

# Cache for market ticker data (separate from stock cache)
_ticker_cache: List[dict] = []
_ticker_cache_time: float = 0.0
_TICKER_CACHE_TTL = 300  # 5 minutes
_ticker_lock = threading.Lock()


def _fetch_market_tickers() -> List[dict]:
    """Fetch all market ticker data via direct Yahoo v8 chart API (no yfinance)."""
    global _ticker_cache, _ticker_cache_time
    import random as _rnd

    with _ticker_lock:
        if time.time() - _ticker_cache_time < _TICKER_CACHE_TTL and _ticker_cache:
            return _ticker_cache

    results = []
    for i, meta in enumerate(MARKET_TICKER_SYMBOLS):
        result = stock_service.fetch_market_ticker(meta)
        results.append(result)
        status = "OK" if result["price"] > 0 else "MISS"
        print(f"[MarketTicker] {meta['key']}: {status} ({result['price']})")
        # Small delay between each fetch
        if i < len(MARKET_TICKER_SYMBOLS) - 1:
            time.sleep(_rnd.uniform(0.3, 0.8))

    # Update cache
    with _ticker_lock:
        _ticker_cache = results
        _ticker_cache_time = time.time()

    fetched = sum(1 for r in results if r["price"] > 0)
    print(f"[MarketTicker] Fetched {fetched}/{len(results)} tickers with prices")

    return results


@app.get("/api/market-ticker")
def get_market_ticker():
    """Get market indices, forex rates, and commodity prices."""
    return _fetch_market_tickers()


# ══════════════════════════════════════════════════════════
#  STATIC FILE SERVING (Production)
# ══════════════════════════════════════════════════════════

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="static")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        """Serve React frontend for all non-API routes."""
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
