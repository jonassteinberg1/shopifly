#!/usr/bin/env python3
"""CLI for Shopify Requirements Gatherer."""

import asyncio
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from scrapers import (
    RedditScraper,
    AppStoreScraper,
    TwitterScraper,
    CommunityScraper,
    RawDataPoint,
    DataSource,
)
from analysis import Classifier, ClassifiedInsight
from storage import get_storage, StorageBackend
from config import settings


class StorageBackendType(str, Enum):
    """Storage backend types."""
    airtable = "airtable"
    sqlite = "sqlite"

app = typer.Typer(help="Shopify Requirements Gatherer - Find app opportunities")
console = Console()


@app.command()
def scrape(
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Specific source: reddit, appstore, twitter, community"
    ),
    limit: int = typer.Option(100, "--limit", "-l", help="Max items per source"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save to storage"),
    storage: StorageBackendType = typer.Option(
        StorageBackendType.airtable, "--storage", help="Storage backend: airtable or sqlite"
    ),
    db_path: Optional[str] = typer.Option(
        None, "--db-path", help="SQLite database path (only for sqlite backend)"
    ),
):
    """Scrape data from configured sources."""
    asyncio.run(_scrape(source, limit, save, storage.value, db_path))


async def _scrape(
    source: Optional[str],
    limit: int,
    save: bool,
    storage_backend: str,
    db_path: Optional[str],
):
    """Async scraping implementation."""
    scrapers = []

    if source is None or source == "reddit":
        scrapers.append(("Reddit", RedditScraper()))
    if source is None or source == "appstore":
        scrapers.append(("App Store", AppStoreScraper()))
    if source is None or source == "twitter":
        scrapers.append(("Twitter", TwitterScraper()))
    if source is None or source == "community":
        scrapers.append(("Community", CommunityScraper()))

    storage: StorageBackend | None = None
    if save:
        kwargs = {"db_path": db_path} if db_path and storage_backend == "sqlite" else {}
        storage = get_storage(backend=storage_backend, **kwargs)
    total_scraped = 0

    for name, scraper in scrapers:
        console.print(f"\n[bold blue]Scraping {name}...[/bold blue]")

        # Health check
        try:
            healthy = await scraper.health_check()
            if not healthy:
                console.print(f"[yellow]⚠ {name} health check failed, skipping[/yellow]")
                continue
        except Exception as e:
            console.print(f"[red]✗ {name} error: {e}[/red]")
            continue

        count = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Fetching from {name}...", total=None)

            async for datapoint in scraper.scrape(limit):
                count += 1
                progress.update(task, description=f"Fetched {count} items from {name}")

                if storage:
                    try:
                        storage.save_raw_datapoint(datapoint)
                    except Exception as e:
                        console.print(f"[red]Error saving: {e}[/red]")

        console.print(f"[green]✓ Scraped {count} items from {name}[/green]")
        total_scraped += count

        # Cleanup
        if hasattr(scraper, "close"):
            await scraper.close()

    console.print(f"\n[bold green]Total scraped: {total_scraped} items[/bold green]")


@app.command()
def classify(
    limit: int = typer.Option(100, "--limit", "-l", help="Max items to classify"),
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Parallel API calls"),
    storage: StorageBackendType = typer.Option(
        StorageBackendType.airtable, "--storage", help="Storage backend: airtable or sqlite"
    ),
    db_path: Optional[str] = typer.Option(
        None, "--db-path", help="SQLite database path (only for sqlite backend)"
    ),
):
    """Classify scraped data using LLM."""
    asyncio.run(_classify(limit, concurrency, storage.value, db_path))


