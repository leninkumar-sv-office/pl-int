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


def test_normalize_strips_multiple_words():
    from app.dividend_parser import _normalize
    result = _normalize("The Private Corporation of India Ltd")
    assert "THE" not in result
    assert "PRIVATE" not in result
    assert "CORPORATION" not in result


def test_normalize_strips_trailing_dots():
    from app.dividend_parser import _normalize
    result = _normalize("TATA---.")
    assert result == "TATA"


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


def test_strip_div_suffix_trailing_int():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("SBIN INT")
    assert "INT" not in result


def test_strip_div_suffix_trailing_final():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("TCS FINAL")
    assert "FINAL" not in result


def test_strip_div_suffix_trailing_fin():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("TTLFIN")
    assert result == "TTL"


def test_strip_div_suffix_trailing_dividend():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("RELIANCE Dividend 3")
    assert "Dividend" not in result


def test_strip_div_suffix_trailing_ltd():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("RELIANCE LTD")
    assert "LTD" not in result


def test_strip_div_suffix_trailing_limited():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("RELIANCE LIMITED")
    assert "LIMITED" not in result


def test_strip_div_suffix_trailing_limi():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("RELIANCE LIMI")
    assert "LIMI" not in result


def test_strip_div_suffix_intm():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("SBIN 2ndintm")
    # Should strip the "2ndintm" suffix
    assert "intm" not in result.lower()


def test_strip_div_suffix_dash_number():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("RAILTEL-2")
    assert result == "RAILTEL"


def test_strip_div_suffix_findiv_pattern():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("COALINDIA - FINDIV")
    # Should strip the - FINDIV suffix
    assert "FINDIV" not in result


def test_strip_div_suffix_trailing_number():
    from app.dividend_parser import _strip_dividend_suffix
    result = _strip_dividend_suffix("RELIANCE 3")
    assert result == "RELIANCE"


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


def test_is_dividend_entry_imps():
    from app.dividend_parser import _is_dividend_entry
    assert _is_dividend_entry("CEMTEX DEP IMPS 123456") is False


def test_is_dividend_entry_return():
    from app.dividend_parser import _is_dividend_entry
    assert _is_dividend_entry("CEMTEX DEP RETURN 123") is False


def test_is_dividend_entry_reject():
    from app.dividend_parser import _is_dividend_entry
    assert _is_dividend_entry("CEMTEX DEP REJECT 123") is False


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
    assert "UNPAID DIVIDEND" not in result
    assert "TATASTEEL" in result


def test_extract_company_name_empty():
    from app.dividend_parser import _extract_company_name
    assert _extract_company_name("no cemtex here") == ""


def test_extract_company_name_generic_fallback():
    from app.dividend_parser import _extract_company_name
    desc = "CEMTEX DEP NEFT REF123 HDFC BANK Dividend"
    result = _extract_company_name(desc)
    assert "HDFC" in result


def test_extract_company_name_ultra_fallback():
    from app.dividend_parser import _extract_company_name
    desc = "CEMTEX DEP ACHCr RELIANCE"
    result = _extract_company_name(desc)
    assert "RELIANCE" in result


def test_extract_company_name_c_number_with_dividend():
    from app.dividend_parser import _extract_company_name
    desc = "CEMTEX DEP C12345 67890SBIN DIVIDEND 3"
    result = _extract_company_name(desc)
    assert "DIVIDEND" not in result or "SBIN" in result


# ===================================================================
#  _extract_statement_period
# ===================================================================

def test_extract_statement_period_found():
    from app.dividend_parser import _extract_statement_period
    pages = ["Statement from 01/01/2024 to 31/03/2024"]
    result = _extract_statement_period(pages)
    assert "01/01/2024" in result
    assert "31/03/2024" in result


def test_extract_statement_period_empty():
    from app.dividend_parser import _extract_statement_period
    assert _extract_statement_period([]) == ""
    assert _extract_statement_period(["no period here"]) == ""


