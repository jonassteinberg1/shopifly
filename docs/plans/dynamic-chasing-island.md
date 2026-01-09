# PRD: Approach 1 - Web Scraping + LLM Analysis

## Overview

**Objective:** Build a complete, tested system that scrapes Shopify merchant pain points from 4 sources, classifies them using LLM, and stores results for analysis.

**Scope:** Scraping + Classification pipeline only. Clustering and scoring deferred to later phase.

**Build approach:** Enhance existing codebase (scrapers, classifier, storage already written)

---

## Current State (Already Implemented)

| Component | Status | Files |
|-----------|--------|-------|
| Reddit Scraper (API) | ✅ Built (needs API key) | `scrapers/reddit.py` |
| App Store Scraper | ✅ Built | `scrapers/appstore.py` |
| Twitter Scraper | ✅ Built | `scrapers/twitter.py` |
| Community Scraper | ✅ Built | `scrapers/community.py` |
| LLM Classifier | ✅ Built | `analysis/classifier.py` |
| Airtable Storage | ✅ Built | `storage/airtable.py` |
| CLI | ✅ Built | `main.py` |
| Unit Tests | ✅ Built | `tests/unit/` |
| Integration Tests | ✅ Built | `tests/integration/` |
| Dockerfile | ✅ Built | `Dockerfile` |

---

## What Needs to Be Built

### 1. Reddit JSON Scraper (No API Key Required)

**Why:** Reddit now requires API application approval. The `.json` suffix on Reddit URLs returns structured data without authentication, enabling scraping without waiting for approval.

**How It Works:**
```
https://www.reddit.com/r/shopify.json        → Returns 25 posts (listing)
https://www.reddit.com/r/shopify.json?after=t3_xxx  → Next page (pagination)
https://www.reddit.com/r/shopify/comments/abc123.json  → Full thread with comments
```

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    REDDIT JSON SCRAPER PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PHASE 1: Subreddit Discovery                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ For each subreddit in [shopify, ecommerce, dropship, ...]       │   │
│  │   → Fetch /r/{subreddit}.json?limit=100                         │   │
│  │   → Paginate using "after" cursor until limit reached           │   │
│  │   → Extract: id, title, selftext, score, num_comments, url      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  PHASE 2: Keyword Pre-Filter                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Filter posts matching pain keywords:                            │   │
│  │   "frustrated", "problem", "issue", "help", "need", etc.        │   │
│  │ Keep posts mentioning "shopify" in title or body                │   │
│  │ Output: Candidate posts for LLM analysis                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  PHASE 3: LLM Relevance Scoring                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ For each candidate post, ask LLM:                               │   │
│  │   "Is this a genuine merchant pain point? Score 1-10"           │   │
│  │   "What category? (inventory, analytics, shipping, etc.)"       │   │
│  │ Filter: Keep posts with relevance_score >= 6                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  PHASE 4: Thread Deep Dive                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ For high-relevance posts (score >= 7):                          │   │
│  │   → Fetch /r/{sub}/comments/{id}.json                           │   │
│  │   → Extract top 20 comments                                     │   │
│  │   → LLM analyze comments for:                                   │   │
│  │       - Additional pain points                                  │   │
│  │       - Workarounds mentioned                                   │   │
│  │       - Willingness to pay signals                              │   │
│  │       - App recommendations (competitors)                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  PHASE 5: Priority Reranking                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Rerank all insights by priority score:                          │   │
│  │                                                                  │   │
│  │   priority = (relevance × 0.3) +                                │   │
│  │              (frustration_level × 0.25) +                       │   │
│  │              (engagement_score × 0.2) +                         │   │
│  │              (wtp_signal × 0.15) +                              │   │
│  │              (recency × 0.1)                                    │   │
│  │                                                                  │
│  │   engagement_score = log(score + 1) + log(num_comments + 1)     │   │
│  │   recency = 1.0 if < 7 days, 0.7 if < 30 days, 0.4 otherwise   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  OUTPUT: Ranked list of pain points with full context                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Implementation: `scrapers/reddit_json.py`**

