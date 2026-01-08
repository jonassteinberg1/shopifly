"""Twitter/X scraper for Shopify complaints and discussions."""

import asyncio
from datetime import datetime
from typing import AsyncIterator

import tweepy
from tweepy import Client

from config import settings
from .base import BaseScraper, DataSource, RawDataPoint


class TwitterScraper(BaseScraper):
    """Scrape Twitter/X for Shopify-related complaints."""

    source = DataSource.TWITTER

    # Search queries targeting pain points
    SEARCH_QUERIES = [
        "shopify frustrated -is:retweet",
        "shopify problem -is:retweet",
        "shopify issue -is:retweet",
        "shopify hate -is:retweet",
        "shopify wish -is:retweet",
        "shopify help -is:retweet",
        "shopify broken -is:retweet",
        "shopify expensive -is:retweet",
        "shopify alternative -is:retweet",
        "shopify app missing -is:retweet",
        '"shopify" "need" "app" -is:retweet',
        '"shopify" "looking for" -is:retweet',
    ]

    def __init__(self):
        self.client = Client(
            bearer_token=settings.twitter_bearer_token,
            wait_on_rate_limit=True,
        )

    async def health_check(self) -> bool:
        """Check Twitter API connectivity."""
        if not settings.twitter_bearer_token:
            print("Twitter bearer token not configured")
            return False
        try:
            loop = asyncio.get_event_loop()
            # Simple API call to verify credentials
            await loop.run_in_executor(
                None, lambda: self.client.get_me()
            )
            return True
        except tweepy.errors.Unauthorized:
            # Bearer token might only support app-only auth
            # Try a search instead
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self.client.search_recent_tweets(
                        "shopify", max_results=10
                    ),
                )
                return True
            except Exception:
                return False
        except Exception:
            return False

    async def scrape(self, limit: int = 100) -> AsyncIterator[RawDataPoint]:
        """Scrape tweets about Shopify pain points.

        Args:
            limit: Maximum tweets to scrape across all queries.

        Yields:
            RawDataPoint for each relevant tweet.
        """
        loop = asyncio.get_event_loop()
        tweets_per_query = max(10, limit // len(self.SEARCH_QUERIES))
        total_scraped = 0

        for query in self.SEARCH_QUERIES:
            if total_scraped >= limit:
                break

            try:
                response = await loop.run_in_executor(
                    None,
                    lambda q=query: self.client.search_recent_tweets(
                        q,
                        max_results=min(tweets_per_query, 100),  # API limit
                        tweet_fields=["created_at", "author_id", "public_metrics", "context_annotations"],
                        expansions=["author_id"],
                        user_fields=["username"],
                    ),
                )

                if not response.data:
                    continue

                # Build author lookup
                authors = {}
                if response.includes and "users" in response.includes:
                    for user in response.includes["users"]:
                        authors[user.id] = user.username

                for tweet in response.data:
                    if total_scraped >= limit:
                        break

                    datapoint = self._tweet_to_datapoint(tweet, authors, query)
                    if datapoint:
                        yield datapoint
                        total_scraped += 1

                await asyncio.sleep(settings.request_delay_seconds)

            except tweepy.errors.TooManyRequests:
                print("Twitter rate limit reached, waiting...")
                await asyncio.sleep(60)
            except Exception as e:
                print(f"Error searching Twitter for '{query}': {e}")
                continue

    def _tweet_to_datapoint(
        self, tweet, authors: dict, query: str
    ) -> RawDataPoint | None:
        """Convert a tweet to a RawDataPoint."""
        try:
            username = authors.get(tweet.author_id, "unknown")
            metrics = tweet.public_metrics or {}

            return RawDataPoint(
                source=self.source,
                source_id=f"twitter_{tweet.id}",
                url=f"https://twitter.com/{username}/status/{tweet.id}",
                title=None,
                content=tweet.text,
                author=username,
                created_at=tweet.created_at or datetime.utcnow(),
                metadata={
                    "query": query,
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "type": "tweet",
                },
            )
        except Exception as e:
            print(f"Error converting tweet: {e}")
            return None
