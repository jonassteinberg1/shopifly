"""Integration tests for Reddit Selenium/RSS scraper.

These tests verify the scraper integrates correctly with the storage layer
and other components, using mocked HTTP responses.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from scrapers.reddit_selenium import (
    RedditSeleniumScraper,
    scrape_reddit_posts,
)
from scrapers.base import DataSource, RawDataPoint
from storage.sqlite import SQLiteStorage


# Sample RSS XML for integration testing
SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Shopify</title>
    <entry>
        <author><name>/u/integration_user</name></author>
        <title>Integration Test Post - Shopify Problem</title>
        <link href="https://www.reddit.com/r/shopify/comments/int123/integration_test/"/>
        <content type="html">&lt;p&gt;This is a test post about Shopify problems for integration testing.&lt;/p&gt;</content>
        <updated>2026-01-08T10:00:00+00:00</updated>
    </entry>
    <entry>
        <author><name>/u/another_int_user</name></author>
        <title>Another Integration Test - Need Help</title>
        <link href="https://www.reddit.com/r/shopify/comments/int456/another_test/"/>
        <content type="html">&lt;p&gt;I need help with my store. Very frustrated!&lt;/p&gt;</content>
        <updated>2026-01-07T09:00:00+00:00</updated>
    </entry>
</feed>
"""

SAMPLE_COMMENTS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <author><name>/u/integration_user</name></author>
        <title>Integration Test Post</title>
        <link href="https://www.reddit.com/r/shopify/comments/int123/integration_test/"/>
        <content type="html">&lt;p&gt;Original post&lt;/p&gt;</content>
        <updated>2026-01-08T10:00:00+00:00</updated>
    </entry>
    <entry>
        <author><name>/u/helper</name></author>
        <title>Re: Integration Test Post</title>
        <link href="https://www.reddit.com/r/shopify/comments/int123/integration_test/c1/"/>
        <content type="html">&lt;p&gt;Here is some helpful advice.&lt;/p&gt;</content>
        <updated>2026-01-08T11:00:00+00:00</updated>
    </entry>
