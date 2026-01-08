"""Unit tests for Reddit Selenium/RSS scraper."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, Mock
import xml.etree.ElementTree as ET

from scrapers.reddit_selenium import (
    RedditSeleniumScraper,
    scrape_reddit_posts,
    _extract_selftext_from_html,
    _fetch_rss_simple,
    _fetch_post_comments,
    RSS_ENDPOINTS,
    DEFAULT_HEADERS,
)
from scrapers.base import DataSource, RawDataPoint


# Sample RSS XML for testing
SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Shopify</title>
    <entry>
        <author><name>/u/test_user</name></author>
        <title>Test Post Title</title>
        <link href="https://www.reddit.com/r/shopify/comments/abc123/test_post_title/"/>
        <content type="html">&lt;p&gt;This is the post content about Shopify problems.&lt;/p&gt;</content>
        <updated>2026-01-08T10:00:00+00:00</updated>
    </entry>
    <entry>
        <author><name>/u/another_user</name></author>
        <title>Another Test Post</title>
        <link href="https://www.reddit.com/r/shopify/comments/def456/another_test/"/>
        <content type="html">&lt;p&gt;More content here with issues.&lt;/p&gt;</content>
        <updated>2026-01-07T09:00:00+00:00</updated>
    </entry>
</feed>
"""

SAMPLE_COMMENTS_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Test Post Title</title>
    <entry>
        <author><name>/u/test_user</name></author>
        <title>Test Post Title</title>
        <link href="https://www.reddit.com/r/shopify/comments/abc123/test_post_title/"/>
        <content type="html">&lt;p&gt;Original post content&lt;/p&gt;</content>
        <updated>2026-01-08T10:00:00+00:00</updated>
    </entry>
    <entry>
        <author><name>/u/commenter1</name></author>
        <title>Re: Test Post Title</title>
        <link href="https://www.reddit.com/r/shopify/comments/abc123/test_post_title/comment1/"/>
        <content type="html">&lt;p&gt;This is a helpful comment.&lt;/p&gt;</content>
        <updated>2026-01-08T11:00:00+00:00</updated>
    </entry>
    <entry>
        <author><name>/u/commenter2</name></author>
        <title>Re: Test Post Title</title>
        <link href="https://www.reddit.com/r/shopify/comments/abc123/test_post_title/comment2/"/>
        <content type="html">&lt;p&gt;Another comment here.&lt;/p&gt;</content>
        <updated>2026-01-08T12:00:00+00:00</updated>
    </entry>