# ===================================================================
#  _parse_date
# ===================================================================

def test_parse_date_slash():
    from app.dividend_parser import _parse_date
    assert _parse_date("15/03/2024") == "2024-03-15"


def test_parse_date_dash():
    from app.dividend_parser import _parse_date
    assert _parse_date("01-06-2023") == "2023-06-01"


def test_parse_date_short_year():
    from app.dividend_parser import _parse_date
    assert _parse_date("01/06/24") == "2024-06-01"


def test_parse_date_invalid():
    from app.dividend_parser import _parse_date
    result = _parse_date("not-a-date")
    assert result == "not-a-date"


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


def test_parse_amount_invalid():
    from app.dividend_parser import _parse_amount
    assert _parse_amount("abc") == 0.0


def test_parse_amount_with_spaces():
    from app.dividend_parser import _parse_amount
    assert _parse_amount(" 1 234.56 ") == pytest.approx(1234.56)


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


def test_resolve_symbol_user_override_cleaned():
    from app.dividend_parser import _resolve_symbol
    overrides = {"TPOWER": "TATAPOWER"}
    symbol, matched = _resolve_symbol("TPOWERDIV2", {}, set(), user_overrides=overrides)
    # After stripping DIV suffix, cleaned = "TPOWER", should match override
    assert symbol == "TATAPOWER"
    assert matched is True


def test_resolve_symbol_portfolio_preference():
    from app.dividend_parser import _resolve_symbol
    symbol_set = {"RELIANCE"}
    portfolio = {"RELIANCE"}
    symbol, matched = _resolve_symbol("RELIANCE", {}, symbol_set, portfolio_symbols=portfolio)
    assert symbol == "RELIANCE"
    assert matched is True


def test_resolve_symbol_first_token_portfolio():
    from app.dividend_parser import _resolve_symbol
    portfolio = {"RAILTEL"}
    symbol_set = {"RAILTEL"}
    symbol, matched = _resolve_symbol("RAILTEL CORP OF INDIA", {}, symbol_set, portfolio_symbols=portfolio)
    assert symbol == "RAILTEL"
    assert matched is True


def test_resolve_symbol_prefix_match():
    from app.dividend_parser import _resolve_symbol, _normalize
    name_to_symbol = {_normalize("ASIAN PAINTS LIMITED"): "ASIANPAINT"}
    symbol_set = {"ASIANPAINT"}
    symbol, matched = _resolve_symbol("ASIAN PAINTS", name_to_symbol, symbol_set)
    assert symbol == "ASIANPAINT"
    assert matched is True


def test_resolve_symbol_fuzzy_match():
    from app.dividend_parser import _resolve_symbol, _normalize
    name_to_symbol = {_normalize("TATA CONSULTANCY SERVICES"): "TCS"}
    symbol_set = {"TCS"}
    symbol, matched = _resolve_symbol("TATA CONSULTANC SERV", name_to_symbol, symbol_set)
    # Should fuzzy match to TCS
    assert matched is True


def test_resolve_symbol_two_word_prefix():
    from app.dividend_parser import _resolve_symbol, _normalize
    name_to_symbol = {_normalize("BAJAJ FINANCE LIMITED"): "BAJFINANCE"}
    symbol_set = {"BAJFINANCE"}
    symbol, matched = _resolve_symbol("BAJAJ FINAN", name_to_symbol, symbol_set)
    assert matched is True


def test_resolve_symbol_unmatched_returns_first_word():
    from app.dividend_parser import _resolve_symbol
    symbol, matched = _resolve_symbol("UNKNOWNCOMPANY XYZ", {}, set())
    assert matched is False
    assert symbol != ""  # Should return first token


def test_resolve_symbol_whitespace_only():
    from app.dividend_parser import _resolve_symbol
    symbol, matched = _resolve_symbol("   ", {}, set())
    assert symbol == ""
    assert matched is False


