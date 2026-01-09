"""LLM-based classifier for analyzing scraped content."""

from __future__ import annotations

import json
from enum import Enum
from typing import AsyncIterator

import anthropic
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from scrapers.base import RawDataPoint


class ProblemCategory(str, Enum):
    """Categories for Shopify merchant problems."""

    ADMIN = "admin"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    LOYALTY = "loyalty"
    PAYMENTS = "payments"
    FULFILLMENT = "fulfillment"
    INVENTORY = "inventory"
    CUSTOMER_SUPPORT = "customer_support"
    DESIGN = "design"
    SEO = "seo"
    INTEGRATIONS = "integrations"
    PERFORMANCE = "performance"
    PRICING = "pricing"
    OTHER = "other"


class ClassifiedInsight(BaseModel):
    """A classified and analyzed insight from raw data."""

    # Original data reference
    source_id: str = Field(description="ID linking back to raw data")
    source_url: str = Field(description="URL of the original content")

    # Extracted insights
    problem_statement: str = Field(
        description="Concise description of the problem (1-2 sentences)"
    )
    category: ProblemCategory = Field(description="Primary problem category")
    secondary_categories: list[ProblemCategory] = Field(
        default_factory=list, description="Additional relevant categories"
    )

    # Scoring
    frustration_level: int = Field(
        ge=1, le=5, description="1=mild annoyance, 5=severe frustration"
    )
    clarity_score: int = Field(
        ge=1, le=5, description="How clearly the problem is described"
    )

    # Signals
    willingness_to_pay: bool = Field(
        description="Does the content indicate willingness to pay for a solution?"
    )
    wtp_quotes: list[str] = Field(
        default_factory=list, description="Quotes indicating willingness to pay"
    )

    current_workaround: str | None = Field(
        default=None, description="Any workaround mentioned"
    )

    # Keywords for clustering
    keywords: list[str] = Field(
        default_factory=list, description="Key terms for clustering similar problems"
    )

    # Original content summary
    original_title: str | None = None
    content_snippet: str = Field(description="First 500 chars of original content")


CLASSIFICATION_PROMPT = """Analyze this Shopify merchant feedback and extract structured insights.

<content>
Title: {title}
Source: {source}
Content: {content}
</content>

Extract the following information in JSON format:

1. problem_statement: A concise 1-2 sentence description of the core problem or need
2. category: Primary category from: admin, analytics, marketing, loyalty, payments, fulfillment, inventory, customer_support, design, seo, integrations, performance, pricing, other
3. secondary_categories: List of other relevant categories (can be empty)
4. frustration_level: 1-5 scale (1=mild annoyance, 5=severe frustration)
5. clarity_score: 1-5 scale of how clearly the problem is described
6. willingness_to_pay: true/false - does this indicate they'd pay for a solution?
7. wtp_quotes: Any quotes that suggest willingness to pay (empty list if none)
8. current_workaround: Any workaround they mention using (null if none)
9. keywords: 3-5 key terms for clustering similar problems

Respond with ONLY valid JSON, no other text:
{{
    "problem_statement": "...",
    "category": "...",
    "secondary_categories": [...],
    "frustration_level": N,
    "clarity_score": N,
    "willingness_to_pay": true/false,
    "wtp_quotes": [...],
    "current_workaround": "..." or null,
    "keywords": [...]
}}"""


class Classifier:
    """LLM-based classifier for analyzing merchant feedback."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def classify(self, datapoint: RawDataPoint) -> ClassifiedInsight | None:
        """Classify a single data point.

        Args:
            datapoint: Raw scraped data to analyze.

        Returns:
            ClassifiedInsight if successful, None otherwise.
        """
        try:
            prompt = CLASSIFICATION_PROMPT.format(
                title=datapoint.title or "No title",
                source=datapoint.source.value,
                content=datapoint.content[:2000],  # Limit content length
            )

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract JSON from response
            response_text = response.content[0].text.strip()

            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            result = json.loads(response_text)

            return ClassifiedInsight(
                source_id=datapoint.source_id,
                source_url=datapoint.url,
                problem_statement=result["problem_statement"],
                category=ProblemCategory(result["category"]),
                secondary_categories=[
                    ProblemCategory(c) for c in result.get("secondary_categories", [])
                ],
                frustration_level=result["frustration_level"],
                clarity_score=result["clarity_score"],
                willingness_to_pay=result["willingness_to_pay"],
                wtp_quotes=result.get("wtp_quotes", []),
                current_workaround=result.get("current_workaround"),
                keywords=result.get("keywords", []),
                original_title=datapoint.title,
                content_snippet=datapoint.content[:500],
            )

        except json.JSONDecodeError as e:
            print(f"JSON parse error for {datapoint.source_id}: {e}")
            return None
        except Exception as e:
            print(f"Classification error for {datapoint.source_id}: {e}")
            return None

    async def classify_batch(
        self, datapoints: list[RawDataPoint], concurrency: int = 5
    ) -> AsyncIterator[ClassifiedInsight]:
        """Classify multiple data points with controlled concurrency.

        Args:
            datapoints: List of raw data to analyze.
            concurrency: Maximum concurrent API calls.

        Yields:
            ClassifiedInsight for each successful classification.
        """
        import asyncio

        semaphore = asyncio.Semaphore(concurrency)

        async def classify_with_semaphore(dp: RawDataPoint) -> ClassifiedInsight | None:
            async with semaphore:
                return await self.classify(dp)

        tasks = [classify_with_semaphore(dp) for dp in datapoints]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                yield result
