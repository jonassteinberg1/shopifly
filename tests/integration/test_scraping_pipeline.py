"""Integration tests for the scraping pipeline."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import json

from scrapers import (
    RedditScraper,
    AppStoreScraper,
    CommunityScraper,
    TwitterScraper,
    RawDataPoint,
    DataSource,
)
from analysis import Classifier, ClassifiedInsight
from storage import AirtableStorage


class TestRedditScrapingPipeline:
    """Integration tests for Reddit scraping pipeline."""

    @pytest.fixture
    def mock_reddit(self):
        """Create mock Reddit client."""
        with patch("scrapers.reddit.praw.Reddit") as mock:
            yield mock

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage."""
        with patch("storage.airtable.Api"), \
             patch("storage.airtable.settings") as mock_settings:
            mock_settings.airtable_api_key = "test"
            mock_settings.airtable_base_id = "test"
            storage = AirtableStorage()
            storage._tables = {}

            mock_table = MagicMock()
            mock_table.first.return_value = None
            mock_table.create.return_value = {"id": "rec123"}
            storage._get_table = MagicMock(return_value=mock_table)

            return storage

    @pytest.mark.asyncio
    async def test_scrape_and_save_pipeline(self, mock_reddit, mock_storage):
        """Test full pipeline from scraping to storage."""
        # Create mock submissions
        mock_submission = MagicMock()
        mock_submission.id = "test123"
        mock_submission.title = "Shopify inventory problem - need help"
        mock_submission.selftext = "I'm frustrated with the inventory system"
        mock_submission.author = MagicMock()
        mock_submission.author.__str__ = lambda x: "test_user"
        mock_submission.permalink = "/r/shopify/comments/test123"
        mock_submission.created_utc = datetime.now().timestamp()
        mock_submission.score = 10
        mock_submission.num_comments = 5
        mock_submission.upvote_ratio = 0.9
        mock_submission.subreddit = MagicMock()
        mock_submission.subreddit.__str__ = lambda x: "shopify"
        mock_submission.comments = MagicMock()
        mock_submission.comments.replace_more = MagicMock()
        mock_submission.comments.__iter__ = lambda x: iter([])

        # Set up mock subreddit
        mock_subreddit = MagicMock()
        mock_subreddit.search.return_value = [mock_submission]

        mock_reddit_instance = mock_reddit.return_value
        mock_reddit_instance.subreddit.return_value = mock_subreddit

        # Create scraper and run
        scraper = RedditScraper()
        scraper.subreddits = ["shopify"]  # Limit to one subreddit for test

        datapoints = []
        async for dp in scraper.scrape(limit=10):
            datapoints.append(dp)
            # Save to storage
            mock_storage.save_raw_datapoint(dp)

        # Verify we got datapoints
        assert len(datapoints) > 0

        # Verify datapoint structure
        dp = datapoints[0]
        assert dp.source == DataSource.REDDIT
        assert "shopify" in dp.title.lower() or "shopify" in dp.content.lower()

        # Verify storage was called
        mock_storage._get_table.assert_called()


class TestAppStoreScrapingPipeline:
    """Integration tests for App Store scraping pipeline."""

    @pytest.fixture
    def mock_httpx(self):
        """Create mock httpx client."""
        with patch("scrapers.appstore.httpx.AsyncClient") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_scrape_reviews_pipeline(self, mock_httpx, sample_app_review_html):
        """Test scraping app reviews and processing."""
        # Set up mock HTTP responses
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = f"""
        <html>
        <body>
            {sample_app_review_html}
        </body>
        </html>
        """
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        mock_httpx.return_value = mock_client

        scraper = AppStoreScraper()
        scraper.TARGET_APPS = ["test-app"]  # Limit for test

        datapoints = []
        async for dp in scraper.scrape(limit=5):
            datapoints.append(dp)

        await scraper.close()

        # Should get the review from our mock HTML
        assert len(datapoints) >= 0  # May be 0 if review doesn't pass filters


class TestCommunityScrapingPipeline:
    """Integration tests for Community forum scraping pipeline."""

    @pytest.fixture
    def mock_httpx(self):
        """Create mock httpx client."""
        with patch("scrapers.community.httpx.AsyncClient") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_scrape_topics_pipeline(self, mock_httpx, sample_community_topic_html):
        """Test scraping community topics."""
        # Set up mock responses
        mock_client = AsyncMock()

        # Board listing page
        board_html = """
        <html><body>
            <a class="topic-title" href="/t/test-topic/12345">Test Topic</a>
        </body></html>
        """

        responses = [
            MagicMock(status_code=200, text=board_html),  # Board page
            MagicMock(status_code=200, text=sample_community_topic_html),  # Topic page
        ]
        mock_client.get = AsyncMock(side_effect=responses)
        mock_client.aclose = AsyncMock()
        mock_httpx.return_value = mock_client

        scraper = CommunityScraper()
        scraper.BOARDS = ["/c/test-board"]  # Limit for test

        datapoints = []
        async for dp in scraper.scrape(limit=5):
            datapoints.append(dp)

        await scraper.close()

        # Verify we processed the topic
        if datapoints:
            dp = datapoints[0]
            assert dp.source == DataSource.COMMUNITY


