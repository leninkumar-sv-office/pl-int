"""
Additional unit tests for app/zerodha_service.py — targeting uncovered lines.
Covers: _api_get edge cases, auto_login, fetch_historical_52w, SMA/RSI, instrument
loading, MF instruments, stock history, market tickers, ticker historical changes,
validate_session, get_status, _update_env.
"""
import time
import os
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta

import pytest


def _reset_globals():
    import app.zerodha_service as zs
    zs._access_token = "test_token"
    zs._api_key = "test_api_key"
    zs._api_secret = "test_secret"
    zs._auth_failed = False
    zs._conn_failed = False
    zs._conn_fail_time = 0.0
    zs._session_valid = True
    zs._last_error = ""
    zs._auto_login_in_progress = False


# ═══════════════════════════════════════════════════════════
#  _api_get edge cases
# ═══════════════════════════════════════════════════════════

class TestApiGet:
    def test_no_token_tries_auto_login(self):
        import app.zerodha_service as zs
        _reset_globals()
        zs._access_token = ""
        with patch.object(zs, "_try_auto_login_and_retry", return_value={"data": "ok"}) as m:
            result = zs._api_get("/test")
            assert result == {"data": "ok"}
            m.assert_called_once()

    def test_auth_failed_tries_auto_login(self):
        import app.zerodha_service as zs
        _reset_globals()
        zs._auth_failed = True
        with patch.object(zs, "_try_auto_login_and_retry", return_value=None):
            result = zs._api_get("/test")
            assert result is None

    def test_conn_failed_skips_if_recent(self):
        import app.zerodha_service as zs
        _reset_globals()
        zs._conn_failed = True
        zs._conn_fail_time = time.time()
        result = zs._api_get("/test")
        assert result is None
        zs._conn_failed = False

    def test_connection_error_sets_conn_failed(self):
        import app.zerodha_service as zs
        import requests as req_lib
        _reset_globals()
        with patch("app.zerodha_service.requests.get", side_effect=req_lib.exceptions.ConnectionError("refused")):
            with patch("app.zerodha_service.time.sleep"):
                result = zs._api_get("/test")
        assert result is None
        assert zs._conn_failed is True
        zs._conn_failed = False

    def test_non_200_non_403_non_429(self):
        import app.zerodha_service as zs
        _reset_globals()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch("app.zerodha_service.requests.get", return_value=mock_resp):
            result = zs._api_get("/test")
        assert result is None
        assert "500" in zs._last_error

    def test_403_auto_login_retry_succeeds(self):
        import app.zerodha_service as zs
        _reset_globals()
        mock_403 = MagicMock()
        mock_403.status_code = 403
        mock_403.text = "Token expired"
        with patch("app.zerodha_service.requests.get", return_value=mock_403):
            with patch.object(zs, "_try_auto_login_and_retry", return_value={"data": "ok"}):
                result = zs._api_get("/test")
        assert result == {"data": "ok"}


# ═══════════════════════════════════════════════════════════
#  _try_auto_login_and_retry
# ═══════════════════════════════════════════════════════════

class TestTryAutoLoginAndRetry:
    def test_cannot_auto_login(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "can_auto_login", return_value=False):
            result = zs._try_auto_login_and_retry("/test")
            assert result is None

    def test_in_progress(self):
        import app.zerodha_service as zs
        _reset_globals()
        zs._auto_login_in_progress = True
        with patch.object(zs, "can_auto_login", return_value=True):
            result = zs._try_auto_login_and_retry("/test")
            assert result is None
        zs._auto_login_in_progress = False

    def test_auto_login_fails(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "can_auto_login", return_value=True):
            with patch.object(zs, "auto_login", return_value=False):
                result = zs._try_auto_login_and_retry("/test")
                assert result is None

    def test_auto_login_succeeds_retry_succeeds(self):
        import app.zerodha_service as zs
        _reset_globals()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": "retried"}
        with patch.object(zs, "can_auto_login", return_value=True):
            with patch.object(zs, "auto_login", return_value=True):
                with patch("app.zerodha_service.requests.get", return_value=mock_resp):
                    result = zs._try_auto_login_and_retry("/test")
                    assert result == {"data": "retried"}

    def test_auto_login_succeeds_retry_fails(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "can_auto_login", return_value=True):
            with patch.object(zs, "auto_login", return_value=True):
                with patch("app.zerodha_service.requests.get", side_effect=Exception("fail")):
                    result = zs._try_auto_login_and_retry("/test")
                    assert result is None


