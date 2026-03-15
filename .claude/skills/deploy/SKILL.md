---
name: deploy
description: Commit, push to main, watch CI/CD deployment, and auto-fix if it fails. Use when user wants to deploy changes through the CI/CD pipeline and ensure it succeeds.
---

# Deploy via CI/CD

Commit all staged/unstaged changes, push to main, trigger CI/CD, and monitor until successful. If CI/CD fails, diagnose the error, fix it, and retry — looping until deployment succeeds.

## Steps

### 1. Stage and Commit

```bash
git status
git diff HEAD --stat
git log --oneline -3
```

- Review all changes (staged + unstaged)
- Stage relevant files (skip `.DS_Store`, credentials, `.env`)
- Create a commit with a clear message describing the changes
- Do NOT use `git add -A` — add specific files

### 2. Push to main

```bash
git push origin main
```

### 3. Watch CI/CD

```bash
# Get the latest run ID
gh run list --limit 1 --json databaseId,status,displayTitle

# Watch it until completion (use --exit-status to get non-zero exit on failure)
gh run watch <RUN_ID> --exit-status
```

Use a timeout of 600000ms (10 minutes) for the watch command.

### 4. On Success

- Report the deployment tag and status
- Verify health endpoint:
  ```bash
  curl -s https://pl.thirumagal.com/health | python3 -m json.tool
  ```

### 5. On Failure — Auto-Fix Loop

If CI/CD fails:

1. **Get the failure logs:**
   ```bash
   gh run view <RUN_ID> --log-failed
   ```

2. **Diagnose** the root cause from the logs

3. **Fix** the issue in the codebase

4. **Rebuild frontend** if frontend files were changed:
   ```bash
   cd frontend && npm run build
   ```

5. **Create a new commit** with the fix (do NOT amend — always new commit)

6. **Push again:**
   ```bash
   git push origin main
   ```

7. **Watch the new CI/CD run** — go back to Step 3

8. **Repeat** until CI/CD succeeds. Max 5 retries before asking the user for help.

## Important Notes

- Always check `gh run list` to get the correct run ID after each push
- Use `gh run watch` with `--exit-status` flag so you can detect failure
- When fixing errors, read the actual failing log output to understand what broke
- Common failures: build errors, health check timeout, missing dependencies
- After successful deployment, confirm with health check on the public URL
- The deploy workflow runs in app mode (not Docker) by default
