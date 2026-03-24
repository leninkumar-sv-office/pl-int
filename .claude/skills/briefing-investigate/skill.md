---
name: briefing-investigate
description: Deep-dive investigation into a single stock or mutual fund — 1 month of news, price action, fundamentals, bull/bear cases, and clear verdict. Use when user asks to investigate, analyze, or research a specific stock or mutual fund.
user_invocable: true
---

# Stock/MF Deep Investigation

Perform a comprehensive, deeply researched investigation into a single stock or mutual fund. Covers 1 month of news, price action, fundamentals, analyst views, and produces a clear buy/sell/hold verdict with full reasoning.

## Step 0: Parse Input

The user may provide a stock or MF name as an argument: `/briefing-investigate HDFC Bank`

- **If input is provided**: use it as the investigation target
- **If no input**: ask the user: "Which stock or mutual fund would you like me to investigate?"
- Wait for the user's response before proceeding.

## Step 1: Authentication

Generate an auth token for API calls:
```bash
cd /Users/lenin/Desktop/workspace/pl/backend && python3 -c "
from app.auth import create_session_token, ALLOWED_EMAILS
email = ALLOWED_EMAILS[0] if ALLOWED_EMAILS else 'admin@local'
token = create_session_token(email, 'CLI')
print(token)
"
```
Use this token as `Authorization: Bearer <token>` header on ALL API calls.

## Step 2: Auto-Detect Stock vs Mutual Fund

Fetch both datasets to identify the target:

```bash
# Stock holdings
curl -s http://localhost:9999/api/portfolio/stock-summary -H "Authorization: Bearer $TOKEN"

# MF holdings
curl -s http://localhost:9999/api/mutual-funds/dashboard -H "Authorization: Bearer $TOKEN"
```

**Match the user input** against:
- Stock names, symbols (e.g., "HDFC Bank" matches symbol "HDFCBANK" or name containing "HDFC Bank")
- MF scheme names (e.g., "Parag Parikh" matches scheme name containing it)

**If matched as stock**: proceed with stock investigation flow
**If matched as MF**: proceed with MF investigation flow
**If matched in both or ambiguous**: ask user to clarify — "Did you mean the stock or the mutual fund?"
**If not found in portfolio**: proceed anyway as a non-held stock/MF investigation (search for it on web)

Record whether the target is HELD (qty > 0), PREVIOUSLY HELD (qty = 0 in portfolio), or NOT IN PORTFOLIO.

## Step 3: Fetch Targeted Data

### For Stocks:
```bash
# 1-year price history
curl -s "http://localhost:9999/api/stock/SYMBOL/history?exchange=NSE&period=1y" -H "Authorization: Bearer $TOKEN"

# Market ticker (light context)
curl -s http://localhost:9999/api/market-ticker -H "Authorization: Bearer $TOKEN"

# Backend articles (7 days) — filter for target stock
curl -s http://localhost:9999/api/advisor/articles -H "Authorization: Bearer $TOKEN"
```
If articles are empty, refresh first:
```bash
curl -s -X POST http://localhost:9999/api/advisor/refresh -H "Authorization: Bearer $TOKEN"
```

Filter articles for the target stock by scanning `title`, `summary`, and `body` fields for the stock name, symbol, or related keywords.

### For Mutual Funds:
```bash
# MF dashboard with NAV data
curl -s http://localhost:9999/api/mutual-funds/dashboard -H "Authorization: Bearer $TOKEN"

# Market ticker (light context)
curl -s http://localhost:9999/api/market-ticker -H "Authorization: Bearer $TOKEN"

# Backend articles (7 days) — filter for target MF/AMC
curl -s http://localhost:9999/api/advisor/articles -H "Authorization: Bearer $TOKEN"
```

## Step 4: Deep WebSearch (9 Rounds — 1 Month Lookback)

This is the most critical step. Search broadly and deeply for the target.

### For Stocks:

**Round 1 — Latest news & analyst views:**
```
WebSearch: "{STOCK_NAME} NSE stock latest news analyst target price 2026"
```

**Round 2 — Quarterly results & financials:**
```
WebSearch: "{STOCK_NAME} quarterly results revenue profit margin Q3 Q4 FY2026"
```

**Round 3 — Risks, concerns & bear case:**
```
WebSearch: "{STOCK_NAME} stock risks concerns downgrade sell 2026"
```

**Round 4 — Sector outlook & competitive position:**
```
WebSearch: "{STOCK_NAME} sector outlook competition market share India"
```

