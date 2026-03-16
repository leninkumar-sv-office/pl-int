"""
Unit tests for app/models.py

Tests Pydantic model instantiation, field validation, and defaults.
"""
import pytest
from pydantic import ValidationError


# ═══════════════════════════════════════════════════════════
#  AddStockRequest
# ═══════════════════════════════════════════════════════════

def test_add_stock_request_valid():
    from app.models import AddStockRequest
    req = AddStockRequest(
        symbol="RELIANCE", quantity=10, buy_price=2500.0, buy_date="2024-01-01"
    )
    assert req.symbol == "RELIANCE"
    assert req.exchange == "NSE"  # default
    assert req.notes == ""


def test_add_stock_request_missing_symbol():
    from app.models import AddStockRequest
    with pytest.raises(ValidationError):
        AddStockRequest(quantity=10, buy_price=2500.0, buy_date="2024-01-01")


def test_add_stock_request_zero_quantity():
    from app.models import AddStockRequest
    with pytest.raises(ValidationError):
        AddStockRequest(symbol="TCS", quantity=0, buy_price=100.0, buy_date="2024-01-01")


def test_add_stock_request_negative_price():
    from app.models import AddStockRequest
    with pytest.raises(ValidationError):
        AddStockRequest(symbol="TCS", quantity=1, buy_price=-100.0, buy_date="2024-01-01")


def test_add_stock_request_exchange_default():
    from app.models import AddStockRequest
    req = AddStockRequest(symbol="TCS", quantity=5, buy_price=3500.0, buy_date="2024-06-01")
    assert req.exchange == "NSE"


# ═══════════════════════════════════════════════════════════
#  SellStockRequest
# ═══════════════════════════════════════════════════════════

def test_sell_stock_request_valid():
    from app.models import SellStockRequest
    req = SellStockRequest(holding_id="abc12345", quantity=5, sell_price=2600.0)
    assert req.holding_id == "abc12345"
    assert req.sell_date == ""  # default


def test_sell_stock_request_missing_holding_id():
    from app.models import SellStockRequest
    with pytest.raises(ValidationError):
        SellStockRequest(quantity=5, sell_price=2600.0)


def test_sell_stock_request_zero_quantity():
    from app.models import SellStockRequest
    with pytest.raises(ValidationError):
        SellStockRequest(holding_id="abc12345", quantity=0, sell_price=2600.0)


# ═══════════════════════════════════════════════════════════
#  Holding
# ═══════════════════════════════════════════════════════════

def test_holding_valid():
    from app.models import Holding
    h = Holding(
        symbol="INFY", exchange="NSE", name="Infosys",
        quantity=20, buy_price=1800.0, buy_date="2023-05-01"
    )
    assert h.symbol == "INFY"
    assert len(h.id) > 0  # auto-generated
    assert h.notes == ""


def test_holding_missing_required_fields():
    from app.models import Holding
    with pytest.raises(ValidationError):
        Holding(symbol="INFY", exchange="NSE")  # missing quantity, buy_price, buy_date, name


# ═══════════════════════════════════════════════════════════
#  SoldPosition
# ═══════════════════════════════════════════════════════════

def test_sold_position_valid():
    from app.models import SoldPosition
    sp = SoldPosition(
        symbol="TCS", exchange="NSE", name="TCS",
        quantity=10, buy_price=3000.0, buy_date="2022-01-01",
        sell_price=3600.0, sell_date="2023-06-01", realized_pl=6000.0
    )
    assert sp.realized_pl == 6000.0
    assert len(sp.id) > 0


# ═══════════════════════════════════════════════════════════
#  StockLiveData
# ═══════════════════════════════════════════════════════════

def test_stock_live_data_defaults():
    from app.models import StockLiveData
    d = StockLiveData(
        symbol="WIPRO", exchange="NSE", name="Wipro",
        current_price=450.0, week_52_high=550.0, week_52_low=380.0
    )
    assert d.day_change == 0.0
    assert d.day_change_pct == 0.0
    assert d.volume == 0
    assert d.is_manual is False


def test_stock_live_data_required_fields():
    from app.models import StockLiveData
    with pytest.raises(ValidationError):
        StockLiveData(symbol="WIPRO")  # missing required fields


# ═══════════════════════════════════════════════════════════
#  PortfolioSummary
# ═══════════════════════════════════════════════════════════

def test_portfolio_summary_valid():
    from app.models import PortfolioSummary
    s = PortfolioSummary(
        total_invested=100000.0, current_value=120000.0,
        unrealized_pl=20000.0, unrealized_pl_pct=20.0,
        realized_pl=5000.0, total_holdings=10,
        stocks_in_profit=7, stocks_in_loss=3
    )
    assert s.total_dividend == 0.0  # default