```python
class RedditJsonScraper(BaseScraper):
    """Reddit scraper using public JSON endpoints (no API key required)."""

    source = DataSource.REDDIT
    BASE_URL = "https://www.reddit.com"

    # Target subreddits
    SUBREDDITS = ["shopify", "ecommerce", "dropship", "smallbusiness", "Entrepreneur"]

    # Pagination
    POSTS_PER_PAGE = 100  # Reddit max
    MAX_PAGES_PER_SUBREDDIT = 4  # Up to 400 posts per subreddit

    async def scrape(self, limit: int = 100) -> AsyncIterator[RawDataPoint]:
        """
        Multi-phase scraping with LLM analysis and reranking.

        1. Fetch posts from all subreddits (paginated)
        2. Keyword pre-filter
        3. LLM relevance scoring
        4. Deep dive into high-value threads
        5. Rerank by priority
        """

    async def _fetch_subreddit_posts(self, subreddit: str, limit: int) -> list[dict]:
        """Fetch posts with pagination using 'after' cursor."""

    async def _fetch_thread_comments(self, subreddit: str, post_id: str) -> list[dict]:
        """Fetch comments from a specific thread."""

    def _keyword_filter(self, posts: list[dict]) -> list[dict]:
        """Pre-filter posts by pain point keywords."""

    async def _llm_score_relevance(self, post: dict) -> dict:
        """Use LLM to score post relevance (1-10) and categorize."""

    async def _llm_analyze_comments(self, comments: list[dict]) -> dict:
        """Extract insights from thread comments."""

    def _calculate_priority_score(self, insight: dict) -> float:
        """Calculate priority score for reranking."""
```

**JSON Response Structure (for reference):**

```python
# Subreddit listing: /r/shopify.json
{
    "kind": "Listing",
    "data": {
        "after": "t3_abc123",  # Pagination cursor
        "before": null,
        "dist": 25,            # Number of posts
        "children": [
            {
                "kind": "t3",  # t3 = post
                "data": {
                    "id": "abc123",
                    "name": "t3_abc123",
                    "title": "Frustrated with inventory sync",
                    "selftext": "Post body content...",
                    "score": 45,
                    "num_comments": 23,
                    "created_utc": 1704567890,
                    "author": "merchant_user",
                    "permalink": "/r/shopify/comments/abc123/frustrated_with_inventory/",
                    "subreddit": "shopify"
                }
            }
        ]
    }
}

# Thread comments: /r/shopify/comments/abc123.json
[
    { /* Post data */ },
    {
        "kind": "Listing",
        "data": {
            "children": [
                {
                    "kind": "t1",  # t1 = comment
                    "data": {
                        "id": "xyz789",
                        "body": "I had the same issue...",
                        "score": 12,
                        "author": "helpful_user"
                    }
                }
            ]
        }
    }
]
```

**LLM Prompts:**

```python
# Phase 3: Relevance Scoring
RELEVANCE_PROMPT = """
Analyze this Reddit post from r/{subreddit}:

Title: {title}
Content: {selftext}

Score this post 1-10 on how useful it is for understanding Shopify merchant pain points:
- 1-3: Not relevant (memes, promotions, unrelated)
- 4-6: Somewhat relevant (general discussion, minor issues)
- 7-10: Highly relevant (clear pain point, frustration, seeking solutions)

Also categorize the primary pain point (if any):
Categories: analytics, inventory, shipping, payments, marketing, customer_support,
           integrations, pricing, performance, design, admin, seo, loyalty, other

Return JSON:
{
    "relevance_score": <1-10>,
    "category": "<category>",
    "pain_summary": "<one sentence summary>",
    "wtp_signal": <true if mentions budget/paying/pricing>,
    "frustration_level": <1-5>
}
"""

# Phase 4: Comment Analysis
COMMENT_ANALYSIS_PROMPT = """
Analyze these comments from a Shopify-related Reddit thread:

Original Post: {title}

Comments:
{comments}

Extract:
1. Additional pain points mentioned
2. Workarounds or solutions people are using
3. Apps/tools mentioned (potential competitors)
4. Willingness to pay signals
5. Most insightful quotes

Return JSON:
{
    "additional_pain_points": ["..."],
    "workarounds": ["..."],
    "competitor_apps": ["..."],
    "wtp_quotes": ["..."],
    "key_quotes": ["..."]
}
"""
```

