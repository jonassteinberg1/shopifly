# Meta-PRD: Shopifly Market Research Pipeline

## Overview

**Objective:** Coordinate two parallel workstreams to build a complete Shopify merchant pain point discovery system combining automated scraping with qualitative interview research.

**Execution Model:** Autonomous agents (ralph + beads) working in parallel on independent tasks, with synchronization points for integration work.

---

## Sub-PRDs

| PRD | File | Focus | Status |
|-----|------|-------|--------|
| **Scraping Pipeline** | `.claude/plans/dynamic-chasing-island.md` | Web scraping + LLM classification | ~85% complete |
| **Interview Research** | `.claude/plans/refactored-wobbling-quokka.md` | Merchant interviews + validation | Code: 100%, Process: 0% |
| **Visualization Dashboard** | `.claude/plans/dynamic-chasing-island.md` | Dashboard UI for insights visualization | 0% - NEW |

---

## Important Notes

### Reddit Scraping Approach

**DO NOT USE the Reddit JSON API approach.** Reddit denied our API access request.

**USE ONLY the RSS-based approach** which is already implemented in `scrapers/reddit_selenium.py`:
- Uses public RSS feeds (no API key required)
- Endpoints: `/r/shopify/.rss`, `/r/shopify/new/.rss`, etc.
- Supports fetching comments via RSS
- Already integrated with the scraping pipeline

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SHOPIFLY MARKET RESEARCH SYSTEM                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  WORKSTREAM A: Automated Scraping          WORKSTREAM B: Interview Research │
│  (dynamic-chasing-island.md)               (refactored-wobbling-quokka.md)  │
│  ┌─────────────────────────────┐           ┌─────────────────────────────┐  │
│  │                             │           │                             │  │
│  │  ┌───────────────────────┐  │           │  ┌───────────────────────┐  │  │
│  │  │ Reddit RSS Scraper ✅ │  │           │  │ Recruitment Pipeline  │  │  │
│  │  │ (reddit_selenium.py)  │  │           │  │ (Human Process)       │  │  │
│  │  └───────────┬───────────┘  │           │  └───────────┬───────────┘  │  │
│  │              │              │           │              │              │  │
│  │  ┌───────────┴───────────┐  │           │  ┌───────────┴───────────┐  │  │
│  │  │ App Store Scraper ✅  │  │           │  │ Interview Execution   │  │  │
│  │  │ Community Scraper ✅  │  │           │  │ (Human Process)       │  │  │
│  │  │ Twitter Scraper ✅    │  │           │  └───────────┬───────────┘  │  │
│  │  └───────────┬───────────┘  │           │              │              │  │
│  │              │              │           │  ┌───────────┴───────────┐  │  │
│  │  ┌───────────┴───────────┐  │           │  │ Data Entry CLI ✅     │  │  │
│  │  │ LLM Classifier ✅     │  │           │  │ interview add-*       │  │  │
│  │  └───────────┬───────────┘  │           │  └───────────┬───────────┘  │  │
│  │              │              │           │              │              │  │
│  └──────────────┼──────────────┘           └──────────────┼──────────────┘  │
│                 │                                         │                 │
│                 └─────────────────┬───────────────────────┘                 │
│                                   │                                         │
│                                   ▼                                         │
│                 ┌─────────────────────────────────────────┐                 │
│                 │         UNIFIED INSIGHTS DATABASE        │                 │
│                 │                                         │                 │
│                 │  ┌─────────────┐    ┌─────────────────┐ │                 │
│                 │  │  Scraped    │    │   Interview     │ │                 │
│                 │  │  Insights   │◄──►│   Insights      │ │                 │
│                 │  │  (N=1000s)  │    │   (N=50+)       │ │                 │
│                 │  └─────────────┘    └─────────────────┘ │                 │
│                 │                                         │                 │
│                 └─────────────────┬───────────────────────┘                 │
│                                   │                                         │
│                                   ▼                                         │
│                 ┌─────────────────────────────────────────┐                 │
│                 │      INTERVIEW-ENHANCED RERANKER ✅      │                 │
│                 │                                         │                 │
│                 │  Priority = Scrape Score (65%) +        │                 │
│                 │            Interview Bonus (35%)        │                 │
│                 │                                         │                 │
│                 │  Output: Ranked Product Opportunities   │                 │
│                 └─────────────────┬───────────────────────┘                 │
│                                   │                                         │
│                                   ▼                                         │
│                 ┌─────────────────────────────────────────┐                 │
│                 │        VISUALIZATION DASHBOARD           │                 │
│                 │                                         │                 │
│                 │  - Category breakdown charts            │                 │
│                 │  - Frustration trends over time         │                 │
│                 │  - Top opportunities table              │                 │
│                 │  - Keyword cloud visualization          │                 │
│                 │  - Competitor mention analysis          │                 │
│                 └─────────────────────────────────────────┘                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Task Breakdown for Autonomous Agents

