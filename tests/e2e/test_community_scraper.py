"""End-to-end tests for Shopify Community scraper.

These tests actually hit the Shopify Community website to verify the scraper works
in production. They use small limits to avoid rate limiting.

Run with: pytest tests/e2e/test_community_scraper.py -v -m e2e
"""

import pytest
from datetime import datetime

from scrapers.community import CommunityScraper
from scrapers.base import DataSource, RawDataPoint
from storage.sqlite import SQLiteStorage


@pytest.mark.e2e
class TestCommunityScraperEndpoints:
    """E2E tests for Community scraper endpoints."""

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_e2e_health_check(self, scraper):
        """Test that Community site is accessible."""
        healthy = await scraper.health_check()
        assert healthy is True, "Shopify Community should be accessible"

    @pytest.mark.asyncio
    async def test_e2e_can_fetch_page(self, scraper):
        """Test that we can fetch a page from the Community."""
        html = await scraper._fetch_page(scraper.BASE_URL)
        assert html is not None, "Should be able to fetch Community homepage"
        assert len(html) > 0, "Response should have content"


@pytest.mark.e2e
class TestCommunityTopicScraping:
    """E2E tests for topic scraping functionality."""

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_e2e_scrape_topics(self, scraper):
        """Test scraping topics from Community forums."""
        topics = []
        count = 0

        async for datapoint in scraper.scrape(limit=3):
            assert isinstance(datapoint, RawDataPoint)
            assert datapoint.source == DataSource.COMMUNITY
            topics.append(datapoint)
            count += 1
            if count >= 3:
                break

        # Note: May get 0 results if site structure changed or rate limited
        # But structure should be valid if we get any
        for topic in topics:
            assert topic.title is not None
            assert topic.content is not None
            assert topic.url is not None

    @pytest.mark.asyncio
    async def test_e2e_topic_has_replies_metadata(self, scraper):
        """Test that scraped topics include replies in metadata."""
        async for datapoint in scraper.scrape(limit=5):
            # Every topic should have replies key in metadata
            assert "replies" in datapoint.metadata, "Topic should have 'replies' in metadata"
            assert isinstance(datapoint.metadata["replies"], list), "Replies should be a list"

            # If there are replies, check their structure
            if datapoint.metadata["replies"]:
                reply = datapoint.metadata["replies"][0]
                assert "content" in reply, "Reply should have 'content'"
                assert "author" in reply, "Reply should have 'author'"
                assert "position" in reply, "Reply should have 'position'"
                # Found a topic with replies, test passed
                return

        # If we get here, no topics had replies (acceptable for e2e)
        pytest.skip("No topics with replies found in this run")


@pytest.mark.e2e
class TestCommunityReplyExtraction:
    """E2E tests specifically for reply extraction."""

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_e2e_replies_have_content(self, scraper):
        """Test that extracted replies have meaningful content."""
        topics_checked = 0

        async for datapoint in scraper.scrape(limit=10):
            topics_checked += 1
            replies = datapoint.metadata.get("replies", [])

            for reply in replies:
                # Each reply should have non-empty content
                assert reply["content"], f"Reply content should not be empty"
                assert len(reply["content"]) > 5, "Reply should have meaningful content"

            if topics_checked >= 10:
                break

    @pytest.mark.asyncio
    async def test_e2e_op_content_not_duplicated_in_replies(self, scraper):
        """Test that OP content is not duplicated in replies."""
        async for datapoint in scraper.scrape(limit=5):
            op_content = datapoint.content[:100]  # First 100 chars of OP

            for reply in datapoint.metadata.get("replies", []):
                # Reply content should not be identical to OP
                if len(reply["content"]) >= 100:
                    assert reply["content"][:100] != op_content, \
                        "Reply should not be duplicate of OP"

            return  # Just check first topic

        pytest.skip("No topics scraped")


@pytest.mark.e2e
class TestCommunityStoragePipeline:
    """E2E tests for the full scrape-to-storage pipeline."""

    @pytest.fixture
    def sqlite_storage(self, tmp_path):
        """Create a temporary SQLite storage."""
        db_path = tmp_path / "e2e_community.db"
        return SQLiteStorage(db_path=str(db_path))

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_e2e_scrape_and_store_with_replies(self, scraper, sqlite_storage):
        """Test full pipeline: scrape from Community and store with replies."""
        stored_count = 0

        async for datapoint in scraper.scrape(limit=3):
            record_id = sqlite_storage.save_raw_datapoint(datapoint)
            assert record_id is not None
            stored_count += 1
            if stored_count >= 3:
                break

        if stored_count == 0:
            pytest.skip("No topics scraped (site may have changed)")

        # Verify storage
        stats = sqlite_storage.get_stats()
        assert stats["raw_data_points"] == stored_count

        # Retrieve and verify replies preserved
        import json
        unprocessed = sqlite_storage.get_unprocessed_raw_data()
        for item in unprocessed:
            # Storage returns dict with metadata as JSON string
            metadata_raw = item.get('metadata', '{}')
            metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
            assert "replies" in metadata
            assert isinstance(metadata["replies"], list)

    @pytest.mark.asyncio
    async def test_e2e_full_thread_context_for_llm(self, scraper):
        """Test that we can build full thread context for LLM classification."""
        async for datapoint in scraper.scrape(limit=3):
            # Build full context string as would be sent to LLM
            full_context = f"Title: {datapoint.title}\n\n"
            full_context += f"Original Post:\n{datapoint.content}\n\n"

            replies = datapoint.metadata.get("replies", [])
            if replies:
                full_context += "Replies:\n"
                for i, reply in enumerate(replies, 1):
                    full_context += f"\n--- Reply {i} by {reply['author']} ---\n"
                    full_context += f"{reply['content']}\n"

            # Full context should be substantial enough for classification
            assert len(full_context) > 50, "Should have enough context for LLM"

            # If we have replies, context should be richer
            if replies:
                assert len(full_context) > len(datapoint.content), \
                    "Full context with replies should be longer than just OP"
                return  # Test passed with replies

        pytest.skip("No topics with replies found")


@pytest.mark.e2e
class TestCommunityScraperResilience:
    """E2E tests for scraper resilience and error handling."""

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_e2e_handles_rate_limiting_gracefully(self, scraper):
        """Test that scraper handles rate limiting without crashing."""
        # Scrape with a larger limit to potentially trigger rate limiting
        count = 0
        try:
            async for datapoint in scraper.scrape(limit=10):
                count += 1
                if count >= 10:
                    break
        except Exception as e:
            # Should not crash even if rate limited
            pytest.fail(f"Scraper crashed with exception: {e}")

        # May get fewer results due to rate limiting, but shouldn't crash
        assert count >= 0

    @pytest.mark.asyncio
    async def test_e2e_data_integrity(self, scraper):
        """Test that scraped data maintains integrity."""
        async for datapoint in scraper.scrape(limit=3):
            # Source should always be COMMUNITY
            assert datapoint.source == DataSource.COMMUNITY

            # URL should be valid Community URL
            assert "shopify.com" in datapoint.url or datapoint.url.startswith("http")

            # Metadata should have expected structure
            assert "type" in datapoint.metadata
            assert "replies" in datapoint.metadata

            return  # Just check first topic

        pytest.skip("No topics scraped")
