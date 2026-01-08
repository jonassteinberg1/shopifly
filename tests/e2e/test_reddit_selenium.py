"""End-to-end tests for Reddit Selenium/RSS scraper.

These tests actually hit Reddit's RSS endpoints to verify the scraper works
in production. They use small limits to avoid rate limiting.

Run with: pytest tests/e2e/test_reddit_selenium.py -v -m e2e
"""

import pytest
from datetime import datetime

from scrapers.reddit_selenium import (
    RedditSeleniumScraper,
    scrape_reddit_posts,
    RSS_ENDPOINTS,
)
from scrapers.base import DataSource, RawDataPoint
from storage.sqlite import SQLiteStorage


@pytest.mark.e2e
class TestRedditRSSEndpoints:
    """E2E tests for Reddit RSS endpoints."""

    def test_e2e_hot_rss_endpoint(self):
        """Test that hot RSS endpoint returns posts."""
        posts = scrape_reddit_posts(
            limit=3,
            sort_types=["hot"],
            include_comments=False,
            request_delay=2.0
        )

        assert len(posts) > 0, "Should get at least one post from hot RSS"
        for post in posts:
            assert post["title"], "Post should have a title"
            assert post["url"], "Post should have a URL"
            assert post["id"], "Post should have an ID"

    def test_e2e_new_rss_endpoint(self):
        """Test that new RSS endpoint returns posts."""
        posts = scrape_reddit_posts(
            limit=3,
            sort_types=["new"],
            include_comments=False,
            request_delay=2.0
        )

        assert len(posts) > 0, "Should get at least one post from new RSS"

    def test_e2e_top_week_rss_endpoint(self):
        """Test that top_week RSS endpoint returns posts."""
        posts = scrape_reddit_posts(
            limit=3,
            sort_types=["top_week"],
            include_comments=False,
            request_delay=2.0
        )

        assert len(posts) > 0, "Should get at least one post from top_week RSS"


@pytest.mark.e2e
class TestRedditPostScraping:
    """E2E tests for post scraping functionality."""

    def test_e2e_scrape_multiple_posts(self):
        """Test scraping multiple posts from Reddit."""
        posts = scrape_reddit_posts(
            limit=10,
            sort_types=["hot", "new"],
            include_comments=False,
            request_delay=2.0
        )

        assert len(posts) >= 5, "Should get at least 5 unique posts"

        # Verify post structure
        for post in posts:
            assert "title" in post
            assert "selftext" in post
            assert "id" in post
            assert "url" in post
            assert "author" in post
            assert "comments" in post

    def test_e2e_post_urls_are_valid(self):
        """Test that post URLs are valid Reddit URLs."""
        posts = scrape_reddit_posts(
            limit=3,
            sort_types=["hot"],
            include_comments=False,
            request_delay=2.0
        )

        for post in posts:
            assert "reddit.com" in post["url"]
            assert "/r/shopify/" in post["url"]
            assert "/comments/" in post["url"]

    def test_e2e_deduplication_works(self):
        """Test that posts are deduplicated across sort types."""
        posts = scrape_reddit_posts(
            limit=50,
            sort_types=["hot", "new", "top_week"],
            include_comments=False,
            request_delay=1.5
        )

        # Check for unique IDs
        ids = [post["id"] for post in posts]
        assert len(ids) == len(set(ids)), "All post IDs should be unique"


@pytest.mark.e2e
class TestRedditCommentScraping:
    """E2E tests for comment scraping functionality."""

    def test_e2e_scrape_posts_with_comments(self):
        """Test scraping posts with their comments."""
        posts = scrape_reddit_posts(
            limit=2,
            sort_types=["hot"],
            include_comments=True,
            request_delay=2.0
        )

        assert len(posts) > 0, "Should get at least one post"

        # At least one post should have comments (popular subreddit)
        total_comments = sum(len(post["comments"]) for post in posts)
        # Note: Some posts might have no comments, so we just check structure
        for post in posts:
            assert isinstance(post["comments"], list)

    def test_e2e_comment_structure(self):
        """Test that comments have the expected structure."""
        posts = scrape_reddit_posts(
            limit=3,
            sort_types=["top_week"],  # Top posts more likely to have comments
            include_comments=True,
            request_delay=2.0
        )

        # Find a post with comments
        posts_with_comments = [p for p in posts if p["comments"]]

        if posts_with_comments:
            post = posts_with_comments[0]
            comment = post["comments"][0]

            assert "author" in comment
            assert "content" in comment
            assert "url" in comment


