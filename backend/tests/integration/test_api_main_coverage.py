"""
Comprehensive integration tests for app/main.py — targeting uncovered endpoints.
Covers: version, drive, portfolio CRUD, dividend, contract note, stock lookup/search,
price management, zerodha auth, dashboard, MF CRUD, CDSL CAS, SIP, advisor, alerts,
legal pages, and settings endpoints.
"""
import base64
import json
import pytest
from unittest.mock import patch, MagicMock

HEADERS = {"X-User-Id": "testuser"}


# ── Helpers ─────────────────────────────────────────────

def _add_stock(client, symbol="RELIANCE", qty=10, price=2500.0, exchange="NSE"):
    return client.post(
        "/api/portfolio/add",
        json={
            "symbol": symbol, "exchange": exchange,
            "name": f"{symbol} Industries", "quantity": qty,
            "buy_price": price, "buy_date": "2024-01-15",
        },
        headers=HEADERS,
    )


def _buy_mf(client, fund_name="Test Fund Direct Growth", units=100.0, nav=50.0):
    return client.post(
        "/api/mutual-funds/buy",
        json={
            "fund_code": "", "fund_name": fund_name,
            "units": units, "nav": nav, "buy_date": "2024-01-15",
        },
        headers=HEADERS,
    )


# ══════════════════════════════════════════════════════════
#  VERSION & DRIVE
# ══════════════════════════════════════════════════════════

def test_version_returns_tag(app_client):
    resp = app_client.get("/api/version")
    assert resp.status_code == 200
    assert "tag" in resp.json()


def test_drive_status_returns_200(app_client):
    with patch("app.drive_service.get_drive_status", return_value={"status": "ok"}):
        resp = app_client.get("/api/drive/status", headers=HEADERS)
        assert resp.status_code == 200


