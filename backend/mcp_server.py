"""
Portfolio Dashboard MCP Server

Exposes all portfolio data and actions as MCP tools for AI agents.
Proxies requests to the running FastAPI backend at http://localhost:9999.

Usage:
  python mcp_server.py
  # Or add to Claude Code MCP config:
  # "portfolio": {"command": "python", "args": ["/path/to/mcp_server.py"]}
"""
import json
import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = "http://localhost:9999/api"

mcp = FastMCP(
    "Portfolio Dashboard",
    instructions=(
        "A comprehensive Indian investment portfolio tracker. "
        "Provides real-time data for stocks, mutual funds, fixed deposits, "
        "recurring deposits, insurance, PPF, NPS, and standing instructions. "
        "Market data powered by Zerodha Kite API."
    ),
)


# ── Helpers ──────────────────────────────────────────────

def _get(path: str, params: dict = None) -> dict | list | str:
    """GET request to backend API."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{BASE_URL}{path}", params=params)
        resp.raise_for_status()
        return resp.json()


def _post(path: str, payload: dict = None) -> dict | list | str:
    """POST request to backend API."""
    with httpx.Client(timeout=120) as client:
        resp = client.post(f"{BASE_URL}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()


def _put(path: str, payload: dict) -> dict | list | str:
    """PUT request to backend API."""
    with httpx.Client(timeout=30) as client:
        resp = client.put(f"{BASE_URL}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()


def _delete(path: str) -> dict | list | str:
    """DELETE request to backend API."""
    with httpx.Client(timeout=30) as client:
        resp = client.delete(f"{BASE_URL}{path}")
        resp.raise_for_status()
        return resp.json()


def _fmt(data) -> str:
    """Format response data as readable JSON string."""
    return json.dumps(data, indent=2, default=str)


# ═══════════════════════════════════════════════════════════
#  STOCK PORTFOLIO — Read
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_portfolio() -> str:
    """Get all current stock holdings with live prices, P&L, and allocation details.

    Returns a list of holdings with: symbol, exchange, quantity, avg_buy_price,
    current_price, total_invested, current_value, unrealized_pl, unrealized_pl_pct,
    day_change, day_change_pct, and more.
    """
    return _fmt(_get("/portfolio"))


@mcp.tool()
def get_stock_summary() -> str:
    """Get consolidated stock summary grouped by symbol.

    Each entry includes: symbol, exchange, name, total_quantity, avg_buy_price,
    current_price, total_invested, current_value, unrealized_pl, unrealized_pl_pct,
    week_52_high, week_52_low, day_change_pct, week_change_pct, month_change_pct,
    total_dividends, weight_pct.
    """
    return _fmt(_get("/portfolio/stock-summary"))


@mcp.tool()
def get_dashboard_summary() -> str:
    """Get overall portfolio dashboard with totals.

    Returns: total_invested, current_value, total_pl, total_pl_pct,
    day_change, day_change_pct, total_dividends, holdings_count,
    top_gainers, top_losers, sector breakdown, etc.
    """
    return _fmt(_get("/dashboard/summary"))


@mcp.tool()
def get_transactions() -> str:
    """Get all sell/sold transaction history.

    Each entry includes: symbol, exchange, quantity, buy_price, sell_price,
    buy_date, sell_date, realized_pl, realized_pl_pct, holding_days.
    """
    return _fmt(_get("/transactions"))


@mcp.tool()
def get_stock_price(symbol: str, exchange: str = "NSE") -> str:
    """Get live price and details for a specific stock.

    Args:
        symbol: Stock symbol (e.g., RELIANCE, TCS, INFY)
        exchange: NSE or BSE (default: NSE)
    """
    return _fmt(_get(f"/stock/{symbol}/price", {"exchange": exchange}))


@mcp.tool()
def get_stock_history(symbol: str, exchange: str = "NSE", period: str = "1y") -> str:
    """Get historical OHLCV price data for a stock (for charting).

    Args:
        symbol: Stock symbol (e.g., RELIANCE, TCS)
        exchange: NSE or BSE (default: NSE)
        period: 1d, 5d, 1m, 6m, ytd, 1y, 5y, or max
    """
    return _fmt(_get(f"/stock/{symbol}/history", {"exchange": exchange, "period": period}))


@mcp.tool()
def search_stock(query: str, exchange: str = "NSE") -> str:
    """Search for stocks by symbol or company name.

    Args:
        query: Search query (e.g., "reliance", "tata", "info")
        exchange: NSE or BSE (default: NSE)

    Returns up to 10 matching stocks with symbol, name, exchange.
    """
    return _fmt(_get(f"/stock/search/{query}", {"exchange": exchange}))


# ═══════════════════════════════════════════════════════════
#  MARKET TICKER — Read
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_market_ticker() -> str:
    """Get current market ticker data — indices, commodities, forex.

    Returns tickers for: SENSEX, NIFTY 50, GIFT Nifty, USD/INR,
    Crude Oil, Gold, Silver with price, change, change_pct,
    week_change_pct, month_change_pct.
    Also returns last_updated timestamp.
    """
    return _fmt(_get("/market-ticker"))


# ═══════════════════════════════════════════════════════════
#  MUTUAL FUNDS — Read
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_mf_summary() -> str:
    """Get all mutual fund holdings with current NAV, P&L.

    Each fund includes: fund_code, fund_name, units, avg_nav,
    current_nav, invested, current_value, unrealized_pl, unrealized_pl_pct,
    day_change_pct, week_change_pct, month_change_pct, xirr.
    """
    return _fmt(_get("/mutual-funds/summary"))


@mcp.tool()
def get_mf_dashboard() -> str:
    """Get mutual fund dashboard totals.

    Returns: total_invested, current_value, total_pl, total_pl_pct,
    day_change, funds_count, overall_xirr.
    """
    return _fmt(_get("/mutual-funds/dashboard"))


@mcp.tool()
def search_mf(query: str, plan: str = "direct", scheme_type: str = "") -> str:
    """Search for mutual fund schemes.

    Args:
        query: Fund name search (e.g., "axis bluechip", "parag parikh")
        plan: "direct" or "regular" (default: direct)
        scheme_type: "growth" or "dividend" or "" for all

    Returns up to 15 matching funds.
    """
    return _fmt(_get("/mutual-funds/search", {"q": query, "plan": plan, "scheme_type": scheme_type}))


@mcp.tool()
def get_sip_configs() -> str:
    """Get all configured SIP (Systematic Investment Plan) entries."""
    return _fmt(_get("/mutual-funds/sip"))


@mcp.tool()
def get_pending_sips() -> str:
    """Get SIPs that are due for execution this month."""
    return _fmt(_get("/mutual-funds/sip/pending"))


# ═══════════════════════════════════════════════════════════
#  FIXED DEPOSITS — Read
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_fd_summary() -> str:
    """Get all fixed deposit details.

    Each FD includes: bank, principal, interest_rate, start_date,
    maturity_date, maturity_amount, tenure_months, days_remaining, status.
    """
    return _fmt(_get("/fixed-deposits/summary"))


@mcp.tool()
def get_fd_dashboard() -> str:
    """Get fixed deposit dashboard totals.

    Returns: total_invested, total_maturity, total_interest,
    avg_rate, active_count, maturing_soon.
    """
    return _fmt(_get("/fixed-deposits/dashboard"))


# ═══════════════════════════════════════════════════════════
#  RECURRING DEPOSITS — Read
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_rd_summary() -> str:
    """Get all recurring deposit details.

    Each RD includes: bank, monthly_amount, interest_rate, start_date,
    maturity_date, total_deposited, installments_paid, status.
    """
    return _fmt(_get("/recurring-deposits/summary"))


@mcp.tool()
def get_rd_dashboard() -> str:
    """Get recurring deposit dashboard totals."""
    return _fmt(_get("/recurring-deposits/dashboard"))


# ═══════════════════════════════════════════════════════════
#  INSURANCE — Read
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_insurance_summary() -> str:
    """Get all insurance policies.

    Each policy includes: policy_name, insurer, type (term/health/life/etc),
    sum_assured, premium, premium_frequency, start_date, maturity_date, status.
    """
    return _fmt(_get("/insurance/summary"))


@mcp.tool()
def get_insurance_dashboard() -> str:
    """Get insurance dashboard totals.

    Returns: total_cover, total_annual_premium, active_policies,
    policies_by_type breakdown.
    """
    return _fmt(_get("/insurance/dashboard"))


# ═══════════════════════════════════════════════════════════
#  PPF — Read
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_ppf_summary() -> str:
    """Get all PPF (Public Provident Fund) account details.

    Each account includes: bank, account_number, opening_date,
    maturity_date, total_deposits, current_balance, interest_earned,
    yearly_contributions, status.
    """
    return _fmt(_get("/ppf/summary"))


@mcp.tool()
def get_ppf_dashboard() -> str:
    """Get PPF dashboard totals."""
    return _fmt(_get("/ppf/dashboard"))


# ═══════════════════════════════════════════════════════════
#  NPS — Read
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_nps_summary() -> str:
    """Get all NPS (National Pension System) account details.

    Each account includes: pran, fund_manager, scheme,
    total_contribution, current_value, returns, status.
    """
    return _fmt(_get("/nps/summary"))


@mcp.tool()
def get_nps_dashboard() -> str:
    """Get NPS dashboard totals."""
    return _fmt(_get("/nps/dashboard"))


# ═══════════════════════════════════════════════════════════
#  STANDING INSTRUCTIONS — Read
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_si_summary() -> str:
    """Get all standing instructions (auto-pay mandates).

    Each SI includes: bank, beneficiary, amount, frequency,
    start_date, end_date, days_to_expiry, alert_days, status.
    """
    return _fmt(_get("/standing-instructions/summary"))


@mcp.tool()
def get_si_dashboard() -> str:
    """Get standing instructions dashboard totals."""
    return _fmt(_get("/standing-instructions/dashboard"))


# ═══════════════════════════════════════════════════════════
#  ZERODHA STATUS
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_zerodha_status() -> str:
    """Get Zerodha Kite API connection status.

    Returns: configured, session_valid, auth_failed, api_key_prefix, last_error.
    """
    return _fmt(_get("/zerodha/status"))


# ═══════════════════════════════════════════════════════════
#  STOCK PORTFOLIO — Actions
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def add_stock(symbol: str, exchange: str, quantity: int, price: float, date: str, broker: str = "") -> str:
    """Add a stock purchase to the portfolio.

    Args:
        symbol: Stock symbol (e.g., RELIANCE, TCS)
        exchange: NSE or BSE
        quantity: Number of shares bought
        price: Purchase price per share
        date: Purchase date (YYYY-MM-DD)
        broker: Broker name (optional)
    """
    return _fmt(_post("/portfolio/add", {
        "symbol": symbol, "exchange": exchange, "quantity": quantity,
        "price": price, "date": date, "broker": broker,
    }))


@mcp.tool()
def sell_stock(symbol: str, exchange: str, quantity: int, price: float, date: str) -> str:
    """Sell stock from portfolio (FIFO lot matching).

    Args:
        symbol: Stock symbol
        exchange: NSE or BSE
        quantity: Number of shares to sell
        price: Sell price per share
        date: Sell date (YYYY-MM-DD)

    Returns realized P&L details.
    """
    return _fmt(_post("/portfolio/sell", {
        "symbol": symbol, "exchange": exchange, "quantity": quantity,
        "price": price, "date": date,
    }))


@mcp.tool()
def add_dividend(symbol: str, exchange: str, amount: float, date: str) -> str:
    """Record a dividend received for a stock.

    Args:
        symbol: Stock symbol
        exchange: NSE or BSE
        amount: Total dividend amount received (INR)
        date: Dividend date (YYYY-MM-DD)
    """
    return _fmt(_post("/portfolio/dividend", {
        "symbol": symbol, "exchange": exchange, "amount": amount, "date": date,
    }))


# ═══════════════════════════════════════════════════════════
#  REFRESH / PRICES — Actions
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def refresh_prices() -> str:
    """Trigger a live price refresh from Zerodha for all holdings.
    This fetches fresh prices from the exchange.
    """
    return _fmt(_post("/prices/refresh"))


@mcp.tool()
def refresh_market_ticker() -> str:
    """Trigger a market ticker refresh (indices, commodities, forex)."""
    return _fmt(_post("/market-ticker/refresh"))


@mcp.tool()
def refresh_mf_nav() -> str:
    """Trigger mutual fund NAV refresh from AMFI/mfapi."""
    return _fmt(_post("/mutual-funds/refresh-nav"))


# ═══════════════════════════════════════════════════════════
#  MUTUAL FUNDS — Actions
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def buy_mf(fund_code: str, fund_name: str, units: float, nav: float, date: str) -> str:
    """Record a mutual fund purchase.

    Args:
        fund_code: ISIN or fund code (e.g., INF209K01YN0)
        fund_name: Fund name
        units: Number of units bought
        nav: NAV (price per unit) at purchase
        date: Purchase date (YYYY-MM-DD)
    """
    return _fmt(_post("/mutual-funds/buy", {
        "fund_code": fund_code, "fund_name": fund_name,
        "units": units, "nav": nav, "date": date,
    }))


@mcp.tool()
def redeem_mf(fund_code: str, units: float, nav: float, date: str) -> str:
    """Redeem (sell) mutual fund units.

    Args:
        fund_code: ISIN or fund code
        units: Number of units to redeem
        nav: NAV at redemption
        date: Redemption date (YYYY-MM-DD)

    Returns realized P&L details.
    """
    return _fmt(_post("/mutual-funds/redeem", {
        "fund_code": fund_code, "units": units, "nav": nav, "date": date,
    }))


# ═══════════════════════════════════════════════════════════
#  FIXED DEPOSITS — Actions
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def add_fd(bank: str, principal: float, interest_rate: float, start_date: str,
           maturity_date: str, compounding: str = "quarterly") -> str:
    """Add a fixed deposit.

    Args:
        bank: Bank name
        principal: Deposit amount (INR)
        interest_rate: Annual interest rate (%)
        start_date: Start date (YYYY-MM-DD)
        maturity_date: Maturity date (YYYY-MM-DD)
        compounding: quarterly, monthly, or yearly
    """
    return _fmt(_post("/fixed-deposits/add", {
        "bank": bank, "principal": principal, "interest_rate": interest_rate,
        "start_date": start_date, "maturity_date": maturity_date,
        "compounding": compounding,
    }))


@mcp.tool()
def delete_fd(fd_id: str) -> str:
    """Delete a fixed deposit by ID.

    Args:
        fd_id: The FD's unique identifier
    """
    return _fmt(_delete(f"/fixed-deposits/{fd_id}"))


# ═══════════════════════════════════════════════════════════
#  RECURRING DEPOSITS — Actions
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def add_rd(bank: str, monthly_amount: float, interest_rate: float, start_date: str,
           maturity_date: str) -> str:
    """Add a recurring deposit.

    Args:
        bank: Bank name
        monthly_amount: Monthly installment amount (INR)
        interest_rate: Annual interest rate (%)
        start_date: Start date (YYYY-MM-DD)
        maturity_date: Maturity date (YYYY-MM-DD)
    """
    return _fmt(_post("/recurring-deposits/add", {
        "bank": bank, "monthly_amount": monthly_amount,
        "interest_rate": interest_rate, "start_date": start_date,
        "maturity_date": maturity_date,
    }))


# ═══════════════════════════════════════════════════════════
#  INSURANCE — Actions
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def add_insurance(policy_name: str, insurer: str, type: str, sum_assured: float,
                  premium: float, premium_frequency: str, start_date: str,
                  maturity_date: str = "") -> str:
    """Add an insurance policy.

    Args:
        policy_name: Policy name/number
        insurer: Insurance company name
        type: term, health, life, ulip, endowment, etc.
        sum_assured: Sum assured / cover amount (INR)
        premium: Premium amount per frequency (INR)
        premium_frequency: monthly, quarterly, half-yearly, yearly
        start_date: Policy start date (YYYY-MM-DD)
        maturity_date: Maturity date if applicable (YYYY-MM-DD)
    """
    payload = {
        "policy_name": policy_name, "insurer": insurer, "type": type,
        "sum_assured": sum_assured, "premium": premium,
        "premium_frequency": premium_frequency, "start_date": start_date,
    }
    if maturity_date:
        payload["maturity_date"] = maturity_date
    return _fmt(_post("/insurance/add", payload))


# ═══════════════════════════════════════════════════════════
#  PPF — Actions
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def add_ppf(bank: str, account_number: str, opening_date: str) -> str:
    """Add a PPF account.

    Args:
        bank: Bank/PO name
        account_number: PPF account number
        opening_date: Account opening date (YYYY-MM-DD)
    """
    return _fmt(_post("/ppf/add", {
        "bank": bank, "account_number": account_number, "opening_date": opening_date,
    }))


@mcp.tool()
def add_ppf_contribution(ppf_id: str, amount: float, date: str) -> str:
    """Add a contribution to a PPF account.

    Args:
        ppf_id: PPF account ID
        amount: Contribution amount (INR)
        date: Contribution date (YYYY-MM-DD)
    """
    return _fmt(_post(f"/ppf/{ppf_id}/contribution", {"amount": amount, "date": date}))


# ═══════════════════════════════════════════════════════════
#  NPS — Actions
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def add_nps(pran: str, fund_manager: str, scheme: str) -> str:
    """Add an NPS account.

    Args:
        pran: PRAN (Permanent Retirement Account Number)
        fund_manager: Fund manager name (e.g., SBI, HDFC, ICICI)
        scheme: Scheme choice (e.g., Tier I - Active Choice)
    """
    return _fmt(_post("/nps/add", {
        "pran": pran, "fund_manager": fund_manager, "scheme": scheme,
    }))


@mcp.tool()
def add_nps_contribution(nps_id: str, amount: float, date: str) -> str:
    """Add a contribution to an NPS account.

    Args:
        nps_id: NPS account ID
        amount: Contribution amount (INR)
        date: Contribution date (YYYY-MM-DD)
    """
    return _fmt(_post(f"/nps/{nps_id}/contribution", {"amount": amount, "date": date}))


# ═══════════════════════════════════════════════════════════
#  STANDING INSTRUCTIONS — Actions
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def add_si(bank: str, beneficiary: str, amount: float, frequency: str,
           start_date: str, end_date: str, alert_days: int = 30) -> str:
    """Add a standing instruction (auto-pay mandate).

    Args:
        bank: Bank name
        beneficiary: Payee/beneficiary name
        amount: Payment amount (INR)
        frequency: monthly, quarterly, yearly
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        alert_days: Days before expiry to alert (default: 30)
    """
    return _fmt(_post("/standing-instructions/add", {
        "bank": bank, "beneficiary": beneficiary, "amount": amount,
        "frequency": frequency, "start_date": start_date,
        "end_date": end_date, "alert_days": alert_days,
    }))


# ═══════════════════════════════════════════════════════════
#  ADVISOR — Business Line News & Insights
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_todays_market_news() -> str:
    """Get today's Business Line articles from key financial sections.

    Scrapes articles from: Markets, Stock Markets, Portfolio, Money & Banking,
    Economy, and Companies sections of thehindubusinessline.com.

    Returns article titles, summaries, sections, and URLs.
    Use this to understand what's happening in Indian markets today.
    """
    return _fmt(_get("/advisor/articles"))


@mcp.tool()
def get_portfolio_insights() -> str:
    """Get personalized financial insights from today's Business Line news.

    Analyzes today's articles against your portfolio holdings and returns:
    - Articles mentioning your stocks (with sentiment: positive/negative/neutral)
    - Market-moving headlines (SENSEX, NIFTY, RBI, crude, rupee)
    - Sector impacts
    - Each insight includes: headline, stocks_affected, sentiment, action, urgency

    Call this to get a quick briefing of what matters for YOUR portfolio today.
    """
    return _fmt(_get("/advisor/insights"))


@mcp.tool()
def refresh_market_news() -> str:
    """Force re-scrape today's Business Line articles and regenerate insights.

    Use this if you want the latest articles (e.g., after market hours when
    new articles may have been published).
    """
    return _fmt(_post("/advisor/refresh"))


if __name__ == "__main__":
    mcp.run()
