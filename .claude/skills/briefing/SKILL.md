---
name: briefing
description: Generate a comprehensive, detailed market briefing from Business Line, The Hindu, Moneycontrol, and Google News. Use when user asks for market news, daily briefing, stock recommendations, 52-week low screening, or financial analysis.
user_invocable: true
---

# Daily Market Briefing

Generate a comprehensive market briefing from the past 7 days of Business Line + The Hindu + Moneycontrol + Google News articles.

**Key output: An actionable stock report with buy/sell recommendations, 52-week low screening, broker calls, and per-stock deep analysis — all in clean, non-overlapping sections.**

**IMPORTANT: The entire briefing MUST be displayed as your text response in the terminal.** The user reads the briefing in their terminal — do NOT hide content behind "see the saved file" or output a summary instead of the full report. The HTML file saved at the end is just a copy for later reference.

## Steps

### 1. Authentication

Generate auth token from the DOCKER container (port 9999):
```bash
docker exec pl-dashboard python3 -c "
import sys
sys.path.insert(0, '/app/backend')
from app.auth import create_session_token, ALLOWED_EMAILS
email = ALLOWED_EMAILS[0] if ALLOWED_EMAILS else 'admin@local'
token = create_session_token(email, 'CLI')
print(token)
"
```
Use as `Authorization: Bearer <token>` on ALL API calls to `localhost:9999`.

### 2. Data Fetching (run all in parallel)

```bash
# Articles (past 7 days, all sources)
curl -s http://localhost:9999/api/advisor/articles -H "Authorization: Bearer $TOKEN"

# Portfolio holdings
curl -s http://localhost:9999/api/portfolio/stock-summary -H "Authorization: Bearer $TOKEN"

# Advisor insights
curl -s http://localhost:9999/api/advisor/insights -H "Authorization: Bearer $TOKEN"

# Market ticker (GIFT Nifty, Sensex, Nifty, crude, gold, USDINR)
curl -s http://localhost:9999/api/market-ticker -H "Authorization: Bearer $TOKEN"
```

If articles list is empty, refresh first: `curl -s -X POST http://localhost:9999/api/advisor/refresh -H "Authorization: Bearer $TOKEN"`

### 3. Stock Technical Analysis

Fetch 1-year price history for EVERY portfolio stock (held + 0-unit watchlist):
```bash
curl -s "http://localhost:9999/api/stock/SYMBOL/history?exchange=NSE&period=1y" -H "Authorization: Bearer $TOKEN"
```
Compute from candles: 52-week high/low, % from low, 50-SMA, 200-SMA, RSI(14), trend direction.

### 4. Deep Stock Research (parallel agents)

Launch parallel Agent tool calls in batches of 10-12 stocks:

- **Round 1**: `"{STOCK} NSE stock latest news analyst target price {year}"` — news + analyst views
- **Round 2**: `"{STOCK} quarterly results revenue profit margin Q3 Q4 FY{year}"` — financials
- **Round 3**: `"{STOCK} stock risks concerns downgrade sell {year}"` — bear case

Also search for NEW opportunities:
```
"best stocks to buy India {month} {year} broker recommendations"
"midcap largecap stocks 52 week low India {month} {year} value buy"
"India defensive stocks {month} {year} analyst picks"
```

### 5. Article Analysis

Read the BODY of every article. Extract: broker calls with target prices, stock-to-buy articles, F&O strategies, earnings results, FII/DII flows, policy changes, IPOs, 52-week low lists, deal amounts.

### 6. Generate and Display Briefing

Produce the briefing using the Output Format below. **Output the FULL briefing as your text response** — the user reads it directly in the terminal. Do NOT summarize, truncate, or say "see the HTML file for details." The terminal IS the primary reading experience.

**Write each section as a direct text response to the user.** The markdown you output to the terminal is the briefing.

### 7. Save HTML (single file, synced to Drive)

After outputting the full briefing to the terminal, save the same content as HTML:
```bash
curl -s -X POST http://localhost:9999/api/advisor/analysis-html \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"markdown\": \"<the full briefing markdown>\"}"
```
This saves to `dumps/temp/analysis/DD-MM-YY/HH_MMhrs.html` with full styling and syncs to Google Drive. Report the path and Drive sync status to the user.

**The HTML is a copy for later reference — the terminal output is the primary deliverable.**

---

## Output Format