**Rate Limiting & Politeness:**
- 2 second delay between requests (Reddit is sensitive)
- Respect 429 responses with exponential backoff
- User-Agent: "Shopifly/1.0 (market research; contact@example.com)"
- Max 1000 posts per run to avoid abuse

**Priority Reranking Algorithm:**

```python
def calculate_priority(insight: dict) -> float:
    """
    Calculate priority score for ranking insights.

    Weights:
    - relevance (LLM score): 30%
    - frustration level: 25%
    - engagement (upvotes + comments): 20%
    - willingness to pay signal: 15%
    - recency: 10%
    """
    relevance = insight.get("relevance_score", 5) / 10  # Normalize to 0-1
    frustration = insight.get("frustration_level", 3) / 5  # Normalize to 0-1

    # Engagement: logarithmic scale
    score = insight.get("score", 0)
    comments = insight.get("num_comments", 0)
    engagement = (math.log(score + 1) + math.log(comments + 1)) / 10  # Normalize
    engagement = min(engagement, 1.0)  # Cap at 1.0

    # WTP signal: boolean
    wtp = 1.0 if insight.get("wtp_signal") else 0.0

    # Recency: based on created_utc
    age_days = (time.time() - insight.get("created_utc", 0)) / 86400
    if age_days < 7:
        recency = 1.0
    elif age_days < 30:
        recency = 0.7
    elif age_days < 90:
        recency = 0.4
    else:
        recency = 0.2

    # Weighted sum
    priority = (
        relevance * 0.30 +
        frustration * 0.25 +
        engagement * 0.20 +
        wtp * 0.15 +
        recency * 0.10
    )

    return round(priority * 100, 2)  # Return as 0-100 score
```

**CLI Integration:**

```bash
# Use JSON scraper (no API key needed)
python main.py scrape --source reddit-json --limit 100

# Use API scraper (requires credentials)
python main.py scrape --source reddit --limit 100
```

**Files to Create/Modify:**
- `scrapers/reddit_json.py` - New JSON-based scraper
- `scrapers/__init__.py` - Export new scraper
- `analysis/reranker.py` - Priority reranking logic
- `main.py` - Add `reddit-json` source option
- `tests/unit/test_reddit_json.py` - Unit tests
- `tests/e2e/test_reddit_json_pipeline.py` - E2E tests

---

### 2. SQLite Storage Backend (for testing)

**Why:** Enable e2e tests without requiring Airtable credentials. Also useful for local development.

**Implementation:**
- Create `storage/sqlite.py` with same interface as `storage/airtable.py`
- Create abstract `StorageBackend` base class
- Make both Airtable and SQLite implement this interface
- Add `--storage` flag to CLI (`airtable` or `sqlite`)
- SQLite file location configurable via env var (default: `./data/shopify.db`)

