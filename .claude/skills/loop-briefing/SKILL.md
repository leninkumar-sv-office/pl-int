---
name: loop-briefing
description: Schedule recurring market briefings on an interval. Runs /briefing immediately, then sets up a cron to repeat it every hour (default). All briefing logic lives in /briefing.
user_invocable: true
---

# Loop Briefing

Schedule recurring market briefings. Runs `/briefing` immediately on invocation, then sets up a cron to repeat it on a recurring interval.

**All briefing logic (data fetching, analysis, output format, PDF) lives in `/briefing`.** This skill only handles scheduling.

## Usage

`/loop-briefing [interval]` — default interval is `1h` at the start of each hour

Examples:
- `/loop-briefing` — every 1 hour at :00
- `/loop-briefing 30m` — every 30 minutes
- `/loop-briefing 2h` — every 2 hours
- `/loop-briefing 4h` — every 4 hours

## Steps

1. **Parse the interval** from args. Default to `1h` if not specified. Accept formats like `30m`, `1h`, `2h`, `4h`, `1d`. Also accept natural language like "every 1 hour", "every 30 minutes", etc.

2. **Convert interval to cron expression:**
   - `30m` → `*/30 * * * *`
   - `1h` → `0 * * * *`
   - `2h` → `0 */2 * * *`
   - `4h` → `0 */4 * * *`
   - `1d` → `0 8 * * *` (8:00 AM daily)
   - If user specifies "at minute X", use that minute. Otherwise use minute 0.

3. **IMPORTANT: Run `/briefing` immediately** — invoke the briefing skill NOW so the user sees a full briefing right away. Do NOT skip this step.

4. **After the briefing is displayed**, create a recurring cron using `CronCreate`:
   - `cron`: the expression from step 2
   - `recurring`: true
   - `prompt`: see below

5. **Confirm to user:**
   > Briefing loop active — generating every {interval}.
   > Recurring jobs auto-expire after 3 days.
   > Use CronList / CronDelete to manage.

## Cron Prompt

The prompt passed to CronCreate should be exactly:

```
Generate a fresh market briefing by running /briefing
```
