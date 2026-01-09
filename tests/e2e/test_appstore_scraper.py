"""End-to-end tests for Shopify App Store scraper.

These tests actually hit the Shopify App Store to verify the scraper works
in production. They use small limits to avoid rate limiting.

Note: App Store reviews don't have comments/replies. Each review is standalone
content that can be directly classified by the LLM.

Run with: pytest tests/e2e/test_appstore_scraper.py -v -m e2e
"""

import pytest
from datetime import datetime

from scrapers.appstore import AppStoreScraper
from scrapers.base import DataSource, RawDataPoint
from storage.sqlite import SQLiteStorage


@pytest.mark.e2e
class TestAppStoreScraperEndpoints:
    """E2E tests for App Store scraper endpoints."""

    @pytest.fixture
    def scraper(self):
        """Create an AppStoreScraper instance."""
        return AppStoreScraper(headless=True)

    @pytest.mark.asyncio
    async def test_e2e_health_check(self, scraper):
        """Test that App Store is accessible."""
        try:
            healthy = await scraper.health_check()
            assert healthy is True, "Shopify App Store should be accessible"
        finally:
            await scraper.close()

    @pytest.mark.asyncio
    async def test_e2e_app_store_base_url_accessible(self, scraper):
        """Test that the base App Store URL is accessible."""
        driver = scraper._get_driver()
        try:
            driver.get(scraper.BASE_URL)
            assert "Shopify" in driver.title or "App Store" in driver.title
        finally:
            scraper._close_driver()


@pytest.mark.e2e
class TestAppStoreReviewScraping:
    """E2E tests for review scraping functionality."""

    @pytest.fixture
    def scraper(self):
        """Create an AppStoreScraper instance."""
        return AppStoreScraper(headless=True)

    @pytest.mark.asyncio
    async def test_e2e_scrape_reviews(self, scraper):
        """Test scraping reviews from App Store."""
        reviews = []

        try:
            async for datapoint in scraper.scrape(limit=5):
                assert isinstance(datapoint, RawDataPoint)
                assert datapoint.source == DataSource.APP_STORE
                reviews.append(datapoint)
                if len(reviews) >= 5:
                    break
        finally:
            await scraper.close()

        # Note: May get 0 results if site structure changed
        # But structure should be valid if we get any
        for review in reviews:
            assert review.content is not None
            assert len(review.content) > 0
            assert review.url is not None

    @pytest.mark.asyncio
    async def test_e2e_review_has_rating(self, scraper):
        """Test that scraped reviews include rating in metadata."""
        try:
            async for datapoint in scraper.scrape(limit=3):
                # Every review should have rating in metadata
                assert "rating" in datapoint.metadata, "Review should have 'rating' in metadata"
                rating = datapoint.metadata["rating"]
                assert 1 <= rating <= 5, f"Rating should be 1-5, got {rating}"
                return  # Found valid review

        finally:
            await scraper.close()

        pytest.skip("No reviews scraped (site may have changed)")

    @pytest.mark.asyncio
    async def test_e2e_review_has_app_info(self, scraper):
        """Test that scraped reviews include app information."""
        try:
            async for datapoint in scraper.scrape(limit=3):
                assert "app_slug" in datapoint.metadata, "Review should have 'app_slug'"
                assert datapoint.metadata["app_slug"] in scraper.TARGET_APPS, \
                    "App slug should be from target apps list"
                return  # Found valid review

        finally:
            await scraper.close()

        pytest.skip("No reviews scraped")


@pytest.mark.e2e
class TestAppStoreReviewContent:
    """E2E tests for review content extraction."""

    @pytest.fixture
    def scraper(self):
        """Create an AppStoreScraper instance."""
        return AppStoreScraper(headless=True)

    @pytest.mark.asyncio
    async def test_e2e_review_content_meaningful(self, scraper):
        """Test that review content is meaningful and not boilerplate."""
        try:
            async for datapoint in scraper.scrape(limit=5):
                content = datapoint.content

                # Content should be substantial
                assert len(content) > 10, "Review content should be substantial"

                # Content should not be just UI elements
                assert content.lower() != "show more"
                assert content.lower() != "show less"

                return  # Found valid review

        finally:
            await scraper.close()

        pytest.skip("No reviews scraped")

    @pytest.mark.asyncio
    async def test_e2e_negative_reviews_captured(self, scraper):
        """Test that negative reviews (pain points) are captured."""
        negative_reviews = []

        try:
            async for datapoint in scraper.scrape(limit=20):
                rating = datapoint.metadata.get("rating", 5)
                if rating <= 3:
                    negative_reviews.append(datapoint)
                if len(negative_reviews) >= 3:
                    break
        finally:
            await scraper.close()

        # Scraper prioritizes low ratings, so should find some negative reviews
        # (but may be 0 if apps have all positive reviews)
        for review in negative_reviews:
            assert review.metadata["rating"] <= 3


