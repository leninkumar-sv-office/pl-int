"""
Stock Portfolio Dashboard - FastAPI Backend
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict, Optional
from datetime import date, datetime
import os
import json
import uuid
import time
import threading
import traceback

from .models import (
    AddStockRequest, SellStockRequest, AddDividendRequest, ManualPriceRequest,
    Holding, SoldPosition, StockLiveData, Transaction,
    PortfolioSummary, HoldingWithLive, StockSummaryItem,
    AddMFRequest, RedeemMFRequest, SIPConfigRequest,
    AddFDRequest, UpdateFDRequest,
    AddRDRequest, UpdateRDRequest, AddRDInstallmentRequest,
    AddInsuranceRequest, UpdateInsuranceRequest,
    AddPPFRequest, UpdatePPFRequest, AddPPFContributionRequest, PPFWithdrawRequest,
    AddNPSRequest, UpdateNPSRequest, AddNPSContributionRequest,
    AddSIRequest, UpdateSIRequest,
    CDSLCASUpload, MFImportPayload,
)
from .xlsx_database import xlsx_db as db
from .mf_xlsx_database import mf_db, clear_nav_cache as clear_mf_nav_cache
from . import stock_service
from . import zerodha_service
from . import contract_note_parser
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

app = FastAPI(title="Stock Portfolio Dashboard", version="1.0.0")


# ── Global exception handler: logs unhandled errors to console ──
# (Using exception_handler instead of BaseHTTPMiddleware which can
#  break sync endpoints and large responses)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[ERROR] {request.method} {request.url.path} → {type(exc).__name__}: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error: {str(exc)[:200]}"},
    )


# ══════════════════════════════════════════════════════════
#  STARTUP / SHUTDOWN — background price refresh
# ══════════════════════════════════════════════════════════

@app.on_event("startup")
def on_startup():
    """Start background refresh threads on server boot."""
    # ── Pre-warm xlsx caches so first request is fast ──
    t0 = time.time()
    try:
        holdings = db.get_all_holdings()  # parses all xlsx files → populates cache
        sold = db.get_all_sold()
        symbols = list(set((h.symbol, h.exchange) for h in holdings))
        stock_service.get_cached_prices(symbols)  # populates price cache from JSON
        elapsed = time.time() - t0
        print(f"[App] Pre-warmed caches: {len(holdings)} holdings, "
              f"{len(sold)} sold, {len(symbols)} symbols in {elapsed:.1f}s")
    except Exception as e:
        print(f"[App] Pre-warm error (non-fatal): {e}")

    # Check Zerodha connection
    if zerodha_service.is_configured():
        if zerodha_service.is_session_valid():
            print(f"[App] Zerodha configured — API key: {zerodha_service._api_key[:4]}..., "
                  f"access token: {'set' if zerodha_service._access_token else 'NOT SET'}")
        else:
            print("[App] Zerodha API key configured but no access token — "
                  "visit /api/zerodha/login-url or POST /api/zerodha/set-token")
    else:
        print("[App] Zerodha NOT configured — using Yahoo/Google fallback only")
    # Show fallback status
    if stock_service.ENABLE_YAHOO_GOOGLE:
        print("[App] Yahoo/Google fallback: ENABLED (set ENABLE_FALLBACK= to disable)")
    else:
        print("[App] Yahoo/Google fallback: DISABLED (set ENABLE_FALLBACK=1 to enable)")
    stock_service.start_background_refresh()
    print("[App] Background stock price refresh started")
    # Load Zerodha instrument names in background for symbol→name lookup
    if zerodha_service.is_configured():
        zerodha_service.load_instruments_async()
        print("[App] Loading Zerodha instrument names (background)...")
    _start_ticker_bg_refresh()
    print("[App] Background market ticker refresh started (every 300s)")


@app.on_event("shutdown")
def on_shutdown():
    """Stop background refreshes cleanly."""
    stock_service.stop_background_refresh()
    _stop_ticker_bg_refresh()
    print("[App] Background refreshes stopped")

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
    """Get all holdings with cached price data (instant, no network calls)."""
    holdings = db.get_all_holdings()
    if not holdings:
        return []

    # Use cached prices only — live fetches happen in background threads
    # Request both BSE and NSE for each symbol so fallback works
    base_symbols = set((h.symbol, h.exchange) for h in holdings)
    symbols_with_alt = set(base_symbols)
    for sym, exch in base_symbols:
        alt = "NSE" if exch == "BSE" else "BSE"
        symbols_with_alt.add((sym, alt))
    live_data = stock_service.get_cached_prices(list(symbols_with_alt))

    result = []
    for h in holdings:
        try:
            key = f"{h.symbol}.{h.exchange}"
            live = live_data.get(key)
            # Fall back to alternate exchange (BSE↔NSE) if primary has no price
            if not live or (live.current_price or 0) <= 0:
                alt_exchange = "NSE" if h.exchange == "BSE" else "BSE"
                alt_key = f"{h.symbol}.{alt_exchange}"
                alt_live = live_data.get(alt_key)
                if alt_live and (alt_live.current_price or 0) > 0:
                    live = alt_live

            current_price = live.current_price if live else 0
            invested = h.buy_price * h.quantity
            current_value = current_price * h.quantity
            unrealized_pl = current_value - invested
            unrealized_pl_pct = (unrealized_pl / invested * 100) if invested > 0 else 0

            price_error = ""
            if not live or current_price <= 0:
                price_error = f"Price unavailable for {h.symbol}.{h.exchange}"

            result.append(HoldingWithLive(
                holding=h,
                live=live,
                unrealized_pl=round(unrealized_pl, 2),
                unrealized_pl_pct=round(unrealized_pl_pct, 2),
                current_value=round(current_value, 2),
                is_above_buy_price=current_price > h.buy_price if current_price > 0 else False,
                can_sell=h.quantity > 0,
                price_error=price_error,
            ))
        except Exception as e:
            # Per-stock error: log and continue with remaining stocks
            print(f"[Portfolio] Error processing {h.symbol}.{h.exchange}: {e}")
            result.append(HoldingWithLive(
                holding=h,
                live=None,
                price_error=f"Error: {str(e)[:100]}",
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
    try:
        db.add_sell_transaction(
            symbol=holding.symbol,
            exchange=holding.exchange,
            quantity=req.quantity,
            price=req.sell_price,
            sell_date=sell_date,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
#  CONTRACT NOTE PDF IMPORT
# ══════════════════════════════════════════════════════════

class ContractNoteUpload(BaseModel):
    """PDF file as base64-encoded string (avoids python-multipart dependency)."""
    pdf_base64: str
    filename: str = "contract_note.pdf"


def _decode_and_parse_pdf(req: ContractNoteUpload) -> dict:
    """Shared helper: decode base64 PDF and parse contract note."""
    import base64

    if not req.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    try:
        pdf_bytes = base64.b64decode(req.pdf_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 PDF data")

    try:
        return contract_note_parser.parse_contract_note_from_bytes(pdf_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Import] PDF parse error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {str(e)[:200]}")


@app.post("/api/portfolio/parse-contract-note")
def parse_contract_note_preview(req: ContractNoteUpload):
    """Parse a contract note PDF and return a preview — no data is written.

    Also checks each transaction against existing xlsx data to flag duplicates.
    Each transaction gets an `isDuplicate` boolean field.
    """
    parsed = _decode_and_parse_pdf(req)

    # ── Duplicate detection ──
    # Build a fingerprint cache: symbol → (fingerprints_set, remarks_set)
    _fp_cache: dict = {}
    contract_no = parsed.get("contract_no", "")
    cn_remark = f"CN#{contract_no}" if contract_no else ""
    dup_count = 0

    for tx in parsed.get("transactions", []):
        symbol = (tx.get("symbol") or "").upper()
        if not symbol:
            tx["isDuplicate"] = False
            continue

        # Lazy-load fingerprints per symbol
        if symbol not in _fp_cache:
            try:
                _fp_cache[symbol] = db.get_existing_transaction_fingerprints(symbol)
            except Exception:
                _fp_cache[symbol] = (set(), set())

        fingerprints, remarks_set = _fp_cache[symbol]

        # Check 1: exact contract note number match → definitely duplicate
        if cn_remark and cn_remark in remarks_set:
            tx["isDuplicate"] = True
            dup_count += 1
            continue

        # Check 2: transaction fingerprint match (date + action + qty + price)
        # Try both WAP and effective_price since xlsx might store either
        trade_date = tx.get("trade_date", parsed.get("trade_date", ""))
        action = tx.get("action", "")
        qty = int(tx.get("quantity", 0))
        wap = round(tx.get("wap", 0), 2)
        eff = round(tx.get("effective_price", 0), 2)

        fp_wap = (trade_date, action, qty, wap)
        fp_eff = (trade_date, action, qty, eff)
        matched = fp_wap in fingerprints or fp_eff in fingerprints
        if matched:
            tx["isDuplicate"] = True
            dup_count += 1
        else:
            tx["isDuplicate"] = False
            # Add to in-memory cache so within-batch duplicates are also flagged
            # (e.g. parser produced same row twice, or multi-PDF merge has overlaps)
            fingerprints.add(fp_wap)
            fingerprints.add(fp_eff)

    if dup_count > 0:
        print(f"[Import] Found {dup_count} duplicate transaction(s) in preview")

    return parsed


@app.post("/api/portfolio/import-contract-note")
def import_contract_note(req: ContractNoteUpload):
    """Import transactions from an SBICAP Securities contract note PDF.

    Parses Annexure B to extract per-stock buy/sell transactions with
    all-inclusive pricing (WAP + brokerage + GST + STT + other levies).
    Accepts PDF as base64-encoded string in JSON body.
    """
    parsed = _decode_and_parse_pdf(req)

    trade_date = parsed["trade_date"]
    contract_no = parsed.get("contract_no", "")
    transactions = parsed["transactions"]

    if not transactions:
        return {
            "message": "No transactions found in the contract note",
            "trade_date": trade_date,
            "imported": {"buys": 0, "sells": 0},
        }

    # ── Server-side duplicate detection ──
    _fp_cache: dict = {}
    cn_remark = f"CN#{contract_no}" if contract_no else ""
    skipped_dups = 0

    imported_buys = []
    imported_sells = []
    errors = []

    for tx in transactions:
        try:
            # Check for duplicates before writing
            symbol = (tx.get("symbol") or "").upper()
            if symbol:
                if symbol not in _fp_cache:
                    try:
                        _fp_cache[symbol] = db.get_existing_transaction_fingerprints(symbol)
                    except Exception:
                        _fp_cache[symbol] = (set(), set())

                fingerprints, remarks_set = _fp_cache[symbol]

                if cn_remark and cn_remark in remarks_set:
                    skipped_dups += 1
                    continue

                tx_date = tx.get("trade_date", trade_date)
                action = tx.get("action", "")
                qty = int(tx.get("quantity", 0))
                wap = round(tx.get("wap", 0), 2)
                eff = round(tx.get("effective_price", tx.get("wap", 0)), 2)
                fp_wap = (tx_date, action, qty, wap)
                fp_eff = (tx_date, action, qty, eff)
                if fp_wap in fingerprints or fp_eff in fingerprints:
                    skipped_dups += 1
                    continue

            remark = f"CN#{contract_no}" if contract_no else f"CN-{trade_date}"

            if tx["action"] == "Buy":
                # Create holding with WAP in price column, net_after in cost column
                holding = Holding(
                    id="temp",
                    symbol=tx["symbol"],
                    exchange=tx["exchange"],
                    name=tx["name"],
                    quantity=tx["quantity"],
                    price=tx["wap"],
                    buy_price=tx["effective_price"],
                    buy_cost=tx["net_total_after_levies"],
                    buy_date=tx["trade_date"],
                    notes=remark,
                )

                # Use _insert_transaction directly for precise cost control
                filepath = db._find_file_for_symbol(tx["symbol"])
                if filepath is None:
                    filepath = db._create_stock_file(
                        tx["symbol"], tx["exchange"], tx["name"]
                    )

                buy_tx = Transaction(
                    date=tx["trade_date"],
                    exchange=tx["exchange"],
                    action="Buy",
                    quantity=tx["quantity"],
                    price=tx["wap"],           # Column E: raw WAP
                    cost=tx["net_total_after_levies"],  # Column F: all-inclusive cost
                    remarks=remark,
                    stt=tx["stt"],
                    add_chrg=tx["add_charges"],
                )
                db._insert_transaction(filepath, buy_tx)
                db._invalidate_symbol(tx["symbol"])

                imported_buys.append({
                    "symbol": tx["symbol"],
                    "name": tx["name"],
                    "quantity": tx["quantity"],
                    "wap": tx["wap"],
                    "effective_price": tx["effective_price"],
                    "total_cost": tx["net_total_after_levies"],
                })

            elif tx["action"] == "Sell":
                # Insert Sell row — FIFO matching will handle lot assignment
                filepath = db._find_file_for_symbol(tx["symbol"])
                if filepath is None:
                    errors.append(
                        f"SELL {tx['symbol']}: No existing holding file found. "
                        f"Cannot sell without prior buy records."
                    )
                    continue

                sell_tx = Transaction(
                    date=tx["trade_date"],
                    exchange=tx["exchange"],
                    action="Sell",
                    quantity=tx["quantity"],
                    price=tx["effective_price"],  # Column E: effective sell price
                    cost=tx["net_total_after_levies"],
                    remarks=remark,
                    stt=tx["stt"],
                    add_chrg=tx["add_charges"],
                )
                db._insert_transaction(filepath, sell_tx)
                db._invalidate_symbol(tx["symbol"])

                imported_sells.append({
                    "symbol": tx["symbol"],
                    "name": tx["name"],
                    "quantity": tx["quantity"],
                    "wap": tx["wap"],
                    "effective_price": tx["effective_price"],
                    "total_proceeds": tx["net_total_after_levies"],
                })

        except Exception as e:
            error_msg = f"{tx['action']} {tx['symbol']}: {str(e)[:100]}"
            errors.append(error_msg)
            print(f"[Import] Error: {error_msg}")
            traceback.print_exc()

    # Reindex to pick up any new files
    db.reindex()

    if skipped_dups > 0:
        print(f"[Import] Skipped {skipped_dups} duplicate transaction(s) server-side")

    return {
        "message": (
            f"Imported {len(imported_buys)} buys, {len(imported_sells)} sells "
            f"from contract note dated {trade_date}"
            + (f" ({skipped_dups} duplicates skipped)" if skipped_dups > 0 else "")
        ),
        "trade_date": trade_date,
        "contract_no": contract_no,
        "imported": {
            "buys": len(imported_buys),
            "sells": len(imported_sells),
            "buy_details": imported_buys,
            "sell_details": imported_sells,
        },
        "skipped_duplicates": skipped_dups,
        "errors": errors if errors else None,
    }


class ConfirmedImportPayload(BaseModel):
    """Payload for the confirmed import — pre-parsed and possibly user-edited transactions."""
    trade_date: str
    contract_no: Optional[str] = ""
    transactions: list


@app.post("/api/portfolio/import-contract-note-confirmed")
def import_contract_note_confirmed(req: ConfirmedImportPayload):
    """Import pre-parsed transactions from the preview modal.

    Receives transactions already parsed (and possibly symbol-edited by user).
    No PDF re-parsing needed.
    """
    trade_date = req.trade_date
    contract_no = req.contract_no or ""
    transactions = req.transactions

    if not transactions:
        return {
            "message": "No transactions to import",
            "trade_date": trade_date,
            "imported": {"buys": 0, "sells": 0},
        }

    # ── Server-side duplicate detection (safety net) ──
    # IMPORTANT: _fp_cache is updated after each insert so that within-batch
    # duplicates are also caught (e.g. same stock appears twice in the same batch).
    _fp_cache: dict = {}  # symbol -> (fingerprints_set, remarks_set)
    cn_remark = f"CN#{contract_no}" if contract_no else ""
    skipped_dups = 0

    imported_buys = []
    imported_sells = []
    errors = []

    for tx in transactions:
        try:
            # Check for duplicates before writing
            symbol = (tx.get("symbol") or "").upper()
            if symbol:
                if symbol not in _fp_cache:
                    try:
                        _fp_cache[symbol] = db.get_existing_transaction_fingerprints(symbol)
                    except Exception:
                        _fp_cache[symbol] = (set(), set())

                fingerprints, remarks_set = _fp_cache[symbol]

                # Check 1: CN# remark match
                if cn_remark and cn_remark in remarks_set:
                    skipped_dups += 1
                    continue

                # Check 2: transaction fingerprint match (try both WAP and effective price)
                tx_date = tx.get("trade_date", trade_date)
                action = tx.get("action", "")
                qty = int(tx.get("quantity", 0))
                wap = round(tx.get("wap", 0), 2)
                eff = round(tx.get("effective_price", tx.get("wap", 0)), 2)
                fp_wap = (tx_date, action, qty, wap)
                fp_eff = (tx_date, action, qty, eff)
                if fp_wap in fingerprints or fp_eff in fingerprints:
                    skipped_dups += 1
                    continue

            remark = f"CN#{contract_no}" if contract_no else f"CN-{trade_date}"

            if tx["action"] == "Buy":
                filepath = db._find_file_for_symbol(tx["symbol"])
                if filepath is None:
                    filepath = db._create_stock_file(
                        tx["symbol"], tx.get("exchange", "NSE"), tx.get("name", tx["symbol"])
                    )

                buy_tx = Transaction(
                    date=tx.get("trade_date", trade_date),
                    exchange=tx.get("exchange", "NSE"),
                    action="Buy",
                    quantity=tx["quantity"],
                    price=tx.get("wap", tx.get("effective_price", 0)),
                    cost=tx.get("net_total_after_levies", 0),
                    remarks=remark,
                    stt=tx.get("stt", 0),
                    add_chrg=tx.get("add_charges", 0),
                )
                db._insert_transaction(filepath, buy_tx)
                db._invalidate_symbol(tx["symbol"])

                imported_buys.append({
                    "symbol": tx["symbol"],
                    "name": tx.get("name", ""),
                    "quantity": tx["quantity"],
                })

            elif tx["action"] == "Sell":
                filepath = db._find_file_for_symbol(tx["symbol"])
                if filepath is None:
                    errors.append(
                        f"SELL {tx['symbol']}: No existing holding file found."
                    )
                    continue

                sell_tx = Transaction(
                    date=tx.get("trade_date", trade_date),
                    exchange=tx.get("exchange", "NSE"),
                    action="Sell",
                    quantity=tx["quantity"],
                    price=tx.get("effective_price", tx.get("wap", 0)),
                    cost=tx.get("net_total_after_levies", 0),
                    remarks=remark,
                    stt=tx.get("stt", 0),
                    add_chrg=tx.get("add_charges", 0),
                )
                db._insert_transaction(filepath, sell_tx)
                db._invalidate_symbol(tx["symbol"])

                imported_sells.append({
                    "symbol": tx["symbol"],
                    "name": tx.get("name", ""),
                    "quantity": tx["quantity"],
                })

            # ── Update in-memory cache so within-batch duplicates are caught ──
            # Only add fingerprints — NOT the CN# remark.
            # CN# remark check is for "entire contract note already imported before"
            # (from xlsx). Within-batch, fingerprint check handles individual tx dedup.
            if symbol:
                fingerprints, remarks_set = _fp_cache.get(symbol, (set(), set()))
                fingerprints.add(fp_wap)
                fingerprints.add(fp_eff)
                _fp_cache[symbol] = (fingerprints, remarks_set)

        except Exception as e:
            error_msg = f"{tx.get('action', '?')} {tx.get('symbol', '?')}: {str(e)[:100]}"
            errors.append(error_msg)
            print(f"[Import] Error: {error_msg}")
            traceback.print_exc()

    db.reindex()

    if skipped_dups > 0:
        print(f"[Import] Skipped {skipped_dups} duplicate transaction(s) server-side")

    return {
        "message": (
            f"Imported {len(imported_buys)} buys, {len(imported_sells)} sells "
            f"from contract note dated {trade_date}"
            + (f" ({skipped_dups} duplicates skipped)" if skipped_dups > 0 else "")
        ),
        "trade_date": trade_date,
        "contract_no": contract_no,
        "imported": {
            "buys": len(imported_buys),
            "sells": len(imported_sells),
            "buy_details": imported_buys,
            "sell_details": imported_sells,
        },
        "skipped_duplicates": skipped_dups,
        "errors": errors if errors else None,
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

    # Use cached prices (instant, no network calls)
    # Request both BSE and NSE for each symbol so exchange fallback works
    # Include BOTH held and sold symbols so fully-sold stocks get live data too
    base_symbols = set((h.symbol, h.exchange) for h in holdings)
    for s in sold_positions:
        base_symbols.add((s.symbol, s.exchange))
    symbols_with_alt = set(base_symbols)
    for sym, exch in base_symbols:
        alt = "NSE" if exch == "BSE" else "BSE"
        symbols_with_alt.add((sym, alt))
    live_data = stock_service.get_cached_prices(list(symbols_with_alt)) if base_symbols else {}

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
        try:
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
            # Split realized P&L by holding period (LTCG vs STCG)
            ltcg_realized_pl = 0.0
            stcg_realized_pl = 0.0
            ltcg_sold_qty = 0
            stcg_sold_qty = 0
            ltcg_sold_cost = 0.0
            stcg_sold_cost = 0.0
            ltcg_sold_earliest_buy = ""
            ltcg_sold_latest_sell = ""
            stcg_sold_earliest_buy = ""
            stcg_sold_latest_sell = ""
            for s in sold_lots:
                try:
                    b_dt = datetime.strptime(s.buy_date, "%Y-%m-%d").date()
                    s_dt = datetime.strptime(s.sell_date, "%Y-%m-%d").date()
                    is_lt = (s_dt - b_dt).days > 365
                except Exception:
                    is_lt = False
                if is_lt:
                    ltcg_realized_pl += s.realized_pl
                    ltcg_sold_qty += s.quantity
                    ltcg_sold_cost += s.buy_price * s.quantity
                    if not ltcg_sold_earliest_buy or s.buy_date < ltcg_sold_earliest_buy:
                        ltcg_sold_earliest_buy = s.buy_date
                    if not ltcg_sold_latest_sell or s.sell_date > ltcg_sold_latest_sell:
                        ltcg_sold_latest_sell = s.sell_date
                else:
                    stcg_realized_pl += s.realized_pl
                    stcg_sold_qty += s.quantity
                    stcg_sold_cost += s.buy_price * s.quantity
                    if not stcg_sold_earliest_buy or s.buy_date < stcg_sold_earliest_buy:
                        stcg_sold_earliest_buy = s.buy_date
                    if not stcg_sold_latest_sell or s.sell_date > stcg_sold_latest_sell:
                        stcg_sold_latest_sell = s.sell_date

            # Live data — try primary exchange, fall back to alternate (BSE↔NSE)
            live_key = f"{sym}.{exchange}"
            live = live_data.get(live_key)
            if not live or (live.current_price or 0) <= 0:
                alt_exchange = "NSE" if exchange == "BSE" else "BSE"
                alt_key = f"{sym}.{alt_exchange}"
                alt_live = live_data.get(alt_key)
                if alt_live and (alt_live.current_price or 0) > 0:
                    live = alt_live
            current_price = live.current_price if live else 0
            current_value = current_price * total_held_qty
            unrealized_pl = current_value - total_invested
            unrealized_pl_pct = (unrealized_pl / total_invested * 100) if total_invested > 0 else 0

            # Per-lot profitability: split into profitable vs loss lots AND LTCG vs STCG
            profitable_qty = 0
            loss_qty = 0
            unrealized_profit = 0.0  # P&L sum from lots where current > buy
            unrealized_loss = 0.0    # P&L sum from lots where current <= buy
            ltcg_unrealized_profit = 0.0
            stcg_unrealized_profit = 0.0
            ltcg_unrealized_loss = 0.0
            stcg_unrealized_loss = 0.0
            ltcg_profitable_qty = 0
            stcg_profitable_qty = 0
            ltcg_loss_qty = 0
            stcg_loss_qty = 0
            ltcg_invested = 0.0
            stcg_invested = 0.0
            ltcg_earliest_date = ""
            stcg_earliest_date = ""
            today = date.today()
            if current_price > 0:
                for h in held_lots:
                    lot_pl = (current_price - h.buy_price) * h.quantity
                    lot_cost = h.buy_cost if h.buy_cost > 0 else (h.buy_price * h.quantity)
                    # Determine LTCG vs STCG (India: >365 days = long-term)
                    try:
                        buy_dt = datetime.strptime(h.buy_date, "%Y-%m-%d").date()
                        is_ltcg = (today - buy_dt).days > 365
                    except Exception:
                        is_ltcg = False
                    # Track per-category invested & earliest date
                    if is_ltcg:
                        ltcg_invested += lot_cost
                        if not ltcg_earliest_date or h.buy_date < ltcg_earliest_date:
                            ltcg_earliest_date = h.buy_date
                    else:
                        stcg_invested += lot_cost
                        if not stcg_earliest_date or h.buy_date < stcg_earliest_date:
                            stcg_earliest_date = h.buy_date
                    if current_price > h.buy_price:
                        profitable_qty += h.quantity
                        unrealized_profit += lot_pl
                        if is_ltcg:
                            ltcg_unrealized_profit += lot_pl
                            ltcg_profitable_qty += h.quantity
                        else:
                            stcg_unrealized_profit += lot_pl
                            stcg_profitable_qty += h.quantity
                    else:
                        loss_qty += h.quantity
                        unrealized_loss += lot_pl
                        if is_ltcg:
                            ltcg_unrealized_loss += lot_pl
                            ltcg_loss_qty += h.quantity
                        else:
                            stcg_unrealized_loss += lot_pl
                            stcg_loss_qty += h.quantity

            price_error = ""
            if total_held_qty > 0 and (not live or current_price <= 0):
                price_error = f"Price unavailable for {sym}.{exchange}"

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
                ltcg_unrealized_profit=round(ltcg_unrealized_profit, 2),
                stcg_unrealized_profit=round(stcg_unrealized_profit, 2),
                ltcg_unrealized_loss=round(ltcg_unrealized_loss, 2),
                stcg_unrealized_loss=round(stcg_unrealized_loss, 2),
                ltcg_realized_pl=round(ltcg_realized_pl, 2),
                stcg_realized_pl=round(stcg_realized_pl, 2),
                ltcg_profitable_qty=ltcg_profitable_qty,
                stcg_profitable_qty=stcg_profitable_qty,
                ltcg_loss_qty=ltcg_loss_qty,
                stcg_loss_qty=stcg_loss_qty,
                ltcg_invested=round(ltcg_invested, 2),
                stcg_invested=round(stcg_invested, 2),
                ltcg_earliest_date=ltcg_earliest_date,
                stcg_earliest_date=stcg_earliest_date,
                ltcg_sold_qty=ltcg_sold_qty,
                stcg_sold_qty=stcg_sold_qty,
                ltcg_sold_cost=round(ltcg_sold_cost, 2),
                stcg_sold_cost=round(stcg_sold_cost, 2),
                ltcg_sold_earliest_buy=ltcg_sold_earliest_buy,
                ltcg_sold_latest_sell=ltcg_sold_latest_sell,
                stcg_sold_earliest_buy=stcg_sold_earliest_buy,
                stcg_sold_latest_sell=stcg_sold_latest_sell,
                total_dividend=round(dividends_by_symbol.get(sym, {}).get("amount", 0), 2),
                dividend_count=dividends_by_symbol.get(sym, {}).get("count", 0),
                dividend_units=dividends_by_symbol.get(sym, {}).get("units", 0),
                num_held_lots=len(held_lots),
                num_sold_lots=len(sold_lots),
                profitable_qty=profitable_qty,
                loss_qty=loss_qty,
                live=live,
                is_above_avg_buy=current_price > avg_buy_price if current_price > 0 and avg_buy_price > 0 else False,
                price_error=price_error,
            ))
        except Exception as e:
            # Per-stock error: log and continue with remaining stocks
            print(f"[StockSummary] Error processing {sym}: {e}")
            exchange = held_by_symbol.get(sym, sold_by_symbol.get(sym, {})).get("exchange", "NSE")
            result.append(StockSummaryItem(
                symbol=sym, exchange=exchange, name=sym,
                price_error=f"Error: {str(e)[:100]}",
            ))

    # Sort: stocks with held shares first, then by unrealized P&L
    result.sort(key=lambda x: (-x.total_held_qty, -abs(x.unrealized_pl)))
    return result


# ══════════════════════════════════════════════════════════
#  DIAGNOSTICS
# ══════════════════════════════════════════════════════════

@app.get("/api/diagnostics/symbol-map")
def get_symbol_map():
    """Diagnostic endpoint: show how each xlsx file is mapped to symbols.

    Lists every xlsx file, the primary resolved symbol, any derived aliases,
    and whether fingerprint lookup would work for each alias.
    """
    from .xlsx_database import SYMBOL_MAP, _REVERSE_MAP
    from . import symbol_resolver as sr

    entries = []
    for filename, primary_symbol in sorted(SYMBOL_MAP.items()):
        derived = sr.derive_symbol(filename)
        has_primary_files = primary_symbol in db._all_files and len(db._all_files[primary_symbol]) > 0
        has_derived_files = derived in db._all_files and len(db._all_files[derived]) > 0
        entry = {
            "filename": filename,
            "primary_symbol": primary_symbol,
            "derived_symbol": derived if derived != primary_symbol else None,
            "symbols_match": primary_symbol == derived,
            "primary_indexed": has_primary_files,
            "derived_indexed": has_derived_files,
        }
        if derived != primary_symbol and not has_derived_files:
            entry["warning"] = f"Derived symbol '{derived}' not indexed — duplicate detection may fail"
        entries.append(entry)

    mismatches = [e for e in entries if not e["symbols_match"]]
    return {
        "total_files": len(entries),
        "symbol_mismatches": len(mismatches),
        "entries": entries,
    }


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
    """Get stock data including 52-week range (cached, no network calls)."""
    results = stock_service.get_cached_prices([(symbol, exchange)])
    data = results.get(f"{symbol}.{exchange}")
    if not data:
        raise HTTPException(status_code=404, detail=f"No cached data for {symbol}")
    return data


@app.get("/api/stock/lookup/{symbol}")
def lookup_stock_name(symbol: str, exchange: str = "NSE"):
    """Fast lookup of company name — tries Zerodha instruments, then saved prices."""
    sym = symbol.upper()
    exch = exchange.upper()
    # Try Zerodha instrument cache first
    name = zerodha_service.lookup_instrument_name(sym, exch)
    if not name:
        # Fallback: check saved stock_prices.json (has "name" field)
        saved = stock_service._load_prices_file()
        key = f"{sym}.{exch}"
        info = saved.get(key)
        if info and info.get("name"):
            name = info["name"]
        else:
            # Try the other exchange
            alt_exch = "BSE" if exch == "NSE" else "NSE"
            alt_info = saved.get(f"{sym}.{alt_exch}")
            if alt_info and alt_info.get("name"):
                name = alt_info["name"]
    return {"symbol": sym, "exchange": exch, "name": name}


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


def _do_price_refresh():
    """Worker: reindex xlsx files then fetch live prices."""
    try:
        db.reindex()
        stock_service.clear_cache()
        stock_service._reset_circuit()
        holdings = db.get_all_holdings()
        if not holdings:
            return
        symbols = list(set((h.symbol, h.exchange) for h in holdings))
        res = stock_service.fetch_multiple(symbols)
        live = sum(1 for v in res.values() if not v.is_manual)
        print(f"[PriceRefresh] Done: {live} live, {len(res)-live} fallback / {len(symbols)} stocks")
    except Exception as e:
        print(f"[PriceRefresh] Error: {e}")


@app.post("/api/prices/refresh")
def trigger_price_refresh():
    """Trigger an immediate price refresh (BLOCKING — waits for fresh prices).
    Re-scans dumps/ for new xlsx files, then fetches live prices synchronously."""
    t0 = time.time()
    try:
        reindex_result = db.reindex()
        stock_service.clear_cache()
        stock_service._reset_circuit()
        holdings = db.get_all_holdings()
        if not holdings:
            return {"message": "No holdings found", "stocks": 0, "reindex": reindex_result}
        symbols = list(set((h.symbol, h.exchange) for h in holdings))
        res = stock_service.fetch_multiple(symbols)
        live = sum(1 for v in res.values() if not v.is_manual)
        fb = sum(1 for v in res.values() if v.is_manual)
        elapsed = round(time.time() - t0, 1)
        print(f"[PriceRefresh] Done in {elapsed}s: {live} live, {fb} fallback / {len(symbols)} stocks")
        return {
            "message": f"Refreshed {live} live + {fb} cached / {len(symbols)} stocks in {elapsed}s",
            "stocks": len(symbols),
            "live": live,
            "fallback": fb,
            "elapsed": elapsed,
            "reindex": reindex_result,
        }
    except Exception as e:
        print(f"[PriceRefresh] Error: {e}")
        traceback.print_exc()
        return {
            "message": f"Refresh error: {str(e)[:200]}",
            "stocks": 0,
        }


@app.post("/api/prices/bulk-update")
def bulk_update_prices(req: BulkPriceUpdate):
    """Push prices from external source (useful when Yahoo is down)."""
    updated = stock_service.bulk_update_prices(req.prices)
    return {"message": f"Updated {updated} prices", "count": updated}


def _do_ticker_refresh():
    """Background thread for ticker refresh."""
    try:
        results = _refresh_tickers_once()
        ok = sum(1 for r in results if r.get("price", 0) > 0)
        print(f"[MarketTicker] Refresh done: {ok}/{len(results)} tickers with prices")
    except Exception as e:
        print(f"[MarketTicker] Refresh error: {e}")

@app.post("/api/market-ticker/refresh")
def trigger_ticker_refresh():
    """Force an immediate live market ticker refresh (Yahoo → Google → file). Non-blocking."""
    threading.Thread(target=_do_ticker_refresh, daemon=True).start()
    # Return current cached data immediately
    with _ticker_lock:
        cached = list(_ticker_cache) if _ticker_cache else []
    ok = sum(1 for t in cached if t.get("price", 0) > 0)
    return {
        "message": f"Ticker refresh started ({ok} currently cached)",
        "total": len(cached),
        "with_price": ok,
    }


# ══════════════════════════════════════════════════════════
#  REFRESH SETTINGS
# ══════════════════════════════════════════════════════════

_VALID_INTERVALS = [60, 120, 300, 600]  # 1m, 2m, 5m, 10m

@app.get("/api/settings/refresh-interval")
def get_refresh_interval():
    """Get the current backend refresh intervals (stock prices + market tickers)."""
    return {
        "stock_interval": stock_service.REFRESH_INTERVAL,
        "ticker_interval": _TICKER_REFRESH_INTERVAL,
    }


@app.post("/api/settings/refresh-interval")
def set_refresh_interval(body: dict):
    """Set the backend refresh interval in seconds (applies to both stock + ticker)."""
    global _TICKER_REFRESH_INTERVAL
    interval = int(body.get("interval", 300))
    if interval < 60:
        interval = 60
    if interval > 600:
        interval = 600
    stock_service.REFRESH_INTERVAL = interval
    _TICKER_REFRESH_INTERVAL = interval
    return {"interval": interval, "message": f"Refresh interval set to {interval}s"}


@app.get("/api/settings/fallback")
def get_fallback_status():
    """Check if Yahoo/Google fallback is enabled."""
    return {"enabled": stock_service.ENABLE_YAHOO_GOOGLE}


@app.post("/api/settings/fallback")
def toggle_fallback(body: dict):
    """Enable/disable Yahoo/Google Finance fallback at runtime.
    Body: {"enabled": true} or {"enabled": false}"""
    enabled = body.get("enabled", False)
    stock_service.ENABLE_YAHOO_GOOGLE = bool(enabled)
    status = "enabled" if enabled else "disabled"
    print(f"[App] Yahoo/Google fallback {status}")
    return {"enabled": stock_service.ENABLE_YAHOO_GOOGLE,
            "message": f"Yahoo/Google fallback {status}"}


# ══════════════════════════════════════════════════════════
#  ZERODHA AUTH & STATUS
# ══════════════════════════════════════════════════════════

@app.get("/api/zerodha/status")
def get_zerodha_status():
    """Get Zerodha connection status."""
    return zerodha_service.get_status()


@app.get("/api/zerodha/login")
def zerodha_login_page():
    """Serve Zerodha login/settings page."""
    html_path = os.path.join(os.path.dirname(__file__), "zerodha_login.html")
    return FileResponse(html_path, media_type="text/html")


@app.get("/api/zerodha/login-url")
def get_zerodha_login_url():
    """Get Kite Connect login URL for browser auth."""
    if not zerodha_service.is_configured():
        raise HTTPException(status_code=400, detail="Zerodha API key not configured in .env")
    url = zerodha_service.get_login_url()
    return {"login_url": url}


@app.get("/api/zerodha/callback")
def zerodha_callback(request_token: str = "", action: str = "", status: str = ""):
    """Kite Connect redirect callback — exchanges request_token for access_token."""
    from fastapi.responses import RedirectResponse
    if action != "login" or not request_token:
        return RedirectResponse(url="/api/zerodha/login?auth=failed&error=Invalid+callback")
    success = zerodha_service.generate_session(request_token)
    if success:
        # Trigger background refresh with the new token
        threading.Thread(target=_do_price_refresh, daemon=True).start()
        return RedirectResponse(url="/api/zerodha/login?auth=success")
    return RedirectResponse(url="/api/zerodha/login?auth=failed&error=Token+exchange+failed")


@app.post("/api/zerodha/set-token")
def set_zerodha_token(body: dict):
    """Manually set the Zerodha access token."""
    token = body.get("access_token", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="access_token is required")
    zerodha_service.set_access_token(token)
    # Validate
    valid = zerodha_service.validate_session()
    if valid:
        # Trigger background refresh with the new valid token
        threading.Thread(target=_do_price_refresh, daemon=True).start()
    return {
        "message": "Token set" + (" and validated — refreshing prices" if valid else " (validation pending)"),
        "valid": valid,
    }


@app.get("/api/zerodha/validate")
def validate_zerodha():
    """Validate the current Zerodha session."""
    if not zerodha_service.is_session_valid():
        return {"valid": False, "message": "No access token configured"}
    valid = zerodha_service.validate_session()
    return {"valid": valid, "message": "Session valid" if valid else "Session expired — re-login needed"}


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

    # Use cached prices (instant, no network calls)
    symbols = list(set((h.symbol, h.exchange) for h in holdings))
    live_data = stock_service.get_cached_prices(symbols) if symbols else {}

    total_invested = 0.0
    current_value = 0.0
    stocks_in_profit = 0
    stocks_in_loss = 0

    for h in holdings:
        try:
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
        except Exception as e:
            print(f"[Dashboard] Error processing {h.symbol}.{h.exchange}: {e}")

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
    {"key": "SENSEX",    "yahoo": "%5EBSESN",    "label": "Sensex",     "type": "index",     "kite": True},
    {"key": "NIFTY50",   "yahoo": "%5ENSEI",     "label": "Nifty 50",   "type": "index",     "kite": True},
    {"key": "GOLD",      "yahoo": "GC%3DF",      "label": "Gold",       "type": "commodity", "unit": "₹/g",    "kite": True, "divisor": 10},
    {"key": "SILVER",    "yahoo": "SI%3DF",       "label": "Silver",     "type": "commodity", "unit": "₹/g",    "kite": True, "divisor": 1000},
    {"key": "SGX",       "yahoo": "%5ESTI",         "label": "SGX STI",    "type": "index",                        "kite": False},
    {"key": "NIKKEI",    "yahoo": "%5EN225",      "label": "Nikkei",     "type": "index",                        "kite": False},
    {"key": "SGDINR",    "yahoo": "SGDINR%3DX",   "label": "SGD/INR",   "type": "forex",                        "kite": False},
    {"key": "USDINR",    "yahoo": "USDINR%3DX",   "label": "USD/INR",   "type": "forex",     "kite": True},
    {"key": "CRUDEOIL",  "yahoo": "CL%3DF",       "label": "Crude Oil", "type": "commodity", "unit": "₹/bbl",   "kite": True},
]

# ══════════════════════════════════════════════════════════
#  MARKET TICKER — cache, persistence, background refresh
# ══════════════════════════════════════════════════════════

_ticker_cache: List[dict] = []
_ticker_cache_time: float = 0.0
_TICKER_REFRESH_INTERVAL = 300   # 5 minutes
_ticker_lock = threading.Lock()
_TICKER_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "market_ticker.json")
_TICKER_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "market_ticker_history.json")

# Background thread state
_ticker_bg_running = False
_ticker_bg_thread = None


def _load_ticker_file() -> List[dict]:
    """Load ticker data from JSON file."""
    try:
        with open(_TICKER_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_ticker_file(tickers: List[dict]):
    """Save ticker data to JSON file — MERGE: never overwrite non-zero with zero."""
    os.makedirs(os.path.dirname(_TICKER_FILE), exist_ok=True)
    # Load existing file to preserve non-zero values
    existing = _load_ticker_file()
    existing_map = {t["key"]: t for t in existing if t.get("price", 0) > 0}
    # Build merged list: new non-zero values override, but zeros don't clobber
    merged_map = dict(existing_map)  # start with saved non-zero
    for t in tickers:
        key = t.get("key", "")
        if t.get("price", 0) > 0:
            merged_map[key] = t
        # If new price is 0 but existing has non-zero, keep existing (already in map)
    # Rebuild list in canonical order
    key_order = [m["key"] for m in MARKET_TICKER_SYMBOLS]
    result = []
    for key in key_order:
        if key in merged_map:
            result.append(merged_map[key])
        else:
            # No data at all — include placeholder
            meta = next((m for m in MARKET_TICKER_SYMBOLS if m["key"] == key), {})
            result.append({
                "key": key, "label": meta.get("label", key),
                "type": meta.get("type", "index"), "unit": meta.get("unit", ""),
                "price": 0, "change": 0, "change_pct": 0,
            })
    with open(_TICKER_FILE, "w") as f:
        json.dump(result, f, indent=2)


def _record_ticker_history(tickers: List[dict]):
    """Append today's prices to history file for 1W/1M change tracking.
    Format: {date_str: {key: price, ...}, ...}  — keeps last 40 days."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(_TICKER_HISTORY_FILE) as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = {}

    # Only update once per day (don't overwrite with stale intraday)
    if today_str in history:
        return history

    day_data = {}
    for t in tickers:
        if t.get("price", 0) > 0:
            day_data[t["key"]] = t["price"]

    if day_data:
        history[today_str] = day_data
        # Prune to last 40 days
        sorted_dates = sorted(history.keys())
        if len(sorted_dates) > 40:
            for old in sorted_dates[:-40]:
                del history[old]
        os.makedirs(os.path.dirname(_TICKER_HISTORY_FILE), exist_ok=True)
        with open(_TICKER_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)

    return history


