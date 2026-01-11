# Agent Instructions

This project uses **bd** (Beads) for task tracking. **You MUST use bd commands to track your work.**

## MANDATORY Workflow

```bash
# 1. ALWAYS start by checking what's ready
bd ready

# 2. Claim the task before starting work
bd update <task-id> --status in_progress

# 3. Do the work

# 4. Close the task when done
bd close <task-id>

# 5. Check what's next
bd ready
```

## Current Task Pipeline

```
shopifly-bbu → shopifly-nya → shopifly-43j → shopifly-fkp → shopifly-5gj
   (scrape)      (classify)    (dashboard)    (start)       (e2e tests)
```

Tasks are blocked until their dependencies complete. `bd ready` shows only unblocked tasks.

## Quick Reference

```bash
bd ready              # Find available work (UNBLOCKED tasks only)
bd list               # List all tasks
bd show <id>          # View task details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd dep tree <id>      # Show dependency tree
```

## Shopifly-Specific Instructions

### Key Constraints
- **Use SQLite storage** - All commands use `--storage sqlite`
- **Reddit uses RSS** - NOT JSON API (denied). Use `scrapers/reddit_selenium.py`
- **LLM Model** - `claude-3-haiku-20240307` (see `.env`)

### Reference PRDs
- `docs/plans/meta-shopifly-orchestrator.md` - Main orchestration
- `docs/plans/dynamic-chasing-island.md` - Scraping details
- `RALPH_PROMPT.md` - Detailed task execution instructions

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST:

1. **Update Beads** - Close finished tasks, note progress on in_progress tasks
2. **Run quality gates** - Tests, linters if code changed
3. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
4. **Report status** - What's done, what's next

**CRITICAL:** Work is NOT complete until `git push` succeeds. NEVER stop before pushing.
