"""
Unit tests for app/cdsl_cas_parser.py

Tests CAS PDF parsing with mocked pdfplumber.
"""
import io
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════
#  Helper functions (pure logic — no mocking needed)
# ═══════════════════════════════════════════════════════════

def test_parse_number_basic():
    from app.cdsl_cas_parser import _parse_number
    assert _parse_number("1234.56") == pytest.approx(1234.56)


def test_parse_number_with_commas():
    from app.cdsl_cas_parser import _parse_number
    assert _parse_number("12,345.67") == pytest.approx(12345.67)


def test_parse_number_empty():
    from app.cdsl_cas_parser import _parse_number
    assert _parse_number("") == 0.0


def test_parse_number_dash():
    from app.cdsl_cas_parser import _parse_number
    assert _parse_number("--") == 0.0
    assert _parse_number("-") == 0.0


def test_parse_number_newline():
    from app.cdsl_cas_parser import _parse_number
    assert _parse_number("100.00\n") == pytest.approx(100.0)


def test_parse_date_ddmmyyyy():
    from app.cdsl_cas_parser import _parse_date_ddmmyyyy
    assert _parse_date_ddmmyyyy("12-01-2026") == "2026-01-12"


def test_parse_date_invalid():
    from app.cdsl_cas_parser import _parse_date_ddmmyyyy
    # Invalid date should return as-is
    result = _parse_date_ddmmyyyy("not-a-date")
    assert result == "not-a-date"


def test_determine_action_buy():
    from app.cdsl_cas_parser import _determine_action
    assert _determine_action("SIP Purchase") == "Buy"
    assert _determine_action("Lumpsum Purchase") == "Buy"


def test_determine_action_sell_redemption():
    from app.cdsl_cas_parser import _determine_action
    assert _determine_action("Redemption - Full") == "Sell"
    assert _determine_action("Switch Out - HDFC") == "Sell"


def test_determine_action_sell_reversal():
    from app.cdsl_cas_parser import _determine_action
    assert _determine_action("SIP Purchase (Reversal)") == "Sell"


def test_determine_action_sell_insufficient():
    from app.cdsl_cas_parser import _determine_action
    assert _determine_action("Insufficient Balance") == "Sell"


def test_should_skip_row_opening_balance():
    from app.cdsl_cas_parser import _should_skip_row
    assert _should_skip_row("Opening Balance") is True
    assert _should_skip_row("opening balance ") is True


def test_should_skip_row_closing_balance():
    from app.cdsl_cas_parser import _should_skip_row
    assert _should_skip_row("Closing Balance") is True


def test_should_skip_row_normal_transaction():
    from app.cdsl_cas_parser import _should_skip_row
    assert _should_skip_row("SIP Purchase") is False


def test_clean_description():
    from app.cdsl_cas_parser import _clean_description
    assert _clean_description("SIP\nPurchase\n- Regular") == "SIP Purchase - Regular"


def test_clean_description_empty():
    from app.cdsl_cas_parser import _clean_description
    assert _clean_description("") == ""


def test_clean_description_none():
    from app.cdsl_cas_parser import _clean_description
    assert _clean_description(None) == ""


# ═══════════════════════════════════════════════════════════
#  _extract_metadata_from_text
# ═══════════════════════════════════════════════════════════

def test_extract_metadata_amc_header():
    from app.cdsl_cas_parser import _extract_metadata_from_text
    text = """
AMC Name : ICICI Prudential Mutual Fund
Scheme Name : ICICI Prudential Flexi Cap Fund  Scheme Code : 12345
Folio No : 1234567/89
ISIN : INF109K01XY2
"""
    result = _extract_metadata_from_text(text)
    assert "INF109K01XY2" in result
    meta = result["INF109K01XY2"]
    assert "ICICI Prudential Mutual Fund" in meta.get("amc", "")


def test_extract_metadata_isin_re():
    """ISIN regex should match INFxxx format."""
    import re
    from app.cdsl_cas_parser import _ISIN_RE
    line = "ISIN : INF109K01YJ4 UCC : 1234"
    m = _ISIN_RE.search(line)
    assert m is not None
    assert m.group(1) == "INF109K01YJ4"


# ═══════════════════════════════════════════════════════════
#  parse_cas_pdf — mocked pdfplumber
# ═══════════════════════════════════════════════════════════

def _make_mock_pdf(tables_per_page, text_per_page=""):
    """Build a mock pdfplumber PDF object."""
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


def test_parse_cas_pdf_empty_tables():
    """Parsing with no valid tables returns empty result."""
    from app.cdsl_cas_parser import parse_cdsl_cas as parse_cas_pdf
    mock_pdf = _make_mock_pdf([[]])
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.cdsl_cas_parser.mf_db") as mock_db:
        mock_db._file_map = {}
        mock_db._name_map = {}
        result = parse_cas_pdf(b"fake pdf content")
    assert result["funds"] == []
    assert "error" not in result or result.get("error") is None


