---
name: briefing
description: Generate a comprehensive, detailed market briefing from Business Line, The Hindu, and Google News. Use when user asks for market news, daily briefing, stock recommendations, or financial analysis.
user_invocable: true
---

# Daily Market Briefing

Generate a comprehensive, detailed market briefing from the past 7 days of Business Line + The Hindu + Google News articles. Focus on today's actionable items but include context from the week.

## Steps

### Authentication

1. **Generate auth token** — The API requires authentication:
   ```bash
   cd /Users/lenin/Desktop/workspace/pl/backend && python3 -c "
   from app.auth import create_session_token, ALLOWED_EMAILS
   email = ALLOWED_EMAILS[0] if ALLOWED_EMAILS else 'admin@local'
   token = create_session_token(email, 'CLI')
   print(token)
   "
   ```
   Use this token as `Authorization: Bearer <token>` header on ALL API calls below.

### Data Fetching

2. **Fetch articles** from the backend (past 7 days from all sources):
   ```bash
   curl -s http://localhost:9999/api/advisor/articles -H "Authorization: Bearer $TOKEN"
   ```
   Returns a JSON array with fields: title, summary, body (up to 3000 chars), section, url, source ("Business Line", "The Hindu", or "Google News (SourceName)"), date (ISO format).
   Articles span the past 7 days via RSS feeds + page scraping + Google News RSS search.

3. If the articles list is empty or the backend is down, try refreshing first:
   ```bash
   curl -s -X POST http://localhost:9999/api/advisor/refresh -H "Authorization: Bearer $TOKEN"
   ```

4. **Fetch portfolio holdings** for context:
   ```bash
   curl -s http://localhost:9999/api/portfolio/stock-summary -H "Authorization: Bearer $TOKEN"
   ```

5. **Fetch advisor insights** (keyword-matched or AI-generated):
   ```bash
   curl -s http://localhost:9999/api/advisor/insights -H "Authorization: Bearer $TOKEN"
   ```

6. **Fetch GIFT Nifty / market ticker data** for forecasting:
   ```bash
   curl -s http://localhost:9999/api/market-ticker -H "Authorization: Bearer $TOKEN"
   ```
   Returns tickers array with: key, label, price, change, change_pct, week_change_pct, month_change_pct. Includes GIFT Nifty, Sensex, Nifty50, crude oil, gold, silver, USDINR.

### Article Analysis

7. **Read the BODY of every article** — not just headlines. The `body` field contains actual article text. Extract:
   - Specific investment amounts ("Apollo-led funds invest $500M in Adani Energy")
   - Company names involved in deals, mergers, partnerships
   - Negative news — lawsuits, frauds, earnings misses, downgrades
   - Analyst recommendations with target prices
   - Government policy changes with affected companies
   - IPO details with subscription recommendations
   - Earnings results with revenue/profit figures and YoY comparisons
   - Management commentary and forward guidance
   - Regulatory actions (SEBI, RBI, IRDAI, TRAI)
   - Foreign investment flows (FII/DII daily and weekly figures)

### Briefing Generation

8. **Produce the briefing** using the Output Format below.

9. **Generate PDF** — After producing the briefing markdown, save it as a PDF:
   ```bash
   curl -s -X POST http://localhost:9999/api/advisor/briefing-pdf \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d "{\"markdown\": \"<the full briefing markdown>\"}"
   ```
   Report the PDF file path to the user.

## Output Format

Start with:
> Sources: X articles from Business Line, Y articles from The Hindu, Z articles from Google News
> Generated: YYYY-MM-DD HH:MM IST

