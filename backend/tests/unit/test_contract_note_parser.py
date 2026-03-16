"""
Unit tests for app/contract_note_parser.py

Tests contract note PDF parsing with mocked pdfplumber.
"""
import io
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════
#  Pure helper functions
# ═══════════════════════════════════════════════════════════

def test_extract_trade_date_valid():
    from app.contract_note_parser import _extract_trade_date
    text = "CONTRACT NOTE\nTRADE DATE 09-FEB-26\nSOME OTHER TEXT"
    result = _extract_trade_date(text)
    assert result == "2026-02-09"


def test_extract_trade_date_full_year():
    from app.contract_note_parser import _extract_trade_date
    text = "TRADE DATE 15-MAR-2025"
    result = _extract_trade_date(text)
    assert result == "2025-03-15"


def test_extract_trade_date_not_found():
    from app.contract_note_parser import _extract_trade_date
    text = "No date here"
    result = _extract_trade_date(text)
    assert result is None


def test_extract_contract_no():
    from app.contract_note_parser import _extract_contract_no
    text = "CONTRACT NOTE NO. 252611665409"
    result = _extract_contract_no(text)
    assert result == "252611665409"


def test_extract_contract_no_not_found():
    from app.contract_note_parser import _extract_contract_no
    assert _extract_contract_no("no contract here") is None


def test_extract_exchange_map_bse():
    """ISINs under BSEM section are mapped to BSE."""
    from app.contract_note_parser import _extract_exchange_map
    text = "BSEM\nINE123456789 SOME COMPANY\nNSEM\nINE987654321 OTHER CO"
    result = _extract_exchange_map(text)
    assert result.get("INE123456789") == "BSE"
    assert "INE987654321" not in result  # NSE is default, not stored


def test_extract_exchange_map_empty():
    from app.contract_note_parser import _extract_exchange_map
    result = _extract_exchange_map("no exchange sections here")
    assert result == {}


# ═══════════════════════════════════════════════════════════
#  _build_transaction
# ═══════════════════════════════════════════════════════════

def test_build_transaction_buy():
    from app.contract_note_parser import _build_transaction
    t = _build_transaction(
        action="Buy", symbol="RELIANCE", exchange="NSE",
        company_name="Reliance Industries", isin="INE002A01018",
        quantity=10, avg_rate=2500.0, net_after=25050.0,
        brokerage=25.0, gst=4.5, stt=5.0, other_levies=2.5,
        trade_date="2026-02-09"
    )
    assert t["action"] == "Buy"
    assert t["symbol"] == "RELIANCE"
    assert t["quantity"] == 10
    assert t["effective_price"] == pytest.approx(25050.0 / 10, abs=0.01)
    assert t["stt"] == pytest.approx(5.0)
    assert t["trade_date"] == "2026-02-09"


def test_build_transaction_sell():
    from app.contract_note_parser import _build_transaction
    t = _build_transaction(
        action="Sell", symbol="TCS", exchange="NSE",
        company_name="TCS", isin="INE467B01029",
        quantity=5, avg_rate=3600.0, net_after=-18000.0,
        brokerage=18.0, gst=3.24, stt=4.5, other_levies=1.5,
        trade_date="2026-02-09"
    )
    assert t["action"] == "Sell"
    assert t["effective_price"] == pytest.approx(18000.0 / 5, abs=0.01)
    assert t["net_total_after_levies"] == pytest.approx(18000.0, abs=0.01)


def test_build_transaction_add_charges():
    from app.contract_note_parser import _build_transaction
    t = _build_transaction(
        action="Buy", symbol="WIPRO", exchange="NSE",
        company_name="Wipro", isin="INE075A01022",
        quantity=20, avg_rate=450.0, net_after=9100.0,
        brokerage=10.0, gst=1.8, stt=2.0, other_levies=1.0,
        trade_date="2026-02-10"
    )
    # add_charges = brokerage + gst + other_levies
    assert t["add_charges"] == pytest.approx(10.0 + 1.8 + 1.0, abs=0.01)


