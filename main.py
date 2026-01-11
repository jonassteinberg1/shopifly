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
    RedditSeleniumScraper,
    AppStoreScraper,
    TwitterScraper,
    CommunityScraper,
    RawDataPoint,
    DataSource,
)
from analysis import Classifier, ClassifiedInsight
from analysis.classifier import ProblemCategory
from analysis.interview_reranker import InterviewReranker, format_opportunity_report
from storage import get_storage, StorageBackend
from research import (
    InterviewStorage,
    InterviewParticipant,
    InterviewInsight,
    InterviewFrequency,
    BusinessImpact,
)
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
        scrapers.append(("Reddit", RedditSeleniumScraper()))
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
    # Use RSS-based scraper which doesn't require API credentials
    scraper = RedditSeleniumScraper()
    ok = await scraper.health_check()
    return ok, "Connected (RSS)" if ok else "Connection failed"


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


# -------------------------------------------------------------------------
# Interview Research Commands
# -------------------------------------------------------------------------

interview_app = typer.Typer(help="Interview research commands")
app.add_typer(interview_app, name="interview")


@interview_app.command("add-participant")
def interview_add_participant(
    participant_id: str = typer.Option(..., "--id", help="Unique participant ID (e.g., P001)"),
    vertical: str = typer.Option(..., "--vertical", "-v", help="Store vertical (e.g., fashion, home_goods)"),
    gmv_range: str = typer.Option(..., "--gmv", help="Monthly GMV range (e.g., '$10K-$30K')"),
    store_age: int = typer.Option(..., "--age", help="Store age in months"),
    team_size: int = typer.Option(1, "--team", help="Team size"),
    app_count: int = typer.Option(0, "--apps", help="Number of Shopify apps in use"),
    app_budget: Optional[int] = typer.Option(None, "--budget", help="Monthly app budget in dollars"),
    beta_tester: bool = typer.Option(False, "--beta", help="Interested in beta testing"),
    db_path: Optional[str] = typer.Option(None, "--db-path", help="SQLite database path"),
):
    """Add a new interview participant."""
    from datetime import datetime

    storage = InterviewStorage(db_path=db_path)

    participant = InterviewParticipant(
        participant_id=participant_id,
        interview_date=datetime.utcnow(),
        store_vertical=vertical,
        monthly_gmv_range=gmv_range,
        store_age_months=store_age,
        team_size=team_size,
        app_count=app_count,
        monthly_app_budget=app_budget,
        beta_tester=beta_tester,
    )

    try:
        storage.save_participant(participant)
        console.print(f"[green]✓ Added participant {participant_id}[/green]")
    except Exception as e:
        console.print(f"[red]Error adding participant: {e}[/red]")


@interview_app.command("add-insight")
def interview_add_insight(
    interview_id: str = typer.Option(..., "--interview", "-i", help="Interview ID"),
    participant_id: str = typer.Option(..., "--participant", "-p", help="Participant ID"),
    category: str = typer.Option(..., "--category", "-c", help="Pain point category"),
    summary: str = typer.Option(..., "--summary", "-s", help="Pain point summary"),
    frustration: int = typer.Option(3, "--frustration", "-f", help="Frustration level (1-5)"),
    frequency: str = typer.Option("weekly", "--frequency", help="Frequency: daily, weekly, monthly, occasionally"),
    impact: str = typer.Option("medium", "--impact", help="Business impact: high, medium, low"),
    wtp_low: Optional[int] = typer.Option(None, "--wtp-low", help="WTP low bound ($/month)"),
    wtp_high: Optional[int] = typer.Option(None, "--wtp-high", help="WTP high bound ($/month)"),
    workaround: Optional[str] = typer.Option(None, "--workaround", help="Current workaround"),
    notes: str = typer.Option("", "--notes", help="Interviewer notes"),
    db_path: Optional[str] = typer.Option(None, "--db-path", help="SQLite database path"),
):
    """Add an insight from an interview."""
    storage = InterviewStorage(db_path=db_path)

    try:
        pain_category = ProblemCategory(category)
    except ValueError:
        console.print(f"[red]Invalid category: {category}[/red]")
        console.print(f"Valid categories: {[c.value for c in ProblemCategory]}")
        return

    try:
        freq = InterviewFrequency(frequency)
    except ValueError:
        console.print(f"[red]Invalid frequency: {frequency}[/red]")
        return

    try:
        biz_impact = BusinessImpact(impact)
    except ValueError:
        console.print(f"[red]Invalid impact: {impact}[/red]")
        return

    insight = InterviewInsight(
        interview_id=interview_id,
        participant_id=participant_id,
        pain_category=pain_category,
        pain_summary=summary,
        frustration_level=frustration,
        frequency=freq,
        business_impact=biz_impact,
        wtp_amount_low=wtp_low,
        wtp_amount_high=wtp_high,
        current_workaround=workaround,
        interviewer_notes=notes,
    )

    try:
        record_id = storage.save_insight(insight)
        console.print(f"[green]✓ Added insight (ID: {record_id})[/green]")
    except Exception as e:
        console.print(f"[red]Error adding insight: {e}[/red]")