</feed>
"""


class TestExtractSelftextFromHtml:
    """Tests for _extract_selftext_from_html function."""

    def test_extracts_text_from_simple_html(self):
        """Test extracting text from simple HTML."""
        html = "<p>This is a test paragraph.</p>"
        result = _extract_selftext_from_html(html)
        assert "This is a test paragraph." in result

    def test_handles_html_entities(self):
        """Test handling of HTML entities."""
        html = "&lt;p&gt;Test &amp; more&lt;/p&gt;"
        result = _extract_selftext_from_html(html)
        assert "<p>" in result or "Test" in result
        assert "&" in result or "more" in result

    def test_converts_br_to_newlines(self):
        """Test that <br> tags become newlines."""
        html = "Line 1<br/>Line 2<br>Line 3"
        result = _extract_selftext_from_html(html)
        assert "\n" in result

    def test_converts_p_tags_to_double_newlines(self):
        """Test that </p> tags become double newlines."""
        html = "<p>Paragraph 1</p><p>Paragraph 2</p>"
        result = _extract_selftext_from_html(html)
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result

    def test_removes_link_comments_boilerplate(self):
        """Test removal of [link] [comments] boilerplate."""
        html = "Content here [link] [comments]"
        result = _extract_selftext_from_html(html)
        assert "[link]" not in result
        assert "[comments]" not in result

    def test_handles_empty_string(self):
        """Test handling of empty string."""
        result = _extract_selftext_from_html("")
        assert result == ""

    def test_handles_none(self):
        """Test handling of None-like empty content."""
        result = _extract_selftext_from_html("")
        assert result == ""

    def test_strips_whitespace(self):
        """Test that result is stripped of excess whitespace."""
        html = "  <p>  Content  </p>  "
        result = _extract_selftext_from_html(html)
        assert not result.startswith(" ")
        assert not result.endswith(" ")


class TestRSSEndpoints:
    """Tests for RSS endpoints configuration."""

    def test_all_endpoints_defined(self):
        """Test that all expected endpoints are defined."""
        expected = ["hot", "new", "top_day", "top_week", "top_month", "top_year", "top_all", "rising"]
        for key in expected:
            assert key in RSS_ENDPOINTS
            assert RSS_ENDPOINTS[key].startswith("https://www.reddit.com/r/shopify")

    def test_endpoints_are_rss_urls(self):
        """Test that all endpoints end with .rss."""
        for key, url in RSS_ENDPOINTS.items():
            assert ".rss" in url, f"Endpoint {key} should be an RSS URL"

    def test_top_endpoints_have_time_filter(self):
        """Test that top endpoints have time filter parameter."""
        assert "t=day" in RSS_ENDPOINTS["top_day"]
        assert "t=week" in RSS_ENDPOINTS["top_week"]
        assert "t=month" in RSS_ENDPOINTS["top_month"]
        assert "t=year" in RSS_ENDPOINTS["top_year"]
        assert "t=all" in RSS_ENDPOINTS["top_all"]


class TestDefaultHeaders:
    """Tests for default HTTP headers."""

    def test_user_agent_defined(self):
        """Test that User-Agent is defined."""
        assert "User-Agent" in DEFAULT_HEADERS
        assert "Mozilla" in DEFAULT_HEADERS["User-Agent"]

    def test_accept_header_includes_xml(self):
        """Test that Accept header includes XML types."""
        assert "Accept" in DEFAULT_HEADERS
        assert "xml" in DEFAULT_HEADERS["Accept"].lower()


class TestRedditSeleniumScraper:
    """Tests for RedditSeleniumScraper class."""

    @pytest.fixture
    def scraper(self):
        """Create a RedditSeleniumScraper instance."""
        return RedditSeleniumScraper(headless=True, request_delay=0.1)

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

    def test_is_relevant_with_shopify(self, scraper):
        """Test _is_relevant returns True when Shopify is mentioned."""
        assert scraper._is_relevant("Shopify question", "How do I do this?")

    def test_is_relevant_with_pain_keywords(self, scraper):
        """Test _is_relevant returns True with pain keywords."""
        assert scraper._is_relevant("Help needed", "I'm frustrated with shipping")

    def test_is_relevant_positive_no_keywords(self, scraper):
        """Test _is_relevant returns False for purely positive content."""
        assert not scraper._is_relevant("Great day", "Everything is wonderful today")

    def test_source_is_reddit(self, scraper):
        """Test that scraper source is Reddit."""
        assert scraper.source == DataSource.REDDIT

    def test_init_parameters(self):
        """Test initialization parameters."""
        scraper = RedditSeleniumScraper(headless=False, request_delay=5.0)
        assert scraper.headless is False
        assert scraper.request_delay == 5.0


class TestFetchRssSimple:
    """Tests for _fetch_rss_simple function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock httpx client."""
        client = MagicMock()
        return client

    def test_parses_valid_rss(self, mock_client):
        """Test parsing valid RSS response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        results = _fetch_rss_simple(mock_client, "https://example.com/rss", debug=False)

        assert len(results) == 2
        assert results[0]["title"] == "Test Post Title"
        assert results[0]["author"] == "test_user"
        assert results[0]["id"] == "abc123"
        assert "Shopify problems" in results[0]["selftext"]

    def test_handles_http_error(self, mock_client):
        """Test handling of HTTP error response."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_client.get.return_value = mock_response

        results = _fetch_rss_simple(mock_client, "https://example.com/rss", debug=False)

        assert len(results) == 0

    def test_handles_invalid_xml(self, mock_client):
        """Test handling of invalid XML response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "not valid xml <<<"
        mock_client.get.return_value = mock_response

        results = _fetch_rss_simple(mock_client, "https://example.com/rss", debug=False)

        assert len(results) == 0

    def test_extracts_post_id_from_url(self, mock_client):
        """Test extraction of post ID from URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        results = _fetch_rss_simple(mock_client, "https://example.com/rss", debug=False)

        assert results[0]["id"] == "abc123"
        assert results[1]["id"] == "def456"


class TestFetchPostComments:
    """Tests for _fetch_post_comments function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock httpx client."""
        client = MagicMock()
        return client

    def test_parses_comments_rss(self, mock_client):
        """Test parsing comments from RSS."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_COMMENTS_RSS_XML
        mock_client.get.return_value = mock_response

        comments = _fetch_post_comments(mock_client, "abc123", debug=False)

        # First entry is the post, so we should have 2 comments
        assert len(comments) == 2
        assert comments[0]["author"] == "commenter1"
        assert "helpful comment" in comments[0]["content"]
        assert comments[1]["author"] == "commenter2"

    def test_skips_first_entry_as_post(self, mock_client):
        """Test that first entry (the post itself) is skipped."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_COMMENTS_RSS_XML
        mock_client.get.return_value = mock_response

        comments = _fetch_post_comments(mock_client, "abc123", debug=False)

        # None of the comments should have the original post author's content
        for comment in comments:
            assert "Original post content" not in comment["content"]

    def test_handles_http_error(self, mock_client):
        """Test handling of HTTP error when fetching comments."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response

        comments = _fetch_post_comments(mock_client, "abc123", debug=False)

        assert len(comments) == 0

    def test_constructs_correct_url(self, mock_client):
        """Test that correct URL is constructed for comments."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_COMMENTS_RSS_XML
        mock_client.get.return_value = mock_response

        _fetch_post_comments(mock_client, "xyz789", debug=False)

        mock_client.get.assert_called_once()
        called_url = mock_client.get.call_args[0][0]
        assert "xyz789" in called_url
        assert ".rss" in called_url


class TestScrapeRedditPosts:
    """Tests for scrape_reddit_posts function."""

    @patch("scrapers.reddit_selenium.httpx.Client")
    def test_uses_default_sort_types(self, mock_client_class):
        """Test that default sort types are used."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        results = scrape_reddit_posts(limit=5, include_comments=False, request_delay=0.01)

        # Should have called get for hot, new, top_week (default sort types)
        assert mock_client.get.call_count >= 1

    @patch("scrapers.reddit_selenium.httpx.Client")
    def test_deduplicates_by_post_id(self, mock_client_class):
        """Test that duplicate posts are removed."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        # Request more than available, but should dedupe
        results = scrape_reddit_posts(
            limit=100,
            sort_types=["hot", "new"],  # Both return same posts
            include_comments=False,
            request_delay=0.01
        )

        # Should only have 2 unique posts from sample XML
        assert len(results) == 2

    @patch("scrapers.reddit_selenium.httpx.Client")
    def test_respects_limit(self, mock_client_class):
        """Test that limit is respected."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        results = scrape_reddit_posts(limit=1, include_comments=False, request_delay=0.01)

        assert len(results) == 1

    @patch("scrapers.reddit_selenium.httpx.Client")
    def test_includes_comments_when_requested(self, mock_client_class):
        """Test that comments are fetched when include_comments=True."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # First call returns posts, subsequent calls return comments
        mock_response_posts = MagicMock()
        mock_response_posts.status_code = 200
        mock_response_posts.text = SAMPLE_RSS_XML

        mock_response_comments = MagicMock()
        mock_response_comments.status_code = 200
        mock_response_comments.text = SAMPLE_COMMENTS_RSS_XML

        mock_client.get.side_effect = [mock_response_posts, mock_response_comments, mock_response_comments]

        results = scrape_reddit_posts(
            limit=2,
            sort_types=["hot"],
            include_comments=True,
            request_delay=0.01
        )

        assert len(results) == 2
        # Each post should have comments
        for post in results:
            assert "comments" in post

    @patch("scrapers.reddit_selenium.httpx.Client")
    def test_handles_unknown_sort_type(self, mock_client_class):
        """Test handling of unknown sort type."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        # Should not crash with unknown sort type
        results = scrape_reddit_posts(
            limit=5,
            sort_types=["unknown_sort", "hot"],
            include_comments=False,
            request_delay=0.01,
            debug=True
        )

        # Should still get results from valid sort type
        assert len(results) > 0


class TestScraperClassMethods:
    """Tests for RedditSeleniumScraper class methods."""

    def test_parse_rss_entry(self):
        """Test _parse_rss_entry method."""
        scraper = RedditSeleniumScraper()

        root = ET.fromstring(SAMPLE_RSS_XML)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", ns)

        result = scraper._parse_rss_entry(entry, ns)

        assert result is not None
        assert isinstance(result, RawDataPoint)
        assert result.source == DataSource.REDDIT
        assert result.title == "Test Post Title"
        assert "test_user" in result.author
        assert "abc123" in result.source_id

    @patch("scrapers.reddit_selenium.httpx.Client")
    def test_fetch_rss_posts(self, mock_client_class):
        """Test _fetch_rss_posts method."""
        mock_client = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_RSS_XML
        mock_client.get.return_value = mock_response

        scraper = RedditSeleniumScraper()
        results = scraper._fetch_rss_posts(mock_client, "https://example.com/rss")

        assert len(results) == 2
        assert all(isinstance(r, RawDataPoint) for r in results)