# ═══════════════════════════════════════════════════════════
#  auto_login
# ═══════════════════════════════════════════════════════════

class TestAutoLogin:
    def test_missing_credentials(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "can_auto_login", return_value=False):
            assert zs.auto_login() is False

    def test_already_in_progress(self):
        import app.zerodha_service as zs
        _reset_globals()
        zs._auto_login_in_progress = True
        with patch.object(zs, "can_auto_login", return_value=True):
            assert zs.auto_login() is False
        zs._auto_login_in_progress = False

    def test_login_fails(self):
        import app.zerodha_service as zs
        _reset_globals()
        mock_login = MagicMock()
        mock_login.status_code = 401
        mock_login.text = "Bad credentials"
        mock_session = MagicMock()
        mock_session.post.return_value = mock_login
        with patch.object(zs, "can_auto_login", return_value=True):
            with patch("app.zerodha_service.requests.Session", return_value=mock_session):
                result = zs.auto_login()
        assert result is False

    def test_no_request_id(self):
        import app.zerodha_service as zs
        _reset_globals()
        mock_login = MagicMock()
        mock_login.status_code = 200
        mock_login.json.return_value = {"data": {}}
        mock_session = MagicMock()
        mock_session.post.return_value = mock_login
        with patch.object(zs, "can_auto_login", return_value=True):
            with patch("app.zerodha_service.requests.Session", return_value=mock_session):
                result = zs.auto_login()
        assert result is False

    def test_twofa_fails(self):
        import app.zerodha_service as zs
        _reset_globals()
        mock_login = MagicMock()
        mock_login.status_code = 200
        mock_login.json.return_value = {"data": {"request_id": "req123", "twofa_type": "app_code"}}
        mock_twofa = MagicMock()
        mock_twofa.status_code = 401
        mock_twofa.text = "Bad TOTP"
        mock_session = MagicMock()
        mock_session.post.side_effect = [mock_login, mock_twofa]
        with patch.object(zs, "can_auto_login", return_value=True):
            with patch("app.zerodha_service.requests.Session", return_value=mock_session):
                with patch("pyotp.TOTP") as mock_totp_cls:
                    mock_totp_cls.return_value.now.return_value = "123456"
                    result = zs.auto_login()
        assert result is False

    def test_exception(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "can_auto_login", return_value=True):
            with patch("app.zerodha_service.requests.Session", side_effect=Exception("boom")):
                result = zs.auto_login()
        assert result is False


# ═══════════════════════════════════════════════════════════
#  _fetch_historical_52w (SMA / RSI / signal)
# ═══════════════════════════════════════════════════════════

class TestFetchHistorical52w:
    def _make_candles(self, n=200, base=100):
        """Generate n daily candles."""
        from datetime import datetime, timedelta
        now = datetime.now()
        candles = []
        for i in range(n):
            dt = now - timedelta(days=n - i)
            ts = dt.strftime("%Y-%m-%d")
            price = base + i * 0.5
            candles.append([ts, price - 1, price + 2, price - 2, price, 100000])
        return candles

    def test_success_with_sma_rsi(self):
        import app.zerodha_service as zs
        candles = self._make_candles(250)
        api_response = {"data": {"candles": candles}}
        with patch.object(zs, "_api_get", return_value=api_response):
            result = zs._fetch_historical_52w(12345)
        assert result is not None
        assert result["week_52_high"] > 0
        assert result["week_52_low"] > 0
        assert result["sma_50"] is not None
        assert result["sma_200"] is not None
        assert result["signal"] in ("strong_bull", "weak_bull", "weak_bear", "strong_bear")
        assert result["rsi"] is not None

    def test_no_data(self):
        import app.zerodha_service as zs
        with patch.object(zs, "_api_get", return_value=None):
            result = zs._fetch_historical_52w(12345)
            assert result is None

    def test_empty_candles(self):
        import app.zerodha_service as zs
        with patch.object(zs, "_api_get", return_value={"data": {"candles": []}}):
            result = zs._fetch_historical_52w(12345)
            assert result is None

    def test_short_history(self):
        import app.zerodha_service as zs
        candles = self._make_candles(30)
        with patch.object(zs, "_api_get", return_value={"data": {"candles": candles}}):
            result = zs._fetch_historical_52w(12345)
        assert result is not None
        # With only 30 candles, sma_50 uses 20-day fallback
        assert result["sma_50"] is not None


# ═══════════════════════════════════════════════════════════
#  fetch_52_week_range (with cache)
# ═══════════════════════════════════════════════════════════

