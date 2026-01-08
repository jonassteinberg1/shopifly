"""Shopify Community Forums scraper."""

import asyncio
import re
from datetime import datetime
from typing import AsyncIterator
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from .base import BaseScraper, DataSource, RawDataPoint


class CommunityScraper(BaseScraper):
    """Scrape Shopify Community Forums for pain points and feature requests."""

    source = DataSource.COMMUNITY

    BASE_URL = "https://community.shopify.com"

    # Forum boards with high signal for app opportunities
    BOARDS = [
        "/c/shopify-discussion",
        "/c/technical-qa",
        "/c/ecommerce-marketing",
        "/c/shopify-apps",
        "/c/shopify-design",
        "/c/building-shopify-stores",
    ]

    # Keywords indicating pain points
    PAIN_KEYWORDS = [
        "help",
        "problem",
        "issue",
        "not working",
        "broken",
        "bug",
        "frustrated",
        "need",
        "looking for",
        "how to",
        "can't",
        "doesn't",
        "missing",
        "feature request",
        "wish",
        "suggestion",
        "alternative",
    ]

    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=30.0,
            follow_redirects=True,
        )

    async def health_check(self) -> bool:
        """Check if we can access the Shopify Community."""
        try:
            response = await self.client.get(self.BASE_URL)
            return response.status_code == 200
        except Exception:
            return False

    async def scrape(self, limit: int = 100) -> AsyncIterator[RawDataPoint]:
        """Scrape community forum posts.

        Args:
            limit: Maximum posts to scrape.

        Yields:
            RawDataPoint for each relevant post.
        """
        posts_per_board = max(10, limit // len(self.BOARDS))
        total_scraped = 0

        for board in self.BOARDS:
            if total_scraped >= limit:
                break

            try:
                async for post in self._scrape_board(board, posts_per_board):
                    if total_scraped >= limit:
                        break
                    yield post
                    total_scraped += 1
            except Exception as e:
                print(f"Error scraping board {board}: {e}")
                continue

    async def _scrape_board(
        self, board_path: str, limit: int
    ) -> AsyncIterator[RawDataPoint]:
        """Scrape posts from a specific board.

        Args:
            board_path: The board URL path.
            limit: Maximum posts to scrape.

        Yields:
            RawDataPoint for each relevant post.
        """
        board_url = urljoin(self.BASE_URL, board_path)
        page = 1
        posts_scraped = 0

        while posts_scraped < limit:
            try:
                # Fetch board listing page
                html = await self._fetch_page(f"{board_url}?page={page}")
                if not html:
                    break

                soup = BeautifulSoup(html, "html.parser")

                # Find topic links (adjust selectors based on actual HTML structure)
                topics = soup.select("a.topic-title, a.title, .topic-list-item a")

                if not topics:
                    # Try alternative selectors
                    topics = soup.select("[data-topic-id] a, .topic-link")

                if not topics:
                    break

                for topic in topics:
                    if posts_scraped >= limit:
                        break

                    topic_url = topic.get("href", "")
                    if not topic_url:
                        continue

                    topic_url = urljoin(self.BASE_URL, topic_url)

                    # Fetch and parse the topic
                    datapoint = await self._scrape_topic(topic_url)
                    if datapoint and self._is_relevant(datapoint):
                        yield datapoint
                        posts_scraped += 1

                    await asyncio.sleep(settings.request_delay_seconds)

                page += 1

            except Exception as e:
                print(f"Error on page {page} of {board_path}: {e}")
                break

    async def _scrape_topic(self, topic_url: str) -> RawDataPoint | None:
        """Scrape a single topic/thread.

        Args:
            topic_url: Full URL to the topic.

        Returns:
            RawDataPoint if successfully scraped, None otherwise.
        """
        try:
            html = await self._fetch_page(topic_url)
            if not html:
                return None

            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title_elem = soup.select_one("h1, .topic-title, .thread-title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Extract first post content
            post_elem = soup.select_one(
                ".post-body, .topic-body, .message-body, .cooked, article"
            )
            content = post_elem.get_text(strip=True) if post_elem else ""

            if not content:
                return None

            # Extract author
            author_elem = soup.select_one(
                ".author-name, .username, .user-link, [data-user-card]"
            )
            author = author_elem.get_text(strip=True) if author_elem else "Anonymous"

            # Extract date
            date_elem = soup.select_one("time, .post-date, .relative-date")
            date_str = date_elem.get("datetime") or date_elem.get_text(strip=True) if date_elem else ""
            created_at = self._parse_date(date_str)

            # Extract metadata
            replies = self._extract_number(soup, ".reply-count, .replies")
            views = self._extract_number(soup, ".view-count, .views")
            likes = self._extract_number(soup, ".like-count, .likes")

            # Generate unique ID from URL
            topic_id = re.search(r"/t/[^/]+/(\d+)", topic_url)
            source_id = topic_id.group(1) if topic_id else str(hash(topic_url))

            return RawDataPoint(
                source=self.source,
                source_id=f"community_{source_id}",
                url=topic_url,
                title=title,
                content=content,
                author=author,
                created_at=created_at,
                metadata={
                    "replies": replies,
                    "views": views,
                    "likes": likes,
                    "type": "topic",
                },
            )

        except Exception as e:
            print(f"Error scraping topic {topic_url}: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_page(self, url: str) -> str | None:
        """Fetch a page with retry logic."""
        response = await self.client.get(url)
        if response.status_code == 200:
            return response.text
        return None

    def _is_relevant(self, datapoint: RawDataPoint) -> bool:
        """Check if a post is relevant (contains pain point indicators)."""
        text = datapoint.full_text.lower()
        return any(keyword in text for keyword in self.PAIN_KEYWORDS)

    def _extract_number(self, soup: BeautifulSoup, selector: str) -> int:
        """Extract a number from an element."""
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            numbers = re.findall(r"\d+", text)
            if numbers:
                return int(numbers[0])
        return 0

    def _parse_date(self, date_str: str) -> datetime:
        """Parse various date formats."""
        if not date_str:
            return datetime.utcnow()

        # Try ISO format first
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass

        # Handle relative dates
        date_str = date_str.lower()
        now = datetime.utcnow()

        if "today" in date_str or "just now" in date_str:
            return now

        match = re.search(r"(\d+)\s*(day|week|month|year|hour|minute)s?\s*ago", date_str)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit == "minute":
                return now
            elif unit == "hour":
                return now
            elif unit == "day":
                return now.replace(day=max(1, now.day - amount))
            elif unit == "week":
                return now.replace(day=max(1, now.day - amount * 7))
            elif unit == "month":
                return now.replace(month=max(1, now.month - amount))
            elif unit == "year":
                return now.replace(year=now.year - amount)

        return now

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
