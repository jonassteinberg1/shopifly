"""Reddit scraper for Shopify-related discussions."""

import asyncio
from datetime import datetime
from typing import AsyncIterator

import praw
from praw.models import Submission

from config import settings
from .base import BaseScraper, DataSource, RawDataPoint


class RedditScraper(BaseScraper):
    """Scrape Reddit for Shopify pain points and complaints."""

    source = DataSource.REDDIT

    # Keywords indicating pain points or complaints
    PAIN_POINT_KEYWORDS = [
        "frustrated",
        "annoying",
        "hate",
        "wish",
        "missing",
        "need",
        "want",
        "problem",
        "issue",
        "bug",
        "broken",
        "expensive",
        "overpriced",
        "alternative",
        "better",
        "help",
        "stuck",
        "can't",
        "doesn't work",
        "looking for",
        "recommend",
        "suggestion",
        "advice",
    ]

    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )
        self.subreddits = settings.reddit_subreddits

    async def health_check(self) -> bool:
        """Check Reddit API connectivity."""
        try:
            # Run synchronous PRAW call in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.reddit.user.me())
            return True
        except Exception:
            # Read-only mode should still work
            try:
                loop = asyncio.get_event_loop()
                subreddit = await loop.run_in_executor(
                    None, lambda: self.reddit.subreddit("shopify")
                )
                await loop.run_in_executor(None, lambda: list(subreddit.hot(limit=1)))
                return True
            except Exception:
                return False

    async def scrape(self, limit: int = 100) -> AsyncIterator[RawDataPoint]:
        """Scrape Reddit posts and comments about Shopify.

        Args:
            limit: Maximum posts per subreddit.

        Yields:
            RawDataPoint for each relevant post/comment.
        """
        loop = asyncio.get_event_loop()

        for subreddit_name in self.subreddits:
            try:
                subreddit = await loop.run_in_executor(
                    None, lambda name=subreddit_name: self.reddit.subreddit(name)
                )

                # Search for Shopify-related posts
                search_queries = ["shopify", "shopify app", "shopify problem", "shopify help"]

                for query in search_queries:
                    submissions = await loop.run_in_executor(
                        None,
                        lambda q=query: list(
                            subreddit.search(q, sort="new", time_filter="month", limit=limit // 4)
                        ),
                    )

                    for submission in submissions:
                        if self._is_relevant(submission):
                            yield self._submission_to_datapoint(submission)

                            # Also get top-level comments
                            await loop.run_in_executor(
                                None, lambda s=submission: s.comments.replace_more(limit=0)
                            )

                            for comment in submission.comments[:10]:
                                if hasattr(comment, "body") and self._has_pain_keywords(
                                    comment.body
                                ):
                                    yield self._comment_to_datapoint(comment, submission)

                        # Rate limiting
                        await asyncio.sleep(settings.request_delay_seconds)

            except Exception as e:
                print(f"Error scraping r/{subreddit_name}: {e}")
                continue

    def _is_relevant(self, submission: Submission) -> bool:
        """Check if a submission is relevant to Shopify pain points."""
        text = f"{submission.title} {submission.selftext}".lower()
        return "shopify" in text and self._has_pain_keywords(text)

    def _has_pain_keywords(self, text: str) -> bool:
        """Check if text contains pain point indicators."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.PAIN_POINT_KEYWORDS)

    def _submission_to_datapoint(self, submission: Submission) -> RawDataPoint:
        """Convert a Reddit submission to a RawDataPoint."""
        return RawDataPoint(
            source=self.source,
            source_id=f"reddit_post_{submission.id}",
            url=f"https://reddit.com{submission.permalink}",
            title=submission.title,
            content=submission.selftext or "[No body text]",
            author=str(submission.author) if submission.author else "[deleted]",
            created_at=datetime.utcfromtimestamp(submission.created_utc),
            metadata={
                "subreddit": str(submission.subreddit),
                "score": submission.score,
                "num_comments": submission.num_comments,
                "upvote_ratio": submission.upvote_ratio,
                "type": "post",
            },
        )

    def _comment_to_datapoint(self, comment, submission: Submission) -> RawDataPoint:
        """Convert a Reddit comment to a RawDataPoint."""
        return RawDataPoint(
            source=self.source,
            source_id=f"reddit_comment_{comment.id}",
            url=f"https://reddit.com{comment.permalink}",
            title=f"Re: {submission.title}",
            content=comment.body,
            author=str(comment.author) if comment.author else "[deleted]",
            created_at=datetime.utcfromtimestamp(comment.created_utc),
            metadata={
                "subreddit": str(submission.subreddit),
                "score": comment.score,
                "parent_post_id": submission.id,
                "type": "comment",
            },
        )
