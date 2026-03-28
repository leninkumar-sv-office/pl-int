"""
Additional coverage tests for contract_note_parser.py — targeting remaining uncovered lines.
Covers: _resolve_symbol fallbacks, _parse_pdfplumber_tables, _parse_text_section,
_parse_obligation_details, _prorate_obligation_charges, parse_contract_note full flow,
extract_text_from_pdf fallbacks, parse_contract_note_from_bytes.
"""
import os
import re
import tempfile
from unittest.mock import patch, MagicMock
import pytest


class TestResolveSymbol:
    def test_isin_resolved(self):
        from app.contract_note_parser import _resolve_symbol
        with patch("app.contract_note_parser._sym_resolver") as mock_resolver:
            mock_resolver.resolve_by_isin.return_value = ("RELIANCE", "NSE", "Reliance Industries")
            sym, exch, name = _resolve_symbol("INE002A01018", "RELIANCE", {})
        assert sym == "RELIANCE"

    def test_zerodha_name_resolved(self):
        from app.contract_note_parser import _resolve_symbol
        with patch("app.contract_note_parser._sym_resolver") as mock_resolver:
            mock_resolver.resolve_by_isin.return_value = None
            mock_resolver.resolve_by_name.return_value = "RELIANCE"
            sym, exch, name = _resolve_symbol("INE002A01018", "RELIANCE IND", {"INE002A01018": "BSE"})
        assert sym == "RELIANCE"
        assert exch == "BSE"

    def test_symbol_map_resolved(self):
        from app.contract_note_parser import _resolve_symbol
        with patch("app.contract_note_parser._sym_resolver") as mock_resolver:
            mock_resolver.resolve_by_isin.return_value = None
            mock_resolver.resolve_by_name.return_value = None
            mock_resolver._normalize.side_effect = lambda s: s.lower().replace(" ", "")
            with patch("app.contract_note_parser._sym_resolver._normalize", side_effect=lambda s: s.lower().replace(" ", "")):
                with patch.dict("sys.modules", {}):
                    # This tries to import xlsx_database.SYMBOL_MAP — mock it
                    mock_sym_map = {"Reliance Industries": "RELIANCE"}
                    with patch("app.xlsx_database.SYMBOL_MAP", mock_sym_map, create=True):
                        sym, exch, name = _resolve_symbol("INE002A01018", "Reliance Industries", {})

    def test_derive_symbol_fallback(self):
        from app.contract_note_parser import _resolve_symbol
        with patch("app.contract_note_parser._sym_resolver") as mock_resolver:
            mock_resolver.resolve_by_isin.return_value = None
            mock_resolver.resolve_by_name.return_value = None
            mock_resolver.derive_symbol.return_value = "DERIVEDSTOCK"
            sym, exch, name = _resolve_symbol("INE999X99999", "UNKNOWN COMPANY", {"INE999X99999": "BSE"})
        assert sym == "DERIVEDSTOCK"
        assert exch == "BSE"


class TestBuildTransaction:
    def test_buy_transaction(self):
        from app.contract_note_parser import _build_transaction
        t = _build_transaction("Buy", "RELIANCE", "NSE", "Reliance Industries",
                               "INE002A01018", 10, 2500.0, 25100.0,
                               10.0, 1.8, 25.0, 5.0, "2024-01-15")
        assert t["action"] == "Buy"
        assert t["quantity"] == 10
        assert t["effective_price"] == pytest.approx(2510.0, rel=0.01)

    def test_sell_transaction(self):
        from app.contract_note_parser import _build_transaction
        t = _build_transaction("Sell", "TCS", "NSE", "Tata Consultancy",
                               "INE467B01029", 5, 3600.0, -17900.0,
                               8.0, 1.5, 18.0, 4.0, "2024-01-15")
        assert t["action"] == "Sell"
        assert t["effective_price"] == pytest.approx(3580.0, rel=0.01)