### Parallelization Strategy

Tasks are organized into **independent tracks** that can run simultaneously, with **sync points** where outputs must be integrated.

**Note:** Reddit scraping (A1) is COMPLETE via RSS approach. Do not implement JSON API approach.

```
TIME ──────────────────────────────────────────────────────────────────────────────────────►

TRACK A (Scraping/Classification)   TRACK B (Interview)    TRACK C (Testing)    TRACK E (Visualization)
═════════════════════════════════   ═══════════════════    ═══════════════════  ═══════════════════════

[A1] Reddit RSS ✅                  [B1] Additional CLI    [C1] Unit Tests
     (DONE)                              Commands               for A2, A3
         │                                 │                       │
         ▼                                 │                       │
[A2] Enhanced Classification               │                       │
     Pipeline (HIGH PRIORITY)              │                       │
     - ContentType enum                    │                       │
     - Haiku screening                     │                       │
     - Aggregation views                   │                       │
         │                                 │                       │
         ▼                                 ▼                       ▼
[A3] Reranker                      [B2] Report Export     [C2] Integration
     Module                             Enhancements           Tests
         │                                 │                       │
         └─────────────────────────────────┼───────────────────────┘
                                           │
                                           ▼
                                ═══════════════════════
                                [SYNC] E2E Pipeline Test
                                ═══════════════════════
                                           │
                                           ├───────────────────────────────────┐
                                           ▼                                   ▼
                                [D1] Documentation Update            [E1] Dashboard Backend
                                           │                              API endpoints
                                           ▼                                   │
                                [D2] Docker Verification                       ▼
                                                                     [E2] Dashboard Frontend
                                                                          Charts & UI
                                                                               │
                                                                               ▼
                                                                     [E3] Dashboard Polish
                                                                          Filters & Export
```

---

## Task Specifications

### Track A: Scraping Pipeline Completion

#### A1: Reddit Scraper [STATUS: ✅ COMPLETE]

**DO NOT IMPLEMENT.** Reddit API access was denied.

The RSS-based approach is already implemented in `scrapers/reddit_selenium.py`:
- `RedditSeleniumScraper` class using RSS feeds
- Standalone `scrape_reddit_posts()` function
- Comment fetching via RSS
- Pain point keyword filtering

**Existing Implementation:**
- File: `scrapers/reddit_selenium.py`
- RSS Endpoints: hot, new, top_day/week/month/year/all, rising
- Already exported in `scrapers/__init__.py`

**Verification:**
```bash
# Test RSS scraper directly
python -c "from scrapers.reddit_selenium import scrape_reddit_posts; print(scrape_reddit_posts(limit=3, debug=True))"

# Test via CLI (if integrated)
python main.py scrape --source reddit --storage sqlite --limit 10
```

---

