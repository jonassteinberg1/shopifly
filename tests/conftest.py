"""Shared test fixtures and configuration."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from scrapers.base import RawDataPoint, DataSource
from analysis.classifier import ClassifiedInsight, ProblemCategory


@pytest.fixture
def sample_raw_datapoint():
    """Create a sample RawDataPoint for testing."""
    return RawDataPoint(
        source=DataSource.REDDIT,
        source_id="reddit_post_abc123",
        url="https://reddit.com/r/shopify/comments/abc123",
        title="Frustrated with Shopify's analytics",
        content="I've been using Shopify for 2 years and the built-in analytics are terrible. "
        "I need better conversion tracking but all the apps are way too expensive. "
        "I'd happily pay $20/month for something that actually works.",
        author="merchant_user",
        created_at=datetime(2024, 1, 15, 10, 30, 0),
        metadata={
            "subreddit": "shopify",
            "score": 45,
            "num_comments": 23,
            "type": "post",
        },
    )


@pytest.fixture
def sample_classified_insight():
    """Create a sample ClassifiedInsight for testing."""
    return ClassifiedInsight(
        source_id="reddit_post_abc123",
        source_url="https://reddit.com/r/shopify/comments/abc123",
        problem_statement="Shopify's built-in analytics are insufficient for conversion tracking",
        category=ProblemCategory.ANALYTICS,
        secondary_categories=[ProblemCategory.PRICING],
        frustration_level=4,
        clarity_score=5,
        willingness_to_pay=True,
        wtp_quotes=["I'd happily pay $20/month for something that actually works"],
        current_workaround=None,
        keywords=["analytics", "conversion tracking", "expensive apps"],
        original_title="Frustrated with Shopify's analytics",
        content_snippet="I've been using Shopify for 2 years and the built-in analytics are terrible.",
    )


@pytest.fixture
def sample_reddit_submission():
    """Create a mock Reddit submission."""
    submission = MagicMock()
    submission.id = "abc123"
    submission.title = "Need help with inventory management"
    submission.selftext = "Looking for a better way to track inventory. The current system is frustrating."
    submission.author = MagicMock()
    submission.author.__str__ = lambda x: "test_user"
    submission.permalink = "/r/shopify/comments/abc123/need_help"
    submission.created_utc = 1705312200.0  # 2024-01-15
    submission.score = 25
    submission.num_comments = 10
    submission.upvote_ratio = 0.92
    submission.subreddit = MagicMock()
    submission.subreddit.__str__ = lambda x: "shopify"
    return submission


@pytest.fixture
def sample_app_review_html():
    """Sample HTML for App Store review parsing."""
    return """
    <div class="review-listing">
        <div class="review-listing-header">
            <span class="review-listing-header__text">Test Store</span>
            <span class="review-listing-header__date">2 days ago</span>
        </div>
        <div class="ui-star-rating" aria-label="2 out of 5 stars">
            <span class="ui-star-rating__star--filled"></span>
            <span class="ui-star-rating__star--filled"></span>
        </div>
        <div class="review-listing-body">
            App crashes constantly. Missing basic features that competitors have.
            Support takes forever to respond.
        </div>
    </div>
    """


@pytest.fixture
def sample_community_topic_html():
    """Sample HTML for Community forum topic parsing."""
    return """
    <html>
    <head><title>Test Topic</title></head>
    <body>
        <h1 class="topic-title">How to automate order fulfillment?</h1>
        <div class="post-body">
            I'm looking for a way to automate my order fulfillment process.
            Currently spending 2 hours a day on manual tasks.
            Need help finding a solution that doesn't cost $500/month.
        </div>
        <a class="username">helpful_merchant</a>
        <time datetime="2024-01-10T14:30:00Z">January 10, 2024</time>
        <span class="reply-count">15 replies</span>
        <span class="view-count">234 views</span>
    </body>
    </html>
    """


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response for classification."""
    return {
        "problem_statement": "Shopify's built-in analytics are insufficient for conversion tracking",
        "category": "analytics",
        "secondary_categories": ["pricing"],
        "frustration_level": 4,
        "clarity_score": 5,
        "willingness_to_pay": True,
        "wtp_quotes": ["I'd happily pay $20/month"],
        "current_workaround": None,
        "keywords": ["analytics", "conversion", "tracking"],
    }


@pytest.fixture
def mock_airtable_records():
    """Mock Airtable records for storage tests."""
    return [
        {
            "id": "rec123",
            "fields": {
                "source_id": "reddit_post_abc123",
                "source": "reddit",
                "url": "https://reddit.com/r/shopify/test",
                "title": "Test Post",
                "content": "Test content about shopify problems",
                "author": "test_user",
                "created_at": "2024-01-15T10:30:00",
                "processed": False,
            },
        },
        {
            "id": "rec456",
            "fields": {
                "source_id": "reddit_post_def456",
                "source": "reddit",
                "url": "https://reddit.com/r/shopify/test2",
                "title": "Another Test",
                "content": "More content about issues",
                "author": "another_user",
                "created_at": "2024-01-16T11:00:00",
                "processed": False,
            },
        },
    ]
