# Shopifly

**Discover Shopify app opportunities by analyzing real merchant pain points.**

Shopifly scrapes customer feedback from multiple sources, classifies problems using Claude AI, and visualizes insights in an interactive dashboard.

## What It Does

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   SCRAPE     │ ──► │   CLASSIFY   │ ──► │    STORE     │ ──► │  VISUALIZE   │
│              │     │              │     │              │     │              │
│ Reddit       │     │ Claude AI    │     │ SQLite       │     │ Streamlit    │
│ App Store    │     │ categorizes  │     │ persists     │     │ dashboard    │
│ Community    │     │ & scores     │     │ insights     │     │ 6 charts     │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

## Quick Start

```bash
# Clone and setup
git clone https://github.com/jonassteinberg1/shopifly.git
cd shopifly
cp .env.example .env  # Add your ANTHROPIC_API_KEY

# Run the full pipeline
docker compose run --rm app scrape --source reddit --storage sqlite --limit 100
docker compose run --rm app scrape --source appstore --storage sqlite --limit 50
docker compose run --rm app scrape --source community --storage sqlite --limit 50
docker compose run --rm app classify --storage sqlite --limit 200

# View results
docker compose run --rm app stats --storage sqlite
docker compose run --rm app opportunities --storage sqlite --top 10

# Launch dashboard
PYTHONPATH=. streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
```

## Dashboard

The Streamlit dashboard provides 6 visualizations:

| Section | Description |
|---------|-------------|
| **Overview** | Key metrics: total insights, avg frustration, WTP signals |
| **Categories** | Bar chart breakdown by problem category |
| **Trends** | Line chart of insights over time |
| **Word Cloud** | Visual frequency of keywords |
| **Top Opportunities** | Ranked table by opportunity score |
| **Competitors** | Bar chart of competitor mentions |

**Access:** `http://localhost:8501` (or your server IP)

## CLI Commands

```bash
# Scrape data
python main.py scrape --source reddit --storage sqlite --limit 100
python main.py scrape --source appstore --storage sqlite --limit 50
python main.py scrape --source community --storage sqlite --limit 50

# Classify with AI
python main.py classify --storage sqlite --concurrency 5

# View statistics
python main.py stats --storage sqlite

# Top opportunities
python main.py opportunities --storage sqlite --top 10

# Health check
python main.py health
```

## Data Sources

| Source | Method | Notes |
|--------|--------|-------|
| **Reddit** | RSS feeds | Scrapes r/shopify and related subreddits |
| **App Store** | Selenium | Shopify App Store reviews (1-3 stars) |
| **Community** | HTTP | community.shopify.com forums |

## Classification

Claude AI analyzes each data point and extracts:

- **Problem Statement** - Concise description
- **Category** - One of 14 categories (admin, analytics, marketing, etc.)
- **Frustration Level** - 1-5 scale
- **Willingness to Pay** - Boolean + supporting quotes
- **Keywords** - 3-5 terms for clustering

### Categories

`admin` · `analytics` · `marketing` · `loyalty` · `payments` · `fulfillment` · `inventory` · `customer_support` · `design` · `seo` · `integrations` · `performance` · `pricing` · `other`

## Configuration

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...   # Required for classification
REQUEST_DELAY_SECONDS=1.0       # Rate limiting
```

## Project Structure

```
shopifly/
├── main.py              # CLI entry point
├── dashboard/           # Streamlit visualization
│   ├── app.py           # Main dashboard (6 sections)
│   ├── data.py          # SQLite queries
│   └── charts.py        # Plotly charts
├── scrapers/            # Data collection
│   ├── reddit_selenium.py
│   ├── appstore.py
│   └── community.py
├── analysis/
│   └── classifier.py    # Claude AI classification
├── storage/
│   └── sqlite.py        # SQLite backend
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── tdd/
├── .beads/              # Task management
├── Dockerfile
└── docker-compose.yml
```

## Docker Commands

```bash
docker compose run --rm app <command>     # Run CLI commands
docker compose run --rm test              # Run tests
docker compose run --rm dev               # Interactive shell
docker compose up -d dashboard            # Start dashboard server
```

## Testing

```bash
# All tests
docker compose run --rm test

# Specific suites
docker compose run --rm test tests/unit -v
docker compose run --rm test tests/integration -v
docker compose run --rm test tests/e2e -v
docker compose run --rm test tests/tdd -v
```

## AI-Assisted Development

This project uses:

- **Beads** (`bd`) - Git-backed task tracking with dependency management
- **Ralph** - Autonomous iteration loops for Claude Code
- **AGENTS.md** - Instructions for AI agents

```bash
# View tasks
bd list
bd ready
bd show <task-id>

# Start autonomous development
claude --dangerously-skip-permissions
/ralph-loop "Execute Beads workflow" --max-iterations 50
```

## License

Proprietary - All Rights Reserved