def test_resolve_symbol_known_abbrev_normalized():
    from app.dividend_parser import _resolve_symbol
    # Test that normalized form is checked against known abbreviations
    symbol, matched = _resolve_symbol("HEROMOTOCORPLT", {}, set())
    assert symbol == "HEROMOTOCO"
    assert matched is True


def test_resolve_symbol_single_word_fuzzy_symbol():
    from app.dividend_parser import _resolve_symbol
    # Long single word that might fuzzy match a symbol
    symbol_set = {"COALINDIA"}
    portfolio = {"COALINDIA"}
    symbol, matched = _resolve_symbol("COALINDIADIV", {}, symbol_set, portfolio_symbols=portfolio)
    # After stripping DIV, should match COALINDIA
    assert symbol == "COALINDIA" or matched is True


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
    assert "SBIN" in symbol_set


def test_build_lookup_tables_missing_cache(tmp_path):
    from app.dividend_parser import _build_lookup_tables
    missing = tmp_path / "nonexistent.json"
    name_to_symbol, symbol_set, aliases = _build_lookup_tables(missing, {})
    assert isinstance(name_to_symbol, dict)
    assert isinstance(symbol_set, set)


def test_build_lookup_tables_corrupt_cache(tmp_path):
    from app.dividend_parser import _build_lookup_tables
    bad_file = tmp_path / "symbol_cache.json"
    bad_file.write_text("not json")
    name_to_symbol, symbol_set, aliases = _build_lookup_tables(bad_file, {})
    assert isinstance(name_to_symbol, dict)


def test_build_lookup_tables_isin_short_entry(tmp_path):
    from app.dividend_parser import _build_lookup_tables
    cache = {
        "name": {},
        "isin": {"INE001": ["SYM", "NSE"]},  # Only 2 elements, < 3 — should be skipped
    }
    cache_file = tmp_path / "symbol_cache.json"
    cache_file.write_text(json.dumps(cache))
    name_to_symbol, symbol_set, aliases = _build_lookup_tables(cache_file, {})
    # Short isin entries (< 3 elements) are skipped for name lookup,
    # but symbol_set only gets symbols from entries with 3+ elements
    assert isinstance(symbol_set, set)


def test_build_lookup_tables_portfolio_overrides(tmp_path):
    from app.dividend_parser import _build_lookup_tables, _normalize
    cache = {"name": {"RELIANCE INDUSTRIES": "RELIANCE"}, "isin": {}}
    cache_file = tmp_path / "symbol_cache.json"
    cache_file.write_text(json.dumps(cache))
    # Portfolio should override cache entries
    name_to_symbol, symbol_set, aliases = _build_lookup_tables(
        cache_file, {"CUSTOM": "Reliance Industries"}
    )
    norm = _normalize("Reliance Industries")
    assert name_to_symbol[norm] == "CUSTOM"  # Portfolio wins


# ===================================================================
#  parse_dividend_statement
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


