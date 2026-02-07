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
    buy_price: float
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


class HoldingWithLive(BaseModel):
    holding: Holding
    live: Optional[StockLiveData] = None
    unrealized_pl: float = 0.0
    unrealized_pl_pct: float = 0.0
    current_value: float = 0.0
    is_above_buy_price: bool = False
    can_sell: bool = True


class StockSummaryItem(BaseModel):
    """Per-stock aggregated summary showing held + sold totals."""
    symbol: str
    exchange: str
    name: str
    total_held_qty: int = 0       # total shares currently held
    total_sold_qty: int = 0       # total shares sold
    avg_buy_price: float = 0.0    # weighted average buy price (held lots)
    total_invested: float = 0.0   # sum of (buy_price * qty) for held lots
    current_value: float = 0.0    # current_price * total_held_qty
    unrealized_pl: float = 0.0
    unrealized_pl_pct: float = 0.0
    unrealized_profit: float = 0.0   # P&L from lots where current > buy (positive)
    unrealized_loss: float = 0.0     # P&L from lots where current <= buy (negative)
    realized_pl: float = 0.0        # sum of realized P&L from sold lots
    num_held_lots: int = 0           # individual held lot count
    num_sold_lots: int = 0           # individual sold lot count
    profitable_qty: int = 0          # shares where lot buy_price < current_price
    loss_qty: int = 0                # shares where lot buy_price >= current_price
    total_dividend: float = 0.0      # total dividend income received
    live: Optional[StockLiveData] = None
    is_above_avg_buy: bool = False