**Schema (SQLite):**
```sql
-- Raw scraped data
CREATE TABLE raw_sources (
    id INTEGER PRIMARY KEY,
    source_id TEXT UNIQUE,
    source TEXT,
    url TEXT,
    title TEXT,
    content TEXT,
    author TEXT,
    created_at TIMESTAMP,
    scraped_at TIMESTAMP,
    metadata JSON,
    processed BOOLEAN DEFAULT FALSE
);

-- Classified insights
CREATE TABLE insights (
    id INTEGER PRIMARY KEY,
    source_id TEXT UNIQUE,
    source_url TEXT,
    problem_statement TEXT,
    category TEXT,
    secondary_categories TEXT,
    frustration_level INTEGER,
    clarity_score INTEGER,
    willingness_to_pay BOOLEAN,
    wtp_quotes TEXT,
    current_workaround TEXT,
    keywords TEXT,
    original_title TEXT,
    content_snippet TEXT,
    raw_source_id INTEGER REFERENCES raw_sources(id)
);
```

### 2. End-to-End Tests (Real APIs, Small Limits)

**Strategy:** Hit real APIs with minimal data to prove the full pipeline works.

**Test Configuration:**
```python
E2E_CONFIG = {
    "reddit_limit": 3,        # 3 posts
    "appstore_limit": 3,      # 3 reviews
    "twitter_limit": 3,       # 3 tweets
    "community_limit": 3,     # 3 topics
    "classify_limit": 5,      # Classify 5 items total
}
```

**E2E Test Cases:**

| Test | Description | Verifies |
|------|-------------|----------|
| `test_e2e_reddit_pipeline` | Scrape 3 Reddit posts → Store in SQLite → Classify → Verify insights | Reddit + LLM + Storage |
| `test_e2e_appstore_pipeline` | Scrape 3 App Store reviews → Store → Classify | App Store scraper works |
| `test_e2e_twitter_pipeline` | Scrape 3 tweets → Store → Classify | Twitter API integration |
| `test_e2e_community_pipeline` | Scrape 3 forum posts → Store → Classify | Community scraper works |
| `test_e2e_full_pipeline` | Run all scrapers → Classify all → Verify counts | Complete system works |
| `test_e2e_cli_commands` | Test CLI: scrape, classify, stats | CLI interface works |

**Requirements:**
- Tests require real API credentials (skip if not configured)
- Use `pytest.mark.e2e` marker to separate from unit/integration tests
- Create `tests/e2e/` directory
- Tests use SQLite storage (not Airtable)

### 3. Storage Backend Abstraction

**Files to modify:**
- Create `storage/base.py` - Abstract base class
- Modify `storage/airtable.py` - Implement base class
- Create `storage/sqlite.py` - New SQLite implementation
- Modify `main.py` - Add `--storage` flag

**Interface:**
```python
class StorageBackend(ABC):
    @abstractmethod
    def save_raw_datapoint(self, datapoint: RawDataPoint) -> str: ...

    @abstractmethod
    def get_unprocessed_raw_data(self, limit: int) -> list[dict]: ...

    @abstractmethod
    def mark_as_processed(self, source_id: str) -> None: ...

    @abstractmethod
    def save_insight(self, insight: ClassifiedInsight) -> str: ...

    @abstractmethod
    def get_stats(self) -> dict: ...
```

### 4. CLI Enhancements

**New flags:**
```bash
# Storage backend selection
python main.py scrape --storage sqlite --limit 10
python main.py classify --storage sqlite

# E2E test mode (small limits, SQLite)
python main.py scrape --e2e  # Equivalent to --storage sqlite --limit 3
```

---

## File Structure (Final)

```
/root/shopify/
├── Dockerfile
├── pyproject.toml
├── pytest.ini
├── config/
│   ├── __init__.py
│   └── settings.py
├── scrapers/
│   ├── __init__.py
│   ├── base.py
│   ├── reddit.py           # Original API-based scraper
│   ├── reddit_json.py      # NEW: JSON endpoint scraper (no API key)
│   ├── appstore.py
│   ├── twitter.py
│   └── community.py
├── analysis/
│   ├── __init__.py
│   ├── classifier.py
│   └── reranker.py         # NEW: Priority reranking algorithm
├── storage/
│   ├── __init__.py
│   ├── base.py          # Abstract base class
│   ├── airtable.py      # Airtable backend
│   └── sqlite.py        # SQLite backend
├── main.py              # MODIFY: Add reddit-json source
├── data/                # SQLite database location
│   └── .gitkeep
└── tests/
    ├── conftest.py
    ├── unit/
    │   └── test_reddit_json.py    # NEW: JSON scraper tests
    ├── integration/
    └── e2e/
        ├── __init__.py
        ├── conftest.py
        ├── test_full_pipeline.py
        └── test_reddit_json_pipeline.py  # NEW: JSON scraper E2E
```