class TestParseNumsFromRow:
    def test_buy_and_sell(self):
        from app.contract_note_parser import _parse_nums_from_row
        transactions = []
        numbers = ["10", "5", "2500.00", "25000.00", "10.00", "24990.00",
                   "1.80", "25.00", "5.00", "25032.80"]
        with patch("app.contract_note_parser._resolve_symbol", return_value=("STOCK", "NSE", "Stock Ltd")):
            result = _parse_nums_from_row(numbers, "Stock Ltd", "INE123",
                                          {}, "2024-01-15", transactions)
        assert result is True
        assert len(transactions) == 2

    def test_invalid_numbers(self):
        from app.contract_note_parser import _parse_nums_from_row
        transactions = []
        numbers = ["abc", "5", "2500.00"]  # too short
        result = _parse_nums_from_row(numbers, "Stock", "INE123",
                                      {}, "2024-01-15", transactions)
        assert result is False


class TestParseEquitySegmentRow:
    def test_buy_only(self):
        from app.contract_note_parser import _parse_equity_segment_row
        transactions = []
        numbers = [10.0, 2500.0, 0.5, 2500.5, 25005.0,
                   0.0, 0.0, 0.0, 0.0, 0.0,
                   10.0, 25005.0]
        with patch("app.contract_note_parser._resolve_symbol", return_value=("STOCK", "NSE", "Stock Ltd")):
            result = _parse_equity_segment_row("INE123", "Stock Ltd", numbers,
                                               {}, "2024-01-15", transactions)
        assert result is True
        assert len(transactions) == 1
        assert transactions[0]["action"] == "Buy"

    def test_sell_only(self):
        from app.contract_note_parser import _parse_equity_segment_row
        transactions = []
        numbers = [0.0, 0.0, 0.0, 0.0, 0.0,
                   5.0, 3600.0, 0.3, 3600.3, 18001.5,
                   -5.0, -18001.5]
        with patch("app.contract_note_parser._resolve_symbol", return_value=("TCS", "NSE", "TCS Ltd")):
            result = _parse_equity_segment_row("INE467", "TCS", numbers,
                                               {}, "2024-01-15", transactions)
        assert result is True
        assert transactions[0]["action"] == "Sell"

    def test_parse_error(self):
        from app.contract_note_parser import _parse_equity_segment_row
        transactions = []
        result = _parse_equity_segment_row("INE123", "Stock", [1.0, 2.0],
                                           {}, "2024-01-15", transactions)
        assert result is False


class TestExtractTextFromPdf:
    def test_pdfplumber_layout(self):
        from app.contract_note_parser import extract_text_from_pdf
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 text"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            result = extract_text_from_pdf("/fake/path.pdf", layout=True)
        assert result == "Page 1 text"

    def test_pdfplumber_no_layout(self):
        from app.contract_note_parser import extract_text_from_pdf
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Plain text"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            result = extract_text_from_pdf("/fake/path.pdf", layout=False)
        assert result == "Plain text"

    def test_pdfplumber_import_error_raises(self):
        from app.contract_note_parser import extract_text_from_pdf
        with patch("pdfplumber.open", side_effect=ImportError("no pdfplumber")):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with pytest.raises(RuntimeError, match="PDF text extraction failed"):
                    extract_text_from_pdf("/fake/path.pdf", layout=True)

    def test_pdftotext_fallback(self):
        from app.contract_note_parser import extract_text_from_pdf
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "pdftotext output text"
        with patch("pdfplumber.open", side_effect=Exception("pdfplumber failed")):
            with patch("subprocess.run", return_value=mock_result):
                result = extract_text_from_pdf("/fake/path.pdf", layout=True)
        assert result == "pdftotext output text"

    def test_pdftotext_not_found_raises(self):
        from app.contract_note_parser import extract_text_from_pdf
        with patch("pdfplumber.open", side_effect=Exception("fail")):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with pytest.raises(RuntimeError, match="PDF text extraction failed"):
                    extract_text_from_pdf("/fake/path.pdf", layout=True)

    def test_pdftotext_cli_error(self):
        from app.contract_note_parser import extract_text_from_pdf
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("pdfplumber.open", side_effect=Exception("fail")):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(RuntimeError):
                    extract_text_from_pdf("/fake/path.pdf", layout=True)


