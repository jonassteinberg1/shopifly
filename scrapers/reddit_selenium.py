"""Reddit scraper for Shopify-related discussions.

This scraper uses httpx for RSS feeds (primary, most reliable) and
Selenium as a fallback for HTML parsing when needed.
"""

import asyncio
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from typing import AsyncIterator

import httpx
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from .base import BaseScraper, DataSource, RawDataPoint


# Default headers for httpx requests
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# RSS endpoints for different sort types
RSS_ENDPOINTS = {
    "hot": "https://www.reddit.com/r/shopify/.rss",
    "new": "https://www.reddit.com/r/shopify/new/.rss",
    "top_day": "https://www.reddit.com/r/shopify/top/.rss?t=day",
    "top_week": "https://www.reddit.com/r/shopify/top/.rss?t=week",
    "top_month": "https://www.reddit.com/r/shopify/top/.rss?t=month",
    "top_year": "https://www.reddit.com/r/shopify/top/.rss?t=year",
    "top_all": "https://www.reddit.com/r/shopify/top/.rss?t=all",
    "rising": "https://www.reddit.com/r/shopify/rising/.rss",
}


class RedditSeleniumScraper(BaseScraper):
    """Scrape Reddit for Shopify pain points using RSS/httpx with Selenium fallback."""

    source = DataSource.REDDIT

    PAIN_POINT_KEYWORDS = [
        "frustrated", "annoying", "hate", "wish", "missing", "need", "want",
        "problem", "issue", "bug", "broken", "expensive", "overpriced",
        "alternative", "better", "help", "stuck", "can't", "doesn't work",
        "looking for", "recommend", "suggestion", "advice",
    ]

    def __init__(self, headless: bool = True, request_delay: float = 2.0):
        """Initialize the scraper.

        Args:
            headless: Run browser in headless mode (default True).
            request_delay: Delay between requests in seconds (default 2.0).
        """
        self.headless = headless
        self.request_delay = request_delay
        self._driver = None
        self._client = None

    def _get_client(self) -> httpx.Client:
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.Client(
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
                timeout=30,
            )
        return self._client

    def _close_client(self):
        """Close httpx client."""
        if self._client:
            self._client.close()
            self._client = None

    def _get_driver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver."""
        if self._driver is None:
            options = Options()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
        return self._driver

    def _close_driver(self):
        """Close the WebDriver if open."""
        if self._driver:
            self._driver.quit()
            self._driver = None

    async def health_check(self) -> bool:
        """Check if we can connect to Reddit."""
        try:
            client = self._get_client()
            resp = client.get(RSS_ENDPOINTS["hot"])
            return resp.status_code == 200 and "<feed" in resp.text
        except Exception:
            return False
        finally:
            self._close_client()

    async def scrape(self, limit: int = 100) -> AsyncIterator[RawDataPoint]:
        """Scrape Reddit posts about Shopify.

        Args:
            limit: Maximum posts to scrape.

        Yields:
            RawDataPoint for each relevant post.
        """
        loop = asyncio.get_event_loop()
        posts = await loop.run_in_executor(None, self._scrape_posts, limit)

        for post in posts:
            yield post

    def _scrape_posts(self, limit: int) -> list[RawDataPoint]:
        """Scrape posts using RSS feeds."""
        results = []
        seen_ids = set()

        try:
            client = self._get_client()

            for sort_type, url in RSS_ENDPOINTS.items():
                if len(results) >= limit:
                    break

                posts = self._fetch_rss_posts(client, url)
                for post in posts:
                    if len(results) >= limit:
                        break
                    if post.source_id not in seen_ids:
                        seen_ids.add(post.source_id)
                        if self._is_relevant(post.title or "", post.content):
                            results.append(post)

                time.sleep(self.request_delay)

        finally:
            self._close_client()

        return results

    def _fetch_rss_posts(self, client: httpx.Client, url: str) -> list[RawDataPoint]:
        """Fetch posts from an RSS endpoint."""
        results = []
        try:
            resp = client.get(url)
            if resp.status_code != 200:
                return results

            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                try:
                    datapoint = self._parse_rss_entry(entry, ns)
                    if datapoint:
                        results.append(datapoint)
                except Exception:
                    continue

        except Exception:
            pass

        return results

    def _parse_rss_entry(self, entry, ns: dict) -> RawDataPoint | None:
        """Parse an RSS entry into a RawDataPoint."""
        title_elem = entry.find("atom:title", ns)
        title = title_elem.text if title_elem is not None else ""

        link_elem = entry.find("atom:link[@href]", ns)
        url = link_elem.get("href") if link_elem is not None else ""

        author_elem = entry.find("atom:author/atom:name", ns)
        author = author_elem.text if author_elem is not None else ""
        author = author.replace("/u/", "") if author else "[unknown]"

        content_elem = entry.find("atom:content", ns)
        content_html = content_elem.text if content_elem is not None else ""
        selftext = _extract_selftext_from_html(content_html)

        post_id = ""
        if url and "/comments/" in url:
            parts = url.split("/comments/")
            if len(parts) > 1:
                post_id = parts[1].split("/")[0]

        updated_elem = entry.find("atom:updated", ns)
        updated_str = updated_elem.text if updated_elem is not None else ""
        created_at = datetime.utcnow()
        if updated_str:
            try:
                created_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            except Exception:
                pass

        return RawDataPoint(
            source=self.source,
            source_id=f"reddit_post_{post_id}",
            url=url,
            title=title,
            content=selftext or "[No body text]",
            author=author,
            created_at=created_at,
            metadata={
                "subreddit": "shopify",
                "type": "post",
                "scrape_method": "rss",
            },
        )

    def _is_relevant(self, title: str, selftext: str) -> bool:
        """Check if a post is relevant to Shopify pain points."""
        text = f"{title} {selftext}".lower()
        return "shopify" in text or self._has_pain_keywords(text)

    def _has_pain_keywords(self, text: str) -> bool:
        """Check if text contains pain point indicators."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.PAIN_POINT_KEYWORDS)


