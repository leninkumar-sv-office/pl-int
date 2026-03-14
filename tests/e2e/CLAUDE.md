# E2E Test Suite — Testing Strategy

## Overview

Playwright-based end-to-end tests that validate the full portfolio dashboard UI
against live backend API data. Tests bypass Google OAuth by generating JWT tokens
directly from `backend/app/auth.py`.

## Test Architecture

### Authentication (`helpers.js`)

- `generateJWT()` — calls Python backend to create a valid session token
- `authenticate(page)` — injects JWT + user info into localStorage, then reloads
- `waitForDashboard(page)` — waits for auth gate to pass and tab bar to render
- `switchTab(page, name)` — clicks a tab and waits for content to load
- `apiGet(endpoint)` — fetches backend API directly for data comparison

### Test Files

| File | What it tests | Key validations |
|------|--------------|-----------------|
| `market-ticker.spec.js` | Ticker bar (Sensex, Nifty, Gold, etc.) | Prices match API, 1D/7D/1M changes visible, up/down arrows |
| `stocks-tab.spec.js` | Stocks tab | 57 stocks held count matches API, expandable rows with lots/charts/tax, Buy/Sell buttons |
| `mutual-funds-tab.spec.js` | MF tab | 10 held funds match API, AMC grouping, search filter, held-only toggle, expandable rows with NAV charts & redemptions |
| `fixed-deposits-tab.spec.js` | FD tab | 3 FDs match API, columns, paid installment counts |
| `recurring-deposits-tab.spec.js` | RD tab | 6 RDs match API, account numbers, installment progress |
| `other-tabs.spec.js` | PPF, NPS, SI, Insurance | Empty states render correctly, proper columns, add buttons |
| `charts-tab.spec.js` | Charts tab | SVG charts render, P&L and composition charts, stock symbols in labels |
| `user-switching.spec.js` | User dropdown | 3 users visible, switching changes portfolio data, switching back restores |
| `header-controls.spec.js` | Header bar | Zerodha status, price/reload intervals, refresh button, context-aware add buttons per tab, all 9 tabs present |

## Critical Testing Principle

**Always validate data, not just rendering.** A tab that renders with 0 items when
it should have 10 is a test failure, even if the UI looks fine. Each test fetches
data from the API and compares counts/values against what the UI shows.

## Adding New Tests

1. Create a new `.spec.js` file in this directory
2. Use `authenticate()` + `waitForDashboard()` in `beforeEach`
3. Use `apiGet()` to fetch expected data for comparison
4. Test both positive cases (data present) and edge cases (empty states)
5. For expandable rows: test the expanded content (lots, charts, buttons)

## Running

```bash
# From project root (pl/)
npm test                          # all tests
npx playwright test <file>.spec.js  # single file
npm run test:headed               # see browser
npm run test:report               # HTML report
```

## Prerequisites

- Backend running on `localhost:8000`
- Frontend running on `localhost:5173`
- `AUTH_MODE=google` in `backend/.env`
- Valid `backend/data/.jwt_secret` (auto-created on first backend start)
- Playwright chromium installed (`npx playwright install chromium`)
