Generate a CONCISE daily market briefing dashboard from past 7 days of Business Line + The Hindu articles.

## Steps

1. Fetch articles (past 7 days): `curl -s http://localhost:9999/api/advisor/articles`
2. Fetch portfolio: `curl -s http://localhost:9999/api/portfolio/stock-summary`
3. Fetch insights: `curl -s http://localhost:9999/api/advisor/insights`
4. Fetch market ticker: `curl -s http://localhost:9999/api/market-ticker`
5. If empty, refresh: `curl -s -X POST http://localhost:9999/api/advisor/refresh`

Read article BODIES for data extraction, but keep OUTPUT concise.

## CRITICAL: BREVITY

This is a DASHBOARD, not an article. Rules:
- Bullets: MAX 10-15 words each
- Table Detail cells: MAX 12 words each
- No sentences in tables — use fragments: "USFDA clearance. Holding Rs.1.57L"
- Numbers over prose: "Rs.3.6L cr fiscal hit" not "the fiscal burden could increase..."

## Output format:

> Sources: X from Business Line, Y from The Hindu

### Market Overview
Short bullets: "GIFT Nifty: 23,718 (-0.9%). +79 pts premium. Flat open signal."

### Actionable Stock Ideas
| Stock | Signal | Action | Source | Detail (12-20 words with specific catalyst + target) |

### Corporate Actions & Deals
| WHO (full names) | WHAT (specific action) | HOW MUCH | WHY IT MATTERS (10-15 words, investor impact) |

### Negative News & Risks
| WHAT (specific event) | WHO (name companies) | HOW BAD (quantify) | ACTION (verdict + stocks) |

### Sector Impacts
One-line bullets: "- Oil/Energy: CRISIS. Brent $100+. OMCs crushed. Upstream surging."

### MF / SIP / IPO
| Item | Detail (MAX 12 words) |

### Macro & Geopolitical
One-line bullets: "- Crude: $100.27 (+9%). Iran tanker attacks. IEA 400M bbl release."

### Portfolio Impact
| Stock | Value | Signal | Action | Why (15-25 words, specific catalyst + quantified impact) |
Sort by urgency: TRIM/EXIT first, then ADD, HOLD, WATCH.
Skip no-news holdings — just list names at end.

### Key Takeaway
1-2 sentences MAX. What to DO, not what happened.

## PDF Generation
After producing briefing: `curl -s -X POST http://localhost:9999/api/advisor/briefing-pdf -H "Content-Type: application/json" -d '{"markdown": "<briefing>"}'`

## Rules
- BREVITY IS MANDATORY — dashboard for quick scanning
- Cover ALL articles from BOTH sources
- Every stock = clear verdict (BUY/SELL/HOLD/AVOID/WATCH)
- Flag urgent items with [ACTION TODAY]
- GIFT Nifty mandatory as first indicator
