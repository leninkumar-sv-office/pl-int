"""
Additional unit tests for app/contract_note_parser.py — targeting uncovered lines.
Covers: _build_transaction, _parse_nums_from_row, _parse_equity_segment_row,
extract_text_from_pdf, _parse_text_section, _parse_obligation_details,
_prorate_obligation_charges, parse_contract_note, parse_contract_note_from_bytes.
"""
import os
import tempfile
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


# ═══════════════════════════════════════════════════════════
#  _build_transaction
# ═══════════════════════════════════════════════════════════

class TestBuildTransaction:
    def test_buy(self):
        from app.contract_note_parser import _build_transaction
        tx = _build_transaction(
            action="Buy", symbol="RELIANCE", exchange="NSE",
            company_name="Reliance Industries", isin="INE002A01018",
            quantity=10, avg_rate=2500.0, net_after=25100.0,
            brokerage=50.0, gst=9.0, stt=25.0, other_levies=16.0,
            trade_date="2024-01-15",
        )
        assert tx["action"] == "Buy"
        assert tx["quantity"] == 10
        assert tx["effective_price"] == pytest.approx(2510.0, rel=1e-2)
        assert tx["net_total_after_levies"] == 25100.0
        assert tx["add_charges"] == pytest.approx(75.0, rel=1e-2)

    def test_sell(self):
        from app.contract_note_parser import _build_transaction
        tx = _build_transaction(
            action="Sell", symbol="TCS", exchange="NSE",
            company_name="TCS Limited", isin="INE467B01029",
            quantity=5, avg_rate=3500.0, net_after=-17400.0,
            brokerage=30.0, gst=5.4, stt=17.0, other_levies=10.0,
            trade_date="2024-06-01",
        )
        assert tx["action"] == "Sell"
        assert tx["net_total_after_levies"] == 17400.0
        assert tx["effective_price"] == pytest.approx(3480.0, rel=1e-2)


# ═══════════════════════════════════════════════════════════
#  _parse_nums_from_row
# ═══════════════════════════════════════════════════════════

class TestParseNumsFromRow:
    def test_buy_transaction(self):
        from app.contract_note_parser import _parse_nums_from_row
        numbers = ["10", "0", "500.50", "5005.00", "25.00", "5030.00",
                    "4.50", "5.00", "2.00", "5041.50"]
        transactions = []
        with patch("app.contract_note_parser._resolve_symbol", return_value=("TEST", "NSE", "Test Co")):
            result = _parse_nums_from_row(
                numbers, "Test Security", "INE123A01234",
                {}, "2024-01-15", transactions,
            )
        assert result is True
        assert len(transactions) == 1
        assert transactions[0]["action"] == "Buy"

    def test_sell_transaction(self):
        from app.contract_note_parser import _parse_nums_from_row
        numbers = ["0", "5", "1000.00", "5000.00", "25.00", "4975.00",
                    "4.50", "5.00", "2.00", "-4943.50"]
        transactions = []
        with patch("app.contract_note_parser._resolve_symbol", return_value=("SELL", "NSE", "Sell Co")):
            result = _parse_nums_from_row(
                numbers, "Sell Security", "INE999A01234",
                {}, "2024-01-15", transactions,
            )
        assert result is True
        assert len(transactions) == 1
        assert transactions[0]["action"] == "Sell"

    def test_bad_numbers(self):
        from app.contract_note_parser import _parse_nums_from_row
        numbers = ["bad", "0", "not_a_number"]
        transactions = []
        result = _parse_nums_from_row(
            numbers, "Bad", "INE000", {}, "2024-01-15", transactions,
        )
        assert result is False

    def test_insufficient_numbers(self):
        from app.contract_note_parser import _parse_nums_from_row
        numbers = ["10", "0", "500"]
        transactions = []
        result = _parse_nums_from_row(
            numbers, "Short", "INE000", {}, "2024-01-15", transactions,
        )
        assert result is False


# ═══════════════════════════════════════════════════════════
#  _parse_equity_segment_row
# ═══════════════════════════════════════════════════════════

