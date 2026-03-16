"""
Unit tests for app/symbol_resolver.py

Tests symbol lookup, normalization, cache loading, and persistence.
All network and file I/O are mocked.
"""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest


# ─── helpers to reset module globals between tests ──────────────────────────

def _reset_globals():
    import app.symbol_resolver as sr
    sr._ISIN_MAP.clear()
    sr._NAME_MAP.clear()
    sr._LOADED_OK = False
    sr._LOADED_AT = 0


# ═══════════════════════════════════════════════════════════
#  _normalize
# ═══════════════════════════════════════════════════════════

def test_normalize_strips_limited():
    from app.symbol_resolver import _normalize
    assert _normalize("Reliance Industries Limited") == "RELIANCE INDUSTRIES"


def test_normalize_strips_ltd():
    from app.symbol_resolver import _normalize
    assert _normalize("Tata Motors Ltd") == "TATA MOTORS"


def test_normalize_strips_ltd_dot():
    from app.symbol_resolver import _normalize
    assert _normalize("Infosys Ltd.") == "INFOSYS"


def test_normalize_strips_archive():
    from app.symbol_resolver import _normalize
    assert _normalize("SBI - ARCHIVE") == "SBI"


def test_normalize_uppercase():
    from app.symbol_resolver import _normalize
    assert _normalize("infosys") == "INFOSYS"


def test_normalize_pvt():
    from app.symbol_resolver import _normalize
    assert _normalize("Some Company Pvt") == "SOME COMPANY"


# ═══════════════════════════════════════════════════════════
#  _normalize_variants
# ═══════════════════════════════════════════════════════════

def test_normalize_variants_with_parens():
    from app.symbol_resolver import _normalize_variants
    variants = _normalize_variants("Dixon Techno (India)")
    assert "DIXON TECHNO (INDIA)" in variants or any("DIXON TECHNO" in v for v in variants)
    # Without parens variant should also be present
    assert any("DIXON TECHNO" in v and "INDIA" not in v for v in variants)


def test_normalize_variants_no_parens():
    from app.symbol_resolver import _normalize_variants
    variants = _normalize_variants("Reliance Industries")
    assert len(variants) == 1  # no parens → only one variant


# ═══════════════════════════════════════════════════════════
#  derive_symbol
# ═══════════════════════════════════════════════════════════

def test_derive_symbol_single_word():
    from app.symbol_resolver import derive_symbol
    assert derive_symbol("RELIANCE") == "RELIANCE"


def test_derive_symbol_strips_limited():
    from app.symbol_resolver import derive_symbol
    assert derive_symbol("Tata Motors Limited") == "TATA"


def test_derive_symbol_two_short_words():
    from app.symbol_resolver import derive_symbol
    # "AB Testing": first word 2 chars, second not stripped → concat
    result = derive_symbol("AB Testing")
    assert result == "ABTESTING"


def test_derive_symbol_empty():
    from app.symbol_resolver import derive_symbol
    assert derive_symbol("") == "UNKNOWN"


def test_derive_symbol_long_name():
    from app.symbol_resolver import derive_symbol
    result = derive_symbol("Bajaj Auto Limited")
    assert result == "BAJAJ"


# ═══════════════════════════════════════════════════════════
#  resolve_by_isin — direct map lookup
# ═══════════════════════════════════════════════════════════

def test_resolve_by_isin_found():
    from app import symbol_resolver as sr
    _reset_globals()
    sr._ISIN_MAP["INE002A01018"] = ("RELIANCE", "NSE", "Reliance Industries")
    result = sr.resolve_by_isin("INE002A01018")
    assert result == ("RELIANCE", "NSE", "Reliance Industries")


def test_resolve_by_isin_not_found():
    from app import symbol_resolver as sr
    _reset_globals()
    assert sr.resolve_by_isin("INVALID123") is None


# ═══════════════════════════════════════════════════════════
#  resolve_by_name — name map lookup
# ═══════════════════════════════════════════════════════════

def test_resolve_by_name_exact_match():
    from app import symbol_resolver as sr
    _reset_globals()
    sr._NAME_MAP["TATA MOTORS"] = "TATAMOTORS"
    result = sr.resolve_by_name("Tata Motors Limited")
    assert result == "TATAMOTORS"


def test_resolve_by_name_partial_match():
    from app import symbol_resolver as sr
    _reset_globals()
    sr._NAME_MAP["INFOSYS"] = "INFY"
    result = sr.resolve_by_name("Infosys BPO")  # "INFOSYS" is in "INFOSYS BPO"
    assert result == "INFY"


def test_resolve_by_name_empty_map():
    from app import symbol_resolver as sr
    _reset_globals()
    assert sr.resolve_by_name("Any Company") is None


def test_resolve_by_name_no_match():
    from app import symbol_resolver as sr
    _reset_globals()
    sr._NAME_MAP["WIPRO"] = "WIPRO"
    result = sr.resolve_by_name("Totally Unknown Company Xyz")
    assert result is None


# ═══════════════════════════════════════════════════════════
#  _load_cache
# ═══════════════════════════════════════════════════════════