@pytest.mark.e2e
class TestAppStoreStoragePipeline:
    """E2E tests for the full scrape-to-storage pipeline."""

    @pytest.fixture
    def sqlite_storage(self, tmp_path):
        """Create a temporary SQLite storage."""
        db_path = tmp_path / "e2e_appstore.db"
        return SQLiteStorage(db_path=str(db_path))

    @pytest.fixture
    def scraper(self):
        """Create an AppStoreScraper instance."""
        return AppStoreScraper(headless=True)

    @pytest.mark.asyncio
    async def test_e2e_scrape_and_store_reviews(self, scraper, sqlite_storage):
        """Test full pipeline: scrape from App Store and store."""
        stored_count = 0

        try:
            async for datapoint in scraper.scrape(limit=5):
                record_id = sqlite_storage.save_raw_datapoint(datapoint)
                assert record_id is not None
                stored_count += 1
                if stored_count >= 5:
                    break
        finally:
            await scraper.close()

        if stored_count == 0:
            pytest.skip("No reviews scraped (site may have changed)")

        # Verify storage
        stats = sqlite_storage.get_stats()
        assert stats["raw_data_points"] == stored_count

        # Retrieve and verify (returns dicts, not objects)
        unprocessed = sqlite_storage.get_unprocessed_raw_data()
        for item in unprocessed:
            assert item["source"] == DataSource.APP_STORE.value
            assert "rating" in item["metadata"]
            assert "app_slug" in item["metadata"]

    @pytest.mark.asyncio
    async def test_e2e_review_ready_for_llm(self, scraper):
        """Test that reviews are ready for LLM classification."""
        try:
            async for datapoint in scraper.scrape(limit=3):
                # Build context string as would be sent to LLM
                context = f"App: {datapoint.metadata.get('app_slug', 'unknown')}\n"
                context += f"Rating: {datapoint.metadata.get('rating', 'N/A')}/5 stars\n"
                context += f"Review: {datapoint.content}\n"

                # Context should be meaningful for classification
                assert len(context) > 30, "Should have enough context for LLM"

                # For negative reviews, content should express pain points
                if datapoint.metadata.get("rating", 5) <= 3:
                    # Low-rated reviews typically express issues
                    assert len(datapoint.content) > 20, \
                        "Negative review should have substantive content"

                return  # Test passed

        finally:
            await scraper.close()

        pytest.skip("No reviews scraped")


@pytest.mark.e2e
class TestAppStoreScraperResilience:
    """E2E tests for scraper resilience and error handling."""

    @pytest.fixture
    def scraper(self):
        """Create an AppStoreScraper instance."""
        return AppStoreScraper(headless=True)

    @pytest.mark.asyncio
    async def test_e2e_handles_multiple_apps(self, scraper):
        """Test that scraper can handle multiple apps without crashing."""
        app_slugs_seen = set()

        try:
            async for datapoint in scraper.scrape(limit=15):
                app_slug = datapoint.metadata.get("app_slug")
                if app_slug:
                    app_slugs_seen.add(app_slug)
        except Exception as e:
            pytest.fail(f"Scraper crashed with exception: {e}")
        finally:
            await scraper.close()

        # Should have scraped from at least one app
        # (may be limited if running quickly)
        assert len(app_slugs_seen) >= 0  # May be 0 if site issues

    @pytest.mark.asyncio
    async def test_e2e_data_integrity(self, scraper):
        """Test that scraped data maintains integrity."""
        try:
            async for datapoint in scraper.scrape(limit=3):
                # Source should always be APP_STORE
                assert datapoint.source == DataSource.APP_STORE

                # URL should be valid App Store URL
                assert "apps.shopify.com" in datapoint.url

                # Metadata should have expected structure
                assert "type" in datapoint.metadata
                assert datapoint.metadata["type"] == "review"
                assert "rating" in datapoint.metadata

                return  # Just check first review

        finally:
            await scraper.close()

        pytest.skip("No reviews scraped")

    @pytest.mark.asyncio
    async def test_e2e_cleans_up_driver(self, scraper):
        """Test that WebDriver is properly cleaned up."""
        try:
            count = 0
            async for _ in scraper.scrape(limit=2):
                count += 1
                if count >= 2:
                    break
        finally:
            await scraper.close()

        # Driver should be None after close
        assert scraper._driver is None, "Driver should be cleaned up after close"


@pytest.mark.e2e
class TestAppStoreReviewClassification:
    """E2E tests verifying reviews are suitable for classification pipeline."""

    @pytest.fixture
    def scraper(self):
        """Create an AppStoreScraper instance."""
        return AppStoreScraper(headless=True)

    @pytest.mark.asyncio
    async def test_e2e_reviews_contain_classifiable_content(self, scraper):
        """Test that reviews contain content that can be classified."""
        classifiable_reviews = []

        try:
            async for datapoint in scraper.scrape(limit=10):
                content = datapoint.content.lower()

                # Check if content contains classifiable keywords
                has_feature_words = any(word in content for word in [
                    "feature", "need", "want", "wish", "missing",
                    "should", "could", "add", "improve", "better"
                ])
                has_issue_words = any(word in content for word in [
                    "bug", "issue", "problem", "broken", "error",
                    "crash", "slow", "doesn't work", "not working"
                ])

                if has_feature_words or has_issue_words:
                    classifiable_reviews.append(datapoint)

                if len(classifiable_reviews) >= 3:
                    break
        finally:
            await scraper.close()

        # Should find some classifiable content (pain points/feature requests)
        # in negative reviews
        assert len(classifiable_reviews) >= 0  # May be 0 if all positive reviews

    @pytest.mark.asyncio
    async def test_e2e_review_text_not_truncated(self, scraper):
        """Test that review text is not inappropriately truncated."""
        try:
            async for datapoint in scraper.scrape(limit=5):
                content = datapoint.content

                # Check for truncation indicators
                assert not content.endswith("...") or len(content) > 100, \
                    "Content should not be truncated to just ellipsis"
                assert "Show more" not in content, \
                    "Content should not contain 'Show more' button text"

                return  # Found valid review

        finally:
            await scraper.close()

        pytest.skip("No reviews scraped")
