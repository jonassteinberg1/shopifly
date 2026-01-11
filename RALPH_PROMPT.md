# Ralph Execution Prompt for Shopifly

## Quick Start

```bash
cd ~/shopifly
claude --dangerously-skip-permissions
```

Then run:

```
/ralph-loop "Execute Shopifly pipeline using Beads for task tracking" --max-iterations 50
```

---

## CRITICAL: Use Beads for Task Tracking

**Before starting ANY work, check what tasks are ready:**

```bash
bd ready    # Shows tasks with no blockers
```

**When starting a task:**
```bash
bd update <task-id> --status in_progress
```

**When completing a task:**
```bash
bd close <task-id>
```

**Current task pipeline (with dependencies):**

```
shopifly-bbu (scrape) → shopifly-nya (classify) → shopifly-43j (dashboard) → shopifly-fkp (start) → shopifly-5gj (tests)
```

Only `bd ready` tasks can be worked on. Complete them in order.

---

## Task Details

### shopifly-bbu: Scrape data from all sources
```bash
bd update shopifly-bbu --status in_progress
python main.py scrape --source reddit --storage sqlite --limit 100
python main.py scrape --source appstore --storage sqlite --limit 50
python main.py scrape --source community --storage sqlite --limit 50
python main.py stats --storage sqlite  # Verify: 150+ raw data points
bd close shopifly-bbu
```

### shopifly-nya: Classify scraped data with LLM
```bash
bd update shopifly-nya --status in_progress
python main.py classify --storage sqlite --limit 200
python main.py stats --storage sqlite  # Verify: 100+ classified insights
bd close shopifly-nya
```

### shopifly-43j: Build Streamlit dashboard with 6 visualizations
```bash
bd update shopifly-43j --status in_progress
# Create dashboard/ directory with:
# - dashboard/__init__.py
# - dashboard/app.py (main Streamlit app)
# - dashboard/data.py (SQLite queries)
# - dashboard/charts.py (chart helpers)
#
# Dashboard sections (see meta-shopifly-orchestrator.md Track E):
# 1. Overview metrics cards
# 2. Category breakdown bar chart
# 3. Trends line chart
# 4. Word cloud visualization
# 5. Top opportunities table
# 6. Competitor analysis chart
bd close shopifly-43j
```

### shopifly-fkp: Start dashboard server on port 8501
```bash
bd update shopifly-fkp --status in_progress
streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501 &
# Verify dashboard loads at http://localhost:8501
bd close shopifly-fkp
```

### shopifly-5gj: Run E2E tests to verify pipeline
```bash
bd update shopifly-5gj --status in_progress
pytest tests/e2e -v
# All tests must pass
bd close shopifly-5gj
```

---

## Workflow Summary

```
1. bd ready                           # What can I work on?
2. bd update <id> --status in_progress  # Claim the task
3. <do the work>                       # Execute the task
4. bd close <id>                       # Mark complete
5. bd ready                           # Next task is now unblocked
6. Repeat until bd ready shows nothing
```

---

## Quality Gates

After each task, verify:

| Task | Verification |
|------|--------------|
| shopifly-bbu | `python main.py stats` shows 150+ raw data points |
| shopifly-nya | `python main.py stats` shows 100+ classified insights |
| shopifly-43j | `ls dashboard/*.py` shows 3-4 Python files |
| shopifly-fkp | `curl http://localhost:8501` returns HTML |
| shopifly-5gj | `pytest tests/e2e -v` shows all green |

---

## Critical Constraints

1. **Use SQLite** - All commands use `--storage sqlite`
2. **Reddit uses RSS** - NOT JSON API (API access denied). Use `scrapers/reddit_selenium.py`
3. **Follow existing patterns** - Look at `storage/sqlite.py`, `analysis/classifier.py`
4. **LLM Model** - `claude-3-haiku-20240307` (in `.env`)

---

## Reference PRDs

- `docs/plans/meta-shopifly-orchestrator.md` - Main orchestration PRD
- `docs/plans/dynamic-chasing-island.md` - Scraping pipeline details
- `docs/plans/deployment-orchestration.md` - Deployment details

---

## Concise Ralph Command

