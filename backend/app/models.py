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
    week_change_pct: float = 0.0
    month_change_pct: float = 0.0
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


# ═══════════════════════════════════════════════════════════
#  FIXED DEPOSIT MODELS
# ═══════════════════════════════════════════════════════════

class FDItem(BaseModel):
    """A single Fixed Deposit."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    bank: str
    principal: float
    interest_rate: float
    tenure_months: int
    start_date: str
    maturity_date: str
    maturity_amount: float = 0.0
    interest_earned: float = 0.0
    tds: float = 0.0
    status: str = "Active"   # Active / Matured / Premature / Closed
    remarks: str = ""


class AddFDRequest(BaseModel):
    """Request to add a Fixed Deposit."""
    bank: str = Field(..., description="Bank or institution name")
    principal: float = Field(..., gt=0, description="Deposit amount")
    interest_rate: float = Field(..., gt=0, description="Annual interest rate (%)")
    tenure_months: int = Field(..., gt=0, description="Tenure in months")
    type: str = Field(default="FD", description="FD or MIS")
    interest_payout: str = Field(default="Quarterly", description="Monthly/Quarterly/Half-Yearly/Annually")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    maturity_date: str = Field(default="", description="Maturity date YYYY-MM-DD (auto-calculated if empty)")
    tds: float = Field(default=0.0, ge=0, description="TDS deducted")
    status: str = Field(default="Active", description="Active/Matured/Premature/Closed")
    remarks: str = ""


class UpdateFDRequest(BaseModel):
    """Request to update a Fixed Deposit."""
    bank: Optional[str] = None
    principal: Optional[float] = None
    interest_rate: Optional[float] = None
    tenure_months: Optional[int] = None
    start_date: Optional[str] = None
    maturity_date: Optional[str] = None
    tds: Optional[float] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


# ═══════════════════════════════════════════════════════════
#  RECURRING DEPOSIT MODELS
# ═══════════════════════════════════════════════════════════

class RDInstallment(BaseModel):
    """A single RD installment payment."""
    date: str
    amount: float
    remarks: str = ""


class RDItem(BaseModel):
    """A single Recurring Deposit."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    bank: str
    monthly_amount: float
    interest_rate: float
    tenure_months: int
    start_date: str
    maturity_date: str
    maturity_amount: float = 0.0
    total_deposited: float = 0.0
    status: str = "Active"   # Active / Matured / Closed
    remarks: str = ""
    installments: list = Field(default_factory=list)  # List[RDInstallment]


class AddRDRequest(BaseModel):
    """Request to add a Recurring Deposit."""
    bank: str = Field(..., description="Bank or institution name")
    monthly_amount: float = Field(..., gt=0, description="Monthly installment amount")
    interest_rate: float = Field(..., gt=0, description="Annual interest rate (%)")
    tenure_months: int = Field(..., gt=0, description="Tenure in months")
    compounding_frequency: int = Field(default=4, description="Compounding frequency: 1=Monthly, 4=Quarterly, 6=Half-Yearly, 12=Annually")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    maturity_date: str = Field(default="", description="Maturity date YYYY-MM-DD (auto-calculated if empty)")
    status: str = Field(default="Active", description="Active/Matured/Closed")
    remarks: str = ""


class UpdateRDRequest(BaseModel):
    """Request to update a Recurring Deposit."""
    bank: Optional[str] = None
    monthly_amount: Optional[float] = None
    interest_rate: Optional[float] = None
    tenure_months: Optional[int] = None
    start_date: Optional[str] = None
    maturity_date: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class AddRDInstallmentRequest(BaseModel):
    """Request to add an RD installment."""
    date: str = Field(..., description="Installment date YYYY-MM-DD")
    amount: float = Field(..., gt=0, description="Installment amount")
    remarks: str = ""


# ═══════════════════════════════════════════════════════════
#  INSURANCE POLICY MODELS
# ═══════════════════════════════════════════════════════════