# ═══════════════════════════════════════════════════════════
#  HoldingWithLive
# ═══════════════════════════════════════════════════════════

def test_holding_with_live_defaults():
    from app.models import HoldingWithLive, Holding
    h = Holding(
        symbol="HDFC", exchange="NSE", name="HDFC Bank",
        quantity=5, buy_price=1400.0, buy_date="2024-01-01"
    )
    hwl = HoldingWithLive(holding=h)
    assert hwl.live is None
    assert hwl.unrealized_pl == 0.0
    assert hwl.can_sell is True
    assert hwl.price_error == ""


# ═══════════════════════════════════════════════════════════
#  MFHolding
# ═══════════════════════════════════════════════════════════

def test_mf_holding_valid():
    from app.models import MFHolding
    mf = MFHolding(
        fund_code="INF200K01RO2", name="Axis Small Cap Fund",
        units=150.5, nav=48.23, buy_price=48.23, buy_date="2024-03-01"
    )
    assert mf.units == 150.5
    assert mf.buy_cost == 0.0  # default


def test_mf_holding_missing_required():
    from app.models import MFHolding
    with pytest.raises(ValidationError):
        MFHolding(fund_code="INF200K01RO2")  # missing units, nav, etc.


# ═══════════════════════════════════════════════════════════
#  FDItem
# ═══════════════════════════════════════════════════════════

def test_fd_item_valid():
    from app.models import FDItem
    fd = FDItem(
        bank="SBI", principal=100000.0, interest_rate=7.5,
        tenure_months=24, start_date="2024-01-01", maturity_date="2026-01-01"
    )
    assert fd.status == "Active"
    assert fd.tds == 0.0
    assert len(fd.id) > 0


def test_fd_item_custom_status():
    from app.models import FDItem
    fd = FDItem(
        bank="HDFC", principal=50000.0, interest_rate=6.5,
        tenure_months=12, start_date="2023-01-01", maturity_date="2024-01-01",
        status="Matured"
    )
    assert fd.status == "Matured"


# ═══════════════════════════════════════════════════════════
#  AddFDRequest
# ═══════════════════════════════════════════════════════════

def test_add_fd_request_valid():
    from app.models import AddFDRequest
    req = AddFDRequest(
        bank="ICICI", principal=200000.0, interest_rate=7.0,
        tenure_months=36, start_date="2024-01-01"
    )
    assert req.status == "Active"
    assert req.type == "FD"


def test_add_fd_request_zero_principal():
    from app.models import AddFDRequest
    with pytest.raises(ValidationError):
        AddFDRequest(
            bank="ICICI", principal=0.0, interest_rate=7.0,
            tenure_months=12, start_date="2024-01-01"
        )


# ═══════════════════════════════════════════════════════════
#  Transaction
# ═══════════════════════════════════════════════════════════

def test_transaction_valid():
    from app.models import Transaction
    t = Transaction(
        date="2024-01-15", action="Buy", quantity=10, price=150.0
    )
    assert t.exchange == "NSE"  # default
    assert t.cost == 0.0
    assert t.stt == 0.0


def test_transaction_missing_required():
    from app.models import Transaction
    with pytest.raises(ValidationError):
        Transaction(date="2024-01-01")  # missing action, quantity, price


# ═══════════════════════════════════════════════════════════
#  AddDividendRequest
# ═══════════════════════════════════════════════════════════

def test_add_dividend_request_valid():
    from app.models import AddDividendRequest
    req = AddDividendRequest(symbol="ONGC", amount=500.0)
    assert req.exchange == "NSE"  # default
    assert req.remarks == ""


def test_add_dividend_request_zero_amount():
    from app.models import AddDividendRequest
    with pytest.raises(ValidationError):
        AddDividendRequest(symbol="ONGC", amount=0.0)


# ═══════════════════════════════════════════════════════════
#  RDItem
# ═══════════════════════════════════════════════════════════

def test_rd_item_valid():
    from app.models import RDItem
    rd = RDItem(
        bank="Post Office", monthly_amount=5000.0, interest_rate=6.7,
        tenure_months=60, start_date="2023-06-01", maturity_date="2028-06-01"
    )
    assert rd.status == "Active"
    assert rd.installments == []


# ═══════════════════════════════════════════════════════════
#  InsurancePolicy
# ═══════════════════════════════════════════════════════════

def test_insurance_policy_valid():
    from app.models import InsurancePolicy
    p = InsurancePolicy(
        policy_name="Star Health Family Floater",
        provider="Star Health"
    )
    assert p.type == "Health"
    assert p.status == "Active"
    assert p.premium == 0.0


def test_insurance_policy_missing_required():
    from app.models import InsurancePolicy
    with pytest.raises(ValidationError):
        InsurancePolicy(provider="Star Health")  # missing policy_name