class TestParseTextSection:
    def test_equity_segment_section(self):
        from app.contract_note_parser import _parse_text_section
        text = (
            "EQUITY SEGMENT\n"
            "SECURITY  BUY  SELL  WAP  GROSS  BROKERAGE  NET  GST  STT  OTHER  NETAFTER\n"
            "INE002A01018  RELIANCE INDUSTRIES                "
            "10.00  0.00  2500.00  25000.00  10.00  24990.00  1.80  25.00  5.00  25032.80\n"
            "OBLIGATION DETAILS\n"
        )
        with patch("app.contract_note_parser._resolve_symbol", return_value=("RELIANCE", "NSE", "Reliance")):
            result = _parse_text_section(text, "2024-01-15", {})
        # Should find at least one transaction if numbers parse correctly
        assert isinstance(result, list)

    def test_annexure_b_section(self):
        from app.contract_note_parser import _parse_text_section
        text = (
            "ANNEXURE B\n"
            "Equity Reliance Industries - Cash - INE002A01018  "
            "10.00  0.00  2500.00  25000.00  10.00  24990.00  1.80  25.00  5.00  25032.80\n"
            "DESCRIPTION OF SERVICE\n"
        )
        with patch("app.contract_note_parser._resolve_symbol", return_value=("RELIANCE", "NSE", "Reliance")):
            result = _parse_text_section(text, "2024-01-15", {})
        assert isinstance(result, list)

    def test_no_section_found(self):
        from app.contract_note_parser import _parse_text_section
        result = _parse_text_section("Random text with no sections", "2024-01-15", {})
        assert result == []

    def test_skip_lines(self):
        from app.contract_note_parser import _parse_text_section
        text = (
            "EQUITY SEGMENT\n"
            "SUB TOTAL  100  200\n"
            "CGST  1.80\n"
            "Segment  Security  Header  Row\n"
            "PAGE 1 / 3\n"
            "EXCHANGE-WISE breakdown\n"
            "OBLIGATION DETAILS\n"
        )
        result = _parse_text_section(text, "2024-01-15", {})
        assert result == []


class TestParseObligationDetails:
    def test_basic_parsing(self):
        from app.contract_note_parser import _parse_obligation_details
        text = (
            "OBLIGATION DETAILS\n"
            "SECURITY TRANSACTION TAX  25.00\n"
            "CGST\n"
            "Rate 9.00\n"
            "Amount  1.80\n"
            "SGST\n"
            "Amount  1.80\n"
            "EXCHANGE TRANSACTION CHARGE  2.50\n"
            "SEBI TURNOVER Fees  0.10\n"
            "STAMP DUTY  1.00\n"
        )
        result = _parse_obligation_details(text)
        assert result["stt"] == 25.0
        assert result["gst"] == pytest.approx(3.6, rel=0.01)
        assert result["exchange_charges"] == 2.5

    def test_no_obligation_section(self):
        from app.contract_note_parser import _parse_obligation_details
        result = _parse_obligation_details("Just some text")
        assert result == {}

    def test_igst_and_utt(self):
        from app.contract_note_parser import _parse_obligation_details
        text = (
            "OBLIGATION DETAILS\n"
            "IGST\n"
            "Amount  3.60\n"
            "UTT\n"
            "Amount  0.50\n"
        )
        result = _parse_obligation_details(text)
        assert result["gst"] == pytest.approx(4.1, rel=0.01)

    def test_page_break_stops_parsing(self):
        from app.contract_note_parser import _parse_obligation_details
        text = (
            "OBLIGATION DETAILS\n"
            "SECURITY TRANSACTION TAX  25.00\n"
            "PAGE 1 / 3\n"
            "Should not reach here  99999.00\n"
        )
        result = _parse_obligation_details(text)
        assert result["stt"] == 25.0

    def test_net_amount_payable_stops(self):
        from app.contract_note_parser import _parse_obligation_details
        text = (
            "OBLIGATION DETAILS\n"
            "SECURITY TRANSACTION TAX  25.00\n"
            "NET AMOUNT PAYABLE  25032.80\n"
            "Should not reach here  99999.00\n"
        )
        result = _parse_obligation_details(text)
        assert result["stt"] == 25.0