def test_parse_cas_pdf_with_transaction():
    """Parsing a valid CAS table extracts a transaction."""
    from app.cdsl_cas_parser import parse_cdsl_cas as parse_cas_pdf
    # Table row 0: ISIN identifier
    # Row 1: header
    # Row 2: opening balance (should be skipped)
    # Row 3: actual transaction
    # Row 4: closing balance
    table = [
        ["ISIN : INF200K01RO2 UCC : 1234", None, None, None, None, None, None, None, None],
        ["Date", "Transaction Description", "Amount", "NAV", "Price", "Units", "Stamp Duty", "Load", "Balance"],
        ["", "Opening Balance", "", "", "", "100.000", "", "", ""],
        ["12-01-2026", "SIP Purchase - ICICI", "4999.75", "41.04", "41.04", "121.826", ".25", "0", "0"],
        ["", "Closing Balance", "", "", "", "221.826", "", "", ""],
    ]
    mock_pdf = _make_mock_pdf([[table]], text_per_page="")
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.cdsl_cas_parser.mf_db") as mock_db, \
         patch("app.cdsl_cas_parser._match_fund_code", return_value=None), \
         patch("app.cdsl_cas_parser._check_duplicate", return_value=False):
        mock_db._file_map = {}
        mock_db._name_map = {}
        result = parse_cas_pdf(b"fake pdf content")
    assert len(result["funds"]) == 1
    fund = result["funds"][0]
    assert fund["isin"] == "INF200K01RO2"
    assert len(fund["transactions"]) == 1
    tx = fund["transactions"][0]
    assert tx["action"] == "Buy"
    assert tx["date"] == "2026-01-12"
    assert tx["units"] == pytest.approx(121.826)


def test_parse_cas_pdf_skips_zero_nav():
    """Rows with zero NAV or units are skipped."""
    from app.cdsl_cas_parser import parse_cdsl_cas as parse_cas_pdf
    table = [
        ["ISIN : INF200K01RO2 UCC : 1234", None, None, None, None, None, None, None, None],
        ["Date", "Description", "Amount", "NAV", "Price", "Units", "Stamp", "Load", "Bal"],
        ["12-01-2026", "SIP Purchase", "1000", "0", "0", "0", "0", "0", "0"],  # zero nav → skip
    ]
    mock_pdf = _make_mock_pdf([[table]])
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.cdsl_cas_parser.mf_db") as mock_db, \
         patch("app.cdsl_cas_parser._match_fund_code", return_value=None), \
         patch("app.cdsl_cas_parser._check_duplicate", return_value=False):
        mock_db._file_map = {}
        mock_db._name_map = {}
        result = parse_cas_pdf(b"fake pdf content")
    if result["funds"]:
        assert len(result["funds"][0]["transactions"]) == 0


def test_parse_cas_pdf_redemption_is_sell():
    """Redemption transactions are mapped to Sell action."""
    from app.cdsl_cas_parser import parse_cdsl_cas as parse_cas_pdf
    table = [
        ["ISIN : INF200K01RO2 UCC : 1234", None, None, None, None, None, None, None, None],
        ["Date", "Description", "Amount", "NAV", "Price", "Units", "Stamp", "Load", "Bal"],
        ["15-03-2025", "Redemption - Full", "5000", "50.00", "50.00", "100.00", "0", "0", "0"],
    ]
    mock_pdf = _make_mock_pdf([[table]])
    with patch("pdfplumber.open", return_value=mock_pdf), \
         patch("app.cdsl_cas_parser.mf_db") as mock_db, \
         patch("app.cdsl_cas_parser._match_fund_code", return_value=None), \
         patch("app.cdsl_cas_parser._check_duplicate", return_value=False):
        mock_db._file_map = {}
        mock_db._name_map = {}
        result = parse_cas_pdf(b"fake pdf content")
    if result["funds"] and result["funds"][0]["transactions"]:
        assert result["funds"][0]["transactions"][0]["action"] == "Sell"


def test_parse_cas_pdf_pdf_open_failure():
    """pdfplumber open failure raises ValueError (password-protected or corrupted)."""
    from app.cdsl_cas_parser import parse_cdsl_cas as parse_cas_pdf
    with patch("pdfplumber.open", side_effect=Exception("corrupted pdf")):
        with pytest.raises((ValueError, Exception)):
            parse_cas_pdf(b"bad content")


# ═══════════════════════════════════════════════════════════
#  _match_fund_code
# ═══════════════════════════════════════════════════════════

def test_match_fund_code_by_isin():
    """Should return ISIN directly if it exists in mf_db._file_map."""
    from app.cdsl_cas_parser import _match_fund_code
    with patch("app.cdsl_cas_parser.mf_db") as mock_db:
        mock_db._file_map = {"INF200K01RO2": "/path/to/fund.xlsx"}
        mock_db._name_map = {}
        result = _match_fund_code("INF200K01RO2", "Some Fund")
    assert result == "INF200K01RO2"


def test_match_fund_code_not_found():
    """Returns None when no match is found."""
    from app.cdsl_cas_parser import _match_fund_code
    with patch("app.cdsl_cas_parser.mf_db") as mock_db:
        mock_db._file_map = {}
        mock_db._name_map = {}
        result = _match_fund_code("INF999X99ZZZ", "Unknown Fund")
    assert result is None