### Market Overview
Detailed bullets with context. Format: "**METRIC**: VALUE (CHANGE%) — context sentence."
- **GIFT Nifty**: 23,718 (-0.9%) — trading at +79 pts premium to Nifty close, signaling a GAP UP opening. Premium has widened from +40 pts at Asian open, suggesting buying interest from global funds.
- **Sensex**: VALUE (CHANGE%). **Nifty**: VALUE (CHANGE%). Include intraday high/low if available.
- **Rupee**: VALUE vs USD. Include weekly trend. "Rupee at 83.42 (-0.15%), weakest in 3 weeks on dollar strength and crude spike."
- **Brent Crude**: $XX.XX (CHANGE%). Impact on India: "Every $10 rise adds Rs.1.1L cr to import bill."
- **Gold**: Rs.XX,XXX/10g (CHANGE%). Include MCX and international price.
- **Top gainers**: 4-5 names with % and reason. "Tata Motors +4.2% (JLR strong Q4 deliveries), ONGC +3.1% (crude rally)"
- **Top losers**: 4-5 names with % and reason.
- **FII/DII flows**: Daily + weekly cumulative. "FII: -Rs.2,340 cr (net sellers 5th day). DII: +Rs.3,100 cr (absorbed selling)."
- **Market breadth**: Advance/decline ratio if available.

### Actionable Stock Ideas
| Stock | Signal | Action | Source | Detailed Analysis |
|-------|--------|--------|--------|-------------------|
- **Detailed Analysis column: 25-40 words.** Include: specific catalyst, quantified impact, target price, holding value if in portfolio, timeframe, risk.
  Example: "USFDA issued VAI classification for Andhra plant — removes key overhang. Holding Rs.1.57L. Consensus target Rs.1,400 (18% upside). Accumulate on dips below Rs.1,180. Risk: FDA reinspection."
- Signal: BULLISH, BEARISH, NEUTRAL, BUY PUT, BOOK PROFIT, BREAKOUT, BREAKDOWN
- Action: BUY, SELL, HOLD, ADD, TRIM, EXIT, AVOID, WATCH, SL@PRICE — always filled
- Include ALL stocks mentioned in articles with recommendations
- Group by conviction: HIGH conviction first, then MEDIUM, then LOW

### Corporate Actions & Deals
| WHO | WHAT | HOW MUCH | WHY IT MATTERS |
|-----|------|----------|----------------|
- **WHO**: Full entity names with relationship. "Apollo Global Management -> Adani Energy Solutions (via subsidiary)"
- **WHAT**: Specific action with full context. "Issued secured notes to refinance existing debt on transmission unit. Replaces 9.5% bonds maturing 2025 with 7.8% notes due 2030."
- **HOW MUCH**: Currency + amount + context. "$500M (Rs.4,150 cr at current rates). Represents 15% of Adani Energy's total debt."
- **WHY IT MATTERS**: 15-25 words with investor implication. "Signals institutional confidence in India power infra. Lower interest cost improves EBITDA margins by ~80bps. Positive for Adani Green too."

### Negative News & Risks
| WHAT | WHO | HOW BAD | ACTION |
|------|-----|---------|--------|
- **WHAT**: Full event description with context. "US initiates Section 301 trade investigation covering imports from 16 countries including India. Targets $150B+ in bilateral trade."
- **WHO**: Name ALL affected companies and sectors. "Direct hit: Textiles (Welspun, Page Industries, KPR Mill), Auto (Tata Motors, Bajaj Auto exports), Steel (JSW, Tata Steel), Pharma (Sun, Dr Reddy's API exports)"
- **HOW BAD**: Quantify with multiple metrics. "Potential 25% tariff on $30B Indian exports. Rs.3.6L cr fiscal hit. CAD could widen from 1.2% to 2% GDP. INR depreciation pressure to 84.5."
- **ACTION**: Specific recommendation. "TRIM export-heavy holdings (Page, Welspun). WATCH Tata Motors for JLR UK exposure clarity. AVOID new positions in textile exporters until tariff rates announced (expected April 15)."

### Sector Impacts
Detailed paragraph per sector (3-5 sentences each). Cover all relevant sectors:

- **Oil & Energy**: Direction + catalyst + affected stocks + recommendation. "BULLISH. Brent above $90 boosts upstream (ONGC +3%, Oil India +2.5%) but crushes downstream OMCs (BPCL -4%, HPCL -5%). Government may delay fuel price revision ahead of state elections. Avoid OMCs; accumulate ONGC on dips."
- **Banking & Finance**: NPA trends, credit growth, NIM outlook, rate cycle impact.
- **IT Services**: Deal wins, attrition, margin guidance, USD/INR impact.
- **Pharma**: USFDA actions, API pricing, domestic formulation growth.
- **Auto**: Monthly sales data, EV transition, commodity cost impact.
- **Metals & Mining**: Global commodity prices, China demand, anti-dumping duties.
- **Real Estate & Infra**: Project wins, order book, government capex.
- **FMCG & Consumer**: Rural recovery, input cost inflation, volume vs value growth.
- **Insurance**: Regulatory changes, premium growth, claims ratio.
- **Telecom**: ARPU trends, 5G rollout, spectrum costs.

