Generate a comprehensive daily market briefing from Business Line + The Hindu articles.

## Steps

1. Fetch articles: `curl -s http://localhost:8000/api/advisor/articles`
   - Returns articles with `source` field: "Business Line" or "The Hindu"
2. Fetch portfolio: `curl -s http://localhost:8000/api/portfolio/stock-summary`
3. Fetch insights: `curl -s http://localhost:8000/api/advisor/insights`
4. Fetch market ticker (GIFT Nifty, Sensex, crude, gold, etc.): `curl -s http://localhost:8000/api/market-ticker`
5. If empty, refresh: `curl -s -X POST http://localhost:8000/api/advisor/refresh`

Read the BODY of every article (not just headlines). Extract specific details:
- Investment amounts, deal sizes, company names
- Analyst recommendations with target prices
- Bad news: frauds, arrests, downgrades, supply disruptions
- Government policy changes and affected companies

## Output as:

Start with: > Sources: X articles from Business Line, Y articles from The Hindu

### Market Overview
- **GIFT Nifty**: Level, change vs Nifty close, gap up/down signal for next session
- Nifty/Sensex direction, % change, key levels, top gainers/losers

### Actionable Stock Ideas
| Stock | Signal | Action | Source | Detail |
Table with ALL stock recommendations, target prices, analyst names. Action column = BUY/SELL/HOLD/ADD/TRIM/EXIT/AVOID/WATCH for every row.

### Corporate Actions & Deals
Every investment/acquisition/fundraising with WHO, HOW MUCH, IN WHAT, WHY it matters.

### Negative News & Risks
Every bad news item with WHAT, WHO, HOW BAD, WHAT TO DO.

### Sector Themes
Group 3+ related articles into named themes with affected companies and takeaway

### Sector Impacts
Cover every sector with news: Oil, Banking, IT, Pharma, Defence, Auto, FMCG, Metals, Infra, etc.

### MF / SIP / Investment Products
New launches, SIP trends, IPO reviews, rate changes

### Macro & Geopolitical
RBI, inflation, crude, rupee, gold, global cues

### Portfolio Impact Assessment
Cross-reference recommendations against user's actual holdings (from stock-summary API):
- **Holdings with news**: table showing held stock, holding value, signal, news, action (HOLD/ADD/TRIM/EXIT)
- **New opportunities**: stocks with BUY/BULLISH signals user doesn't hold
- **Holdings with no news**: brief list so user knows nothing was missed

### Key Takeaway
2-3 specific actionable sentences

## PDF Generation
After producing the briefing, generate a PDF by posting the markdown to:
`curl -s -X POST http://localhost:8000/api/advisor/briefing-pdf -H "Content-Type: application/json" -d '{"markdown": "<briefing>"}'`
Report the saved PDF path to the user.

## Rules
- Cover ALL articles from BOTH sources, read bodies not just headlines
- Be specific: ₹ amounts, % changes, company names
- Cross-reference between BL and TH for consensus/divergence
- Bad news equally important as good news
- Connect dots (crude up → paints down, ONGC up)
- No vague language. Flag urgent items with [ACTION TODAY]
- Every stock/sector mention must have a clear BUY/SELL/HOLD/AVOID/WATCH verdict
- GIFT Nifty is mandatory in Market Overview as the first indicator
