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

## Step 2: Run /deploy

Follow the full /deploy workflow:

1. Assess git state (branch, changes)
2. Commit and push to main (or merge feature branch)
3. Watch CI/CD (`gh run watch <RUN_ID> --exit-status`)
4. On success: verify health check (`curl -s https://pl.thirumagal.com/health`)
5. On failure: read logs, fix, push again (auto-fix loop, max 5 retries)
