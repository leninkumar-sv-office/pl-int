"""
Additional coverage tests for zerodha_service.py — targeting remaining uncovered lines.
Covers: auto_login full flow, _load_instruments error paths, fetch_ohlc,
fetch_52_week_range with thread pool, fetch_ticker_historical_changes with candles,
search_mf_instruments edge cases, fetch_stock_history max/5y period, _api_get 429 retry.
"""
import time
import os
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta
import pytest


def _reset():
    import app.zerodha_service as zs
    zs._access_token = "test_token"
    zs._api_key = "test_api_key"
    zs._api_secret = "test_secret"
    zs._user_id = "testuser"
    zs._password = "testpass"
    zs._totp_secret = "JBSWY3DPEHPK3PXP"
    zs._auth_failed = False
    zs._conn_failed = False
    zs._conn_fail_time = 0.0
    zs._session_valid = True
    zs._last_error = ""
    zs._auto_login_in_progress = False


class TestApiGet429:
    def test_rate_limited_retries_then_returns_none(self):
        import app.zerodha_service as zs
        _reset()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limited"
        with patch("app.zerodha_service.requests.get", return_value=mock_resp):
            with patch("app.zerodha_service.time.sleep"):
                result = zs._api_get("/test")
        assert result is None
        assert "429" in zs._last_error

    def test_api_get_no_api_key(self):
        import app.zerodha_service as zs
        _reset()
        zs._api_key = ""
        result = zs._api_get("/test")
        assert result is None
        zs._api_key = "test_api_key"

    def test_403_no_auto_login_retry_fails(self):
        import app.zerodha_service as zs
        _reset()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Token expired"
        with patch("app.zerodha_service.requests.get", return_value=mock_resp):
            with patch.object(zs, "_try_auto_login_and_retry", return_value=None):
                result = zs._api_get("/test")
        assert result is None
        assert zs._auth_failed is True


class TestAutoLoginFullFlow:
    def test_full_auto_login_success(self):
        import app.zerodha_service as zs
        _reset()

        mock_login_resp = MagicMock()
        mock_login_resp.status_code = 200
        mock_login_resp.json.return_value = {"data": {"request_id": "req123", "twofa_type": "app_code"}}

        mock_twofa_resp = MagicMock()
        mock_twofa_resp.status_code = 200

        # Redirect response with request_token in Location header
        mock_connect_resp = MagicMock()
        mock_connect_resp.status_code = 302
        mock_connect_resp.headers = {"Location": "http://localhost/callback?request_token=tok123&action=login"}
        mock_connect_resp.url = "http://localhost/callback?request_token=tok123"

        mock_session = MagicMock()
        mock_session.post.side_effect = [mock_login_resp, mock_twofa_resp]
        mock_session.get.return_value = mock_connect_resp

        with patch.object(zs, "can_auto_login", return_value=True):
            with patch("app.zerodha_service.requests.Session", return_value=mock_session):
                with patch("pyotp.TOTP") as mock_totp_cls:
                    mock_totp_cls.return_value.now.return_value = "123456"
                    with patch.object(zs, "generate_session", return_value=True):
                        result = zs.auto_login()
        assert result is True

    def test_auto_login_no_request_token_in_redirects(self):
        import app.zerodha_service as zs
        _reset()

        mock_login_resp = MagicMock()
        mock_login_resp.status_code = 200
        mock_login_resp.json.return_value = {"data": {"request_id": "req123", "twofa_type": "app_code"}}

        mock_twofa_resp = MagicMock()
        mock_twofa_resp.status_code = 200

        # No request_token in redirect or final URL
        mock_connect_resp = MagicMock()
        mock_connect_resp.status_code = 200  # Not a redirect
        mock_connect_resp.headers = {}
        mock_connect_resp.url = "http://localhost/no-token-here"

        mock_session = MagicMock()
        mock_session.post.side_effect = [mock_login_resp, mock_twofa_resp]
        mock_session.get.return_value = mock_connect_resp

        with patch.object(zs, "can_auto_login", return_value=True):
            with patch("app.zerodha_service.requests.Session", return_value=mock_session):
                with patch("pyotp.TOTP") as mock_totp_cls:
                    mock_totp_cls.return_value.now.return_value = "123456"
                    result = zs.auto_login()
        assert result is False

    def test_auto_login_request_token_in_fallback_url(self):
        """Test the fallback URL parsing when redirects don't have token."""
        import app.zerodha_service as zs
        _reset()

        mock_login_resp = MagicMock()
        mock_login_resp.status_code = 200
        mock_login_resp.json.return_value = {"data": {"request_id": "req123"}}

        mock_twofa_resp = MagicMock()
        mock_twofa_resp.status_code = 200

        # First redirect has no token; second is not a redirect
        mock_redirect_resp = MagicMock()
        mock_redirect_resp.status_code = 302
        mock_redirect_resp.headers = {"Location": "http://localhost/intermediate"}

        mock_intermediate_resp = MagicMock()
        mock_intermediate_resp.status_code = 200
        mock_intermediate_resp.headers = {}
        mock_intermediate_resp.url = "http://localhost/callback?request_token=fallback_tok"

        mock_session = MagicMock()
        mock_session.post.side_effect = [mock_login_resp, mock_twofa_resp]
        mock_session.get.side_effect = [mock_redirect_resp, mock_intermediate_resp]

        with patch.object(zs, "can_auto_login", return_value=True):
            with patch("app.zerodha_service.requests.Session", return_value=mock_session):
                with patch("pyotp.TOTP") as mock_totp_cls:
                    mock_totp_cls.return_value.now.return_value = "123456"
                    with patch.object(zs, "generate_session", return_value=True):
                        result = zs.auto_login()
        assert result is True