@pytest.mark.e2e
class TestRedditSeleniumScraperClass:
    """E2E tests for RedditSeleniumScraper class."""

    @pytest.mark.asyncio
    async def test_e2e_scraper_health_check(self):
        """Test scraper health check against live Reddit."""
        scraper = RedditSeleniumScraper(request_delay=2.0)
        healthy = await scraper.health_check()
        assert healthy is True, "Scraper should be healthy (Reddit RSS accessible)"

    @pytest.mark.asyncio
    async def test_e2e_scraper_async_scrape(self):
        """Test async scrape method against live Reddit."""
        scraper = RedditSeleniumScraper(request_delay=2.0)

        posts = []
        async for datapoint in scraper.scrape(limit=3):
            assert isinstance(datapoint, RawDataPoint)
            assert datapoint.source == DataSource.REDDIT
            posts.append(datapoint)

        assert len(posts) > 0, "Should scrape at least one post"


@pytest.mark.e2e
class TestRedditStoragePipeline:
    """E2E tests for the full scrape-to-storage pipeline."""

    @pytest.fixture
    def sqlite_storage(self, tmp_path):
        """Create a temporary SQLite storage."""
        db_path = tmp_path / "e2e_reddit_selenium.db"
        return SQLiteStorage(db_path=str(db_path))

    def test_e2e_scrape_and_store_posts(self, sqlite_storage):
        """Test full pipeline: scrape from Reddit and store in SQLite."""
        # Scrape
        posts = scrape_reddit_posts(
            limit=5,
            sort_types=["hot", "new"],
            include_comments=False,
            request_delay=2.0
        )

        assert len(posts) > 0, "Should scrape some posts"

        # Store
        for post in posts:
            datapoint = RawDataPoint(
                source=DataSource.REDDIT,
                source_id=f"reddit_post_{post['id']}",
                url=post["url"],
                title=post["title"],
                content=post["selftext"] or "[No body text]",
                author=post["author"] or "[unknown]",
                created_at=datetime.utcnow(),
                metadata={
                    "subreddit": "shopify",
                    "type": "post",
                    "scrape_method": "rss",
                },
            )
            sqlite_storage.save_raw_datapoint(datapoint)

        # Verify
        stats = sqlite_storage.get_stats()
        assert stats["raw_data_points"] == len(posts)

        # Retrieve and verify
        unprocessed = sqlite_storage.get_unprocessed_raw_data()
        assert len(unprocessed) == len(posts)

    @pytest.mark.asyncio
    async def test_e2e_scraper_class_pipeline(self, sqlite_storage):
        """Test full pipeline using RedditSeleniumScraper class."""
        scraper = RedditSeleniumScraper(request_delay=2.0)

        # Health check
        healthy = await scraper.health_check()
        assert healthy, "Scraper should be healthy"

        # Scrape and store
        count = 0
        async for datapoint in scraper.scrape(limit=3):
            record_id = sqlite_storage.save_raw_datapoint(datapoint)
            assert record_id is not None
            count += 1

        assert count > 0, "Should have scraped and stored at least one post"

        # Verify storage
        stats = sqlite_storage.get_stats()
        assert stats["raw_data_points"] == count


@pytest.mark.e2e
class TestRedditLargeScaleScraping:
    """E2E tests for larger scale scraping (100+ posts)."""

    def test_e2e_scrape_100_posts(self):
        """Test scraping 100 posts from multiple sort types."""
        posts = scrape_reddit_posts(
            limit=100,
            sort_types=["hot", "new", "top_day", "top_week", "top_month", "top_year", "top_all"],
            include_comments=False,
            request_delay=1.5
        )

        assert len(posts) >= 50, f"Should get at least 50 unique posts, got {len(posts)}"

        # Verify all posts have required fields
        for post in posts:
            assert post["title"]
            assert post["id"]
            assert post["url"]

        # Verify uniqueness
        ids = [p["id"] for p in posts]
        assert len(ids) == len(set(ids)), "All posts should have unique IDs"

    def test_e2e_scrape_with_comments_at_scale(self):
        """Test scraping posts with comments at scale."""
        posts = scrape_reddit_posts(
            limit=10,
            sort_types=["top_week"],  # Top posts have more comments
            include_comments=True,
            request_delay=2.0
        )

        assert len(posts) > 0

        # Count total comments
        total_comments = sum(len(p["comments"]) for p in posts)
        # Top posts should have some comments
        assert total_comments > 0, "Should have scraped some comments from top posts"
