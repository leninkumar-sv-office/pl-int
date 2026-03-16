"""
Unit tests for app.xlsx_database — the stock XLSX portfolio engine.

Tests cover:
  - XlsxPortfolio construction and file creation
  - add_holding() — creates xlsx, correct sheets, correct data
  - Multiple buys of same stock → same xlsx file, total quantity correct
  - add_sell_transaction() — FIFO order (oldest lots sold first)
  - Partial sell → remaining quantity correct
  - Sell all → no remaining holdings
  - get_all_holdings() → returns list with correct fields
  - remove_holding() → removes holding
  - Empty portfolio → empty list
  - Dividend recording via add_dividend()
  - fifo_match() pure function
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def stocks_dir(tmp_path):
    """Create an empty Stocks directory with a parent for manual_prices.json."""
    d = tmp_path / "Stocks"
    d.mkdir(parents=True)
    # manual_prices.json lives in the parent of stocks_dir
    (tmp_path / "manual_prices.json").write_text(json.dumps({}))
    return d


@pytest.fixture
def portfolio(stocks_dir):
    """Create an XlsxPortfolio instance with all external deps mocked."""
    with patch("app.xlsx_database._sym_resolver") as mock_resolver, \
         patch("app.xlsx_database._sync_to_drive"):
        # ensure_loaded does nothing
        mock_resolver.ensure_loaded.return_value = None
        # resolve_by_name returns the name uppercased as the symbol
        mock_resolver.resolve_by_name.side_effect = lambda name: name.upper().replace(" ", "")
        mock_resolver.derive_symbol.side_effect = lambda name: name.upper().split()[0] if name else "UNKNOWN"

        from app.xlsx_database import XlsxPortfolio
        db = XlsxPortfolio(stocks_dir)
    return db


def _make_holding(symbol="RELIANCE", exchange="NSE", name="Reliance Industries",
                  quantity=10, buy_price=2500.0, buy_date="2025-01-15", notes=""):
    """Create a Holding model instance for testing."""
    from app.models import Holding
    return Holding(
        symbol=symbol,
        exchange=exchange,
        name=name,
        quantity=quantity,
        buy_price=buy_price,
        buy_date=buy_date,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Pure function: fifo_match
# ---------------------------------------------------------------------------

class TestFifoMatch:
    """Tests for the fifo_match() pure function."""

    def test_no_sells(self):
        from app.xlsx_database import fifo_match
        buys = [
            {"date": "2025-01-01", "quantity": 10, "price": 100.0},
            {"date": "2025-02-01", "quantity": 5, "price": 110.0},
        ]
        remaining, sold = fifo_match(buys, [])
        assert len(remaining) == 2
        assert remaining[0]["remaining"] == 10
        assert remaining[1]["remaining"] == 5
        assert sold == []

    def test_full_sell_fifo_order(self):
        from app.xlsx_database import fifo_match
        buys = [
            {"date": "2025-01-01", "quantity": 10, "price": 100.0},
            {"date": "2025-02-01", "quantity": 5, "price": 110.0},
        ]
        sells = [{"date": "2025-03-01", "quantity": 10, "price": 120.0}]
        remaining, sold = fifo_match(buys, sells)
        # Oldest lot (10 @ 100) fully consumed
        assert len(remaining) == 1
        assert remaining[0]["remaining"] == 5
        assert remaining[0]["price"] == 110.0
        # Sold position
        assert len(sold) == 1
        assert sold[0]["buy_price"] == 100.0
        assert sold[0]["sell_price"] == 120.0
        assert sold[0]["quantity"] == 10
        assert sold[0]["realized_pl"] == (120.0 - 100.0) * 10

    def test_partial_sell(self):
        from app.xlsx_database import fifo_match
        buys = [{"date": "2025-01-01", "quantity": 10, "price": 100.0}]
        sells = [{"date": "2025-03-01", "quantity": 3, "price": 120.0}]
        remaining, sold = fifo_match(buys, sells)
        assert len(remaining) == 1
        assert remaining[0]["remaining"] == 7
        assert len(sold) == 1
        assert sold[0]["quantity"] == 3

    def test_sell_spans_multiple_lots(self):
        from app.xlsx_database import fifo_match
        buys = [
            {"date": "2025-01-01", "quantity": 5, "price": 100.0},
            {"date": "2025-02-01", "quantity": 5, "price": 110.0},
        ]
        sells = [{"date": "2025-03-01", "quantity": 8, "price": 130.0}]
        remaining, sold = fifo_match(buys, sells)
        # First lot fully consumed (5), second lot partially consumed (3)
        assert len(remaining) == 1
        assert remaining[0]["remaining"] == 2
        assert remaining[0]["price"] == 110.0
        # Two sold positions: 5 from lot1, 3 from lot2
        assert len(sold) == 2
        assert sold[0]["quantity"] == 5
        assert sold[0]["buy_price"] == 100.0
        assert sold[1]["quantity"] == 3
        assert sold[1]["buy_price"] == 110.0

    def test_sell_all(self):
        from app.xlsx_database import fifo_match
        buys = [
            {"date": "2025-01-01", "quantity": 5, "price": 100.0},
            {"date": "2025-02-01", "quantity": 5, "price": 110.0},
        ]
        sells = [{"date": "2025-03-01", "quantity": 10, "price": 120.0}]
        remaining, sold = fifo_match(buys, sells)
        assert len(remaining) == 0
        assert len(sold) == 2

    def test_multiple_sells(self):
        from app.xlsx_database import fifo_match
        buys = [
            {"date": "2025-01-01", "quantity": 10, "price": 100.0},
        ]
        sells = [
            {"date": "2025-02-01", "quantity": 3, "price": 110.0},
            {"date": "2025-03-01", "quantity": 4, "price": 120.0},
        ]
        remaining, sold = fifo_match(buys, sells)
        assert len(remaining) == 1
        assert remaining[0]["remaining"] == 3
        assert len(sold) == 2


# ---------------------------------------------------------------------------
# XlsxPortfolio: Construction
# ---------------------------------------------------------------------------

class TestXlsxPortfolioConstruction:
    """Tests for XlsxPortfolio initialisation."""

    def test_empty_dir_creates_portfolio(self, portfolio, stocks_dir):
        assert portfolio.stocks_dir == stocks_dir
        assert portfolio.get_all_holdings() == []

    def test_dir_created_if_missing(self, tmp_path):
        new_dir = tmp_path / "nonexistent" / "Stocks"
        (tmp_path / "nonexistent" / "manual_prices.json").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "nonexistent" / "manual_prices.json").write_text(json.dumps({}))

        with patch("app.xlsx_database._sym_resolver") as mock_resolver, \
             patch("app.xlsx_database._sync_to_drive"):
            mock_resolver.ensure_loaded.return_value = None
            mock_resolver.resolve_by_name.return_value = None
            mock_resolver.derive_symbol.return_value = "UNKNOWN"
            from app.xlsx_database import XlsxPortfolio
            db = XlsxPortfolio(new_dir)
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# XlsxPortfolio: add_holding
# ---------------------------------------------------------------------------

class TestAddHolding:
    """Tests for XlsxPortfolio.add_holding()."""

    def test_add_holding_creates_xlsx(self, portfolio, stocks_dir):
        with patch("app.xlsx_database._sync_to_drive"):
            h = _make_holding()
            result = portfolio.add_holding(h)

        # File should exist
        xlsx_files = list(stocks_dir.glob("*.xlsx"))
        assert len(xlsx_files) == 1

        # Verify xlsx structure
        wb = openpyxl.load_workbook(xlsx_files[0])
        assert "Trading History" in wb.sheetnames
        assert "Index" in wb.sheetnames
        wb.close()

    def test_add_holding_returns_holding_with_correct_fields(self, portfolio):
        with patch("app.xlsx_database._sync_to_drive"):
            h = _make_holding(symbol="TCS", name="TCS Limited",
                              quantity=5, buy_price=3800.0, buy_date="2025-03-10")
            result = portfolio.add_holding(h)

        assert result.symbol == "TCS"
        assert result.quantity == 5
        assert result.buy_date == "2025-03-10"
        assert abs(result.buy_price - 3800.0) < 0.01

    def test_add_holding_appears_in_get_all(self, portfolio):
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="INFY", name="Infosys",
                              quantity=20, buy_price=1500.0, buy_date="2025-01-01")
            )
        holdings = portfolio.get_all_holdings()
        assert len(holdings) == 1
        assert holdings[0].symbol == "INFY"
        assert holdings[0].quantity == 20

    def test_multiple_buys_same_stock_same_file(self, portfolio, stocks_dir):
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="RELIANCE", name="Reliance Industries",
                              quantity=10, buy_price=2500.0, buy_date="2025-01-01")
            )
            portfolio.add_holding(
                _make_holding(symbol="RELIANCE", name="Reliance Industries",
                              quantity=5, buy_price=2600.0, buy_date="2025-02-01")
            )

        # Should still be one xlsx file
        xlsx_files = list(stocks_dir.glob("*.xlsx"))
        assert len(xlsx_files) == 1

        # Total qty = 15 across 2 lots
        holdings = portfolio.get_all_holdings()
        total_qty = sum(h.quantity for h in holdings)
        assert total_qty == 15
        assert len(holdings) == 2

    def test_add_holdings_different_stocks(self, portfolio, stocks_dir):
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="TCS", name="TCS Limited",
                              quantity=10, buy_price=3800.0, buy_date="2025-01-01")
            )
            portfolio.add_holding(
                _make_holding(symbol="INFY", name="Infosys",
                              quantity=20, buy_price=1500.0, buy_date="2025-01-01")
            )

        xlsx_files = list(stocks_dir.glob("*.xlsx"))
        assert len(xlsx_files) == 2

        holdings = portfolio.get_all_holdings()
        symbols = {h.symbol for h in holdings}
        assert symbols == {"TCS", "INFY"}


# ---------------------------------------------------------------------------
# XlsxPortfolio: Sell / FIFO
# ---------------------------------------------------------------------------

class TestSellTransaction:
    """Tests for XlsxPortfolio.add_sell_transaction() — FIFO matching."""

    def _setup_two_lots(self, portfolio):
        """Add two buy lots: 10 @ 100 (Jan), 5 @ 110 (Feb)."""
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="TEST", name="Test Company",
                              quantity=10, buy_price=100.0, buy_date="2025-01-01")
            )
            portfolio.add_holding(
                _make_holding(symbol="TEST", name="Test Company",
                              quantity=5, buy_price=110.0, buy_date="2025-02-01")
            )

    def test_partial_sell_oldest_first(self, portfolio):
        self._setup_two_lots(portfolio)
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_sell_transaction(
                symbol="TEST", exchange="NSE",
                quantity=7, price=120.0, sell_date="2025-03-01"
            )

        holdings = portfolio.get_all_holdings()
        total_qty = sum(h.quantity for h in holdings)
        # 15 - 7 = 8 remaining
        assert total_qty == 8

        # FIFO: first lot (10) reduced to 3, second lot (5) untouched
        qtys = sorted([h.quantity for h in holdings])
        assert qtys == [3, 5]

    def test_sell_entire_lot(self, portfolio):
        self._setup_two_lots(portfolio)
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_sell_transaction(
                symbol="TEST", exchange="NSE",
                quantity=10, price=120.0, sell_date="2025-03-01"
            )

        holdings = portfolio.get_all_holdings()
        # Only second lot (5 @ 110) remains
        assert len(holdings) == 1
        assert holdings[0].quantity == 5
        assert abs(holdings[0].buy_price - 110.0) < 0.01

    def test_sell_all_shares(self, portfolio):
        self._setup_two_lots(portfolio)
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_sell_transaction(
                symbol="TEST", exchange="NSE",
                quantity=15, price=120.0, sell_date="2025-03-01"
            )

        holdings = portfolio.get_all_holdings()
        test_holdings = [h for h in holdings if h.symbol == "TEST"]
        assert len(test_holdings) == 0

    def test_sell_creates_sold_positions(self, portfolio):
        self._setup_two_lots(portfolio)
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_sell_transaction(
                symbol="TEST", exchange="NSE",
                quantity=12, price=130.0, sell_date="2025-03-15"
            )

        sold = portfolio.get_all_sold()
        test_sold = [s for s in sold if s.symbol == "TEST"]
        assert len(test_sold) == 2
        # FIFO: 10 from first lot, 2 from second lot
        sold_qtys = sorted([s.quantity for s in test_sold])
        assert sold_qtys == [2, 10]

    def test_sell_more_than_held_raises(self, portfolio):
        self._setup_two_lots(portfolio)
        with patch("app.xlsx_database._sync_to_drive"):
            with pytest.raises(ValueError, match="Cannot sell"):
                portfolio.add_sell_transaction(
                    symbol="TEST", exchange="NSE",
                    quantity=20, price=120.0, sell_date="2025-03-01"
                )

    def test_sell_nonexistent_stock_raises(self, portfolio):
        with patch("app.xlsx_database._sync_to_drive"):
            with pytest.raises(FileNotFoundError):
                portfolio.add_sell_transaction(
                    symbol="NOSUCH", exchange="NSE",
                    quantity=1, price=100.0, sell_date="2025-03-01"
                )


# ---------------------------------------------------------------------------
# XlsxPortfolio: get_all_holdings
# ---------------------------------------------------------------------------

class TestGetAllHoldings:
    """Tests for XlsxPortfolio.get_all_holdings()."""

    def test_empty_portfolio(self, portfolio):
        assert portfolio.get_all_holdings() == []

    def test_returns_correct_holding_fields(self, portfolio):
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="HDFCBANK", name="HDFC Bank",
                              quantity=25, buy_price=1650.0, buy_date="2025-06-10")
            )
        holdings = portfolio.get_all_holdings()
        assert len(holdings) == 1
        h = holdings[0]
        assert h.symbol == "HDFCBANK"
        assert h.exchange == "NSE"
        assert h.name == "HDFC Bank"
        assert h.quantity == 25
        assert h.buy_date == "2025-06-10"
        assert h.id  # Should have a deterministic ID


# ---------------------------------------------------------------------------
# XlsxPortfolio: remove_holding
# ---------------------------------------------------------------------------

class TestRemoveHolding:
    """Tests for XlsxPortfolio.remove_holding()."""

    def test_remove_holding(self, portfolio):
        with patch("app.xlsx_database._sync_to_drive"):
            result = portfolio.add_holding(
                _make_holding(symbol="DEL", name="Delete Me",
                              quantity=10, buy_price=500.0, buy_date="2025-01-01")
            )
        holding_id = result.id

        # Pre-condition: holding exists
        holdings = portfolio.get_all_holdings()
        assert any(h.id == holding_id for h in holdings)

        with patch("app.xlsx_database._sync_to_drive"):
            success = portfolio.remove_holding(holding_id)
        assert success is True

        holdings = portfolio.get_all_holdings()
        assert not any(h.id == holding_id for h in holdings)

    def test_remove_nonexistent_holding(self, portfolio):
        result = portfolio.remove_holding("nonexistent")
        assert result is False


# ---------------------------------------------------------------------------
# XlsxPortfolio: Dividends
# ---------------------------------------------------------------------------

class TestDividends:
    """Tests for XlsxPortfolio.add_dividend() and dividend tracking."""

    def test_add_dividend(self, portfolio):
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="ITC", name="ITC Limited",
                              quantity=100, buy_price=450.0, buy_date="2025-01-01")
            )
            portfolio.add_dividend(
                symbol="ITC", exchange="NSE",
                amount=650.0, dividend_date="2025-06-15",
                remarks="Q1 Dividend"
            )

        dividends = portfolio.get_dividends_by_symbol()
        assert "ITC" in dividends
        assert dividends["ITC"]["amount"] == 650.0
        assert dividends["ITC"]["count"] == 1

    def test_dividend_no_file_raises(self, portfolio):
        with patch("app.xlsx_database._sync_to_drive"):
            with pytest.raises(FileNotFoundError):
                portfolio.add_dividend(
                    symbol="NOSUCH", exchange="NSE",
                    amount=100.0, dividend_date="2025-06-15"
                )

    def test_multiple_dividends(self, portfolio):
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="HDFCBANK", name="HDFC Bank",
                              quantity=50, buy_price=1600.0, buy_date="2025-01-01")
            )
            portfolio.add_dividend(
                symbol="HDFCBANK", exchange="NSE",
                amount=400.0, dividend_date="2025-03-15"
            )
            portfolio.add_dividend(
                symbol="HDFCBANK", exchange="NSE",
                amount=500.0, dividend_date="2025-09-15"
            )

        dividends = portfolio.get_dividends_by_symbol()
        assert "HDFCBANK" in dividends
        assert dividends["HDFCBANK"]["amount"] == 900.0
        assert dividends["HDFCBANK"]["count"] == 2


# ---------------------------------------------------------------------------
# XlsxPortfolio: File structure validation
# ---------------------------------------------------------------------------

class TestFileStructure:
    """Tests that created xlsx files have the correct internal structure."""

    def test_index_sheet_has_code(self, portfolio, stocks_dir):
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="SBIN", name="State Bank Of India",
                              quantity=10, buy_price=600.0, buy_date="2025-01-01")
            )

        xlsx_files = list(stocks_dir.glob("*.xlsx"))
        assert len(xlsx_files) == 1

        wb = openpyxl.load_workbook(xlsx_files[0], data_only=True)
        assert "Index" in wb.sheetnames
        ws_idx = wb["Index"]
        # Code should be like "NSE:SBIN"
        assert ws_idx.cell(1, 2).value == "Code"
        code_val = ws_idx.cell(1, 3).value
        assert "SBIN" in code_val
        wb.close()

    def test_trading_history_has_headers(self, portfolio, stocks_dir):
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="WIPRO", name="Wipro",
                              quantity=15, buy_price=480.0, buy_date="2025-01-01")
            )

        xlsx_files = list(stocks_dir.glob("*.xlsx"))
        wb = openpyxl.load_workbook(xlsx_files[0])
        ws = wb["Trading History"]
        # Header row is typically row 4
        vals = [ws.cell(4, c).value for c in range(1, 8)]
        assert "DATE" in vals
        assert "ACTION" in vals
        assert "QTY" in vals
        assert "PRICE" in vals
        wb.close()

    def test_buy_row_written_correctly(self, portfolio, stocks_dir):
        with patch("app.xlsx_database._sync_to_drive"):
            portfolio.add_holding(
                _make_holding(symbol="ZOMATO", name="Zomato",
                              quantity=100, buy_price=250.0, buy_date="2025-05-20")
            )

        xlsx_files = list(stocks_dir.glob("*.xlsx"))
        wb = openpyxl.load_workbook(xlsx_files[0], data_only=True)
        ws = wb["Trading History"]
        # Data row should be at row 5 (header at 4, data starts at 5)
        action = ws.cell(5, 3).value
        assert action == "Buy"
        qty = ws.cell(5, 4).value
        assert qty == 100
        price = ws.cell(5, 5).value
        assert abs(float(price) - 250.0) < 0.01
        wb.close()