The briefing has **9 sections**, ordered from most urgent to reference material. Each section covers ONE topic — no duplication across sections.

```
> Sources: X from Business Line, Y from The Hindu, Z from Moneycontrol, W from Google News
> Generated: YYYY-MM-DD HH:MM IST
```

---

### SECTION 1: What To Do Today

*The most actionable section — read this first. Every item has a specific price level.*

**Immediate Actions:**
- **[BUY]**: Stock @ price range, SL, target, 1-line reason
- **[SELL/TRIM]**: Stock @ price, reason
- **[WATCH]**: Stock — trigger condition

**This Week's Calendar:**
| Date | Event | Stocks Affected | Expected Impact |
|------|-------|----------------|-----------------|

**Capital Deployment Plan:**
```
TRANCHE 1 (X%): Deploy now — list stocks
TRANCHE 2 (X%): Deploy at [index level] — list stocks
TRANCHE 3 (X%): Reserve for further dips
```

---

### SECTION 2: Market Dashboard

*All market numbers in one place. No stock-specific analysis here — just the scoreboard.*

| Indicator | Value | Day Change | Week Change | Month Change | Key Context |
|-----------|-------|------------|-------------|--------------|-------------|
| GIFT Nifty | | | | | Gap up/down signal |
| Sensex | | | | | Consecutive weekly gains/losses |
| Nifty 50 | | | | | |
| Rupee/USD | | | | | vs all-time low |
| Brent Crude | | | | | Impact on India |
| Gold (MCX) | | | | | |
| Silver (MCX) | | | | | |
| 10Y G-Sec Yield | | | | | vs recent range |
| Forex Reserves | | | | | Import cover days |

**Flows:**
- FII: Daily / Weekly / Monthly cumulative (Rs Cr + $ equivalent)
- DII: Daily / Weekly / Monthly cumulative
- Consecutive selling/buying streak

**Market Breadth:** Advances / Declines / Unchanged. Stocks at 52-week low count. Top 3 gainers + top 3 losers with % and reason.

---

### SECTION 3: Key Events & Macro Context

*What happened this week and why it matters. Organized by theme, not by day.*

For each major theme (geopolitical, policy, regulatory, global), write a **3-5 sentence paragraph** covering: what happened, who's affected, what to expect next.

Themes to always cover:
- Geopolitical (wars, sanctions, trade)
- Government policy (tax changes, duty changes, subsidies)
- RBI / monetary policy
- Global markets (US Fed, China, oil, currencies)
- Regulatory (SEBI, RBI actions on specific companies)

---

### SECTION 4: Broker Calls & Article Picks

*Every analyst/broker recommendation extracted from this week's articles. Pure extraction — no editorializing.*

| Stock | Call | Brokerage | Target | Stop Loss | Upside | Source Article |
|-------|------|-----------|--------|-----------|--------|---------------|

Include: "Broker's call" articles, "Stock to buy today", "F&O Strategy", "Buy/sell/hold?" articles, analyst upgrades/downgrades with specific targets. One row per call.

---

### SECTION 5: Buy & Sell Recommendations

*Your synthesized recommendations combining technicals + fundamentals + news + broker calls. Grouped by conviction.*

#### HIGHEST CONVICTION
| # | Stock | CMP | Entry Zone | Target (Source) | Upside | Stop Loss | Catalyst | Key Risk |
|---|-------|-----|------------|-----------------|--------|-----------|----------|----------|

#### HIGH CONVICTION
Same table.

#### MEDIUM CONVICTION
Same table.

#### SPECULATIVE
Same table.

#### SELL / TRIM / AVOID
| # | Stock | CMP | Action | Reason |
|---|-------|-----|--------|--------|

*Every stock from Sections 4 + 8 should map to a conviction tier here. This is the master recommendation list.*

---

### SECTION 6: 52-Week Low Screener

*Exhaustive list of stocks near 52-week lows from portfolio + articles + web searches.*

#### LARGECAP (Market Cap > Rs.50,000 Cr)
| # | Stock | CMP | 52W Low | 52W High | % From Low | RSI | Trend | Analyst View | Verdict |
|---|-------|-----|---------|----------|------------|-----|-------|-------------|---------|

#### MIDCAP (Rs.10,000 — Rs.50,000 Cr)
Same table.

#### SMALLCAP (< Rs.10,000 Cr)
Same table.

