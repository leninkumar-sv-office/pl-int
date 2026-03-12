---
name: briefing
description: Generate a comprehensive daily market briefing from Business Line and The Hindu articles. Use when user asks for market news, daily briefing, stock recommendations, or financial analysis.
---

# Daily Market Briefing

Generate a comprehensive, detailed market briefing from today's Business Line + The Hindu articles.

## Steps

1. **Fetch articles** from the backend:
   ```bash
   curl -s http://localhost:8000/api/advisor/articles
   ```
   Returns a JSON array with fields: title, summary, body, section, url, source ("Business Line" or "The Hindu").

2. **Fetch portfolio holdings** for context:
   ```bash
   curl -s http://localhost:8000/api/portfolio/stock-summary
   ```

3. **Fetch advisor insights** (keyword-matched or AI-generated):
   ```bash
   curl -s http://localhost:8000/api/advisor/insights
   ```

4. If the articles list is empty or the backend is down, try refreshing first:
   ```bash
   curl -s -X POST http://localhost:8000/api/advisor/refresh
   ```

5. **Read the BODY of every article** — not just headlines. The `body` field contains the actual article text (up to 3000 chars). Use this to extract:
   - Specific investment amounts ("Apollo-led funds invest $500M in Adani Energy")
   - Company names involved in deals, mergers, partnerships
   - Negative news — lawsuits, frauds, earnings misses, downgrades
   - Analyst recommendations with target prices
   - Government policy changes with affected companies
   - IPO details with subscription recommendations

6. **Produce the briefing** using the format below.

## Output Format

Start with a source summary line:
> Sources: X articles from Business Line, Y articles from The Hindu

### Market Overview
- Nifty/Sensex direction, % change, key index levels
- FII/DII flow direction if mentioned
- Top gainers and losers by name

### Actionable Stock Ideas
| Stock | Signal | Source | Detail |
|-------|--------|--------|--------|
List ALL stocks mentioned with specific recommendations. Include:
- Price targets if mentioned
- Analyst house (Jefferies, CLSA, etc.) if mentioned
- Reason for the call (order win, earnings, sector tailwind)
- Source column: BL or TH

### Corporate Actions & Deals
For EVERY article about investments, acquisitions, fundraising, partnerships:
- WHO is investing/acquiring
- HOW MUCH (₹ or $ amount)
- IN WHAT (target company/unit)
- WHY it matters for investors
Example: "Apollo-led funds invested $500M in Adani Energy Solutions' transmission unit — signals institutional confidence in India's power infra buildout"

### Negative News & Risks
For EVERY article about bad news, fraud, regulatory action, earnings miss:
- WHAT happened
- WHO is affected
- HOW BAD (quantify if possible — stock drop %, fine amount, etc.)
- WHAT TO DO (sell/avoid/watch)
Example: "CBI arrested Darwin Labs co-founder in crypto fraud — avoid related stocks, check exposure to crypto-adjacent companies"

### Sector Themes
Group related articles into themes. For each theme with 3+ articles:
- Name the theme (e.g., "Oil Crisis Impact", "Jal Jeevan Mission Beneficiaries")
- List ALL affected companies with specific context
- Actionable takeaway

### Sector Impacts
Cover EVERY sector that has news:
- Oil/Energy, Banking/NBFC, IT, Pharma, Defence, Auto/EV, FMCG, Metals, Infra, Real Estate, Insurance, Hospitality
- For each: what happened, which companies, direction (bullish/bearish)

### Mutual Fund / SIP / Investment Products
- New fund launches (name, NAV, type)
- SIP trend data
- AMC-specific news
- IPO reviews with subscribe/avoid recommendation
- FD/RD rate changes if any

### Macro & Geopolitical
- RBI policy, inflation data
- Crude oil price and direction
- Rupee level and trend
- Gold/Silver prices
- Global cues (US, China, EU)
- Geopolitical events with market impact

### Key Takeaway
2-3 sentences: What should an investor DO today? Be specific.

## Critical Guidelines
- **Read article bodies, not just headlines** — the detail is in the body text
- **Cover ALL articles from BOTH sources** — Business Line AND The Hindu
- **Be specific** — include ₹ amounts, % changes, company names, analyst names
- **Every company mention = potential insight** — if Company A invests in Company B, BOTH are relevant
- **Bad news is as important as good news** — frauds, arrests, downgrades, supply disruptions
- **No vague language** — don't say "markets may move", say "Nifty fell 1.2% to 21,850"
- **Connect the dots** — if crude rises, mention which companies benefit (ONGC, Oil India) AND which suffer (paints, airlines, logistics)
- **Cross-reference between sources** — if both BL and TH cover same topic, note the consensus or divergence
- Use INR for all currency references
- Flag items needing immediate action with **[ACTION TODAY]**
