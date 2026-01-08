# Shopifly

[![Tests](https://github.com/jonassteinberg1/shopifly/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/jonassteinberg1/shopifly/actions/workflows/tests.yml)

Shopify merchant pain point analyzer - scrape customer feedback, classify problems with AI, and identify app opportunities.

## Overview

Shopifly helps identify genuine Shopify app opportunities by:

1. **Scraping** customer feedback from 4 major sources (Reddit, App Store, Twitter, Community forums)
2. **Classifying** merchant problems using Claude AI into 14 categories
3. **Storing** findings in SQLite (local) or Airtable (production)
4. **Ranking** opportunities by frequency, frustration level, and willingness-to-pay signals

## Features

- **5 Data Scrapers**: Reddit (API + RSS fallback), Shopify App Store reviews, Twitter/X, Shopify Community forums
- **LLM Classification**: Anthropic Claude-powered analysis with frustration scoring, WTP detection, and keyword extraction
- **Dual Storage**: Airtable (production) or SQLite (local/testing)
- **CLI Interface**: Rich terminal UI with progress indicators
- **Docker Support**: Full containerization with Chrome/Selenium for JavaScript-rendered pages
- **160+ Tests**: Comprehensive unit, integration, and E2E test coverage

## Quick Start

### Local Installation

```bash
# Clone
git clone https://github.com/jonassteinberg1/shopifly.git
cd shopifly

# Install (requires Python 3.11+)
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
python main.py --help
```

### Docker (Recommended)

```bash
# Build
docker build -t shopifly .

# Run commands
docker run --rm -v $(pwd)/.env:/app/.env shopifly scrape --storage sqlite --limit 10
docker run --rm -v $(pwd)/.env:/app/.env shopifly classify --storage sqlite
docker run --rm -v $(pwd)/.env:/app/.env shopifly stats --storage sqlite

# Or use docker-compose for development
docker-compose run dev  # Interactive shell
docker-compose run test # Run tests
```

## CLI Commands

### Scrape Data

```bash
# Scrape from all sources
python main.py scrape --limit 50

# Scrape from specific source
python main.py scrape --source reddit --limit 20
python main.py scrape --source appstore --limit 20
python main.py scrape --source twitter --limit 20
python main.py scrape --source community --limit 20

# Use SQLite instead of Airtable
python main.py scrape --storage sqlite --limit 10
```

### Classify with AI

```bash
# Classify unprocessed data
python main.py classify --limit 20

# Increase concurrency for faster processing
python main.py classify --concurrency 10 --limit 100
```

### View Results

```bash
# View statistics
python main.py stats

# View top opportunities
python main.py opportunities --top 10

# Health check all services
python main.py health
```

## Data Sources

### Reddit Scraper

Two implementations available:

**1. API-based (`reddit.py`)** - Requires Reddit API credentials
- Uses PRAW library
- Searches r/shopify, r/ecommerce, r/dropship, r/smallbusiness, r/Entrepreneur
- Collects posts and comments with engagement metrics

**2. RSS-based (`reddit_selenium.py`)** - No API required
- Uses RSS feeds via httpx (Selenium fallback for blocked requests)
- Supports multiple sort types: hot, new, top (day/week/month/year/all), rising
- Can fetch 100+ unique posts by combining sort endpoints
- Includes comment scraping via post-specific RSS feeds

```python
# Direct usage of RSS scraper
from scrapers.reddit_selenium import scrape_reddit_posts

posts = scrape_reddit_posts(
    limit=100,
    sort_types=["hot", "new", "top_week", "top_month"],
    include_comments=True,
    request_delay=2.0
)
```

### App Store Scraper

- Scrapes Shopify App Store reviews using Selenium (JavaScript-rendered)
- Targets 10 popular Shopify apps (Flow, Inbox, Search & Discovery, etc.)
- Prioritizes 1-3 star reviews for pain point discovery
- Extracts: review text, rating, date, app metadata

### Twitter Scraper

- Uses Twitter/X API v2 via Tweepy
- 12 targeted search queries for pain points
- Collects: tweet text, engagement metrics, author info

### Community Forum Scraper

- Scrapes community.shopify.com forums via httpx/BeautifulSoup
- Targets 6 high-signal boards (Discussion, Technical Q&A, Apps, etc.)
- Collects: thread title, content, replies, views

## Classification

The Claude-powered classifier analyzes each data point and extracts:

| Field | Description |
|-------|-------------|
| `problem_statement` | Concise 1-2 sentence problem description |
| `category` | Primary category (see below) |
| `secondary_categories` | Related categories |
| `frustration_level` | 1-5 scale (1=mild, 5=severe) |
| `clarity_score` | 1-5 scale (how clear the problem is) |
| `willingness_to_pay` | Boolean + supporting quotes |
| `current_workaround` | Any mentioned workarounds |
| `keywords` | 3-5 terms for clustering |

### Problem Categories

| Category | Description |
|----------|-------------|
| `admin` | Dashboard, settings, user management |
| `analytics` | Reporting, metrics, conversion tracking |
| `marketing` | Email, ads, promotions, SEO |
| `loyalty` | Rewards, referrals, customer retention |
| `payments` | Checkout, payment processing, subscriptions |
| `fulfillment` | Shipping, delivery, order management |
| `inventory` | Stock management, variants, syncing |
| `customer_support` | Help desk, chat, returns |
| `design` | Themes, customization, branding |
| `seo` | Search optimization, metadata |
| `integrations` | Third-party apps, APIs |
| `performance` | Speed, reliability, uptime |
| `pricing` | App costs, Shopify fees |
| `other` | Uncategorized |

## Configuration

Create a `.env` file:

```bash
# Required for classification
ANTHROPIC_API_KEY=sk-ant-...

# Optional - Reddit API (for reddit.py scraper)
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=ShopifyRequirementsGatherer/1.0

# Optional - Twitter API
TWITTER_BEARER_TOKEN=...

# Optional - Airtable storage
AIRTABLE_API_KEY=...
AIRTABLE_BASE_ID=...

# Optional - Scraping behavior
REQUEST_DELAY_SECONDS=1.0
MAX_RETRIES=3
```

**Note**: The RSS-based Reddit scraper (`reddit_selenium.py`) works without any API credentials.

## Storage

### SQLite (Default for local development)

```bash
python main.py scrape --storage sqlite --db-path ./data/mydb.db
```

Schema:
- `raw_sources` - Scraped data with metadata
- `insights` - Classified problems
- `clusters` - Grouped similar problems
- `opportunity_scores` - Ranked opportunities

### Airtable (Production)

Requires 4 tables in your Airtable base:
- Raw Sources
- Insights
- Problem Clusters
- Opportunity Scores

## Architecture

```
shopifly/
├── main.py                 # CLI entry point (typer + rich)
├── config/
│   └── settings.py         # Pydantic settings from .env
├── scrapers/
│   ├── base.py             # Abstract base class, DataSource enum
│   ├── reddit.py           # Reddit API via PRAW
│   ├── reddit_selenium.py  # Reddit RSS + Selenium fallback
│   ├── appstore.py         # Shopify App Store (Selenium)
│   ├── twitter.py          # Twitter/X API via Tweepy
│   └── community.py        # Community forums (httpx/BS4)
├── analysis/
│   └── classifier.py       # Claude-powered classification
├── storage/
│   ├── base.py             # Abstract storage interface
│   ├── sqlite.py           # SQLite backend
│   └── airtable.py         # Airtable backend
├── tests/
│   ├── unit/               # 47 unit tests
│   ├── integration/        # 13 integration tests
│   └── e2e/                # 14 E2E tests
├── Dockerfile              # Python 3.11 + Chrome/Selenium
├── docker-compose.yml      # Dev services
└── pyproject.toml          # Dependencies
```

## Data Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                     1. SCRAPING PHASE                       │
├─────────────────────────────────────────────────────────────┤
│  Reddit (PRAW/RSS) ──┐                                      │
│  App Store (Selenium)─┼──► RawDataPoint ──► Storage         │
│  Twitter (Tweepy) ────┤                     (raw_sources)   │
│  Community (httpx) ───┘                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   2. CLASSIFICATION PHASE                   │
├─────────────────────────────────────────────────────────────┤
│  Unprocessed Raw Data ──► Claude LLM ──► ClassifiedInsight  │
│                                          (insights table)   │
│                                          Mark as processed  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    3. ANALYSIS PHASE                        │
├─────────────────────────────────────────────────────────────┤
│  Group by keywords ──► Calculate scores ──► Rank opportunities│
│  - Frequency Score      (clusters)         (opportunity_scores)│
│  - Intensity Score                                          │
│  - WTP Score                                                │
│  - Competition Gap                                          │
└─────────────────────────────────────────────────────────────┘
```

## Testing

```bash
# Run unit & integration tests (no API keys needed)
pytest tests/unit tests/integration -v

# Run E2E tests (requires API keys)
pytest tests/e2e -v -m e2e

# Run specific test file
pytest tests/unit/test_reddit_selenium.py -v

# Run in Docker
docker run --rm --entrypoint pytest shopifly tests/unit tests/integration -v

# With coverage
pytest tests/unit tests/integration --cov=scrapers --cov=analysis --cov=storage
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run linting
ruff check .

# Format code
ruff format .

# Type checking (optional)
mypy scrapers/ analysis/ storage/
```

## Docker Compose Services

```bash
# Interactive development shell
docker-compose run dev

# Run tests
docker-compose run test

# Run specific scraper
docker-compose run scrape-reddit
docker-compose run scrape-community
```

## Dependencies

**Core**:
- httpx - Async HTTP client
- beautifulsoup4 - HTML parsing
- praw - Reddit API
- tweepy - Twitter API
- anthropic - Claude API
- pyairtable - Airtable API
- selenium + webdriver-manager - Browser automation

**Framework**:
- pydantic + pydantic-settings - Data validation
- typer + rich - CLI interface
- tenacity - Retry logic

## License

Proprietary - All Rights Reserved. See [LICENSE](LICENSE) for details.
