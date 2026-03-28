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


# ═══════════════════════════════════════════════════════════
#  _load_from_network — Zerodha CSV parsing (lines 160-173)
# ═══════════════════════════════════════════════════════════

def test_load_from_network_parses_zerodha_csv():
    """Zerodha CSV rows with EQ/ETF instrument_type are loaded into name_map."""
    from app import symbol_resolver as sr

    nse_csv = "SYMBOL,NAME OF COMPANY,ISIN NUMBER\r\n"  # empty NSE data
    zerodha_csv = (
        "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\r\n"
        "1234,567,RELIANCE,Reliance Industries,2500,,0,0.05,1,EQ,NSE,NSE\r\n"
        "2345,678,GOLDBEES,Nippon Gold ETF,55,,0,0.01,1,ETF,NSE,NSE\r\n"
        "3456,789,NIFTY25MAR,Nifty Futures,22000,2025-03-27,0,0.05,50,FUT,NFO,NFO\r\n"  # skipped: not EQ/ETF
        "4567,890,SBIN,State Bank of India,750,,0,0.05,1,EQ,BSE,BSE\r\n"
    )

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

    # EQ and ETF should be in the map
    assert name_map.get("RELIANCE INDUSTRIES") == "RELIANCE"
    # BSE entry should be there (because it wasn't already in from NSE)
    assert name_map.get("STATE BANK OF INDIA") == "SBIN"


def test_load_from_network_nse_skips_missing_isin_or_symbol():
    """NSE CSV rows without ISIN or symbol are skipped (line 135)."""
    from app import symbol_resolver as sr

    # Row missing ISIN, row missing symbol
    nse_csv = "SYMBOL,NAME OF COMPANY,ISIN NUMBER\r\n,Missing Symbol Corp,INE999Z99999\r\nHASISIN,Has ISIN Corp,\r\n"
    zerodha_csv = "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\r\n"

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
        return mock_nse_resp if call_count[0] == 1 else mock_z_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        isin_map, name_map = sr._load_from_network()

    # Both rows should be skipped
    assert len(isin_map) == 0


def test_load_from_network_zerodha_skips_empty_name_or_symbol():
    """Zerodha rows without tradingsymbol or name are skipped (line 167)."""
    from app import symbol_resolver as sr

    nse_csv = "SYMBOL,NAME OF COMPANY,ISIN NUMBER\r\n"
    zerodha_csv = (
        "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\r\n"
        "1234,567,,Reliance,2500,,0,0.05,1,EQ,NSE,NSE\r\n"  # missing tradingsymbol
        "2345,678,SBIN,,750,,0,0.05,1,EQ,NSE,NSE\r\n"  # missing name
    )

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
        return mock_nse_resp if call_count[0] == 1 else mock_z_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        isin_map, name_map = sr._load_from_network()

    # Both rows should be skipped
    assert len(name_map) == 0


def test_load_from_network_nse_skips_non_ine_isins():
    """NSE CSV rows with ISINs not starting with INE/INF are skipped."""
    from app import symbol_resolver as sr

    nse_csv = "SYMBOL,NAME OF COMPANY,ISIN NUMBER\r\nFOREIGN,Foreign Corp,US0000000001\r\n"
    zerodha_csv = "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\r\n"

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
        return mock_nse_resp if call_count[0] == 1 else mock_z_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        isin_map, name_map = sr._load_from_network()

    assert "US0000000001" not in isin_map


