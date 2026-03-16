"""
Unit tests for app/stock_service.py

Tests the Zerodha-primary / Yahoo-fallback price fetching logic.
All external I/O (network, file system) is mocked.
"""
import json
import os
from unittest.mock import MagicMock, patch, mock_open

import pytest

from app.models import StockLiveData


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_stock_live(symbol="RELIANCE", exchange="NSE", price=2500.0):
    return StockLiveData(
        symbol=symbol, exchange=exchange, name="Reliance Industries",
        current_price=price, week_52_high=2800.0, week_52_low=2200.0,
        day_change=50.0, day_change_pct=2.0,
        volume=1000000, previous_close=2450.0,
        is_manual=False,
    )


# ═══════════════════════════════════════════════════════════
#  cache helpers
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
#  _yahoo_sym
# ═══════════════════════════════════════════════════════════

def test_yahoo_sym_nse():
    from app.stock_service import _yahoo_sym
    assert _yahoo_sym("RELIANCE", "NSE") == "RELIANCE.NS"


def test_yahoo_sym_bse():
    from app.stock_service import _yahoo_sym
    assert _yahoo_sym("500325", "BSE") == "500325.BO"


def test_yahoo_sym_already_suffixed():
    from app.stock_service import _yahoo_sym
    assert _yahoo_sym("TCS.NS", "NSE") == "TCS.NS"


# ═══════════════════════════════════════════════════════════
#  _load_prices_file / _save_prices_file
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
#  _file_fallback
# ═══════════════════════════════════════════════════════════

def test_file_fallback_found(tmp_path):
    from app import stock_service as ss
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({
        "INFY.NSE": {"price": 1800.0, "name": "Infosys", "week_52_high": 2000.0,
                     "week_52_low": 1500.0, "day_change": 0, "day_change_pct": 0,
                     "volume": 0, "previous_close": 0}
    }))
    with patch.object(ss, "_PRICES_FILE", str(prices_file)):
        result = ss._file_fallback("INFY", "NSE")
    assert result is not None
    assert result.current_price == 1800.0
    assert result.is_manual is True


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


# ═══════════════════════════════════════════════════════════
#  fetch_multiple — Zerodha success path
# ═══════════════════════════════════════════════════════════

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
    """When Zerodha is unavailable, should fall back to JSON file."""
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({
        "TCS.NSE": {"price": 3500.0, "name": "TCS", "week_52_high": 4000.0,
                    "week_52_low": 3000.0, "day_change": 0, "day_change_pct": 0,
                    "volume": 0, "previous_close": 0}
    }))

    with patch("app.stock_service.zerodha_service") as mock_z, \
         patch.object(ss, "_PRICES_FILE", str(prices_file)):
        mock_z.is_session_valid.return_value = False
        results = ss.fetch_multiple([("TCS", "NSE")])

    assert "TCS.NSE" in results
    assert results["TCS.NSE"].current_price == 3500.0
    assert results["TCS.NSE"].is_manual is True


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


# ═══════════════════════════════════════════════════════════
#  bulk_update_prices
# ═══════════════════════════════════════════════════════════

def test_bulk_update_prices(tmp_path):
    from app import stock_service as ss
    ss.clear_cache()
    prices_file = tmp_path / "stock_prices.json"
    prices_file.write_text(json.dumps({}))

    with patch.object(ss, "_PRICES_FILE", str(prices_file)), \
         patch.object(ss, "_DATA_DIR", str(tmp_path)):
        count = ss.bulk_update_prices({
            "HDFC": {"exchange": "NSE", "price": 1500.0, "name": "HDFC Bank"},
            "INVALID": {"exchange": "NSE", "price": 0},  # should be skipped
        })

    assert count == 1
    result = ss._cache_get("HDFC.NSE")
    assert result is not None
    assert result.current_price == 1500.0


# ═══════════════════════════════════════════════════════════
#  get_refresh_status
# ═══════════════════════════════════════════════════════════

def test_get_refresh_status_structure():
    from app.stock_service import get_refresh_status
    status = get_refresh_status()
    assert "status" in status
    assert "cache_size" in status
    assert "refresh_interval" in status


# ═══════════════════════════════════════════════════════════
#  get_cached_prices — memory → JSON → xlsx chain
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
#  _download_batch (Yahoo Finance mock)
# ═══════════════════════════════════════════════════════════

def test_download_batch_empty_tickers():
    from app.stock_service import _download_batch
    result = _download_batch([])
    assert result == {}


def test_download_batch_yf_fails():
    from app.stock_service import _download_batch
    import pandas as pd
    with patch("yfinance.download", return_value=pd.DataFrame()):
        result = _download_batch(["RELIANCE.NS"])
    assert result == {}
