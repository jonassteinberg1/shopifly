# Meta-PRD: Shopifly Market Research Pipeline

## Overview

**Objective:** Coordinate two parallel workstreams to build a complete Shopify merchant pain point discovery system combining automated scraping with qualitative interview research.

**Execution Model:** Autonomous agents (ralph + beads) working in parallel on independent tasks, with synchronization points for integration work.

---

## Sub-PRDs

| PRD | File | Focus | Status |
|-----|------|-------|--------|
| **Scraping Pipeline** | `docs/plans/dynamic-chasing-island.md` | Web scraping + LLM classification | ~85% complete |
| **Interview Research** | `docs/plans/refactored-wobbling-quokka.md` | Merchant interviews + validation | Code: 100%, Process: 0% |
| **Visualization Dashboard** | `docs/plans/dynamic-chasing-island.md` | Dashboard UI for insights visualization | 0% - NEW |
| **Deployment & Orchestration** | `docs/plans/deployment-orchestration.md` | AWS EC2, automation, systemd services | NEW |

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
TIME ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────►

TRACK A (Scraping/Class)   TRACK B (Interview)    TRACK C (Testing)    TRACK E (Visualization)   TRACK F (Transcription)
════════════════════════   ═══════════════════    ═══════════════════  ═══════════════════════   ═══════════════════════

[A1] Reddit RSS ✅         [B1] Additional CLI    [C1] Unit Tests                                 [F4] Directory Setup
     (DONE)                     Commands               for A2, A3                                      │
         │                        │                       │                                            ▼
         ▼                        │                       │                                      [F1] VTT + Whisper
[A2] Enhanced Classification      │                       │                                           Integration
     Pipeline (HIGH PRI)          │                       │                                            │
     - ContentType enum           │                       │                                            ▼
     - Haiku screening            │                       │                                      [F2] Transcript
     - Aggregation views          │                       │                                           Classification
         │                        │                       │                                            │
         ▼                        ▼                       ▼                                            ▼
[A3] Reranker             [B2] Report Export     [C2] Integration                              [F3] E2E Processing
     Module                    Enhancements           Tests                                            │
         │                        │                       │                                            ▼
         │                        │                       │                                      [F5] Transcription
         │                        │                       │                                           E2E Tests
         │                        │                       │                                       (VTT + Whisper)
         │                        │                       │                                            │
         └────────────────────────┴───────────────────────┼────────────────────────────────────────────┘
                                                          │
                                                          ▼
                                               ═══════════════════════
                                               [SYNC] E2E Pipeline Test
                                               ═══════════════════════
                                                          │
                                          ┌───────────────┼───────────────┐
                                          ▼               ▼               ▼
                               [D1] Documentation   [E1] Dashboard   [E2] Dashboard
                                    Update              Backend          Frontend
                                          │               │               │
                                          ▼               ▼               ▼
                               [D2] Docker         [E3] Dashboard    Dashboard
                                    Verification        Polish        Complete
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

### Track F: Interview Transcription Pipeline (NEW)

#### F1: Transcription Integration [PRIORITY: HIGH]
**Objective:** Enable transcription of recorded interviews via Zoom VTT import OR local Whisper processing.

**Agent Instructions:**
```
Implement interview transcription workflow with two paths:

PATH A - Zoom VTT Import (preferred):
1. Parse VTT transcript files from Zoom
2. Convert to unified JSON transcript format
3. Add CLI command for VTT import

PATH B - Whisper Local (fallback):
1. Add openai-whisper dependency
2. Create transcription module
3. Add CLI command for audio transcription
4. Store transcripts as JSON
```

**Files to Create:**
- `research/transcription.py` - Whisper integration + VTT parser module

**Files to Modify:**
- `main.py` - Add `interview transcribe`, `interview import-vtt`, and `interview process-recording` commands
- `pyproject.toml` - Add `openai-whisper` dependency (optional, for Path B)

**Completion Criteria:**
- [ ] `interview import-vtt <file.vtt>` command works (Zoom transcripts)
- [ ] `interview transcribe <audio_file>` command works (Whisper fallback)
- [ ] Supports base/medium/large Whisper models
- [ ] Both paths output unified JSON transcript format
- [ ] Transcripts stored in `./data/interviews/transcripts/`

