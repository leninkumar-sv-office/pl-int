from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
import uuid


class AddStockRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol e.g. RELIANCE, TCS")
    exchange: str = Field(default="NSE", description="Exchange: NSE or BSE")
    name: str = Field(default="", description="Company name (auto-fetched if empty)")
    quantity: int = Field(..., gt=0, description="Number of shares")
    buy_price: float = Field(..., gt=0, description="Purchase price per share")
    buy_date: str = Field(..., description="Purchase date YYYY-MM-DD")
    notes: str = ""


class SellStockRequest(BaseModel):
    holding_id: str = Field(..., description="ID of the holding to sell")
    quantity: int = Field(..., gt=0, description="Number of shares to sell")
    sell_price: float = Field(..., gt=0, description="Sell price per share")
    sell_date: str = Field(default="", description="Sell date YYYY-MM-DD (defaults to today)")


class AddDividendRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol e.g. RELIANCE, TCS")
    exchange: str = Field(default="NSE")
    amount: float = Field(..., gt=0, description="Total dividend amount received")
    dividend_date: str = Field(default="", description="Dividend date YYYY-MM-DD (defaults to today)")
    remarks: str = Field(default="", description="Optional notes")


class ManualPriceRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    price: float = Field(..., gt=0)


class Transaction(BaseModel):
    """Represents a single Buy/Sell row in an xlsx Trading History sheet."""
    date: str = Field(..., description="Transaction date YYYY-MM-DD")
    exchange: str = Field(default="NSE", description="NSE or BSE")
    action: str = Field(..., description="Buy or Sell")
    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)
    cost: float = 0.0
    remarks: str = "~"
    stt: float = 0.0
    add_chrg: float = 0.0


class Holding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str
    exchange: str
    name: str
    quantity: int
    price: float = 0.0       # Raw transaction price per share (column E)
    buy_price: float          # Per-unit cost incl. charges = COST/QTY (column F / D)
    buy_cost: float = 0.0    # Total cost including STT+charges (column F)
    buy_date: str
    notes: str = ""


class SoldPosition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str
    exchange: str
    name: str
    quantity: int
    buy_price: float
    buy_date: str
    sell_price: float
    sell_date: str
    realized_pl: float


class StockLiveData(BaseModel):
    symbol: str
    exchange: str
    name: str
    current_price: float
    week_52_high: float
    week_52_low: float
    day_change: float = 0.0
    day_change_pct: float = 0.0
    volume: int = 0
    previous_close: float = 0.0
    is_manual: bool = False


class PortfolioSummary(BaseModel):
    total_invested: float
    current_value: float
    unrealized_pl: float
    unrealized_pl_pct: float
    realized_pl: float
    total_holdings: int
    stocks_in_profit: int
    stocks_in_loss: int
    total_dividend: float = 0.0


class HoldingWithLive(BaseModel):
    holding: Holding
    live: Optional[StockLiveData] = None
    unrealized_pl: float = 0.0
    unrealized_pl_pct: float = 0.0
    current_value: float = 0.0
    is_above_buy_price: bool = False
    can_sell: bool = True
    price_error: str = ""  # Non-empty when price is unavailable


class StockSummaryItem(BaseModel):
    """Per-stock aggregated summary showing held + sold totals."""
    symbol: str
    exchange: str
    name: str
    total_held_qty: int = 0       # total shares currently held
    total_sold_qty: int = 0       # total shares sold
    avg_price: float = 0.0        # weighted average transaction price (column E)
    avg_buy_price: float = 0.0    # weighted average buy price incl. charges (COST/QTY)
    total_invested: float = 0.0   # sum of COST (column F) for held lots
    current_value: float = 0.0    # current_price * total_held_qty
    unrealized_pl: float = 0.0
    unrealized_pl_pct: float = 0.0
    unrealized_profit: float = 0.0   # P&L from lots where current > buy (positive)
    unrealized_loss: float = 0.0     # P&L from lots where current <= buy (negative)
    realized_pl: float = 0.0        # sum of realized P&L from sold lots
    # LTCG / STCG breakdown (India: >12 months = long-term)
    ltcg_unrealized_profit: float = 0.0
    stcg_unrealized_profit: float = 0.0
    ltcg_unrealized_loss: float = 0.0
    stcg_unrealized_loss: float = 0.0
    ltcg_realized_pl: float = 0.0
    stcg_realized_pl: float = 0.0
    # Per-category detail for metrics display (units, %, duration, p.a.)
    ltcg_profitable_qty: int = 0
    stcg_profitable_qty: int = 0
    ltcg_loss_qty: int = 0
    stcg_loss_qty: int = 0
    ltcg_invested: float = 0.0       # total cost of LTCG held lots
    stcg_invested: float = 0.0       # total cost of STCG held lots
    ltcg_earliest_date: str = ""     # earliest buy_date among LTCG held lots
    stcg_earliest_date: str = ""     # earliest buy_date among STCG held lots
    ltcg_sold_qty: int = 0
    stcg_sold_qty: int = 0
    ltcg_sold_cost: float = 0.0      # sum of buy_price*qty for LTCG sold lots
    stcg_sold_cost: float = 0.0
    ltcg_sold_earliest_buy: str = ""
    ltcg_sold_latest_sell: str = ""
    stcg_sold_earliest_buy: str = ""
    stcg_sold_latest_sell: str = ""
    num_held_lots: int = 0           # individual held lot count
    num_sold_lots: int = 0           # individual sold lot count
    profitable_qty: int = 0          # shares where lot buy_price < current_price
    loss_qty: int = 0                # shares where lot buy_price >= current_price
    total_dividend: float = 0.0      # total dividend income received
    dividend_count: int = 0          # number of dividend payments
    dividend_units: int = 0          # total units that received dividends
    live: Optional[StockLiveData] = None
    is_above_avg_buy: bool = False
    price_error: str = ""  # Non-empty when price is unavailable


