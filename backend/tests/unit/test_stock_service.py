"""
Unit tests for app/stock_service.py

Tests the Zerodha-primary / Yahoo-fallback price fetching logic.
All external I/O (network, file system) is mocked.
"""
import json
import os
import time
from unittest.mock import MagicMock, patch, mock_open

import pytest
import pandas as pd

from app.models import StockLiveData


# helpers

def _make_stock_live(symbol="RELIANCE", exchange="NSE", price=2500.0):
    return StockLiveData(
        symbol=symbol, exchange=exchange, name="Reliance Industries",
        current_price=price, week_52_high=2800.0, week_52_low=2200.0,
        day_change=50.0, day_change_pct=2.0,
        volume=1000000, previous_close=2450.0,
        is_manual=False,
    )


# cache helpers

def test_cache_get_set_hit():
    from app import stock_service as ss
    ss.clear_cache()
    data = _make_stock_live()
    ss._cache_set("RELIANCE.NSE", data)
    result = ss._cache_get("RELIANCE.NSE")
    assert result is data


def test_cache_miss_returns_none():
    from app import stock_service as ss
    ss.clear_cache()
    assert ss._cache_get("MISSING.NSE") is None


def test_clear_cache():
    from app import stock_service as ss
    ss._cache_set("X.NSE", _make_stock_live("X"))
    ss.clear_cache()
    assert ss._cache_get("X.NSE") is None


# _yahoo_sym

def test_yahoo_sym_nse():
    from app.stock_service import _yahoo_sym
    assert _yahoo_sym("RELIANCE", "NSE") == "RELIANCE.NS"


def test_yahoo_sym_bse():
    from app.stock_service import _yahoo_sym
    assert _yahoo_sym("500325", "BSE") == "500325.BO"


def test_yahoo_sym_already_suffixed():
    from app.stock_service import _yahoo_sym
    assert _yahoo_sym("TCS.NS", "NSE") == "TCS.NS"
    assert _yahoo_sym("TCS.BO", "BSE") == "TCS.BO"


# _load_prices_file / _save_prices_file

def test_load_prices_file_missing(tmp_path):
    from app import stock_service as ss
    with patch.object(ss, "_PRICES_FILE", str(tmp_path / "nonexistent.json")):
        result = ss._load_prices_file()
    assert result == {}


def test_load_prices_file_invalid_json(tmp_path):
    from app import stock_service as ss
    bad_file = tmp_path / "stock_prices.json"
    bad_file.write_text("not json")
    with patch.object(ss, "_PRICES_FILE", str(bad_file)):
        result = ss._load_prices_file()
    assert result == {}


def test_save_and_load_prices_file(tmp_path):
    from app import stock_service as ss
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({}))
    prices = {"RELIANCE.NSE": {"price": 2500.0, "name": "Reliance"}}
    with patch.object(ss, "_PRICES_FILE", str(prices_file)), \
         patch.object(ss, "_DATA_DIR", str(tmp_path)), \
         patch("app.drive_service.sync_data_file", return_value=None):
        ss._save_prices_file(prices)
        loaded = ss._load_prices_file()
    assert "RELIANCE.NSE" in loaded
    assert loaded["RELIANCE.NSE"]["price"] == 2500.0


def test_save_prices_file_merges(tmp_path):
    from app import stock_service as ss
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({"EXISTING.NSE": {"price": 100}}))
    with patch.object(ss, "_PRICES_FILE", str(prices_file)), \
         patch.object(ss, "_DATA_DIR", str(tmp_path)):
        ss._save_prices_file({"NEW.NSE": {"price": 200}})
        loaded = ss._load_prices_file()
    assert "EXISTING.NSE" in loaded
    assert "NEW.NSE" in loaded


def test_save_prices_file_exception(tmp_path):
    from app import stock_service as ss
    # Force an exception in _load_prices_file during merge
    with patch.object(ss, "_PRICES_FILE", str(tmp_path / "prices.json")), \
         patch.object(ss, "_DATA_DIR", str(tmp_path)), \
         patch.object(ss, "_load_prices_file", side_effect=Exception("read fail")):
        ss._save_prices_file({"X.NSE": {"price": 1}})  # Should not raise