---

## Implementation Steps

### Phase 1: Reddit JSON Scraper (NEW - PRIORITY)
1. Create `scrapers/reddit_json.py`:
   - `RedditJsonScraper` class extending `BaseScraper`
   - Pagination logic using `after` cursor
   - Keyword pre-filtering
   - LLM relevance scoring integration
   - Thread comment fetching
2. Create `analysis/reranker.py`:
   - `calculate_priority()` function
   - Configurable weights
3. Update `scrapers/__init__.py` to export `RedditJsonScraper`
4. Update `main.py`:
   - Add `reddit-json` as source option
   - Wire up new scraper
5. Create `tests/unit/test_reddit_json.py`:
   - Test pagination logic
   - Test keyword filtering
   - Test priority calculation
   - Mock HTTP responses
6. Create `tests/e2e/test_reddit_json_pipeline.py`:
   - Test full pipeline with real Reddit data

### Phase 2: Storage Abstraction (DONE)
1. ✅ Create `storage/base.py` with `StorageBackend` ABC
2. ✅ Refactor `storage/airtable.py` to inherit from base
3. ✅ Create `storage/sqlite.py` implementing same interface
4. ✅ Add unit tests for SQLite storage

### Phase 3: CLI Updates (DONE)
1. ✅ Add `--storage` option to CLI commands
2. ✅ Add storage factory function to select backend
3. ✅ Update `main.py` commands to use selected backend
4. ✅ Test CLI with both backends

### Phase 4: E2E Test Infrastructure (DONE)
1. ✅ Create `tests/e2e/` directory structure
2. ✅ Create `tests/e2e/conftest.py`
3. ✅ Add `pytest.mark.e2e` marker to `pytest.ini`

### Phase 5: E2E Tests (DONE)
1. ✅ `test_e2e_appstore_pipeline`
2. ✅ `test_e2e_community_pipeline`
3. ✅ `test_e2e_classification_pipeline`
4. ✅ `test_e2e_cli_commands`
5. ✅ `test_e2e_storage_roundtrip`

### Phase 6: Documentation & Verification
1. Update README with reddit-json usage
2. Verify Docker build with new scraper
3. Run full test suite

---

## Verification

### Running All Tests

```bash
# Unit + Integration tests (no API keys needed)
pytest tests/unit tests/integration -v

# E2E tests (requires API keys in .env)
pytest tests/e2e -v --e2e

# Full test suite
pytest tests/ -v
```

### Manual Verification

```bash
# 1. Test Reddit JSON scraper (NO API KEY NEEDED)
python main.py scrape --storage sqlite --source reddit-json --limit 50
python main.py stats --storage sqlite

# 2. Test classification
python main.py classify --storage sqlite --limit 10

# 3. Verify data and rankings
sqlite3 data/shopify.db "SELECT COUNT(*) FROM raw_sources"
sqlite3 data/shopify.db "SELECT COUNT(*) FROM insights"
sqlite3 data/shopify.db "SELECT category, COUNT(*) FROM insights GROUP BY category"

# 4. View ranked opportunities
python main.py opportunities --storage sqlite --top 10

# 5. Test with Docker
docker build -t shopify-gatherer .
docker run --rm -v $(pwd)/.env:/app/.env shopify-gatherer scrape --storage sqlite --source reddit-json --limit 20
```

### Success Criteria