### MF / SIP / IPO
| Item | Type | Detail | Recommendation |
|------|------|--------|----------------|
- **Detail**: 20-30 words with specific figures. "Parag Parikh Flexi Cap NAV Rs.72.34 (+1.2%). AUM crosses Rs.50,000 cr. Fund maintains 25% international allocation — hedges against INR weakness."
- **Recommendation**: Specific action. "Continue SIP. Lump sum investors wait for Nifty correction below 22,000."
- Cover: NFO launches, NAV milestones, category performance, SIP flow data, IPO listings and upcoming IPOs with subscription recommendations.

### Macro & Geopolitical
Detailed bullets with chain-of-impact analysis:
- **Crude Oil**: Price, trend, India-specific impact chain. "$92.27 (+2.3%). Iran tensions + OPEC cuts. India impact: OMC losses mount, subsidy bill rises Rs.15,000 cr, CAD widens. RBI may need to defend rupee via reserves."
- **US Fed / Global rates**: Latest stance, market expectations, India spillover.
- **China**: PMI data, property crisis, commodity demand impact on Indian metals.
- **Geopolitical**: Wars, sanctions, trade disputes with specific India impact.
- **Domestic macro**: GDP growth, IIP, CPI, PMI data with trend analysis.
- **RBI**: Policy stance, liquidity management, forex reserves.

### Portfolio Impact
| Stock | Current Value | 1D Change | Signal | Action | Detailed Analysis (30-50 words) |
|-------|--------------|-----------|--------|--------|----------------------------------|
- **Detailed Analysis**: Include the specific catalyst from articles, quantified impact, what to watch for, and timeline.
  Example: "Brent >$90 devastates refining margins — GRM dropped from $12 to $6/bbl in Q4. Stock down 4% today. Moody's flagged margin volatility in March report. TRIM 30% position if crude stays above $90 for 2 weeks. Next catalyst: Q4 results April 25."
- ONLY stocks with news. List holdings with no news separately at the end.
- Sort by action urgency: TRIM/EXIT first, then ADD, then HOLD, then WATCH.
- Include current holding value, day change, and cumulative P&L.

### Weekly Trends
Since articles span 7 days, identify emerging patterns:
- Stocks with 3+ articles in the week (building momentum or trouble)
- Sectors with shifting sentiment (was bearish, now turning)
- Regulatory trends (multiple actions in same area)
- FII/DII flow patterns over the week

### Key Takeaway
3-5 bullet points of what to DO today, not what happened:
- **Immediate actions**: Stocks to buy/sell/trim TODAY with specific price levels
- **This week**: What to watch for, upcoming events (earnings, policy, data releases)
- **Risk management**: Position sizing advice, stop-loss levels, hedge suggestions

## Critical Guidelines
- **DETAIL IS MANDATORY** — this is a comprehensive analytical briefing, NOT a dashboard. Include context, analysis, and reasoning.
- Read EVERY article body. Extract specific numbers, names, amounts, dates.
- Cover ALL articles from ALL three sources (BL, TH, Google News)
- Every stock/sector = clear verdict (BUY/SELL/HOLD/AVOID/WATCH) with reasoning
- Connect dots across articles: crude up -> OMC margins down -> ONGC up -> paints input cost up
- Flag urgent items with **[ACTION TODAY]** and include specific price levels
- **GIFT Nifty is mandatory** as first Market Overview indicator
- Include source attribution: "(BL)", "(TH)", "(GN-ET)", "(GN-Mint)" after each insight
- Quantify everything: Rs. amounts, % changes, target prices, timeframes
- Portfolio impact section must map EVERY article with portfolio relevance to specific holdings