</feed>
"""


class TestScraperStorageIntegration:
    """Tests for scraper integration with SQLite storage."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a temporary SQLite storage."""
        db_path = tmp_path / "integration_test.db"
        return SQLiteStorage(db_path=str(db_path))

    @patch("scrapers.reddit_selenium.requests.Session")
    def test_scraped_posts_can_be_stored(self, mock_client_class, storage):
        """Test that scraped posts can be saved to storage."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        # Scrape posts
        posts = scrape_reddit_posts(
            limit=2,
            sort_types=["hot"],
            include_comments=False,
            request_delay=0.01
        )

        # Convert to RawDataPoint and store
        for post in posts:
            datapoint = RawDataPoint(
                source=DataSource.REDDIT,
                source_id=f"reddit_post_{post['id']}",
                url=post["url"],
                title=post["title"],
                content=post["selftext"] or "[No body text]",
                author=post["author"],
                created_at=datetime.utcnow(),
                metadata={
                    "subreddit": "shopify",
                    "type": "post",
                    "scrape_method": "rss",
                },
            )
            record_id = storage.save_raw_datapoint(datapoint)
            assert record_id is not None

        # Verify storage
        stats = storage.get_stats()
        assert stats["raw_data_points"] == 2

    @patch("scrapers.reddit_selenium.requests.Session")
    def test_duplicate_posts_not_stored_twice(self, mock_client_class, storage):
        """Test that duplicate posts are handled correctly."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        # Scrape and store twice
        for _ in range(2):
            posts = scrape_reddit_posts(
                limit=2,
                sort_types=["hot"],
                include_comments=False,
                request_delay=0.01
            )

            for post in posts:
                datapoint = RawDataPoint(
                    source=DataSource.REDDIT,
                    source_id=f"reddit_post_{post['id']}",
                    url=post["url"],
                    title=post["title"],
                    content=post["selftext"] or "[No body text]",
                    author=post["author"],
                    created_at=datetime.utcnow(),
                    metadata={"subreddit": "shopify", "type": "post"},
                )
                # save_raw_datapoint should handle duplicates
                storage.save_raw_datapoint(datapoint)

        # Should still only have 2 unique posts
        stats = storage.get_stats()
        assert stats["raw_data_points"] == 2

    @patch("scrapers.reddit_selenium.requests.Session")
    def test_posts_with_comments_stored_correctly(self, mock_client_class, storage):
        """Test that posts with comments are stored with metadata."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # First call returns posts, second returns comments
        mock_response_posts = MagicMock()
        mock_response_posts.status_code = 200
        mock_response_posts.text = SAMPLE_RSS_XML

        mock_response_comments = MagicMock()
        mock_response_comments.status_code = 200
        mock_response_comments.text = SAMPLE_COMMENTS_RSS

        mock_client.get.side_effect = [
            mock_response_posts,
            mock_response_comments,
            mock_response_comments
        ]

        # Scrape with comments
        posts = scrape_reddit_posts(
            limit=2,
            sort_types=["hot"],
            include_comments=True,
            request_delay=0.01
        )

        # Store with comment count in metadata
        for post in posts:
            datapoint = RawDataPoint(
                source=DataSource.REDDIT,
                source_id=f"reddit_post_{post['id']}",
                url=post["url"],
                title=post["title"],
                content=post["selftext"] or "[No body text]",
                author=post["author"],
                created_at=datetime.utcnow(),
                metadata={
                    "subreddit": "shopify",
                    "type": "post",
                    "comment_count": len(post.get("comments", [])),
                },
            )
            storage.save_raw_datapoint(datapoint)

        # Verify
        stats = storage.get_stats()
        assert stats["raw_data_points"] == 2


class TestScraperClassIntegration:
    """Tests for RedditSeleniumScraper class integration."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a temporary SQLite storage."""
        db_path = tmp_path / "scraper_class_test.db"
        return SQLiteStorage(db_path=str(db_path))

    @patch("scrapers.reddit_selenium.requests.Session")
    @pytest.mark.asyncio
    async def test_scraper_class_scrape_method(self, mock_client_class, storage):
        """Test the async scrape method of RedditSeleniumScraper."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        scraper = RedditSeleniumScraper(request_delay=0.01)

        count = 0
        async for datapoint in scraper.scrape(limit=2):
            assert isinstance(datapoint, RawDataPoint)
            assert datapoint.source == DataSource.REDDIT

            # Store the datapoint
            record_id = storage.save_raw_datapoint(datapoint)
            assert record_id is not None
            count += 1

        assert count > 0
        stats = storage.get_stats()
        assert stats["raw_data_points"] == count

    @patch("scrapers.reddit_selenium.requests.Session")
    @pytest.mark.asyncio
    async def test_scraper_health_check(self, mock_client_class):
        """Test the health check method."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        scraper = RedditSeleniumScraper()
        healthy = await scraper.health_check()

        # Should be healthy with valid RSS response containing <feed
        assert healthy is True

    @patch("scrapers.reddit_selenium.requests.Session")
    @pytest.mark.asyncio
    async def test_scraper_health_check_failure(self, mock_client_class):
        """Test health check when Reddit is down."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        mock_client.get.return_value = mock_response

        scraper = RedditSeleniumScraper()
        healthy = await scraper.health_check()

        assert healthy is False


class TestMultipleSortTypesIntegration:
    """Tests for scraping from multiple sort types."""

    @patch("scrapers.reddit_selenium.requests.Session")
    def test_all_sort_types_queried(self, mock_client_class):
        """Test that all specified sort types are queried."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        sort_types = ["hot", "new", "top_week", "rising"]

        scrape_reddit_posts(
            limit=100,
            sort_types=sort_types,
            include_comments=False,
            request_delay=0.01
        )

        # Should have made at least one call per sort type
        assert mock_client.get.call_count >= len(sort_types)

    @patch("scrapers.reddit_selenium.requests.Session")
    def test_stops_early_when_limit_reached(self, mock_client_class):
        """Test that scraping stops when limit is reached."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        # Limit of 1, should stop after first unique post
        posts = scrape_reddit_posts(
            limit=1,
            sort_types=["hot", "new", "top_week", "rising"],
            include_comments=False,
            request_delay=0.01
        )

        assert len(posts) == 1


class TestCommentsIntegration:
    """Tests for comments scraping integration."""

    @patch("scrapers.reddit_selenium.requests.Session")
    def test_comments_fetched_for_each_post(self, mock_client_class):
        """Test that comments are fetched for each post."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response_posts = MagicMock()
        mock_response_posts.status_code = 200
        mock_response_posts.text = SAMPLE_RSS_XML

        mock_response_comments = MagicMock()
        mock_response_comments.status_code = 200
        mock_response_comments.text = SAMPLE_COMMENTS_RSS

        # Posts first, then comments for each post
        mock_client.get.side_effect = [
            mock_response_posts,
            mock_response_comments,
            mock_response_comments,
        ]

        posts = scrape_reddit_posts(
            limit=2,
            sort_types=["hot"],
            include_comments=True,
            request_delay=0.01
        )

        # Should have comments for each post
        for post in posts:
            assert "comments" in post
            assert isinstance(post["comments"], list)

    @patch("scrapers.reddit_selenium.requests.Session")
    def test_handles_comment_fetch_failure(self, mock_client_class):
        """Test graceful handling of comment fetch failures."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response_posts = MagicMock()
        mock_response_posts.status_code = 200
        mock_response_posts.text = SAMPLE_RSS_XML

        mock_response_comments_fail = MagicMock()
        mock_response_comments_fail.status_code = 429  # Rate limited

        mock_client.get.side_effect = [
            mock_response_posts,
            mock_response_comments_fail,
            mock_response_comments_fail,
        ]

        # Should not crash, just have empty comments
        posts = scrape_reddit_posts(
            limit=2,
            sort_types=["hot"],
            include_comments=True,
            request_delay=0.01
        )

        assert len(posts) == 2
        for post in posts:
            assert post["comments"] == []