# ═══════════════════════════════════════════════════════════
#  MUTUAL FUND MODELS
# ═══════════════════════════════════════════════════════════

class MFHolding(BaseModel):
    """A single held lot of a mutual fund (fractional units)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    fund_code: str         # MUTF_IN:xxx from Index sheet
    name: str              # Fund name (from filename)
    units: float           # fractional units held
    nav: float             # NAV at purchase (column E)
    buy_price: float       # per-unit cost = COST / Units (column F / D)
    buy_cost: float = 0.0  # total cost (column F)
    buy_date: str
    remarks: str = ""


class MFSoldPosition(BaseModel):
    """A FIFO-matched sold lot of a mutual fund."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    fund_code: str
    name: str
    units: float
    buy_nav: float         # NAV at purchase
    buy_date: str
    sell_nav: float        # NAV at redemption
    sell_date: str
    realized_pl: float


class MFSummaryItem(BaseModel):
    """Per-fund aggregated summary showing held + redeemed totals."""
    fund_code: str
    name: str
    total_held_units: float = 0.0
    total_sold_units: float = 0.0
    avg_nav: float = 0.0           # weighted avg purchase NAV
    total_invested: float = 0.0    # sum of COST for held lots
    current_nav: float = 0.0       # latest NAV
    current_value: float = 0.0     # current_nav * total_held_units
    unrealized_pl: float = 0.0
    unrealized_pl_pct: float = 0.0
    realized_pl: float = 0.0
    # LTCG/STCG (MF equity: >12m = long-term; debt: >36m = long-term)
    ltcg_unrealized_pl: float = 0.0
    stcg_unrealized_pl: float = 0.0
    ltcg_realized_pl: float = 0.0
    stcg_realized_pl: float = 0.0
    num_held_lots: int = 0
    num_sold_lots: int = 0
    week_52_high: float = 0.0
    week_52_low: float = 0.0
    is_above_avg_nav: bool = False


# ── MF Request Models ──────────────────────────────────

class AddMFRequest(BaseModel):
    """Request to add a mutual fund holding (Buy)."""
    fund_code: str = Field(default="", description="MUTF_IN:xxx code (empty for new fund)")
    fund_name: str = Field(..., description="Fund name e.g. 'SBI Small Cap Fund - Direct Growth'")
    units: float = Field(..., gt=0, description="Fractional units purchased")
    nav: float = Field(..., gt=0, description="NAV at purchase")
    buy_date: str = Field(..., description="Purchase date YYYY-MM-DD")
    remarks: str = ""


class RedeemMFRequest(BaseModel):
    """Request to redeem mutual fund units (Sell)."""
    fund_code: str = Field(..., description="MUTF_IN:xxx code of the fund")
    units: float = Field(..., gt=0, description="Units to redeem")
    nav: float = Field(..., gt=0, description="Redemption NAV")
    sell_date: str = Field(default="", description="Redemption date YYYY-MM-DD (defaults to today)")
    remarks: str = ""


class SIPConfigRequest(BaseModel):
    """Request to create or update a SIP configuration."""
    fund_code: str = Field(..., description="MUTF_IN:xxx code")
    fund_name: str = Field(..., description="Fund display name")
    amount: float = Field(..., gt=0, description="SIP amount in rupees")
    frequency: str = Field(default="monthly", description="weekly, monthly, or quarterly")
    sip_date: int = Field(default=1, ge=1, le=28, description="Day of month (1-28) for monthly/quarterly")
    start_date: str = Field(default="", description="SIP start date YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="SIP end date (null = perpetual)")
    enabled: bool = True
    notes: str = ""