def _enrich_ticker_changes(tickers: List[dict]) -> List[dict]:
    """Add week_change_pct and month_change_pct using Zerodha Historical Data API.
    Requires instrument_token in ticker data (set during Zerodha quote fetch)."""
    # Build {key: {instrument_token, ...}} from tickers that have tokens
    ticker_data = {}
    for t in tickers:
        t.setdefault("week_change_pct", 0.0)
        t.setdefault("month_change_pct", 0.0)
        token = t.get("instrument_token")
        if token and t.get("price", 0) > 0:
            ticker_data[t["key"]] = {"instrument_token": token}

    if not ticker_data:
        return tickers

    changes = zerodha_service.fetch_ticker_historical_changes(ticker_data)
    for t in tickers:
        ch = changes.get(t["key"])
        if ch:
            t["week_change_pct"] = ch["week_change_pct"]
            t["month_change_pct"] = ch["month_change_pct"]

    return tickers


def _refresh_tickers_once():
    """Single refresh cycle: Zerodha (primary) → saved JSON (offline cache).
    Yahoo/Google are ONLY used if ENABLE_FALLBACK is explicitly turned on."""
    global _ticker_cache, _ticker_cache_time

    # Build fallback map from file + cache (non-zero values only)
    saved = _load_ticker_file()
    saved_map = {t["key"]: t for t in saved if t.get("price", 0) > 0}
    with _ticker_lock:
        cache_map = {t["key"]: t for t in _ticker_cache if t.get("price", 0) > 0}
    fallback_map = {**saved_map, **cache_map}

    # ── SOURCE 1: ZERODHA ──
    zerodha_tickers: Dict[str, dict] = {}
    if zerodha_service.is_session_valid() and not zerodha_service._auth_failed:
        try:
            zerodha_tickers = zerodha_service.fetch_market_tickers()
            if zerodha_tickers:
                ok = sum(1 for v in zerodha_tickers.values() if v.get("price", 0) > 0)
                print(f"[MarketTicker] Zerodha returned {ok} tickers")
            else:
                print(f"[MarketTicker] Zerodha returned no data")
        except Exception as e:
            print(f"[MarketTicker] Zerodha error: {e}")
    else:
        if zerodha_service._auth_failed:
            reason = "token expired — visit /api/zerodha/login"
        elif not zerodha_service._access_token:
            reason = "no access token set"
        elif zerodha_service._conn_failed:
            reason = "connection failed, retrying in 60s"
        else:
            reason = "not configured"
        print(f"[MarketTicker] Zerodha skipped ({reason})")

    results = []
    for meta in MARKET_TICKER_SYMBOLS:
        key = meta["key"]

        divisor = meta.get("divisor", 1)

        # Try Zerodha
        zt = zerodha_tickers.get(key)
        if zt and zt.get("price", 0) > 0:
            result = {
                "key": key, "label": meta["label"],
                "type": meta.get("type", "index"), "unit": meta.get("unit", ""),
                "price": round(zt["price"] / divisor, 2),
                "change": round(zt.get("change", 0) / divisor, 2),
                "change_pct": zt.get("change_pct", 0),
                "instrument_token": zt.get("instrument_token"),
                "source": "zerodha",
            }
            results.append(result)
            continue

        # SOURCE 2: Yahoo/Google — ONLY if explicitly enabled
        if stock_service.ENABLE_YAHOO_GOOGLE:
            import random as _rnd
            yg_result = stock_service.fetch_market_ticker(meta)
            if yg_result.get("price", 0) > 0:
                if divisor != 1:
                    yg_result["price"] = round(yg_result["price"] / divisor, 2)
                    yg_result["change"] = round(yg_result.get("change", 0) / divisor, 2)
                yg_result["source"] = "yahoo/google"
                results.append(yg_result)
                time.sleep(_rnd.uniform(0.3, 0.8))
                continue

        # SOURCE 3: Saved JSON (offline cache from last successful fetch)
        if key in fallback_map:
            fb = fallback_map[key]
            result = {
                "key": key, "label": meta["label"],
                "type": meta.get("type", "index"), "unit": meta.get("unit", ""),
                "price": fb["price"], "change": fb.get("change", 0),
                "change_pct": fb.get("change_pct", 0),
                "source": "cached",
            }
            results.append(result)
            continue

        # No data at all
        results.append({
            "key": key, "label": meta["label"],
            "type": meta.get("type", "index"), "unit": meta.get("unit", ""),
            "price": 0, "change": 0, "change_pct": 0,
            "source": "none",
        })

    # Log summary by source
    by_source = {}
    for r in results:
        src = r.get("source", "none")
        by_source[src] = by_source.get(src, 0) + 1
    summary = ", ".join(f"{v} {k}" for k, v in by_source.items())
    print(f"[MarketTicker] Refresh done: {summary}")

    # Save to file (merge-safe) and update cache
    _save_ticker_file(results)
    _record_ticker_history(results)
    _enrich_ticker_changes(results)
    with _ticker_lock:
        _ticker_cache = results
        _ticker_cache_time = time.time()

    return results


