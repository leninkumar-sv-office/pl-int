---
name: include-test-deploy
description: Add tests for changed code, then deploy through CI/CD. Combines /include-test and /deploy.
user_invocable: true
---

# Include Tests + Deploy

Combines `/include-test` and `/deploy` into a single flow:

1. Run `/include-test` — write tests, run locally, fix failures
2. Run `/deploy` — commit, push, watch CI/CD, verify deployment

This ensures every deploy has test coverage for changed code.