@interview_app.command("stats")
def interview_stats(
    db_path: Optional[str] = typer.Option(None, "--db-path", help="SQLite database path"),
):
    """Show interview research statistics."""
    storage = InterviewStorage(db_path=db_path)

    try:
        stats = storage.get_interview_stats()
    except Exception as e:
        console.print(f"[red]Error fetching stats: {e}[/red]")
        return

    console.print("\n[bold]📊 Interview Research Stats[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total Participants", str(stats["total_participants"]))
    table.add_row("Total Insights", str(stats["total_insights"]))
    table.add_row("Avg Insights/Interview", f"{stats['avg_insights_per_interview']:.1f}")
    table.add_row("Beta Testers", str(stats["beta_testers"]))
    table.add_row("Insights with WTP", str(stats["insights_with_wtp"]))
    table.add_row("WTP Rate", f"{stats['wtp_rate']:.1f}%")
    if stats["avg_wtp_amount"]:
        table.add_row("Avg WTP Amount", f"${stats['avg_wtp_amount']:.0f}/mo")
    if stats["wtp_range"]:
        table.add_row("WTP Range", f"${stats['wtp_range'][0]} - ${stats['wtp_range'][1]}/mo")

    console.print(table)

    # Category breakdown
    category_stats = storage.get_category_summary()
    if category_stats:
        console.print("\n[bold]📂 Category Breakdown[/bold]\n")
        cat_table = Table(show_header=True, header_style="bold magenta")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Count", justify="right")
        cat_table.add_column("Avg Frustration", justify="right")
        cat_table.add_column("WTP Count", justify="right")
        cat_table.add_column("Avg WTP", justify="right")

        for cat, data in sorted(category_stats.items(), key=lambda x: x[1]["count"], reverse=True):
            cat_table.add_row(
                cat,
                str(data["count"]),
                f"{data['avg_frustration']:.1f}",
                str(data["wtp_count"]),
                f"${data['avg_wtp']:.0f}" if data["avg_wtp"] else "-",
            )

        console.print(cat_table)


@interview_app.command("list")
def interview_list(
    db_path: Optional[str] = typer.Option(None, "--db-path", help="SQLite database path"),
):
    """List all interview participants."""
    storage = InterviewStorage(db_path=db_path)

    try:
        participants = storage.get_all_participants()
    except Exception as e:
        console.print(f"[red]Error fetching participants: {e}[/red]")
        return

    if not participants:
        console.print("[yellow]No participants found[/yellow]")
        return

    console.print(f"\n[bold]👥 Interview Participants ({len(participants)})[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Date")
    table.add_column("Vertical")
    table.add_column("GMV Range")
    table.add_column("Apps")
    table.add_column("Beta")

    for p in participants:
        table.add_row(
            p.participant_id,
            p.interview_date.strftime("%Y-%m-%d"),
            p.store_vertical,
            p.monthly_gmv_range,
            str(p.app_count),
            "✓" if p.beta_tester else "",
        )

    console.print(table)


@interview_app.command("beta-testers")
def interview_beta_testers(
    db_path: Optional[str] = typer.Option(None, "--db-path", help="SQLite database path"),
):
    """List participants interested in beta testing."""
    storage = InterviewStorage(db_path=db_path)

    try:
        testers = storage.get_beta_testers()
    except Exception as e:
        console.print(f"[red]Error fetching beta testers: {e}[/red]")
        return

    if not testers:
        console.print("[yellow]No beta testers found[/yellow]")
        return

    console.print(f"\n[bold]🧪 Beta Testers ({len(testers)})[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Date")
    table.add_column("Vertical")
    table.add_column("GMV Range")
    table.add_column("App Budget")

    for p in testers:
        table.add_row(
            p.participant_id,
            p.interview_date.strftime("%Y-%m-%d"),
            p.store_vertical,
            p.monthly_gmv_range,
            f"${p.monthly_app_budget}/mo" if p.monthly_app_budget else "-",
        )

    console.print(table)