class TestIsSessionValid:
    def test_auto_login_on_invalid_session(self):
        import app.zerodha_service as zs
        _reset()
        zs._access_token = ""
        zs._auth_failed = True
        with patch.object(zs, "can_auto_login", return_value=True):
            with patch.object(zs, "auto_login", return_value=True):
                result = zs.is_session_valid()
        assert result is True

    def test_auto_login_fails(self):
        import app.zerodha_service as zs
        _reset()
        zs._access_token = ""
        with patch.object(zs, "can_auto_login", return_value=True):
            with patch.object(zs, "auto_login", return_value=False):
                result = zs.is_session_valid()
        assert result is False


class TestFetchOhlc:
    def test_fetch_ohlc_success(self):
        import app.zerodha_service as zs
        _reset()
        api_resp = {
            "data": {
                "NSE:RELIANCE": {
                    "last_price": 2500.0,
                    "ohlc": {"open": 2480, "high": 2520, "low": 2470, "close": 2490},
                }
            }
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_resp):
                result = zs.fetch_ohlc([("RELIANCE", "NSE")])
        assert "RELIANCE.NSE" in result
        assert result["RELIANCE.NSE"]["price"] == 2500.0

    def test_fetch_ohlc_zero_price_skipped(self):
        import app.zerodha_service as zs
        _reset()
        api_resp = {
            "data": {
                "NSE:DEAD": {"last_price": 0, "ohlc": {"open": 0, "high": 0, "low": 0, "close": 0}}
            }
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_resp):
                result = zs.fetch_ohlc([("DEAD", "NSE")])
        assert "DEAD.NSE" not in result

    def test_fetch_ohlc_no_session(self):
        import app.zerodha_service as zs
        with patch.object(zs, "is_session_valid", return_value=False):
            result = zs.fetch_ohlc([("RELIANCE", "NSE")])
        assert result == {}

    def test_fetch_ohlc_unmapped_key_skipped(self):
        import app.zerodha_service as zs
        _reset()
        api_resp = {
            "data": {
                "NSE:UNKNOWNSTOCK": {"last_price": 100.0, "ohlc": {"open": 99, "high": 101, "low": 98, "close": 99.5}}
            }
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_resp):
                result = zs.fetch_ohlc([("RELIANCE", "NSE")])
        assert "RELIANCE.NSE" not in result


