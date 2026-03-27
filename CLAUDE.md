# Portfolio Dashboard (pl)

## Project Structure

```
pl/
├── backend/          # FastAPI (Python) — API server on port 9999
│   ├── app/
│   │   ├── main.py           # All API endpoints
│   │   ├── auth.py           # Google SSO + JWT session tokens
│   │   ├── config.py         # DUMPS_BASE path, user dirs
│   │   ├── drive_service.py  # Google Drive sync
│   │   └── zerodha_service.py # Zerodha API for live prices
│   ├── data/                 # JSON data files, .jwt_secret
│   └── .env                  # API keys (never commit)
├── frontend/         # React (Vite) — dev server on port 5173
│   ├── src/
│   │   ├── App.jsx           # Main app with AuthGate, tabs, data loading
│   │   ├── components/       # Tab components (MutualFundTable, etc.)
│   │   └── services/api.js   # Axios API client with auth interceptor
│   └── vite.config.js        # Proxy /api → localhost:9999
├── tests/e2e/        # Playwright end-to-end tests
│   ├── helpers.js            # Auth helpers (JWT generation, page setup)
│   ├── market-ticker.spec.js
│   ├── stocks-tab.spec.js
│   ├── mutual-funds-tab.spec.js
│   ├── fixed-deposits-tab.spec.js
│   ├── recurring-deposits-tab.spec.js
│   ├── other-tabs.spec.js    # PPF, NPS, SI, Insurance
│   ├── charts-tab.spec.js
│   ├── user-switching.spec.js
│   └── header-controls.spec.js
└── playwright.config.js
```

## Running the App

```bash
# Local dev (port 9998 — won't conflict with Docker on 9999)
./scripts/run.sh

# Or manually:
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 9998
cd frontend && npm run dev   # Vite proxies /api → localhost:9998
```

## Deployment

- **Always deploy after making changes** — use `/deploy` to commit, push, and watch CI/CD
- CI/CD runs Docker deployment by default (port 9999, via Cloudflare tunnel)
- Docker container: `pl-dashboard` at `https://pl.thirumagal.com/`
- Local dev runs on port 9998, Docker prod runs on port 9999 (no conflict)

## Running Tests

```bash
# Run all e2e tests (requires backend + frontend running)
npm test

# Run with browser visible
npm run test:headed

# Run specific test file
npx playwright test tests/e2e/stocks-tab.spec.js

# View HTML report
npm run test:report
```

## Authentication

- `AUTH_MODE=google` in `.env` — requires Google OAuth login
- Tests bypass OAuth by generating JWT tokens directly via `app/auth.py`
- JWT secret is persisted in `backend/data/.jwt_secret` to survive restarts
- 401 responses trigger `auth-expired` event → shows login page

## Key Conventions

- **Zerodha API is the primary data source** for all market prices (NOT Yahoo Finance)
- MF fund codes are ISINs from CDSL CAS import
- MF NAVs use AMFI NAVAll.txt (bulk fetch, 1hr cache)
- User data lives in Google Drive desktop sync at `DUMPS_BASE`
- All MF funds are Direct Growth plans, names in Title Case
- **Feature parity: StockSummaryTable ↔ MutualFundTable** — any feature added to one (sorting modes, filtering, display options, columns) MUST also be added to the other. They should have the same UX capabilities.

## MANDATORY: Verify Every Deploy with Playwright

**THIS IS NOT OPTIONAL. After EVERY deploy**, verify using the Playwright MCP browser:
1. Navigate to `https://pl.thirumagal.com`
2. Wait for data to load (wait for "ADANI" or similar stock name)
3. Take a screenshot to visually confirm the change works
4. Check columns have data, filters work, no empty values where data should be
5. Check the browser console for errors
6. If Playwright can't launch (Chrome session conflict), verify via API calls instead

**If you skip this step, the user WILL find bugs and ask you to test. Do it proactively.**
**Every time you think "this is a small change, no need to test" — TEST IT ANYWAY.**

## Test Strategy

Tests validate **data correctness**, not just UI rendering:
- API responses are fetched and compared against what the UI displays
- Counts (stocks held, funds held, FDs active) are verified against backend data
- Each tab is tested for: correct columns, data presence, interactive features
- Expandable rows tested for: lot details, charts, tax summary, action buttons
- User switching tested for: data isolation between users
