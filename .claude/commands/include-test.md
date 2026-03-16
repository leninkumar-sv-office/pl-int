Add comprehensive tests for new or changed code, ensuring CI/CD test gating catches regressions.

## When to Use

Run this after implementing a feature, fixing a bug, or adding a new module — it ensures full test coverage for the changes and verifies CI/CD will catch regressions.

## Step 1: Identify What Changed

```bash
git diff --name-only HEAD~1..HEAD
git diff --stat HEAD~1..HEAD
```

Categorize changed files:
- **Backend Python** (`backend/app/*.py`) → needs pytest unit + integration tests
- **Frontend JSX/JS** (`frontend/src/**`) → needs Vitest + RTL component tests
- **Both** → needs both

## Step 2: Backend Tests (if Python files changed)

### 2a: Unit Tests

For each changed/new backend module, create or update a test file in `backend/tests/unit/`:

**Test file naming:** `test_{module_name}.py` (e.g., `test_auth.py` for `app/auth.py`)

**Test patterns:**
```python
"""Tests for app/{module}.py"""
from unittest.mock import patch, MagicMock
import pytest

# Use fixtures from conftest.py: tmp_data_dir, tmp_dumps_dir, app_client, auth_token
```

**What to test per function:**
- Happy path with valid input → correct output
- Edge cases: empty input, None, zero, negative numbers
- Error paths: every `except` block, every early `return None`
- Boundary values: max/min, first/last
- For database modules: CRUD (add, get_all, update, delete), empty state
- For parsers: valid input, malformed input, empty input (mock `pdfplumber.open`)
- For services: mock ALL external calls (Zerodha, Drive, AMFI, Yahoo Finance, requests.get)

**Mock patterns for external services:**
```python
# Zerodha
with patch("app.zerodha_service.KiteConnect") as mock_kite:
    mock_kite.return_value.ltp.return_value = {"NSE:RELIANCE": {"last_price": 2800}}

# Google Drive
with patch("app.drive_service.upload_file", MagicMock()):

# PDF parsing
mock_page = MagicMock()
mock_page.extract_text.return_value = "sample text"
with patch("pdfplumber.open") as mock_pdf:
    mock_pdf.return_value.__enter__ = lambda self: MagicMock(pages=[mock_page])
```

### 2b: Integration Tests (API endpoints)

For each new/changed API endpoint, create or update a test file in `backend/tests/integration/`:

**Test file naming:** `test_api_{domain}.py` (e.g., `test_api_stocks.py`)

**Test patterns:**
```python
def test_endpoint_happy_path(app_client):
    response = app_client.get("/api/endpoint")
    assert response.status_code == 200

def test_endpoint_missing_field(app_client):
    response = app_client.post("/api/endpoint", json={})
    assert response.status_code == 422

def test_endpoint_not_found(app_client):
    response = app_client.get("/api/endpoint/nonexistent-id")
    assert response.status_code == 404
```

**Key:** The `app_client` fixture (from `conftest.py`) provides a FastAPI TestClient with:
- AUTH_MODE=local (no auth needed)
- X-User-Id header set to "TestUser"
- Isolated tmp directories (won't touch real data)
- Mocked external services (Zerodha, Drive, stock_service)

### 2c: Run Backend Tests

```bash
cd backend && source venv/bin/activate && python -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
```

All tests MUST pass. Fix failures before proceeding.

## Step 3: Frontend Tests (if JSX/JS files changed)

### 3a: Component Tests

For each changed/new component, create or update a test file alongside it:

**Test file naming:** `ComponentName.test.jsx` (same directory as component)

**Test patterns:**
```jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ComponentName from './ComponentName';

describe('ComponentName', () => {
  const defaultProps = {
    onClose: vi.fn(),
    onAdd: vi.fn(),
    // ... all required props with vi.fn() for callbacks
  };

  it('renders without crashing', () => {
    render(<ComponentName {...defaultProps} />);
    expect(screen.getByText(/expected text/i)).toBeInTheDocument();
  });

  it('handles empty data', () => {
    render(<ComponentName {...defaultProps} data={[]} />);
    // Should not crash
  });
});
```

**What to test per component:**
- **Tables:** Renders rows with data, column headers present, empty state, P&L colors (green/red)
- **Modals:** Form fields render, validation (disabled submit when empty), onClose callback, submit with data
- **Supporting:** Correct props displayed, click handlers fire

**Available test utilities** (from `src/test/`):
- `src/test/setup.js` — jest-dom matchers, cleanup, recharts mock
- `src/test/utils.js` — `renderComponent()`, `setupAuth()`, `mockStockData()`, `mockMFData()`
- `src/test/mocks/api.js` — mock data for all asset types

### 3b: Run Frontend Tests

```bash
cd frontend && npx vitest run --reporter=verbose
```

All tests MUST pass.

## Step 4: Verify Full Suite

Run the complete test suite to ensure nothing is broken:

```bash
# Backend (602+ tests)
cd backend && source venv/bin/activate && python -m pytest tests/ --tb=short -q

# Frontend (94+ tests)
cd frontend && npx vitest run
```

## Step 5: Commit and Deploy

Stage test files alongside the feature code:

```bash
git add backend/tests/ frontend/src/components/*.test.jsx frontend/src/test/
git commit -m "test: add tests for [feature name]"
```

Then use `/deploy` to push through CI/CD. The deploy workflow will:
1. Run `test / frontend-tests` (Vitest)
2. Run `test / backend-tests` (pytest with coverage)
3. Only if BOTH pass → `tag-and-deploy` runs

If tests fail in CI:
1. Get logs: `gh run view <RUN_ID> --log-failed`
2. Fix the failing tests locally
3. Push again

## CI/CD Test Architecture

```
.github/workflows/test.yml     ← Runs on PR + called by deploy
.github/workflows/deploy.yml   ← needs: test (blocked until tests pass)

Backend test stack:
  pytest + pytest-asyncio + pytest-cov + httpx
  backend/tests/conftest.py    ← shared fixtures
  backend/tests/unit/           ← 22 test files, pure logic tests
  backend/tests/integration/    ← 9 test files, API endpoint tests

Frontend test stack:
  vitest + @testing-library/react + @testing-library/jest-dom + jsdom
  frontend/vitest.config.js     ← test config
  frontend/src/test/setup.js    ← global setup
  frontend/src/test/utils.js    ← helpers
  frontend/src/test/mocks/      ← mock data
  frontend/src/components/*.test.jsx ← 15 component test files
```

## Quick Reference

| What Changed | Test Location | Command |
|-------------|--------------|---------|
| `backend/app/auth.py` | `backend/tests/unit/test_auth.py` | `pytest tests/unit/test_auth.py -v` |
| `backend/app/main.py` (new endpoint) | `backend/tests/integration/test_api_*.py` | `pytest tests/integration/ -v` |
| `frontend/src/components/Foo.jsx` | `frontend/src/components/Foo.test.jsx` | `npx vitest run src/components/Foo.test.jsx` |
| `frontend/src/services/api.js` | `frontend/src/services/api.test.js` | `npx vitest run src/services/api.test.js` |