class InsurancePolicy(BaseModel):
    """A single Insurance Policy."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    policy_name: str
    provider: str
    type: str = "Health"     # Health / Car / Bike / Life / Other
    policy_number: str = ""
    premium: float = 0.0
    coverage_amount: float = 0.0
    start_date: str = ""
    expiry_date: str = ""
    payment_frequency: str = "Annual"  # Monthly / Quarterly / Annual
    status: str = "Active"   # Active / Expired / Cancelled
    remarks: str = ""


class AddInsuranceRequest(BaseModel):
    """Request to add an Insurance Policy."""
    policy_name: str = Field(..., description="Policy name")
    provider: str = Field(..., description="Insurance provider/company")
    type: str = Field(default="Health", description="Health/Car/Bike/Life/Other")
    policy_number: str = Field(default="", description="Policy number")
    premium: float = Field(..., gt=0, description="Premium amount")
    coverage_amount: float = Field(default=0.0, ge=0, description="Sum assured / coverage")
    start_date: str = Field(..., description="Policy start date YYYY-MM-DD")
    expiry_date: str = Field(..., description="Policy expiry date YYYY-MM-DD")
    payment_frequency: str = Field(default="Annual", description="Monthly/Quarterly/Annual")
    status: str = Field(default="Active", description="Active/Expired/Cancelled")
    remarks: str = ""


class UpdateInsuranceRequest(BaseModel):
    """Request to update an Insurance Policy."""
    policy_name: Optional[str] = None
    provider: Optional[str] = None
    type: Optional[str] = None
    policy_number: Optional[str] = None
    premium: Optional[float] = None
    coverage_amount: Optional[float] = None
    start_date: Optional[str] = None
    expiry_date: Optional[str] = None
    payment_frequency: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


# ═══════════════════════════════════════════════════════════
#  PPF (PUBLIC PROVIDENT FUND) MODELS
# ═══════════════════════════════════════════════════════════

class PPFContribution(BaseModel):
    """A single PPF contribution."""
    date: str
    amount: float
    remarks: str = ""


class AddPPFRequest(BaseModel):
    """Request to add a PPF account."""
    account_name: str = Field(default="PPF Account", description="Account display name")
    bank: str = Field(..., description="Bank or Post Office")
    account_number: str = Field(default="", description="PPF account number")
    interest_rate: float = Field(default=7.1, description="Annual interest rate (%)")
    start_date: str = Field(..., description="Account opening date YYYY-MM-DD")
    tenure_years: int = Field(default=15, description="Lock-in period in years")
    payment_type: str = Field(default="one_time", description="one_time or sip")
    amount_added: float = Field(default=0, ge=0, description="Initial deposit amount (one-time)")
    sip_amount: float = Field(default=0, ge=0, description="SIP amount per period")
    sip_frequency: str = Field(default="monthly", description="monthly / quarterly / yearly")
    sip_end_date: Optional[str] = Field(default=None, description="SIP end date (null = until maturity)")
    remarks: str = ""


class UpdatePPFRequest(BaseModel):
    """Request to update a PPF account."""
    account_name: Optional[str] = None
    bank: Optional[str] = None
    account_number: Optional[str] = None
    interest_rate: Optional[float] = None
    start_date: Optional[str] = None
    tenure_years: Optional[int] = None
    payment_type: Optional[str] = None
    sip_amount: Optional[float] = None
    sip_frequency: Optional[str] = None
    sip_end_date: Optional[str] = None
    remarks: Optional[str] = None


class AddPPFContributionRequest(BaseModel):
    """Request to add a PPF contribution."""
    date: str = Field(..., description="Contribution date YYYY-MM-DD")
    amount: float = Field(..., gt=0, description="Contribution amount")
    remarks: str = ""


# ═══════════════════════════════════════════════════════════
#  NPS (NATIONAL PENSION SYSTEM) MODELS
# ═══════════════════════════════════════════════════════════

class AddNPSRequest(BaseModel):
    """Request to add an NPS account."""
    account_name: str = Field(default="NPS Account", description="Account display name")
    pran: str = Field(default="", description="Permanent Retirement Account Number")
    tier: str = Field(default="Tier I", description="Tier I or Tier II")
    fund_manager: str = Field(default="", description="Pension Fund Manager name")
    scheme_preference: str = Field(default="Auto Choice", description="Auto Choice / Active Choice / Aggressive / Moderate / Conservative")
    start_date: str = Field(..., description="Account opening date YYYY-MM-DD")
    current_value: float = Field(default=0, ge=0, description="Current corpus value")
    status: str = Field(default="Active", description="Active / Frozen / Closed")
    remarks: str = ""


class UpdateNPSRequest(BaseModel):
    """Request to update an NPS account."""
    account_name: Optional[str] = None
    pran: Optional[str] = None
    tier: Optional[str] = None
    fund_manager: Optional[str] = None
    scheme_preference: Optional[str] = None
    start_date: Optional[str] = None
    current_value: Optional[float] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class AddNPSContributionRequest(BaseModel):
    """Request to add an NPS contribution."""
    date: str = Field(..., description="Contribution date YYYY-MM-DD")
    amount: float = Field(..., gt=0, description="Contribution amount")
    remarks: str = ""


# ═══════════════════════════════════════════════════════════
#  STANDING INSTRUCTION (SI) MODELS
# ═══════════════════════════════════════════════════════════

class SIItem(BaseModel):
    """A single Standing Instruction (NACH/ECS/UPI Autopay mandate)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    bank: str
    beneficiary: str
    amount: float
    frequency: str = "Monthly"
    purpose: str = "SIP"
    mandate_type: str = "NACH"
    account_number: str = ""
    start_date: str
    expiry_date: str
    alert_days: int = 30
    status: str = "Active"
    remarks: str = ""


class AddSIRequest(BaseModel):
    """Request to add a Standing Instruction."""
    bank: str = Field(..., description="Bank name")
    beneficiary: str = Field(..., description="Who receives the payment")
    amount: float = Field(..., gt=0, description="Debit amount")
    frequency: str = Field(default="Monthly", description="Monthly/Quarterly/Half-Yearly/Annually")
    purpose: str = Field(default="SIP", description="SIP/EMI/Utility/Insurance/Other")
    mandate_type: str = Field(default="NACH", description="NACH/ECS/UPI Autopay/Other")
    account_number: str = Field(default="", description="Bank account number")
    start_date: str = Field(..., description="Mandate start date YYYY-MM-DD")
    expiry_date: str = Field(..., description="Mandate expiry date YYYY-MM-DD")
    alert_days: int = Field(default=30, ge=1, description="Alert before N days of expiry")
    status: str = Field(default="Active", description="Active/Expired/Cancelled")
    remarks: str = ""


class UpdateSIRequest(BaseModel):
    """Request to update a Standing Instruction."""
    bank: Optional[str] = None
    beneficiary: Optional[str] = None
    amount: Optional[float] = None
    frequency: Optional[str] = None
    purpose: Optional[str] = None
    mandate_type: Optional[str] = None
    account_number: Optional[str] = None
    start_date: Optional[str] = None
    expiry_date: Optional[str] = None
    alert_days: Optional[int] = None
    status: Optional[str] = None
    remarks: Optional[str] = None