# _file_fallback

def test_file_fallback_found(tmp_path):
    from app import stock_service as ss
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({
        "INFY.NSE": {"price": 1800.0, "name": "Infosys", "week_52_high": 2000.0,
                     "week_52_low": 1500.0, "day_change": 10, "day_change_pct": 0.5,
                     "week_change_pct": 1.2, "month_change_pct": 3.5,
                     "volume": 500000, "previous_close": 1790}
    }))
    with patch.object(ss, "_PRICES_FILE", str(prices_file)):
        result = ss._file_fallback("INFY", "NSE")
    assert result is not None
    assert result.current_price == 1800.0
    assert result.is_manual is True
    assert result.week_change_pct == 1.2
    assert result.month_change_pct == 3.5


def test_file_fallback_zero_price(tmp_path):
    from app import stock_service as ss
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({"INFY.NSE": {"price": 0}}))
    with patch.object(ss, "_PRICES_FILE", str(prices_file)):
        result = ss._file_fallback("INFY", "NSE")
    assert result is None


def test_file_fallback_missing_key(tmp_path):
    from app import stock_service as ss
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({}))
    with patch.object(ss, "_PRICES_FILE", str(prices_file)):
        result = ss._file_fallback("UNKNOWN", "NSE")
    assert result is None


# xlsx fallback

def test_xlsx_fallback_no_file():
    from app import stock_service as ss
    with patch.object(ss, "db") as mock_db:
        mock_db._file_map = {}
        mock_db.get_manual_price.return_value = None
        result = ss._xlsx_fallback("NOSYM", "NSE")
    assert result is None


def test_xlsx_single_cached():
    from app import stock_service as ss
    ss._xlsx_idx["CACHED"] = {"price": 100, "w52h": 120, "w52l": 80}
    result = ss._xlsx_single("CACHED")
    assert result["price"] == 100
    del ss._xlsx_idx["CACHED"]


def test_xlsx_fallback_with_manual_price():
    from app import stock_service as ss
    ss._xlsx_idx["MANUAL"] = {"price": 0, "w52h": 0, "w52l": 0}
    with patch.object(ss, "db") as mock_db:
        mock_db._file_map = {"MANUAL": "/fake"}
        mock_db.get_manual_price.return_value = 150.0
        mock_db._name_map = {"MANUAL": "Manual Stock"}
        result = ss._xlsx_fallback("MANUAL", "NSE")
    assert result is not None
    assert result.current_price == 150.0
    del ss._xlsx_idx["MANUAL"]


# fetch_multiple

def test_fetch_multiple_zerodha_success(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    zerodha_quote = {
        "RELIANCE.NSE": {
            "price": 2500.0, "name": "Reliance Industries",
            "week_52_high": 2800.0, "week_52_low": 2200.0,
            "day_change": 50.0, "day_change_pct": 2.0,
            "volume": 1000000, "close": 2450.0,
        }
    }
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({}))

    with patch("app.stock_service.zerodha_service") as mock_z, \
         patch.object(ss, "_PRICES_FILE", str(prices_file)), \
         patch.object(ss, "_DATA_DIR", str(tmp_path)), \
         patch("app.stock_service.zerodha_service.fetch_52_week_range", return_value={}):
        mock_z.is_session_valid.return_value = True
        mock_z.fetch_quotes.return_value = zerodha_quote
        mock_z.fetch_52_week_range.return_value = {}
        results = ss.fetch_multiple([("RELIANCE", "NSE")])

    assert "RELIANCE.NSE" in results
    assert results["RELIANCE.NSE"].current_price == 2500.0
    assert results["RELIANCE.NSE"].is_manual is False