---

#### F2: Transcript Classification [PRIORITY: HIGH]
**Objective:** Extract structured insights from interview transcripts using LLM.

**Agent Instructions:**
```
Implement transcript-to-insights pipeline:
1. Create transcript classifier using LLM
2. Extract multiple pain points per transcript
3. Extract WTP signals and participant profile
4. Store insights in interview_insights table
```

**Files to Create:**
- `research/transcript_classifier.py` - LLM-based transcript analysis

**Files to Modify:**
- `main.py` - Add `interview classify-transcript` command
- `storage/sqlite.py` - Ensure interview tables support transcript-derived data

**Completion Criteria:**
- [ ] `interview classify-transcript <transcript.json>` command works
- [ ] Extracts pain points with categories, frustration levels, quotes
- [ ] Extracts WTP signals
- [ ] Stores insights linked to participant ID
- [ ] Works with existing interview-enhanced reranker

---

#### F3: End-to-End Interview Processing [PRIORITY: MEDIUM]
**Objective:** Single command to process recording → transcript → insights.

**Agent Instructions:**
```
Create unified command that:
1. Transcribes audio file
2. Classifies transcript
3. Stores all data
4. Reports summary of extracted insights
```

**Files to Modify:**
- `main.py` - Add `interview process-recording` command

**Completion Criteria:**
- [ ] `interview process-recording <audio.mp3>` runs full pipeline
- [ ] Prints summary of insights extracted
- [ ] Handles errors gracefully (e.g., bad audio)

---

#### F4: Interview Data Directories Setup [PRIORITY: LOW]
**Objective:** Ensure proper directory structure for interview data.

**Agent Instructions:**
```
Create directory structure and .gitkeep files:
- data/interviews/recordings/
- data/interviews/transcripts/
- data/interviews/insights/
```

**Files to Create:**
- `data/interviews/recordings/.gitkeep`
- `data/interviews/transcripts/.gitkeep`
- `data/interviews/insights/.gitkeep`

**Completion Criteria:**
- [ ] Directories exist
- [ ] .gitkeep files committed

---

#### F5: Transcription E2E Tests [PRIORITY: HIGH]
**Objective:** Comprehensive E2E tests for both Zoom VTT import and Whisper transcription paths.

**Agent Instructions:**
```
Create E2E tests covering both transcription paths:

1. Zoom VTT Import Tests:
   - Parse real VTT file format
   - Convert VTT to unified JSON transcript format
   - Verify timestamps are preserved
   - Test CLI command: interview import-vtt
   - Test with sample VTT file (create test fixture)

2. Whisper Transcription Tests:
   - Transcribe sample audio file
   - Verify JSON output format
   - Test different Whisper models (base/medium)
   - Test CLI command: interview transcribe
   - Test with short sample audio (create test fixture)

3. Transcript Classification Tests:
   - Extract insights from transcript
   - Verify pain points are categorized correctly
   - Verify WTP signals are extracted
   - Test CLI command: interview classify-transcript

4. End-to-End Pipeline Tests:
   - VTT → JSON → Classification → Database
   - Audio → Whisper → JSON → Classification → Database
   - Verify insights appear in interview opportunities
   - Test CLI command: interview process-recording
```

**Test Fixtures to Create:**
- `tests/fixtures/sample_interview.vtt` - Sample Zoom VTT transcript
- `tests/fixtures/sample_interview.mp3` - Short (10-15 sec) sample audio
- `tests/fixtures/sample_transcript.json` - Pre-created transcript for classification tests

**Files to Create:**
- `tests/e2e/test_transcription_pipeline.py` - Full E2E transcription tests
- `tests/unit/test_vtt_parser.py` - VTT parsing unit tests
- `tests/unit/test_whisper_transcription.py` - Whisper integration unit tests
- `tests/unit/test_transcript_classifier.py` - Classification unit tests

**E2E Test Cases:**