def _ticker_bg_loop():
    """Background loop: refresh market tickers every REFRESH_INTERVAL seconds."""
    global _ticker_cache, _ticker_cache_time
    # Initial load from file (instant, no network)
    saved = _load_ticker_file()
    if saved:
        _enrich_ticker_changes(saved)
        with _ticker_lock:
            _ticker_cache = saved
            _ticker_cache_time = time.time()
        ok = sum(1 for t in saved if t.get("price", 0) > 0)
        print(f"[MarketTicker] Loaded {ok}/{len(saved)} from file on startup")

    while _ticker_bg_running:
        try:
            _refresh_tickers_once()
        except Exception as e:
            print(f"[MarketTicker] Refresh error: {e}")
        # Sleep in 1s chunks so we can exit promptly
        for _ in range(_TICKER_REFRESH_INTERVAL):
            if not _ticker_bg_running:
                break
            time.sleep(1)


def _start_ticker_bg_refresh():
    global _ticker_bg_thread, _ticker_bg_running
    if _ticker_bg_running:
        return
    _ticker_bg_running = True
    _ticker_bg_thread = threading.Thread(target=_ticker_bg_loop, daemon=True)
    _ticker_bg_thread.start()


def _stop_ticker_bg_refresh():
    global _ticker_bg_running
    _ticker_bg_running = False