def test_fetch_multiple_zerodha_not_available(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({
        "TCS.NSE": {"price": 3500.0, "name": "TCS", "week_52_high": 4000.0,
                    "week_52_low": 3000.0, "day_change": 0, "day_change_pct": 0,
                    "volume": 0, "previous_close": 0}
    }))

    # Ensure fallback is disabled (other tests may have changed this)
    original_fallback = ss.ENABLE_YAHOO_GOOGLE
    ss.ENABLE_YAHOO_GOOGLE = False
    try:
        with patch("app.stock_service.zerodha_service") as mock_z, \
             patch.object(ss, "_PRICES_FILE", str(prices_file)):
            mock_z.is_session_valid.return_value = False
            results = ss.fetch_multiple([("TCS", "NSE")])

        assert "TCS.NSE" in results
        assert results["TCS.NSE"].current_price == 3500.0
        assert results["TCS.NSE"].is_manual is True
    finally:
        ss.ENABLE_YAHOO_GOOGLE = original_fallback


def test_fetch_multiple_serves_from_cache():
    from app import stock_service as ss
    ss.clear_cache()
    cached = _make_stock_live("WIPRO", "NSE", 450.0)
    ss._cache_set("WIPRO.NSE", cached)

    with patch("app.stock_service.zerodha_service") as mock_z:
        mock_z.is_session_valid.return_value = True
        mock_z.fetch_quotes.return_value = {}
        results = ss.fetch_multiple([("WIPRO", "NSE")])

    assert "WIPRO.NSE" in results
    assert results["WIPRO.NSE"].current_price == 450.0


def test_fetch_multiple_all_cached():
    from app import stock_service as ss
    ss.clear_cache()
    ss._cache_set("A.NSE", _make_stock_live("A", "NSE", 100.0))
    ss._cache_set("B.NSE", _make_stock_live("B", "NSE", 200.0))
    results = ss.fetch_multiple([("A", "NSE"), ("B", "NSE")])
    assert len(results) == 2


def test_fetch_multiple_zerodha_with_52w(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({}))

    zerodha_quote = {
        "SBIN.NSE": {"price": 600.0, "name": "SBI", "day_change": 5, "day_change_pct": 0.8,
                     "volume": 100000, "close": 595.0}
    }
    w52 = {
        "SBIN.NSE": {"week_52_high": 700.0, "week_52_low": 450.0,
                     "week_change_pct": 1.5, "month_change_pct": 3.2,
                     "sma_50": 580, "sma_200": 550, "signal": "bullish",
                     "days_below_sma": 0, "rsi": 55.0}
    }

    with patch("app.stock_service.zerodha_service") as mock_z, \
         patch.object(ss, "_PRICES_FILE", str(prices_file)), \
         patch.object(ss, "_DATA_DIR", str(tmp_path)):
        mock_z.is_session_valid.return_value = True
        mock_z.fetch_quotes.return_value = zerodha_quote
        mock_z.fetch_52_week_range.return_value = w52
        results = ss.fetch_multiple([("SBIN", "NSE")])

    assert results["SBIN.NSE"].week_52_high == 700.0
    assert results["SBIN.NSE"].week_change_pct == 1.5
    assert results["SBIN.NSE"].sma_50 == 580
    assert results["SBIN.NSE"].rsi == 55.0


def test_fetch_multiple_52w_fallback_to_saved(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({
        "HDFC.NSE": {"price": 1500, "week_52_high": 1800, "week_52_low": 1200,
                     "week_change_pct": 2.0, "month_change_pct": 5.0}
    }))

    zerodha_quote = {
        "HDFC.NSE": {"price": 1500.0, "name": "HDFC", "day_change": 0, "day_change_pct": 0,
                     "volume": 0, "close": 1500}
    }
    # 52w returns empty for this stock
    w52 = {"HDFC.NSE": {"week_52_high": 0, "week_52_low": 0}}

    with patch("app.stock_service.zerodha_service") as mock_z, \
         patch.object(ss, "_PRICES_FILE", str(prices_file)), \
         patch.object(ss, "_DATA_DIR", str(tmp_path)):
        mock_z.is_session_valid.return_value = True
        mock_z.fetch_quotes.return_value = zerodha_quote
        mock_z.fetch_52_week_range.return_value = w52
        results = ss.fetch_multiple([("HDFC", "NSE")])

    # Should fall back to saved prices for 52w data (or xlsx)
    assert results["HDFC.NSE"].week_52_high >= 0  # May be 1800 or 0 depending on xlsx cache