#### A2: Enhanced Classification Pipeline [PRIORITY: HIGH]
**PRD Reference:** `dynamic-chasing-island.md` → Section "LLM Classification Pipeline (ENHANCED)"

**Agent Instructions:**
```
READ: .claude/plans/dynamic-chasing-island.md (Section: LLM Classification Pipeline)

The existing classifier needs enhancement for:
1. Multi-stage processing (pre-filter → Haiku screen → Sonnet classify)
2. New ContentType enum (complaint, feature_request, question, etc.)
3. New fields: urgency_score, price_sensitivity, competitor_mentions
4. Aggregation views for visualization

STAGE 1 - Pre-filtering (no LLM):
- Keyword/heuristic filter before any LLM calls
- Must mention "shopify" OR contain pain keywords
- Minimum 50 char content length

STAGE 2 - Relevance Screening (Haiku):
- Use claude-3-haiku for cheap/fast screening
- Returns: { relevant, content_type, confidence }
- Filter out items with confidence < 0.6

STAGE 3 - Deep Classification (Sonnet):
- Use claude-3-5-sonnet for quality classification
- Process items individually (not batched)
- Concurrency: 5 parallel requests
```

**Files to Create:**
- `analysis/content_types.py` - ContentType enum
- `analysis/relevance_screener.py` - Haiku-based Stage 2 screening
- `analysis/aggregator.py` - Aggregation queries and views

**Files to Modify:**
- `analysis/classifier.py` - Add content_type, urgency_score, competitor_mentions, price_sensitivity
- `storage/sqlite.py` - Update insights schema, add aggregation views
- `main.py` - Add `--model` and `--skip-screening` flags

**Completion Criteria:**
- [ ] ContentType enum with 7 types implemented
- [ ] Pre-filter reduces items by 50-70%
- [ ] Haiku screening works with < $0.001/item cost
- [ ] Deep classification includes all new fields
- [ ] Aggregation views created in SQLite
- [ ] CLI flags for model selection work

---

#### A3: Reranker Module [PRIORITY: MEDIUM]
**PRD Reference:** `dynamic-chasing-island.md` → Section "Priority Reranking Algorithm"

**Agent Instructions:**
```
READ: .claude/plans/dynamic-chasing-island.md (lines 270-317)
CREATE: analysis/reranker.py (base reranker, separate from interview_reranker.py)

Implement calculate_priority() function:
- relevance (LLM score): 30%
- frustration level: 25%
- engagement (upvotes + comments): 20%
- willingness to pay signal: 15%
- recency: 10%

This is the BASE reranker for scraped data only.
The interview_reranker.py (already exists) enhances this with interview data.
```

**Files to Create:**
- `analysis/reranker.py`

**Files to Modify:**
- `analysis/__init__.py` (add export)

**Completion Criteria:**
- [ ] `calculate_priority()` function implemented
- [ ] Weights are configurable
- [ ] Handles missing data gracefully
- [ ] Unit tests pass

---

### Track B: Interview Infrastructure Enhancements

#### B1: Additional CLI Commands [PRIORITY: LOW]
**PRD Reference:** `refactored-wobbling-quokka.md` → Section "Files to Create/Modify"

**Agent Instructions:**
```
The core interview CLI commands are already implemented in main.py:
- interview add-participant
- interview add-insight
- interview stats
- interview list
- interview beta-testers
- interview opportunities

ADD these additional commands:
1. interview import-csv - Bulk import from CSV file
2. interview export-csv - Export all data to CSV
3. interview correlate - Show correlation report with scraped data
```

**Files to Modify:**
- `main.py` (add new commands)

**Completion Criteria:**
- [ ] CSV import/export works
- [ ] Correlation report command works
- [ ] Help text is clear

---

#### B2: Report Export Enhancements [PRIORITY: LOW]
**PRD Reference:** `refactored-wobbling-quokka.md` → Section "Deliverables"