| Criteria | Metric |
|----------|--------|
| Unit tests pass | 150+ tests green |
| E2E tests pass | 8+ e2e tests green |
| **Reddit JSON scraper works** | Fetches posts without API key |
| **Pagination works** | Fetches 100+ posts per subreddit |
| **LLM relevance scoring** | Filters irrelevant posts |
| **Comment analysis** | Extracts insights from threads |
| **Priority reranking** | Ranks insights by importance |
| App Store scraper works | Fetches real reviews |
| Community scraper works | Fetches real topics |
| LLM classifier works | Produces valid insights |
| SQLite storage works | Data persists correctly |
| CLI works | All commands functional |
| Docker works | Image builds and runs |

---

## Environment Variables Required

```bash
# Required for LLM classification
ANTHROPIC_API_KEY=xxx

# Optional (only for API-based Reddit scraper)
REDDIT_CLIENT_ID=xxx
REDDIT_CLIENT_SECRET=xxx

# Optional (for Twitter scraper)
TWITTER_BEARER_TOKEN=xxx

# Optional (for Airtable storage)
AIRTABLE_API_KEY=xxx
AIRTABLE_BASE_ID=xxx
```

**Note:** The new Reddit JSON scraper (`--source reddit-json`) requires NO API keys - only the Anthropic key for LLM analysis.

---

## Out of Scope (Deferred)

- Clustering/deduplication of similar problems
- Profitability scoring
- Scheduled/automated runs
- Dashboard/visualization
- Competition analysis

---

## LLM Classification Pipeline (ENHANCED)

### Overview

The classification pipeline transforms raw scraped content into structured, aggregatable insights. The system uses a multi-stage approach to optimize for both cost and quality.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LLM CLASSIFICATION PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STAGE 1: Pre-filtering (No LLM - Keyword/Heuristic)                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Input: Raw scraped content                                              │ │
│  │ Filter: Must mention "shopify" OR contain pain keywords                 │ │
│  │ Filter: Minimum content length (50 chars)                               │ │
│  │ Filter: Not a duplicate (by source_id)                                  │ │
│  │ Output: Candidate content for classification                            │ │
│  │ Cost: $0 (no LLM calls)                                                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                               │
│                              ▼                                               │
│  STAGE 2: Relevance Screening (Haiku - Cheap & Fast)                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Model: claude-3-haiku                                                   │ │
│  │ Input: Title + first 500 chars of content                               │ │
│  │ Output: { relevant: bool, content_type: string, confidence: float }     │ │
│  │ Filter: Keep only relevant=true AND confidence > 0.6                    │ │
│  │ Cost: ~$0.00025 per item (very cheap)                                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                               │
│                              ▼                                               │
│  STAGE 3: Deep Classification (Sonnet - Quality)                            │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Model: claude-3-5-sonnet                                                │ │
│  │ Input: Full content (truncated to 2000 chars)                           │ │
│  │ Output: ClassifiedInsight with all fields                               │ │
│  │ Batching: Process individually (not batched - each item is independent) │ │
│  │ Concurrency: 5 parallel requests                                        │ │
│  │ Cost: ~$0.003 per item                                                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              │                                               │
│                              ▼                                               │
│  STAGE 4: Storage & Aggregation                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Store: ClassifiedInsight → insights table                               │ │
│  │ Index: By category, content_type, frustration_level                     │ │
│  │ Aggregate: Category counts, avg frustration, WTP rate                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Models

#### Content Types (NEW)

```python
class ContentType(str, Enum):
    """Type of content being analyzed."""

    COMPLAINT = "complaint"           # User expressing frustration with existing feature
    FEATURE_REQUEST = "feature_request"  # User requesting new functionality
    QUESTION = "question"             # User asking how to do something
    COMPARISON = "comparison"         # User comparing Shopify to alternatives
    REVIEW = "review"                 # General review/feedback
    WORKAROUND = "workaround"         # User sharing a solution/hack
    OTHER = "other"                   # Doesn't fit other categories
```