# ============================================================================
# Simple standalone functions
# ============================================================================

def scrape_reddit_posts(
    limit: int = 25,
    sort_types: list[str] | None = None,
    include_comments: bool = False,
    request_delay: float = 2.0,
    debug: bool = False,
) -> list[dict]:
    """Scrape Reddit r/shopify posts with optional comments.

    Args:
        limit: Maximum number of posts to fetch.
        sort_types: List of sort types to use. Options: hot, new, top_day, top_week,
                   top_month, top_year, top_all, rising. Default: ["hot", "new", "top_week"].
        include_comments: Whether to fetch comments for each post.
        request_delay: Delay between requests in seconds.
        debug: Print debug information.

    Returns:
        List of dicts with 'title', 'selftext', 'comments', and other metadata.
    """
    if sort_types is None:
        sort_types = ["hot", "new", "top_week"]

    results = []
    seen_ids = set()

    client = httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=30)

    try:
        for sort_type in sort_types:
            if len(results) >= limit:
                break

            url = RSS_ENDPOINTS.get(sort_type)
            if not url:
                if debug:
                    print(f"Unknown sort type: {sort_type}")
                continue

            if debug:
                print(f"Fetching {sort_type} posts...")

            posts = _fetch_rss_simple(client, url, debug)

            for post in posts:
                if len(results) >= limit:
                    break

                if post["id"] and post["id"] not in seen_ids:
                    seen_ids.add(post["id"])

                    if include_comments and post["url"]:
                        if debug:
                            print(f"  Fetching comments for: {post['title'][:50]}...")
                        time.sleep(request_delay)
                        post["comments"] = _fetch_post_comments(client, post["id"], debug)
                    else:
                        post["comments"] = []

                    results.append(post)

            time.sleep(request_delay)

        if debug:
            print(f"Total posts scraped: {len(results)}")

    finally:
        client.close()

    return results


