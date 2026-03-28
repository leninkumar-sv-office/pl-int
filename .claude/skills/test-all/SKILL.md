---
name: test-all
description: Run all test suites (backend pytest, frontend vitest, e2e playwright) and report results. Use when user asks to run all tests or validate everything works.
user_invocable: true
---

# Run All Tests

Run all test suites in parallel and report a consolidated pass/fail summary.

## Step 1: Run backend and frontend tests in parallel

Launch both in background:

```bash
# Backend tests (parallel with pytest-xdist)
cd /Users/lenin/Desktop/workspace/pl-int/backend
source venv/bin/activate 2>/dev/null || (python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt -q)
pip install pytest-xdist -q
AUTH_MODE=local python -m pytest tests/ -n auto --cov=app --cov-report=term -v --tb=short 2>&1 | tee /tmp/backend-test-results.txt &

# Frontend tests (parallel with threads)
cd /Users/lenin/Desktop/workspace/pl-int/frontend
npm install --silent 2>/dev/null
npx vitest run --reporter=verbose --pool=threads 2>&1 | tee /tmp/frontend-test-results.txt &

wait
```

## Step 2: E2E tests (optional)

Only run if the production site is accessible:

```bash
curl -s https://pl.thirumagal.com/health | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null
```

If healthy, run Playwright tests via the Playwright MCP browser:
1. Navigate to https://pl.thirumagal.com
2. Authenticate using JWT (generate from Docker container)
3. Verify key features visually

## Step 3: Summary

Print consolidated results:

```
Test Results
────────────────────────────────────────
Backend (pytest):    ✓ X passed / ✗ Y failed  (Zs, parallel)
Frontend (vitest):   ✓ X passed / ✗ Y failed  (Zs, threaded)
E2E (playwright):    ✓ verified / skipped
────────────────────────────────────────
Overall: PASS / FAIL
```

If any suite failed, show the failing test names and suggest fixes.

## Key Rules

- Backend and frontend MUST run in parallel (not sequential)
- Backend uses `pytest-xdist -n auto` for multi-process execution
- Frontend uses `vitest --pool=threads` for multi-threaded execution
- Report coverage numbers if available
- If tests fail, don't just report — analyze and suggest fixes