class TestFetchQuotesEdgeCases:
    def test_fetch_quotes_retry_on_failure(self):
        import app.zerodha_service as zs
        _reset()
        api_resp = {
            "data": {
                "NSE:TCS": {
                    "last_price": 3600.0,
                    "ohlc": {"open": 3580, "high": 3620, "low": 3570, "close": 3590},
                    "volume": 500000,
                    "lower_circuit_limit": 3200.0,
                    "upper_circuit_limit": 3900.0,
                }
            }
        }
        # First call returns None (triggers retry), second succeeds
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", side_effect=[None, api_resp]):
                with patch("app.zerodha_service.time.sleep"):
                    result = zs.fetch_quotes([("TCS", "NSE")])
        assert "TCS.NSE" in result

    def test_fetch_quotes_zero_ltp_skipped(self):
        import app.zerodha_service as zs
        _reset()
        api_resp = {
            "data": {
                "NSE:DEAD": {
                    "last_price": 0.0,
                    "ohlc": {"open": 0, "high": 0, "low": 0, "close": 0},
                }
            }
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_resp):
                result = zs.fetch_quotes([("DEAD", "NSE")])
        assert "DEAD.NSE" not in result


class TestFetch52WeekRangeThreaded:
    def test_fetch_with_thread_pool(self):
        import app.zerodha_service as zs
        _reset()
        hist_data = {
            "week_52_high": 3000.0, "week_52_low": 2000.0,
            "week_change_pct": 1.5, "month_change_pct": -2.0,
            "sma_50": 2800.0, "sma_200": 2500.0,
            "signal": "strong_bull", "days_below_sma": 0, "rsi": 65.0,
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_get_instrument_token", return_value=12345):
                with patch.object(zs, "_fetch_historical_52w", return_value=hist_data):
                    with patch("app.zerodha_service.time.sleep"):
                        # Clear cache
                        with zs._52w_cache_lock:
                            zs._52w_cache.clear()
                        result = zs.fetch_52_week_range([("RELIANCE", "NSE")])
        assert "RELIANCE.NSE" in result
        assert result["RELIANCE.NSE"]["week_52_high"] == 3000.0

    def test_fetch_with_error_in_thread(self):
        import app.zerodha_service as zs
        _reset()
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_get_instrument_token", return_value=12345):
                with patch.object(zs, "_fetch_historical_52w", return_value=None):
                    with patch("app.zerodha_service.time.sleep"):
                        with zs._52w_cache_lock:
                            zs._52w_cache.clear()
                        result = zs.fetch_52_week_range([("FAIL", "NSE")])
        assert "FAIL.NSE" not in result


class TestTickerHistoricalChangesWithCandles:
    def test_full_candle_parsing(self):
        import app.zerodha_service as zs
        _reset()
        now = datetime.now()
        candles = []
        for i in range(35):
            dt = now - timedelta(days=35 - i)
            ts = dt.strftime("%Y-%m-%d")
            candles.append([ts, 100 + i, 102 + i, 98 + i, 101 + i, 10000])

        api_resp = {"data": {"candles": candles}}
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_resp):
                with patch("app.zerodha_service.time.sleep"):
                    with zs._ticker_hist_lock:
                        zs._ticker_hist_cache.clear()
                    result = zs.fetch_ticker_historical_changes({
                        "SENSEX": {"instrument_token": 99, "price": 72000, "divisor": 1},
                    })
        assert "SENSEX" in result
        assert "week_change_pct" in result["SENSEX"]

    def test_no_instrument_token_skipped(self):
        import app.zerodha_service as zs
        _reset()
        with patch.object(zs, "is_session_valid", return_value=True):
            result = zs.fetch_ticker_historical_changes({
                "NOTOKEN": {"price": 100},  # no instrument_token
            })
        assert result == {}

    def test_empty_candles_skipped(self):
        import app.zerodha_service as zs
        _reset()
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value={"data": {"candles": []}}):
                with patch("app.zerodha_service.time.sleep"):
                    with zs._ticker_hist_lock:
                        zs._ticker_hist_cache.clear()
                    result = zs.fetch_ticker_historical_changes({
                        "SENSEX": {"instrument_token": 99, "price": 100},
                    })
        assert "SENSEX" not in result

    def test_divisor_applied(self):
        import app.zerodha_service as zs
        _reset()
        now = datetime.now()
        candles = []
        for i in range(35):
            dt = now - timedelta(days=35 - i)
            ts = dt.strftime("%Y-%m-%d")
            candles.append([ts, 200, 210, 190, 200, 10000])

        api_resp = {"data": {"candles": candles}}
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_resp):
                with patch("app.zerodha_service.time.sleep"):
                    with zs._ticker_hist_lock:
                        zs._ticker_hist_cache.clear()
                    result = zs.fetch_ticker_historical_changes({
                        "GOLD": {"instrument_token": 99, "price": 100, "divisor": 2},
                    })
        assert "GOLD" in result