class TestFetch52WeekRange:
    def test_cached_result(self):
        import app.zerodha_service as zs
        _reset_globals()
        with zs._52w_cache_lock:
            zs._52w_cache["RELIANCE.NSE"] = {
                "week_52_high": 3000, "week_52_low": 2000,
                "week_change_pct": 1.5, "month_change_pct": 5.0,
                "sma_50": 2800, "sma_200": 2500, "signal": "strong_bull",
                "days_below_sma": 0, "rsi": 65.0, "fetched_at": time.time(),
            }
        with patch.object(zs, "is_session_valid", return_value=True):
            result = zs.fetch_52_week_range([("RELIANCE", "NSE")])
        assert result["RELIANCE.NSE"]["week_52_high"] == 3000
        with zs._52w_cache_lock:
            zs._52w_cache.clear()

    def test_no_instrument_token(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_get_instrument_token", return_value=None):
                result = zs.fetch_52_week_range([("NOTOKEN", "NSE")])
        assert result == {}


# ═══════════════════════════════════════════════════════════
#  Instrument loading
# ═══════════════════════════════════════════════════════════

class TestLoadInstruments:
    def test_load_instruments_success(self):
        import app.zerodha_service as zs
        _reset_globals()
        csv_data = "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n"
        csv_data += "12345,6789,RELIANCE,Reliance Industries,2500,,,0.05,1,EQ,NSE,NSE\n"
        csv_data += "12346,6790,TCS,Tata Consultancy Services,3600,,,0.05,1,EQ,NSE,NSE\n"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_data

        old_loaded_names = zs._instrument_names_loaded
        old_loaded_tokens = zs._instrument_tokens_loaded
        zs._instrument_names_loaded = False
        zs._instrument_tokens_loaded = False

        with patch("app.zerodha_service.requests.get", return_value=mock_resp):
            zs._load_instruments()

        assert "RELIANCE.NSE" in zs._instrument_names
        assert zs._instrument_token_cache.get("RELIANCE.NSE") == 12345
        zs._instrument_names_loaded = old_loaded_names
        zs._instrument_tokens_loaded = old_loaded_tokens

    def test_load_instruments_no_credentials(self):
        import app.zerodha_service as zs
        old_key = zs._api_key
        zs._api_key = ""
        old_loaded = zs._instrument_names_loaded
        zs._instrument_names_loaded = False
        zs._load_instruments()
        zs._api_key = old_key
        zs._instrument_names_loaded = old_loaded

    def test_load_instruments_async(self):
        import app.zerodha_service as zs
        with patch.object(zs, "_load_instruments"):
            zs.load_instruments_async()

    def test_lookup_instrument_name(self):
        import app.zerodha_service as zs
        zs._instrument_names["TEST.NSE"] = "Test Company"
        zs._instrument_names_loaded = True
        assert zs.lookup_instrument_name("TEST", "NSE") == "Test Company"
        assert zs.lookup_instrument_name("UNKNOWN", "NSE") == ""

    def test_search_instruments(self):
        import app.zerodha_service as zs
        zs._instrument_names.update({
            "RELIANCE.NSE": "Reliance Industries",
            "RELINFRA.NSE": "Reliance Infrastructure",
            "TCS.NSE": "Tata Consultancy Services",
        })
        zs._instrument_names_loaded = True
        results = zs.search_instruments("REL", "NSE")
        assert len(results) == 2
        assert results[0]["symbol"] == "RELIANCE"

    def test_search_instruments_empty_query(self):
        import app.zerodha_service as zs
        zs._instrument_names_loaded = True
        assert zs.search_instruments("") == []


# ═══════════════════════════════════════════════════════════
#  MF Instruments
# ═══════════════════════════════════════════════════════════

class TestMFInstruments:
    def test_load_mf_instruments(self):
        import app.zerodha_service as zs
        _reset_globals()
        csv_data = "tradingsymbol,amc,name,purchase_allowed,redemption_allowed,minimum_purchase_amount,purchase_amount_multiplier,minimum_additional_purchase_amount,minimum_redemption_quantity,redemption_quantity_multiplier,last_price,last_price_date,scheme_type,plan,settlement_type,dividend_type\n"
        csv_data += "INF123,Axis,Axis Direct Growth Fund,1,1,500,1,100,1,1,55.0,2024-01-15,equity,direct,T1,growth\n"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_data

        old_loaded = zs._mf_instruments_loaded
        zs._mf_instruments_loaded = False

        with patch("app.zerodha_service.requests.get", return_value=mock_resp):
            zs._load_mf_instruments()

        assert len(zs._mf_instruments) >= 1
        zs._mf_instruments_loaded = old_loaded

    def test_load_mf_no_credentials(self):
        import app.zerodha_service as zs
        old_key = zs._api_key
        zs._api_key = ""
        old_loaded = zs._mf_instruments_loaded
        zs._mf_instruments_loaded = False
        zs._load_mf_instruments()
        zs._api_key = old_key
        zs._mf_instruments_loaded = old_loaded

    def test_search_mf_instruments(self):
        import app.zerodha_service as zs
        zs._mf_instruments = [
            {"tradingsymbol": "INF123", "name": "Axis Bluechip Direct Growth",
             "amc": "AxisMF", "scheme_type": "equity", "plan": "direct",
             "dividend_type": "growth", "last_price": 55.0},
            {"tradingsymbol": "INF456", "name": "Axis Bluechip Regular Growth",
             "amc": "AxisMF", "scheme_type": "equity", "plan": "regular",
             "dividend_type": "growth", "last_price": 50.0},
        ]
        zs._mf_instruments_loaded = True
        results = zs.search_mf_instruments("Axis Bluechip", plan="direct")
        assert len(results) >= 1
        assert results[0]["plan"] == "direct"

    def test_search_mf_short_query(self):
        import app.zerodha_service as zs
        zs._mf_instruments_loaded = True
        assert zs.search_mf_instruments("A") == []

    def test_get_mf_ltp(self):
        import app.zerodha_service as zs
        zs._mf_instruments = [
            {"tradingsymbol": "INF999", "last_price": 123.45, "name": "Test",
             "amc": "Test", "plan": "direct", "dividend_type": "growth"},
        ]
        zs._mf_instruments_loaded = True
        assert zs.get_mf_ltp("INF999") == 123.45
        assert zs.get_mf_ltp("NOTFOUND") == 0.0


# ═══════════════════════════════════════════════════════════
#  Stock History
# ═══════════════════════════════════════════════════════════

class TestFetchStockHistory:
    def test_no_session(self):
        import app.zerodha_service as zs
        with patch.object(zs, "is_session_valid", return_value=False):
            result = zs.fetch_stock_history("RELIANCE", "NSE", "1y")
            assert result is None

    def test_invalid_period(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "is_session_valid", return_value=True):
            result = zs.fetch_stock_history("RELIANCE", "NSE", "invalid")
            assert result is None

    def test_no_instrument_token(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_get_instrument_token", return_value=None):
                result = zs.fetch_stock_history("NOTFOUND", "NSE", "1y")
                assert result is None

    def test_success_1y(self):
        import app.zerodha_service as zs
        _reset_globals()
        candles = [["2024-01-15T00:00:00", 100, 105, 95, 102, 50000]]
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_get_instrument_token", return_value=12345):
                with patch.object(zs, "_api_get", return_value={"data": {"candles": candles}}):
                    # Clear history cache first
                    with zs._history_cache_lock:
                        zs._history_cache.clear()
                    result = zs.fetch_stock_history("TEST", "NSE", "1y")
        assert result is not None
        assert len(result) == 1
        assert result[0]["close"] == 102

    def test_ytd_period(self):
        import app.zerodha_service as zs
        _reset_globals()
        candles = [["2024-06-15T00:00:00", 100, 105, 95, 102, 50000]]
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_get_instrument_token", return_value=12345):
                with patch.object(zs, "_api_get", return_value={"data": {"candles": candles}}):
                    with zs._history_cache_lock:
                        zs._history_cache.clear()
                    result = zs.fetch_stock_history("TEST", "NSE", "ytd")
        assert result is not None

    def test_cached_result(self):
        import app.zerodha_service as zs
        cached_data = [{"date": "2024-01-15", "open": 100, "high": 105, "low": 95, "close": 102, "volume": 50000}]
        with zs._history_cache_lock:
            zs._history_cache["CACHED.NSE.1y"] = {"data": cached_data, "fetched_at": time.time()}
        with patch.object(zs, "is_session_valid", return_value=True):
            result = zs.fetch_stock_history("CACHED", "NSE", "1y")
        assert result == cached_data
        with zs._history_cache_lock:
            zs._history_cache.clear()


# ═══════════════════════════════════════════════════════════
#  Market Tickers
# ═══════════════════════════════════════════════════════════

class TestMarketTickers:
    def test_near_month_suffixes(self):
        from app.zerodha_service import _get_near_month_suffixes
        suffixes = _get_near_month_suffixes()
        assert len(suffixes) == 3
        assert len(suffixes[0]) == 5  # e.g. "26MAR"

    def test_build_ticker_candidates(self):
        from app.zerodha_service import _build_ticker_candidates
        candidates = _build_ticker_candidates()
        assert "SENSEX" in candidates
        assert "NIFTY50" in candidates
        assert "GOLD" in candidates
        assert len(candidates["SGX"]) == 0  # international

    def test_fetch_market_tickers_no_session(self):
        import app.zerodha_service as zs
        with patch.object(zs, "is_session_valid", return_value=False):
            result = zs.fetch_market_tickers()
            assert result == {}

    def test_fetch_market_tickers_success(self):
        import app.zerodha_service as zs
        _reset_globals()
        api_response = {
            "data": {
                "BSE:SENSEX": {
                    "last_price": 72000.0,
                    "ohlc": {"close": 71800.0, "open": 71900, "high": 72100, "low": 71700},
                    "instrument_token": 99999,
                },
            }
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_response):
                result = zs.fetch_market_tickers()
        assert "SENSEX" in result
        assert result["SENSEX"]["price"] == 72000.0


# ═══════════════════════════════════════════════════════════
#  Ticker Historical Changes
# ═══════════════════════════════════════════════════════════

class TestTickerHistoricalChanges:
    def test_no_session(self):
        import app.zerodha_service as zs
        with patch.object(zs, "is_session_valid", return_value=False):
            result = zs.fetch_ticker_historical_changes({})
            assert result == {}

    def test_cached(self):
        import app.zerodha_service as zs
        _reset_globals()
        with zs._ticker_hist_lock:
            zs._ticker_hist_cache["SENSEX"] = {
                "prev_day_close": 71800,
                "week_change_pct": 1.5, "month_change_pct": 3.0,
                "fetched_at": time.time(),
            }
        with patch.object(zs, "is_session_valid", return_value=True):
            result = zs.fetch_ticker_historical_changes({
                "SENSEX": {"instrument_token": 99, "price": 72000},
            })
        assert result["SENSEX"]["week_change_pct"] == 1.5
        with zs._ticker_hist_lock:
            zs._ticker_hist_cache.clear()


# ═══════════════════════════════════════════════════════════
#  validate_session / get_status / _update_env
# ═══════════════════════════════════════════════════════════

class TestValidateSession:
    def test_valid(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value={"data": {"user_name": "Test"}}):
                assert zs.validate_session() is True

    def test_invalid(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=None):
                assert zs.validate_session() is False

    def test_no_session(self):
        import app.zerodha_service as zs
        with patch.object(zs, "is_session_valid", return_value=False):
            assert zs.validate_session() is False


class TestGetStatus:
    def test_returns_dict(self):
        import app.zerodha_service as zs
        _reset_globals()
        with patch.object(zs, "is_session_valid", return_value=True):
            status = zs.get_status()
        assert isinstance(status, dict)
        assert "configured" in status
        assert "has_access_token" in status
        assert "session_valid" in status


class TestUpdateEnv:
    def test_update_existing_key(self, tmp_path):
        import app.zerodha_service as zs
        env_file = tmp_path / ".env"
        env_file.write_text("ZERODHA_ACCESS_TOKEN=old_val\nOTHER=keep\n")
        old_path = zs._ENV_PATH
        zs._ENV_PATH = str(env_file)
        try:
            zs._update_env("ZERODHA_ACCESS_TOKEN", "new_val")
            content = env_file.read_text()
            assert "ZERODHA_ACCESS_TOKEN=new_val" in content
            assert "OTHER=keep" in content
        finally:
            zs._ENV_PATH = old_path

    def test_add_new_key(self, tmp_path):
        import app.zerodha_service as zs
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=val\n")
        old_path = zs._ENV_PATH
        zs._ENV_PATH = str(env_file)
        try:
            zs._update_env("NEW_KEY", "new_val")
            content = env_file.read_text()
            assert "NEW_KEY=new_val" in content
        finally:
            zs._ENV_PATH = old_path


# ═══════════════════════════════════════════════════════════
#  clear_52w_cache
# ═══════════════════════════════════════════════════════════

def test_clear_52w_cache():
    import app.zerodha_service as zs
    with zs._52w_cache_lock:
        zs._52w_cache["TEST.NSE"] = {"data": "test"}
    zs.clear_52w_cache()
    with zs._52w_cache_lock:
        assert zs._52w_cache == {}
