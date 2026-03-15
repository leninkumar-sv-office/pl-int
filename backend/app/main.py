"""
Stock Portfolio Dashboard - FastAPI Backend
"""
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict, Optional
from datetime import date, datetime, timedelta
import os
import json
import uuid
import time
import threading
import traceback
import contextvars

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
    DividendStatementUpload,
)
from .xlsx_database import xlsx_db as db, XlsxPortfolio
from .mf_xlsx_database import mf_db, clear_nav_cache as clear_mf_nav_cache, MFXlsxPortfolio
from .config import get_users, save_users, get_user_dumps_dir, get_user_email, get_users_for_email
from . import stock_service
from . import zerodha_service
from . import contract_note_parser
from . import dividend_parser
from . import epaper_service
from . import auth as auth_module
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

    # Check Zerodha connection — auto-login if token expired/missing
    if zerodha_service.is_configured():
        if zerodha_service.is_session_valid():
            # Validate existing token
            valid = zerodha_service.validate_session()
            if valid:
                print(f"[App] Zerodha configured — session valid, API key: {zerodha_service._api_key[:4]}...")
            elif zerodha_service.can_auto_login():
                print("[App] Zerodha token expired — attempting auto-login...")
                if zerodha_service.auto_login():
                    print("[App] Zerodha auto-login successful!")
                else:
                    print("[App] Zerodha auto-login failed — visit /api/zerodha/login")
            else:
                print("[App] Zerodha token invalid — visit /api/zerodha/login-url or POST /api/zerodha/set-token")
        elif zerodha_service.can_auto_login():
            print("[App] Zerodha no access token — attempting auto-login...")
            if zerodha_service.auto_login():
                print("[App] Zerodha auto-login successful!")
            else:
                print("[App] Zerodha auto-login failed — visit /api/zerodha/login")
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
    print("[App] Background market ticker refresh started (every 60s)")

    # Migrate: seed drive_folder_id for the primary email from env var
    try:
        default_folder_id = os.getenv("GOOGLE_DRIVE_DUMPS_FOLDER_ID", "").strip()
        primary_email = os.getenv("USER_EMAIL", "").strip().lower()
        if default_folder_id and primary_email:
            existing = auth_module.get_drive_folder_id(primary_email)
            if not existing:
                auth_module.set_drive_folder_id(primary_email, default_folder_id)
                print(f"[App] Seeded drive_folder_id for {primary_email}")
    except Exception as e:
        print(f"[App] Token migration skipped: {e}")

    # Sync data from Google Drive — blocks startup until complete
    # so that database modules find files on first request
    try:
        from app import drive_service
        drive_service.sync_all_emails()
    except Exception as e:
        print(f"[App] Drive sync skipped: {e}")

    # Re-index MF database after Drive sync (files may have arrived after module import)
    mf_db.reindex()
    print(f"[App] MF database re-indexed: {len(mf_db._file_map)} funds")


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


