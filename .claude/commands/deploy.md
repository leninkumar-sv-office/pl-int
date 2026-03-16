Commit changes, get them to main, trigger CI/CD, monitor until successful. Auto-fix failures and retry.

## Step 1: Assess State

```bash
git status
git diff HEAD --stat
git log --oneline -5
git branch --show-current
```

- If **no changes** to commit and already on main → skip to Step 3 (just push or check latest run)
- If on a **feature branch** → commit there, then merge to main (Step 2b)
- If on **main** → commit directly (Step 2a)

## Step 2a: Commit and Push (on main)

- Stage relevant files — skip `.DS_Store`, `.env`, credentials, `__pycache__`, `*.pyc`
- Do NOT use `git add -A` — add specific files by name
- Commit with a clear message
- Push: `git push origin main`

## Step 2b: Merge Feature Branch to Main

- Commit on current branch, push it
- Switch to main: `git checkout main && git pull origin main`
- Merge: `git merge <branch-name>`
- Push: `git push origin main`
- If merge conflicts: resolve them, commit, then push

## Step 3: Watch CI/CD

```bash
# Wait a moment for the run to register
sleep 3

# Get the latest run ID
gh run list --limit 1 --json databaseId,status,displayTitle

# Watch until completion (--exit-status returns non-zero on failure)
gh run watch <RUN_ID> --exit-status
```

Use a **timeout of 600000ms** (10 minutes) for the `gh run watch` command.

## Step 4: On Success

Report the deployment tag and verify:
```bash
curl -s https://pl.thirumagal.com/health | python3 -m json.tool
```

If health check fails (Cloudflare tunnel may take a few minutes), wait 30s and retry up to 3 times.

## Step 5: On Failure — Auto-Fix Loop

1. **Get failure logs:** `gh run view <RUN_ID> --log-failed`
2. **Diagnose** the root cause from the logs
3. **Fix** the issue — apply fixes to BOTH local codebase AND remote if needed:
   - **Test failures:** Fix the test or the code causing the failure locally, then push
   - **Build errors:** Fix imports, missing deps, syntax errors locally, then push
   - **Health check timeout:** SSH/check the deploy target if needed, fix startup issues
   - **Missing frontend/dist:** Ensure `mkdir -p frontend/dist/assets` runs in CI before backend tests
   - **Dependency issues:** Update `requirements.txt` or `package.json`, install locally to verify, then push
   - **Environment issues:** Check `.env` secrets in GitHub Settings, fix workflow env vars
4. **Run tests locally first** to verify the fix works before pushing:
   - Backend: `cd backend && source venv/bin/activate && python -m pytest tests/ --tb=short -q`
   - Frontend: `cd frontend && npx vitest run`
5. **Build frontend locally** if frontend files changed: `cd frontend && npm run build`
6. **New commit** (never amend), push to main
7. **Watch new CI/CD run** — back to Step 3
8. **Max 5 retries** before asking user for help

## Key Rules

- Always use `gh run list` to get the correct run ID after each push
- Always use `--exit-status` with `gh run watch` to detect failure
- Read actual failing log output — don't guess what broke
- **Fix issues in both local AND CI environments** — if CI has a different path, env, or missing dir, fix the workflow too
- Run tests locally before pushing to avoid wasting CI cycles
- Common failures: test failures, build errors, health check timeout, missing dependencies, missing frontend/dist
- Deploy workflow runs in **app mode** (not Docker) by default
- CI runs tests first (`test.yml`) — deploy is blocked until all tests pass