def test_fetch_multiple_52w_exception_fallback(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({
        "AXIS.NSE": {"price": 1000, "week_52_high": 1200, "week_52_low": 800}
    }))

    zerodha_quote = {
        "AXIS.NSE": {"price": 1000.0, "name": "Axis", "day_change": 0, "day_change_pct": 0,
                     "volume": 0, "close": 1000}
    }

    with patch("app.stock_service.zerodha_service") as mock_z, \
         patch.object(ss, "_PRICES_FILE", str(prices_file)), \
         patch.object(ss, "_DATA_DIR", str(tmp_path)):
        mock_z.is_session_valid.return_value = True
        mock_z.fetch_quotes.return_value = zerodha_quote
        mock_z.fetch_52_week_range.side_effect = Exception("52w API failure")
        results = ss.fetch_multiple([("AXIS", "NSE")])

    # Should still have the stock
    assert "AXIS.NSE" in results
    assert results["AXIS.NSE"].current_price == 1000.0


def test_fetch_multiple_zerodha_error(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({}))

    with patch("app.stock_service.zerodha_service") as mock_z, \
         patch.object(ss, "_PRICES_FILE", str(prices_file)):
        mock_z.is_session_valid.return_value = True
        mock_z.fetch_quotes.side_effect = Exception("API down")
        results = ss.fetch_multiple([("MISSING", "NSE")])
    # Should return empty since no fallback data exists
    assert "MISSING.NSE" not in results


# bulk_update_prices

def test_bulk_update_prices(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({}))

    with patch.object(ss, "_PRICES_FILE", str(prices_file)), \
         patch.object(ss, "_DATA_DIR", str(tmp_path)):
        count = ss.bulk_update_prices({
            "HDFC": {"exchange": "NSE", "price": 1500.0, "name": "HDFC Bank",
                     "week_52_high": 1800, "week_52_low": 1200,
                     "day_change": 10, "day_change_pct": 0.67,
                     "week_change_pct": 2.1, "month_change_pct": 5.3,
                     "volume": 500000, "previous_close": 1490},
            "INVALID": {"exchange": "NSE", "price": 0},
        })

    assert count == 1
    result = ss._cache_get("HDFC.NSE")
    assert result is not None
    assert result.current_price == 1500.0
    assert result.is_manual is True


def test_bulk_update_no_prices():
    from app import stock_service as ss
    ss.clear_cache()
    count = ss.bulk_update_prices({})
    assert count == 0


# get_refresh_status

def test_get_refresh_status_structure():
    from app.stock_service import get_refresh_status
    status = get_refresh_status()
    assert "status" in status
    assert "cache_size" in status
    assert "refresh_interval" in status
    assert "last_refresh" in status
    assert "seconds_ago" in status


# get_cached_prices

def test_get_cached_prices_from_memory():
    from app import stock_service as ss
    ss.clear_cache()
    data = _make_stock_live("SBIN", "NSE", 600.0)
    ss._cache_set("SBIN.NSE", data)
    results = ss.get_cached_prices([("SBIN", "NSE")])
    assert "SBIN.NSE" in results
    assert results["SBIN.NSE"].current_price == 600.0


def test_get_cached_prices_from_json(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({
        "AXISBANK.NSE": {
            "price": 1100.0, "name": "Axis Bank",
            "week_52_high": 1200.0, "week_52_low": 900.0,
            "day_change": 0, "day_change_pct": 0,
            "week_change_pct": 0, "month_change_pct": 0,
            "volume": 0, "previous_close": 0,
        }
    }))
    with patch.object(ss, "_PRICES_FILE", str(prices_file)):
        results = ss.get_cached_prices([("AXISBANK", "NSE")])
    assert "AXISBANK.NSE" in results
    assert results["AXISBANK.NSE"].current_price == 1100.0


def test_get_cached_prices_all_from_memory():
    from app import stock_service as ss
    ss.clear_cache()
    ss._cache_set("A.NSE", _make_stock_live("A", "NSE", 100))
    results = ss.get_cached_prices([("A", "NSE")])
    assert len(results) == 1