def test_load_from_network_zerodha_failure_returns_nse_only():
    """If Zerodha download fails, NSE data is still returned."""
    from app import symbol_resolver as sr

    nse_csv = "SYMBOL,NAME OF COMPANY,ISIN NUMBER\r\nINFY,Infosys Ltd,INE009A01021\r\n"
    mock_nse_resp = MagicMock()
    mock_nse_resp.read.return_value = nse_csv.encode()
    mock_nse_resp.__enter__ = lambda s: s
    mock_nse_resp.__exit__ = MagicMock(return_value=False)

    call_count = [0]
    def fake_urlopen(req, timeout=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_nse_resp
        raise ConnectionError("Zerodha down")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        isin_map, name_map = sr._load_from_network()

    assert "INE009A01021" in isin_map


# ═══════════════════════════════════════════════════════════
#  _save_cache — exception handling (lines 195-196)
# ═══════════════════════════════════════════════════════════

def test_save_cache_handles_write_failure():
    """_save_cache logs error but doesn't raise on write failure."""
    from app import symbol_resolver as sr

    with patch.object(sr, "_CACHE_FILE", Path("/nonexistent/dir/cache.json")), \
         patch.object(sr, "_DATA_DIR", Path("/nonexistent/dir")):
        # Should not raise
        sr._save_cache({"INE": ("SYM", "NSE", "Name")}, {"NAME": "SYM"})


# ═══════════════════════════════════════════════════════════
#  _load_cache — exception handling (lines 211-213)
# ═══════════════════════════════════════════════════════════

def test_load_cache_handles_corrupt_file(tmp_path):
    """_load_cache returns (None, None, 0) for corrupt JSON."""
    from app import symbol_resolver as sr

    cache_file = tmp_path / "corrupt.json"
    cache_file.write_text("NOT JSON!!!")
    with patch.object(sr, "_CACHE_FILE", cache_file):
        isin_map, name_map, ts = sr._load_cache()
    assert isin_map is None
    assert name_map is None
    assert ts == 0


# ═══════════════════════════════════════════════════════════
#  _do_load — all paths (lines 220-255)
# ═══════════════════════════════════════════════════════════

def test_do_load_from_fresh_cache(tmp_path):
    """_do_load uses fresh disk cache without network call."""
    from app import symbol_resolver as sr
    _reset_globals()

    cache_data = {
        "ts": time.time(),  # fresh
        "isin": {"INE002A01018": ["RELIANCE", "NSE", "Reliance Industries"]},
        "name": {"RELIANCE INDUSTRIES": "RELIANCE"},
    }
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps(cache_data))

    with patch.object(sr, "_CACHE_FILE", cache_file), \
         patch.object(sr, "_load_from_network") as mock_net:
        sr._do_load()

    mock_net.assert_not_called()
    assert sr._LOADED_OK is True
    assert sr._ISIN_MAP.get("INE002A01018") == ("RELIANCE", "NSE", "Reliance Industries")


def test_do_load_from_network_success(tmp_path):
    """_do_load downloads and saves cache when cache is stale/missing."""
    from app import symbol_resolver as sr
    _reset_globals()

    isin = {"INE002A01018": ("RELIANCE", "NSE", "Reliance Industries")}
    names = {"RELIANCE INDUSTRIES": "RELIANCE"}

    with patch.object(sr, "_CACHE_FILE", tmp_path / "cache.json"), \
         patch.object(sr, "_DATA_DIR", tmp_path), \
         patch.object(sr, "_load_cache", return_value=(None, None, 0)), \
         patch.object(sr, "_load_from_network", return_value=(isin, names)), \
         patch.object(sr, "_save_cache") as mock_save:
        sr._do_load()

    assert sr._LOADED_OK is True
    assert sr._ISIN_MAP == isin
    mock_save.assert_called_once()


def test_do_load_network_fail_uses_stale_cache():
    """_do_load falls back to stale cache when network fails."""
    from app import symbol_resolver as sr
    _reset_globals()

    stale_isin = {"INE999": ("STALE", "NSE", "Stale")}
    stale_names = {"STALE": "STALE"}

    with patch.object(sr, "_load_cache", return_value=(stale_isin, stale_names, 1000.0)), \
         patch.object(sr, "_load_from_network", return_value=({}, {})):
        sr._do_load()

    assert sr._LOADED_OK is True
    assert sr._ISIN_MAP == stale_isin


def test_do_load_network_fail_no_cache():
    """_do_load sets _LOADED_OK=False when both network and cache fail."""
    from app import symbol_resolver as sr
    _reset_globals()

    with patch.object(sr, "_load_cache", return_value=(None, None, 0)), \
         patch.object(sr, "_load_from_network", return_value=({}, {})):
        sr._do_load()

    assert sr._LOADED_OK is False


# ═══════════════════════════════════════════════════════════
#  ensure_loaded — throttle on failure (line 272)
# ═══════════════════════════════════════════════════════════

def test_ensure_loaded_throttles_retries_on_failure():
    """ensure_loaded skips _do_load if last failure was < 60s ago."""
    from app import symbol_resolver as sr
    _reset_globals()
    sr._LOADED_OK = False
    sr._LOADED_AT = time.time() - 10  # failed 10s ago (< 60s throttle)

    with patch.object(sr, "_do_load") as mock_load:
        sr.ensure_loaded()
    mock_load.assert_not_called()


def test_ensure_loaded_retries_after_throttle():
    """ensure_loaded calls _do_load if last failure was > 60s ago."""
    from app import symbol_resolver as sr
    _reset_globals()
    sr._LOADED_OK = False
    sr._LOADED_AT = time.time() - 120  # failed 120s ago (> 60s throttle)

    with patch.object(sr, "_do_load") as mock_load:
        sr.ensure_loaded()
    mock_load.assert_called_once()