class TestParseEquitySegmentRow:
    def test_buy(self):
        from app.contract_note_parser import _parse_equity_segment_row
        numbers = [10.0, 500.0, 2.5, 502.5, 5025.0,
                   0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 5025.0]
        transactions = []
        with patch("app.contract_note_parser._resolve_symbol", return_value=("BUY", "NSE", "Buy Co")):
            result = _parse_equity_segment_row(
                "INE123", "Buy Security", numbers,
                {}, "2024-01-15", transactions,
            )
        assert result is True
        assert len(transactions) == 1
        assert transactions[0]["action"] == "Buy"

    def test_sell(self):
        from app.contract_note_parser import _parse_equity_segment_row
        numbers = [0.0, 0.0, 0.0, 0.0, 0.0,
                   5.0, 1000.0, 3.0, 997.0, 4985.0, -5.0, -4985.0]
        transactions = []
        with patch("app.contract_note_parser._resolve_symbol", return_value=("SELL", "NSE", "Sell Co")):
            result = _parse_equity_segment_row(
                "INE456", "Sell Security", numbers,
                {}, "2024-06-01", transactions,
            )
        assert result is True
        assert len(transactions) == 1
        assert transactions[0]["action"] == "Sell"

    def test_bad_numbers(self):
        from app.contract_note_parser import _parse_equity_segment_row
        transactions = []
        result = _parse_equity_segment_row(
            "INE000", "Bad", [1.0, 2.0],  # insufficient
            {}, "2024-01-15", transactions,
        )
        assert result is False


# ═══════════════════════════════════════════════════════════
#  _extract_exchange_map
# ═══════════════════════════════════════════════════════════

class TestExtractExchangeMap:
    def test_bse_section(self):
        from app.contract_note_parser import _extract_exchange_map
        text = "NSEM\nSome line\nBSEM\nINE002A01018 RELIANCE\nNSEM\nINE467B01029 TCS"
        result = _extract_exchange_map(text)
        assert result.get("INE002A01018") == "BSE"
        assert "INE467B01029" not in result  # NSE is default, not stored

    def test_no_bse(self):
        from app.contract_note_parser import _extract_exchange_map
        text = "NSEM\nINE002A01018 RELIANCE\nINE467B01029 TCS"
        result = _extract_exchange_map(text)
        assert result == {}


# ═══════════════════════════════════════════════════════════
#  _parse_obligation_details
# ═══════════════════════════════════════════════════════════

class TestParseObligationDetails:
    def test_full_details(self):
        from app.contract_note_parser import _parse_obligation_details
        text = """
Some header
OBLIGATION DETAILS
SECURITY TRANSACTION TAX               25.00
CGST
Rate 9.00
Amount                                  4.50
SGST
Rate 9.00
Amount                                  4.50
EXCHANGE TRANSACTION CHARGES            12.00
SEBI TURNOVER FEE                       0.50
STAMP DUTY                              3.00
NET AMOUNT PAYABLE
"""
        result = _parse_obligation_details(text)
        assert result["stt"] == 25.0
        assert result["gst"] == pytest.approx(9.0, rel=0.1)
        assert result["exchange_charges"] == 12.0
        assert result["sebi_fees"] == 0.5
        assert result["stamp_duty"] == 3.0

    def test_no_obligation_section(self):
        from app.contract_note_parser import _parse_obligation_details
        result = _parse_obligation_details("No relevant section here at all")
        assert result == {}


# ═══════════════════════════════════════════════════════════
#  _prorate_obligation_charges
# ═══════════════════════════════════════════════════════════

class TestProrateObligationCharges:
    def test_single_transaction(self):
        from app.contract_note_parser import _prorate_obligation_charges
        transactions = [
            {"action": "Buy", "quantity": 10, "net_total_after_levies": 10000.0,
             "brokerage": 50.0, "stt": 0, "gst": 0, "other_levies": 0,
             "effective_price": 1000.0, "add_charges": 50.0},
        ]
        charges = {"stt": 10.0, "gst": 9.0, "exchange_charges": 5.0,
                   "sebi_fees": 0.5, "stamp_duty": 1.0}
        _prorate_obligation_charges(transactions, charges)
        assert transactions[0]["stt"] == 10.0
        assert transactions[0]["gst"] == 9.0
        assert transactions[0]["net_total_after_levies"] > 10000.0  # charges added

    def test_empty_transactions(self):
        from app.contract_note_parser import _prorate_obligation_charges
        _prorate_obligation_charges([], {"stt": 10.0})  # no error

    def test_zero_charges(self):
        from app.contract_note_parser import _prorate_obligation_charges
        transactions = [{"action": "Buy", "quantity": 10, "net_total_after_levies": 10000.0}]
        _prorate_obligation_charges(transactions, {"stt": 0, "gst": 0, "exchange_charges": 0, "sebi_fees": 0, "stamp_duty": 0})
        # Nothing should change


# ═══════════════════════════════════════════════════════════
#  _parse_text_section
# ═══════════════════════════════════════════════════════════