#### Enhanced ClassifiedInsight

```python
class ClassifiedInsight(BaseModel):
    """A classified and analyzed insight from raw data."""

    # Original data reference
    source_id: str
    source_url: str

    # Content classification (NEW)
    content_type: ContentType          # What kind of content is this?

    # Problem/Feature categorization
    category: ProblemCategory          # Primary category (14 options)
    secondary_categories: list[ProblemCategory]

    # Extracted insights
    problem_statement: str             # Concise 1-2 sentence summary

    # Scoring (1-5 scale)
    frustration_level: int             # 1=mild, 5=severe
    clarity_score: int                 # How clearly described
    urgency_score: int                 # How urgently they need a solution (NEW)

    # Business signals
    willingness_to_pay: bool
    wtp_quotes: list[str]
    price_sensitivity: str | None      # "low", "medium", "high" (NEW)

    # Solutions context
    current_workaround: str | None
    competitor_mentions: list[str]     # Apps/tools mentioned (NEW)

    # Clustering support
    keywords: list[str]                # 3-5 key terms

    # Metadata
    original_title: str | None
    content_snippet: str               # First 500 chars
    classified_at: datetime            # When classified (NEW)
    model_used: str                    # Which model classified this (NEW)
```

### Prompts

#### Stage 2: Relevance Screening Prompt (Haiku)

```python
RELEVANCE_SCREENING_PROMPT = """Analyze this content and determine if it's relevant for understanding Shopify merchant pain points.

<content>
Title: {title}
Content: {content_preview}
</content>

Respond with JSON only:
{{
    "relevant": true/false,
    "content_type": "complaint" | "feature_request" | "question" | "comparison" | "review" | "workaround" | "other",
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}

Rules:
- relevant=true if: expresses frustration, requests features, asks about limitations, compares to competitors
- relevant=false if: promotional, spam, unrelated to Shopify operations, just saying thanks
- confidence: how sure you are (0.0-1.0)
"""
```

#### Stage 3: Deep Classification Prompt (Sonnet)

```python
DEEP_CLASSIFICATION_PROMPT = """Analyze this Shopify merchant feedback and extract structured insights.

<content>
Title: {title}
Source: {source}
Content Type: {content_type}
Full Content: {content}
</content>

Extract the following in JSON format:

{{
    "problem_statement": "1-2 sentence description of the core issue or need",

    "category": "primary category from: admin, analytics, marketing, loyalty, payments, fulfillment, inventory, customer_support, design, seo, integrations, performance, pricing, other",

    "secondary_categories": ["other relevant categories, can be empty"],

    "frustration_level": 1-5,  // 1=mild annoyance, 5=severe frustration/anger
    "clarity_score": 1-5,       // how clearly the problem is described
    "urgency_score": 1-5,       // 1=nice-to-have, 5=blocking their business

    "willingness_to_pay": true/false,
    "wtp_quotes": ["exact quotes suggesting willingness to pay"],
    "price_sensitivity": "low" | "medium" | "high" | null,

    "current_workaround": "workaround mentioned, or null",
    "competitor_mentions": ["apps, tools, or platforms mentioned"],

    "keywords": ["3-5 key terms for clustering"]
}}

Important:
- Be concise in problem_statement
- Only include actual quotes in wtp_quotes
- competitor_mentions should include specific app names, not generic terms
- keywords should be specific enough to cluster similar issues
"""
```

### Batching Strategy

**Why NOT batch multiple items in one prompt:**
- Each item needs individual attention for accurate classification
- Mixing items risks cross-contamination of analysis
- Error in one item would affect others
- Harder to retry failed items

