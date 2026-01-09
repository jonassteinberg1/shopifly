"""Interview-enhanced reranker for prioritizing product opportunities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from analysis.classifier import ProblemCategory
from research.interview_schema import InterviewInsight, BusinessImpact


@dataclass
class RankedOpportunity:
    """A ranked product opportunity combining scraped and interview data."""

    category: ProblemCategory
    base_score: float
    interview_bonus: float
    total_score: float

    # From scraped data
    scraped_count: int
    avg_frustration: float
    wtp_signals: int
    avg_engagement: float

    # From interviews
    interview_validated: bool
    interview_count: int
    interview_wtp_confirmed: bool
    interview_avg_wtp: Optional[float]
    business_impact: Optional[BusinessImpact]
    key_quotes: list[str]


class InterviewReranker:
    """Reranker that enhances priority scores with interview validation."""

    # Weight configuration
    # Base score components (65% total)
    WEIGHT_RELEVANCE = 0.20
    WEIGHT_FRUSTRATION = 0.15
    WEIGHT_ENGAGEMENT = 0.15
    WEIGHT_WTP_SIGNAL = 0.10
    WEIGHT_RECENCY = 0.05

    # Interview bonus components (35% total)
    WEIGHT_INTERVIEW_VALIDATED = 0.15
    WEIGHT_INTERVIEW_WTP = 0.10
    WEIGHT_BUSINESS_IMPACT = 0.10

    def __init__(
        self,
        scraped_insights: list[dict],
        interview_insights: list[InterviewInsight],
    ):
        """Initialize the reranker.

        Args:
            scraped_insights: List of scraped insight records from storage.
            interview_insights: List of interview insights.
        """
        self.scraped_insights = scraped_insights
        self.interview_insights = interview_insights

        # Group by category for analysis
        self._scraped_by_category = self._group_scraped_by_category()
        self._interview_by_category = self._group_interview_by_category()

    def _group_scraped_by_category(self) -> dict[str, list[dict]]:
        """Group scraped insights by category."""
        result: dict[str, list[dict]] = {}
        for insight in self.scraped_insights:
            category = insight.get("category", "other")
            if category not in result:
                result[category] = []
            result[category].append(insight)
        return result

    def _group_interview_by_category(self) -> dict[str, list[InterviewInsight]]:
        """Group interview insights by category."""
        result: dict[str, list[InterviewInsight]] = {}
        for insight in self.interview_insights:
            category = insight.pain_category.value
            if category not in result:
                result[category] = []
            result[category].append(insight)
        return result

    def calculate_base_score(self, category: str) -> tuple[float, dict]:
        """Calculate base priority score from scraped data.

        Args:
            category: The problem category.

        Returns:
            Tuple of (score, metrics dict).
        """
        scraped = self._scraped_by_category.get(category, [])
        if not scraped:
            return 0.0, {}

        # Relevance: normalized count
        max_count = max(len(v) for v in self._scraped_by_category.values())
        relevance = len(scraped) / max_count if max_count > 0 else 0

        # Frustration: average frustration level
        frustrations = [i.get("frustration_level", 3) for i in scraped]
        avg_frustration = sum(frustrations) / len(frustrations) if frustrations else 3
        frustration_norm = avg_frustration / 5.0

        # Engagement: we don't have this in scraped data, use count as proxy
        engagement = min(len(scraped) / 50, 1.0)  # Cap at 50

        # WTP signals
        wtp_count = sum(1 for i in scraped if i.get("willingness_to_pay"))
        wtp_signal = min(wtp_count / 10, 1.0)  # Cap at 10

        # Recency: not available in current schema, default to 0.5
        recency = 0.5

        score = (
            relevance * self.WEIGHT_RELEVANCE +
            frustration_norm * self.WEIGHT_FRUSTRATION +
            engagement * self.WEIGHT_ENGAGEMENT +
            wtp_signal * self.WEIGHT_WTP_SIGNAL +
            recency * self.WEIGHT_RECENCY
        )

        metrics = {
            "scraped_count": len(scraped),
            "avg_frustration": round(avg_frustration, 2),
            "wtp_signals": wtp_count,
            "avg_engagement": round(engagement, 2),
        }

        return score, metrics

    def calculate_interview_bonus(self, category: str) -> tuple[float, dict]:
        """Calculate interview validation bonus.

        Args:
            category: The problem category.

        Returns:
            Tuple of (bonus, metrics dict).
        """
        interviews = self._interview_by_category.get(category, [])

        if not interviews:
            return 0.0, {
                "interview_validated": False,
                "interview_count": 0,
                "interview_wtp_confirmed": False,
                "interview_avg_wtp": None,
                "business_impact": None,
                "key_quotes": [],
            }

        # Validated: category appears in interviews
        validated_bonus = self.WEIGHT_INTERVIEW_VALIDATED

        # WTP confirmed: any interview has WTP data
        wtp_insights = [i for i in interviews if i.has_wtp_data]
        wtp_bonus = self.WEIGHT_INTERVIEW_WTP if wtp_insights else 0

        # Calculate average WTP if available
        wtp_amounts = [i.wtp_midpoint for i in wtp_insights if i.wtp_midpoint is not None]
        avg_wtp = sum(wtp_amounts) / len(wtp_amounts) if wtp_amounts else None

        # Business impact: use highest impact level
        impacts = [i.business_impact for i in interviews]
        highest_impact = None
        impact_bonus = 0
        if BusinessImpact.HIGH in impacts:
            highest_impact = BusinessImpact.HIGH
            impact_bonus = self.WEIGHT_BUSINESS_IMPACT
        elif BusinessImpact.MEDIUM in impacts:
            highest_impact = BusinessImpact.MEDIUM
            impact_bonus = self.WEIGHT_BUSINESS_IMPACT * 0.5
        elif BusinessImpact.LOW in impacts:
            highest_impact = BusinessImpact.LOW
            impact_bonus = self.WEIGHT_BUSINESS_IMPACT * 0.2

        # Collect key quotes
        key_quotes = []
        for insight in interviews[:3]:  # Top 3 insights
            if insight.verbatim_quotes:
                key_quotes.extend(insight.verbatim_quotes[:2])

        bonus = validated_bonus + wtp_bonus + impact_bonus

        metrics = {
            "interview_validated": True,
            "interview_count": len(interviews),
            "interview_wtp_confirmed": bool(wtp_insights),
            "interview_avg_wtp": round(avg_wtp, 2) if avg_wtp else None,
            "business_impact": highest_impact,
            "key_quotes": key_quotes[:5],  # Limit to 5 quotes
        }

        return bonus, metrics

    def rank_opportunities(self) -> list[RankedOpportunity]:
        """Rank all opportunities combining scraped and interview data.

        Returns:
            List of ranked opportunities sorted by total score.
        """
        # Get all unique categories
        all_categories = set(self._scraped_by_category.keys()) | set(
            self._interview_by_category.keys()
        )

        opportunities = []
        for category_str in all_categories:
            try:
                category = ProblemCategory(category_str)
            except ValueError:
                continue

            base_score, base_metrics = self.calculate_base_score(category_str)
            interview_bonus, interview_metrics = self.calculate_interview_bonus(category_str)

            total_score = (base_score * 0.65) + interview_bonus

            opportunities.append(RankedOpportunity(
                category=category,
                base_score=round(base_score * 100, 2),
                interview_bonus=round(interview_bonus * 100, 2),
                total_score=round(total_score * 100, 2),
                scraped_count=base_metrics.get("scraped_count", 0),
                avg_frustration=base_metrics.get("avg_frustration", 0),
                wtp_signals=base_metrics.get("wtp_signals", 0),
                avg_engagement=base_metrics.get("avg_engagement", 0),
                interview_validated=interview_metrics.get("interview_validated", False),
                interview_count=interview_metrics.get("interview_count", 0),
                interview_wtp_confirmed=interview_metrics.get("interview_wtp_confirmed", False),
                interview_avg_wtp=interview_metrics.get("interview_avg_wtp"),
                business_impact=interview_metrics.get("business_impact"),
                key_quotes=interview_metrics.get("key_quotes", []),
            ))

        # Sort by total score descending
        opportunities.sort(key=lambda x: x.total_score, reverse=True)
        return opportunities

    def get_top_opportunities(self, n: int = 10) -> list[RankedOpportunity]:
        """Get top N opportunities.

        Args:
            n: Number of opportunities to return.

        Returns:
            List of top opportunities.
        """
        return self.rank_opportunities()[:n]

    def get_validated_opportunities(self) -> list[RankedOpportunity]:
        """Get only interview-validated opportunities.

        Returns:
            List of validated opportunities.
        """
        return [
            opp for opp in self.rank_opportunities()
            if opp.interview_validated
        ]

    def get_wtp_confirmed_opportunities(self) -> list[RankedOpportunity]:
        """Get opportunities with confirmed willingness to pay.

        Returns:
            List of WTP-confirmed opportunities.
        """
        return [
            opp for opp in self.rank_opportunities()
            if opp.interview_wtp_confirmed
        ]


def format_opportunity_report(opportunities: list[RankedOpportunity]) -> str:
    """Format opportunities as a readable report.

    Args:
        opportunities: List of ranked opportunities.

    Returns:
        Formatted string report.
    """
    lines = [
        "=" * 80,
        "RANKED PRODUCT OPPORTUNITIES",
        "=" * 80,
        "",
    ]

    for i, opp in enumerate(opportunities, 1):
        lines.append(f"#{i}: {opp.category.value.upper()}")
        lines.append("-" * 40)
        lines.append(f"Total Score: {opp.total_score:.1f}/100")
        lines.append(f"  Base Score: {opp.base_score:.1f} (scraped data)")
        lines.append(f"  Interview Bonus: {opp.interview_bonus:.1f}")
        lines.append("")
        lines.append("Scraped Data:")
        lines.append(f"  Count: {opp.scraped_count} mentions")
        lines.append(f"  Avg Frustration: {opp.avg_frustration:.1f}/5")
        lines.append(f"  WTP Signals: {opp.wtp_signals}")
        lines.append("")

        if opp.interview_validated:
            lines.append("Interview Validation: YES")
            lines.append(f"  Interviews: {opp.interview_count}")
            lines.append(f"  WTP Confirmed: {'Yes' if opp.interview_wtp_confirmed else 'No'}")
            if opp.interview_avg_wtp:
                lines.append(f"  Avg WTP: ${opp.interview_avg_wtp:.0f}/month")
            if opp.business_impact:
                lines.append(f"  Business Impact: {opp.business_impact.value.upper()}")
            if opp.key_quotes:
                lines.append("  Key Quotes:")
                for quote in opp.key_quotes[:3]:
                    lines.append(f'    - "{quote[:100]}..."' if len(quote) > 100 else f'    - "{quote}"')
        else:
            lines.append("Interview Validation: NO (not yet validated)")

        lines.append("")
        lines.append("")

    return "\n".join(lines)
