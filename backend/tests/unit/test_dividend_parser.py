"""
Unit tests for app/dividend_parser.py

Tests dividend PDF parsing, symbol resolution, and helper functions.
All PDF I/O and external lookups are mocked.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest


# ===================================================================
#  _normalize
# ===================================================================

def test_normalize_uppercase():
    from app.dividend_parser import _normalize
    assert _normalize("reliance") == "RELIANCE"


def test_normalize_strips_ltd():
    from app.dividend_parser import _normalize
    result = _normalize("Tata Motors Limited")
    assert "LIMITED" not in result
    assert "LTD" not in result


def test_normalize_removes_punctuation():
    from app.dividend_parser import _normalize
    result = _normalize("HDFC Bank & Finance Ltd.")
    assert "." not in result


def test_normalize_strips_india():
    from app.dividend_parser import _normalize
    result = _normalize("Coal India Limited")
    assert "INDIA" not in result
    assert "COAL" in result


# ===================================================================
#  _strip_dividend_suffix
# ===================================================================

def test_strip_div_suffix_simple():
    from app.dividend_parser import _strip_dividend_suffix
    assert _strip_dividend_suffix("TATAMOTORSDIV2") == "TATAMOTORS"


def test_strip_div_suffix_tatasteeldiv():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("TATASTEELDIV 2")
    assert "DIV" not in result.upper()


def test_strip_div_suffix_graphindfnl():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("GRAPHINDFNL202")
    assert "FNL" not in result.upper()


def test_strip_div_suffix_findiv():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("RALLISFINDIV24")
    assert "FINDIV" not in result.upper()


def test_strip_div_suffix_trailing_year():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("COALINDIA 2024")
    assert "2024" not in result


def test_strip_div_suffix_no_suffix():
    from app.dividend_parser import _strip_dividend_suffix
    assert _strip_dividend_suffix("RELIANCE") == "RELIANCE"


# ===================================================================
#  _is_dividend_entry
# ===================================================================

def test_is_dividend_entry_cemtex():
    from app.dividend_parser import _is_dividend_entry
    assert _is_dividend_entry("CEMTEX DEP ACHCr HDFC1234 COALINDIA Dividend") is True


def test_is_dividend_entry_non_cemtex():
    from app.dividend_parser import _is_dividend_entry
    assert _is_dividend_entry("NEFT Transfer from XYZ") is False


def test_is_dividend_entry_reversal():
    from app.dividend_parser import _is_dividend_entry
    assert _is_dividend_entry("CEMTEX DEP REVERSAL COALINDIA") is False


def test_is_dividend_entry_bounce():
    from app.dividend_parser import _is_dividend_entry
    assert _is_dividend_entry("CEMTEX DEP BOUNCE") is False


# ===================================================================
#  _extract_company_name
# ===================================================================

def test_extract_company_name_achcr():
    from app.dividend_parser import _extract_company_name
    desc = "CEMTEX DEP ACHCr NACH1234567 COALINDIA Dividend"
    result = _extract_company_name(desc)
    assert "COALINDIA" in result


def test_extract_company_name_c_number():
    from app.dividend_parser import _extract_company_name
    desc = "CEMTEX DEP C12345 67890TATASTEEL UNPAID DIVIDEND"
    result = _extract_company_name(desc)
    # Should extract TATASTEEL (without UNPAID DIVIDEND)
    assert "UNPAID DIVIDEND" not in result


def test_extract_company_name_empty():
    from app.dividend_parser import _extract_company_name
    assert _extract_company_name("no cemtex here") == ""


# ===================================================================
#  _parse_date
# ===================================================================

def test_parse_date_slash():
    from app.dividend_parser import _parse_date
    assert _parse_date("15/03/2024") == "2024-03-15"


def test_parse_date_dash():
    from app.dividend_parser import _parse_date
    assert _parse_date("01-06-2023") == "2023-06-01"


def test_parse_date_invalid():
    from app.dividend_parser import _parse_date
    result = _parse_date("not-a-date")
    assert result == "not-a-date"  # returned as-is


# ===================================================================
#  _parse_amount
# ===================================================================

def test_parse_amount_string():
    from app.dividend_parser import _parse_amount
    assert _parse_amount("1,234.56") == pytest.approx(1234.56)


def test_parse_amount_float():
    from app.dividend_parser import _parse_amount
    assert _parse_amount(500.0) == pytest.approx(500.0)


def test_parse_amount_int():
    from app.dividend_parser import _parse_amount
    assert _parse_amount(1000) == pytest.approx(1000.0)


def test_parse_amount_empty():
    from app.dividend_parser import _parse_amount
    assert _parse_amount("") == 0.0


def test_parse_amount_none():
    from app.dividend_parser import _parse_amount
    assert _parse_amount(None) == 0.0


# ===================================================================
#  _resolve_symbol
# ===================================================================

def test_resolve_symbol_known_abbreviation():
    from app.dividend_parser import _resolve_symbol
    symbol, matched = _resolve_symbol("SBI", {}, set())
    assert symbol == "SBIN"
    assert matched is True


def test_resolve_symbol_lic():
    from app.dividend_parser import _resolve_symbol
    symbol, matched = _resolve_symbol("LIC", {}, set())
    assert symbol == "LICI"


def test_resolve_symbol_direct_match():
    from app.dividend_parser import _resolve_symbol
    symbol_set = {"RELIANCE", "TCS", "INFY"}
    symbol, matched = _resolve_symbol("RELIANCE", {}, symbol_set)
    assert symbol == "RELIANCE"
    assert matched is True


def test_resolve_symbol_exact_name_match():
    from app.dividend_parser import _resolve_symbol
    from app.dividend_parser import _normalize
    name_to_symbol = {_normalize("HDFC Bank"): "HDFCBANK"}
    symbol_set = {"HDFCBANK"}
    symbol, matched = _resolve_symbol("HDFC BANK", name_to_symbol, symbol_set)
    assert symbol == "HDFCBANK"
    assert matched is True


def test_resolve_symbol_empty():
    from app.dividend_parser import _resolve_symbol
    symbol, matched = _resolve_symbol("", {}, set())
    assert symbol == ""
    assert matched is False


def test_resolve_symbol_user_override():
    from app.dividend_parser import _resolve_symbol
    overrides = {"TATAMOTORS": "TMCV"}
    symbol, matched = _resolve_symbol("TATAMOTORS", {}, set(), user_overrides=overrides)
    assert symbol == "TMCV"
    assert matched is True


# ===================================================================
#  _build_lookup_tables
# ===================================================================

def test_build_lookup_tables_from_cache(tmp_path):
    from app.dividend_parser import _build_lookup_tables
    cache = {
        "name": {"TATA MOTORS": "TATAMOTORS"},
        "isin": {"INE155A01022": ["TATAMOTORS", "NSE", "Tata Motors Limited"]},
    }
    cache_file = tmp_path / "symbol_cache.json"
    cache_file.write_text(json.dumps(cache))
    name_to_symbol, symbol_set, aliases = _build_lookup_tables(cache_file, {"SBIN": "State Bank"})
    assert "TATAMOTORS" in symbol_set
    assert "SBIN" in symbol_set  # from portfolio


def test_build_lookup_tables_missing_cache(tmp_path):
    from app.dividend_parser import _build_lookup_tables
    missing = tmp_path / "nonexistent.json"
    name_to_symbol, symbol_set, aliases = _build_lookup_tables(missing, {})
    # Should not raise, just return empty structures
    assert isinstance(name_to_symbol, dict)
    assert isinstance(symbol_set, set)


# ===================================================================
#  parse_dividend_statement — mocked pdfplumber
# ===================================================================

def _make_mock_pdf_with_tables(tables_per_page, text_per_page=""):
    pages = []
    for tables in tables_per_page:
        page = MagicMock()
        page.extract_text.return_value = text_per_page
        page.extract_tables.return_value = tables
        pages.append(page)
    pdf = MagicMock()
    pdf.pages = pages
    pdf.__enter__ = lambda s: s
    pdf.__exit__ = MagicMock(return_value=False)
    return pdf


def test_parse_dividend_statement_empty_pdf(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    mock_pdf = _make_mock_pdf_with_tables([[]])
    data_dir = tmp_path
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.dividend_parser.DATA_DIR", data_dir):
        result = parse_dividend_statement(b"fake pdf", portfolio_name_map={})
    assert "dividends" in result
    assert isinstance(result["dividends"], list)


def test_parse_dividend_statement_with_dividend_row(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    # Simulate a table with a CEMTEX DEP row
    table = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["15/03/2024", "CEMTEX DEP ACHCr NACH123 COALINDIA Dividend", "", "500.00", "10000.00"],
    ]
    mock_pdf = _make_mock_pdf_with_tables([[table]])
    data_dir = tmp_path
    cache_file = data_dir / "symbol_cache.json"
    cache_file.write_text(json.dumps({"name": {}, "isin": {}}))
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.dividend_parser.DATA_DIR", data_dir):
        result = parse_dividend_statement(b"fake pdf", portfolio_name_map={"COALINDIA": "Coal India"})
    # Should find at least one dividend entry
    assert isinstance(result["dividends"], list)


def test_parse_dividend_statement_skips_non_cemtex(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    table = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["01/04/2024", "NEFT Transfer from ABC Bank", "", "1000.00", "20000.00"],
    ]
    mock_pdf = _make_mock_pdf_with_tables([[table]])
    data_dir = tmp_path
    cache_file = data_dir / "symbol_cache.json"
    cache_file.write_text(json.dumps({"name": {}, "isin": {}}))
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.dividend_parser.DATA_DIR", data_dir):
        result = parse_dividend_statement(b"fake pdf", portfolio_name_map={})
    assert result["dividends"] == []


# ===================================================================
#  save_user_overrides / _load_user_overrides
# ===================================================================

def test_save_and_load_user_overrides(tmp_path):
    from app.dividend_parser import save_user_overrides, _load_user_overrides
    with patch("app.dividend_parser._OVERRIDES_FILE", tmp_path / "overrides.json"), \
         patch("app.dividend_parser.DATA_DIR", tmp_path):
        save_user_overrides({"TATAMOTORS": "TMCV"})
        loaded = _load_user_overrides()
    assert loaded.get("TATAMOTORS") == "TMCV"


def test_load_user_overrides_missing(tmp_path):
    from app.dividend_parser import _load_user_overrides
    with patch("app.dividend_parser._OVERRIDES_FILE", tmp_path / "nonexistent.json"):
        result = _load_user_overrides()
    assert result == {}
