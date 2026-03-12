---
name: briefing
description: Generate a comprehensive daily market briefing from Business Line articles
user_invocable: true
---

# Daily Market Briefing

Generate a comprehensive market briefing from today's Business Line articles.

## Steps

1. **Fetch articles** from the backend:
   ```
   curl -s http://localhost:8000/api/advisor/articles
   ```
   This returns a JSON array of scraped articles with fields: title, summary, body, section, url.

2. **Fetch portfolio holdings** for context:
   ```
   curl -s http://localhost:8000/api/portfolio/stock-summary
   ```

3. **Fetch advisor insights** (keyword-matched or AI-generated):
   ```
   curl -s http://localhost:8000/api/advisor/insights
   ```

4. If the articles list is empty or the backend is down, inform the user and suggest running:
   ```
   curl -s -X POST http://localhost:8000/api/advisor/refresh
   ```

5. **Analyze ALL articles** (not just portfolio-matched ones) and produce a briefing organized into these sections:

### Output Format

```
## Market Overview
- Nifty/Sensex direction, key movers, FII/DII flows

## Actionable Stock Ideas
| Stock | Signal | Detail |
Table of specific buy/sell/watch recommendations from articles

## Sector-specific section (if major news)
E.g. "Jal Jeevan Mission Winners" or "Oil & Energy Crisis" — any theme with 3+ articles

## Sector Impacts
- Group by sector: Oil/Energy, Banking, IT, Pharma, Defence, Auto, FMCG, Metals, Infra, Real Estate
- Only include sectors that have actual news today

## Mutual Fund / SIP Insights
- New fund launches, SIP trends, NAV impacts, AMC news, IPO reviews

## Macro & Geopolitical Risks
- RBI policy, inflation, crude oil, rupee, global cues, geopolitical events

## Key Takeaway
- 2-3 sentence actionable summary of what an investor should do today
```

### Guidelines
- Cover ALL 100+ articles, not just portfolio stocks
- Lead with the most urgent/actionable items
- Use tables for stock picks (Stock | Signal | Detail)
- Flag HIGH urgency items that need action today
- Include source article titles for key insights
- Use INR for all currency
- Be direct and specific — no vague "markets may move" language
- If crude oil, gold, or rupee have significant moves, highlight them prominently