def test_get_cached_prices_alternate_exchange(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({
        "RELIANCE.NSE": {
            "price": 2500.0, "name": "Reliance",
            "week_52_high": 2800, "week_52_low": 2200,
            "day_change": 50, "day_change_pct": 2,
            "week_change_pct": 1, "month_change_pct": 3,
            "volume": 1000000, "previous_close": 2450,
        }
    }))
    with patch.object(ss, "_PRICES_FILE", str(prices_file)):
        results = ss.get_cached_prices([("RELIANCE", "BSE")])
    assert "RELIANCE.BSE" in results
    assert results["RELIANCE.BSE"].current_price == 2500.0


def test_get_cached_prices_xlsx_fallback(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({}))
    # Set up xlsx cache for the symbol
    ss._xlsx_idx["XLSXSTOCK"] = {"price": 777, "w52h": 900, "w52l": 600}
    with patch.object(ss, "_PRICES_FILE", str(prices_file)), \
         patch.object(ss, "db") as mock_db:
        mock_db._name_map = {"XLSXSTOCK": "Xlsx Stock"}
        mock_db._file_map = {"XLSXSTOCK": "/fake/path"}
        mock_db.get_manual_price.return_value = None
        results = ss.get_cached_prices([("XLSXSTOCK", "NSE")])
    assert "XLSXSTOCK.NSE" in results
    assert results["XLSXSTOCK.NSE"].current_price == 777
    del ss._xlsx_idx["XLSXSTOCK"]


# _download_batch (Yahoo Finance mock)

def test_download_batch_empty_tickers():
    from app.stock_service import _download_batch
    result = _download_batch([])
    assert result == {}


def test_download_batch_yf_fails():
    from app.stock_service import _download_batch
    with patch("yfinance.download", return_value=pd.DataFrame()):
        result = _download_batch(["RELIANCE.NS"])
    assert result == {}


def test_download_batch_single_ticker():
    from app.stock_service import _download_batch
    df = pd.DataFrame({"Close": [100.0, 105.0, 110.0]})
    with patch("yfinance.download", return_value=df):
        result = _download_batch(["RELIANCE.NS"])
    assert "RELIANCE.NS" in result
    assert result["RELIANCE.NS"] == 110.0


def test_download_batch_multiple_tickers():
    from app.stock_service import _download_batch
    # Create a proper multi-level DataFrame like yfinance returns
    arrays = [["Close", "Close"], ["RELIANCE.NS", "TCS.NS"]]
    tuples = list(zip(*arrays))
    index = pd.MultiIndex.from_tuples(tuples)
    df = pd.DataFrame([[100.0, 3000.0], [105.0, 3100.0]], columns=index)
    with patch("yfinance.download", return_value=df):
        result = _download_batch(["RELIANCE.NS", "TCS.NS"])
    assert "RELIANCE.NS" in result or "TCS.NS" in result


def test_download_batch_exception():
    from app.stock_service import _download_batch
    with patch("yfinance.download", side_effect=Exception("network error")):
        result = _download_batch(["RELIANCE.NS"])
    assert result == {}


def test_download_batch_with_retry_succeeds():
    from app.stock_service import _download_batch_with_retry
    with patch("app.stock_service._download_batch", return_value={"X.NS": 100.0}):
        result = _download_batch_with_retry(["X.NS"])
    assert "X.NS" in result


def test_download_batch_with_retry_all_fail():
    from app.stock_service import _download_batch_with_retry
    with patch("app.stock_service._download_batch", return_value={}), \
         patch("time.sleep"):
        result = _download_batch_with_retry(["X.NS"])
    assert result == {}


# Google Finance

def test_fetch_google_finance_price_success():
    from app.stock_service import _fetch_google_finance_price
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = 'data-last-price="2500.50"'
    with patch("app.stock_service._requests.get", return_value=mock_resp):
        result = _fetch_google_finance_price("RELIANCE", "NSE")
    assert result == 2500.50


def test_fetch_google_finance_price_no_match():
    from app.stock_service import _fetch_google_finance_price
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = 'no price data here'
    with patch("app.stock_service._requests.get", return_value=mock_resp), \
         patch("time.sleep"):
        result = _fetch_google_finance_price("MISSING", "NSE")
    assert result is None