# Auth middleware — blocks unauthenticated requests when AUTH_MODE=google
# Also validates persona ownership (X-User-Id must belong to authenticated email)
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    email_token = None
    if auth_module.is_auth_enabled():
        path = request.url.path
        # Allow auth endpoints, Zerodha browser pages, static files, and health checks through
        if not (path.startswith("/api/auth/") or path.startswith("/assets/")
                or path == "/" or path == "/favicon.ico"
                or path == "/health" or path == "/api/version"
                or path.startswith("/api/zerodha/")
                or not path.startswith("/api/")):
            auth_header = request.headers.get("authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})
            session = auth_module.verify_session_token(auth_header[7:])
            if not session:
                return JSONResponse(status_code=401, content={"detail": "Invalid or expired session"})

            # Set email context for this request
            email_token = _current_email.set(session["email"])

            # Validate persona ownership
            requested_user_id = request.headers.get("x-user-id", "")
            if requested_user_id:
                persona_email = get_user_email(requested_user_id)
                if persona_email and persona_email.lower() != session["email"].lower():
                    _current_email.reset(email_token)
                    return JSONResponse(
                        status_code=403,
                        content={"detail": f"Persona '{requested_user_id}' does not belong to your account"}
                    )
    try:
        return await call_next(request)
    finally:
        if email_token is not None:
            _current_email.reset(email_token)


# User context middleware — sets _current_user_id from X-User-Id header
@app.middleware("http")
async def user_context_middleware(request: Request, call_next):
    user_id = request.headers.get("x-user-id", "")
    token = _current_user_id.set(user_id)
    try:
        response = await call_next(request)
        return response
    finally:
        _current_user_id.reset(token)


# ══════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ══════════════════════════════════════════════════════════

# Per-request user context (set by middleware)
_current_user_id: contextvars.ContextVar[str] = contextvars.ContextVar('_current_user_id', default='')
_current_email: contextvars.ContextVar[str] = contextvars.ContextVar('_current_email', default='')

# Per-user DB instances: {(user_id, email): {"stocks": XlsxPortfolio, "mf": MFXlsxPortfolio}}
_user_dbs: Dict[tuple, dict] = {}
_user_dbs_lock = threading.Lock()


def _get_default_user_id() -> str:
    email = _current_email.get()
    if email:
        owned = get_users_for_email(email)
        return owned[0]["id"] if owned else ""
    users = get_users()
    return users[0]["id"] if users else "lenin"


def _resolve_email() -> str:
    """Get authenticated email for the current request."""
    return _current_email.get() or ""


def _get_user_dbs(user_id: str) -> dict:
    """Get or create DB instances for a user."""
    email = _resolve_email() or get_user_email(user_id) or ""
    cache_key = (user_id, email)
    with _user_dbs_lock:
        if cache_key in _user_dbs:
            return _user_dbs[cache_key]
    # Outside lock — create instances (I/O)
    dumps = get_user_dumps_dir(user_id, email=email or None)
    from .mf_xlsx_database import MFXlsxPortfolio
    dbs = {
        "stocks": XlsxPortfolio(dumps / "Stocks"),
        "mf": MFXlsxPortfolio(dumps / "Mutual Funds"),
        "dumps_dir": dumps,
    }
    with _user_dbs_lock:
        _user_dbs[cache_key] = dbs
    return dbs


def _resolve_user_id() -> str:
    """Get the current request's user ID from contextvar."""
    uid = _current_user_id.get()
    return uid or _get_default_user_id()


def udb():
    """Get stock DB for the current request's user."""
    uid = _resolve_user_id()
    if uid == _get_default_user_id() and not _resolve_email():
        return db
    return _get_user_dbs(uid)["stocks"]


def umf():
    """Get MF DB for the current request's user."""
    uid = _resolve_user_id()
    if uid == _get_default_user_id() and not _resolve_email():
        return mf_db
    return _get_user_dbs(uid)["mf"]


def user_dumps_dir():
    """Get dumps dir for the current request's user."""
    uid = _resolve_user_id()
    email = _resolve_email() or get_user_email(uid)
    return get_user_dumps_dir(uid, email=email)


def _auto_provision_user(email: str, google_name: str):
    """Auto-create persona, dumps dirs, and Drive folders for a new email.

    Runs on every login but is idempotent — skips if persona already exists.
    """
    from app import drive_service
    email = email.lower()
    existing = get_users_for_email(email)
    if existing:
        # Already has persona(s) — just ensure Drive folder exists
        import threading
        threading.Thread(target=drive_service.init_drive_for_email, args=(email,), daemon=True).start()
        return

    # Create default persona from Google profile name
    display_name = google_name.strip() or email.split("@")[0]
    user_id = display_name.lower().replace(" ", "_")

    # Ensure unique ID
    users = get_users()
    base_id = user_id
    counter = 1
    while any(u["id"] == user_id for u in users):
        user_id = f"{base_id}_{counter}"
        counter += 1

    user = {
        "id": user_id,
        "name": display_name,
        "avatar": display_name[0].upper(),
        "color": "#4e7cff",
        "email": email,
    }
    users.append(user)
    save_users(users)

    # Create dumps directories
    get_user_dumps_dir(user_id, email=email)

    # Init Drive folders in background
    import threading
    threading.Thread(target=drive_service.init_drive_for_email, args=(email,), daemon=True).start()

    print(f"[App] Auto-provisioned persona '{display_name}' ({user_id}) for {email}")


@app.get("/api/users")
def list_users():
    """Get all configured users. If authenticated, returns only personas belonging to the user's email."""
    email = _resolve_email()
    if email:
        return get_users_for_email(email)
    return get_users()


class AddUserRequest(BaseModel):
    name: str
    avatar: str = ""
    color: str = "#4e7cff"


@app.post("/api/users")
def add_user(req: AddUserRequest):
    """Add a new user. Automatically links to the authenticated email."""
    users = get_users()
    user_id = req.name.lower().replace(" ", "_")
    if any(u["id"] == user_id for u in users):
        raise HTTPException(400, f"User '{user_id}' already exists")
    email = _resolve_email()
    user = {"id": user_id, "name": req.name, "avatar": req.avatar or req.name[0].upper(), "color": req.color}
    if email:
        user["email"] = email
    users.append(user)
    save_users(users)
    # Create user's dump directories
    get_user_dumps_dir(user_id, email=email or None)
    return user


# ══════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════

@app.get("/api/version")
def get_version():
    """Return the deployed version tag."""
    tag_file = os.path.join(os.path.dirname(__file__), "..", "data", "deploy_tag.txt")
    tag = "dev"
    if os.path.exists(tag_file):
        tag = open(tag_file).read().strip() or "dev"
    return {"tag": tag}


@app.get("/health")
def health_check():
    """Comprehensive health check — verifies all app subsystems."""
    checks = {}
    healthy = True

    # 1. Stock database
    try:
        holdings = db.get_all_holdings()
        checks["stocks"] = {"status": "ok", "holdings": len(holdings)}
    except Exception as e:
        checks["stocks"] = {"status": "error", "error": str(e)}
        healthy = False

    # 2. Mutual fund database
    try:
        fund_count = len(mf_db._file_map)
        checks["mutual_funds"] = {"status": "ok", "funds": fund_count}
        if fund_count == 0:
            checks["mutual_funds"]["status"] = "warn"
            checks["mutual_funds"]["message"] = "No funds indexed"
    except Exception as e:
        checks["mutual_funds"] = {"status": "error", "error": str(e)}
        healthy = False

    # 3. Dumps directory
    try:
        from .config import DUMPS_DIR
        dumps_exists = DUMPS_DIR.exists()
        checks["data_dir"] = {"status": "ok" if dumps_exists else "error", "path": str(DUMPS_DIR)}
        if not dumps_exists:
            healthy = False
    except Exception as e:
        checks["data_dir"] = {"status": "error", "error": str(e)}
        healthy = False

    # 4. Zerodha connection
    try:
        if zerodha_service.is_configured():
            session_valid = zerodha_service.is_session_valid()
            checks["zerodha"] = {"status": "ok" if session_valid else "warn",
                                 "configured": True, "session_valid": session_valid}
        else:
            checks["zerodha"] = {"status": "warn", "configured": False}
    except Exception as e:
        checks["zerodha"] = {"status": "error", "error": str(e)}

    # 5. Auth module
    try:
        checks["auth"] = {"status": "ok", "mode": auth_module.AUTH_MODE,
                          "enabled": auth_module.is_auth_enabled()}
    except Exception as e:
        checks["auth"] = {"status": "error", "error": str(e)}
        healthy = False

    # 6. Frontend build
    checks["frontend"] = {"status": "ok" if os.path.exists(FRONTEND_DIST) else "error",
                           "dist_exists": os.path.exists(FRONTEND_DIST)}
    if not os.path.exists(FRONTEND_DIST):
        healthy = False

    # Read deploy tag
    tag_file = os.path.join(os.path.dirname(__file__), "..", "data", "deploy_tag.txt")
    tag = "dev"
    if os.path.exists(tag_file):
        tag = open(tag_file).read().strip() or "dev"

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if healthy else "unhealthy", "tag": tag, "checks": checks}
    )


