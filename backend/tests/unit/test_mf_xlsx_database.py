"""
Unit tests for app.mf_xlsx_database — the mutual fund XLSX portfolio engine.

Tests cover:
  - MFXlsxPortfolio construction and file creation
  - add_mf_holding() — creates xlsx, records buy
  - Multiple buys same fund → accumulated units
  - add_mf_sell_transaction() — FIFO matching for fractional units
  - Partial redeem → remaining units correct
  - get_all_holdings() → returns fund list with correct fields
  - Empty portfolio → empty list
  - fifo_match_mf() pure function with fractional units
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
def mf_dir(tmp_path):
    """Create an empty Mutual Funds directory."""
    d = tmp_path / "Mutual Funds"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def mf_portfolio(mf_dir):
    """Create an MFXlsxPortfolio with external deps mocked."""
    with patch("app.mf_xlsx_database._sync_to_drive"):
        from app.mf_xlsx_database import MFXlsxPortfolio
        db = MFXlsxPortfolio(mf_dir)
    return db


# ---------------------------------------------------------------------------
# Pure function: fifo_match_mf (fractional units)
# ---------------------------------------------------------------------------

class TestFifoMatchMF:
    """Tests for the fifo_match_mf() pure function with fractional units."""

    def test_no_sells(self):
        from app.mf_xlsx_database import fifo_match_mf
        buys = [
            {"date": "2025-01-01", "units": 10.5, "nav": 50.0},
            {"date": "2025-02-01", "units": 5.25, "nav": 55.0},
        ]
        remaining, sold = fifo_match_mf(buys, [])
        assert len(remaining) == 2
        assert abs(remaining[0]["remaining"] - 10.5) < 0.001
        assert abs(remaining[1]["remaining"] - 5.25) < 0.001
        assert sold == []

    def test_full_sell_fifo_order(self):
        from app.mf_xlsx_database import fifo_match_mf
        buys = [
            {"date": "2025-01-01", "units": 10.0, "nav": 50.0},
            {"date": "2025-02-01", "units": 5.0, "nav": 55.0},
        ]
        sells = [{"date": "2025-03-01", "units": 10.0, "nav": 60.0}]
        remaining, sold = fifo_match_mf(buys, sells)
        # Oldest lot fully consumed
        assert len(remaining) == 1
        assert abs(remaining[0]["remaining"] - 5.0) < 0.001
        assert remaining[0]["nav"] == 55.0
        assert len(sold) == 1
        assert sold[0]["buy_nav"] == 50.0
        assert sold[0]["sell_nav"] == 60.0
        assert abs(sold[0]["units"] - 10.0) < 0.001
        assert abs(sold[0]["realized_pl"] - (60.0 - 50.0) * 10.0) < 0.01

    def test_fractional_sell(self):
        from app.mf_xlsx_database import fifo_match_mf
        buys = [{"date": "2025-01-01", "units": 10.5678, "nav": 100.0}]
        sells = [{"date": "2025-03-01", "units": 3.2345, "nav": 110.0}]
        remaining, sold = fifo_match_mf(buys, sells)
        assert len(remaining) == 1
        assert abs(remaining[0]["remaining"] - (10.5678 - 3.2345)) < 0.001
        assert len(sold) == 1
        assert abs(sold[0]["units"] - 3.2345) < 0.001

    def test_sell_spans_multiple_lots(self):
        from app.mf_xlsx_database import fifo_match_mf
        buys = [
            {"date": "2025-01-01", "units": 5.5, "nav": 100.0},
            {"date": "2025-02-01", "units": 4.5, "nav": 110.0},
        ]
        sells = [{"date": "2025-03-01", "units": 8.0, "nav": 120.0}]
        remaining, sold = fifo_match_mf(buys, sells)
        # 5.5 from first, 2.5 from second
        assert len(remaining) == 1
        assert abs(remaining[0]["remaining"] - 2.0) < 0.001
        assert len(sold) == 2
        assert abs(sold[0]["units"] - 5.5) < 0.001
        assert abs(sold[1]["units"] - 2.5) < 0.001

    def test_sell_all(self):
        from app.mf_xlsx_database import fifo_match_mf
        buys = [
            {"date": "2025-01-01", "units": 5.0, "nav": 100.0},
            {"date": "2025-02-01", "units": 5.0, "nav": 110.0},
        ]
        sells = [{"date": "2025-03-01", "units": 10.0, "nav": 120.0}]
        remaining, sold = fifo_match_mf(buys, sells)
        assert len(remaining) == 0
        assert len(sold) == 2

    def test_multiple_sells(self):
        from app.mf_xlsx_database import fifo_match_mf
        buys = [{"date": "2025-01-01", "units": 100.0, "nav": 50.0}]
        sells = [
            {"date": "2025-02-01", "units": 30.5, "nav": 55.0},
            {"date": "2025-03-01", "units": 20.25, "nav": 60.0},
        ]
        remaining, sold = fifo_match_mf(buys, sells)
        assert len(remaining) == 1
        assert abs(remaining[0]["remaining"] - 49.25) < 0.001
        assert len(sold) == 2

    def test_tiny_remainder_filtered(self):
        """Lots with < 0.0001 units remaining should be filtered out."""
        from app.mf_xlsx_database import fifo_match_mf
        buys = [{"date": "2025-01-01", "units": 10.0, "nav": 100.0}]
        sells = [{"date": "2025-03-01", "units": 9.9999, "nav": 110.0}]
        remaining, sold = fifo_match_mf(buys, sells)
        # 0.0001 remaining should be filtered out
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# MFXlsxPortfolio: Construction
# ---------------------------------------------------------------------------

class TestMFPortfolioConstruction:
    """Tests for MFXlsxPortfolio initialisation."""

    def test_empty_dir(self, mf_portfolio):
        assert mf_portfolio.get_all_holdings() == []

    def test_dir_created_if_missing(self, tmp_path):
        new_dir = tmp_path / "nonexistent" / "Mutual Funds"
        with patch("app.mf_xlsx_database._sync_to_drive"):
            from app.mf_xlsx_database import MFXlsxPortfolio
            db = MFXlsxPortfolio(new_dir)
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# MFXlsxPortfolio: add_mf_holding
# ---------------------------------------------------------------------------

class TestAddMFHolding:
    """Tests for MFXlsxPortfolio.add_mf_holding()."""

    def test_add_creates_xlsx(self, mf_portfolio, mf_dir):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=50.1234,
                nav=120.50,
                buy_date="2025-01-15",
            )

        xlsx_files = list(mf_dir.glob("*.xlsx"))
        assert len(xlsx_files) == 1

        wb = openpyxl.load_workbook(xlsx_files[0])
        assert "Trading History" in wb.sheetnames
        assert "Index" in wb.sheetnames
        wb.close()

    def test_add_returns_correct_info(self, mf_portfolio):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            result = mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=50.1234,
                nav=120.50,
                buy_date="2025-01-15",
            )

        assert result["fund_code"] == "INF200K01RJ1"
        assert abs(result["units"] - 50.1234) < 0.0001
        assert abs(result["nav"] - 120.50) < 0.01
        assert abs(result["cost"] - round(50.1234 * 120.50, 2)) < 0.01

    def test_add_appears_in_get_all(self, mf_portfolio):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=50.0,
                nav=120.0,
                buy_date="2025-01-15",
            )

        holdings = mf_portfolio.get_all_holdings()
        assert len(holdings) == 1
        assert holdings[0].fund_code == "INF200K01RJ1"
        assert abs(holdings[0].units - 50.0) < 0.001

    def test_multiple_buys_same_fund(self, mf_portfolio, mf_dir):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=50.0,
                nav=120.0,
                buy_date="2025-01-15",
                skip_dup_check=True,
            )
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=30.5,
                nav=125.0,
                buy_date="2025-02-15",
                skip_dup_check=True,
            )

        # Same file
        xlsx_files = list(mf_dir.glob("*.xlsx"))
        assert len(xlsx_files) == 1

        # Two separate lots
        holdings = mf_portfolio.get_all_holdings()
        assert len(holdings) == 2
        total_units = sum(h.units for h in holdings)
        assert abs(total_units - 80.5) < 0.001

    def test_duplicate_detection(self, mf_portfolio):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=50.0,
                nav=120.0,
                buy_date="2025-01-15",
            )
            with pytest.raises(ValueError, match="Duplicate"):
                mf_portfolio.add_mf_holding(
                    fund_code="INF200K01RJ1",
                    fund_name="SBI Small Cap Fund",
                    units=50.0,
                    nav=120.0,
                    buy_date="2025-01-15",
                )

    def test_skip_dup_check(self, mf_portfolio):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=50.0,
                nav=120.0,
                buy_date="2025-01-15",
            )
            # Should not raise with skip_dup_check=True
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=50.0,
                nav=120.0,
                buy_date="2025-01-15",
                skip_dup_check=True,
            )
        holdings = mf_portfolio.get_all_holdings()
        assert len(holdings) == 2

    def test_add_different_funds(self, mf_portfolio, mf_dir):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=50.0,
                nav=120.0,
                buy_date="2025-01-15",
            )
            mf_portfolio.add_mf_holding(
                fund_code="INF846K01DP8",
                fund_name="Axis Bluechip Fund",
                units=100.0,
                nav=45.0,
                buy_date="2025-01-15",
            )

        xlsx_files = list(mf_dir.glob("*.xlsx"))
        assert len(xlsx_files) == 2


# ---------------------------------------------------------------------------
# MFXlsxPortfolio: Redeem / FIFO sell
# ---------------------------------------------------------------------------

class TestMFRedeem:
    """Tests for MFXlsxPortfolio.add_mf_sell_transaction() — FIFO redeem."""

    def _setup_two_lots(self, mf_portfolio):
        """Add two buy lots: 50 @ 100 (Jan), 30 @ 110 (Feb)."""
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="Test Fund",
                units=50.0,
                nav=100.0,
                buy_date="2025-01-01",
                skip_dup_check=True,
            )
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="Test Fund",
                units=30.0,
                nav=110.0,
                buy_date="2025-02-01",
                skip_dup_check=True,
            )

    def test_partial_redeem(self, mf_portfolio):
        self._setup_two_lots(mf_portfolio)
        with patch("app.mf_xlsx_database._sync_to_drive"):
            result = mf_portfolio.add_mf_sell_transaction(
                fund_code="INF200K01RJ1",
                units=20.0,
                nav=120.0,
                sell_date="2025-03-01",
            )

        assert abs(result["remaining_units"] - 60.0) < 0.01
        holdings = mf_portfolio.get_all_holdings()
        total = sum(h.units for h in holdings)
        assert abs(total - 60.0) < 0.01

    def test_redeem_fifo_oldest_first(self, mf_portfolio):
        self._setup_two_lots(mf_portfolio)
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_sell_transaction(
                fund_code="INF200K01RJ1",
                units=50.0,
                nav=120.0,
                sell_date="2025-03-01",
            )

        # Oldest lot (50 @ 100) fully consumed; second lot (30 @ 110) untouched
        holdings = mf_portfolio.get_all_holdings()
        assert len(holdings) == 1
        assert abs(holdings[0].units - 30.0) < 0.001
        assert abs(holdings[0].nav - 110.0) < 0.01

    def test_redeem_spans_lots(self, mf_portfolio):
        self._setup_two_lots(mf_portfolio)
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_sell_transaction(
                fund_code="INF200K01RJ1",
                units=60.0,
                nav=120.0,
                sell_date="2025-03-01",
            )

        holdings = mf_portfolio.get_all_holdings()
        total = sum(h.units for h in holdings)
        # 80 - 60 = 20 remaining from second lot
        assert abs(total - 20.0) < 0.01

    def test_redeem_all(self, mf_portfolio):
        self._setup_two_lots(mf_portfolio)
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_sell_transaction(
                fund_code="INF200K01RJ1",
                units=80.0,
                nav=120.0,
                sell_date="2025-03-01",
            )

        holdings = mf_portfolio.get_all_holdings()
        fund_holdings = [h for h in holdings if h.fund_code == "INF200K01RJ1"]
        assert len(fund_holdings) == 0

    def test_redeem_creates_sold_positions(self, mf_portfolio):
        self._setup_two_lots(mf_portfolio)
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_sell_transaction(
                fund_code="INF200K01RJ1",
                units=60.0,
                nav=120.0,
                sell_date="2025-03-01",
            )

        sold = mf_portfolio.get_all_sold()
        assert len(sold) == 2
        # FIFO: 50 from lot1, 10 from lot2
        sold_units = sorted([s.units for s in sold])
        assert abs(sold_units[0] - 10.0) < 0.001
        assert abs(sold_units[1] - 50.0) < 0.001

    def test_redeem_more_than_held_raises(self, mf_portfolio):
        self._setup_two_lots(mf_portfolio)
        with patch("app.mf_xlsx_database._sync_to_drive"):
            with pytest.raises(ValueError, match="Cannot redeem"):
                mf_portfolio.add_mf_sell_transaction(
                    fund_code="INF200K01RJ1",
                    units=100.0,
                    nav=120.0,
                    sell_date="2025-03-01",
                )

    def test_redeem_nonexistent_fund_raises(self, mf_portfolio):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            with pytest.raises(ValueError, match="No file found"):
                mf_portfolio.add_mf_sell_transaction(
                    fund_code="NOSUCH",
                    units=10.0,
                    nav=100.0,
                    sell_date="2025-03-01",
                )

    def test_fractional_redeem(self, mf_portfolio):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="Test Fund",
                units=100.5678,
                nav=50.0,
                buy_date="2025-01-01",
            )
            mf_portfolio.add_mf_sell_transaction(
                fund_code="INF200K01RJ1",
                units=33.1234,
                nav=55.0,
                sell_date="2025-03-01",
            )

        holdings = mf_portfolio.get_all_holdings()
        total = sum(h.units for h in holdings)
        assert abs(total - (100.5678 - 33.1234)) < 0.01

    def test_realized_pl_positive(self, mf_portfolio):
        """Selling at higher NAV should produce positive realized P&L."""
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="Test Fund",
                units=10.0,
                nav=100.0,
                buy_date="2025-01-01",
            )
            result = mf_portfolio.add_mf_sell_transaction(
                fund_code="INF200K01RJ1",
                units=10.0,
                nav=150.0,
                sell_date="2025-06-01",
            )

        # P&L = (150 - 100) * 10 = 500
        assert result["realized_pl"] == 500.0

    def test_realized_pl_negative(self, mf_portfolio):
        """Selling at lower NAV should produce negative realized P&L."""
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="Test Fund",
                units=10.0,
                nav=100.0,
                buy_date="2025-01-01",
            )
            result = mf_portfolio.add_mf_sell_transaction(
                fund_code="INF200K01RJ1",
                units=10.0,
                nav=80.0,
                sell_date="2025-06-01",
            )

        # P&L = (80 - 100) * 10 = -200
        assert result["realized_pl"] == -200.0


# ---------------------------------------------------------------------------
# MFXlsxPortfolio: get_all_holdings
# ---------------------------------------------------------------------------

class TestMFGetAllHoldings:
    """Tests for MFXlsxPortfolio.get_all_holdings()."""

    def test_empty_portfolio(self, mf_portfolio):
        assert mf_portfolio.get_all_holdings() == []

    def test_returns_correct_fields(self, mf_portfolio):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF846K01DP8",
                fund_name="Axis Bluechip Fund",
                units=75.432,
                nav=45.67,
                buy_date="2025-04-01",
            )

        holdings = mf_portfolio.get_all_holdings()
        assert len(holdings) == 1
        h = holdings[0]
        assert h.fund_code == "INF846K01DP8"
        assert h.name == "Axis Bluechip Fund"
        assert abs(h.units - 75.432) < 0.001
        assert abs(h.nav - 45.67) < 0.01
        assert h.buy_date == "2025-04-01"
        assert h.id  # Should have a deterministic ID


# ---------------------------------------------------------------------------
# MFXlsxPortfolio: File structure validation
# ---------------------------------------------------------------------------

class TestMFFileStructure:
    """Tests that created MF xlsx files have the correct internal structure."""

    def test_index_sheet_has_fund_code(self, mf_portfolio, mf_dir):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=10.0,
                nav=120.0,
                buy_date="2025-01-01",
            )

        xlsx_files = list(mf_dir.glob("*.xlsx"))
        assert len(xlsx_files) == 1

        wb = openpyxl.load_workbook(xlsx_files[0], data_only=True)
        assert "Index" in wb.sheetnames
        ws_idx = wb["Index"]
        assert ws_idx.cell(1, 2).value == "Code"
        assert ws_idx.cell(1, 3).value == "INF200K01RJ1"
        wb.close()

    def test_trading_history_headers(self, mf_portfolio, mf_dir):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=10.0,
                nav=120.0,
                buy_date="2025-01-01",
            )

        xlsx_files = list(mf_dir.glob("*.xlsx"))
        wb = openpyxl.load_workbook(xlsx_files[0])
        ws = wb["Trading History"]
        # Header row is typically row 4
        vals = [ws.cell(4, c).value for c in range(1, 8)]
        assert "DATE" in vals
        assert "ACTION" in vals
        assert "Units" in vals
        assert "NAV" in vals
        wb.close()

    def test_buy_row_written_correctly(self, mf_portfolio, mf_dir):
        with patch("app.mf_xlsx_database._sync_to_drive"):
            mf_portfolio.add_mf_holding(
                fund_code="INF200K01RJ1",
                fund_name="SBI Small Cap Fund",
                units=42.5678,
                nav=123.45,
                buy_date="2025-05-20",
            )

        xlsx_files = list(mf_dir.glob("*.xlsx"))
        wb = openpyxl.load_workbook(xlsx_files[0], data_only=True)
        ws = wb["Trading History"]
        # Data row at 5 (header at 4)
        action = ws.cell(5, 3).value
        assert action == "Buy"
        units = ws.cell(5, 4).value
        assert abs(float(units) - 42.5678) < 0.0001
        nav = ws.cell(5, 5).value
        assert abs(float(nav) - 123.45) < 0.01
        wb.close()