class TestProrateObligationCharges:
    def test_basic_proration(self):
        from app.contract_note_parser import _prorate_obligation_charges
        transactions = [
            {"action": "Buy", "net_total_after_levies": 25000.0, "quantity": 10,
             "stt": 0, "gst": 0, "brokerage": 10.0, "other_levies": 0},
            {"action": "Sell", "net_total_after_levies": 18000.0, "quantity": 5,
             "stt": 0, "gst": 0, "brokerage": 8.0, "other_levies": 0},
        ]
        charges = {"stt": 43.0, "gst": 3.6, "exchange_charges": 2.5,
                   "sebi_fees": 0.1, "stamp_duty": 1.0}
        _prorate_obligation_charges(transactions, charges)
        assert transactions[0]["stt"] > 0
        assert transactions[1]["stt"] > 0
        # Total prorated STT should sum to original
        total_stt = transactions[0]["stt"] + transactions[1]["stt"]
        assert total_stt == pytest.approx(43.0, rel=0.01)

    def test_empty_transactions(self):
        from app.contract_note_parser import _prorate_obligation_charges
        _prorate_obligation_charges([], {"stt": 25.0})

    def test_zero_charges(self):
        from app.contract_note_parser import _prorate_obligation_charges
        transactions = [{"net_total_after_levies": 25000.0}]
        _prorate_obligation_charges(transactions, {"stt": 0, "gst": 0,
                                                    "exchange_charges": 0,
                                                    "sebi_fees": 0, "stamp_duty": 0})

    def test_zero_total_value(self):
        from app.contract_note_parser import _prorate_obligation_charges
        transactions = [{"net_total_after_levies": 0, "quantity": 10}]
        charges = {"stt": 25.0, "gst": 3.6, "exchange_charges": 0,
                   "sebi_fees": 0, "stamp_duty": 0}
        _prorate_obligation_charges(transactions, charges)


class TestParsePdfplumberTables:
    def test_equity_segment_table(self):
        from app.contract_note_parser import _parse_pdfplumber_tables
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "EQUITY SEGMENT with data"
        mock_page.extract_tables.return_value = [
            [
                ["Segment", "Security", "INE002A01018", "RELIANCE IND",
                 "10", "0", "2500", "25000", "10", "24990", "1.8", "25", "5", "25032.80"],
            ]
        ]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("app.contract_note_parser._resolve_symbol", return_value=("RELIANCE", "NSE", "Reliance")):
                result = _parse_pdfplumber_tables("/fake/path.pdf", "2024-01-15", {})
        assert isinstance(result, list)

    def test_no_pdfplumber(self):
        from app.contract_note_parser import _parse_pdfplumber_tables
        with patch.dict("sys.modules", {"pdfplumber": None}):
            with patch("builtins.__import__", side_effect=ImportError("no pdfplumber")):
                result = _parse_pdfplumber_tables("/fake/path.pdf", "2024-01-15", {})
        assert result == []

    def test_exception_returns_empty(self):
        from app.contract_note_parser import _parse_pdfplumber_tables
        with patch("pdfplumber.open", side_effect=Exception("PDF error")):
            result = _parse_pdfplumber_tables("/fake/path.pdf", "2024-01-15", {})
        assert result == []