# ═══════════════════════════════════════════════════════════
#  _resolve_symbol
# ═══════════════════════════════════════════════════════════

def test_resolve_symbol_via_isin():
    from app.contract_note_parser import _resolve_symbol
    with patch("app.contract_note_parser._sym_resolver") as mock_sr:
        mock_sr.resolve_by_isin.return_value = ("RELIANCE", "NSE", "Reliance Industries")
        mock_sr.resolve_by_name.return_value = None
        sym, exch, name = _resolve_symbol("INE002A01018", "RELIANCE INDUSTRIES LTD", {})
    assert sym == "RELIANCE"
    assert exch == "NSE"


def test_resolve_symbol_via_name():
    from app.contract_note_parser import _resolve_symbol
    with patch("app.contract_note_parser._sym_resolver") as mock_sr:
        mock_sr.resolve_by_isin.return_value = None
        mock_sr.resolve_by_name.return_value = "TCS"
        sym, exch, name = _resolve_symbol("INE467B01029", "TCS LIMITED", {})
    assert sym == "TCS"


def test_resolve_symbol_fallback_derive():
    from app.contract_note_parser import _resolve_symbol
    with patch("app.contract_note_parser._sym_resolver") as mock_sr:
        mock_sr.resolve_by_isin.return_value = None
        mock_sr.resolve_by_name.return_value = None
        mock_sr.derive_symbol.return_value = "UNKNOWN"
        sym, exch, name = _resolve_symbol("INE999Z99ZZZ", "Unknown Company Ltd", {})
    assert sym == "UNKNOWN"


def test_resolve_symbol_exchange_from_map():
    """Exchange map overrides the default from isin lookup."""
    from app.contract_note_parser import _resolve_symbol
    with patch("app.contract_note_parser._sym_resolver") as mock_sr:
        mock_sr.resolve_by_isin.return_value = ("RELIANCE", "NSE", "Reliance Industries")
        sym, exch, name = _resolve_symbol(
            "INE002A01018", "RELIANCE", {"INE002A01018": "BSE"}
        )
    assert exch == "BSE"


# ═══════════════════════════════════════════════════════════
#  parse_contract_note — mocked pdfplumber + file system
# ═══════════════════════════════════════════════════════════

def _make_mock_pdf_text(text):
    page = MagicMock()
    page.extract_text.return_value = text
    page.extract_tables.return_value = []
    pdf = MagicMock()
    pdf.pages = [page]
    pdf.__enter__ = lambda s: s
    pdf.__exit__ = MagicMock(return_value=False)
    return pdf


def test_parse_contract_note_no_trade_date(tmp_path):
    """Raises ValueError if no trade date found in PDF."""
    from app.contract_note_parser import parse_contract_note
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake")
    with patch("app.contract_note_parser.extract_text_from_pdf", return_value="no date here"), \
         patch("app.contract_note_parser._sym_resolver"):
        with pytest.raises(ValueError, match="trade date"):
            parse_contract_note(str(pdf_file))


def test_parse_contract_note_empty_transactions(tmp_path):
    """Returns empty transactions list when no valid data found."""
    from app.contract_note_parser import parse_contract_note
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake")
    text_with_date = "TRADE DATE 09-FEB-26\nCONTRACT NOTE NO. 123456"
    with patch("app.contract_note_parser.extract_text_from_pdf", return_value=text_with_date), \
         patch("app.contract_note_parser._parse_pdfplumber_tables", return_value=[]), \
         patch("app.contract_note_parser._parse_text_section", return_value=[]), \
         patch("app.contract_note_parser._sym_resolver"):
        result = parse_contract_note(str(pdf_file))
    assert result["trade_date"] == "2026-02-09"
    assert result["transactions"] == []
    assert result["summary"]["total"] == 0


