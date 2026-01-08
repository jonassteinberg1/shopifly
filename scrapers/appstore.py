"""Shopify App Store review scraper."""

import asyncio
import re
from datetime import datetime
from typing import AsyncIterator

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from .base import BaseScraper, DataSource, RawDataPoint


class AppStoreScraper(BaseScraper):
    """Scrape Shopify App Store reviews for pain points."""

    source = DataSource.APP_STORE

    BASE_URL = "https://apps.shopify.com"

    # Popular app categories to scrape
    APP_CATEGORIES = [
        "store-design",
        "marketing",
        "sales-and-conversion",
        "orders-and-shipping",
        "inventory-management",
        "customer-support",
        "finances",
        "productivity",
        "reporting",
    ]

    # Target apps known to have competitors or gaps (expand this list)
    TARGET_APPS = [
        "smile-io",
        "loox",
        "klaviyo-email-marketing-sms",
        "privy",
        "oberlo",
        "printful",
        "judge-me",
        "yotpo-product-reviews-photos",
        "shopify-inbox",
        "shopify-email",
        "shopify-flow",
        "google-shopping",
        "facebook-channel",
        "mailchimp",
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
        """Check if we can access the Shopify App Store."""
        try:
            response = await self.client.get(self.BASE_URL)
            return response.status_code == 200
        except Exception:
            return False

    async def scrape(self, limit: int = 100) -> AsyncIterator[RawDataPoint]:
        """Scrape app reviews, focusing on low ratings.

        Args:
            limit: Maximum reviews per app.

        Yields:
            RawDataPoint for each review.
        """
        apps_per_limit = limit // len(self.TARGET_APPS) or 1

        for app_slug in self.TARGET_APPS:
            try:
                async for review in self._scrape_app_reviews(app_slug, apps_per_limit):
                    yield review
            except Exception as e:
                print(f"Error scraping app {app_slug}: {e}")
                continue

    async def _scrape_app_reviews(
        self, app_slug: str, limit: int
    ) -> AsyncIterator[RawDataPoint]:
        """Scrape reviews for a specific app.

        Args:
            app_slug: The app's URL slug.
            limit: Maximum reviews to scrape.

        Yields:
            RawDataPoint for each review.
        """
        app_url = f"{self.BASE_URL}/{app_slug}"
        reviews_url = f"{app_url}/reviews"

        page = 1
        reviews_scraped = 0

        while reviews_scraped < limit:
            try:
                html = await self._fetch_page(f"{reviews_url}?page={page}&sort_by=recent")
                if not html:
                    break

                soup = BeautifulSoup(html, "html.parser")
                reviews = soup.select(".review-listing")

                if not reviews:
                    break

                for review in reviews:
                    if reviews_scraped >= limit:
                        break

                    datapoint = self._parse_review(review, app_slug, app_url)
                    if datapoint and self._is_negative_review(datapoint):
                        yield datapoint
                        reviews_scraped += 1

                page += 1
                await asyncio.sleep(settings.request_delay_seconds)

            except Exception as e:
                print(f"Error on page {page} for {app_slug}: {e}")
                break

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_page(self, url: str) -> str | None:
        """Fetch a page with retry logic."""
        response = await self.client.get(url)
        if response.status_code == 200:
            return response.text
        return None

    def _parse_review(
        self, review_element, app_slug: str, app_url: str
    ) -> RawDataPoint | None:
        """Parse a review HTML element into a RawDataPoint."""
        try:
            # Extract rating
            rating_elem = review_element.select_one(".ui-star-rating")
            rating = self._extract_rating(rating_elem)

            # Extract review text
            body_elem = review_element.select_one(".review-listing-body")
            body = body_elem.get_text(strip=True) if body_elem else ""

            if not body:
                return None

            # Extract metadata
            header = review_element.select_one(".review-listing-header")
            store_name = ""
            date_str = ""
            if header:
                store_elem = header.select_one(".review-listing-header__text")
                store_name = store_elem.get_text(strip=True) if store_elem else ""

                date_elem = header.select_one(".review-listing-header__date")
                date_str = date_elem.get_text(strip=True) if date_elem else ""

            # Generate unique ID
            review_id = f"{app_slug}_{hash(body)}"

            return RawDataPoint(
                source=self.source,
                source_id=f"appstore_{review_id}",
                url=app_url,
                title=f"Review of {app_slug} ({rating}/5 stars)",
                content=body,
                author=store_name or "Anonymous",
                created_at=self._parse_date(date_str),
                metadata={
                    "app_slug": app_slug,
                    "rating": rating,
                    "type": "review",
                },
            )
        except Exception as e:
            print(f"Error parsing review: {e}")
            return None

    def _extract_rating(self, rating_elem) -> int:
        """Extract numeric rating from star rating element."""
        if not rating_elem:
            return 0
        # Look for aria-label like "4 out of 5 stars"
        aria_label = rating_elem.get("aria-label", "")
        match = re.search(r"(\d+)\s*out of\s*(\d+)", aria_label)
        if match:
            return int(match.group(1))
        # Fallback: count filled stars
        filled = rating_elem.select(".ui-star-rating__star--filled")
        return len(filled)

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime."""
        # Handle relative dates like "2 days ago", "1 month ago"
        date_str = date_str.lower().strip()
        now = datetime.utcnow()

        if "today" in date_str or "just now" in date_str:
            return now

        match = re.search(r"(\d+)\s*(day|week|month|year)s?\s*ago", date_str)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit == "day":
                return now.replace(day=max(1, now.day - amount))
            elif unit == "week":
                return now.replace(day=max(1, now.day - amount * 7))
            elif unit == "month":
                return now.replace(month=max(1, now.month - amount))
            elif unit == "year":
                return now.replace(year=now.year - amount)

        return now

    def _is_negative_review(self, datapoint: RawDataPoint) -> bool:
        """Check if a review indicates problems/pain points."""
        rating = datapoint.metadata.get("rating", 5)
        # Focus on 1-3 star reviews
        if rating <= 3:
            return True
        # Also include higher-rated reviews that mention issues
        pain_words = ["but", "however", "wish", "missing", "would be nice", "only issue"]
        return any(word in datapoint.content.lower() for word in pain_words)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