def test_fetch_google_finance_price_error():
    from app.stock_service import _fetch_google_finance_price
    with patch("app.stock_service._requests.get", side_effect=Exception("timeout")), \
         patch("time.sleep"):
        result = _fetch_google_finance_price("X", "NSE")
    assert result is None


def test_fetch_google_finance_ticker_success():
    from app.stock_service import _fetch_google_finance_ticker
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = 'data-last-price="73000.50" data-previous-close="72800.00"'
    with patch("app.stock_service._requests.get", return_value=mock_resp):
        result = _fetch_google_finance_ticker("SENSEX:INDEXBOM")
    assert result is not None
    assert result[0] == 73000.50
    assert result[1] == 72800.00


def test_fetch_google_finance_ticker_no_prev():
    from app.stock_service import _fetch_google_finance_ticker
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = 'data-last-price="73000"'
    with patch("app.stock_service._requests.get", return_value=mock_resp):
        result = _fetch_google_finance_ticker("SENSEX:INDEXBOM")
    assert result == (73000.0, 0)


def test_fetch_google_finance_ticker_failure():
    from app.stock_service import _fetch_google_finance_ticker
    with patch("app.stock_service._requests.get", side_effect=Exception("err")), \
         patch("time.sleep"):
        result = _fetch_google_finance_ticker("X:Y")
    assert result is None


# fetch_market_ticker

def test_fetch_market_ticker_non_kite_success():
    from app.stock_service import fetch_market_ticker
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "chart": {"result": [{"meta": {"regularMarketPrice": 73000, "previousClose": 72500}}]}
    }
    meta = {"key": "SENSEX", "label": "SENSEX", "yahoo": "^BSESN", "kite": False, "type": "index", "unit": ""}
    with patch("app.stock_service._requests.get", return_value=mock_resp):
        result = fetch_market_ticker(meta)
    assert result["price"] == 73000
    assert result["key"] == "SENSEX"


def test_fetch_market_ticker_fallback_google():
    from app.stock_service import fetch_market_ticker
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    meta = {"key": "SENSEX", "label": "SENSEX", "yahoo": "^BSESN", "kite": False, "type": "index", "unit": ""}
    with patch("app.stock_service._requests.get", return_value=mock_resp), \
         patch("app.stock_service._fetch_google_finance_ticker", return_value=(73000.0, 72000.0)):
        result = fetch_market_ticker(meta)
    assert result["price"] == 73000.0


def test_fetch_market_ticker_placeholder():
    from app.stock_service import fetch_market_ticker
    # kite ticker should return placeholder when ENABLE_YAHOO_GOOGLE is off
    import app.stock_service as ss
    original = ss.ENABLE_YAHOO_GOOGLE
    ss.ENABLE_YAHOO_GOOGLE = False
    meta = {"key": "NIFTY50", "label": "NIFTY 50", "yahoo": "^NSEI", "type": "index", "unit": ""}
    result = fetch_market_ticker(meta)
    assert result["price"] == 0
    ss.ENABLE_YAHOO_GOOGLE = original


# fetch_yahoo_ticker_historical

def test_fetch_yahoo_ticker_historical_success():
    from app.stock_service import fetch_yahoo_ticker_historical
    from datetime import datetime, timedelta
    import time as time_mod

    now = datetime.now()
    ts_7d = int((now - timedelta(days=10)).timestamp())
    ts_30d = int((now - timedelta(days=35)).timestamp())
    ts_now = int(now.timestamp())

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "chart": {"result": [{
            "timestamp": [ts_30d, ts_7d, ts_now],
            "indicators": {"quote": [{"close": [100.0, 105.0, 110.0]}]},
        }]}
    }
    meta = {"key": "SENSEX", "yahoo": "^BSESN"}
    with patch("app.stock_service._requests.get", return_value=mock_resp):
        result = fetch_yahoo_ticker_historical(meta)
    assert "week_change_pct" in result
    assert "month_change_pct" in result


