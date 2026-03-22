---
name: test-all
description: Run all test suites (backend pytest, frontend vitest, e2e playwright) and report results. Use when user asks to run all tests or validate everything works.
user_invocable: true
---

# Run All Tests

Run all three test suites and report a consolidated pass/fail summary.

## Steps

### 1. Backend tests (pytest)

```bash
cd /Users/lenin/Desktop/workspace/pl/backend
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt -q
AUTH_MODE=local python -m pytest tests/ -v --tb=short 2>&1
```

Record: total passed, failed, errors.

### 2. Frontend tests (vitest)

```bash
cd /Users/lenin/Desktop/workspace/pl/frontend
npm test 2>&1
```

Record: total passed, failed.

### 3. E2E tests (playwright)

Only run if backend + frontend are already running (check ports 9998/5173):

```bash
cd /Users/lenin/Desktop/workspace/pl
# Check if servers are up
curl -s http://localhost:9998/api/health > /dev/null 2>&1 && curl -s http://localhost:5173 > /dev/null 2>&1
```

If both are up:
```bash
npx playwright test 2>&1
```

If not running, skip with a note: "E2E tests skipped — start backend (port 9998) and frontend (port 5173) first."

### 4. Summary

Print a consolidated report:

```
Test Results
────────────
Backend (pytest):    ✓ X passed / ✗ Y failed
Frontend (vitest):   ✓ X passed / ✗ Y failed
E2E (playwright):    ✓ X passed / ✗ Y failed  (or: skipped)
────────────
Overall: PASS / FAIL
```

If any suite failed, highlight the failures and suggest next steps.