**Round 5 — Promoter activity & institutional holdings:**
```
WebSearch: "{STOCK_NAME} promoter holding FII DII stake change 2026"
```

**Round 6 — Historical price catalysts (past month):**
```
WebSearch: "{STOCK_NAME} stock price movement reason why rally fall March 2026"
```

**Round 7 — Business Line coverage:**
```
WebSearch: "{STOCK_NAME} site:thehindubusinessline.com"
```

**Round 8 — The Hindu coverage:**
```
WebSearch: "{STOCK_NAME} site:thehindu.com business"
```

**Round 9 — Moneycontrol coverage:**
```
WebSearch: "{STOCK_NAME} site:moneycontrol.com"
```

### For Mutual Funds:

Replace rounds with MF-specific searches:

**R1:** `"{MF_NAME} mutual fund NAV performance 2026"`
**R2:** `"{MF_NAME} mutual fund portfolio changes top holdings 2026"`
**R3:** `"{MF_NAME} mutual fund risks outflow redemption"`
**R4:** `"{MF_NAME} vs {CATEGORY} category comparison returns"`
**R5:** `"{AMC_NAME} fund manager commentary strategy AUM"`
**R6:** `"{MF_NAME} mutual fund SIP recommendation review"`
**R7:** `"{MF_NAME} site:thehindubusinessline.com"`
**R8:** `"{MF_NAME} site:thehindu.com"`
**R9:** `"{MF_NAME} site:moneycontrol.com OR site:valueresearchonline.com"`

## Step 5: WebFetch Full Articles

From all WebSearch results, identify the **3-5 most relevant and substantive articles** and read them in full using WebFetch. Prioritize:
- Recent analyst reports with target prices
- Quarterly results coverage with detailed numbers
- Investigative pieces on risks/concerns
- Business Line and The Hindu articles (trusted Indian financial sources)

## Step 6: Iterative Reasoning

Do NOT finalize a verdict until you have gone through 3 reasoning iterations:

- **Iteration 1**: Form initial thesis based on price history + news + financials. What does the evidence suggest?
- **Iteration 2**: Challenge the thesis — actively search for counter-arguments. If bullish, find the bear case. If bearish, find the bull case. Do additional WebSearch if needed.
- **Iteration 3**: Synthesize final verdict incorporating ALL evidence. Assign conviction level.

You must be convinced of your own explanation before writing the final output.

## Step 7: Generate Output

### Output Format for Stocks:

```markdown
> Investigation: {STOCK_NAME} ({SYMBOL}) — {EXCHANGE}
> Portfolio Status: {HELD / PREVIOUSLY HELD / NOT IN PORTFOLIO}
> Sources: X backend articles, Y web searches, Z full articles read
> Generated: YYYY-MM-DD HH:MM IST
```

#### Position Summary
If held: Qty, avg buy price, current price, current value, unrealized P&L (Rs. and %), realized P&L from sold lots, lot-wise breakdown.
If previously held (0 qty): Last sold price, total realized P&L, when exited.
If not in portfolio: "Not in portfolio — evaluating for entry."

#### Verdict
```
**{BUY / SELL / HOLD / ADD / TRIM / EXIT / ACCUMULATE / AVOID / RE-ENTER}**
Conviction: {HIGH / MEDIUM / LOW}
Target Price: Rs.{XXX} ({X}% upside) — {timeframe}
Stop Loss: Rs.{XXX} ({X}% below current)
```
One-paragraph summary (3-4 sentences) of WHY this verdict.

#### Price Action & Technicals
From 1-year price history data:
- **52-week range**: Rs.XXX — Rs.XXX. Current price at X% of range.
- **Trend**: 1M (up/down X%), 3M (up/down X%), 6M (up/down X%)
- **Key support levels**: Rs.XXX, Rs.XXX (from price action)
- **Key resistance levels**: Rs.XXX, Rs.XXX
- **Volume trend**: Increasing/decreasing conviction
- **Pattern**: Breakout / breakdown / consolidation / double bottom / etc.

#### Fundamentals
- Latest quarterly results: Revenue Rs.XXX cr (YoY X%, QoQ X%), PAT Rs.XXX cr, margins X%
- EPS: Rs.XXX (trailing), Rs.XXX (forward estimate)
- PE: Current X vs 5-year avg X vs sector avg X
- Debt/Equity: X. Interest coverage: X
- ROE: X%, ROCE: X%
- Management guidance / forward commentary