def _fetch_rss_simple(client: httpx.Client, url: str, debug: bool = False) -> list[dict]:
    """Fetch posts from an RSS endpoint."""
    results = []

    try:
        resp = client.get(url)
        if resp.status_code != 200:
            if debug:
                print(f"  HTTP {resp.status_code} from {url}")
            return results

        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        entries = root.findall("atom:entry", ns)
        if debug:
            print(f"  Found {len(entries)} entries")

        for entry in entries:
            try:
                title_elem = entry.find("atom:title", ns)
                title = title_elem.text if title_elem is not None else ""

                link_elem = entry.find("atom:link[@href]", ns)
                url = link_elem.get("href") if link_elem is not None else ""

                author_elem = entry.find("atom:author/atom:name", ns)
                author = author_elem.text if author_elem is not None else ""
                author = author.replace("/u/", "") if author else ""

                content_elem = entry.find("atom:content", ns)
                content_html = content_elem.text if content_elem is not None else ""
                selftext = _extract_selftext_from_html(content_html)

                post_id = ""
                if url and "/comments/" in url:
                    parts = url.split("/comments/")
                    if len(parts) > 1:
                        post_id = parts[1].split("/")[0]

                updated_elem = entry.find("atom:updated", ns)
                updated_str = updated_elem.text if updated_elem is not None else ""

                results.append({
                    "title": title,
                    "selftext": selftext,
                    "id": post_id,
                    "url": url,
                    "author": author,
                    "updated": updated_str,
                    "score": 0,
                    "comments": [],
                })

            except Exception as e:
                if debug:
                    print(f"  Error parsing entry: {e}")
                continue

    except Exception as e:
        if debug:
            print(f"  Error fetching RSS: {e}")

    return results


def _fetch_post_comments(client: httpx.Client, post_id: str, debug: bool = False) -> list[dict]:
    """Fetch comments for a specific post."""
    comments = []
    url = f"https://www.reddit.com/r/shopify/comments/{post_id}/.rss"

    try:
        resp = client.get(url)
        if resp.status_code != 200:
            if debug:
                print(f"    HTTP {resp.status_code} fetching comments")
            return comments

        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        entries = root.findall("atom:entry", ns)

        # First entry is usually the post itself, rest are comments
        for i, entry in enumerate(entries):
            if i == 0:
                # Skip the post itself
                continue

            try:
                author_elem = entry.find("atom:author/atom:name", ns)
                author = author_elem.text if author_elem is not None else ""
                author = author.replace("/u/", "") if author else ""

                content_elem = entry.find("atom:content", ns)
                content_html = content_elem.text if content_elem is not None else ""
                content = _extract_selftext_from_html(content_html)

                link_elem = entry.find("atom:link[@href]", ns)
                comment_url = link_elem.get("href") if link_elem is not None else ""

                updated_elem = entry.find("atom:updated", ns)
                updated_str = updated_elem.text if updated_elem is not None else ""

                comments.append({
                    "author": author,
                    "content": content,
                    "url": comment_url,
                    "updated": updated_str,
                })

            except Exception as e:
                if debug:
                    print(f"    Error parsing comment: {e}")
                continue

        if debug:
            print(f"    Found {len(comments)} comments")

    except Exception as e:
        if debug:
            print(f"    Error fetching comments: {e}")

    return comments


def _extract_selftext_from_html(html_content: str) -> str:
    """Extract selftext from RSS HTML content."""
    if not html_content:
        return ""

    html_content = unescape(html_content)

    text = re.sub(r"<br\s*/?>", "\n", html_content, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    text = re.sub(r"\[link\]\s*\[comments\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"submitted by.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)

    return text.strip()


# Legacy alias for backwards compatibility
def scrape_reddit_simple(limit: int = 25, debug: bool = False, method: str = "auto") -> list[dict]:
    """Legacy function - use scrape_reddit_posts instead."""
    return scrape_reddit_posts(limit=limit, debug=debug)


if __name__ == "__main__":
    print("Scraping r/shopify posts with comments...")
    posts = scrape_reddit_posts(limit=5, include_comments=True, debug=True)

    for i, post in enumerate(posts, 1):
        print(f"\n{'='*60}")
        print(f"Post {i}: {post['title']}")
        print(f"Selftext: {post['selftext'][:200]}..." if len(post['selftext']) > 200 else f"Selftext: {post['selftext']}")
        print(f"Comments: {len(post['comments'])}")
        for j, comment in enumerate(post['comments'][:3], 1):
            print(f"  Comment {j} by {comment['author']}: {comment['content'][:100]}...")