```
/ralph-loop "Execute Shopifly pipeline with Beads task tracking:

1. Run bd ready to see available tasks
2. For each ready task:
   - bd update <id> --status in_progress
   - Execute the task (scrape/classify/build dashboard/etc)
   - Verify completion criteria
   - bd close <id>
3. Repeat until all tasks complete

Current pipeline: shopifly-bbu → shopifly-nya → shopifly-43j → shopifly-fkp → shopifly-5gj

Use SQLite storage. Reddit uses RSS. See RALPH_PROMPT.md for task details." --max-iterations 50
```

---

## Scope Control: OUT OF SCOPE Items

Do NOT implement these - they are explicitly OUT OF SCOPE for this phase:

### Scraping (shopifly-bbu)
- Twitter scraping (API issues)
- Historical data (only current/recent)

### Classification (shopifly-nya)
- Enhanced classification (A2) - ContentType enum, Haiku screening
- Sonnet model usage
- Competitor mention extraction

### Dashboard (shopifly-43j)
- Filters and interactivity
- Export to PDF/CSV
- User authentication
- Mobile responsive design
- Dark mode

### Infrastructure
- HTTPS setup
- Domain configuration
- Nginx reverse proxy
- Docker deployment

If you find yourself working on any of these, STOP and refocus on the core task.

---

## Logging Requirement

**You MUST log all significant actions to `execution.log`.**

### Log Format
```
[TIMESTAMP] [TASK-ID] [ACTION] Message
```

### What to Log
```bash
# Starting a task
echo "[$(date -Iseconds)] [shopifly-bbu] [START] Beginning scrape task" >> execution.log

# Command execution
echo "[$(date -Iseconds)] [shopifly-bbu] [RUN] python main.py scrape --source reddit --storage sqlite --limit 100" >> execution.log

# Results
echo "[$(date -Iseconds)] [shopifly-bbu] [RESULT] Scraped 100 reddit posts" >> execution.log

# Errors
echo "[$(date -Iseconds)] [shopifly-bbu] [ERROR] Scraper failed: connection timeout" >> execution.log

# Completion
echo "[$(date -Iseconds)] [shopifly-bbu] [DONE] Task complete, closing in Beads" >> execution.log
```

### Example Session Log
```
[2026-01-10T16:30:00+00:00] [shopifly-bbu] [START] Beginning scrape task
[2026-01-10T16:30:01+00:00] [shopifly-bbu] [RUN] python main.py scrape --source reddit --storage sqlite --limit 100
[2026-01-10T16:31:15+00:00] [shopifly-bbu] [RESULT] Scraped 98 reddit posts
[2026-01-10T16:31:16+00:00] [shopifly-bbu] [RUN] python main.py scrape --source appstore --storage sqlite --limit 50
[2026-01-10T16:32:30+00:00] [shopifly-bbu] [RESULT] Scraped 50 appstore reviews
[2026-01-10T16:32:31+00:00] [shopifly-bbu] [VERIFY] python main.py stats shows 148 raw data points
[2026-01-10T16:32:32+00:00] [shopifly-bbu] [DONE] Task complete, closing in Beads
```

This log helps humans understand what AI did and debug issues.

---

## Git Workflow & Rollback Strategy

**AI work happens on a feature branch, NOT main.**

### Before Starting
```bash
# Create feature branch
git checkout -b ai/pipeline-$(date +%Y%m%d-%H%M)

# Tag current state for easy rollback
git tag pre-ai-run-$(date +%Y%m%d-%H%M)
```

### During Work
```bash
# Commit after each task completion
git add -A
git commit -m "Complete shopifly-XXX: <task description>"
```

### After Completion
```bash
# Push branch for review
git push origin ai/pipeline-YYYYMMDD-HHMM

# Human reviews, then merges
# (See docs/CODE_REVIEW.md)
```

### Rollback (if something goes wrong)
```bash
# Option 1: Reset to tag
git checkout main
git reset --hard pre-ai-run-YYYYMMDD-HHMM

# Option 2: Delete branch and start over
git checkout main
git branch -D ai/pipeline-YYYYMMDD-HHMM

# Option 3: Restore specific file
git checkout pre-ai-run-YYYYMMDD-HHMM -- path/to/file.py
```

### Important
- NEVER commit directly to main
- ALWAYS create tag before starting
- Commit frequently (after each task)