# ══════════════════════════════════════════════════════════
#  AUTHENTICATION ENDPOINTS
# ══════════════════════════════════════════════════════════

@app.get("/api/auth/status")
def auth_status():
    """Check if authentication is enabled and current config."""
    return {
        "auth_enabled": auth_module.is_auth_enabled(),
        "auth_mode": auth_module.AUTH_MODE,
        "google_client_id": auth_module.GOOGLE_CLIENT_ID if auth_module.is_auth_enabled() else "",
    }


@app.post("/api/auth/google")
def google_login(body: dict):
    """Verify Google ID token and return a session JWT."""
    id_token = body.get("token", "").strip()
    if not id_token:
        raise HTTPException(400, "token is required")
    if not auth_module.is_auth_enabled():
        raise HTTPException(400, "Google auth is not enabled (set AUTH_MODE=google)")
    user_info = auth_module.verify_google_token(id_token)
    if not user_info:
        raise HTTPException(401, "Invalid Google token or email not allowed")
    session_token = auth_module.create_session_token(user_info["email"], user_info["name"])
    return {
        "session_token": session_token,
        "email": user_info["email"],
        "name": user_info["name"],
        "picture": user_info["picture"],
    }


@app.post("/api/auth/google-code")
def google_login_with_code(body: dict):
    """Exchange Google OAuth authorization code for session + Drive tokens."""
    auth_code = body.get("code", "").strip()
    if not auth_code:
        raise HTTPException(400, "code is required")
    if not auth_module.is_auth_enabled():
        raise HTTPException(400, "Google auth is not enabled")
    try:
        result = auth_module.exchange_auth_code(auth_code)
    except ValueError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        print(f"[Auth] Code exchange failed: {e}")
        raise HTTPException(401, "Failed to exchange authorization code")
    # Auto-provision new user: persona + dumps dir + Drive folders
    _auto_provision_user(result["email"], result["name"])

    session_token = auth_module.create_session_token(result["email"], result["name"])
    return {
        "session_token": session_token,
        "email": result["email"],
        "name": result["name"],
        "picture": result["picture"],
    }