@app.get("/api/market-ticker")
def get_market_ticker():
    """Get market indices, forex rates, and commodity prices.
    Data is refreshed automatically every 5 minutes by background thread."""
    with _ticker_lock:
        if _ticker_cache:
            return _ticker_cache
    # Fallback: if background hasn't populated cache yet, load from file
    saved = _load_ticker_file()
    if saved:
        _enrich_ticker_changes(saved)
    return saved if saved else []


@app.post("/api/market-ticker/update")
def update_market_ticker(tickers: List[dict]):
    """Manually push market ticker data (bypass Yahoo).
    Each item: {key, label, type, unit, price, change, change_pct}"""
    global _ticker_cache, _ticker_cache_time
    meta_map = {m["key"]: m for m in MARKET_TICKER_SYMBOLS}
    pushed = []
    for t in tickers:
        key = t.get("key", "")
        meta = meta_map.get(key, {})
        pushed.append({
            "key": key,
            "label": t.get("label", meta.get("label", key)),
            "type": t.get("type", meta.get("type", "index")),
            "unit": t.get("unit", meta.get("unit", "")),
            "price": float(t.get("price", 0)),
            "change": float(t.get("change", 0)),
            "change_pct": float(t.get("change_pct", 0)),
        })
    # Merge-safe save (non-zero pushed values win, zeros don't clobber)
    _save_ticker_file(pushed)
    # Update cache: merge pushed into current cache
    with _ticker_lock:
        cache_map = {t["key"]: t for t in _ticker_cache}
        for p in pushed:
            if p["price"] > 0:
                cache_map[p["key"]] = p
        _ticker_cache = [cache_map.get(m["key"], {"key": m["key"], "label": m["label"],
                         "type": m.get("type","index"), "unit": m.get("unit",""),
                         "price": 0, "change": 0, "change_pct": 0})
                         for m in MARKET_TICKER_SYMBOLS]
        _ticker_cache_time = time.time()
    print(f"[MarketTicker] Manual update: {len(pushed)} tickers")
    return {"updated": len(pushed)}


