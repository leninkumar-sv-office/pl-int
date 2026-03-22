"""
Shared test fixtures for the backend test suite.

Provides temporary data/dumps directories, a pre-configured FastAPI TestClient
with mocked external services, auth helpers, and sample data generators.
"""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Temporary data directory (replaces backend/data/)
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temp data dir populated with the required JSON seed files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # users.json — minimal user list
    (data_dir / "users.json").write_text(json.dumps([
        {
            "id": "testuser",
            "name": "TestUser",
            "avatar": "T",
            "color": "#4e7cff",
            "email": "test@example.com",
        }
    ]))

    # stock_prices.json — empty price cache
    (data_dir / "stock_prices.json").write_text(json.dumps({}))

    # market_ticker.json — empty ticker data
    (data_dir / "market_ticker.json").write_text(json.dumps({}))

    # market_ticker_history.json — empty history
    (data_dir / "market_ticker_history.json").write_text(json.dumps({}))

    # portfolio.json — legacy portfolio (empty)
    (data_dir / "portfolio.json").write_text(json.dumps({
        "holdings": [],
        "sold": [],
    }))

    # mf_scheme_map.json — empty scheme mapping
    (data_dir / "mf_scheme_map.json").write_text(json.dumps({}))

    # nav_history.json — empty NAV history
    (data_dir / "nav_history.json").write_text(json.dumps({}))

    # manual_prices.json — empty manual price overrides
    (data_dir / "manual_prices.json").write_text(json.dumps({}))

    # symbol_cache.json — empty symbol cache
    (data_dir / "symbol_cache.json").write_text(json.dumps({}))

    # .jwt_secret — deterministic secret for reproducible tokens
    (data_dir / ".jwt_secret").write_text("test-jwt-secret-for-pytest-only-00")

    return data_dir


# ---------------------------------------------------------------------------
# Temporary dumps directory (replaces backend/dumps/)
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dumps_dir(tmp_path):
    """Create a temp dumps dir with per-user asset subdirectories."""
    dumps_dir = tmp_path / "dumps"
    user_dir = dumps_dir / "test@example.com" / "TestUser"
    for sub in [
        "Stocks",
        "Mutual Funds",
        "FD",
        "RD",
        "PPF",
        "NPS",
        "Standing Instructions",
    ]:
        (user_dir / sub).mkdir(parents=True, exist_ok=True)
    return dumps_dir


# ---------------------------------------------------------------------------
# FastAPI TestClient with patched paths and mocked services
# ---------------------------------------------------------------------------

@pytest.fixture
def app_client(tmp_data_dir, tmp_dumps_dir):
    """
    Yield a ``TestClient`` wired to the real FastAPI app but with:

    * DATA_DIR / DUMPS_BASE pointed at temp directories
    * AUTH_MODE set to ``local`` (no Google OAuth required)
    * External services (Zerodha, Drive, stock_service) mocked out
    """
    # Force auth mode to local before anything imports auth
    os.environ["AUTH_MODE"] = "local"
    os.environ["JWT_SECRET"] = "test-jwt-secret-for-pytest-only-00"

    # --- Patch config paths ------------------------------------------------
    patches = [
        # config module paths
        patch("app.config.DUMPS_BASE", tmp_dumps_dir),
        patch("app.config._USERS_FILE", tmp_data_dir / "users.json"),

        # database module (legacy JSON DB)
        patch("app.database.DATA_DIR", str(tmp_data_dir)),
        patch("app.database.DB_FILE", str(tmp_data_dir / "portfolio.json")),

        # stock_service price file paths
        patch("app.stock_service._DATA_DIR", str(tmp_data_dir)),
        patch("app.stock_service._PRICES_FILE", str(tmp_data_dir / "stock_prices.json")),

        # mf_xlsx_database NAV paths
        patch("app.mf_xlsx_database._NAV_DATA_DIR", str(tmp_data_dir)),
        patch("app.mf_xlsx_database._SCHEME_MAP_FILE", str(tmp_data_dir / "mf_scheme_map.json")),

        # symbol_resolver cache
        patch("app.symbol_resolver._DATA_DIR", tmp_data_dir),
        patch("app.symbol_resolver._CACHE_FILE", tmp_data_dir / "symbol_cache.json"),

        # drive_service data dir
        patch("app.drive_service.DATA_DIR", tmp_data_dir),

        # dividend_parser data dir
        patch("app.dividend_parser.DATA_DIR", tmp_data_dir),

        # notification_service paths
        patch("app.notification_service.DUMPS_BASE", tmp_dumps_dir),
        patch("app.notification_service._LEGACY_PREFS_FILE", tmp_data_dir / "notification_prefs.json"),

        # alert_service paths
        patch("app.alert_service._DATA_DIR", tmp_data_dir),
        patch("app.alert_service._ALERTS_FILE", tmp_data_dir / "alerts.json"),
        patch("app.alert_service._HISTORY_FILE", tmp_data_dir / "alert_history.json"),

        # expiry_rules paths
        patch("app.expiry_rules.DUMPS_BASE", tmp_dumps_dir),
        patch("app.expiry_rules._LEGACY_RULES_FILE", tmp_data_dir / "expiry_rules.json"),

        # user_settings paths
        patch("app.user_settings.DUMPS_BASE", tmp_dumps_dir),

        # Mock external service calls so tests never hit the network
        patch("app.zerodha_service.is_configured", return_value=False),
        patch("app.zerodha_service.is_session_valid", return_value=False),
        patch("app.zerodha_service.fetch_quotes", return_value={}),
        patch("app.drive_service.sync_data_file", return_value=None),
        patch("app.drive_service.sync_dumps_file", return_value=None),
        patch("app.drive_service.upload_file", return_value=None),
        patch("app.stock_service.fetch_live_data", return_value=None),
    ]

    for p in patches:
        p.start()

    # Import app *after* patches are in place
    from app.main import app as fastapi_app

    client = TestClient(fastapi_app, raise_server_exceptions=False)
    yield client

    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# Auth helper — produces a valid JWT for test requests
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_token():
    """Generate a valid JWT session token for the test user."""
    # Use the same secret we seeded into tmp_data_dir / .jwt_secret
    import jwt as pyjwt
    import time

    payload = {
        "email": "test@example.com",
        "name": "TestUser",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return pyjwt.encode(payload, "test-jwt-secret-for-pytest-only-00", algorithm="HS256")


# ---------------------------------------------------------------------------
# Sample data generators
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_stock_xlsx(tmp_dumps_dir):
    """
    Create a minimal stock XLSX file (``TESTSTOCK.xlsx``) with a single
    Buy transaction and return the file path.
    """
    import openpyxl
    from datetime import date

    user_stocks_dir = tmp_dumps_dir / "test@example.com" / "TestUser" / "Stocks"
    filepath = user_stocks_dir / "TESTSTOCK.xlsx"

    wb = openpyxl.Workbook()

    # -- "Trading History" sheet (required by xlsx_database) --
    ws = wb.active
    ws.title = "Trading History"
    headers = ["Date", "Type", "Qty", "Price", "Exchange", "Notes"]
    ws.append(headers)
    ws.append([
        date(2024, 1, 15).isoformat(),  # Date
        "Buy",                           # Type
        10,                              # Qty
        150.00,                          # Price
        "NSE",                           # Exchange
        "",                              # Notes
    ])

    wb.save(filepath)
    return filepath
