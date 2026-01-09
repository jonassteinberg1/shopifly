"""Unit tests for Community scraper reply extraction."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from bs4 import BeautifulSoup

from scrapers.community import CommunityScraper
from scrapers.base import DataSource, RawDataPoint


# Sample HTML with multiple replies
SAMPLE_TOPIC_WITH_REPLIES_HTML = """
<html>
<head><title>Test Topic</title></head>
<body>
    <h1 class="topic-title">How to fix inventory sync issues?</h1>

    <!-- Original Post -->
    <article class="post">
        <a class="username">original_poster</a>
        <div class="post-body">
            I'm having major issues with inventory syncing between my warehouse and Shopify.
            Items show as in stock when they're actually sold out. This is causing customer complaints.
            Need help urgently!
        </div>
    </article>

    <!-- Reply 1 -->
    <article class="post">
        <a class="username">helpful_user</a>
        <div class="post-body">
            Have you tried checking your inventory settings? Go to Settings > Inventory and make sure
            "Track quantity" is enabled for all products.
        </div>
    </article>

    <!-- Reply 2 -->
    <article class="post">
        <a class="username">shopify_expert</a>
        <div class="post-body">
            This is a common issue. You might want to use an inventory management app like Stocky
            or Skubana. They handle multi-location sync much better than the built-in system.
        </div>
    </article>

    <!-- Reply 3 -->
    <article class="post">
        <a class="username">another_merchant</a>
        <div class="post-body">
            I had the same problem! Ended up switching to a third-party solution. The native
            inventory system just doesn't cut it for larger stores.
        </div>
    </article>

    <time datetime="2024-01-10T14:30:00Z">January 10, 2024</time>
    <span class="reply-count">3 replies</span>
    <span class="view-count">156 views</span>
</body>
</html>
"""

# Sample HTML with Lithium forum structure (used by Shopify Community)
SAMPLE_LITHIUM_TOPIC_HTML = """
<html>
<body>
    <h1>App not loading properly after update</h1>

    <div class="lia-message-body-content">
        Ever since the last update, my store's app keeps crashing.
        I've tried clearing cache but nothing works. Very frustrated!
    </div>
    <a class="lia-user-name-link">frustrated_merchant</a>

    <div class="lia-message-body-content">
        Try reinstalling the app completely. That fixed it for me.
    </div>
    <a class="lia-user-name-link">tech_helper</a>

    <div class="lia-message-body-content">
        Same issue here. I contacted support and they said they're aware of the bug.
    </div>
    <a class="lia-user-name-link">affected_user</a>

    <span class="replies">2</span>
</body>
</html>
"""

# Sample HTML with no replies
SAMPLE_TOPIC_NO_REPLIES_HTML = """
<html>
<body>
    <h1 class="topic-title">New store question</h1>
    <div class="post-body">
        Just started my Shopify store. Looking for tips on SEO optimization.
    </div>
    <a class="username">new_merchant</a>
    <time datetime="2024-01-15T10:00:00Z">January 15, 2024</time>
    <span class="reply-count">0 replies</span>