```python
@pytest.mark.e2e
class TestZoomVTTImport:
    """E2E tests for Zoom VTT transcript import."""

    def test_e2e_vtt_parse_format(self, sample_vtt_file):
        """Test VTT file parsing produces correct JSON structure."""
        # Verify timestamps, segments, full_text

    def test_e2e_vtt_import_cli(self, cli_runner, sample_vtt_file, cli_db_path):
        """Test interview import-vtt CLI command."""
        # Run CLI, verify transcript stored

    def test_e2e_vtt_to_classification(self, sample_vtt_file, cli_db_path):
        """Test full VTT → JSON → Classification pipeline."""
        # Import VTT, classify, verify insights in DB

    def test_e2e_vtt_with_participant_link(self, sample_vtt_file, cli_db_path):
        """Test VTT import linked to participant ID."""
        # Add participant, import VTT with --participant, verify link


@pytest.mark.e2e
class TestWhisperTranscription:
    """E2E tests for Whisper audio transcription."""

    @pytest.mark.slow  # Mark as slow - Whisper takes time
    def test_e2e_whisper_transcribe_audio(self, sample_audio_file):
        """Test Whisper transcription of audio file."""
        # Transcribe, verify JSON output

    @pytest.mark.slow
    def test_e2e_whisper_cli(self, cli_runner, sample_audio_file, cli_db_path):
        """Test interview transcribe CLI command."""
        # Run CLI with --model base, verify transcript created

    def test_e2e_whisper_model_selection(self, sample_audio_file):
        """Test different Whisper model sizes."""
        # Test base vs medium model selection

    def test_e2e_whisper_output_format(self, sample_audio_file):
        """Test Whisper output matches unified JSON format."""
        # Verify same format as VTT import


@pytest.mark.e2e
class TestTranscriptClassification:
    """E2E tests for LLM transcript classification."""

    def test_e2e_classify_transcript_extracts_pain_points(self, sample_transcript):
        """Test classification extracts pain points from transcript."""
        # Classify, verify pain_points list populated

    def test_e2e_classify_transcript_extracts_wtp(self, sample_transcript):
        """Test classification extracts WTP signals."""
        # Verify wtp_signals extracted from budget discussion

    def test_e2e_classify_transcript_cli(self, cli_runner, sample_transcript_file, cli_db_path):
        """Test interview classify-transcript CLI command."""
        # Run CLI, verify insights stored in DB

    def test_e2e_classify_transcript_multiple_insights(self, sample_transcript):
        """Test classification extracts multiple distinct pain points."""
        # Verify 2+ pain points from single interview


@pytest.mark.e2e
class TestFullTranscriptionPipeline:
    """E2E tests for complete transcription pipelines."""

    def test_e2e_vtt_full_pipeline(self, sample_vtt_file, cli_db_path):
        """Test VTT → JSON → Classify → DB → Opportunities."""
        # Full pipeline, verify in opportunities output

    @pytest.mark.slow
    def test_e2e_audio_full_pipeline(self, sample_audio_file, cli_db_path):
        """Test Audio → Whisper → JSON → Classify → DB."""
        # Full pipeline with real audio

    def test_e2e_process_recording_cli(self, cli_runner, sample_audio_file, cli_db_path):
        """Test interview process-recording one-command pipeline."""
        # Single command does transcribe + classify

    def test_e2e_transcribed_insights_in_dashboard_data(self, sample_vtt_file, cli_db_path):
        """Test transcribed insights appear in dashboard queries."""
        # Import, classify, verify in aggregation queries

    def test_e2e_transcribed_insights_correlation(self, sample_vtt_file, cli_db_path):
        """Test transcribed insights correlate with scraped data."""
        # Add scraped data, import interview, run correlation
```

**Sample VTT Fixture Format:**
```vtt
WEBVTT

00:00:00.000 --> 00:00:05.000
Thanks for taking the time to chat today.

00:00:05.500 --> 00:00:12.000
So tell me, what's the biggest challenge you face running your Shopify store?

00:00:13.000 --> 00:00:28.000
Honestly, inventory management is killing me. I have products on Amazon and Etsy too, and keeping stock levels synced is a nightmare. I'd easily pay thirty dollars a month for something that just works.

00:00:29.000 --> 00:00:35.000
That sounds frustrating. What have you tried so far?

00:00:36.000 --> 00:00:48.000
I tried Stocky but it doesn't work with my other channels. I've also looked at Skubana but it's way too expensive for my size store.
```