def test_load_cache_returns_none_when_missing(tmp_path):
    from app import symbol_resolver as sr
    with patch.object(sr, "_CACHE_FILE", tmp_path / "nonexistent.json"):
        isin_map, name_map, ts = sr._load_cache()
    assert isin_map is None
    assert name_map is None
    assert ts == 0


def test_load_cache_reads_valid_file(tmp_path):
    from app import symbol_resolver as sr
    cache_file = tmp_path / "symbol_cache.json"
    cache_data = {
        "ts": 1700000000.0,
        "isin": {"INE002A01018": ["RELIANCE", "NSE", "Reliance Industries"]},
        "name": {"RELIANCE INDUSTRIES": "RELIANCE"},
    }
    cache_file.write_text(json.dumps(cache_data))
    with patch.object(sr, "_CACHE_FILE", cache_file):
        isin_map, name_map, ts = sr._load_cache()
    assert isin_map["INE002A01018"] == ("RELIANCE", "NSE", "Reliance Industries")
    assert name_map["RELIANCE INDUSTRIES"] == "RELIANCE"
    assert ts == 1700000000.0


# ═══════════════════════════════════════════════════════════
#  _save_cache
# ═══════════════════════════════════════════════════════════

def test_save_cache_writes_file(tmp_path):
    from app import symbol_resolver as sr
    isin_map = {"INE002A01018": ("RELIANCE", "NSE", "Reliance Industries")}
    name_map = {"RELIANCE INDUSTRIES": "RELIANCE"}
    cache_file = tmp_path / "symbol_cache.json"
    with patch.object(sr, "_CACHE_FILE", cache_file), \
         patch.object(sr, "_DATA_DIR", tmp_path):
        sr._save_cache(isin_map, name_map)
    assert cache_file.exists()
    data = json.loads(cache_file.read_text())
    assert "RELIANCE INDUSTRIES" in data["name"]
    assert "INE002A01018" in data["isin"]


# ═══════════════════════════════════════════════════════════
#  ensure_loaded — fresh cache avoids network call
# ═══════════════════════════════════════════════════════════

def test_ensure_loaded_uses_fresh_cache(tmp_path):
    """ensure_loaded() should not call _do_load when data is fresh."""
    from app import symbol_resolver as sr
    _reset_globals()
    sr._LOADED_OK = True
    sr._LOADED_AT = time.time()  # just loaded
    with patch.object(sr, "_do_load") as mock_load:
        sr.ensure_loaded()
    mock_load.assert_not_called()


def test_ensure_loaded_calls_do_load_when_stale(tmp_path):
    """ensure_loaded() triggers _do_load when data is stale."""
    from app import symbol_resolver as sr
    _reset_globals()
    sr._LOADED_OK = True
    sr._LOADED_AT = time.time() - 90000  # older than 24h TTL
    with patch.object(sr, "_do_load") as mock_load:
        sr.ensure_loaded()
    mock_load.assert_called_once()


# ═══════════════════════════════════════════════════════════
#  _load_from_network — mocked urllib
# ═══════════════════════════════════════════════════════════

def test_load_from_network_parses_nse_csv():
    from app import symbol_resolver as sr
    nse_csv = "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\r\nRELIANCE,Reliance Industries Ltd,EQ,29-NOV-1995,10,1,INE002A01018,10\r\n"
    zerodha_csv = "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\r\n"  # empty

    mock_nse_resp = MagicMock()
    mock_nse_resp.read.return_value = nse_csv.encode()
    mock_nse_resp.__enter__ = lambda s: s
    mock_nse_resp.__exit__ = MagicMock(return_value=False)

    mock_z_resp = MagicMock()
    mock_z_resp.read.return_value = zerodha_csv.encode()
    mock_z_resp.__enter__ = lambda s: s
    mock_z_resp.__exit__ = MagicMock(return_value=False)

    call_count = [0]
    def fake_urlopen(req, timeout=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_nse_resp
        return mock_z_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        isin_map, name_map = sr._load_from_network()

    assert "INE002A01018" in isin_map
    assert isin_map["INE002A01018"][0] == "RELIANCE"


def test_load_from_network_handles_nse_failure():
    """Network failure returns empty maps without raising."""
    from app import symbol_resolver as sr
    with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
        isin_map, name_map = sr._load_from_network()
    assert isin_map == {}
    assert name_map == {}


# ═══════════════════════════════════════════════════════════
#  get_name_map / get_isin_map
# ═══════════════════════════════════════════════════════════

def test_get_name_map_returns_reference():
    from app import symbol_resolver as sr
    _reset_globals()
    sr._NAME_MAP["TEST"] = "TEST"
    assert sr.get_name_map() is sr._NAME_MAP


def test_get_isin_map_returns_reference():
    from app import symbol_resolver as sr
    _reset_globals()
    sr._ISIN_MAP["INE001A01036"] = ("TCS", "NSE", "Tata Consultancy Services")
    assert sr.get_isin_map() is sr._ISIN_MAP