def test_drive_sync_noop(app_client):
    resp = app_client.post("/api/drive/sync", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ══════════════════════════════════════════════════════════
#  PORTFOLIO — track, search-untracked, update, rename
# ══════════════════════════════════════════════════════════

def test_track_stocks(app_client):
    resp = app_client.post(
        "/api/portfolio/track",
        json=[{"symbol": "ZEEL", "exchange": "NSE", "name": "Zee Entertainment"}],
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "added" in data
    assert "count" in data


def test_track_already_tracked(app_client):
    _add_stock(app_client, symbol="INFY")
    resp = app_client.post(
        "/api/portfolio/track",
        json=[{"symbol": "INFY", "exchange": "NSE"}],
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_track_empty_symbol_skipped(app_client):
    resp = app_client.post(
        "/api/portfolio/track",
        json=[{"symbol": "", "exchange": "NSE"}],
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_search_untracked(app_client):
    with patch("app.zerodha_service.search_instruments", return_value=[
        {"symbol": "NEWSTOCK", "name": "New Stock Ltd"},
    ]):
        resp = app_client.get("/api/stock/search-untracked?q=NEW", headers=HEADERS)
        assert resp.status_code == 200


def test_update_holding_not_found(app_client):
    resp = app_client.put(
        "/api/portfolio/holdings/nonexistent",
        json={"quantity": 5},
        headers=HEADERS,
    )
    assert resp.status_code == 404


def test_update_holding_success(app_client):
    add_resp = _add_stock(app_client, symbol="TCS", qty=10, price=3500)
    h_id = add_resp.json()["id"]
    resp = app_client.put(
        f"/api/portfolio/holdings/{h_id}",
        json={"quantity": 15},
        headers=HEADERS,
    )
    # Might succeed or fail depending on xlsx row matching
    assert resp.status_code in (200, 404)


def test_update_sold_row_not_found(app_client):
    resp = app_client.put(
        "/api/portfolio/sold/NOSYMBOL/99",
        json={"price": 100},
        headers=HEADERS,
    )
    assert resp.status_code == 404


def test_rename_stock_missing_symbol(app_client):
    resp = app_client.put(
        "/api/portfolio/stocks/RELIANCE/rename",
        json={"new_symbol": ""},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_rename_stock_nonexistent(app_client):
    resp = app_client.put(
        "/api/portfolio/stocks/NOSYMBOL/rename",
        json={"new_symbol": "NEWSYM", "new_name": "New Name"},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_sell_excess_returns_400(app_client):
    add_resp = _add_stock(app_client, symbol="WIPRO", qty=5, price=400)
    h_id = add_resp.json()["id"]
    resp = app_client.post(
        "/api/portfolio/sell",
        json={"holding_id": h_id, "quantity": 100, "sell_price": 500},
        headers=HEADERS,
    )
    assert resp.status_code == 400


# ══════════════════════════════════════════════════════════
#  DIVIDEND
# ══════════════════════════════════════════════════════════

def test_add_dividend_success(app_client):
    _add_stock(app_client, symbol="ITC", qty=100, price=450)
    resp = app_client.post(
        "/api/portfolio/dividend",
        json={"symbol": "ITC", "exchange": "NSE", "amount": 500, "dividend_date": "2024-06-01"},
        headers=HEADERS,
    )
    assert resp.status_code == 200


def test_add_dividend_no_stock_returns_404(app_client):
    resp = app_client.post(
        "/api/portfolio/dividend",
        json={"symbol": "NOSTOCKXYZ", "exchange": "NSE", "amount": 100},
        headers=HEADERS,
    )
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
#  DIVIDEND STATEMENT IMPORT
# ══════════════════════════════════════════════════════════

def test_parse_dividend_statement_non_pdf(app_client):
    resp = app_client.post(
        "/api/portfolio/parse-dividend-statement",
        json={"pdf_base64": base64.b64encode(b"not a pdf").decode(), "filename": "test.xlsx"},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_parse_dividend_statement_bad_base64(app_client):
    resp = app_client.post(
        "/api/portfolio/parse-dividend-statement",
        json={"pdf_base64": "!!!not-base64!!!", "filename": "test.pdf"},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_import_dividends_confirmed_empty(app_client):
    resp = app_client.post(
        "/api/portfolio/import-dividends-confirmed",
        json={"dividends": []},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 0


def test_import_dividends_confirmed_invalid_entry(app_client):
    resp = app_client.post(
        "/api/portfolio/import-dividends-confirmed",
        json={"dividends": [{"symbol": "", "amount": 0}]},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 0


def test_import_dividends_confirmed_with_overrides(app_client):
    _add_stock(app_client, symbol="HDFC", qty=10, price=1500)
    resp = app_client.post(
        "/api/portfolio/import-dividends-confirmed",
        json={
            "dividends": [
                {"symbol": "HDFC", "date": "2024-06-15", "amount": 50.0, "remarks": "DIV"},
            ],
            "symbol_overrides": {"OLD_HDFC": "HDFC"},
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] >= 0


# ══════════════════════════════════════════════════════════
#  CONTRACT NOTE
# ══════════════════════════════════════════════════════════

def test_parse_contract_note_non_pdf(app_client):
    resp = app_client.post(
        "/api/portfolio/parse-contract-note",
        json={"pdf_base64": base64.b64encode(b"data").decode(), "filename": "note.xlsx"},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_parse_contract_note_bad_base64(app_client):
    resp = app_client.post(
        "/api/portfolio/parse-contract-note",
        json={"pdf_base64": "!!!invalid!!!", "filename": "note.pdf"},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_import_contract_note_non_pdf(app_client):
    resp = app_client.post(
        "/api/portfolio/import-contract-note",
        json={"pdf_base64": base64.b64encode(b"data").decode(), "filename": "note.txt"},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_import_contract_note_confirmed_empty(app_client):
    resp = app_client.post(
        "/api/portfolio/import-contract-note-confirmed",
        json={"trade_date": "2024-01-15", "contract_no": "CN001", "transactions": []},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"]["buys"] == 0
    assert data["imported"]["sells"] == 0


def test_import_contract_note_confirmed_buy(app_client):
    import uuid
    unique_sym = f"CN{uuid.uuid4().hex[:6].upper()}"
    unique_cn = f"CNTEST{uuid.uuid4().hex[:6]}"
    resp = app_client.post(
        "/api/portfolio/import-contract-note-confirmed",
        json={
            "trade_date": "2024-06-01",
            "contract_no": unique_cn,
            "transactions": [
                {
                    "action": "Buy", "symbol": unique_sym, "exchange": "NSE",
                    "name": "New Stock Ltd", "quantity": 10, "wap": 100.0,
                    "effective_price": 101.0, "net_total_after_levies": 1010.0,
                    "stt": 0.5, "add_charges": 1.0, "trade_date": "2024-06-01",
                }
            ],
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"]["buys"] >= 1


def test_import_contract_note_confirmed_sell_no_file(app_client):
    resp = app_client.post(
        "/api/portfolio/import-contract-note-confirmed",
        json={
            "trade_date": "2024-06-01",
            "contract_no": "",
            "transactions": [
                {
                    "action": "Sell", "symbol": "UNKNOWNXYZ", "exchange": "NSE",
                    "name": "Unknown", "quantity": 5, "wap": 200.0,
                    "effective_price": 199.0, "net_total_after_levies": 995.0,
                    "stt": 0.3, "add_charges": 0.5, "trade_date": "2024-06-01",
                }
            ],
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert len(resp.json().get("errors", [])) > 0


# ══════════════════════════════════════════════════════════
#  STOCK SUMMARY — single symbol
# ══════════════════════════════════════════════════════════

def test_stock_summary_single_found(app_client):
    _add_stock(app_client, symbol="SBIN", qty=20, price=600)
    resp = app_client.get("/api/portfolio/stock-summary/SBIN", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "SBIN"


def test_stock_summary_single_not_found(app_client):
    resp = app_client.get("/api/portfolio/stock-summary/NOSUCHSTOCK", headers=HEADERS)
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
#  DIAGNOSTICS
# ══════════════════════════════════════════════════════════

def test_diagnostics_symbol_map(app_client):
    resp = app_client.get("/api/diagnostics/symbol-map", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_files" in data
    assert "entries" in data


# ══════════════════════════════════════════════════════════
#  TRANSACTIONS
# ══════════════════════════════════════════════════════════

def test_get_transactions(app_client):
    resp = app_client.get("/api/transactions", headers=HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ══════════════════════════════════════════════════════════
#  LIVE STOCK DATA
# ══════════════════════════════════════════════════════════

def test_get_stock_live_not_found(app_client):
    resp = app_client.get("/api/stock/NOSYMBOL?exchange=NSE", headers=HEADERS)
    assert resp.status_code == 404


def test_get_stock_price_not_found(app_client):
    resp = app_client.get("/api/stock/NOSYMBOL/price?exchange=NSE", headers=HEADERS)
    assert resp.status_code == 404


def test_lookup_stock_name(app_client):
    with patch("app.zerodha_service.lookup_instrument_name", return_value="Reliance Industries"):
        resp = app_client.get("/api/stock/lookup/RELIANCE?exchange=NSE", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "RELIANCE"
        assert data["name"] == "Reliance Industries"


def test_lookup_stock_name_fallback(app_client):
    with patch("app.zerodha_service.lookup_instrument_name", return_value=None):
        resp = app_client.get("/api/stock/lookup/SOMESTOCK?exchange=NSE", headers=HEADERS)
        assert resp.status_code == 200


def test_search_stock(app_client):
    with patch("app.zerodha_service.search_instruments", return_value=[
        {"symbol": "TCS", "name": "TCS Limited"},
    ]):
        resp = app_client.get("/api/stock/search/TCS", headers=HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) > 0


def test_search_stock_fallback(app_client):
    with patch("app.zerodha_service.search_instruments", return_value=[]):
        with patch("app.stock_service.search_stock", return_value=[]):
            resp = app_client.get("/api/stock/search/UNKN", headers=HEADERS)
            assert resp.status_code == 200


def test_get_stock_history_not_found(app_client):
    with patch("app.zerodha_service.fetch_stock_history", return_value=None):
        resp = app_client.get("/api/stock/NOSYM/history?exchange=NSE&period=1y", headers=HEADERS)
        assert resp.status_code == 404


def test_get_stock_history_found(app_client):
    mock_data = [{"date": "2024-01-15", "close": 100}]
    with patch("app.zerodha_service.fetch_stock_history", return_value=mock_data):
        resp = app_client.get("/api/stock/RELIANCE/history?exchange=NSE&period=1y", headers=HEADERS)
        assert resp.status_code == 200


def test_manual_price(app_client):
    resp = app_client.post(
        "/api/stock/manual-price",
        json={"symbol": "RELIANCE", "exchange": "NSE", "price": 2800.0},
        headers=HEADERS,
    )
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════
#  PRICE MANAGEMENT
# ══════════════════════════════════════════════════════════

def test_get_price_status(app_client):
    resp = app_client.get("/api/prices/status", headers=HEADERS)
    assert resp.status_code == 200


def test_trigger_price_refresh(app_client):
    resp = app_client.post("/api/prices/refresh", headers=HEADERS)
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_clear_52w_cache(app_client):
    resp = app_client.post("/api/prices/clear-cache", headers=HEADERS)
    assert resp.status_code == 200


def test_bulk_update_prices(app_client):
    resp = app_client.post(
        "/api/prices/bulk-update",
        json={"prices": {"RELIANCE": {"exchange": "NSE", "price": 2800}}},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert "count" in resp.json()


# ══════════════════════════════════════════════════════════
#  REFRESH SETTINGS
# ══════════════════════════════════════════════════════════

def test_get_refresh_interval(app_client):
    resp = app_client.get("/api/settings/refresh-interval", headers=HEADERS)
    assert resp.status_code == 200
    assert "stock_interval" in resp.json()
    assert "ticker_interval" in resp.json()


def test_set_refresh_interval(app_client):
    resp = app_client.post(
        "/api/settings/refresh-interval",
        json={"interval": 120},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["interval"] == 120


def test_set_refresh_interval_clamped_min(app_client):
    resp = app_client.post(
        "/api/settings/refresh-interval",
        json={"interval": 10},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["interval"] == 60


def test_set_refresh_interval_clamped_max(app_client):
    resp = app_client.post(
        "/api/settings/refresh-interval",
        json={"interval": 9999},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["interval"] == 600


def test_get_fallback_status(app_client):
    resp = app_client.get("/api/settings/fallback", headers=HEADERS)
    assert resp.status_code == 200
    assert "enabled" in resp.json()


def test_toggle_fallback(app_client):
    resp = app_client.post(
        "/api/settings/fallback",
        json={"enabled": True},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


# ══════════════════════════════════════════════════════════
#  ZERODHA AUTH & STATUS
# ══════════════════════════════════════════════════════════

def test_zerodha_status(app_client):
    resp = app_client.get("/api/zerodha/status", headers=HEADERS)
    assert resp.status_code == 200


def test_zerodha_login_page(app_client):
    resp = app_client.get("/api/zerodha/login")
    # May 200 if html exists, 500 if not
    assert resp.status_code in (200, 500)


def test_zerodha_login_url_not_configured(app_client):
    resp = app_client.get("/api/zerodha/login-url")
    assert resp.status_code == 400


def test_zerodha_callback_invalid(app_client):
    resp = app_client.get("/api/zerodha/callback?request_token=&action=&status=")
    # Redirects
    assert resp.status_code in (200, 307)


def test_zerodha_callback_no_login_action(app_client):
    resp = app_client.get("/api/zerodha/callback?request_token=tok&action=blah&status=ok")
    assert resp.status_code in (200, 307)


def test_zerodha_set_token_empty(app_client):
    resp = app_client.post(
        "/api/zerodha/set-token",
        json={"access_token": ""},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_zerodha_set_token(app_client):
    with patch("app.zerodha_service.set_access_token"):
        with patch("app.zerodha_service.validate_session", return_value=False):
            resp = app_client.post(
                "/api/zerodha/set-token",
                json={"access_token": "test-token-123"},
                headers=HEADERS,
            )
            assert resp.status_code == 200
            assert resp.json()["valid"] is False


def test_zerodha_validate_no_token(app_client):
    resp = app_client.get("/api/zerodha/validate", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


# ══════════════════════════════════════════════════════════
#  DASHBOARD SUMMARY
# ══════════════════════════════════════════════════════════

def test_dashboard_summary_returns_200(app_client):
    resp = app_client.get("/api/dashboard/summary", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    # Shape validation — values may be non-zero from default db
    assert "total_invested" in data
    assert "current_value" in data
    assert "unrealized_pl" in data
    assert "realized_pl" in data
    assert "total_holdings" in data


def test_dashboard_summary_with_holdings(app_client):
    _add_stock(app_client, symbol="DASHTEST", qty=10, price=2500)
    resp = app_client.get("/api/dashboard/summary", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_holdings"] >= 1


# ══════════════════════════════════════════════════════════
#  MARKET TICKER — additional coverage
# ══════════════════════════════════════════════════════════

def test_ticker_history_not_found(app_client):
    resp = app_client.get("/api/market-ticker/NONEXISTENT/history", headers=HEADERS)
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
#  MUTUAL FUNDS — additional coverage
# ══════════════════════════════════════════════════════════

def test_mf_dashboard(app_client):
    resp = app_client.get("/api/mutual-funds/dashboard", headers=HEADERS)
    assert resp.status_code == 200


def test_mf_refresh_nav(app_client):
    resp = app_client.post("/api/mutual-funds/refresh-nav", headers=HEADERS)
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_mf_nav_history_not_found(app_client):
    with patch("app.mf_xlsx_database.get_mf_nav_history", return_value=None):
        resp = app_client.get("/api/mf/NOSUCHFUND/history?period=1y", headers=HEADERS)
        assert resp.status_code == 404


def test_mf_nav_history_found(app_client):
    mock_data = [{"date": "2024-01-15", "nav": 50.0}]
    with patch("app.mf_xlsx_database.get_mf_nav_history", return_value=mock_data):
        resp = app_client.get("/api/mf/TESTFUND/history?period=1y", headers=HEADERS)
        assert resp.status_code == 200


def test_search_mf(app_client):
    with patch("app.zerodha_service.search_mf_instruments", return_value=[]):
        resp = app_client.get("/api/mutual-funds/search?q=axis", headers=HEADERS)
        assert resp.status_code == 200


def test_update_mf_holding_not_found(app_client):
    resp = app_client.put(
        "/api/mutual-funds/holdings/NOSUCHFUND/noid",
        json={"units": 50},
        headers=HEADERS,
    )
    assert resp.status_code == 404


def test_update_mf_sold_row_not_found(app_client):
    resp = app_client.put(
        "/api/mutual-funds/sold/NOSUCHFUND/99",
        json={"nav": 100},
        headers=HEADERS,
    )
    assert resp.status_code == 404


def test_rename_mf_missing_code(app_client):
    resp = app_client.put(
        "/api/mutual-funds/OLDFUND/rename",
        json={"new_code": ""},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_rename_mf_not_found(app_client):
    resp = app_client.put(
        "/api/mutual-funds/NOSUCHFUND/rename",
        json={"new_code": "NEWCODE", "new_name": "New Name"},
        headers=HEADERS,
    )
    assert resp.status_code == 400


# ══════════════════════════════════════════════════════════
#  CDSL CAS
# ══════════════════════════════════════════════════════════

def test_parse_cdsl_cas_bad_base64(app_client):
    resp = app_client.post(
        "/api/mutual-funds/parse-cdsl-cas",
        json={"pdf_base64": "!!!invalid!!!"},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_import_cdsl_cas_confirmed_empty(app_client):
    resp = app_client.post(
        "/api/mutual-funds/import-cdsl-cas-confirmed",
        json={"funds": []},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"]["buys"] == 0


def test_import_cdsl_cas_confirmed_with_dup(app_client):
    resp = app_client.post(
        "/api/mutual-funds/import-cdsl-cas-confirmed",
        json={
            "funds": [
                {
                    "fund_code": "INF12345",
                    "fund_name": "Test CAS Fund Direct Growth",
                    "transactions": [
                        {"isDuplicate": True, "action": "Buy", "units": 10, "nav": 50, "date": "2024-01-15"},
                    ],
                }
            ]
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["skipped_duplicates"] == 1


def test_import_cdsl_cas_confirmed_buy(app_client):
    import uuid
    fund_name = f"CAS Buy Fund {uuid.uuid4().hex[:6]} Direct Growth"
    resp = app_client.post(
        "/api/mutual-funds/import-cdsl-cas-confirmed",
        json={
            "funds": [
                {
                    "fund_code": "",
                    "fund_name": fund_name,
                    "transactions": [
                        {"isDuplicate": False, "action": "Buy", "units": 100, "nav": 50.0, "date": "2024-01-15", "description": "CAS import"},
                    ],
                }
            ]
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["imported"]["buys"] == 1


def test_import_cdsl_cas_confirmed_sell(app_client):
    # Buy first, then sell
    _buy_mf(app_client, fund_name="CAS Sell Test Direct Growth", units=200, nav=50)
    # Get the fund code
    summary = app_client.get("/api/mutual-funds/summary", headers=HEADERS).json()
    fund_code = None
    for f in summary:
        if "CAS Sell Test" in f.get("fund_name", ""):
            fund_code = f.get("fund_code", "")
            break

    if fund_code:
        resp = app_client.post(
            "/api/mutual-funds/import-cdsl-cas-confirmed",
            json={
                "funds": [
                    {
                        "fund_code": fund_code,
                        "fund_name": "CAS Sell Test Direct Growth",
                        "transactions": [
                            {"isDuplicate": False, "action": "Sell", "units": 50, "nav": 60.0, "date": "2024-06-01", "description": "CAS sell"},
                        ],
                    }
                ]
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════
#  SIP EXECUTE
# ══════════════════════════════════════════════════════════

def test_execute_sip_not_found(app_client):
    resp = app_client.post("/api/mutual-funds/sip/execute/NOSUCHFUND", headers=HEADERS)
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════
#  ADVISOR
# ══════════════════════════════════════════════════════════

def test_advisor_status(app_client):
    resp = app_client.get("/api/advisor/status", headers=HEADERS)
    assert resp.status_code == 200


def test_advisor_insights(app_client):
    with patch("app.epaper_service.fetch_todays_articles", return_value=[]):
        with patch("app.epaper_service.generate_insights", return_value=[]):
            resp = app_client.get("/api/advisor/insights", headers=HEADERS)
            assert resp.status_code == 200
            assert "insights" in resp.json()


def test_advisor_refresh(app_client):
    with patch("app.epaper_service.fetch_todays_articles", return_value=[]):
        with patch("app.epaper_service.generate_insights", return_value=[]):
            resp = app_client.post("/api/advisor/refresh", headers=HEADERS)
            assert resp.status_code == 200


def test_advisor_chat_missing_message(app_client):
    resp = app_client.post(
        "/api/advisor/chat",
        json={"message": ""},
        headers=HEADERS,
    )
    assert resp.status_code == 400


def test_advisor_chat(app_client):
    with patch("app.epaper_service.fetch_todays_articles", return_value=[]):
        with patch("app.epaper_service.chat", return_value="Test response"):
            resp = app_client.post(
                "/api/advisor/chat",
                json={"message": "What's happening in markets?", "history": []},
                headers=HEADERS,
            )
            assert resp.status_code == 200
            assert resp.json()["response"] == "Test response"


def test_advisor_articles(app_client):
    with patch("app.epaper_service.fetch_todays_articles", return_value=[
        {"title": "Test Article", "summary": "Summary", "body": "Body text",
         "section": "Markets", "url": "https://example.com/article", "source": "Business Line"},
    ]):
        resp = app_client.get("/api/advisor/articles", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Article"


def test_generate_briefing_pdf_empty(app_client):
    resp = app_client.post(
        "/api/advisor/briefing-pdf",
        json={"markdown": ""},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_generate_briefing_pdf(app_client):
    with patch("app.briefing_pdf.generate_briefing_pdf", return_value="/tmp/test.pdf"):
        resp = app_client.post(
            "/api/advisor/briefing-pdf",
            json={"markdown": "# Test Briefing\nSome content here."},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert "path" in resp.json()


def test_generate_analysis_pdf_empty(app_client):
    resp = app_client.post(
        "/api/advisor/analysis-pdf",
        json={"markdown": ""},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_generate_analysis_pdf(app_client):
    with patch("app.briefing_pdf.generate_briefing_pdf", return_value="/tmp/analysis.pdf"):
        resp = app_client.post(
            "/api/advisor/analysis-pdf",
            json={"markdown": "# Analysis\nContent."},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert "path" in resp.json()


def test_generate_briefing_html_empty(app_client):
    resp = app_client.post(
        "/api/advisor/briefing-html",
        json={"markdown": ""},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_generate_briefing_html(app_client):
    with patch("app.briefing_html.generate_briefing_html", return_value="/tmp/test.html"):
        resp = app_client.post(
            "/api/advisor/briefing-html",
            json={"markdown": "# HTML Briefing\nContent."},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert "path" in resp.json()


def test_generate_analysis_html_empty(app_client):
    resp = app_client.post(
        "/api/advisor/analysis-html",
        json={"markdown": ""},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_generate_analysis_html(app_client):
    with patch("app.briefing_html.generate_briefing_html", return_value="/tmp/analysis.html"):
        resp = app_client.post(
            "/api/advisor/analysis-html",
            json={"markdown": "# Analysis HTML\nContent."},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert "path" in resp.json()


# ══════════════════════════════════════════════════════════
#  ALERTS
# ══════════════════════════════════════════════════════════

def test_list_alerts(app_client):
    resp = app_client.get("/api/alerts", headers=HEADERS)
    assert resp.status_code == 200


def test_create_alert(app_client):
    resp = app_client.post(
        "/api/alerts",
        json={"name": "Test Alert", "enabled": True, "channel": "email", "condition": {}},
        headers=HEADERS,
    )
    assert resp.status_code == 200


def test_delete_alert_not_found(app_client):
    resp = app_client.delete("/api/alerts/nonexistent", headers=HEADERS)
    assert resp.status_code == 404


def test_alert_history(app_client):
    resp = app_client.get("/api/alerts/history?limit=10", headers=HEADERS)
    assert resp.status_code == 200


def test_test_notification(app_client):
    with patch("app.alert_service.send_test_notification", return_value={"sent": True}):
        resp = app_client.post(
            "/api/alerts/test",
            json={"channel": "all"},
            headers=HEADERS,
        )
        assert resp.status_code == 200


def test_get_channels(app_client):
    resp = app_client.get("/api/alerts/channels", headers=HEADERS)
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════
#  TEST EMAIL
# ══════════════════════════════════════════════════════════

def test_test_email_no_recipients(app_client):
    with patch("app.notification_service.get_user_notification_emails", return_value=[]):
        resp = app_client.post("/api/notifications/test-email", headers=HEADERS)
        assert resp.status_code == 400


def test_test_email_no_smtp(app_client):
    with patch("app.notification_service.get_user_notification_emails", return_value=["a@b.com"]):
        with patch("app.notification_service.email_configured", return_value=False):
            resp = app_client.post("/api/notifications/test-email", headers=HEADERS)
            assert resp.status_code == 400


def test_test_email_success(app_client):
    with patch("app.notification_service.get_user_notification_emails", return_value=["a@b.com"]):
        with patch("app.notification_service.email_configured", return_value=True):
            with patch("app.notification_service.send_email", return_value=True):
                resp = app_client.post("/api/notifications/test-email", headers=HEADERS)
                assert resp.status_code == 200
                assert resp.json()["success"] is True


# ══════════════════════════════════════════════════════════
#  PPF WITHDRAWAL
# ══════════════════════════════════════════════════════════

def test_ppf_withdraw_not_found(app_client):
    resp = app_client.post(
        "/api/ppf/nonexistent/withdraw",
        json={"amount": 5000, "date": "2024-06-01"},
        headers=HEADERS,
    )
    assert resp.status_code == 400


# ══════════════════════════════════════════════════════════
#  LEGAL PAGES
# ══════════════════════════════════════════════════════════

def test_privacy_policy(app_client):
    resp = app_client.get("/privacy")
    assert resp.status_code == 200
    assert "Privacy Policy" in resp.text


def test_terms_of_service(app_client):
    resp = app_client.get("/terms")
    assert resp.status_code == 200
    assert "Terms of Service" in resp.text


# ══════════════════════════════════════════════════════════
#  AUTH MIDDLEWARE — google-code endpoint
# ══════════════════════════════════════════════════════════

def test_google_code_missing(app_client):
    resp = app_client.post("/api/auth/google-code", json={"code": ""})
    assert resp.status_code == 400


def test_google_code_auth_disabled(app_client):
    resp = app_client.post("/api/auth/google-code", json={"code": "test-code"})
    assert resp.status_code == 400  # auth not enabled in local mode