def test_parse_contract_note_buy_sell_counts(tmp_path):
    """Summary counts buys and sells correctly."""
    from app.contract_note_parser import parse_contract_note
    pdf_file = tmp_path / "cn.pdf"
    pdf_file.write_bytes(b"fake")
    mock_txns = [
        {"action": "Buy", "symbol": "RELIANCE", "isin": "INE001", "quantity": 10,
         "wap": 2500.0, "stt": 5.0, "gst": 2.0},
        {"action": "Buy", "symbol": "TCS", "isin": "INE002", "quantity": 5,
         "wap": 3600.0, "stt": 3.0, "gst": 1.5},
        {"action": "Sell", "symbol": "INFY", "isin": "INE003", "quantity": 8,
         "wap": 1800.0, "stt": 4.0, "gst": 2.0},
    ]
    text_with_date = "TRADE DATE 09-FEB-26\nCONTRACT NOTE NO. 999"
    with patch("app.contract_note_parser.extract_text_from_pdf", return_value=text_with_date), \
         patch("app.contract_note_parser._parse_pdfplumber_tables", return_value=mock_txns), \
         patch("app.contract_note_parser._parse_obligation_details", return_value={}), \
         patch("app.contract_note_parser._sym_resolver"):
        result = parse_contract_note(str(pdf_file))
    assert result["summary"]["buys"] == 2
    assert result["summary"]["sells"] == 1
    assert result["summary"]["total"] == 3


def test_parse_contract_note_deduplicates_transactions(tmp_path):
    """Duplicate transactions (same ISIN+action+qty+wap) are removed."""
    from app.contract_note_parser import parse_contract_note
    pdf_file = tmp_path / "dup.pdf"
    pdf_file.write_bytes(b"fake")
    dup_tx = {"action": "Buy", "symbol": "RELIANCE", "isin": "INE001",
              "quantity": 10, "wap": 2500.0, "stt": 0, "gst": 0}
    mock_txns = [dup_tx, dup_tx]  # duplicate
    text_with_date = "TRADE DATE 09-FEB-26"
    with patch("app.contract_note_parser.extract_text_from_pdf", return_value=text_with_date), \
         patch("app.contract_note_parser._parse_pdfplumber_tables", return_value=mock_txns), \
         patch("app.contract_note_parser._parse_obligation_details", return_value={}), \
         patch("app.contract_note_parser._sym_resolver"):
        result = parse_contract_note(str(pdf_file))
    assert len(result["transactions"]) == 1


# ═══════════════════════════════════════════════════════════
#  _parse_nums_from_row
# ═══════════════════════════════════════════════════════════

def test_parse_nums_from_row_buy():
    from app.contract_note_parser import _parse_nums_from_row
    transactions = []
    numbers = ["10", "0", "2500.0", "25000.0", "25.0", "25025.0", "4.5", "5.0", "2.5", "25057.0"]
    with patch("app.contract_note_parser._resolve_symbol",
               return_value=("RELIANCE", "NSE", "Reliance Industries")):
        result = _parse_nums_from_row(
            numbers, "RELIANCE INDUSTRIES", "INE002A01018", {}, "2026-02-09", transactions
        )
    assert result is True
    assert len(transactions) == 1
    assert transactions[0]["action"] == "Buy"
    assert transactions[0]["quantity"] == 10


def test_parse_nums_from_row_both_buy_sell():
    from app.contract_note_parser import _parse_nums_from_row
    transactions = []
    # bought 5, sold 3
    numbers = ["5", "3", "1800.0", "9000.0", "18.0", "8982.0", "3.24", "2.0", "1.0", "5400.0"]
    with patch("app.contract_note_parser._resolve_symbol",
               return_value=("INFY", "NSE", "Infosys")):
        _parse_nums_from_row(
            numbers, "INFOSYS", "INE009A01021", {}, "2026-02-09", transactions
        )
    assert len(transactions) == 2


def test_parse_nums_from_row_invalid():
    from app.contract_note_parser import _parse_nums_from_row
    transactions = []
    numbers = ["not", "a", "number"]  # too short and invalid
    result = _parse_nums_from_row(
        numbers, "COMPANY", "INE001", {}, "2026-02-09", transactions
    )
    assert result is False