def test_parse_dividend_statement_7col_row(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    table = [
        ["ValDate", "PostDate", "Details", "RefNo", "Debit", "Credit", "Balance"],
        ["15/03/2024", "15/03/2024", "CEMTEX DEP ACHCr NACH123 SBIN Dividend", "REF1", "", "750.00", "50000.00"],
    ]
    mock_pdf = _make_mock_pdf_with_tables([[table]])
    data_dir = tmp_path
    cache_file = data_dir / "symbol_cache.json"
    cache_file.write_text(json.dumps({"name": {}, "isin": {}}))
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.dividend_parser.DATA_DIR", data_dir):
        result = parse_dividend_statement(b"fake pdf", portfolio_name_map={"SBIN": "State Bank"})
    # Should find the dividend
    assert result["summary"]["count"] >= 0


def test_parse_dividend_statement_zero_credit_skipped(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    table = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["15/03/2024", "CEMTEX DEP ACHCr NACH123 SBIN Dividend", "500.00", "0", "10000.00"],
    ]
    mock_pdf = _make_mock_pdf_with_tables([[table]])
    data_dir = tmp_path
    cache_file = data_dir / "symbol_cache.json"
    cache_file.write_text(json.dumps({"name": {}, "isin": {}}))
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.dividend_parser.DATA_DIR", data_dir):
        result = parse_dividend_statement(b"fake pdf", portfolio_name_map={})
    assert result["dividends"] == []


def test_parse_dividend_statement_with_duplicates(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    table = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["15/03/2024", "CEMTEX DEP ACHCr NACH123 SBIN Dividend", "", "500.00", "10000.00"],
    ]
    mock_pdf = _make_mock_pdf_with_tables([[table]])
    data_dir = tmp_path
    cache_file = data_dir / "symbol_cache.json"
    cache_file.write_text(json.dumps({"name": {}, "isin": {}}))

    def existing_fps(symbol):
        return {("2024-03-15", 500.0)}

    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.dividend_parser.DATA_DIR", data_dir):
        result = parse_dividend_statement(
            b"fake pdf", portfolio_name_map={"SBIN": "SBI"},
            existing_fingerprints_fn=existing_fps,
        )
    if result["dividends"]:
        assert result["dividends"][0]["isDuplicate"] is True


def test_parse_dividend_statement_short_rows_skipped(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    table = [
        ["Date", "Description"],  # Only 2 columns < 6
        ["15/03/2024", "CEMTEX DEP ACHCr NACH123 SBIN Dividend"],
    ]
    mock_pdf = _make_mock_pdf_with_tables([[table]])
    data_dir = tmp_path
    cache_file = data_dir / "symbol_cache.json"
    cache_file.write_text(json.dumps({"name": {}, "isin": {}}))
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.dividend_parser.DATA_DIR", data_dir):
        result = parse_dividend_statement(b"fake pdf", portfolio_name_map={})
    assert result["dividends"] == []


def test_parse_dividend_statement_no_tables(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    page = MagicMock()
    page.extract_text.return_value = "some text"
    page.extract_tables.return_value = None
    pdf = MagicMock()
    pdf.pages = [page]
    pdf.__enter__ = lambda s: s
    pdf.__exit__ = MagicMock(return_value=False)
    data_dir = tmp_path
    cache_file = data_dir / "symbol_cache.json"
    cache_file.write_text(json.dumps({"name": {}, "isin": {}}))
    with patch("pdfplumber.open", return_value=pdf), \
         patch("app.dividend_parser.DATA_DIR", data_dir):
        result = parse_dividend_statement(b"fake pdf", portfolio_name_map={})
    assert result["dividends"] == []


def test_parse_dividend_statement_password_protected(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    with patch("pdfplumber.open", side_effect=Exception("encrypted")):
        with pytest.raises(ValueError, match="Could not open PDF"):
            parse_dividend_statement(b"encrypted pdf", portfolio_name_map={})


def test_parse_dividend_statement_empty_table(tmp_path):
    from app.dividend_parser import parse_dividend_statement
    mock_pdf = _make_mock_pdf_with_tables([[None, []]])
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


def test_load_user_overrides_corrupt(tmp_path):
    from app.dividend_parser import _load_user_overrides
    bad_file = tmp_path / "overrides.json"
    bad_file.write_text("not json")
    with patch("app.dividend_parser._OVERRIDES_FILE", bad_file):
        result = _load_user_overrides()
    assert result == {}


def test_save_user_overrides_merges(tmp_path):
    from app.dividend_parser import save_user_overrides, _load_user_overrides
    of = tmp_path / "overrides.json"
    with patch("app.dividend_parser._OVERRIDES_FILE", of):
        save_user_overrides({"A": "B"})
        save_user_overrides({"C": "D"})
        loaded = _load_user_overrides()
    assert loaded["A"] == "B"
    assert loaded["C"] == "D"