**Agent Instructions:**
```
Enhance scripts/export_interview_report.py:
1. Add --format markdown option
2. Add --format html option (basic HTML report)
3. Add date range filtering (--since, --until)
```

**Files to Modify:**
- `scripts/export_interview_report.py`

**Completion Criteria:**
- [ ] Markdown export works
- [ ] HTML export produces valid HTML
- [ ] Date filtering works

---

### Track C: Testing

#### C1: Unit Tests for New Code [PRIORITY: HIGH]
**Agent Instructions:**
```
Create unit tests for all new code:

For A1 (Reddit JSON Scraper):
- tests/unit/test_reddit_json.py
- Test pagination logic
- Test keyword filtering
- Test JSON parsing
- Mock HTTP responses

For A2 (Reranker):
- tests/unit/test_reranker.py
- Test priority calculation
- Test edge cases (missing data)
- Test weight configuration
```

**Files to Create:**
- `tests/unit/test_reddit_json.py`
- `tests/unit/test_reranker.py`

**Completion Criteria:**
- [ ] 80%+ code coverage for new modules
- [ ] All edge cases tested
- [ ] Tests pass with `pytest tests/unit -v`

---

#### C2: Integration Tests [PRIORITY: MEDIUM]
**Agent Instructions:**
```
Create integration tests:
- tests/integration/test_reddit_json_integration.py
- Test scraper with mocked HTTP but real classifier
- Test full pipeline: scrape → classify → store
```

**Files to Create:**
- `tests/integration/test_reddit_json_integration.py`

**Completion Criteria:**
- [ ] Tests pass without external API calls
- [ ] Pipeline integration verified

---

### Sync Point: E2E Pipeline Test

**Prerequisite:** A1, A2, C1, C2 complete

**Agent Instructions:**
```
Create/update E2E test:
- tests/e2e/test_reddit_json_pipeline.py

Test full pipeline with REAL Reddit data (small limit):
1. Scrape 5 posts via reddit-json
2. Store in SQLite
3. Classify with LLM
4. Verify insights created
5. Run interview-enhanced reranker
6. Verify ranked output
```

**Files to Create/Modify:**
- `tests/e2e/test_reddit_json_pipeline.py`

**Completion Criteria:**
- [ ] E2E test passes with real Reddit data
- [ ] Pipeline produces ranked opportunities

---

### Track E: Visualization Dashboard

#### E1: Dashboard Backend API [PRIORITY: MEDIUM]
**PRD Reference:** `dynamic-chasing-island.md` → Section "Dashboard/Visualization UI"

**Agent Instructions:**
```
READ: .claude/plans/dynamic-chasing-island.md (Section: Dashboard/Visualization UI)

Create REST API endpoints to serve aggregated data for the dashboard:
1. GET /api/insights/summary - Category counts, avg frustration, WTP rates
2. GET /api/insights/trends - Time series data (weekly/monthly)
3. GET /api/insights/keywords - Keyword frequency for word cloud
4. GET /api/insights/competitors - Competitor mention analysis
5. GET /api/insights/opportunities - Top ranked opportunities
6. GET /api/insights/export - Export data as CSV/JSON
```

**Files to Create:**
- `api/__init__.py` - API package
- `api/routes.py` - FastAPI/Flask routes for dashboard endpoints
- `api/schemas.py` - Pydantic response schemas

**Completion Criteria:**
- [ ] All 6 API endpoints implemented
- [ ] Endpoints return properly formatted JSON
- [ ] Filtering by date range works
- [ ] Export endpoint generates valid CSV

---

#### E2: Dashboard Frontend UI [PRIORITY: MEDIUM]
**PRD Reference:** `dynamic-chasing-island.md` → Section "Dashboard/Visualization UI"