**Efficient processing approach:**
```python
async def classify_batch(datapoints: list[RawDataPoint], concurrency: int = 5):
    """Process items with controlled concurrency, not as a single batch."""

    semaphore = asyncio.Semaphore(concurrency)

    async def classify_one(dp):
        async with semaphore:
            # Stage 2: Screen with Haiku (cheap)
            screening = await screen_relevance(dp)
            if not screening.relevant or screening.confidence < 0.6:
                return None

            # Stage 3: Deep classify with Sonnet (quality)
            return await deep_classify(dp, screening.content_type)

    # Process all items concurrently (up to 5 at a time)
    tasks = [classify_one(dp) for dp in datapoints]
    results = await asyncio.gather(*tasks)

    return [r for r in results if r is not None]
```

### Cost Estimation

| Stage | Model | Cost/Item | 1000 Items | Notes |
|-------|-------|-----------|------------|-------|
| Pre-filter | None | $0 | $0 | Keyword/heuristic only |
| Relevance Screen | Haiku | $0.00025 | $0.25 | ~50% filtered out |
| Deep Classify | Sonnet | $0.003 | $1.50 | Only ~500 items reach this |
| **Total** | - | - | **~$1.75** | For 1000 raw items |

### Aggregation Schema

For visualization and reporting, insights are aggregated into summary tables:

```sql
-- Category summary (for bar charts)
CREATE VIEW category_summary AS
SELECT
    category,
    content_type,
    COUNT(*) as count,
    AVG(frustration_level) as avg_frustration,
    AVG(urgency_score) as avg_urgency,
    SUM(CASE WHEN willingness_to_pay THEN 1 ELSE 0 END) as wtp_count,
    COUNT(DISTINCT source_id) as unique_sources
FROM insights
GROUP BY category, content_type;

-- Time series (for trend charts)
CREATE VIEW insights_by_week AS
SELECT
    strftime('%Y-%W', classified_at) as week,
    category,
    COUNT(*) as count,
    AVG(frustration_level) as avg_frustration
FROM insights
GROUP BY week, category;

-- Top keywords (for word clouds)
CREATE VIEW keyword_frequency AS
SELECT
    keyword,
    category,
    COUNT(*) as frequency
FROM insights, json_each(insights.keywords) as keyword
GROUP BY keyword, category
ORDER BY frequency DESC;

-- Competitor mentions (for competitive analysis)
CREATE VIEW competitor_summary AS
SELECT
    competitor,
    COUNT(*) as mention_count,
    AVG(frustration_level) as context_frustration
FROM insights, json_each(insights.competitor_mentions) as competitor
WHERE competitor != ''
GROUP BY competitor
ORDER BY mention_count DESC;
```

### Implementation Files

**Files to Create:**
- `analysis/content_types.py` - ContentType enum and related logic
- `analysis/relevance_screener.py` - Stage 2 Haiku-based screening
- `analysis/aggregator.py` - Aggregation queries and views

**Files to Modify:**
- `analysis/classifier.py` - Add content_type, urgency_score, competitor_mentions fields
- `storage/sqlite.py` - Add aggregation views, update insights schema
- `main.py` - Add `--model` flag to choose classification model

### CLI Commands

```bash
# Classify with default settings (Haiku screen → Sonnet classify)
python main.py classify --storage sqlite --limit 100

# Skip screening, use Sonnet for everything (more expensive, slightly better)
python main.py classify --storage sqlite --limit 100 --skip-screening

# Use Haiku for everything (cheapest, lower quality)
python main.py classify --storage sqlite --limit 100 --model haiku

# View aggregated stats
python main.py stats --storage sqlite --aggregate

# Export aggregations for visualization
python main.py export --format csv --output reports/category_summary.csv
```

### Success Criteria for Classification

| Metric | Target |
|--------|--------|
| Pre-filter pass rate | 30-50% (filters noise) |
| Relevance screen pass rate | 60-80% of pre-filtered |
| Classification accuracy | 90%+ category match on sample |
| Processing speed | 100 items/minute with concurrency=5 |
| Cost per 1000 items | < $2.00 |
| Content type distribution | Complaints > 40%, Feature requests > 20% |
