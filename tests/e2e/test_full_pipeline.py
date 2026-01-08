"""End-to-end tests for the full pipeline.

These tests hit real APIs with minimal data to prove the full pipeline works.
Run with: pytest tests/e2e -v -m e2e

Requirements:
- Reddit API credentials (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
- Twitter API credentials (TWITTER_BEARER_TOKEN)
- Anthropic API credentials (ANTHROPIC_API_KEY)
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, AsyncMock

from scrapers import RedditScraper, AppStoreScraper, TwitterScraper, CommunityScraper
from scrapers.base import RawDataPoint, DataSource
from analysis import Classifier
from storage.sqlite import SQLiteStorage

from tests.e2e.conftest import (
    skip_without_reddit,
    skip_without_twitter,
    skip_without_anthropic,
    E2E_CONFIG,
)


@pytest.mark.e2e
class TestRedditPipeline:
    """E2E tests for Reddit scraping pipeline."""

    @skip_without_reddit
    @pytest.mark.asyncio
    async def test_e2e_reddit_pipeline(self, sqlite_storage, e2e_config):
        """Test Reddit scrape → Store → Verify flow."""
        scraper = RedditScraper()

        # Health check
        healthy = await scraper.health_check()
        assert healthy, "Reddit scraper health check failed"

        # Scrape
        count = 0
        async for datapoint in scraper.scrape(limit=e2e_config["reddit_limit"]):
            assert isinstance(datapoint, RawDataPoint)
            assert datapoint.source == DataSource.REDDIT
            assert datapoint.content
            assert datapoint.url

            # Store
            record_id = sqlite_storage.save_raw_datapoint(datapoint)
            assert record_id is not None
            count += 1

        assert count > 0, "No Reddit posts were scraped"

        # Verify storage
        stats = sqlite_storage.get_stats()
        assert stats["raw_data_points"] == count

        # Get unprocessed
        unprocessed = sqlite_storage.get_unprocessed_raw_data()
        assert len(unprocessed) == count


@pytest.mark.e2e
class TestAppStorePipeline:
    """E2E tests for App Store scraping pipeline."""

    @pytest.mark.asyncio
    async def test_e2e_appstore_pipeline(self, sqlite_storage, e2e_config):
        """Test App Store scrape → Store → Verify flow."""
        scraper = AppStoreScraper()

        try:
            # Health check
            healthy = await scraper.health_check()
            if not healthy:
                pytest.skip("App Store scraper health check failed")

            # Scrape
            count = 0
            async for datapoint in scraper.scrape(limit=e2e_config["appstore_limit"]):
                assert isinstance(datapoint, RawDataPoint)
                assert datapoint.source == DataSource.APP_STORE
                assert datapoint.content

                # Store
                record_id = sqlite_storage.save_raw_datapoint(datapoint)
                assert record_id is not None
                count += 1

            # App store may have limited reviews, so we allow 0
            # Verify storage matches what we scraped
            stats = sqlite_storage.get_stats()
            assert stats["raw_data_points"] == count

        finally:
            await scraper.close()


@pytest.mark.e2e
class TestTwitterPipeline:
    """E2E tests for Twitter scraping pipeline."""

    @skip_without_twitter
    @pytest.mark.asyncio
    async def test_e2e_twitter_pipeline(self, sqlite_storage, e2e_config):
        """Test Twitter scrape → Store → Verify flow."""
        scraper = TwitterScraper()

        # Health check
        healthy = await scraper.health_check()
        assert healthy, "Twitter scraper health check failed"

        # Scrape
        count = 0
        async for datapoint in scraper.scrape(limit=e2e_config["twitter_limit"]):
            assert isinstance(datapoint, RawDataPoint)
            assert datapoint.source == DataSource.TWITTER
            assert datapoint.content

            # Store
            record_id = sqlite_storage.save_raw_datapoint(datapoint)
            assert record_id is not None
            count += 1

        assert count > 0, "No tweets were scraped"

        # Verify storage
        stats = sqlite_storage.get_stats()
        assert stats["raw_data_points"] == count


@pytest.mark.e2e
class TestCommunityPipeline:
    """E2E tests for Shopify Community scraping pipeline."""

    @pytest.mark.asyncio
    async def test_e2e_community_pipeline(self, sqlite_storage, e2e_config):
        """Test Community scrape → Store → Verify flow."""
        scraper = CommunityScraper()

        try:
            # Health check
            healthy = await scraper.health_check()
            if not healthy:
                pytest.skip("Community scraper health check failed")

            # Scrape
            count = 0
            async for datapoint in scraper.scrape(limit=e2e_config["community_limit"]):
                assert isinstance(datapoint, RawDataPoint)
                assert datapoint.source == DataSource.COMMUNITY
                assert datapoint.content

                # Store
                record_id = sqlite_storage.save_raw_datapoint(datapoint)
                assert record_id is not None
                count += 1

            # Verify storage matches what we scraped
            stats = sqlite_storage.get_stats()
            assert stats["raw_data_points"] == count

        finally:
            await scraper.close()


@pytest.mark.e2e
class TestClassificationPipeline:
    """E2E tests for LLM classification pipeline."""

    @skip_without_anthropic
    @pytest.mark.asyncio
    async def test_e2e_classification_pipeline(self, sqlite_storage):
        """Test classification with real Anthropic API."""
        classifier = Classifier()

        # Create test data
        test_datapoints = [
            RawDataPoint(
                source=DataSource.REDDIT,
                source_id="e2e_test_1",
                url="https://reddit.com/r/shopify/test1",
                title="Analytics are terrible",
                content="I've been using Shopify for 2 years and the analytics are terrible. "
                "I need better conversion tracking. I'd pay $30/month for good analytics.",
                author="test_user",
                created_at=datetime.now(),
            ),
            RawDataPoint(
                source=DataSource.REDDIT,
                source_id="e2e_test_2",
                url="https://reddit.com/r/shopify/test2",
                title="Inventory management issues",
                content="Managing inventory across multiple channels is a nightmare. "
                "The stock sync takes hours and often fails. Very frustrating!",
                author="test_user2",
                created_at=datetime.now(),
            ),
        ]

        # Store test data
        for dp in test_datapoints:
            sqlite_storage.save_raw_datapoint(dp)

        # Classify
        classified_count = 0
        async for insight in classifier.classify_batch(test_datapoints, concurrency=1):
            assert insight.source_id in ["e2e_test_1", "e2e_test_2"]
            assert insight.problem_statement
            assert insight.category
            assert 1 <= insight.frustration_level <= 5
            assert 1 <= insight.clarity_score <= 5

            # Save insight
            sqlite_storage.save_insight(insight)
            sqlite_storage.mark_as_processed(insight.source_id)
            classified_count += 1

        assert classified_count == 2, f"Expected 2 classifications, got {classified_count}"

        # Verify storage
        stats = sqlite_storage.get_stats()
        assert stats["classified_insights"] == 2


@pytest.mark.e2e
class TestFullPipeline:
    """E2E tests for the complete pipeline."""

    @skip_without_reddit
    @skip_without_anthropic
    @pytest.mark.asyncio
    async def test_e2e_full_pipeline(self, sqlite_storage, e2e_config):
        """Test full pipeline: Reddit scrape → Store → Classify → Verify."""
        # Step 1: Scrape from Reddit
        scraper = RedditScraper()
        healthy = await scraper.health_check()
        assert healthy, "Reddit health check failed"

        datapoints = []
        async for datapoint in scraper.scrape(limit=2):  # Just 2 for cost
            sqlite_storage.save_raw_datapoint(datapoint)
            datapoints.append(datapoint)

        assert len(datapoints) > 0, "No data scraped"

        # Step 2: Classify
        classifier = Classifier()
        insights = []
        async for insight in classifier.classify_batch(datapoints, concurrency=1):
            sqlite_storage.save_insight(insight)
            sqlite_storage.mark_as_processed(insight.source_id)
            insights.append(insight)

        # Step 3: Verify
        stats = sqlite_storage.get_stats()
        assert stats["raw_data_points"] == len(datapoints)
        assert stats["classified_insights"] == len(insights)

        # All raw data should be processed
        unprocessed = sqlite_storage.get_unprocessed_raw_data()
        assert len(unprocessed) == 0


@pytest.mark.e2e
class TestCLICommands:
    """E2E tests for CLI commands with SQLite backend."""

    def test_e2e_cli_stats_sqlite(self, e2e_db_path):
        """Test stats command with SQLite backend."""
        from typer.testing import CliRunner
        from main import app

        runner = CliRunner()

        # Run stats command with SQLite
        result = runner.invoke(
            app, ["stats", "--storage", "sqlite", "--db-path", e2e_db_path]
        )

        assert result.exit_code == 0
        assert "Data Collection Stats" in result.stdout
        assert "0" in result.stdout  # Empty database

    def test_e2e_cli_opportunities_sqlite(self, e2e_db_path):
        """Test opportunities command with SQLite backend."""
        from typer.testing import CliRunner
        from main import app

        runner = CliRunner()

        result = runner.invoke(
            app, ["opportunities", "--storage", "sqlite", "--db-path", e2e_db_path]
        )

        assert result.exit_code == 0
        assert "No scored opportunities" in result.stdout

    @skip_without_reddit
    def test_e2e_cli_scrape_sqlite(self, e2e_db_path):
        """Test scrape command with SQLite backend (real API)."""
        from typer.testing import CliRunner
        from main import app

        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "scrape",
                "--source", "reddit",
                "--limit", "2",
                "--storage", "sqlite",
                "--db-path", e2e_db_path,
            ],
        )

        assert result.exit_code == 0
        assert "Scraping Reddit" in result.stdout
        assert "Total scraped" in result.stdout

        # Verify data was stored
        storage = SQLiteStorage(db_path=e2e_db_path)
        stats = storage.get_stats()
        assert stats["raw_data_points"] >= 1


@pytest.mark.e2e
class TestStorageOperations:
    """E2E tests for storage operations."""

    def test_e2e_storage_roundtrip(self, sqlite_storage):
        """Test complete storage roundtrip."""
        from analysis.classifier import ClassifiedInsight, ProblemCategory

        # Create and store raw data
        datapoint = RawDataPoint(
            source=DataSource.REDDIT,
            source_id="roundtrip_test",
            url="https://example.com/test",
            title="Test Title",
            content="Test content for roundtrip verification",
            author="test_author",
            created_at=datetime.now(),
            metadata={"test_key": "test_value"},
        )
        raw_id = sqlite_storage.save_raw_datapoint(datapoint)
        assert raw_id

        # Create and store insight
        insight = ClassifiedInsight(
            source_id="roundtrip_test",
            source_url="https://example.com/test",
            problem_statement="Test problem statement",
            category=ProblemCategory.ANALYTICS,
            secondary_categories=[ProblemCategory.PRICING],
            frustration_level=4,
            clarity_score=5,
            willingness_to_pay=True,
            wtp_quotes=["I'd pay $50/month"],
            current_workaround="Manual tracking",
            keywords=["analytics", "tracking"],
            original_title="Test Title",
            content_snippet="Test content",
        )
        insight_id = sqlite_storage.save_insight(insight, raw_record_id=raw_id)
        assert insight_id

        # Create and store cluster
        cluster_id = sqlite_storage.save_cluster(
            name="Test Cluster",
            description="Test cluster description",
            category=ProblemCategory.ANALYTICS,
            insight_ids=[insight_id],
            frequency=10,
        )
        assert cluster_id

        # Create and store opportunity score
        score_id = sqlite_storage.save_opportunity_score(
            cluster_id=cluster_id,
            cluster_name="Test Cluster",
            frequency_score=80.0,
            intensity_score=75.0,
            wtp_score=90.0,
            competition_gap_score=85.0,
            total_score=82.5,
            notes="Test notes",
        )
        assert score_id

        # Verify all data
        stats = sqlite_storage.get_stats()
        assert stats["raw_data_points"] == 1
        assert stats["classified_insights"] == 1
        assert stats["problem_clusters"] == 1
        assert stats["scored_opportunities"] == 1

        # Verify retrieval
        all_insights = sqlite_storage.get_all_insights()
        assert len(all_insights) == 1
        assert all_insights[0]["source_id"] == "roundtrip_test"

        clusters = sqlite_storage.get_clusters()
        assert len(clusters) == 1
        assert clusters[0]["name"] == "Test Cluster"

        opportunities = sqlite_storage.get_ranked_opportunities()
        assert len(opportunities) == 1
        assert opportunities[0]["total_score"] == 82.5