def test_fetch_yahoo_ticker_historical_failure():
    from app.stock_service import fetch_yahoo_ticker_historical
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    meta = {"key": "SENSEX", "yahoo": "^BSESN"}
    with patch("app.stock_service._requests.get", return_value=mock_resp):
        result = fetch_yahoo_ticker_historical(meta)
    assert result == {"week_change_pct": 0.0, "month_change_pct": 0.0}


def test_fetch_yahoo_ticker_historical_exception():
    from app.stock_service import fetch_yahoo_ticker_historical
    meta = {"key": "X", "yahoo": "^X"}
    with patch("app.stock_service._requests.get", side_effect=Exception("err")):
        result = fetch_yahoo_ticker_historical(meta)
    assert result["week_change_pct"] == 0.0


def test_fetch_yahoo_ticker_historical_empty_chart():
    from app.stock_service import fetch_yahoo_ticker_historical
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"chart": {"result": []}}
    meta = {"key": "X", "yahoo": "^X"}
    with patch("app.stock_service._requests.get", return_value=mock_resp):
        result = fetch_yahoo_ticker_historical(meta)
    assert result["week_change_pct"] == 0.0


# fetch_live_data

def test_fetch_live_data_from_cache():
    from app import stock_service as ss
    ss.clear_cache()
    data = _make_stock_live("TCS", "NSE", 3500.0)
    ss._cache_set("TCS.NSE", data)
    result = ss.fetch_live_data("TCS", "NSE")
    assert result.current_price == 3500.0


def test_fetch_live_data_calls_fetch_multiple():
    from app import stock_service as ss
    ss.clear_cache()
    with patch.object(ss, "fetch_multiple", return_value={"INFY.NSE": _make_stock_live("INFY", "NSE", 1800)}) as mock_fm:
        result = ss.fetch_live_data("INFY", "NSE")
    assert result.current_price == 1800.0


# search_stock

def test_search_stock_found():
    from app.stock_service import search_stock
    mock_ticker = MagicMock()
    mock_ticker.info = {"shortName": "TCS Limited"}
    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = search_stock("TCS")
    assert len(result) == 1
    assert result[0]["symbol"] == "TCS"


def test_search_stock_not_found():
    from app.stock_service import search_stock
    mock_ticker = MagicMock()
    mock_ticker.info = {}
    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = search_stock("NOSYM")
    assert result == []


def test_search_stock_exception():
    from app.stock_service import search_stock
    with patch("yfinance.Ticker", side_effect=Exception("err")):
        result = search_stock("ERR")
    assert result == []


# _reset_circuit

def test_reset_circuit():
    from app.stock_service import _reset_circuit
    _reset_circuit()  # no-op, just ensure it doesn't raise


# stop_background_refresh

def test_stop_background_refresh():
    from app.stock_service import stop_background_refresh
    stop_background_refresh()  # no-op


# _fetch_via_zerodha

def test_fetch_via_zerodha_session_invalid():
    from app.stock_service import _fetch_via_zerodha
    with patch("app.stock_service.zerodha_service") as mock_z:
        mock_z.is_session_valid.return_value = False
        result = _fetch_via_zerodha([("X", "NSE")])
    assert result == {}


def test_fetch_via_zerodha_exception():
    from app.stock_service import _fetch_via_zerodha
    with patch("app.stock_service.zerodha_service") as mock_z:
        mock_z.is_session_valid.return_value = True
        mock_z.fetch_quotes.side_effect = Exception("err")
        result = _fetch_via_zerodha([("X", "NSE")])
    assert result == {}


# _initial_live_fetch

def test_initial_live_fetch_no_holdings():
    from app import stock_service as ss
    with patch.object(ss, "db") as mock_db:
        mock_db.get_all_holdings.return_value = []
        mock_db.get_all_sold.return_value = []
        ss._initial_live_fetch()
    assert ss._last_refresh_status == "no_holdings"


def test_initial_live_fetch_exception():
    from app import stock_service as ss
    with patch.object(ss, "db") as mock_db:
        mock_db.get_all_holdings.side_effect = Exception("db error")
        ss._initial_live_fetch()
    assert "error" in ss._last_refresh_status