</body>
</html>
"""


class TestCommunityScraperReplyExtraction:
    """Tests for Community scraper reply extraction functionality."""

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_extracts_replies_from_topic(self, scraper):
        """Test that replies are extracted from topic HTML."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_WITH_REPLIES_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            assert datapoint is not None
            assert "replies" in datapoint.metadata
            assert len(datapoint.metadata["replies"]) == 3

    @pytest.mark.asyncio
    async def test_reply_content_extracted_correctly(self, scraper):
        """Test that reply content is correctly extracted."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_WITH_REPLIES_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            replies = datapoint.metadata["replies"]
            # First reply should mention inventory settings
            assert any("inventory" in r["content"].lower() for r in replies)
            # Second reply should mention apps
            assert any("stocky" in r["content"].lower() or "skubana" in r["content"].lower() for r in replies)

    @pytest.mark.asyncio
    async def test_reply_authors_extracted(self, scraper):
        """Test that reply authors are extracted when possible."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_WITH_REPLIES_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            replies = datapoint.metadata["replies"]
            # Should have extracted some author names
            authors = [r["author"] for r in replies]
            assert len(authors) == 3

    @pytest.mark.asyncio
    async def test_reply_positions_tracked(self, scraper):
        """Test that reply positions are tracked."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_WITH_REPLIES_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            replies = datapoint.metadata["replies"]
            positions = [r["position"] for r in replies]
            assert positions == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_op_content_separate_from_replies(self, scraper):
        """Test that OP content is stored separately from replies."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_WITH_REPLIES_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            # OP content should be in the main content field
            assert "inventory syncing" in datapoint.content.lower()
            # Replies should not be in the main content
            assert "stocky" not in datapoint.content.lower()

    @pytest.mark.asyncio
    async def test_handles_topic_with_no_replies(self, scraper):
        """Test handling of topics with no replies."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_NO_REPLIES_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            assert datapoint is not None
            assert datapoint.metadata["replies"] == []
            assert "SEO" in datapoint.content

    @pytest.mark.asyncio
    async def test_handles_lithium_forum_structure(self, scraper):
        """Test handling of Lithium forum HTML structure."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_LITHIUM_TOPIC_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            assert datapoint is not None
            # Should have extracted the OP
            assert "crashing" in datapoint.content.lower() or "update" in datapoint.content.lower()
            # Should have extracted replies
            assert len(datapoint.metadata["replies"]) >= 1

    @pytest.mark.asyncio
    async def test_skips_empty_replies(self, scraper):
        """Test that empty/trivial replies are skipped."""
        html_with_empty = """
        <html>
        <body>
            <h1>Test Topic</h1>
            <div class="post-body">Main content here with enough text to be valid.</div>
            <div class="post-body">   </div>
            <div class="post-body">OK</div>
            <div class="post-body">This is a real reply with meaningful content.</div>
        </body>
        </html>
        """
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = html_with_empty

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            # Should skip empty and very short replies
            replies = datapoint.metadata["replies"]
            for reply in replies:
                assert len(reply["content"]) > 5

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_page(self, scraper):
        """Test that None is returned for empty pages."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            assert datapoint is None

    @pytest.mark.asyncio
    async def test_returns_none_for_no_content(self, scraper):
        """Test that None is returned when no content found."""
        html_no_content = "<html><body><h1>Title Only</h1></body></html>"
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = html_no_content

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            assert datapoint is None


class TestCommunityScraperReplyMetadata:
    """Tests for reply metadata in Community scraper."""

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_metadata_includes_reply_count(self, scraper):
        """Test that metadata includes reply count."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_WITH_REPLIES_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            # Should have reply_count in metadata
            assert "reply_count" in datapoint.metadata

    @pytest.mark.asyncio
    async def test_metadata_structure_for_llm(self, scraper):
        """Test that metadata structure is suitable for LLM processing."""
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = SAMPLE_TOPIC_WITH_REPLIES_HTML

            datapoint = await scraper._scrape_topic("https://community.shopify.com/test")

            # Verify structure matches expected format for LLM pipeline
            assert datapoint.title is not None
            assert datapoint.content is not None
            assert isinstance(datapoint.metadata["replies"], list)

            # Each reply should have required fields
            for reply in datapoint.metadata["replies"]:
                assert "content" in reply
                assert "author" in reply
                assert "position" in reply


class TestCommunityScraperMultipleSelectors:
    """Tests for handling multiple HTML selector patterns."""

    @pytest.fixture
    def scraper(self):
        """Create a CommunityScraper instance."""
        return CommunityScraper()

    @pytest.mark.asyncio
    async def test_handles_post_body_selector(self, scraper):
        """Test handling of .post-body selector."""
        html = """
        <html><body>
            <h1>Title</h1>
            <div class="post-body">Original post content here.</div>
            <div class="post-body">First reply content.</div>
        </body></html>
        """
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = html
            datapoint = await scraper._scrape_topic("https://test.com")
            assert datapoint is not None
            assert len(datapoint.metadata["replies"]) == 1

    @pytest.mark.asyncio
    async def test_handles_message_body_selector(self, scraper):
        """Test handling of .message-body selector."""
        html = """
        <html><body>
            <h1>Title</h1>
            <div class="message-body">Original message here.</div>
            <div class="message-body">Reply message here.</div>
        </body></html>
        """
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = html
            datapoint = await scraper._scrape_topic("https://test.com")
            assert datapoint is not None
            assert len(datapoint.metadata["replies"]) == 1

    @pytest.mark.asyncio
    async def test_handles_article_fallback(self, scraper):
        """Test handling of article tag fallback."""
        html = """
        <html><body>
            <h1>Title</h1>
            <article>Original article content here.</article>
            <article>Reply article content here.</article>
            <article>Another reply here.</article>
        </body></html>
        """
        with patch.object(scraper, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = html
            datapoint = await scraper._scrape_topic("https://test.com")
            assert datapoint is not None
            assert len(datapoint.metadata["replies"]) == 2