**Completion Criteria:**
- [ ] All E2E tests pass for VTT import path
- [ ] All E2E tests pass for Whisper transcription path
- [ ] Tests use realistic fixtures (VTT, audio, transcript JSON)
- [ ] Slow tests marked with `@pytest.mark.slow`
- [ ] Tests verify insights appear in opportunities report
- [ ] Tests verify correlation with scraped data works

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

### Phase 8: Interview Transcription Pipeline
- [ ] **F4** Create `data/interviews/recordings/.gitkeep`
- [ ] **F4** Create `data/interviews/transcripts/.gitkeep`
- [ ] **F4** Create `data/interviews/insights/.gitkeep`
- [ ] **F1** Add `openai-whisper` to `pyproject.toml`
- [ ] **F1** Create `research/transcription.py` - VTT parser + Whisper integration
- [ ] **F1** Add `interview import-vtt` CLI command (Zoom transcripts)
- [ ] **F1** Add `interview transcribe` CLI command (Whisper fallback)
- [ ] **F2** Create `research/transcript_classifier.py` - LLM classification
- [ ] **F2** Add `interview classify-transcript` CLI command
- [ ] **F3** Add `interview process-recording` CLI command (end-to-end)

### Phase 8b: Transcription Pipeline Tests
- [ ] **F5** Create `tests/fixtures/sample_interview.vtt` - Sample VTT fixture
- [ ] **F5** Create `tests/fixtures/sample_transcript.json` - Sample transcript fixture
- [ ] **F5** Create `tests/fixtures/sample_interview.mp3` - Short audio fixture (optional)
- [ ] **F5** Create `tests/unit/test_vtt_parser.py` - VTT parsing tests
- [ ] **F5** Create `tests/unit/test_whisper_transcription.py` - Whisper tests
- [ ] **F5** Create `tests/unit/test_transcript_classifier.py` - Classification tests
- [ ] **F5** Create `tests/e2e/test_transcription_pipeline.py` - Full E2E tests
- [ ] **F5** Test VTT import path: VTT → JSON → Classify → DB
- [ ] **F5** Test Whisper path: Audio → JSON → Classify → DB
- [ ] **F5** Test transcribed insights appear in opportunities report

### Phase 9: Final Verification
- [ ] Full test suite passes: `pytest tests/ -v`
- [ ] Manual verification of CLI commands
- [ ] Docker container runs all commands successfully
- [ ] Classification cost < $2/1000 items
- [ ] Dashboard loads and displays all charts correctly
- [ ] Interview transcription works end-to-end
- [ ] Transcribed insights appear in dashboard alongside scraped data

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
| **Whisper transcription works** | Audio → JSON transcript in < 5 min (25 min recording) |
| **Transcript classification works** | Extracts 2+ pain points per interview |
| **E2E interview pipeline works** | Recording → insights in database in one command |
| **Combined visualization** | Dashboard shows scraped + interview data together |

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
| `research/transcription.py` | F1 | HIGH |
| `research/transcript_classifier.py` | F2 | HIGH |
| `tests/unit/test_content_types.py` | C1 | HIGH |
| `tests/unit/test_relevance_screener.py` | C1 | HIGH |
| `tests/unit/test_reranker.py` | C1 | MEDIUM |
| `tests/unit/test_vtt_parser.py` | F5 | HIGH |
| `tests/unit/test_whisper_transcription.py` | F5 | HIGH |
| `tests/unit/test_transcript_classifier.py` | F5 | HIGH |
| `tests/e2e/test_transcription_pipeline.py` | F5 | HIGH |
| `tests/fixtures/sample_interview.vtt` | F5 | HIGH |
| `tests/fixtures/sample_interview.mp3` | F5 | MEDIUM |
| `tests/fixtures/sample_transcript.json` | F5 | HIGH |
| `tests/integration/test_classification_pipeline.py` | C2 | MEDIUM |
| `tests/integration/test_reddit_rss_integration.py` | C2 | MEDIUM |
| `api/__init__.py` | E1 | MEDIUM |
| `api/routes.py` | E1 | MEDIUM |
| `api/schemas.py` | E1 | MEDIUM |
| `dashboard/app.py` | E2 | MEDIUM |
| `dashboard/charts.py` | E2 | MEDIUM |
| `dashboard/data.py` | E2 | MEDIUM |
| `data/interviews/recordings/.gitkeep` | F4 | LOW |
| `data/interviews/transcripts/.gitkeep` | F4 | LOW |
| `data/interviews/insights/.gitkeep` | F4 | LOW |