#### News Timeline (Past 1 Month)
| Date | Source | Headline | Impact | Sentiment |
|------|--------|----------|--------|-----------|
Sorted newest first. Include 15-25 significant entries. Source = (BL), (TH), (MC), (ET), (GN-source), etc.
- **Impact**: 10-20 words on what it means for the stock
- **Sentiment**: Positive / Negative / Neutral

#### Analyst Views
| Brokerage / Source | Rating | Target Price | Date | Key Thesis (15-25 words) |
|-------------------|--------|-------------|------|--------------------------|
All analyst calls found in searches. Include consensus target if available.

#### Bull Case
3-5 specific catalysts with quantified upside:
- Each point: specific catalyst + financial impact + price implication
- Best-case target: Rs.XXX (X% upside) — what needs to go right

#### Bear Case
3-5 specific risks with quantified downside:
- Each point: specific risk + financial impact + price implication
- Worst-case floor: Rs.XXX (X% downside) — what could go wrong

#### Competitive Landscape
Compare with 2-3 sector peers on:
| Metric | {TARGET} | Peer 1 | Peer 2 | Peer 3 |
|--------|----------|--------|--------|--------|
| Market Cap | | | | |
| PE Ratio | | | | |
| Revenue Growth | | | | |
| PAT Margin | | | | |
| ROE | | | | |

#### Final Analysis & Reasoning (150-300 words)
Synthesize bull vs bear. WHY you chose this verdict. What tipped the balance. How does the market context (bullish/bearish overall) affect this stock? Cross-reference with macro factors. What is the market pricing in vs what you believe? Where is the mispricing opportunity, if any?

#### Action Plan
Specific executable instructions:
- **If BUY/ADD/ACCUMULATE**: At what price to buy, how many tranches, what % of portfolio, what price confirms the thesis
- **If SELL/TRIM/EXIT**: At what price to sell, urgency (today vs this week), where to redeploy
- **If HOLD**: What would change the verdict to BUY or SELL, key triggers to watch
- **Next catalyst**: Date and event (earnings, AGM, product launch, regulatory decision)
- **Invalidation**: What would make this thesis wrong — the "I was wrong if X happens" signal

### Output Format for Mutual Funds:

Same structure but with these replacements:

#### NAV & Performance (replaces Price Action & Technicals)
- Current NAV, 1M/3M/6M/1Y/3Y/5Y returns
- Returns vs benchmark and category average
- Rolling returns consistency
- Drawdown history

#### Portfolio Composition (replaces Fundamentals)
- Top 10 holdings with % allocation
- Recent changes in top holdings (added/removed)
- Sector allocation breakdown
- Market cap allocation (large/mid/small)
- Cash holding %

#### Category Comparison (replaces Competitive Landscape)
| Metric | {TARGET FUND} | Peer 1 | Peer 2 | Category Avg |
|--------|--------------|--------|--------|-------------|
| 1Y Return | | | | |
| 3Y CAGR | | | | |
| Expense Ratio | | | | |
| AUM | | | | |
| Sharpe Ratio | | | | |

#### Action Plan for MF
- SIP recommendation: Continue / Pause / Stop / Increase amount
- Lump sum: Yes at current NAV / Wait for correction to Rs.XXX
- Switch recommendation: If better alternatives exist in category

## Step 8: Generate HTML

Save the investigation as a styled HTML file:

```bash
curl -s -X POST http://localhost:9999/api/advisor/analysis-html \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"markdown\": \"<the full investigation markdown>\"}"
```

Report the HTML file path and Drive sync status to the user.

## Critical Rules

- **DEPTH IS MANDATORY** — this is a deep investigation, not a summary. Every section must have substance.
- **1-month lookback** — don't limit to just the past week. WebSearch is your tool for historical depth.
- **Read full articles** — WebFetch at least 3-5 articles. Snippets are not enough for an investigation.
- **Iterative reasoning** — form thesis, challenge it, then synthesize. Do NOT skip iteration 2 (the challenge).
- **Specific numbers** — real target prices from real analysts, actual quarterly figures, real PE ratios. Do not fabricate.
- **Both bull AND bear** — never present a one-sided analysis. Both cases must be compelling.
- **Source attribution** — cite sources: (BL), (TH), (MC), (ET), (Screener), (Trendlyne), etc.
- **Actionable** — the verdict section must be specific enough that the user can act on it immediately.
- **Market context** — note whether the broader market is helping or hurting this stock. A stock rising in a falling market is more impressive than one rising with the tide.