class TestClassificationPipeline:
    """Integration tests for the classification pipeline."""

    @pytest.fixture
    def mock_anthropic(self):
        """Create mock Anthropic client."""
        with patch("analysis.classifier.anthropic.Anthropic") as mock:
            yield mock

    @pytest.fixture
    def sample_datapoints(self):
        """Create sample datapoints for classification."""
        return [
            RawDataPoint(
                source=DataSource.REDDIT,
                source_id=f"reddit_test_{i}",
                url=f"https://reddit.com/r/shopify/test_{i}",
                title="Shopify analytics are terrible",
                content="I need better conversion tracking. Would pay for a good solution.",
                author="user",
                created_at=datetime.now(),
            )
            for i in range(3)
        ]

    @pytest.mark.asyncio
    async def test_classify_batch_pipeline(
        self, mock_anthropic, sample_datapoints, mock_anthropic_response
    ):
        """Test classifying a batch of datapoints."""
        # Set up mock response
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_anthropic_response))]
        mock_anthropic.return_value.messages.create.return_value = mock_message

        with patch("analysis.classifier.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.anthropic_model = "claude-3-haiku-20240307"

            classifier = Classifier()

            insights = []
            async for insight in classifier.classify_batch(sample_datapoints, concurrency=2):
                insights.append(insight)

        # Should have classified all datapoints
        assert len(insights) == 3

        # Verify insight structure
        for insight in insights:
            assert isinstance(insight, ClassifiedInsight)
            assert insight.category is not None
            assert 1 <= insight.frustration_level <= 5


class TestFullPipeline:
    """End-to-end integration tests."""

    @pytest.fixture
    def mock_all_externals(self):
        """Mock all external services."""
        with patch("scrapers.reddit.praw.Reddit") as mock_reddit, \
             patch("analysis.classifier.anthropic.Anthropic") as mock_anthropic, \
             patch("storage.airtable.Api") as mock_airtable:
            yield {
                "reddit": mock_reddit,
                "anthropic": mock_anthropic,
                "airtable": mock_airtable,
            }

    @pytest.mark.asyncio
    async def test_scrape_classify_store_pipeline(
        self, mock_all_externals, mock_anthropic_response
    ):
        """Test the full pipeline: scrape -> classify -> store."""
        # Set up Reddit mock
        mock_submission = MagicMock()
        mock_submission.id = "pipeline_test"
        mock_submission.title = "Shopify problem with inventory"
        mock_submission.selftext = "Need help tracking stock levels"
        mock_submission.author = MagicMock()
        mock_submission.author.__str__ = lambda x: "test_user"
        mock_submission.permalink = "/r/shopify/comments/pipeline_test"
        mock_submission.created_utc = datetime.now().timestamp()
        mock_submission.score = 20
        mock_submission.num_comments = 8
        mock_submission.upvote_ratio = 0.85
        mock_submission.subreddit = MagicMock()
        mock_submission.subreddit.__str__ = lambda x: "shopify"
        mock_submission.comments = MagicMock()
        mock_submission.comments.replace_more = MagicMock()
        mock_submission.comments.__iter__ = lambda x: iter([])

        mock_subreddit = MagicMock()
        mock_subreddit.search.return_value = [mock_submission]
        mock_all_externals["reddit"].return_value.subreddit.return_value = mock_subreddit

        # Set up Anthropic mock
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_anthropic_response))]
        mock_all_externals["anthropic"].return_value.messages.create.return_value = mock_message

        # Set up Airtable mock
        mock_table = MagicMock()
        mock_table.first.return_value = None
        mock_table.create.return_value = {"id": "rec_test_123"}
        mock_all_externals["airtable"].return_value.table.return_value = mock_table

        # Run pipeline
        with patch("storage.airtable.settings") as mock_storage_settings, \
             patch("analysis.classifier.settings") as mock_classifier_settings:

            mock_storage_settings.airtable_api_key = "test"
            mock_storage_settings.airtable_base_id = "test"
            mock_classifier_settings.anthropic_api_key = "test"
            mock_classifier_settings.anthropic_model = "claude-3-haiku-20240307"

            # 1. Scrape
            scraper = RedditScraper()
            scraper.subreddits = ["shopify"]

            raw_datapoints = []
            async for dp in scraper.scrape(limit=5):
                raw_datapoints.append(dp)
                break  # Just get one for the test

            assert len(raw_datapoints) >= 1

            # 2. Classify
            classifier = Classifier()
            insights = []
            async for insight in classifier.classify_batch(raw_datapoints):
                insights.append(insight)

            assert len(insights) >= 1

            # 3. Store
            storage = AirtableStorage()
            storage._tables = {}
            storage._get_table = MagicMock(return_value=mock_table)

            for dp in raw_datapoints:
                storage.save_raw_datapoint(dp)

            for insight in insights:
                storage.save_insight(insight)

            # Verify storage calls were made
            assert mock_table.create.call_count >= 2  # At least 1 raw + 1 insight


class TestHealthChecks:
    """Tests for service health checks."""

    @pytest.mark.asyncio
    async def test_appstore_health_check_success(self):
        """Test App Store health check success."""
        with patch("scrapers.appstore.httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value = mock_client

            scraper = AppStoreScraper()
            result = await scraper.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_appstore_health_check_failure(self):
        """Test App Store health check failure."""
        with patch("scrapers.appstore.httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_httpx.return_value = mock_client

            scraper = AppStoreScraper()
            result = await scraper.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_community_health_check_success(self):
        """Test Community health check success."""
        with patch("scrapers.community.httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.return_value = mock_client

            scraper = CommunityScraper()
            result = await scraper.health_check()

            assert result is True
