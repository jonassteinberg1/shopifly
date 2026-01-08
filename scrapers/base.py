"""Base scraper class and common data models."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import AsyncIterator

from pydantic import BaseModel, Field


class DataSource(str, Enum):
    """Enumeration of data sources."""

    REDDIT = "reddit"
    APP_STORE = "shopify_app_store"
    TWITTER = "twitter"
    COMMUNITY = "shopify_community"


class RawDataPoint(BaseModel):
    """A single raw data point from any source."""

    source: DataSource
    source_id: str = Field(description="Unique identifier from the source platform")
    url: str = Field(description="Direct URL to the content")
    title: str | None = Field(default=None, description="Title if applicable")
    content: str = Field(description="The actual text content")
    author: str | None = Field(default=None, description="Username or author")
    created_at: datetime = Field(description="When the content was created")
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict, description="Source-specific metadata")

    @property
    def full_text(self) -> str:
        """Combine title and content for analysis."""
        if self.title:
            return f"{self.title}\n\n{self.content}"
        return self.content


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    source: DataSource

    @abstractmethod
    async def scrape(self, limit: int = 100) -> AsyncIterator[RawDataPoint]:
        """Scrape data from the source.

        Args:
            limit: Maximum number of items to scrape.

        Yields:
            RawDataPoint instances.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the scraper can connect to its data source.

        Returns:
            True if connection is healthy, False otherwise.
        """
        pass