# ══════════════════════════════════════════════════════════
#  MUTUAL FUNDS
# ══════════════════════════════════════════════════════════

@app.get("/api/mutual-funds/summary")
def get_mf_summary():
    """Get per-fund aggregated summary with held/sold lots."""
    return mf_db.get_fund_summary()


@app.get("/api/mutual-funds/dashboard")
def get_mf_dashboard():
    """Get aggregated MF portfolio summary for the dashboard."""
    return mf_db.get_dashboard_summary()


@app.post("/api/mutual-funds/refresh-nav")
def refresh_mf_nav():
    """Clear MF NAV cache and re-fetch live NAVs."""
    clear_mf_nav_cache()
    summary = mf_db.get_fund_summary()
    with_nav = sum(1 for f in summary if f.get("current_nav", 0) > 0)
    return {"message": f"NAV refreshed: {with_nav}/{len(summary)} funds with live prices"}


@app.get("/api/mutual-funds/search")
def search_mf(q: str = "", plan: str = "direct", scheme_type: str = ""):
    """Search Zerodha MF instruments by name with filters."""
    return zerodha_service.search_mf_instruments(q, plan=plan, scheme_type=scheme_type)


@app.post("/api/mutual-funds/buy")
def add_mf_holding_endpoint(req: AddMFRequest):
    """Add a mutual fund holding (Buy transaction)."""
    try:
        result = mf_db.add_mf_holding(
            fund_code=req.fund_code,
            fund_name=req.fund_name,
            units=req.units,
            nav=req.nav,
            buy_date=req.buy_date,
            remarks=req.remarks,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/mutual-funds/redeem")
def redeem_mf_units_endpoint(req: RedeemMFRequest):
    """Redeem mutual fund units (Sell transaction)."""
    sell_date = req.sell_date or datetime.now().strftime("%Y-%m-%d")
    try:
        result = mf_db.add_mf_sell_transaction(
            fund_code=req.fund_code,
            units=req.units,
            nav=req.nav,
            sell_date=sell_date,
            remarks=req.remarks,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════
#  CDSL CAS STATEMENT IMPORT
# ══════════════════════════════════════════════════════════

from .cdsl_cas_parser import parse_cdsl_cas


@app.post("/api/mutual-funds/parse-cdsl-cas")
def parse_cdsl_cas_endpoint(req: CDSLCASUpload):
    """Parse a CDSL CAS statement PDF and return preview with dedup flags."""
    import base64
    try:
        pdf_bytes = base64.b64decode(req.pdf_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 PDF data")
    try:
        result = parse_cdsl_cas(pdf_bytes)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Failed to parse CDSL CAS statement: {e}")


@app.post("/api/mutual-funds/import-cdsl-cas-confirmed")
def import_cdsl_cas_confirmed(req: MFImportPayload):
    """Import confirmed (non-duplicate) transactions from CDSL CAS statement."""
    buys = 0
    sells = 0
    skipped = 0
    errors = []

    for fund in req.funds:
        fund_code = fund.get("fund_code", "")
        fund_name = fund.get("fund_name", "")
        for tx in fund.get("transactions", []):
            if tx.get("isDuplicate"):
                skipped += 1
                continue
            try:
                action = tx.get("action", "Buy")
                if action == "Buy":
                    mf_db.add_mf_holding(
                        fund_code=fund_code,
                        fund_name=fund_name,
                        units=float(tx["units"]),
                        nav=float(tx["nav"]),
                        buy_date=tx["date"],
                        remarks=tx.get("description", ""),
                    )
                    buys += 1
                elif action == "Sell":
                    mf_db.add_mf_sell_transaction(
                        fund_code=fund_code,
                        units=float(tx["units"]),
                        nav=float(tx["nav"]),
                        sell_date=tx["date"],
                        remarks=tx.get("description", ""),
                    )
                    sells += 1
            except ValueError as e:
                if "Duplicate" in str(e):
                    skipped += 1
                else:
                    errors.append(f"{fund_name}: {tx.get('date', '?')} — {e}")
            except Exception as e:
                errors.append(f"{fund_name}: {tx.get('date', '?')} — {e}")

    return {
        "imported": {"buys": buys, "sells": sells},
        "skipped_duplicates": skipped,
        "errors": errors,
    }


# ══════════════════════════════════════════════════════════
#  SIP CONFIGURATION
# ══════════════════════════════════════════════════════════

from .sip_manager import sip_mgr


@app.get("/api/mutual-funds/sip")
def get_sip_configs():
    """Get all SIP configurations."""
    return sip_mgr.load_configs()


@app.post("/api/mutual-funds/sip")
def add_sip_config(req: SIPConfigRequest):
    """Add or update a SIP configuration."""
    try:
        result = sip_mgr.add_sip(
            fund_code=req.fund_code,
            fund_name=req.fund_name,
            amount=req.amount,
            frequency=req.frequency,
            sip_date=req.sip_date,
            start_date=req.start_date,
            end_date=req.end_date,
            enabled=req.enabled,
            notes=req.notes,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/mutual-funds/sip/{fund_code:path}")
def delete_sip_config_endpoint(fund_code: str):
    """Delete a SIP configuration."""
    try:
        sip_mgr.delete_sip(fund_code)
        return {"message": f"SIP for {fund_code} deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/mutual-funds/sip/pending")
def get_pending_sips():
    """Get SIPs due for execution today."""
    return sip_mgr.get_pending_sips()


@app.post("/api/mutual-funds/sip/execute/{fund_code:path}")
def execute_sip_endpoint(fund_code: str):
    """Execute a pending SIP — creates a Buy entry using current NAV."""
    configs = sip_mgr.load_configs()
    config = next((c for c in configs if c["fund_code"] == fund_code), None)
    if not config:
        raise HTTPException(status_code=404, detail=f"No SIP config for {fund_code}")
    if not config.get("enabled", True):
        raise HTTPException(status_code=400, detail="SIP is disabled")

    # Get current NAV from the fund's Index sheet
    current_nav = mf_db.get_fund_nav(fund_code)
    if current_nav <= 0:
        raise HTTPException(status_code=400, detail="Current NAV unavailable. Update the fund's xlsx first.")

    amount = config["amount"]
    units = round(amount / current_nav, 6)
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        result = mf_db.add_mf_holding(
            fund_code=fund_code,
            fund_name=config["fund_name"],
            units=units,
            nav=current_nav,
            buy_date=today,
            remarks=f"SIP: ₹{amount:.0f} {config['frequency']}",
        )
        sip_mgr.mark_processed(fund_code, today)
        return {
            "message": f"SIP executed: {units:.4f} units @ ₹{current_nav:.4f}",
            "units": units,
            "nav": current_nav,
            "amount": amount,
            "next_sip_date": sip_mgr.load_configs()
                              and next((c["next_sip_date"] for c in sip_mgr.load_configs()
                                       if c["fund_code"] == fund_code), ""),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════
#  FIXED DEPOSITS
# ══════════════════════════════════════════════════════════

from .fd_database import get_all as fd_get_all, get_dashboard as fd_get_dashboard, add as fd_add, update as fd_update, delete as fd_delete


@app.get("/api/fixed-deposits/summary")
def get_fd_summary():
    """List all Fixed Deposits."""
    return fd_get_all()


@app.get("/api/fixed-deposits/dashboard")
def get_fd_dashboard():
    """Aggregate FD totals for dashboard."""
    return fd_get_dashboard()


@app.post("/api/fixed-deposits/add")
def add_fd_endpoint(req: AddFDRequest):
    """Add a new Fixed Deposit."""
    try:
        return fd_add(req.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/fixed-deposits/{fd_id}")
def update_fd_endpoint(fd_id: str, req: UpdateFDRequest):
    """Update an existing Fixed Deposit."""
    try:
        return fd_update(fd_id, req.dict(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/fixed-deposits/{fd_id}")
def delete_fd_endpoint(fd_id: str):
    """Delete a Fixed Deposit."""
    try:
        return fd_delete(fd_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ══════════════════════════════════════════════════════════
#  RECURRING DEPOSITS
# ══════════════════════════════════════════════════════════

from .rd_database import get_all as rd_get_all, get_dashboard as rd_get_dashboard, add as rd_add, update as rd_update, delete as rd_delete, add_installment as rd_add_installment


@app.get("/api/recurring-deposits/summary")
def get_rd_summary():
    """List all Recurring Deposits."""
    return rd_get_all()


@app.get("/api/recurring-deposits/dashboard")
def get_rd_dashboard():
    """Aggregate RD totals for dashboard."""
    return rd_get_dashboard()


@app.post("/api/recurring-deposits/add")
def add_rd_endpoint(req: AddRDRequest):
    """Add a new Recurring Deposit."""
    try:
        return rd_add(req.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/recurring-deposits/{rd_id}")
def update_rd_endpoint(rd_id: str, req: UpdateRDRequest):
    """Update an existing Recurring Deposit."""
    try:
        return rd_update(rd_id, req.dict(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/recurring-deposits/{rd_id}")
def delete_rd_endpoint(rd_id: str):
    """Delete a Recurring Deposit."""
    try:
        return rd_delete(rd_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/recurring-deposits/{rd_id}/installment")
def add_rd_installment_endpoint(rd_id: str, req: AddRDInstallmentRequest):
    """Add an installment to a Recurring Deposit."""
    try:
        return rd_add_installment(rd_id, req.dict())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════
#  INSURANCE POLICIES
# ══════════════════════════════════════════════════════════

from .insurance_database import get_all as ins_get_all, get_dashboard as ins_get_dashboard, add as ins_add, update as ins_update, delete as ins_delete


@app.get("/api/insurance/summary")
def get_insurance_summary():
    """List all Insurance Policies."""
    return ins_get_all()


@app.get("/api/insurance/dashboard")
def get_insurance_dashboard():
    """Aggregate Insurance totals for dashboard."""
    return ins_get_dashboard()


@app.post("/api/insurance/add")
def add_insurance_endpoint(req: AddInsuranceRequest):
    """Add a new Insurance Policy."""
    try:
        return ins_add(req.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/insurance/{policy_id}")
def update_insurance_endpoint(policy_id: str, req: UpdateInsuranceRequest):
    """Update an existing Insurance Policy."""
    try:
        return ins_update(policy_id, req.dict(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/insurance/{policy_id}")
def delete_insurance_endpoint(policy_id: str):
    """Delete an Insurance Policy."""
    try:
        return ins_delete(policy_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ══════════════════════════════════════════════════════════
#  PPF (PUBLIC PROVIDENT FUND)
# ══════════════════════════════════════════════════════════

from .ppf_database import get_all as ppf_get_all, get_dashboard as ppf_get_dashboard, add as ppf_add, update as ppf_update, delete as ppf_delete, add_contribution as ppf_add_contribution, withdraw as ppf_withdraw


@app.get("/api/ppf/summary")
def get_ppf_summary():
    """List all PPF accounts."""
    return ppf_get_all()


@app.get("/api/ppf/dashboard")
def get_ppf_dashboard():
    """Aggregate PPF totals for dashboard."""
    return ppf_get_dashboard()


@app.post("/api/ppf/add")
def add_ppf_endpoint(req: AddPPFRequest):
    """Add a new PPF account."""
    try:
        return ppf_add(req.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/ppf/{ppf_id}")
def update_ppf_endpoint(ppf_id: str, req: UpdatePPFRequest):
    """Update an existing PPF account."""
    try:
        return ppf_update(ppf_id, req.dict(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/ppf/{ppf_id}")
def delete_ppf_endpoint(ppf_id: str):
    """Delete a PPF account."""
    try:
        return ppf_delete(ppf_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/ppf/{ppf_id}/contribution")
def add_ppf_contribution_endpoint(ppf_id: str, req: AddPPFContributionRequest):
    """Add a contribution to a PPF account."""
    try:
        return ppf_add_contribution(ppf_id, req.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/ppf/{ppf_id}/withdraw")
def withdraw_ppf_endpoint(ppf_id: str, req: PPFWithdrawRequest):
    """Withdraw from a PPF account."""
    try:
        data = req.dict()
        if not data.get("date"):
            data["date"] = datetime.now().strftime("%Y-%m-%d")
        return ppf_withdraw(ppf_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════
#  NPS (NATIONAL PENSION SYSTEM)
# ══════════════════════════════════════════════════════════

from .nps_database import get_all as nps_get_all, get_dashboard as nps_get_dashboard, add as nps_add, update as nps_update, delete as nps_delete, add_contribution as nps_add_contribution


@app.get("/api/nps/summary")
def get_nps_summary():
    """List all NPS accounts."""
    return nps_get_all()


@app.get("/api/nps/dashboard")
def get_nps_dashboard():
    """Aggregate NPS totals for dashboard."""
    return nps_get_dashboard()


@app.post("/api/nps/add")
def add_nps_endpoint(req: AddNPSRequest):
    """Add a new NPS account."""
    try:
        return nps_add(req.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/nps/{nps_id}")
def update_nps_endpoint(nps_id: str, req: UpdateNPSRequest):
    """Update an existing NPS account."""
    try:
        return nps_update(nps_id, req.dict(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/nps/{nps_id}")
def delete_nps_endpoint(nps_id: str):
    """Delete an NPS account."""
    try:
        return nps_delete(nps_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/nps/{nps_id}/contribution")
def add_nps_contribution_endpoint(nps_id: str, req: AddNPSContributionRequest):
    """Add a contribution to an NPS account."""
    try:
        return nps_add_contribution(nps_id, req.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════
#  STANDING INSTRUCTIONS
# ══════════════════════════════════════════════════════════

from .si_database import get_all as si_get_all, get_dashboard as si_get_dashboard, add as si_add, update as si_update, delete as si_delete


@app.get("/api/standing-instructions/summary")
def get_si_summary():
    """List all Standing Instructions."""
    return si_get_all()


@app.get("/api/standing-instructions/dashboard")
def get_si_dashboard():
    """Aggregate SI totals for dashboard."""
    return si_get_dashboard()


@app.post("/api/standing-instructions/add")
def add_si_endpoint(req: AddSIRequest):
    """Add a new Standing Instruction."""
    try:
        return si_add(req.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/standing-instructions/{si_id}")
def update_si_endpoint(si_id: str, req: UpdateSIRequest):
    """Update an existing Standing Instruction."""
    try:
        return si_update(si_id, req.dict(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/standing-instructions/{si_id}")
def delete_si_endpoint(si_id: str):
    """Delete a Standing Instruction."""
    try:
        return si_delete(si_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
        # No-cache on index.html so browser always fetches fresh version
        # (hashed JS/CSS assets are still cached normally)
        return FileResponse(
            os.path.join(FRONTEND_DIST, "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