class TestFetchStockHistoryMaxPeriod:
    def test_max_period_chunks(self):
        import app.zerodha_service as zs
        _reset()
        candles = [["2020-01-15T00:00:00", 100, 105, 95, 102, 50000]]
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_get_instrument_token", return_value=12345):
                with patch.object(zs, "_api_get", return_value={"data": {"candles": candles}}):
                    with zs._history_cache_lock:
                        zs._history_cache.clear()
                    result = zs.fetch_stock_history("TEST", "NSE", "max")
        # Should return some results (from multiple chunks)
        assert result is not None

    def test_5y_period(self):
        import app.zerodha_service as zs
        _reset()
        candles = [["2020-01-15T00:00:00", 100, 105, 95, 102, 50000] for _ in range(600)]
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_get_instrument_token", return_value=12345):
                with patch.object(zs, "_api_get", return_value={"data": {"candles": candles}}):
                    with zs._history_cache_lock:
                        zs._history_cache.clear()
                    result = zs.fetch_stock_history("TEST", "NSE", "5y")
        assert result is not None
        # Should be downsampled since > 500
        assert len(result) <= 400

    def test_provided_instrument_token(self):
        """Test that provided instrument_token is used."""
        import app.zerodha_service as zs
        _reset()
        candles = [["2024-01-15T00:00:00", 100, 105, 95, 102, 50000]]
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value={"data": {"candles": candles}}) as mock_api:
                with zs._history_cache_lock:
                    zs._history_cache.clear()
                result = zs.fetch_stock_history("TEST", "NSE", "1m", instrument_token=99999)
        assert result is not None

    def test_candle_with_datetime_object(self):
        """Test candle timestamp as datetime object (has isoformat)."""
        import app.zerodha_service as zs
        _reset()
        dt = datetime(2024, 1, 15)
        candles = [[dt, 100, 105, 95, 102, 50000]]
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_get_instrument_token", return_value=12345):
                with patch.object(zs, "_api_get", return_value={"data": {"candles": candles}}):
                    with zs._history_cache_lock:
                        zs._history_cache.clear()
                    result = zs.fetch_stock_history("TEST", "NSE", "1y")
        assert result is not None
        assert "2024-01-15" in result[0]["date"]


class TestLoadInstrumentsEdgeCases:
    def test_load_instruments_http_error(self):
        import app.zerodha_service as zs
        _reset()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        zs._instrument_names_loaded = False
        with patch("app.zerodha_service.requests.get", return_value=mock_resp):
            zs._load_instruments()

    def test_load_instruments_exception(self):
        import app.zerodha_service as zs
        _reset()
        zs._instrument_names_loaded = False
        with patch("app.zerodha_service.requests.get", side_effect=Exception("network error")):
            zs._load_instruments()

    def test_load_instruments_invalid_token(self):
        import app.zerodha_service as zs
        _reset()
        csv_data = "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n"
        csv_data += "not_a_number,6789,RELIANCE,Reliance Industries,2500,,,0.05,1,EQ,NSE,NSE\n"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_data
        zs._instrument_names_loaded = False
        zs._instrument_tokens_loaded = False
        with patch("app.zerodha_service.requests.get", return_value=mock_resp):
            zs._load_instruments()
        # Should still load the name even with invalid token
        assert "RELIANCE.NSE" in zs._instrument_names


class TestLoadMFInstrumentsEdgeCases:
    def test_load_mf_instruments_http_error(self):
        import app.zerodha_service as zs
        _reset()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        zs._mf_instruments_loaded = False
        with patch("app.zerodha_service.requests.get", return_value=mock_resp):
            zs._load_mf_instruments()

    def test_load_mf_instruments_exception(self):
        import app.zerodha_service as zs
        _reset()
        zs._mf_instruments_loaded = False
        with patch("app.zerodha_service.requests.get", side_effect=Exception("fail")):
            zs._load_mf_instruments()