### To Modify
| File | Task | Priority |
|------|------|----------|
| `analysis/classifier.py` | A2 | HIGH |
| `storage/sqlite.py` | A2, F2 | HIGH |
| `main.py` | A2, B1, F1, F2, F3 | HIGH |
| `pyproject.toml` | F1 | HIGH |
| `analysis/__init__.py` | A2, A3 | MEDIUM |
| `scripts/export_interview_report.py` | B2 | LOW |
| `README.md` | D1 | MEDIUM |

---

## Deployment & Execution Architecture

> **Full deployment documentation:** See [`docs/plans/deployment-orchestration.md`](deployment-orchestration.md) for complete setup instructions, automation scripts, and operational procedures.

### Overview

The entire Shopifly stack runs on a **single AWS EC2 instance**. There are no productionization concerns - this system is designed for personal use by 1-2 people. The VM can be started and stopped as needed.

### Production Instance

| Property | Value |
|----------|-------|
| **Instance ID** | `i-0f05fffd1aba8db0b` |
| **Type** | t3.xlarge (4 vCPU, 16 GB RAM) |
| **Public IP** | 54.197.8.56 |
| **Storage** | 150 GB gp3 |
| **Region** | us-east-1a |
| **Dashboard** | http://54.197.8.56:8501 |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SINGLE VM DEPLOYMENT                                    │
│                 AWS EC2: i-0f05fffd1aba8db0b (t3.xlarge)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         SHOPIFLY STACK                                   ││
│  │                                                                          ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ ││
│  │  │   SCRAPERS   │  │  LLM ANALYSIS │  │ AGGREGATION  │  │VISUALIZATION│ ││
│  │  │              │  │               │  │              │  │             │ ││
│  │  │ • Reddit RSS │  │ • Pre-filter  │  │ • SQLite DB  │  │ • Streamlit │ ││
│  │  │ • App Store  │  │ • Haiku screen│  │ • Views      │  │ • Charts    │ ││
│  │  │ • Twitter    │  │ • Sonnet class│  │ • Reranker   │  │ • Tables    │ ││
│  │  │ • Community  │  │ • Interview   │  │              │  │ • Export    │ ││
│  │  │              │  │   classifier  │  │              │  │             │ ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ ││
│  │         │                 │                 │                 │         ││
│  │         └─────────────────┴─────────────────┴─────────────────┘         ││
│  │                                   │                                      ││
│  │                                   ▼                                      ││
│  │                    ┌──────────────────────────────┐                      ││
│  │                    │      SQLite Database         │                      ││
│  │                    │      (./data/shopifly.db)    │                      ││
│  │                    └──────────────────────────────┘                      ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    INTERVIEW TRANSCRIPTION PIPELINE                      ││
│  │                                                                          ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ ││
│  │  │   MEETING    │  │SPEECH-TO-TEXT│  │   TRANSCRIPT │  │    LLM      │ ││
│  │  │  RECORDING   │──▶│  (Whisper)   │──▶│    JSON     │──▶│ CLASSIFIER │ ││
│  │  │              │  │              │  │              │  │             │ ││
│  │  │ • Zoom       │  │ • Local      │  │ • Structured │  │ • Extract   │ ││
│  │  │ • Meet       │  │ • Fast       │  │ • Timestamped│  │   insights  │ ││
│  │  │ • Audio file │  │ • Offline    │  │ • Diarized   │  │ • Categorize│ ││
│  │  │              │  │              │  │              │  │ • Store     │ ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ ││
│  │                                                                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Execution Workflow

The system is designed to be run manually as needed. There's no scheduler or always-on services.

