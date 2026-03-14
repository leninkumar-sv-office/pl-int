# Portfolio Dashboard (pl)

## Project Structure

```
pl/
├── backend/          # FastAPI (Python) — API server on port 8000
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
│   └── vite.config.js        # Proxy /api → localhost:8000
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
# Backend
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm run dev

# Both must be running for tests
```

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

## Test Strategy

Tests validate **data correctness**, not just UI rendering:
- API responses are fetched and compared against what the UI displays
- Counts (stocks held, funds held, FDs active) are verified against backend data
- Each tab is tested for: correct columns, data presence, interactive features
- Expandable rows tested for: lot details, charts, tax summary, action buttons
- User switching tested for: data isolation between users