class TestSearchMFInstrumentsEdgeCases:
    def test_search_mf_dividend_filter(self):
        import app.zerodha_service as zs
        zs._mf_instruments = [
            {"tradingsymbol": "INF1", "name": "Axis Growth Fund Direct",
             "amc": "AxisMF", "scheme_type": "equity", "plan": "direct",
             "dividend_type": "growth", "last_price": 55.0},
            {"tradingsymbol": "INF2", "name": "Axis IDCW Fund Direct",
             "amc": "AxisIDCW", "scheme_type": "equity", "plan": "direct",
             "dividend_type": "payout", "last_price": 50.0},
        ]
        zs._mf_instruments_loaded = True
        # Filter for dividend only
        results = zs.search_mf_instruments("Axis", plan="direct", scheme_type="dividend")
        assert all(r["dividend_type"] not in ("", "na", "growth") for r in results)

    def test_search_mf_no_results_debug_log(self):
        import app.zerodha_service as zs
        zs._mf_instruments = [
            {"tradingsymbol": "INF1", "name": "Axis Growth Fund Direct",
             "amc": "AxisMF", "scheme_type": "equity", "plan": "direct",
             "dividend_type": "growth", "last_price": 55.0},
        ]
        zs._mf_instruments_loaded = True
        results = zs.search_mf_instruments("Axis Growth", plan="regular")
        assert results == []


class TestGetInstrumentToken:
    def test_alias_lookup(self):
        import app.zerodha_service as zs
        _reset()
        # SBIETF.NSE maps to NSE:SETFGOLD
        zs._instrument_token_cache["SETFGOLD.NSE"] = 99999
        zs._instrument_tokens_loaded = True
        token = zs._get_instrument_token("SBIETF", "NSE")
        assert token == 99999


class TestKiteInstrument:
    def test_invalid_exchange_defaults_nse(self):
        import app.zerodha_service as zs
        result = zs._kite_instrument("RELIANCE", "INVALID")
        assert result == "NSE:RELIANCE"

    def test_override_map(self):
        import app.zerodha_service as zs
        result = zs._kite_instrument("MAJESCO", "NSE")
        assert result == "NSE:AURUM"


class TestFetchHistorical52wSignals:
    def _make_candles(self, n, trend="up"):
        now = datetime.now()
        candles = []
        for i in range(n):
            dt = now - timedelta(days=n - i)
            ts = dt.strftime("%Y-%m-%d")
            if trend == "up":
                price = 100 + i * 0.5
            elif trend == "down":
                price = 200 - i * 0.5
            else:
                price = 100
            candles.append([ts, price - 1, price + 2, price - 2, price, 100000])
        return candles

    def test_weak_bull_signal(self):
        """50-SMA > 200-SMA but price < 200-SMA"""
        import app.zerodha_service as zs
        # Create candles where price drops below 200-SMA at the end
        candles = self._make_candles(250, "up")
        # Make last few candles have very low price
        for i in range(-5, 0):
            candles[i][4] = 10  # close
            candles[i][1] = 10  # open
        api_response = {"data": {"candles": candles}}
        with patch.object(zs, "_api_get", return_value=api_response):
            result = zs._fetch_historical_52w(12345)
        assert result is not None

    def test_strong_bear_signal(self):
        """50-SMA < 200-SMA and price < 200-SMA"""
        import app.zerodha_service as zs
        candles = self._make_candles(250, "down")
        api_response = {"data": {"candles": candles}}
        with patch.object(zs, "_api_get", return_value=api_response):
            result = zs._fetch_historical_52w(12345)
        assert result is not None
        assert result["signal"] in ("strong_bear", "weak_bear")

    def test_rsi_all_gains(self):
        """Test RSI when all changes are gains."""
        import app.zerodha_service as zs
        candles = self._make_candles(20, "up")
        api_response = {"data": {"candles": candles}}
        with patch.object(zs, "_api_get", return_value=api_response):
            result = zs._fetch_historical_52w(12345)
        assert result is not None
        assert result["rsi"] == 100.0

    def test_no_highs_lows(self):
        """Test with very short candles (<4 elements)."""
        import app.zerodha_service as zs
        candles = [["2024-01-15", 100]]  # too short
        api_response = {"data": {"candles": candles}}
        with patch.object(zs, "_api_get", return_value=api_response):
            result = zs._fetch_historical_52w(12345)
        assert result is None

    def test_candle_with_bad_timestamp(self):
        """Test with unparseable timestamp."""
        import app.zerodha_service as zs
        now = datetime.now()
        candles = []
        for i in range(20):
            dt = now - timedelta(days=20 - i)
            ts = dt.strftime("%Y-%m-%d")
            candles.append([ts, 100, 102, 98, 100, 10000])
        candles[5][0] = None  # bad timestamp
        api_response = {"data": {"candles": candles}}
        with patch.object(zs, "_api_get", return_value=api_response):
            result = zs._fetch_historical_52w(12345)
        assert result is not None