```bash
# ═══════════════════════════════════════════════════════════════════════════
# TYPICAL WORKFLOW: Data Collection → Analysis → Visualization
# ═══════════════════════════════════════════════════════════════════════════

# STEP 1: Scrape fresh data from all sources
python main.py scrape --storage sqlite --limit 100
python main.py scrape --source reddit --storage sqlite --limit 50
python main.py scrape --source appstore --storage sqlite --limit 30
python main.py scrape --source community --storage sqlite --limit 30

# STEP 2: Classify scraped data with LLM
python main.py classify --storage sqlite --limit 100

# STEP 3: View statistics and aggregations
python main.py stats --storage sqlite

# STEP 4: View ranked opportunities
python main.py interview opportunities --storage sqlite

# STEP 5: Launch visualization dashboard
streamlit run dashboard/app.py
# Dashboard available at http://localhost:8501
```

### VM Requirements

| Resource | Minimum | Recommended | Notes |
|----------|---------|-------------|-------|
| CPU | 2 cores | 4 cores | For Whisper transcription |
| RAM | 4 GB | 8 GB | Whisper models need memory |
| Disk | 20 GB | 50 GB | Audio files + database |
| Python | 3.11+ | 3.11+ | Required |
| OS | Linux | Amazon Linux 2023 / Ubuntu | Docker optional |

### Environment Setup

```bash
# Clone repository
git clone <repo-url> ~/shopifly
cd ~/shopifly

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Install Whisper for transcription
pip install openai-whisper

# Configure environment
cp .env.example .env
# Edit .env with ANTHROPIC_API_KEY (required for classification)

# Initialize database
python main.py stats --storage sqlite  # Creates DB if needed
```

### Running Components

#### Scrapers
```bash
# Run all scrapers
python main.py scrape --storage sqlite --limit 100

# Run individual scrapers
python main.py scrape --source reddit --storage sqlite --limit 50
python main.py scrape --source appstore --storage sqlite --limit 30
python main.py scrape --source community --storage sqlite --limit 30
python main.py scrape --source twitter --storage sqlite --limit 30
```

#### LLM Classification
```bash
# Classify unprocessed data (Haiku screening + Sonnet classification)
python main.py classify --storage sqlite --limit 100

# Skip screening, use Sonnet for everything (more expensive)
python main.py classify --storage sqlite --skip-screening --limit 50

# Use Haiku only (cheapest)
python main.py classify --storage sqlite --model haiku --limit 100
```

#### Interview Data Management
```bash
# Add interview participant
python main.py interview add-participant

# Add insight from interview
python main.py interview add-insight

# View interview statistics
python main.py interview stats

# View ranked opportunities (combines scraped + interview data)
python main.py interview opportunities --storage sqlite
```

#### Visualization Dashboard
```bash
# Start dashboard (default port 8501)
streamlit run dashboard/app.py

# Custom port
streamlit run dashboard/app.py --server.port 8080

# Accessible remotely (for VM deployment)
streamlit run dashboard/app.py --server.address 0.0.0.0
```

---

## Live Interview Transcription Pipeline

### Overview

Live interview data flows through a speech-to-text pipeline before being classified alongside scraped data. This allows verbal conversations to be processed by the same LLM classification pipeline.