**Agent Instructions:**
```
Build a simple web dashboard using a lightweight approach (HTML + Chart.js or Streamlit):

OPTION A - Streamlit (Recommended for speed):
- Single Python file dashboard
- Built-in charts and tables
- Easy deployment

OPTION B - HTML + Chart.js:
- Static HTML served by FastAPI
- Chart.js for visualizations
- More customizable

Dashboard Pages/Sections:
1. Overview - Key metrics cards (total insights, categories, avg frustration)
2. Category Breakdown - Bar chart of insights by category
3. Trends - Line chart of insights over time
4. Word Cloud - Keyword frequency visualization
5. Top Opportunities - Sortable table of ranked opportunities
6. Competitor Analysis - Bar chart of competitor mentions
```

**Files to Create (Streamlit approach):**
- `dashboard/app.py` - Main Streamlit dashboard
- `dashboard/charts.py` - Chart generation helpers
- `dashboard/data.py` - Data fetching from SQLite

**Files to Create (HTML approach):**
- `dashboard/static/index.html` - Dashboard HTML
- `dashboard/static/js/charts.js` - Chart.js visualizations
- `dashboard/static/css/style.css` - Dashboard styling

**Completion Criteria:**
- [ ] Dashboard displays all 6 visualization types
- [ ] Data loads from SQLite correctly
- [ ] Charts render without errors
- [ ] Basic responsive layout works

---

#### E3: Dashboard Polish & Export [PRIORITY: LOW]
**PRD Reference:** `dynamic-chasing-island.md` → Section "Dashboard/Visualization UI"

**Agent Instructions:**
```
Add filtering, interactivity, and export features:

1. Filters:
   - Date range picker
   - Category filter (multi-select)
   - Source filter (Reddit, App Store, etc.)
   - Minimum frustration level slider

2. Interactivity:
   - Click on chart segment to drill down
   - Hover tooltips with details
   - Sortable table columns

3. Export:
   - Export filtered data as CSV
   - Export charts as PNG
   - Generate PDF report
```

**Files to Modify:**
- `dashboard/app.py` or `dashboard/static/js/charts.js`

**Completion Criteria:**
- [ ] All filters work correctly
- [ ] CSV export includes filtered data
- [ ] Charts are interactive (hover, click)

---

### Track D: Documentation & Deployment

#### D1: Documentation Update [PRIORITY: MEDIUM]
**Agent Instructions:**
```
Update README.md with:
1. Reddit JSON scraper usage (no API key needed)
2. Interview CLI commands
3. Report generation commands
4. Full pipeline example
```

**Files to Modify:**
- `README.md`

**Completion Criteria:**
- [ ] All new features documented
- [ ] Examples are runnable

---

#### D2: Docker Verification [PRIORITY: LOW]
**Agent Instructions:**
```
Verify Docker build with new components:
1. Build image
2. Run scrape command
3. Run classify command
4. Run interview commands
5. Run report export
```

**Completion Criteria:**
- [ ] `docker build` succeeds
- [ ] All commands work in container

---

## Dependency Graph

```
     ┌─────┐
     │ A1  │ Reddit RSS Scraper ✅ DONE
     └──┬──┘
        │
        ▼
     ┌─────┐
     │ A2  │ Enhanced Classification Pipeline (HIGH PRIORITY)
     └──┬──┘
        │
        ├────────────────┐
        │                │
        ▼                ▼
     ┌─────┐          ┌─────┐
     │ A3  │          │ C1  │ Unit Tests (for A2, A3)
     └──┬──┘          └──┬──┘
        │                │
        └────────┬───────┘
                 │
                 ▼
              ┌─────┐
              │ C2  │ Integration Tests
              └──┬──┘
                 │
                 ▼
           ┌──────────┐
           │ E2E Test │ (Sync Point)
           └────┬─────┘
                │
        ┌───────┼───────┐
        │       │       │
        ▼       ▼       ▼
     ┌─────┐ ┌─────┐ ┌─────┐
     │ B1  │ │ D1  │ │ D2  │
     └─────┘ └─────┘ └─────┘
     (Independent - can run anytime)

     ┌─────┐
     │ B2  │ (Independent - can run anytime)
     └─────┘
```