#### AVOID Despite Low
| Stock | CMP | % From Low | Why Avoid |
|-------|-----|------------|-----------|

---

### SECTION 7: Sector Analysis

*One paragraph per sector (5-8 sentences). Include: what happened, key stocks affected, outlook, verdict.*

Cover: Oil & Energy, Banking, IT Services, Pharma, Auto, Metals, Infra, FMCG, Insurance, Telecom, Defence, Renewables.

End each sector paragraph with: **Sector verdict: OVERWEIGHT / NEUTRAL / UNDERWEIGHT**

---

### SECTION 8: Stock-by-Stock Deep Analysis

*The longest section. Every portfolio stock + 10-15 new ideas. All per-stock info lives here — technicals, fundamentals, news, verdict. NOT duplicated elsewhere.*

**Group into:**
1. Currently Held Stocks (Qty > 0)
2. Watchlist Stocks (Qty = 0) — top 20-25 most relevant
3. New Stocks Worth Considering — at least 10-15 not in portfolio

**For each stock, use this compact format:**

**STOCK_NAME (SYMBOL)** — CMP: Rs.XXX | 52W: Rs.LOW — Rs.HIGH (X% from low) | RSI: XX | Trend: UP/DOWN/SIDE

| Field | Value |
|-------|-------|
| Verdict | **BUY/SELL/HOLD/ADD/TRIM/AVOID** |
| Conviction | HIGH / MEDIUM / LOW |
| Target | Rs.XXX (X% upside) — Brokerage source |
| Stop Loss | Rs.XXX |
| Entry Plan | Tranche 1 at X, Tranche 2 at Y |

**Analysis** (100-200 words covering):
- Latest quarter: Revenue, PAT, margins (YoY)
- Key news/catalyst this week
- Bull case (quantified)
- Bear case (quantified)
- Why this verdict

---

### SECTION 9: Corporate Actions, IPOs & MF

*Reference section for deals, IPOs, dividends, MF changes.*

#### Deals & Corporate Actions
| Company | Action | Amount | Date | Impact |
|---------|--------|--------|------|--------|

#### IPOs
| Company | Size | Price Band | Subscription | Listing Date | Recommendation |
|---------|------|-----------|--------------|-------------|----------------|

#### Mutual Fund & SIP
| Item | Detail | Recommendation |
|------|--------|----------------|

---

## Section Rules (NO DUPLICATION)

| Information | Lives in Section | NOT in |
|------------|-----------------|--------|
| Market index/currency/commodity numbers | 2 (Dashboard) | Anywhere else |
| Macro events, policy, geopolitics | 3 (Events & Macro) | 2 or 7 |
| Raw broker calls from articles | 4 (Broker Calls) | 5 or 8 |
| Synthesized buy/sell recommendations | 5 (Recommendations) | 4 or 8 |
| 52-week low screening tables | 6 (Screener) | 5 or 8 |
| Sector-level analysis | 7 (Sectors) | 8 |
| Per-stock deep analysis (technicals, fundamentals, verdict) | 8 (Deep Analysis) | 5, 6, or 7 |
| Deals, IPOs, MF changes | 9 (Corporate Actions) | 3 or 8 |
| Action items with price levels | 1 (What To Do) | Summary of 5 |

## Critical Guidelines
- **SINGLE PASS RULE**: Each fact appears in exactly ONE section. Cross-reference with "see Section X" if needed.
- **DETAIL IS MANDATORY** — comprehensive analytical briefing, NOT a dashboard
- **52-WEEK LOW SCREENING IS MANDATORY** — exhaustive list across all cap sizes
- **NEW STOCK RECOMMENDATIONS ARE MANDATORY** — at least 10-15 new ideas beyond portfolio
- **BROKER CALLS FROM ARTICLES ARE MANDATORY** — extract every BL/TH/MC broker recommendation
- Read EVERY article body. Extract specific numbers, names, amounts, dates.
- Every stock = clear verdict (BUY/SELL/HOLD/AVOID/WATCH) with reasoning
- Connect dots across articles: crude up -> OMC margins down -> ONGC up -> paints input cost up
- Include source attribution: "(BL)", "(TH)", "(MC)", "(GN-ET)" after each insight
- Quantify everything: Rs. amounts, % changes, target prices, timeframes
- Use parallel Agent tool calls to research stocks in batches of 10-12 for speed
