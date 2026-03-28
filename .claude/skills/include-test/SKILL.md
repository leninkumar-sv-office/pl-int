---
name: include-test
description: Add comprehensive tests for new or changed code, ensuring CI/CD test gating catches regressions.
user_invocable: true
---

# Include Tests — STRICT 100% COVERAGE

Add tests for recently changed code. **Target: 100% line coverage for all application code.**

## Prerequisites

Before starting, check what has changed:

```bash
git diff HEAD --stat
git diff HEAD --name-only
```

## Step 1: Measure Current Coverage

```bash
# Backend coverage
cd backend && source venv/bin/activate
AUTH_MODE=local python -m pytest tests/ --cov=app --cov-report=term-missing --tb=short -q

# Frontend coverage (install coverage dep if missing)
cd frontend
npm install @vitest/coverage-v8 --save-dev --silent 2>/dev/null
npx vitest run --coverage --reporter=verbose
```

**Record the current coverage percentage.** Goal is 100%.

## Step 2: Identify Uncovered Code

From the coverage report, identify modules/files with <100% coverage:
- Look at the "Missing" column — those are uncovered line numbers
- Prioritize: business logic > API endpoints > parsers > external services
- For external services (Zerodha, Drive, epaper), mock the external calls and test the internal logic

## Step 3: Write Tests

### Backend Test Standards
- Location: `backend/tests/unit/test_<module>.py` or `backend/tests/integration/test_api_<feature>.py`
- Framework: pytest + pytest-asyncio + pytest-cov
- Use existing fixtures from `backend/tests/conftest.py`
- **Mock ALL external services** (Zerodha, Google Drive, stock prices, HTTP calls)
- Test EVERY code path: success, error, edge cases, validation
- Test EVERY function/method in the module
- **Minimum: every line must be covered**
- Read existing test files first to match patterns

### Frontend Test Standards
- Location: `frontend/src/components/ComponentName.test.jsx`
- Framework: Vitest + @testing-library/react + @vitest/coverage-v8
- Use existing utilities from `frontend/src/test/utils.js`
- Mock API calls with `vi.mock('../services/api')`
- Test: renders, content, form inputs, button clicks, callbacks, edge cases
- **Every component must have a test file with full coverage**
- Read existing test files first to match patterns

### Quality Standards
- DO NOT test implementation details — test behavior
- Use describe/it blocks with clear descriptions
- Handle async operations properly
- Mock chart libraries (recharts, etc.) to avoid SVG issues in jsdom
- Test loading states, empty states, error states
- Test error handling paths (catch blocks, fallbacks)

## Step 4: Run Tests with Coverage Enforcement

```bash
# Backend — MUST be 100%
cd backend && source venv/bin/activate
AUTH_MODE=local python -m pytest tests/ \
  --cov=app \
  --cov-report=term-missing \
  --cov-fail-under=100 \
  -v --tb=short

# Frontend — MUST be 100%
cd frontend
npx vitest run --coverage --reporter=verbose
```

**Both must show 0 failures AND 100% coverage before proceeding.**

## Step 5: Fix Coverage Gaps

If coverage is <100%:
1. Read the "Missing" lines from the coverage report
2. Write tests that exercise those specific lines
3. For hard-to-test code (external API calls), mock the dependency
4. For unreachable code (dead code), remove it
5. Re-run until 100%

Common patterns for covering missed lines:
- `except` blocks: trigger the exception in a test
- `if/else` branches: test both branches
- Early returns: test the condition that triggers the early return
- External API calls: mock with `unittest.mock.patch`
- File I/O: use `tmp_path` fixture

## Step 6: Update CI/CD Coverage Enforcement

The CI/CD pipeline MUST enforce 100% coverage. Update `test.yml`:

```yaml
# Backend: --cov-fail-under=100
AUTH_MODE=local python -m pytest tests/ --cov=app --cov-fail-under=100

# Frontend: coverage thresholds in vitest.config.js
# coverage: { thresholds: { lines: 100, branches: 100, functions: 100 } }
```

## Step 7: Commit and Push

```bash
git add backend/tests/ frontend/src/components/*.test.jsx
git commit -m "Achieve 100% test coverage

Backend: X tests covering all modules
Frontend: Y tests covering all components
Coverage enforced in CI/CD at 100%.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"

git push origin main
```

## Step 8: Verify CI/CD

```bash
sleep 5
gh run watch $(gh run list --limit 1 --json databaseId -q '.[0].databaseId') --exit-status
```

**Pipeline must pass with 100% coverage.** If it fails:
- Check `gh run view <RUN_ID> --log-failed`
- Fix coverage gaps
- Push again

## Key Rules

- **100% line coverage is MANDATORY** — not 99%, not 95%, exactly 100%
- **CI/CD enforces coverage** — pipeline fails if coverage drops below 100%
- **No dead code** — if code can't be covered, remove it
- **Mock external dependencies** — never skip coverage because "it calls an API"
- **Parallel execution** — backend + frontend tests run in parallel in CI/CD
- **Never skip tests** — if a test is flaky, fix it
- **Read existing tests first** — match the patterns already in use
