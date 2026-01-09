"""Shopify App Store review scraper using Selenium for JavaScript-rendered content."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import AsyncIterator, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import settings
from .base import BaseScraper, DataSource, RawDataPoint


class AppStoreScraper(BaseScraper):
    """Scrape Shopify App Store reviews for pain points.

    Uses Selenium to render JavaScript content since the Shopify App Store
    is a single-page application (SPA).
    """

    source = DataSource.APP_STORE

    BASE_URL = "https://apps.shopify.com"

    # Target apps with verified working URL slugs
    TARGET_APPS = [
        "flow",                    # Shopify Flow - automation
        "inbox",                   # Shopify Inbox - messaging
        "shop",                    # Shop app
        "search-and-discovery",    # Search & Discovery
        "shopify-forms",           # Shopify Forms
        "shopify-bundles",         # Shopify Bundles
        "shopify-subscriptions",   # Shopify Subscriptions
        "translate-and-adapt",     # Translate & Adapt
        "collective",              # Shopify Collective
        "digital-downloads",       # Digital Downloads
    ]

    def __init__(self, headless: bool = True):
        """Initialize the scraper.

        Args:
            headless: Run browser in headless mode (default True).
        """
        self.headless = headless
        self._driver: Optional[webdriver.Chrome] = None

    def _get_driver(self) -> webdriver.Chrome:
        """Get or create the Selenium WebDriver."""
        if self._driver is None:
            options = Options()
            if self.headless:
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            self._driver = webdriver.Chrome(options=options)
        return self._driver

    def _close_driver(self) -> None:
        """Close the WebDriver if open."""
        if self._driver:
            self._driver.quit()
            self._driver = None

    async def health_check(self) -> bool:
        """Check if we can access the Shopify App Store."""
        try:
            driver = self._get_driver()
            driver.get(self.BASE_URL)
            # Wait for page to have a title
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "title"))
            )
            return "Shopify" in driver.title
        except Exception:
            return False

    async def scrape(self, limit: int = 100) -> AsyncIterator[RawDataPoint]:
        """Scrape app reviews, focusing on low ratings.

        Args:
            limit: Maximum total reviews to scrape across all apps.

        Yields:
            RawDataPoint for each review.
        """
        reviews_per_app = max(1, limit // len(self.TARGET_APPS))
        total_scraped = 0

        try:
            for app_slug in self.TARGET_APPS:
                if total_scraped >= limit:
                    break

                try:
                    async for review in self._scrape_app_reviews(
                        app_slug,
                        min(reviews_per_app, limit - total_scraped)
                    ):
                        yield review
                        total_scraped += 1
                        if total_scraped >= limit:
                            break
                except Exception as e:
                    print(f"Error scraping app {app_slug}: {e}")
                    continue
        finally:
            self._close_driver()

    async def _scrape_app_reviews(
        self, app_slug: str, limit: int
    ) -> AsyncIterator[RawDataPoint]:
        """Scrape reviews for a specific app.

        Args:
            app_slug: The app's URL slug.
            limit: Maximum reviews to scrape for this app.

        Yields:
            RawDataPoint for each review.
        """
        app_url = f"{self.BASE_URL}/{app_slug}"
        reviews_url = f"{app_url}/reviews"
        reviews_scraped = 0
        seen_review_ids: set[str] = set()

        driver = self._get_driver()

        # Start with 1-star reviews to get pain points first
        rating_filters = [1, 2, 3, 4, 5]

        for rating_filter in rating_filters:
            if reviews_scraped >= limit:
                break

            filter_url = f"{reviews_url}?ratings%5B%5D={rating_filter}"

            try:
                driver.get(filter_url)
                # Wait for reviews to load
                await asyncio.sleep(3)

                # Parse the rendered HTML
                soup = BeautifulSoup(driver.page_source, "html.parser")
                reviews = self._extract_reviews_from_soup(soup, app_slug, app_url)

                for review in reviews:
                    if reviews_scraped >= limit:
                        break

                    # Skip duplicates
                    if review.source_id in seen_review_ids:
                        continue
                    seen_review_ids.add(review.source_id)

                    # Apply pain point filter
                    if self._is_negative_review(review):
                        yield review
                        reviews_scraped += 1

                await asyncio.sleep(settings.request_delay_seconds)

            except Exception as e:
                print(f"Error on rating {rating_filter} for {app_slug}: {e}")
                continue

    def _extract_reviews_from_soup(
        self, soup: BeautifulSoup, app_slug: str, app_url: str
    ) -> list[RawDataPoint]:
        """Extract reviews from parsed HTML.

        Args:
            soup: Parsed BeautifulSoup object.
            app_slug: The app's URL slug.
            app_url: The app's full URL.

        Returns:
            List of RawDataPoint objects.
        """
        reviews: list[RawDataPoint] = []

        # Find all star rating elements (skip first 2 which are app summary)
        star_elements = soup.find_all(
            attrs={"aria-label": lambda x: x and "out of 5 stars" in x}
        )[2:]  # Skip app-level ratings

        for star_el in star_elements:
            try:
                datapoint = self._parse_review_element(star_el, app_slug, app_url)
                if datapoint:
                    reviews.append(datapoint)
            except Exception as e:
                print(f"Error parsing review element: {e}")
                continue

        return reviews

    def _parse_review_element(
        self, star_element, app_slug: str, app_url: str
    ) -> Optional[RawDataPoint]:
        """Parse a single review from its star rating element.

        Args:
            star_element: BeautifulSoup element containing the star rating.
            app_slug: The app's URL slug.
            app_url: The app's full URL.

        Returns:
            RawDataPoint or None if parsing fails.
        """
        # Extract rating from aria-label
        rating_text = star_element.get("aria-label", "")
        rating_match = re.search(r"(\d+) out of 5", rating_text)
        rating = int(rating_match.group(1)) if rating_match else 0

        # Navigate up to find the review container
        parent = star_element
        for _ in range(15):
            parent = parent.parent
            if parent is None:
                return None
            classes = parent.get("class", [])
            # Look for the review container class
            if "tw-order-2" in classes or "lg:tw-col-span-3" in classes:
                break

        if parent is None:
            return None

        # Extract text content
        text = parent.get_text(separator=" ", strip=True)
        if not text or len(text) < 10:
            return None

        # Extract date (format: "Month DD, YYYY" at the beginning)
        date_match = re.search(r"^([A-Z][a-z]+ \d{1,2}, \d{4})", text)
        date_str = date_match.group(1) if date_match else ""

        # Extract review content (everything after date)
        content = text
        if date_match:
            content = text[len(date_str):].strip()

        # Clean up "Show more/less" and other UI text
        content = re.sub(r"Show (more|less).*$", "", content, flags=re.IGNORECASE).strip()
        content = re.sub(r"^\s*Edited\s*", "", content).strip()

        if not content or len(content) < 10:
            return None

        # Generate unique ID from content hash
        review_id = f"{app_slug}_{hash(content)}"

        return RawDataPoint(
            source=self.source,
            source_id=f"appstore_{review_id}",
            url=app_url,
            title=f"Review of {app_slug} ({rating}/5 stars)",
            content=content,
            author="Anonymous",  # Author info not readily available in new UI
            created_at=self._parse_date(date_str),
            metadata={
                "app_slug": app_slug,
                "rating": rating,
                "type": "review",
            },
        )

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime.

        Args:
            date_str: Date string like "December 15, 2025" or relative dates.

        Returns:
            Parsed datetime object.
        """
        if not date_str:
            return datetime.utcnow()

        date_str = date_str.strip()

        # Try parsing "Month DD, YYYY" format
        try:
            return datetime.strptime(date_str, "%B %d, %Y")
        except ValueError:
            pass

        # Handle relative dates
        date_str_lower = date_str.lower()
        now = datetime.utcnow()

        if "today" in date_str_lower or "just now" in date_str_lower:
            return now

        match = re.search(r"(\d+)\s*(day|week|month|year)s?\s*ago", date_str_lower)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit == "day":
                return now - timedelta(days=amount)
            elif unit == "week":
                return now - timedelta(weeks=amount)
            elif unit == "month":
                return now - timedelta(days=amount * 30)
            elif unit == "year":
                return now - timedelta(days=amount * 365)

        return now

    def _is_negative_review(self, datapoint: RawDataPoint) -> bool:
        """Check if a review indicates problems/pain points.

        Args:
            datapoint: The review data point.

        Returns:
            True if the review contains pain points.
        """
        rating = datapoint.metadata.get("rating", 5)

        # Focus on 1-3 star reviews
        if rating <= 3:
            return True

        # Also include higher-rated reviews that mention issues
        pain_words = [
            "but", "however", "wish", "missing", "would be nice",
            "only issue", "could be better", "needs improvement",
            "frustrating", "annoying", "difficult", "confusing",
            "doesn't work", "not working", "broken", "bug",
        ]
        content_lower = datapoint.content.lower()
        return any(word in content_lower for word in pain_words)

    async def close(self) -> None:
        """Close the browser."""
        self._close_driver()
