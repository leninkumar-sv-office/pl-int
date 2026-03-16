Add tests for changed code, then deploy through CI/CD. Combines /include-test and /deploy.

## Step 1: Run /include-test

Follow the full /include-test workflow:

1. Identify what changed (`git diff --name-only`)
2. Write backend pytest tests for any changed Python files
3. Write frontend Vitest tests for any changed JSX/JS files
4. Run full test suites to verify all pass:
   - `cd backend && source venv/bin/activate && python -m pytest tests/ --tb=short -q`
   - `cd frontend && npx vitest run`
5. Commit test files alongside feature code

## Step 2: Run /deploy (with auto-fix)

Follow the full /deploy workflow:

1. Assess git state (branch, changes)
2. Commit and push to main (or merge feature branch)
3. Watch CI/CD (`gh run watch <RUN_ID> --exit-status`)
4. On success: verify health check (`curl -s https://pl.thirumagal.com/health`)
5. On failure — **auto-fix loop** (max 5 retries):
   - Get logs: `gh run view <RUN_ID> --log-failed`
   - Diagnose root cause from actual log output
   - Fix the issue in **both local code AND CI workflow** if needed:
     - Test failures → fix the test or source code locally, re-run locally to verify
     - Build errors → fix imports, deps, syntax locally
     - CI environment issues → update `.github/workflows/test.yml` or `deploy.yml`
     - Missing dirs/files in CI → add `mkdir -p` steps to workflow
     - Dependency mismatches → update `requirements.txt` or `package.json`
   - Run tests locally before pushing: backend `pytest` + frontend `vitest run`
   - New commit (never amend), push to main
   - Watch new CI/CD run — repeat until green