async def _classify(limit: int, concurrency: int, storage_backend: str, db_path: Optional[str]):
    """Async classification implementation."""
    kwargs = {"db_path": db_path} if db_path and storage_backend == "sqlite" else {}
    storage = get_storage(backend=storage_backend, **kwargs)
    classifier = Classifier()

    console.print("[bold blue]Fetching unprocessed data...[/bold blue]")
    raw_data = storage.get_unprocessed_raw_data(limit)

    if not raw_data:
        console.print("[yellow]No unprocessed data found[/yellow]")
        return

    console.print(f"Found {len(raw_data)} items to classify")

    # Convert to RawDataPoint objects
    datapoints = []
    for record in raw_data:
        try:
            dp = RawDataPoint(
                source=DataSource(record["source"]),
                source_id=record["source_id"],
                url=record["url"],
                title=record.get("title"),
                content=record["content"],
                author=record.get("author"),
                created_at=record["created_at"],
            )
            datapoints.append(dp)
        except Exception as e:
            console.print(f"[red]Error parsing record: {e}[/red]")

    classified_count = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Classifying...", total=len(datapoints))

        async for insight in classifier.classify_batch(datapoints, concurrency):
            classified_count += 1
            progress.update(task, advance=1, description=f"Classified {classified_count}")

            try:
                storage.save_insight(insight)
                storage.mark_as_processed(insight.source_id)
            except Exception as e:
                console.print(f"[red]Error saving insight: {e}[/red]")

    console.print(f"\n[bold green]Classified {classified_count} items[/bold green]")


@app.command()
def stats(
    storage: StorageBackendType = typer.Option(
        StorageBackendType.airtable, "--storage", help="Storage backend: airtable or sqlite"
    ),
    db_path: Optional[str] = typer.Option(
        None, "--db-path", help="SQLite database path (only for sqlite backend)"
    ),
):
    """Show statistics about collected data."""
    kwargs = {"db_path": db_path} if db_path and storage.value == "sqlite" else {}
    storage_inst = get_storage(backend=storage.value, **kwargs)

    try:
        data = storage_inst.get_stats()
    except Exception as e:
        console.print(f"[red]Error fetching stats: {e}[/red]")
        return

    console.print("\n[bold]📊 Data Collection Stats[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")

    table.add_row("Raw Data Points", str(data["raw_data_points"]))
    table.add_row("Classified Insights", str(data["classified_insights"]))
    table.add_row("Problem Clusters", str(data["problem_clusters"]))
    table.add_row("Scored Opportunities", str(data["scored_opportunities"]))

    console.print(table)

    if data["category_breakdown"]:
        console.print("\n[bold]📂 Category Breakdown[/bold]\n")
        cat_table = Table(show_header=True, header_style="bold magenta")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Count", justify="right")

        for cat, count in sorted(
            data["category_breakdown"].items(), key=lambda x: x[1], reverse=True
        ):
            cat_table.add_row(cat, str(count))

        console.print(cat_table)


@app.command()
def opportunities(
    top: int = typer.Option(10, "--top", "-t", help="Number of top opportunities to show"),
    storage: StorageBackendType = typer.Option(
        StorageBackendType.airtable, "--storage", help="Storage backend: airtable or sqlite"
    ),
    db_path: Optional[str] = typer.Option(
        None, "--db-path", help="SQLite database path (only for sqlite backend)"
    ),
):
    """Show ranked app opportunities."""
    kwargs = {"db_path": db_path} if db_path and storage.value == "sqlite" else {}
    storage_inst = get_storage(backend=storage.value, **kwargs)

    try:
        opps = storage_inst.get_ranked_opportunities()[:top]
    except Exception as e:
        console.print(f"[red]Error fetching opportunities: {e}[/red]")
        return

    if not opps:
        console.print("[yellow]No scored opportunities yet. Run the scoring process first.[/yellow]")
        return

    console.print(f"\n[bold]🏆 Top {top} App Opportunities[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Rank", justify="right", style="cyan")
    table.add_column("Problem Cluster")
    table.add_column("Score", justify="right")
    table.add_column("Freq", justify="right")
    table.add_column("WTP", justify="right")
    table.add_column("Gap", justify="right")

    for i, opp in enumerate(opps, 1):
        table.add_row(
            str(i),
            opp.get("cluster_name", "Unknown")[:40],
            f"{opp.get('total_score', 0):.1f}",
            f"{opp.get('frequency_score', 0):.0f}",
            f"{opp.get('wtp_score', 0):.0f}",
            f"{opp.get('competition_gap_score', 0):.0f}",
        )

    console.print(table)


