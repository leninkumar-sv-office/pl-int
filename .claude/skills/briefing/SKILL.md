---
name: briefing
description: Generate a comprehensive daily market briefing from Business Line and The Hindu articles. Use when user asks for market news, daily briefing, stock recommendations, or financial analysis.
---

# Daily Market Briefing

Generate a comprehensive, detailed market briefing from the past 7 days of Business Line + The Hindu articles. Focus on today's actionable items but include context from the week.

## Steps

1. **Fetch articles** from the backend (past 7 days from both sources):
   ```bash
   curl -s http://localhost:9999/api/advisor/articles
   ```
   Returns a JSON array with fields: title, summary, body, section, url, source ("Business Line" or "The Hindu"), date (ISO format).
   Articles span the past 7 days via RSS feeds + page scraping.

2. **Fetch portfolio holdings** for context:
   ```bash
   curl -s http://localhost:9999/api/portfolio/stock-summary
   ```

3. **Fetch advisor insights** (keyword-matched or AI-generated):
   ```bash
   curl -s http://localhost:9999/api/advisor/insights
   ```

4. If the articles list is empty or the backend is down, try refreshing first:
   ```bash
   curl -s -X POST http://localhost:9999/api/advisor/refresh
   ```

5. **Fetch GIFT Nifty / market ticker data** for forecasting:
   ```bash
   curl -s http://localhost:9999/api/market-ticker
   ```
   This returns GIFT Nifty (GIFTNIFTY), Sensex, Nifty50, crude oil, gold, silver, USDINR with live prices and change %. Use GIFT Nifty to forecast next-day market direction (GIFT Nifty trades until 11:30 PM IST and signals where Indian markets will open).

6. **Read the BODY of every article** — not just headlines. The `body` field contains the actual article text (up to 3000 chars). Use this to extract:
   - Specific investment amounts ("Apollo-led funds invest $500M in Adani Energy")
   - Company names involved in deals, mergers, partnerships
   - Negative news — lawsuits, frauds, earnings misses, downgrades
   - Analyst recommendations with target prices
   - Government policy changes with affected companies
   - IPO details with subscription recommendations

7. **Produce the briefing** using the format below.

8. **Generate PDF** — After producing the briefing markdown, save it as a PDF:
   ```bash
   curl -s -X POST http://localhost:9999/api/advisor/briefing-pdf \
     -H "Content-Type: application/json" \
     -d "{\"markdown\": \"<the full briefing markdown>\"}"
   ```
   If the server endpoint is unavailable, generate it directly:
   ```python
   python3 -c "
   from backend.app.briefing_pdf import generate_briefing_pdf
   path = generate_briefing_pdf('''<briefing markdown>''')
   print(f'PDF saved: {path}')
   "
   ```
   Report the PDF file path to the user.

## Output Format

**CRITICAL: Be CONCISE. This is a dashboard, not an article. Max 10-15 words per bullet. Max 12 words per table cell. Use numbers and symbols, not sentences.**

Start with:
> Sources: X articles from Business Line, Y articles from The Hindu

### Market Overview
SHORT bullets only. No prose. Format: "METRIC: VALUE (CHANGE%)"
- **GIFT Nifty**: 23,718 (-0.9%) — +79 pts premium to Nifty close. GAP UP/DOWN/FLAT signal.
- Sensex: VALUE (CHANGE%). Nifty: VALUE (CHANGE%).
- Rupee: VALUE. Brent: VALUE.
- Top gainers: 3-4 names with %. Top losers: 3-4 names with %.
- FII/DII: one line with Rs. figure.

### Actionable Stock Ideas
| Stock | Signal | Action | Source | Detail |
|-------|--------|--------|--------|--------|
- **Detail column: 12-20 words.** Include: specific catalyst, target price, holding value if held. "USFDA VAI clearance for Andhra plant. Holding Rs.1.57L. Target Rs.1,400"
- Signal: single word or short phrase (BULLISH, BEARISH, NEUTRAL, BUY PUT, BOOK PROFIT)
- Action: BUY, SELL, HOLD, ADD, TRIM, EXIT, AVOID, WATCH — always filled
- Include ALL stocks with recommendations

### Corporate Actions & Deals
| WHO | WHAT | HOW MUCH | WHY IT MATTERS |
- **WHO**: Full entity names, not abbreviations. "Apollo Global Mgmt -> Adani Energy Solutions" not "Apollo -> Adani"
- **WHAT**: Specific action with context. "Secured notes for transmission unit refinancing" not "Secured notes financing"
- **HOW MUCH**: Always include currency + amount. "$500M" or "Rs.1,500 cr"
- **WHY IT MATTERS**: 10-15 words. Impact on investors/sector. "Signals institutional confidence in India power infra buildout"

### Negative News & Risks
| WHAT | WHO | HOW BAD | ACTION |
- **WHAT**: Specific event description. "US Section 301 trade probe on imports from 16 countries" not "Section 301 probe"
- **WHO**: Name affected companies/sectors explicitly. "Textiles (Welspun, Page), Auto (Tata Motors), Steel (JSW, Tata Steel)"
- **HOW BAD**: Quantify impact. "Rs.3.6L cr fiscal hit. CAD widens to 2% GDP" not just "fiscal hit"
- **ACTION**: WATCH/AVOID/TRIM + specific stocks and reason

### Sector Impacts
Bullet format: "- Sector: DIRECTION. Key fact. Affected stocks."
- One line per sector. MAX 15 words per line.
- Cover: Oil/Energy, Auto, Pharma, Banking, Paints, IT, Infra, Metals, Insurance, Electronics

### MF / SIP / IPO
| Item | Detail |
- One row per item. Detail MAX 12 words.

### Macro & Geopolitical
Bullet format only. One line per item. "- Crude: $100.27 (+9%). Iran tanker attacks."

### Portfolio Impact
| Stock | Value | Signal | Action | Why (15-25 words, specific detail) |
- **Why column**: Include the specific catalyst, quantified impact, and source. "Brent >$100 destroys refining margins. -4% today. Moody's flagged margin volatility" not just "OMC crushed"
- ONLY stocks with news. Skip holdings with no news — just list names at the end.
- Sort by action urgency: TRIM/EXIT first, then ADD, then HOLD, then WATCH.

### Key Takeaway
1-2 sentences MAX. What to DO today, not what happened.

## Critical Guidelines
- **BREVITY IS MANDATORY** — this is a dashboard for quick scanning, not a research report. If you can say it in 5 words, don't use 15.
- Read article bodies for data extraction, but OUTPUT must be concise
- Cover ALL articles from BOTH sources
- Numbers over words: "Rs.3.6L cr fiscal hit" not "the fiscal burden could increase by approximately..."
- Every stock/sector = clear verdict (BUY/SELL/HOLD/AVOID/WATCH)
- Connect dots (crude up -> paints down, ONGC up) but in SHORT form
- Flag urgent items with **[ACTION TODAY]**
- **GIFT Nifty is mandatory** as first Market Overview indicator
- **Table cells must be SHORT** — max 12 words. Truncate ruthlessly. Data density over explanation.
