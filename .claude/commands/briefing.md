Generate a comprehensive daily market briefing from Business Line articles.

## Steps

1. Fetch articles: `curl -s http://localhost:8000/api/advisor/articles`
2. Fetch portfolio: `curl -s http://localhost:8000/api/portfolio/stock-summary`
3. Fetch insights: `curl -s http://localhost:8000/api/advisor/insights`
4. If empty, refresh: `curl -s -X POST http://localhost:8000/api/advisor/refresh`

Read the BODY of every article (not just headlines). Extract specific details:
- Investment amounts, deal sizes, company names
- Analyst recommendations with target prices
- Bad news: frauds, arrests, downgrades, supply disruptions
- Government policy changes and affected companies

## Output as:

### Market Overview
Nifty/Sensex direction, % change, key levels, top gainers/losers

### Actionable Stock Ideas
| Stock | Signal | Detail |
Table with ALL stock recommendations, target prices, analyst names

### Corporate Actions & Deals
Every investment/acquisition/fundraising with WHO, HOW MUCH, IN WHAT, WHY it matters.
E.g. "Apollo-led funds invested $500M in Adani Energy Solutions unit"

### Negative News & Risks
Every bad news item with WHAT, WHO, HOW BAD, WHAT TO DO.
E.g. "CBI arrested Darwin Labs co-founder in crypto fraud — avoid related stocks"

### Sector Themes
Group 3+ related articles into named themes with affected companies and takeaway

### Sector Impacts
Cover every sector with news: Oil, Banking, IT, Pharma, Defence, Auto, FMCG, Metals, Infra, etc.

### MF / SIP / Investment Products
New launches, SIP trends, IPO reviews, rate changes

### Macro & Geopolitical
RBI, inflation, crude, rupee, gold, global cues

### Key Takeaway
2-3 specific actionable sentences

## Rules
- Cover ALL 100+ articles, read bodies not just headlines
- Be specific: ₹ amounts, % changes, company names
- Every company mention = insight (investor AND investee)
- Bad news equally important as good news
- Connect dots (crude up → paints down, ONGC up)
- No vague language. Flag urgent items with [ACTION TODAY]