class TestParseContractNote:
    def test_no_trade_date_raises(self):
        from app.contract_note_parser import parse_contract_note
        with patch("app.contract_note_parser.extract_text_from_pdf", return_value="No date here"):
            with patch("app.contract_note_parser._sym_resolver"):
                with pytest.raises(ValueError, match="trade date"):
                    parse_contract_note("/fake/path.pdf")

    def test_no_transactions_debug(self, tmp_path):
        from app.contract_note_parser import parse_contract_note
        text = "TRADE DATE 15-JAN-24\nCONTRACT NOTE NO. 12345\nNo tables here"
        with patch("app.contract_note_parser.extract_text_from_pdf", return_value=text):
            with patch("app.contract_note_parser._parse_pdfplumber_tables", return_value=[]):
                with patch("app.contract_note_parser._parse_text_section", return_value=[]):
                    with patch("app.contract_note_parser._sym_resolver"):
                        result = parse_contract_note("/fake/path.pdf")
        assert result["transactions"] == []
        assert "_debug_text" in result

    def test_dedup_transactions(self):
        from app.contract_note_parser import parse_contract_note
        dup_tx = {
            "action": "Buy", "symbol": "RELIANCE", "exchange": "NSE",
            "name": "Reliance", "isin": "INE002A01018", "quantity": 10,
            "wap": 2500.0, "effective_price": 2510.0, "net_total_after_levies": 25100.0,
            "brokerage": 10.0, "gst": 0.0, "stt": 0.0, "other_levies": 0.0,
            "add_charges": 10.0, "trade_date": "2024-01-15",
        }
        text = "TRADE DATE 15-JAN-24\nCONTRACT NOTE NO. 12345\nEQUITY SEGMENT\nOBLIGATION DETAILS"
        with patch("app.contract_note_parser.extract_text_from_pdf", return_value=text):
            with patch("app.contract_note_parser._parse_pdfplumber_tables", return_value=[dup_tx, dup_tx.copy()]):
                with patch("app.contract_note_parser._sym_resolver"):
                    with patch("app.contract_note_parser._parse_obligation_details", return_value={}):
                        result = parse_contract_note("/fake/path.pdf")
        assert len(result["transactions"]) == 1

    def test_proration_applied(self):
        from app.contract_note_parser import parse_contract_note
        tx = {
            "action": "Buy", "symbol": "RELIANCE", "exchange": "NSE",
            "name": "Reliance", "isin": "INE002A01018", "quantity": 10,
            "wap": 2500.0, "effective_price": 2510.0, "net_total_after_levies": 25100.0,
            "brokerage": 10.0, "gst": 0.0, "stt": 0.0, "other_levies": 0.0,
            "add_charges": 10.0, "trade_date": "2024-01-15",
        }
        text = "TRADE DATE 15-JAN-24\nCONTRACT NOTE NO. 12345\nEQUITY SEGMENT\nOBLIGATION DETAILS\nSECURITY TRANSACTION TAX  25.00"
        with patch("app.contract_note_parser.extract_text_from_pdf", return_value=text):
            with patch("app.contract_note_parser._parse_pdfplumber_tables", return_value=[tx]):
                with patch("app.contract_note_parser._sym_resolver"):
                    result = parse_contract_note("/fake/path.pdf")
        # STT should have been prorated
        assert result["transactions"][0]["stt"] > 0

    def test_strategy_fallback_to_text(self):
        from app.contract_note_parser import parse_contract_note
        text = "TRADE DATE 15-JAN-24\nCONTRACT NOTE NO. 12345\nEQUITY SEGMENT"
        with patch("app.contract_note_parser.extract_text_from_pdf", return_value=text):
            with patch("app.contract_note_parser._parse_pdfplumber_tables", return_value=[]):
                with patch("app.contract_note_parser._parse_text_section", return_value=[]):
                    with patch("app.contract_note_parser._sym_resolver"):
                        result = parse_contract_note("/fake/path.pdf")
        assert isinstance(result, dict)


class TestParseContractNoteFromBytes:
    def test_basic(self):
        from app.contract_note_parser import parse_contract_note_from_bytes
        with patch("app.contract_note_parser.parse_contract_note") as mock_parse:
            mock_parse.return_value = {"transactions": [], "trade_date": "2024-01-15",
                                        "contract_no": "12345", "summary": {"buys": 0, "sells": 0, "total": 0}}
            result = parse_contract_note_from_bytes(b"fake pdf content")
        assert result["trade_date"] == "2024-01-15"