class TestParseTextSection:
    def test_equity_segment(self):
        from app.contract_note_parser import _parse_text_section
        text = """
EQUITY SEGMENT :
ISIN         Security Description    BoughtQty SoldQty AvgRate ...
INE002A01018  RELIANCE INDUSTRIES    10.00  0.00  2500.50  25005.00  50.00  25055.00  9.00  25.00  16.00  25105.00  0.00  0.00
OBLIGATION DETAILS
"""
        with patch("app.contract_note_parser._resolve_symbol", return_value=("RELIANCE", "NSE", "Reliance Industries")):
            result = _parse_text_section(text, "2024-01-15", {})
        assert len(result) >= 1

    def test_annexure_b(self):
        from app.contract_note_parser import _parse_text_section
        text = """
ANNEXURE B
Equity Company Name - Cash - INE002A01018    10  0  500.50  5005  25.00  5030  4.50  5.00  2.00  5041.50
DESCRIPTION OF SERVICE
"""
        with patch("app.contract_note_parser._resolve_symbol", return_value=("TEST", "NSE", "Test Co")):
            result = _parse_text_section(text, "2024-01-15", {})
        assert len(result) >= 1

    def test_no_section_found(self):
        from app.contract_note_parser import _parse_text_section
        result = _parse_text_section("No relevant content here", "2024-01-15", {})
        assert result == []


# ═══════════════════════════════════════════════════════════
#  extract_text_from_pdf
# ═══════════════════════════════════════════════════════════

class TestExtractTextFromPdf:
    def test_pdfplumber_success(self, tmp_path):
        from app.contract_note_parser import extract_text_from_pdf
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page content here"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            result = extract_text_from_pdf(str(tmp_path / "test.pdf"), layout=True)
            assert "Page content" in result

    def test_pdfplumber_failure_falls_back(self, tmp_path):
        from app.contract_note_parser import extract_text_from_pdf
        # pdfplumber fails, pdftotext not available
        with patch("pdfplumber.open", side_effect=Exception("open error")):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with pytest.raises(RuntimeError, match="PDF text extraction failed"):
                    extract_text_from_pdf(str(tmp_path / "test.pdf"), layout=True)


# ═══════════════════════════════════════════════════════════
#  parse_contract_note_from_bytes
# ═══════════════════════════════════════════════════════════

class TestParseContractNoteFromBytes:
    def test_success(self):
        from app.contract_note_parser import parse_contract_note_from_bytes
        mock_result = {
            "trade_date": "2024-01-15",
            "contract_no": "12345",
            "transactions": [],
            "summary": {"buys": 0, "sells": 0, "total": 0},
        }
        with patch("app.contract_note_parser.parse_contract_note", return_value=mock_result):
            result = parse_contract_note_from_bytes(b"fake pdf bytes")
        assert result["trade_date"] == "2024-01-15"

    def test_cleanup(self):
        from app.contract_note_parser import parse_contract_note_from_bytes
        with patch("app.contract_note_parser.parse_contract_note", side_effect=ValueError("bad pdf")):
            with pytest.raises(ValueError):
                parse_contract_note_from_bytes(b"fake pdf bytes")


# ═══════════════════════════════════════════════════════════
#  _resolve_symbol
# ═══════════════════════════════════════════════════════════

class TestResolveSymbol:
    def test_isin_resolution(self):
        from app.contract_note_parser import _resolve_symbol
        with patch("app.contract_note_parser._sym_resolver.resolve_by_isin",
                   return_value=("RELIANCE", "NSE", "Reliance Industries")):
            sym, exch, name = _resolve_symbol("INE002A01018", "Reliance", {})
            assert sym == "RELIANCE"
            assert exch == "NSE"

    def test_zerodha_name_fallback(self):
        from app.contract_note_parser import _resolve_symbol
        with patch("app.contract_note_parser._sym_resolver.resolve_by_isin", return_value=None):
            with patch("app.contract_note_parser._sym_resolver.resolve_by_name", return_value="HDFC"):
                sym, exch, name = _resolve_symbol("INE999A01234", "HDFC Bank", {})
                assert sym == "HDFC"

    def test_derive_fallback(self):
        from app.contract_note_parser import _resolve_symbol
        with patch("app.contract_note_parser._sym_resolver.resolve_by_isin", return_value=None):
            with patch("app.contract_note_parser._sym_resolver.resolve_by_name", return_value=None):
                with patch("app.contract_note_parser._sym_resolver.derive_symbol", return_value="UNKNOWN"):
                    sym, exch, name = _resolve_symbol("INE000X01234", "Unknown Company", {})
                    assert sym == "UNKNOWN"
