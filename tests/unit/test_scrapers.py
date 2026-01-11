"""Unit tests for scrapers."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from bs4 import BeautifulSoup

from scrapers.base import DataSource, RawDataPoint
from scrapers.reddit import RedditScraper
from scrapers.appstore import AppStoreScraper
from scrapers.community import CommunityScraper
from scrapers.twitter import TwitterScraper


class TestRedditScraper:
    """Tests for RedditScraper."""

    @pytest.fixture
    def scraper(self):
        """Create a RedditScraper with mocked PRAW."""
        with patch("scrapers.reddit.praw.Reddit"):
            return RedditScraper()

    def test_pain_point_keywords_defined(self, scraper):
        """Test that pain point keywords are defined."""
        assert len(scraper.PAIN_POINT_KEYWORDS) > 0
        assert "frustrated" in scraper.PAIN_POINT_KEYWORDS
        assert "problem" in scraper.PAIN_POINT_KEYWORDS
        assert "help" in scraper.PAIN_POINT_KEYWORDS

    def test_has_pain_keywords_positive(self, scraper):
        """Test _has_pain_keywords returns True for relevant text."""
        assert scraper._has_pain_keywords("I'm so frustrated with this app")
        assert scraper._has_pain_keywords("This is a major problem")
        assert scraper._has_pain_keywords("Need help with inventory")
        assert scraper._has_pain_keywords("Looking for an alternative")

    def test_has_pain_keywords_negative(self, scraper):
        """Test _has_pain_keywords returns False for irrelevant text."""
        assert not scraper._has_pain_keywords("Everything works great")
        assert not scraper._has_pain_keywords("Love this feature")
        assert not scraper._has_pain_keywords("Sales are up 50%")

    def test_has_pain_keywords_case_insensitive(self, scraper):
        """Test keyword matching is case insensitive."""
        assert scraper._has_pain_keywords("FRUSTRATED with this")
        assert scraper._has_pain_keywords("PROBLEM here")

    def test_is_relevant_with_shopify_and_pain(self, scraper, sample_reddit_submission):
        """Test _is_relevant returns True for Shopify + pain points."""
        sample_reddit_submission.title = "Shopify inventory problem"
        sample_reddit_submission.selftext = "I need help with this frustrating issue"
        assert scraper._is_relevant(sample_reddit_submission)

    def test_is_relevant_without_shopify(self, scraper, sample_reddit_submission):
        """Test _is_relevant returns False without Shopify mention."""
        sample_reddit_submission.title = "General ecommerce problem"
        sample_reddit_submission.selftext = "Need help with inventory"
        assert not scraper._is_relevant(sample_reddit_submission)

    def test_is_relevant_without_pain_keywords(self, scraper, sample_reddit_submission):
        """Test _is_relevant returns False without pain keywords."""
        sample_reddit_submission.title = "Shopify update"
        sample_reddit_submission.selftext = "New features released today"
        assert not scraper._is_relevant(sample_reddit_submission)

    def test_submission_to_datapoint(self, scraper, sample_reddit_submission):
        """Test converting submission to RawDataPoint."""
        dp = scraper._submission_to_datapoint(sample_reddit_submission)

        assert dp.source == DataSource.REDDIT
        assert dp.source_id == "reddit_post_abc123"
        assert "need_help" in dp.url
        assert dp.title == "Need help with inventory management"
        assert "inventory" in dp.content.lower()
        assert dp.metadata["subreddit"] == "shopify"
        assert dp.metadata["score"] == 25
        assert dp.metadata["type"] == "post"

    def test_submission_to_datapoint_deleted_author(self, scraper, sample_reddit_submission):
        """Test handling deleted author."""
        sample_reddit_submission.author = None
        dp = scraper._submission_to_datapoint(sample_reddit_submission)
        assert dp.author == "[deleted]"

    def test_submission_to_datapoint_no_body(self, scraper, sample_reddit_submission):
        """Test handling submission with no body text."""
        sample_reddit_submission.selftext = ""
        dp = scraper._submission_to_datapoint(sample_reddit_submission)
        assert dp.content == "[No body text]"


class TestAppStoreScraper:
    """Tests for AppStoreScraper."""

    @pytest.fixture
    def scraper(self):
        """Create an AppStoreScraper."""
        return AppStoreScraper()

    def test_target_apps_defined(self, scraper):
        """Test that target apps list is populated."""
        assert len(scraper.TARGET_APPS) > 0
        # Updated to match current Shopify first-party apps
        assert "flow" in scraper.TARGET_APPS
        assert "inbox" in scraper.TARGET_APPS

    def test_parse_date_relative_days(self, scraper):
        """Test parsing relative date strings."""
        result = scraper._parse_date("2 days ago")
        assert result.date() <= datetime.utcnow().date()

    def test_parse_date_relative_weeks(self, scraper):
        """Test parsing weeks ago."""
        result = scraper._parse_date("1 week ago")
        assert result < datetime.utcnow()

    def test_parse_date_today(self, scraper):
        """Test parsing 'today'."""
        result = scraper._parse_date("today")
        assert result.date() == datetime.utcnow().date()

    def test_is_negative_review_low_rating(self, scraper):
        """Test _is_negative_review with low rating."""
        dp = RawDataPoint(
            source=DataSource.APP_STORE,
            source_id="test",
            url="https://example.com",
            content="This app is fine",
            created_at=datetime.now(),
            metadata={"rating": 2},
        )
        assert scraper._is_negative_review(dp) is True

    def test_is_negative_review_high_rating_with_but(self, scraper):
        """Test _is_negative_review with high rating but complaints."""
        dp = RawDataPoint(
            source=DataSource.APP_STORE,
            source_id="test",
            url="https://example.com",
            content="Great app but missing some features",
            created_at=datetime.now(),
            metadata={"rating": 4},
        )
        assert scraper._is_negative_review(dp) is True

    def test_is_negative_review_positive(self, scraper):
        """Test _is_negative_review with truly positive review."""
        dp = RawDataPoint(
            source=DataSource.APP_STORE,
            source_id="test",
            url="https://example.com",
            content="Absolutely love this app! Works perfectly.",
            created_at=datetime.now(),
            metadata={"rating": 5},
        )
        assert scraper._is_negative_review(dp) is False

    def test_parse_review_element(self, scraper):
        """Test parsing review from star rating element."""
        # Create HTML that matches the current scraper's expected structure
        html = '''
        <div class="lg:tw-col-span-3">
            <div aria-label="2 out of 5 stars">Rating</div>
            <div>December 15, 2025 The app crashes frequently and is hard to use.</div>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser")
        star_elem = soup.find(attrs={"aria-label": "2 out of 5 stars"})

        dp = scraper._parse_review_element(star_elem, "test-app", "https://apps.shopify.com/test-app")

        assert dp is not None
        assert dp.source == DataSource.APP_STORE
        assert "test-app" in dp.source_id
        assert dp.metadata["rating"] == 2
        assert "crashes" in dp.content.lower()


class TestCommunityScraper:
    """Tests for CommunityScraper."""

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper."""
        return CommunityScraper()

    def test_boards_defined(self, scraper):
        """Test that forum boards are defined."""
        assert len(scraper.BOARDS) > 0
        assert "/c/shopify-discussion" in scraper.BOARDS
        assert "/c/shopify-apps" in scraper.BOARDS

    def test_pain_keywords_defined(self, scraper):
        """Test pain keywords are defined."""
        assert len(scraper.PAIN_KEYWORDS) > 0
        assert "help" in scraper.PAIN_KEYWORDS
        assert "problem" in scraper.PAIN_KEYWORDS

    def test_is_relevant_with_keywords(self, scraper, sample_raw_datapoint):
        """Test _is_relevant with pain keywords."""
        sample_raw_datapoint.content = "I need help with this issue"
        assert scraper._is_relevant(sample_raw_datapoint) is True

    def test_is_relevant_without_keywords(self, scraper):
        """Test _is_relevant without pain keywords."""
        dp = RawDataPoint(
            source=DataSource.COMMUNITY,
            source_id="test",
            url="https://example.com",
            title="Success story",
            content="My store is doing great",
            created_at=datetime.now(),
        )
        assert scraper._is_relevant(dp) is False

    def test_extract_number(self, scraper):
        """Test extracting numbers from elements."""
        html = '<span class="reply-count">15 replies</span>'
        soup = BeautifulSoup(html, "html.parser")
        assert scraper._extract_number(soup, ".reply-count") == 15

    def test_extract_number_missing_element(self, scraper):
        """Test extracting number when element missing."""
        soup = BeautifulSoup("<div></div>", "html.parser")
        assert scraper._extract_number(soup, ".nonexistent") == 0

    def test_parse_date_iso_format(self, scraper):
        """Test parsing ISO format dates."""
        result = scraper._parse_date("2024-01-15T10:30:00Z")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_relative(self, scraper):
        """Test parsing relative dates."""
        result = scraper._parse_date("3 days ago")
        assert result < datetime.utcnow()

    def test_parse_date_empty(self, scraper):
        """Test parsing empty date string."""
        result = scraper._parse_date("")
        # Should return current time
        assert result.date() == datetime.utcnow().date()