**Two transcription paths are supported:**
- **Path A (Preferred):** Use Zoom's native transcription (VTT file) - no local processing needed
- **Path B (Fallback):** Use Whisper locally for any audio file (Google Meet, phone recordings, etc.)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│               INTERVIEW TRANSCRIPTION → CLASSIFICATION FLOW                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: Record Interview                                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  • Record Zoom/Google Meet call (get participant consent)              │ │
│  │  • Or record audio directly (phone recorder, Otter.ai, etc.)           │ │
│  │  • Save as: interview_YYYYMMDD_participantid.mp3 (or .wav/.m4a)       │ │
│  │  • Store in: ./data/interviews/recordings/                             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                      │
│                          ┌────────────┴────────────┐                        │
│                          ▼                         ▼                        │
│  STEP 2A: Zoom Native Transcript       STEP 2B: Transcribe with Whisper    │
│  ┌─────────────────────────────┐      ┌─────────────────────────────────┐  │
│  │  • Download VTT from Zoom   │      │  python main.py interview       │  │
│  │  • Requires Pro/Biz license │      │    transcribe <audio_file>      │  │
│  │  • Cloud recording enabled  │      │                                 │  │
│  │  • Auto-generated after mtg │      │  • Uses OpenAI Whisper locally  │  │
│  │                             │      │  • Model: base/medium/large     │  │
│  │  python main.py interview   │      │  • No API cost, runs offline    │  │
│  │    import-vtt <file.vtt>    │      │  • Works with any audio format  │  │
│  └─────────────────────────────┘      └─────────────────────────────────┘  │
│                          │                         │                        │
│                          └────────────┬────────────┘                        │
│                                       ▼                                      │
│                    ┌──────────────────────────────────┐                     │
│                    │  Transcript JSON (unified format) │                     │
│                    │  ./data/interviews/transcripts/   │                     │
│                    └──────────────────────────────────┘                     │
│                                       │                                      │
│                                       ▼                                      │
│  STEP 3: Extract & Classify Insights                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  Command: python main.py interview classify-transcript <transcript>    │ │
│  │                                                                        │ │
│  │  • LLM reads full transcript                                           │ │
│  │  • Extracts: pain points, WTP signals, competitor mentions, quotes     │ │
│  │  • Categorizes each insight (same categories as scraped data)          │ │
│  │  • Assigns frustration levels, urgency scores                          │ │
│  │  • Stores as interview_insights in SQLite                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                      │
│                                       ▼                                      │
│  STEP 4: Merge with Scraped Data                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  • Interview insights join unified insights database                   │ │
│  │  • Interview-enhanced reranker boosts interview-validated pain points  │ │
│  │  • Dashboard shows combined view (scraped + interview data)            │ │
│  │  • Correlation reports identify validated vs interview-only insights   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Transcription Commands

```bash
# ═══════════════════════════════════════════════════════════════════════════
# INTERVIEW TRANSCRIPTION WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# PATH A: Zoom Native Transcript (Preferred - no local processing)
# ─────────────────────────────────────────────────────────────────────────────
# 1. Enable cloud recording + transcription in Zoom settings
# 2. Record interview to cloud
# 3. Download VTT file from Zoom portal after meeting
# 4. Import VTT into Shopifly:

python main.py interview import-vtt ./downloads/interview_20250109.vtt --participant p001

# ─────────────────────────────────────────────────────────────────────────────
# PATH B: Whisper Local Transcription (For non-Zoom or offline)
# ─────────────────────────────────────────────────────────────────────────────
# Transcribe a recorded interview (any audio format)
python main.py interview transcribe ./data/interviews/recordings/interview_20250109_p001.mp3

# Transcribe with specific Whisper model (base=fast, medium=balanced, large=best)
python main.py interview transcribe ./data/interviews/recordings/interview.mp3 --model medium

# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION (Same for both paths)
# ─────────────────────────────────────────────────────────────────────────────
# Classify insights from transcript
python main.py interview classify-transcript ./data/interviews/transcripts/interview_20250109_p001.json

# Or do both (transcribe + classify) in one command
python main.py interview process-recording ./data/interviews/recordings/interview.mp3

# Add participant metadata (optional, can be done before or after)
python main.py interview add-participant --id p001 --vertical "fashion" --gmv "10k-30k"
```

### Zoom Transcription Setup

To use Zoom's native transcription (recommended for Zoom calls):

1. **Enable Cloud Recording**: Account Settings → Recording → Enable Cloud Recording
2. **Enable Transcription**: Advanced cloud recording settings → Check "Create audio transcript"
3. **Record to Cloud**: During meeting, click Record → Record to Cloud
4. **Download VTT**: After meeting, check email for transcript link or go to Zoom Portal → Recordings → Download transcript (VTT)

**Note:** Requires Zoom Pro/Business/Education/Enterprise license. Processing takes ~2x meeting length.

### Transcript JSON Format

