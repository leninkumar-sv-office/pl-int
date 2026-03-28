---
name: include-test
description: Add comprehensive tests for new or changed code, ensuring CI/CD test gating catches regressions.
user_invocable: true
---

# Include Tests

Add tests for recently changed code, run them locally, and verify CI/CD passes.

## Prerequisites

Before starting, check what has changed:

```bash
git diff HEAD --stat
git diff HEAD --name-only
```

## Step 1: Identify Untested Code

Check which components/modules were changed and need tests:

```bash
# Backend: list all modules vs test files
ls backend/app/*.py | sed 's|backend/app/||;s|\.py||' | sort > /tmp/modules.txt
ls backend/tests/unit/test_*.py backend/tests/integration/test_*.py 2>/dev/null | sed 's|.*/test_||;s|\.py||' | sort > /tmp/tested.txt
comm -23 /tmp/modules.txt /tmp/tested.txt

# Frontend: list all components vs test files
ls frontend/src/components/*.jsx | grep -v '.test.' | sed 's|.*/||;s|\.jsx||' | sort > /tmp/components.txt
ls frontend/src/components/*.test.jsx 2>/dev/null | sed 's|.*/||;s|\.test\.jsx||' | sort > /tmp/tested_fe.txt
comm -23 /tmp/components.txt /tmp/tested_fe.txt
```

## Step 2: Write Tests

### Backend Test Standards
- Location: `backend/tests/unit/test_<module>.py` or `backend/tests/integration/test_api_<feature>.py`
- Framework: pytest + pytest-asyncio + pytest-cov
- Use existing fixtures from `backend/tests/conftest.py` (app_client, tmp_data_dir, tmp_dumps_dir, auth_token, sample_stock_xlsx)
- Mock all external services (Zerodha, Google Drive, stock prices)
- Test both success and error paths
- Validate model constraints (Pydantic validation errors)
- **Minimum 5 test cases per module**
- Read existing test files first to match patterns

### Frontend Test Standards
- Location: `frontend/src/components/ComponentName.test.jsx`
- Framework: Vitest + @testing-library/react
- Use existing utilities from `frontend/src/test/utils.js` (renderComponent, setupAuth, mockStockData, mockMFData)
- Mock API calls with `vi.mock('../services/api')`
- Test: renders, content, form inputs, button clicks, callbacks, edge cases
- **Minimum 5 test cases per component**
- Read existing test files first to match patterns

### Quality Standards
- DO NOT test implementation details — test behavior
- Use describe/it blocks with clear descriptions
- Handle async operations properly
- Mock chart libraries (recharts, etc.) to avoid SVG issues in jsdom
- Test loading states, empty states, error states

## Step 3: Run Tests Locally

Run both suites **in parallel** to validate:

```bash
# Terminal 1: Backend (with parallel execution)
cd backend && source venv/bin/activate
pip install pytest-xdist --quiet
AUTH_MODE=local python -m pytest tests/ -n auto --cov=app --cov-report=term -v --tb=short

# Terminal 2: Frontend (with parallel threads)
cd frontend && npx vitest run --reporter=verbose --pool=threads
```

**Both must show 0 failures before proceeding.**

## Step 4: Fix Failures

If tests fail:
1. Read the error message carefully
2. Check if it's a test bug or a code bug
3. If test bug: fix the test (wrong mock, outdated assertion)
4. If code bug: fix the code AND the test
5. Re-run until 0 failures

Common issues:
- `DUMPS_BASE` patches: modules import from `app.config`, not directly. Patch `app.config.DUMPS_BASE` or the function that uses it
- Pydantic `gt=0` vs `ge=0`: check if model constraints changed
- Missing API mocks: new API functions need to be added to `vi.mock`
- Chart rendering: mock `recharts` ResponsiveContainer in jsdom

## Step 5: Commit and Push

```bash
git add backend/tests/ frontend/src/components/*.test.jsx backend/requirements.txt
git commit -m "Add tests for <changed modules/components>

Backend: X new tests for <modules>
Frontend: Y new tests for <components>
All tests passing locally.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"

git push origin main
```

## Step 6: Verify CI/CD

Watch both workflows:

```bash
# Tests workflow (backend + frontend run in PARALLEL)
sleep 5
gh run list -w "Tests" --limit 1 --json databaseId,status
gh run watch <RUN_ID> --exit-status

# Deploy workflow
gh run list -w "Deploy" --limit 1 --json databaseId,status
gh run watch <RUN_ID> --exit-status
```

**Both must pass.** If Tests fail in CI but pass locally:
- Check if `pytest-xdist` causes fixture conflicts (thread safety)
- Check if GitHub runner has different Python/Node versions
- Read the CI logs: `gh run view <RUN_ID> --log-failed`

## Step 7: Verify Rollback Works

The deploy workflow already has rollback (`if: failure()`). Verify it's present:

```bash
grep -n "Rollback\|prev_tag" .github/workflows/deploy.yml
```

Should show the rollback step that:
1. Stops the failed deployment
2. Checks out the previous tag
3. Rebuilds and deploys
4. Verifies with health check

## Key Rules

- **100% component coverage** — every frontend component must have a test file
- **Parallel execution** — backend uses `pytest-xdist -n auto`, frontend uses `vitest --pool=threads`
- **CI/CD runs both in parallel** — `backend-tests` and `frontend-tests` are independent GitHub Actions jobs
- **Never skip tests** — if a test is flaky, fix it, don't skip it
- **Test behavior, not implementation** — assert what the user sees, not internal state
- **Read existing tests first** — match the patterns already in use