class TestTwitterScraper:
    """Tests for TwitterScraper."""

    @pytest.fixture
    def scraper(self):
        """Create a TwitterScraper with mocked client."""
        with patch("scrapers.twitter.Client"):
            return TwitterScraper()

    def test_search_queries_defined(self, scraper):
        """Test that search queries are defined."""
        assert len(scraper.SEARCH_QUERIES) > 0
        # Check queries target pain points
        queries_text = " ".join(scraper.SEARCH_QUERIES).lower()
        assert "frustrated" in queries_text
        assert "problem" in queries_text
        assert "help" in queries_text

    def test_search_queries_exclude_retweets(self, scraper):
        """Test that queries exclude retweets."""
        for query in scraper.SEARCH_QUERIES:
            assert "-is:retweet" in query

    def test_tweet_to_datapoint(self, scraper):
        """Test converting tweet to datapoint."""
        tweet = MagicMock()
        tweet.id = "123456789"
        tweet.text = "Shopify is frustrating today!"
        tweet.author_id = "user123"
        tweet.created_at = datetime(2024, 1, 15, 10, 30, 0)
        tweet.public_metrics = {
            "like_count": 10,
            "retweet_count": 2,
            "reply_count": 5,
        }

        authors = {"user123": "test_user"}

        dp = scraper._tweet_to_datapoint(tweet, authors, "shopify frustrated")

        assert dp.source == DataSource.TWITTER
        assert dp.source_id == "twitter_123456789"
        assert "test_user" in dp.url
        assert dp.content == "Shopify is frustrating today!"
        assert dp.metadata["likes"] == 10
        assert dp.metadata["retweets"] == 2

    def test_tweet_to_datapoint_unknown_author(self, scraper):
        """Test handling unknown author."""
        tweet = MagicMock()
        tweet.id = "123"
        tweet.text = "Test tweet"
        tweet.author_id = "unknown_id"
        tweet.created_at = datetime.now()
        tweet.public_metrics = {}

        dp = scraper._tweet_to_datapoint(tweet, {}, "query")

        assert dp.author == "unknown"