@interview_app.command("opportunities")
def interview_opportunities(
    top: int = typer.Option(10, "--top", "-t", help="Number of top opportunities"),
    validated_only: bool = typer.Option(False, "--validated", help="Show only interview-validated"),
    wtp_only: bool = typer.Option(False, "--wtp", help="Show only with confirmed WTP"),
    storage_type: StorageBackendType = typer.Option(
        StorageBackendType.sqlite, "--storage", help="Storage backend"
    ),
    db_path: Optional[str] = typer.Option(None, "--db-path", help="SQLite database path"),
):
    """Show ranked opportunities with interview validation."""
    kwargs = {"db_path": db_path} if db_path and storage_type.value == "sqlite" else {}
    main_storage = get_storage(backend=storage_type.value, **kwargs)
    interview_storage = InterviewStorage(db_path=db_path)

    try:
        scraped_insights = main_storage.get_all_insights()
        interview_insights = interview_storage.get_all_insights()
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        return

    if not scraped_insights and not interview_insights:
        console.print("[yellow]No insights found. Run scraping and/or add interview data first.[/yellow]")
        return

    reranker = InterviewReranker(scraped_insights, interview_insights)

    if wtp_only:
        opportunities = reranker.get_wtp_confirmed_opportunities()
    elif validated_only:
        opportunities = reranker.get_validated_opportunities()
    else:
        opportunities = reranker.get_top_opportunities(top)

    if not opportunities:
        console.print("[yellow]No opportunities found matching criteria[/yellow]")
        return

    console.print(f"\n[bold]🏆 Ranked Opportunities (Interview-Enhanced)[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Rank", justify="right", style="cyan")
    table.add_column("Category")
    table.add_column("Score", justify="right")
    table.add_column("Base", justify="right")
    table.add_column("Interview+", justify="right")
    table.add_column("Validated")
    table.add_column("WTP")

    for i, opp in enumerate(opportunities[:top], 1):
        table.add_row(
            str(i),
            opp.category.value,
            f"{opp.total_score:.1f}",
            f"{opp.base_score:.1f}",
            f"+{opp.interview_bonus:.1f}",
            "✓" if opp.interview_validated else "",
            f"${opp.interview_avg_wtp:.0f}" if opp.interview_avg_wtp else "",
        )

    console.print(table)

    # Show key quotes for top opportunities
    console.print("\n[bold]💬 Key Quotes from Interviews[/bold]\n")
    for opp in opportunities[:3]:
        if opp.key_quotes:
            console.print(f"[cyan]{opp.category.value.upper()}:[/cyan]")
            for quote in opp.key_quotes[:2]:
                console.print(f'  "{quote[:100]}..."' if len(quote) > 100 else f'  "{quote}"')
            console.print()


