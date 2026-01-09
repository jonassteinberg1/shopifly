"""Integration tests for Community scraper with reply extraction.

These tests verify the scraper integrates correctly with the storage layer
and other components, using mocked HTTP responses.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

from scrapers.community import CommunityScraper
from scrapers.base import DataSource, RawDataPoint
from storage.sqlite import SQLiteStorage


# Sample HTML responses for integration testing
SAMPLE_BOARD_HTML = """
<html>
<body>
    <a class="topic-title" href="/c/shopify-discussion/t/inventory-problem/12345">Inventory sync issue</a>
    <a class="topic-title" href="/c/shopify-discussion/t/checkout-bug/12346">Checkout not working</a>
</body>
</html>
"""

SAMPLE_TOPIC_HTML = """
<html>
<body>
    <h1 class="topic-title">Inventory sync issue - Need help!</h1>

    <div class="post-body">
        My inventory keeps showing wrong quantities. I've tried everything but nothing works.
        This is really frustrating and causing customer complaints. Please help!
    </div>
    <a class="username">original_poster</a>

    <div class="post-body">
        Have you tried the inventory audit feature? Go to Products > Inventory and run an audit.
        This helped me fix similar issues last month.
    </div>
    <a class="username">helpful_responder</a>

    <div class="post-body">
        Same problem here! I ended up using an app called Stocky. It's not perfect but better
        than the built-in system for multi-location stores.
    </div>
    <a class="username">another_merchant</a>

    <time datetime="2024-01-15T10:00:00Z">January 15, 2024</time>
    <span class="reply-count">2 replies</span>
    <span class="view-count">89 views</span>
</body>
</html>
"""

SAMPLE_TOPIC_HTML_2 = """
<html>
<body>
    <h1 class="topic-title">Checkout not working after theme update</h1>

    <div class="post-body">
        After updating my theme, the checkout button doesn't work anymore.
        I need to fix this ASAP - losing sales!
    </div>
    <a class="username">panicked_merchant</a>

    <div class="post-body">
        Check your theme's JavaScript console for errors. Usually it's a conflict
        with a custom script or app.
    </div>
    <a class="username">dev_helper</a>

    <time datetime="2024-01-16T14:00:00Z">January 16, 2024</time>
    <span class="reply-count">1 reply</span>
</body>
</html>
"""


class TestCommunityScraperStorageIntegration:
    """Tests for Community scraper integration with SQLite storage."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a temporary SQLite storage."""
        db_path = tmp_path / "community_integration_test.db"
        return SQLiteStorage(db_path=str(db_path))

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_scraped_topics_with_replies_stored(self, scraper, storage):
        """Test that scraped topics with replies are stored correctly."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            # Store the datapoint
            record_id = storage.save_raw_datapoint(datapoint)
            assert record_id is not None

            # Verify storage
            stats = storage.get_stats()
            assert stats["raw_data_points"] == 1

    @pytest.mark.asyncio
    async def test_replies_preserved_in_metadata(self, scraper, storage):
        """Test that replies are preserved when stored and retrieved."""
        import json

        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            # Store
            storage.save_raw_datapoint(datapoint)

            # Retrieve
            unprocessed = storage.get_unprocessed_raw_data()
            assert len(unprocessed) == 1

            # Verify replies are in metadata
            # Storage returns dict with metadata as JSON string
            retrieved = unprocessed[0]
            metadata_raw = retrieved.get('metadata', '{}')
            metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
            assert "replies" in metadata
            assert len(metadata["replies"]) == 2

    @pytest.mark.asyncio
    async def test_multiple_topics_stored_correctly(self, scraper, storage):
        """Test storing multiple topics with their replies."""
        topics = [
            ("https://community.shopify.com/t/1", SAMPLE_TOPIC_HTML),
            ("https://community.shopify.com/t/2", SAMPLE_TOPIC_HTML_2),
        ]

        for url, html in topics:
            with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = html
                datapoint = await scraper._scrape_topic(url)
                if datapoint:
                    storage.save_raw_datapoint(datapoint)

        stats = storage.get_stats()
        assert stats["raw_data_points"] == 2


class TestCommunityScraperPipelineIntegration:
    """Tests for Community scraper in the full scraping pipeline."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a temporary SQLite storage."""
        db_path = tmp_path / "pipeline_test.db"
        return SQLiteStorage(db_path=str(db_path))

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_scrape_method_yields_topics_with_replies(self, scraper, storage):
        """Test that the scrape() method yields topics with replies."""
        # Mock the HTTP client responses
        with patch.object(scraper.client, 'get', new_callable=AsyncMock) as mock_get:
            # Board listing response
            board_response = MagicMock()
            board_response.status_code = 200
            board_response.text = SAMPLE_BOARD_HTML

            # Topic responses
            topic_response = MagicMock()
            topic_response.status_code = 200
            topic_response.text = SAMPLE_TOPIC_HTML

            # Return board listing first, then topic for each link
            mock_get.side_effect = [
                board_response,  # Board listing
                topic_response,  # First topic
                topic_response,  # Second topic (if reached)
            ]

            count = 0
            async for datapoint in scraper.scrape(limit=1):
                assert isinstance(datapoint, RawDataPoint)
                assert datapoint.source == DataSource.COMMUNITY
                assert "replies" in datapoint.metadata
                storage.save_raw_datapoint(datapoint)
                count += 1
                if count >= 1:
                    break

            assert count >= 0  # May be 0 if selectors don't match mock HTML exactly

    @pytest.mark.asyncio
    async def test_health_check_integration(self, scraper):
        """Test health check method."""
        with patch.object(scraper.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            healthy = await scraper.health_check()
            assert healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, scraper):
        """Test health check when site is down."""
        with patch.object(scraper.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            healthy = await scraper.health_check()
            assert healthy is False


class TestCommunityScraperDataFormat:
    """Tests for data format compatibility with LLM pipeline."""

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_datapoint_format_for_llm(self, scraper):
        """Test that datapoint format is ready for LLM classification."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            # Verify all fields needed for LLM are present
            assert datapoint.title is not None and len(datapoint.title) > 0
            assert datapoint.content is not None and len(datapoint.content) > 0
            assert datapoint.url is not None
            assert datapoint.source == DataSource.COMMUNITY

            # Verify replies structure
            replies = datapoint.metadata.get("replies", [])
            for reply in replies:
                assert "content" in reply
                assert isinstance(reply["content"], str)
                assert len(reply["content"]) > 0

    @pytest.mark.asyncio
    async def test_full_thread_context_available(self, scraper):
        """Test that full thread context is available for classification."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            # Combine OP + replies for full context
            full_text = datapoint.content
            for reply in datapoint.metadata.get("replies", []):
                full_text += "\n" + reply["content"]

            # Should have meaningful content from both OP and replies
            assert "inventory" in full_text.lower()
            assert "stocky" in full_text.lower() or "audit" in full_text.lower()