---

## Agent Assignment Strategy

### Parallel Execution Groups

**Group 1 (Start Immediately - PRIORITY):**
- Agent 1: A2 (Enhanced Classification Pipeline) - **CRITICAL PATH**

**Group 2 (After A2 or in Parallel):**
- Agent 1: A3 (Reranker Module)
- Agent 2: C1 (Unit Tests for A2, A3)
- Agent 3: B1 (Additional CLI Commands)
- Agent 4: B2 (Report Enhancements)

**Group 3 (After Group 2):**
- Agent 1: C2 (Integration Tests)

**Group 4 (After Sync Point):**
- Agent 1: D1 (Documentation)
- Agent 2: D2 (Docker Verification)

**Note:** A1 (Reddit Scraper) is already complete via RSS approach - no work needed.

---

## Execution Checklist

### Phase 1: Already Complete
- [x] **A1** Reddit RSS Scraper (`scrapers/reddit_selenium.py`) - DONE
- [x] **A1** Exported in `scrapers/__init__.py` - DONE

### Phase 2: Enhanced Classification Pipeline (PRIORITY)
- [ ] **A2** Create `analysis/content_types.py` - ContentType enum
- [ ] **A2** Create `analysis/relevance_screener.py` - Haiku-based screening
- [ ] **A2** Create `analysis/aggregator.py` - Aggregation queries
- [ ] **A2** Update `analysis/classifier.py` - Add new fields (content_type, urgency_score, etc.)
- [ ] **A2** Update `storage/sqlite.py` - Add aggregation views
- [ ] **A2** Update `main.py` - Add `--model` and `--skip-screening` flags
- [ ] **C1** Create `tests/unit/test_content_types.py`
- [ ] **C1** Create `tests/unit/test_relevance_screener.py`

### Phase 3: Reranker & Additional Features (Parallel)
- [ ] **A3** Create `analysis/reranker.py`
- [ ] **A3** Update `analysis/__init__.py`
- [ ] **C1** Create `tests/unit/test_reranker.py`
- [ ] **B1** Add CSV import/export commands to `main.py`
- [ ] **B1** Add correlate command to `main.py`
- [ ] **B2** Add markdown/HTML export formats to `scripts/export_interview_report.py`

### Phase 4: Integration Testing
- [ ] **C2** Create `tests/integration/test_classification_pipeline.py`
- [ ] **C2** Create `tests/integration/test_reddit_rss_integration.py`
- [ ] Run all unit tests: `pytest tests/unit -v`
- [ ] Run integration tests: `pytest tests/integration -v`

### Phase 5: Sync Point - E2E Verification
- [ ] Create/run E2E test: `pytest tests/e2e/test_full_pipeline.py -v`
- [ ] Verify RSS scraper → pre-filter → Haiku screen → Sonnet classify → rerank pipeline

### Phase 6: Polish (Parallel)
- [ ] **D1** Update README.md with classification pipeline docs
- [ ] **D2** Verify Docker build and run

### Phase 7: Visualization Dashboard
- [ ] **E1** Create `api/__init__.py` - API package init
- [ ] **E1** Create `api/routes.py` - Dashboard API endpoints
- [ ] **E1** Create `api/schemas.py` - Response schemas
- [ ] **E2** Create `dashboard/app.py` - Streamlit dashboard (or HTML alternative)
- [ ] **E2** Create `dashboard/charts.py` - Chart generation helpers
- [ ] **E2** Create `dashboard/data.py` - Data fetching layer
- [ ] **E3** Add filters and interactivity
- [ ] **E3** Add export functionality (CSV, PNG)

