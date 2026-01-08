# Shopifly

[![Tests](https://github.com/jonassteinberg1/shopifly/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/jonassteinberg1/shopifly/actions/workflows/tests.yml)

Shopify merchant pain point analyzer - scrape, classify, and identify app opportunities.

## Features

- **4 Data Scrapers**: Reddit, Shopify App Store reviews, Twitter/X, Shopify Community forums
- **LLM Classification**: Anthropic Claude-powered analysis of merchant pain points
- **Dual Storage**: Airtable (production) or SQLite (local/testing)
- **CLI Interface**: Rich terminal UI with typer
- **149 Tests**: Comprehensive unit, integration, and E2E test coverage

## Quick Start

```bash
# Clone
git clone https://github.com/jonassteinberg1/shopifly.git
cd shopifly

# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
python main.py --help
```

## Usage

```bash
# Scrape data from all sources
python main.py scrape --limit 50

# Scrape from specific source
python main.py scrape --source appstore --limit 20

# Use SQLite instead of Airtable
python main.py scrape --storage sqlite --limit 10

# Classify scraped data with LLM
python main.py classify --limit 20

# View statistics
python main.py stats

# View top opportunities
python main.py opportunities --top 10

# Health check all services
python main.py health
```

## Configuration

Create a `.env` file with your API credentials:

```bash
# Required for classification
ANTHROPIC_API_KEY=sk-ant-...

# Optional - for Reddit scraping
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...

# Optional - for Twitter scraping
TWITTER_BEARER_TOKEN=...

# Optional - for Airtable storage
AIRTABLE_API_KEY=...
AIRTABLE_BASE_ID=...
```

## Docker

```bash
# Build
docker build -t shopifly .

# Run
docker run --rm -v $(pwd)/.env:/app/.env shopifly scrape --storage sqlite --limit 10
```

## Testing

```bash
# Run all tests (no API keys needed)
pytest tests/unit tests/integration -v

# Run E2E tests (requires API keys)
pytest tests/e2e -v -m e2e

# Run in Docker
docker run --rm --entrypoint pytest shopifly tests/unit tests/integration -v
```

## Architecture

```
shopifly/
├── scrapers/          # Data collection from 4 sources
│   ├── reddit.py      # Reddit API via PRAW
│   ├── appstore.py    # Shopify App Store reviews
│   ├── twitter.py     # Twitter/X API
│   └── community.py   # Shopify Community forums
├── analysis/
│   └── classifier.py  # LLM-based pain point classification
├── storage/
│   ├── airtable.py    # Airtable backend
│   └── sqlite.py      # SQLite backend
├── config/
│   └── settings.py    # Environment configuration
└── main.py            # CLI entry point
```

## License

MIT