@interview_app.command("import-vtt")
def interview_import_vtt(
    vtt_file: str = typer.Argument(..., help="Path to Zoom VTT transcript file"),
    participant_id: Optional[str] = typer.Option(None, "--participant", "-p", help="Participant ID to link"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory for JSON transcript"),
):
    """Import a Zoom VTT transcript file.

    Downloads from Zoom portal: Recordings -> Download transcript (VTT)
    """
    from pathlib import Path
    from research.transcription import import_vtt_file, get_default_transcript_dir

    vtt_path = Path(vtt_file)
    if not vtt_path.exists():
        console.print(f"[red]VTT file not found: {vtt_file}[/red]")
        raise typer.Exit(1)

    out_dir = Path(output_dir) if output_dir else get_default_transcript_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        with console.status(f"Importing {vtt_path.name}..."):
            transcript = import_vtt_file(vtt_path, participant_id=participant_id, output_dir=out_dir)

        output_path = out_dir / f"{vtt_path.stem}.json"
        console.print(f"[green]✓ Imported VTT transcript[/green]")
        console.print(f"  Source: {vtt_path.name}")
        console.print(f"  Segments: {len(transcript.segments)}")
        console.print(f"  Duration: {transcript.duration_seconds:.1f}s" if transcript.duration_seconds else "")
        console.print(f"  Output: {output_path}")
        if participant_id:
            console.print(f"  Participant: {participant_id}")

    except Exception as e:
        console.print(f"[red]Error importing VTT: {e}[/red]")
        raise typer.Exit(1)


@interview_app.command("transcribe")
def interview_transcribe(
    audio_file: str = typer.Argument(..., help="Path to audio file (mp3, wav, m4a, etc.)"),
    model: str = typer.Option("base", "--model", "-m", help="Whisper model: tiny, base, small, medium, large"),
    participant_id: Optional[str] = typer.Option(None, "--participant", "-p", help="Participant ID to link"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory for JSON transcript"),
):
    """Transcribe an audio recording using Whisper.

    Requires openai-whisper: pip install openai-whisper
    """
    from pathlib import Path
    from research.transcription import transcribe_audio_whisper, get_default_transcript_dir

    audio_path = Path(audio_file)
    if not audio_path.exists():
        console.print(f"[red]Audio file not found: {audio_file}[/red]")
        raise typer.Exit(1)

    out_dir = Path(output_dir) if output_dir else get_default_transcript_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        console.print(f"[cyan]Transcribing with Whisper ({model} model)...[/cyan]")
        console.print("[dim]This may take a while depending on audio length and model size.[/dim]")

        transcript = transcribe_audio_whisper(
            audio_path, model_name=model, participant_id=participant_id, output_dir=out_dir
        )

        output_path = out_dir / f"{audio_path.stem}.json"
        console.print(f"\n[green]✓ Transcription complete[/green]")
        console.print(f"  Source: {audio_path.name}")
        console.print(f"  Model: {model}")
        console.print(f"  Language: {transcript.language}")
        console.print(f"  Segments: {len(transcript.segments)}")
        console.print(f"  Duration: {transcript.duration_seconds:.1f}s" if transcript.duration_seconds else "")
        console.print(f"  Output: {output_path}")
        if participant_id:
            console.print(f"  Participant: {participant_id}")

    except ImportError:
        console.print("[red]openai-whisper is not installed.[/red]")
        console.print("Install with: [cyan]pip install openai-whisper[/cyan]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error transcribing: {e}[/red]")
        raise typer.Exit(1)


@interview_app.command("classify-transcript")
def interview_classify_transcript(
    transcript_file: str = typer.Argument(..., help="Path to transcript JSON file"),
    participant_id: Optional[str] = typer.Option(None, "--participant", "-p", help="Participant ID (overrides transcript)"),
    interview_id: Optional[str] = typer.Option(None, "--interview", "-i", help="Interview ID prefix"),
    db_path: Optional[str] = typer.Option(None, "--db-path", help="SQLite database path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze but don't save to database"),
):
    """Extract and classify insights from a transcript using LLM.

    Analyzes the transcript and extracts pain points, WTP signals, etc.
    """
    from pathlib import Path
    from research.transcription import Transcript
    from research.transcript_classifier import TranscriptClassifier

    transcript_path = Path(transcript_file)
    if not transcript_path.exists():
        console.print(f"[red]Transcript file not found: {transcript_file}[/red]")
        raise typer.Exit(1)

    try:
        # Load transcript
        transcript = Transcript.from_json_file(transcript_path)

        # Use participant ID from transcript if not overridden
        pid = participant_id or transcript.participant_id
        if not pid:
            console.print("[yellow]Warning: No participant ID specified. Using 'unknown'.[/yellow]")
            pid = "unknown"

        # Generate interview ID if not provided
        iid = interview_id or f"INT_{transcript_path.stem}"

        console.print(f"[cyan]Analyzing transcript with LLM...[/cyan]")

        classifier = TranscriptClassifier()
        analysis = classifier.classify_transcript(transcript)

        console.print(f"\n[green]✓ Analysis complete[/green]")
        console.print(f"  Pain points found: {len(analysis.pain_points)}")
        console.print(f"  WTP signals found: {len(analysis.wtp_signals)}")

        # Show extracted pain points
        if analysis.pain_points:
            console.print("\n[bold]Extracted Pain Points:[/bold]")
            for i, pp in enumerate(analysis.pain_points, 1):
                console.print(f"\n  {i}. [{pp.category.upper()}] {pp.summary}")
                console.print(f"     Frustration: {pp.frustration_level}/5 | Impact: {pp.business_impact}")
                if pp.verbatim_quote:
                    quote = pp.verbatim_quote[:80] + "..." if len(pp.verbatim_quote) > 80 else pp.verbatim_quote
                    console.print(f'     Quote: "{quote}"')

        # Show WTP signals
        if analysis.wtp_signals:
            console.print("\n[bold]WTP Signals:[/bold]")
            for wtp in analysis.wtp_signals:
                amount = f" ({wtp.amount_mentioned})" if wtp.amount_mentioned else ""
                console.print(f"  • {wtp.context}{amount}")
                console.print(f'    "{wtp.verbatim_quote[:60]}..."' if len(wtp.verbatim_quote) > 60 else f'    "{wtp.verbatim_quote}"')

        if dry_run:
            console.print("\n[yellow]Dry run - insights not saved to database.[/yellow]")
        else:
            # Convert to InterviewInsights and save
            storage = InterviewStorage(db_path=db_path)
            insights = classifier.convert_to_interview_insights(analysis, iid, pid)

            saved_count = 0
            for insight in insights:
                try:
                    storage.save_insight(insight)
                    saved_count += 1
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not save insight: {e}[/yellow]")

            console.print(f"\n[green]✓ Saved {saved_count} insights to database[/green]")

    except Exception as e:
        console.print(f"[red]Error classifying transcript: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@interview_app.command("process-recording")
def interview_process_recording(
    audio_file: str = typer.Argument(..., help="Path to audio file (mp3, wav, m4a, etc.)"),
    participant_id: str = typer.Option(..., "--participant", "-p", help="Participant ID"),
    model: str = typer.Option("base", "--model", "-m", help="Whisper model: tiny, base, small, medium, large"),
    interview_id: Optional[str] = typer.Option(None, "--interview", "-i", help="Interview ID prefix"),
    db_path: Optional[str] = typer.Option(None, "--db-path", help="SQLite database path"),
):
    """End-to-end processing: transcribe audio and extract insights.

    Runs the full pipeline:
    1. Transcribe audio with Whisper
    2. Classify transcript with LLM
    3. Save insights to database
    """
    from pathlib import Path
    from research.transcription import transcribe_audio_whisper, get_default_transcript_dir
    from research.transcript_classifier import TranscriptClassifier

    audio_path = Path(audio_file)
    if not audio_path.exists():
        console.print(f"[red]Audio file not found: {audio_file}[/red]")
        raise typer.Exit(1)

    out_dir = get_default_transcript_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    iid = interview_id or f"INT_{audio_path.stem}"

    try:
        # Step 1: Transcribe
        console.print(f"\n[bold cyan]Step 1/3: Transcribing audio ({model} model)...[/bold cyan]")
        console.print("[dim]This may take a while...[/dim]")

        transcript = transcribe_audio_whisper(
            audio_path, model_name=model, participant_id=participant_id, output_dir=out_dir
        )

        console.print(f"[green]✓ Transcription complete[/green]")
        console.print(f"  Segments: {len(transcript.segments)}")
        console.print(f"  Duration: {transcript.duration_seconds:.1f}s" if transcript.duration_seconds else "")

        # Step 2: Classify
        console.print(f"\n[bold cyan]Step 2/3: Analyzing transcript with LLM...[/bold cyan]")

        classifier = TranscriptClassifier()
        analysis = classifier.classify_transcript(transcript)

        console.print(f"[green]✓ Analysis complete[/green]")
        console.print(f"  Pain points: {len(analysis.pain_points)}")
        console.print(f"  WTP signals: {len(analysis.wtp_signals)}")

        # Step 3: Save
        console.print(f"\n[bold cyan]Step 3/3: Saving to database...[/bold cyan]")

        storage = InterviewStorage(db_path=db_path)
        insights = classifier.convert_to_interview_insights(analysis, iid, participant_id)

        saved_count = 0
        for insight in insights:
            try:
                storage.save_insight(insight)
                saved_count += 1
            except Exception as e:
                console.print(f"[yellow]Warning: {e}[/yellow]")

        console.print(f"[green]✓ Saved {saved_count} insights[/green]")

        # Summary
        console.print(f"\n[bold green]✓ Processing complete![/bold green]")
        console.print(f"  Transcript: {out_dir / f'{audio_path.stem}.json'}")
        console.print(f"  Participant: {participant_id}")
        console.print(f"  Insights saved: {saved_count}")

        # Show top pain points
        if analysis.pain_points:
            console.print(f"\n[bold]Top Pain Points:[/bold]")
            for pp in analysis.pain_points[:3]:
                console.print(f"  • [{pp.category.upper()}] {pp.summary[:60]}...")

    except ImportError:
        console.print("[red]openai-whisper is not installed.[/red]")
        console.print("Install with: [cyan]pip install openai-whisper[/cyan]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