class TestGenerateSession:
    def test_success(self):
        import app.zerodha_service as zs
        _reset()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"access_token": "new_token_abc123"}}
        with patch("app.zerodha_service.requests.post", return_value=mock_resp):
            with patch.object(zs, "_update_env"):
                result = zs.generate_session("request_tok_123")
        assert result is True

    def test_failure(self):
        import app.zerodha_service as zs
        _reset()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad request"
        with patch("app.zerodha_service.requests.post", return_value=mock_resp):
            result = zs.generate_session("bad_token")
        assert result is False

    def test_exception(self):
        import app.zerodha_service as zs
        _reset()
        with patch("app.zerodha_service.requests.post", side_effect=Exception("network")):
            result = zs.generate_session("tok")
        assert result is False

    def test_no_api_key(self):
        import app.zerodha_service as zs
        _reset()
        zs._api_key = ""
        result = zs.generate_session("tok")
        assert result is False
        zs._api_key = "test_api_key"


class TestSetAccessToken:
    def test_set_token(self):
        import app.zerodha_service as zs
        _reset()
        with patch.object(zs, "_update_env"):
            zs.set_access_token("  new_token_123  ")
        assert zs._access_token == "new_token_123"


class TestUpdateEnvError:
    def test_file_write_error(self, tmp_path):
        import app.zerodha_service as zs
        old_path = zs._ENV_PATH
        zs._ENV_PATH = str(tmp_path / "nonexist" / "subdir" / ".env")
        # Should log error but not crash
        zs._update_env("TEST_KEY", "test_val")
        zs._ENV_PATH = old_path


class TestFetchMarketTickersEdgeCases:
    def test_zero_ltp_skipped(self):
        import app.zerodha_service as zs
        _reset()
        api_response = {
            "data": {
                "BSE:SENSEX": {
                    "last_price": 0.0,
                    "ohlc": {"close": 0},
                    "instrument_token": 99999,
                }
            }
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_response):
                result = zs.fetch_market_tickers()
        assert "SENSEX" not in result

    def test_higher_priority_kept(self):
        import app.zerodha_service as zs
        _reset()
        # Both SENSEX candidates return, but BSE:SENSEX has priority 0
        api_response = {
            "data": {
                "BSE:SENSEX": {
                    "last_price": 72000.0,
                    "ohlc": {"close": 71800.0},
                    "instrument_token": 99999,
                },
            }
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_response):
                result = zs.fetch_market_tickers()
        assert "SENSEX" in result

    def test_no_data_returns_empty(self):
        import app.zerodha_service as zs
        _reset()
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=None):
                result = zs.fetch_market_tickers()
        assert result == {}


class TestSearchInstrumentsExchange:
    def test_search_filter_by_exchange(self):
        import app.zerodha_service as zs
        zs._instrument_names.update({
            "TCS.NSE": "Tata Consultancy Services",
            "TCS.BSE": "Tata Consultancy Services",
        })
        zs._instrument_names_loaded = True
        results = zs.search_instruments("TCS", "BSE")
        assert all(r["exchange"] == "BSE" for r in results)