@app.get("/api/auth/verify")
def verify_session(request: Request):
    """Verify a session token is still valid."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "No token provided")
    session = auth_module.verify_session_token(auth_header[7:])
    if not session:
        raise HTTPException(401, "Invalid or expired session")
    return session


# ══════════════════════════════════════════════════════════
#  GOOGLE DRIVE SYNC ENDPOINTS
# ══════════════════════════════════════════════════════════

@app.get("/api/drive/status")
def drive_status():
    """Check Google Drive sync status."""
    from app import drive_service
    email = _resolve_email()
    return drive_service.get_drive_status(email)


@app.post("/api/drive/sync")
def drive_sync_now():
    """Trigger a full sync from Drive."""
    from app import drive_service
    email = _resolve_email()
    if email:
        drive_service.sync_from_drive(email)
    else:
        drive_service.sync_all_emails()
    return {"status": "ok", "message": "Sync complete"}


# ══════════════════════════════════════════════════════════
#  PORTFOLIO ENDPOINTS
# ══════════════════════════════════════════════════════════

@app.get("/api/portfolio", response_model=List[HoldingWithLive])
def get_portfolio():
    """Get all holdings with cached price data (instant, no network calls)."""
    holdings = udb().get_all_holdings()
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

    return udb().add_holding(holding)


@app.post("/api/portfolio/sell")
def sell_stock(req: SellStockRequest):
    """Sell shares from a holding — inserts a Sell row in the stock's xlsx."""
    holding = udb().get_holding_by_id(req.holding_id)
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
        udb().add_sell_transaction(
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
    if udb().remove_holding(holding_id):
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
        udb().add_dividend(
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
#  BANK STATEMENT DIVIDEND IMPORT
# ══════════════════════════════════════════════════════════

@app.post("/api/portfolio/parse-dividend-statement")
def parse_dividend_statement_preview(req: DividendStatementUpload):
    """Parse bank statement PDF for CEMTEX DEP dividend entries — no data is written."""
    import base64

    if not req.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    try:
        pdf_bytes = base64.b64decode(req.pdf_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 PDF data")

    try:
        result = dividend_parser.parse_dividend_statement(
            pdf_bytes=pdf_bytes,
            portfolio_name_map=dict(udb()._name_map),
            existing_fingerprints_fn=lambda sym: udb().get_existing_dividend_fingerprints(sym),
        )
    except Exception as e:
        print(f"[DividendImport] PDF parse error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {str(e)[:200]}")

    return result


@app.post("/api/portfolio/import-dividends-confirmed")
def import_dividends_confirmed(req: dict):
    """Import confirmed dividends from bank statement preview.

    Receives list of dividends (possibly symbol-edited by user).
    Server-side re-checks duplicates as safety net.
    """
    dividends = req.get("dividends", [])
    symbol_overrides = req.get("symbol_overrides", {})
    if not dividends:
        return {"message": "No dividends to import", "imported": 0, "skipped_duplicates": 0}

    # Persist user symbol overrides for future imports
    if symbol_overrides:
        try:
            dividend_parser.save_user_overrides(symbol_overrides)
        except Exception as e:
            print(f"[DividendImport] Failed to save overrides: {e}")

    imported = 0
    skipped_dups = 0
    errors = []
    details = []

    # Cache fingerprints per symbol for batch dedup
    _fp_cache: dict = {}

    for div in dividends:
        symbol = (div.get("symbol") or "").upper()
        div_date = div.get("date", "")
        amount = round(float(div.get("amount", 0)), 2)

        if not symbol or amount <= 0:
            errors.append(f"Invalid entry: {symbol} {amount}")
            continue

        # Server-side duplicate check
        if symbol not in _fp_cache:
            try:
                _fp_cache[symbol] = udb().get_existing_dividend_fingerprints(symbol)
            except Exception:
                _fp_cache[symbol] = set()

        fp = (div_date, amount)
        if fp in _fp_cache[symbol]:
            skipped_dups += 1
            continue

        try:
            udb().add_dividend(
                symbol=symbol,
                exchange="NSE",
                amount=amount,
                dividend_date=div_date,
                remarks=div.get("remarks", "DIVIDEND"),
            )
            imported += 1
            details.append({"symbol": symbol, "date": div_date, "amount": amount})
            # Update in-memory cache
            _fp_cache[symbol].add(fp)
        except FileNotFoundError:
            errors.append(f"{symbol}: No xlsx file found")
        except Exception as e:
            errors.append(f"{symbol}: {str(e)[:100]}")

    if imported > 0:
        udb().reindex()

    total_amount = sum(d["amount"] for d in details)
    return {
        "message": f"Imported {imported} dividend(s) totalling ₹{total_amount:.2f}",
        "imported": imported,
        "skipped_duplicates": skipped_dups,
        "errors": errors,
        "details": details,
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
                _fp_cache[symbol] = udb().get_existing_transaction_fingerprints(symbol)
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
                        _fp_cache[symbol] = udb().get_existing_transaction_fingerprints(symbol)
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
                filepath = udb()._find_file_for_symbol(tx["symbol"])
                if filepath is None:
                    filepath = udb()._create_stock_file(
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
                udb()._insert_transaction(filepath, buy_tx)
                udb()._invalidate_symbol(tx["symbol"])

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
                filepath = udb()._find_file_for_symbol(tx["symbol"])
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
                udb()._insert_transaction(filepath, sell_tx)
                udb()._invalidate_symbol(tx["symbol"])

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
    udb().reindex()

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
                        _fp_cache[symbol] = udb().get_existing_transaction_fingerprints(symbol)
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
                filepath = udb()._find_file_for_symbol(tx["symbol"])
                if filepath is None:
                    filepath = udb()._create_stock_file(
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
                udb()._insert_transaction(filepath, buy_tx)
                udb()._invalidate_symbol(tx["symbol"])

                imported_buys.append({
                    "symbol": tx["symbol"],
                    "name": tx.get("name", ""),
                    "quantity": tx["quantity"],
                })

            elif tx["action"] == "Sell":
                filepath = udb()._find_file_for_symbol(tx["symbol"])
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
                udb()._insert_transaction(filepath, sell_tx)
                udb()._invalidate_symbol(tx["symbol"])

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

    udb().reindex()

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
    holdings = udb().get_all_holdings()
    sold_positions = udb().get_all_sold()
    dividends_by_symbol = udb().get_dividends_by_symbol()

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
        has_primary_files = primary_symbol in udb()._all_files and len(udb()._all_files[primary_symbol]) > 0
        has_derived_files = derived in udb()._all_files and len(udb()._all_files[derived]) > 0
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
    return udb().get_all_sold()


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


@app.get("/api/stock/{symbol}/price")
def get_stock_price(symbol: str, exchange: str = "NSE"):
    """Fetch live price for any stock (triggers network call if not cached)."""
    data = stock_service.fetch_live_data(symbol.upper(), exchange.upper())
    if not data:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {symbol}")
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
    """Search for a stock by name or symbol. Tries Zerodha instruments first, falls back to Yahoo."""
    results = zerodha_service.search_instruments(query, exchange)
    if results:
        return results
    return stock_service.search_stock(query, exchange)


@app.get("/api/stock/{symbol}/history")
def get_stock_history(symbol: str, exchange: str = "NSE", period: str = "1y"):
    """Get historical OHLCV candle data for charting."""
    data = zerodha_service.fetch_stock_history(symbol.upper(), exchange.upper(), period)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No history for {symbol}.{exchange} ({period})")
    return data


@app.get("/api/market-ticker/{key}/history")
def get_ticker_history(key: str, period: str = "1y"):
    """Get historical candle data for a market ticker (SENSEX, NIFTY50, etc.)."""
    key = key.upper()
    # Find the ticker's instrument token from current cache
    with _ticker_lock:
        ticker = next((t for t in _ticker_cache if t.get("key") == key), None)
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker {key} not found")
    token = ticker.get("instrument_token")
    if not token:
        raise HTTPException(status_code=404, detail=f"No instrument token for {key}")
    data = zerodha_service.fetch_stock_history(key, "TICKER", period, instrument_token=token)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No history for {key} ({period})")
    return data


@app.post("/api/stock/manual-price")
def set_manual_price(req: ManualPriceRequest):
    """Manually set a stock price (fallback when Yahoo is unavailable)."""
    udb().set_manual_price(req.symbol.upper(), req.exchange.upper(), req.price)
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
        udb().reindex()
        stock_service.clear_cache()
        stock_service._reset_circuit()
        holdings = udb().get_all_holdings()
        sold = udb().get_all_sold()
        if not holdings and not sold:
            return
        symbols = list(set(
            [(h.symbol, h.exchange) for h in holdings] +
            [(s.symbol, s.exchange) for s in sold]
        ))
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
        reindex_result = udb().reindex()
        stock_service.clear_cache()
        stock_service._reset_circuit()
        holdings = udb().get_all_holdings()
        sold = udb().get_all_sold()
        if not holdings and not sold:
            return {"message": "No holdings found", "stocks": 0, "reindex": reindex_result}
        symbols = list(set(
            [(h.symbol, h.exchange) for h in holdings] +
            [(s.symbol, s.exchange) for s in sold]
        ))
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
def get_zerodha_login_url(request: Request):
    """Get Kite Connect login URL for browser auth."""
    if not zerodha_service.is_configured():
        raise HTTPException(status_code=400, detail="Zerodha API key not configured in .env")
    # Build callback URL from the request origin so it works for both
    # localhost:9999 and pl.thirumagal.com
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:9999"))
    redirect_url = f"{scheme}://{host}/api/zerodha/callback"
    url = zerodha_service.get_login_url(redirect_url=redirect_url)
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
    holdings = udb().get_all_holdings()
    sold_positions = udb().get_all_sold()
    dividends_map = udb().get_dividends_by_symbol()

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
    {"key": "GIFTNIFTY", "yahoo": "%5ENSEI",       "label": "GIFT Nifty", "type": "index",     "kite": True},
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
_TICKER_REFRESH_INTERVAL = 60    # 1 minute
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
    try:
        from app import drive_service
        drive_service.sync_data_file("market_ticker.json")
    except Exception:
        pass


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
        try:
            from app import drive_service
            drive_service.sync_data_file("market_ticker_history.json")
        except Exception:
            pass

    return history


def _enrich_ticker_changes(tickers: List[dict]) -> List[dict]:
    """Add week_change_pct and month_change_pct.
    Kite tickers: use Zerodha Historical Data API.
    Non-Kite tickers: use local ticker history file."""
    # Build {key: {instrument_token, ...}} from tickers that have tokens
    ticker_data = {}
    non_kite_keys = set()
    for t in tickers:
        t.setdefault("week_change_pct", 0.0)
        t.setdefault("month_change_pct", 0.0)
        token = t.get("instrument_token")
        if token and t.get("price", 0) > 0:
            ticker_data[t["key"]] = {"instrument_token": token}
        elif t.get("price", 0) > 0:
            non_kite_keys.add(t["key"])

    # Kite tickers: Zerodha Historical API
    if ticker_data:
        changes = zerodha_service.fetch_ticker_historical_changes(ticker_data)
        for t in tickers:
            ch = changes.get(t["key"])
            if ch:
                t["week_change_pct"] = ch["week_change_pct"]
                t["month_change_pct"] = ch["month_change_pct"]

    # Non-Kite tickers: use Yahoo Finance historical data
    if non_kite_keys:
        meta_map = {m["key"]: m for m in MARKET_TICKER_SYMBOLS}
        for t in tickers:
            if t["key"] not in non_kite_keys:
                continue
            meta = meta_map.get(t["key"])
            if not meta or not meta.get("yahoo"):
                continue
            try:
                ch = stock_service.fetch_yahoo_ticker_historical(meta)
                if ch:
                    t["week_change_pct"] = ch["week_change_pct"]
                    t["month_change_pct"] = ch["month_change_pct"]
            except Exception as e:
                print(f"[MarketTicker] Yahoo historical error for {t['key']}: {e}")

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

        # SOURCE 2: Yahoo/Google — always for non-Kite tickers, else only if explicitly enabled
        if not meta.get("kite", True) or stock_service.ENABLE_YAHOO_GOOGLE:
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
    Data is refreshed automatically every 60 seconds by background thread."""
    with _ticker_lock:
        if _ticker_cache:
            return {
                "tickers": _ticker_cache,
                "last_updated": datetime.fromtimestamp(_ticker_cache_time).isoformat() if _ticker_cache_time else None,
            }
    # Fallback: if background hasn't populated cache yet, load from file
    saved = _load_ticker_file()
    if saved:
        _enrich_ticker_changes(saved)
    return {"tickers": saved if saved else [], "last_updated": None}


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
    return umf().get_fund_summary()


@app.get("/api/mutual-funds/dashboard")
def get_mf_dashboard():
    """Get aggregated MF portfolio summary for the dashboard."""
    return umf().get_dashboard_summary()


@app.post("/api/mutual-funds/refresh-nav")
def refresh_mf_nav():
    """Clear MF NAV cache and re-fetch live NAVs."""
    clear_mf_nav_cache()
    summary = umf().get_fund_summary()
    with_nav = sum(1 for f in summary if f.get("current_nav", 0) > 0)
    return {"message": f"NAV refreshed: {with_nav}/{len(summary)} funds with live prices"}


@app.get("/api/mf/{fund_code}/history")
def get_mf_nav_history(fund_code: str, period: str = "1y", name: str = ""):
    """Get historical NAV data for charting a mutual fund."""
    from .mf_xlsx_database import get_mf_nav_history as _get_mf_nav_history
    data = _get_mf_nav_history(fund_code, period, fund_name=name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No history for {fund_code} ({period})")
    return data


@app.get("/api/mutual-funds/search")
def search_mf(q: str = "", plan: str = "direct", scheme_type: str = ""):
    """Search Zerodha MF instruments by name with filters."""
    return zerodha_service.search_mf_instruments(q, plan=plan, scheme_type=scheme_type)


@app.post("/api/mutual-funds/buy")
def add_mf_holding_endpoint(req: AddMFRequest):
    """Add a mutual fund holding (Buy transaction)."""
    try:
        result = umf().add_mf_holding(
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
        result = umf().add_mf_sell_transaction(
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
                    umf().add_mf_holding(
                        fund_code=fund_code,
                        fund_name=fund_name,
                        units=float(tx["units"]),
                        nav=float(tx["nav"]),
                        buy_date=tx["date"],
                        remarks=tx.get("description", ""),
                    )
                    buys += 1
                elif action == "Sell":
                    umf().add_mf_sell_transaction(
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
    current_nav = umf().get_fund_nav(fund_code)
    if current_nav <= 0:
        raise HTTPException(status_code=400, detail="Current NAV unavailable. Update the fund's xlsx first.")

    amount = config["amount"]
    units = round(amount / current_nav, 6)
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        result = umf().add_mf_holding(
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
    return fd_get_all(base_dir=user_dumps_dir())

@app.get("/api/fixed-deposits/dashboard")
def get_fd_dashboard():
    return fd_get_dashboard(base_dir=user_dumps_dir())

@app.post("/api/fixed-deposits/add")
def add_fd_endpoint(req: AddFDRequest):
    try:
        return fd_add(req.dict(), base_dir=user_dumps_dir())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/fixed-deposits/{fd_id}")
def update_fd_endpoint(fd_id: str, req: UpdateFDRequest):
    try:
        return fd_update(fd_id, req.dict(exclude_none=True), base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/fixed-deposits/{fd_id}")
def delete_fd_endpoint(fd_id: str):
    try:
        return fd_delete(fd_id, base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ══════════════════════════════════════════════════════════
#  RECURRING DEPOSITS
# ══════════════════════════════════════════════════════════

from .rd_database import get_all as rd_get_all, get_dashboard as rd_get_dashboard, add as rd_add, update as rd_update, delete as rd_delete, add_installment as rd_add_installment


@app.get("/api/recurring-deposits/summary")
def get_rd_summary():
    return rd_get_all(base_dir=user_dumps_dir())

@app.get("/api/recurring-deposits/dashboard")
def get_rd_dashboard():
    return rd_get_dashboard(base_dir=user_dumps_dir())

@app.post("/api/recurring-deposits/add")
def add_rd_endpoint(req: AddRDRequest):
    try:
        return rd_add(req.dict(), base_dir=user_dumps_dir())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/recurring-deposits/{rd_id}")
def update_rd_endpoint(rd_id: str, req: UpdateRDRequest):
    try:
        return rd_update(rd_id, req.dict(exclude_none=True), base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/recurring-deposits/{rd_id}")
def delete_rd_endpoint(fd_id: str):
    try:
        return rd_delete(fd_id, base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/recurring-deposits/{rd_id}/installment")
def add_rd_installment_endpoint(rd_id: str, req: AddRDInstallmentRequest):
    try:
        return rd_add_installment(rd_id, req.dict(), base_dir=user_dumps_dir())
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
    return ins_get_all(base_dir=user_dumps_dir())

@app.get("/api/insurance/dashboard")
def get_insurance_dashboard():
    return ins_get_dashboard(base_dir=user_dumps_dir())

@app.post("/api/insurance/add")
def add_insurance_endpoint(req: AddInsuranceRequest):
    try:
        return ins_add(req.dict(), base_dir=user_dumps_dir())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/insurance/{policy_id}")
def update_insurance_endpoint(policy_id: str, req: UpdateInsuranceRequest):
    try:
        return ins_update(policy_id, req.dict(exclude_none=True), base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/insurance/{policy_id}")
def delete_insurance_endpoint(policy_id: str):
    try:
        return ins_delete(policy_id, base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ══════════════════════════════════════════════════════════
#  PPF (PUBLIC PROVIDENT FUND)
# ══════════════════════════════════════════════════════════

from .ppf_database import get_all as ppf_get_all, get_dashboard as ppf_get_dashboard, add as ppf_add, update as ppf_update, delete as ppf_delete, add_contribution as ppf_add_contribution, withdraw as ppf_withdraw


@app.get("/api/ppf/summary")
def get_ppf_summary():
    return ppf_get_all(base_dir=user_dumps_dir())

@app.get("/api/ppf/dashboard")
def get_ppf_dashboard():
    return ppf_get_dashboard(base_dir=user_dumps_dir())

@app.post("/api/ppf/add")
def add_ppf_endpoint(req: AddPPFRequest):
    try:
        return ppf_add(req.dict(), base_dir=user_dumps_dir())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/ppf/{ppf_id}")
def update_ppf_endpoint(ppf_id: str, req: UpdatePPFRequest):
    try:
        return ppf_update(ppf_id, req.dict(exclude_none=True), base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/ppf/{ppf_id}")
def delete_ppf_endpoint(ppf_id: str):
    try:
        return ppf_delete(ppf_id, base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/ppf/{ppf_id}/contribution")
def add_ppf_contribution_endpoint(ppf_id: str, req: AddPPFContributionRequest):
    try:
        return ppf_add_contribution(ppf_id, req.dict(), base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/ppf/{ppf_id}/withdraw")
def withdraw_ppf_endpoint(ppf_id: str, req: PPFWithdrawRequest):
    try:
        data = req.dict()
        if not data.get("date"):
            data["date"] = datetime.now().strftime("%Y-%m-%d")
        return ppf_withdraw(ppf_id, data, base_dir=user_dumps_dir())
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
    return nps_get_all(base_dir=user_dumps_dir())

@app.get("/api/nps/dashboard")
def get_nps_dashboard():
    return nps_get_dashboard(base_dir=user_dumps_dir())

@app.post("/api/nps/add")
def add_nps_endpoint(req: AddNPSRequest):
    try:
        return nps_add(req.dict(), base_dir=user_dumps_dir())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/nps/{nps_id}")
def update_nps_endpoint(nps_id: str, req: UpdateNPSRequest):
    try:
        return nps_update(nps_id, req.dict(exclude_none=True), base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/nps/{nps_id}")
def delete_nps_endpoint(nps_id: str):
    try:
        return nps_delete(nps_id, base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/nps/{nps_id}/contribution")
def add_nps_contribution_endpoint(nps_id: str, req: AddNPSContributionRequest):
    try:
        return nps_add_contribution(nps_id, req.dict(), base_dir=user_dumps_dir())
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
    return si_get_all(base_dir=user_dumps_dir())

@app.get("/api/standing-instructions/dashboard")
def get_si_dashboard():
    return si_get_dashboard(base_dir=user_dumps_dir())

@app.post("/api/standing-instructions/add")
def add_si_endpoint(req: AddSIRequest):
    try:
        return si_add(req.dict(), base_dir=user_dumps_dir())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/standing-instructions/{si_id}")
def update_si_endpoint(si_id: str, req: UpdateSIRequest):
    try:
        return si_update(si_id, req.dict(exclude_none=True), base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/standing-instructions/{si_id}")
def delete_si_endpoint(si_id: str):
    try:
        return si_delete(si_id, base_dir=user_dumps_dir())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ══════════════════════════════════════════════════════════
#  ADVISOR (Business Line + AI Analysis)
# ══════════════════════════════════════════════════════════

@app.get("/api/advisor/status")
def advisor_status():
    return epaper_service.get_status()


@app.get("/api/advisor/insights")
def get_advisor_insights():
    """Get today's personalized financial insights from Business Line."""
    articles = epaper_service.fetch_todays_articles()
    # Get portfolio symbols for matching
    try:
        holdings = udb().get_all_holdings()
        symbols = list(set(h.symbol for h in holdings))
    except Exception:
        symbols = []
    insights = epaper_service.generate_insights(articles, symbols)
    return {
        "date": date.today().isoformat(),
        "insights": insights,
        "articles_count": len(articles),
        "has_ai": epaper_service.has_api_key(),
    }


@app.post("/api/advisor/refresh")
def refresh_advisor():
    """Force re-scrape articles and regenerate insights."""
    articles = epaper_service.fetch_todays_articles(force_refresh=True)
    try:
        holdings = udb().get_all_holdings()
        symbols = list(set(h.symbol for h in holdings))
    except Exception:
        symbols = []
    # Clear insights cache so they regenerate
    today = date.today().isoformat()
    with epaper_service._cache_lock:
        epaper_service._insights_cache.pop(today, None)
    insights = epaper_service.generate_insights(articles, symbols)
    return {
        "date": today,
        "insights": insights,
        "articles_count": len(articles),
        "has_ai": epaper_service.has_api_key(),
    }


@app.post("/api/advisor/chat")
def advisor_chat(body: dict):
    """Chat with the AI advisor about today's market news."""
    message = body.get("message", "").strip()
    history = body.get("history", [])
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    articles = epaper_service.fetch_todays_articles()
    try:
        holdings = udb().get_all_holdings()
        symbols = list(set(h.symbol for h in holdings))
    except Exception:
        symbols = []
    response = epaper_service.chat(message, articles, symbols, history)
    return {"response": response}


@app.get("/api/advisor/articles")
def get_advisor_articles():
    """Get raw scraped articles from Business Line + The Hindu."""
    articles = epaper_service.fetch_todays_articles()
    return [{
        "title": a["title"],
        "summary": a.get("summary", ""),
        "body": a.get("body", ""),
        "section": a["section"],
        "url": a["url"],
        "source": a.get("source", "Business Line"),
    } for a in articles]


@app.post("/api/advisor/briefing-pdf")
async def generate_briefing_pdf(request: Request):
    """Generate a PDF from markdown briefing text. Body: {"markdown": "..."}"""
    from .briefing_pdf import generate_briefing_pdf as gen_pdf
    body = await request.json()
    md = body.get("markdown", "")
    if not md:
        return {"error": "No markdown provided"}
    filepath = gen_pdf(md)
    filename = os.path.basename(filepath)
    return {"path": filepath, "filename": filename}


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