```json
{
  "audio_file": "interview_20250109_p001.mp3",
  "transcribed_at": "2025-01-09T14:30:00Z",
  "model": "medium",
  "duration_seconds": 1847,
  "language": "en",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Thanks for taking the time to chat today."
    },
    {
      "start": 5.5,
      "end": 12.8,
      "text": "So tell me, what's the biggest challenge you face running your Shopify store?"
    },
    {
      "start": 13.1,
      "end": 28.4,
      "text": "Honestly, inventory management is killing me. I have products on Amazon and Etsy too, and keeping stock levels synced is a nightmare."
    }
  ],
  "full_text": "Thanks for taking the time to chat today. So tell me..."
}
```

### Interview Classification Prompt

The LLM uses a specialized prompt to extract structured insights from transcripts:

```python
INTERVIEW_CLASSIFICATION_PROMPT = """
Analyze this interview transcript with a Shopify merchant. Extract all pain points,
insights, and business signals.

<transcript>
{transcript_text}
</transcript>

For EACH distinct pain point or insight mentioned, extract:
{{
  "pain_points": [
    {{
      "category": "<category from: admin, analytics, marketing, loyalty, payments,
                   fulfillment, inventory, customer_support, design, seo,
                   integrations, performance, pricing, other>",
      "summary": "<1-2 sentence description of the pain point>",
      "verbatim_quote": "<exact quote from transcript>",
      "frustration_level": <1-5>,
      "urgency_score": <1-5>,
      "frequency": "<daily/weekly/monthly/occasionally>",
      "business_impact": "<description of how this affects their business>",
      "current_workaround": "<what they're doing to cope, or null>",
      "competitor_mentions": ["<apps or tools mentioned>"],
      "timestamp_approx": "<approximate timestamp in transcript>"
    }}
  ],
  "wtp_signals": [
    {{
      "context": "<what solution they'd pay for>",
      "amount_mentioned": "<dollar amount if stated, or null>",
      "verbatim_quote": "<exact quote>",
      "confidence": "<high/medium/low>"
    }}
  ],
  "participant_profile": {{
    "store_vertical": "<their product category>",
    "app_count_mentioned": <number if mentioned>,
    "monthly_app_spend": "<if mentioned>",
    "team_size": "<if mentioned>",
    "key_quotes": ["<notable quotes for reference>"]
  }}
}}
"""
```

### File Structure for Interviews

```
data/
└── interviews/
    ├── recordings/           # Audio files from interviews
    │   ├── interview_20250109_p001.mp3
    │   ├── interview_20250110_p002.wav
    │   └── ...
    ├── transcripts/          # JSON transcripts from Whisper
    │   ├── interview_20250109_p001.json
    │   ├── interview_20250110_p002.json
    │   └── ...
    └── insights/             # Extracted insights (also in SQLite)
        └── ...
```

### Quick Reference: Full Interview Workflow

**Option A: Zoom with Native Transcription (Easiest)**
```bash
# 1. Record interview in Zoom with cloud recording enabled
# 2. Wait for transcript email from Zoom (~2x meeting length)
# 3. Download VTT file from Zoom portal

# 4. Import VTT transcript
python main.py interview import-vtt ~/Downloads/interview_transcript.vtt --participant p001

# 5. Classify insights from transcript
python main.py interview classify-transcript ./data/interviews/transcripts/interview_20250109_p001.json

# 6. Add participant metadata
python main.py interview add-participant --id p001 --vertical "home-goods" --gmv "5k-10k" --beta-tester

# 7. View combined insights
python main.py interview opportunities --storage sqlite
```

**Option B: Any Audio File with Whisper**
```bash
# 1. After interview, save recording
mv ~/Downloads/zoom_recording.mp3 ./data/interviews/recordings/interview_20250109_p001.mp3

# 2. Transcribe with Whisper
python main.py interview transcribe ./data/interviews/recordings/interview_20250109_p001.mp3 --model medium

# 3. Review transcript (optional)
cat ./data/interviews/transcripts/interview_20250109_p001.json | jq '.full_text'

# 4. Extract and classify insights
python main.py interview classify-transcript ./data/interviews/transcripts/interview_20250109_p001.json

# 5. Add participant metadata
python main.py interview add-participant --id p001 --vertical "home-goods" --gmv "5k-10k" --beta-tester

# 6. View combined insights
python main.py interview opportunities --storage sqlite

# 7. See correlation with scraped data
python main.py interview correlate --storage sqlite
```

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
