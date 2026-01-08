"""Unit tests for data models."""

import pytest
from datetime import datetime

from scrapers.base import RawDataPoint, DataSource
from analysis.classifier import ClassifiedInsight, ProblemCategory


class TestDataSource:
    """Tests for DataSource enum."""

    def test_data_source_values(self):
        """Test all data source enum values."""
        assert DataSource.REDDIT.value == "reddit"
        assert DataSource.APP_STORE.value == "shopify_app_store"
        assert DataSource.TWITTER.value == "twitter"
        assert DataSource.COMMUNITY.value == "shopify_community"

    def test_data_source_from_string(self):
        """Test creating DataSource from string."""
        assert DataSource("reddit") == DataSource.REDDIT
        assert DataSource("shopify_app_store") == DataSource.APP_STORE


class TestRawDataPoint:
    """Tests for RawDataPoint model."""

    def test_create_minimal_datapoint(self):
        """Test creating a datapoint with minimal required fields."""
        dp = RawDataPoint(
            source=DataSource.REDDIT,
            source_id="test_123",
            url="https://example.com",
            content="Test content",
            created_at=datetime.now(),
        )
        assert dp.source == DataSource.REDDIT
        assert dp.source_id == "test_123"
        assert dp.title is None
        assert dp.author is None
        assert dp.metadata == {}

    def test_create_full_datapoint(self, sample_raw_datapoint):
        """Test creating a datapoint with all fields."""
        dp = sample_raw_datapoint
        assert dp.source == DataSource.REDDIT
        assert dp.source_id == "reddit_post_abc123"
        assert dp.title == "Frustrated with Shopify's analytics"
        assert "analytics are terrible" in dp.content
        assert dp.author == "merchant_user"
        assert dp.metadata["subreddit"] == "shopify"
        assert dp.metadata["score"] == 45

    def test_full_text_with_title(self, sample_raw_datapoint):
        """Test full_text property combines title and content."""
        full = sample_raw_datapoint.full_text
        assert "Frustrated with Shopify's analytics" in full
        assert "analytics are terrible" in full

    def test_full_text_without_title(self):
        """Test full_text property when no title."""
        dp = RawDataPoint(
            source=DataSource.TWITTER,
            source_id="tweet_123",
            url="https://twitter.com/test",
            content="Just content here",
            created_at=datetime.now(),
        )
        assert dp.full_text == "Just content here"

    def test_scraped_at_auto_generated(self):
        """Test that scraped_at is auto-generated."""
        before = datetime.utcnow()
        dp = RawDataPoint(
            source=DataSource.REDDIT,
            source_id="test",
            url="https://example.com",
            content="Test",
            created_at=datetime.now(),
        )
        after = datetime.utcnow()
        assert before <= dp.scraped_at <= after

    def test_metadata_default_empty_dict(self):
        """Test that metadata defaults to empty dict."""
        dp = RawDataPoint(
            source=DataSource.REDDIT,
            source_id="test",
            url="https://example.com",
            content="Test",
            created_at=datetime.now(),
        )
        assert dp.metadata == {}
        assert isinstance(dp.metadata, dict)


class TestProblemCategory:
    """Tests for ProblemCategory enum."""

    def test_all_categories_exist(self):
        """Test all expected categories are defined."""
        expected = [
            "admin", "analytics", "marketing", "loyalty", "payments",
            "fulfillment", "inventory", "customer_support", "design",
            "seo", "integrations", "performance", "pricing", "other",
        ]
        for cat in expected:
            assert ProblemCategory(cat) is not None

    def test_category_string_value(self):
        """Test category values are lowercase strings."""
        assert ProblemCategory.ANALYTICS.value == "analytics"
        assert ProblemCategory.CUSTOMER_SUPPORT.value == "customer_support"


class TestClassifiedInsight:
    """Tests for ClassifiedInsight model."""

    def test_create_minimal_insight(self):
        """Test creating insight with minimal required fields."""
        insight = ClassifiedInsight(
            source_id="test_123",
            source_url="https://example.com",
            problem_statement="Test problem",
            category=ProblemCategory.OTHER,
            frustration_level=3,
            clarity_score=3,
            willingness_to_pay=False,
            content_snippet="Test snippet",
        )
        assert insight.source_id == "test_123"
        assert insight.secondary_categories == []
        assert insight.wtp_quotes == []
        assert insight.current_workaround is None
        assert insight.keywords == []

    def test_create_full_insight(self, sample_classified_insight):
        """Test creating insight with all fields."""
        insight = sample_classified_insight
        assert insight.category == ProblemCategory.ANALYTICS
        assert ProblemCategory.PRICING in insight.secondary_categories
        assert insight.frustration_level == 4
        assert insight.willingness_to_pay is True
        assert len(insight.wtp_quotes) == 1
        assert "analytics" in insight.keywords

    def test_frustration_level_bounds(self):
        """Test frustration_level validation (1-5)."""
        # Valid levels
        for level in [1, 2, 3, 4, 5]:
            insight = ClassifiedInsight(
                source_id="test",
                source_url="https://example.com",
                problem_statement="Test",
                category=ProblemCategory.OTHER,
                frustration_level=level,
                clarity_score=3,
                willingness_to_pay=False,
                content_snippet="Test",
            )
            assert insight.frustration_level == level

    def test_frustration_level_invalid(self):
        """Test frustration_level rejects invalid values."""
        with pytest.raises(ValueError):
            ClassifiedInsight(
                source_id="test",
                source_url="https://example.com",
                problem_statement="Test",
                category=ProblemCategory.OTHER,
                frustration_level=0,  # Invalid: below 1
                clarity_score=3,
                willingness_to_pay=False,
                content_snippet="Test",
            )

        with pytest.raises(ValueError):
            ClassifiedInsight(
                source_id="test",
                source_url="https://example.com",
                problem_statement="Test",
                category=ProblemCategory.OTHER,
                frustration_level=6,  # Invalid: above 5
                clarity_score=3,
                willingness_to_pay=False,
                content_snippet="Test",
            )

    def test_clarity_score_bounds(self):
        """Test clarity_score validation (1-5)."""
        for score in [1, 2, 3, 4, 5]:
            insight = ClassifiedInsight(
                source_id="test",
                source_url="https://example.com",
                problem_statement="Test",
                category=ProblemCategory.OTHER,
                frustration_level=3,
                clarity_score=score,
                willingness_to_pay=False,
                content_snippet="Test",
            )
            assert insight.clarity_score == score