### Phase 8: Final Verification
- [ ] Full test suite passes: `pytest tests/ -v`
- [ ] Manual verification of CLI commands
- [ ] Docker container runs all commands successfully
- [ ] Classification cost < $2/1000 items
- [ ] Dashboard loads and displays all charts correctly

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Reddit RSS scraper fetches posts | 100+ posts via RSS feeds (no API key) |
| Pre-filter pass rate | 30-50% of raw items |
| Haiku screening pass rate | 60-80% of pre-filtered items |
| Classification cost | < $2 per 1000 raw items |
| Content type distribution | Complaints > 40%, Feature requests > 20% |
| LLM classification accuracy | 90%+ category match on sample |
| Aggregation views work | Category/time/keyword summaries available |
| Interview data integrates | Correlation report generates |
| Priority ranking works | Top opportunities identified |
| All tests pass | 100% green |
| Docker works | All commands run in container |
| **Dashboard loads** | All 6 chart types render correctly |
| **Dashboard API responds** | All endpoints return valid JSON < 500ms |
| **Dashboard filters work** | Date, category, source filters functional |
| **Dashboard export works** | CSV export generates valid file |

---

## Files Summary

### Already Complete
| File | Task | Status |
|------|------|--------|
| `scrapers/reddit_selenium.py` | A1 | ✅ DONE (RSS approach) |
| `scrapers/__init__.py` | A1 | ✅ DONE (exports RedditSeleniumScraper) |

### To Create
| File | Task | Priority |
|------|------|----------|
| `analysis/content_types.py` | A2 | HIGH |
| `analysis/relevance_screener.py` | A2 | HIGH |
| `analysis/aggregator.py` | A2 | HIGH |
| `analysis/reranker.py` | A3 | MEDIUM |
| `tests/unit/test_content_types.py` | C1 | HIGH |
| `tests/unit/test_relevance_screener.py` | C1 | HIGH |
| `tests/unit/test_reranker.py` | C1 | MEDIUM |
| `tests/integration/test_classification_pipeline.py` | C2 | MEDIUM |
| `tests/integration/test_reddit_rss_integration.py` | C2 | MEDIUM |
| `api/__init__.py` | E1 | MEDIUM |
| `api/routes.py` | E1 | MEDIUM |
| `api/schemas.py` | E1 | MEDIUM |
| `dashboard/app.py` | E2 | MEDIUM |
| `dashboard/charts.py` | E2 | MEDIUM |
| `dashboard/data.py` | E2 | MEDIUM |

### To Modify
| File | Task | Priority |
|------|------|----------|
| `analysis/classifier.py` | A2 | HIGH |
| `storage/sqlite.py` | A2 | HIGH |
| `main.py` | A2, B1 | HIGH |
| `analysis/__init__.py` | A2, A3 | MEDIUM |
| `scripts/export_interview_report.py` | B2 | LOW |
| `README.md` | D1 | MEDIUM |

---

## Notes for Autonomous Agents

1. **Read the sub-PRD** for detailed specifications before starting a task
2. **Follow existing patterns** in the codebase - consistency is key
3. **Run tests frequently** - catch issues early
4. **Mark tasks complete** only when verification passes
5. **Don't block on dependencies** - work on independent tasks while waiting
6. **Coordinate at sync points** - ensure all prerequisites are met before integration

---

## Quick Start for Agents

```bash
# Clone context
cd /root/shopifly

# Check current state
python main.py --help
python main.py stats --storage sqlite

# Run existing tests
pytest tests/unit -v
pytest tests/integration -v

# Verify Reddit RSS scraper works (A1 - ALREADY DONE):
python -c "from scrapers.reddit_selenium import scrape_reddit_posts; posts = scrape_reddit_posts(limit=5, debug=True); print(f'Got {len(posts)} posts')"

# Test scraping via CLI:
python main.py scrape --source reddit --storage sqlite --limit 10
python main.py stats --storage sqlite

# After all tasks, full verification:
pytest tests/ -v
python main.py scrape --source reddit --storage sqlite --limit 50
python main.py classify --storage sqlite --limit 20
python main.py interview opportunities --storage sqlite
```