@app.command()
def health():
    """Check connectivity to all services."""
    asyncio.run(_health())


async def _health():
    """Async health check implementation."""
    console.print("\n[bold]🏥 Health Check[/bold]\n")

    checks = [
        ("Reddit API", _check_reddit),
        ("Shopify App Store", _check_appstore),
        ("Twitter API", _check_twitter),
        ("Shopify Community", _check_community),
        ("Anthropic API", _check_anthropic),
        ("Airtable API", _check_airtable),
    ]

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Service", style="cyan")
    table.add_column("Status")
    table.add_column("Notes")

    for name, check_fn in checks:
        try:
            status, notes = await check_fn()
            if status:
                table.add_row(name, "[green]✓ OK[/green]", notes)
            else:
                table.add_row(name, "[red]✗ Failed[/red]", notes)
        except Exception as e:
            table.add_row(name, "[red]✗ Error[/red]", str(e)[:50])

    console.print(table)


async def _check_reddit() -> tuple[bool, str]:
    if not settings.reddit_client_id:
        return False, "Missing reddit_client_id"
    scraper = RedditScraper()
    ok = await scraper.health_check()
    return ok, "Connected" if ok else "Connection failed"


async def _check_appstore() -> tuple[bool, str]:
    scraper = AppStoreScraper()
    ok = await scraper.health_check()
    await scraper.close()
    return ok, "Connected" if ok else "Connection failed"


async def _check_twitter() -> tuple[bool, str]:
    if not settings.twitter_bearer_token:
        return False, "Missing twitter_bearer_token"
    scraper = TwitterScraper()
    ok = await scraper.health_check()
    return ok, "Connected" if ok else "Connection failed"


async def _check_community() -> tuple[bool, str]:
    scraper = CommunityScraper()
    ok = await scraper.health_check()
    await scraper.close()
    return ok, "Connected" if ok else "Connection failed"


async def _check_anthropic() -> tuple[bool, str]:
    if not settings.anthropic_api_key:
        return False, "Missing anthropic_api_key"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}],
        )
        return True, "Connected"
    except Exception as e:
        return False, str(e)[:50]


async def _check_airtable() -> tuple[bool, str]:
    if not settings.airtable_api_key:
        return False, "Missing airtable_api_key"
    if not settings.airtable_base_id:
        return False, "Missing airtable_base_id"
    try:
        storage = AirtableStorage()
        storage.get_stats()
        return True, "Connected"
    except Exception as e:
        return False, str(e)[:50]


@app.command()
def init():
    """Initialize the project with a sample .env file."""
    env_content = """# Shopify Requirements Gatherer Configuration

# Reddit API (https://www.reddit.com/prefs/apps)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=ShopifyRequirementsGatherer/1.0

# Twitter/X API (https://developer.twitter.com)
TWITTER_BEARER_TOKEN=

# Anthropic API (https://console.anthropic.com)
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-3-haiku-20240307

# Airtable (https://airtable.com/account)
AIRTABLE_API_KEY=
AIRTABLE_BASE_ID=

# Scraping settings
REQUEST_DELAY_SECONDS=1.0
MAX_RETRIES=3
"""

    import os
    env_path = os.path.join(os.path.dirname(__file__), ".env")

    if os.path.exists(env_path):
        console.print("[yellow]⚠ .env file already exists[/yellow]")
        if not typer.confirm("Overwrite?"):
            return

    with open(env_path, "w") as f:
        f.write(env_content)

    console.print("[green]✓ Created .env file[/green]")
    console.print("\nNext steps:")
    console.print("1. Fill in your API credentials in .env")
    console.print("2. Create an Airtable base with these tables:")
    console.print("   - Raw Sources")
    console.print("   - Insights")
    console.print("   - Problem Clusters")
    console.print("   - Opportunity Scores")
    console.print("3. Run [cyan]python main.py health[/cyan] to verify connections")
    console.print("4. Run [cyan]python main.py scrape[/cyan] to start collecting data")


if __name__ == "__main__":
    app()
