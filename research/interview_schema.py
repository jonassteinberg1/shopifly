"""Data models for merchant interview research."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from analysis.classifier import ProblemCategory


class InterviewFrequency(str, Enum):
    """How often the pain point is experienced."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    OCCASIONALLY = "occasionally"


class BusinessImpact(str, Enum):
    """Business impact level of the pain point."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InterviewParticipant(BaseModel):
    """Represents an interview participant (anonymized)."""

    participant_id: str = Field(description="Anonymized participant ID")
    interview_date: datetime = Field(description="Date of the interview")
    store_vertical: str = Field(description="Store vertical (e.g., fashion, home goods)")
    monthly_gmv_range: str = Field(description="Revenue range (e.g., $10K-$30K)")
    store_age_months: int = Field(ge=0, description="Store age in months")
    team_size: int = Field(ge=1, description="Team size")
    app_count: int = Field(ge=0, description="Number of Shopify apps in use")
    monthly_app_budget: Optional[int] = Field(
        default=None, description="Monthly spending on apps in dollars"
    )
    beta_tester: bool = Field(
        default=False, description="Interested in beta testing"
    )


class InterviewInsight(BaseModel):
    """A structured insight captured from a merchant interview."""

    # Interview metadata
    interview_id: str = Field(description="Unique interview session ID")
    participant_id: str = Field(description="Reference to participant")
    recording_url: Optional[str] = Field(
        default=None, description="URL to interview recording if available"
    )

    # Pain point data (maps to existing classifier categories)
    pain_category: ProblemCategory = Field(description="Primary pain point category")
    pain_summary: str = Field(description="Summary of the pain point")
    verbatim_quotes: list[str] = Field(
        default_factory=list, description="Direct quotes from participant"
    )
    frustration_level: int = Field(
        ge=1, le=5, description="Interviewer-assessed frustration (1-5)"
    )
    frequency: InterviewFrequency = Field(description="How often issue occurs")
    business_impact: BusinessImpact = Field(description="Impact on business")

    # Solution context
    current_workaround: Optional[str] = Field(
        default=None, description="Current workaround being used"
    )
    apps_tried: list[str] = Field(
        default_factory=list, description="Apps they've tried for this problem"
    )
    ideal_solution: Optional[str] = Field(
        default=None, description="What ideal solution looks like"
    )

    # Willingness to pay data
    wtp_amount_low: Optional[int] = Field(
        default=None, description="Lower bound of WTP in dollars/month"
    )
    wtp_amount_high: Optional[int] = Field(
        default=None, description="Upper bound of WTP in dollars/month"
    )
    wtp_quote: Optional[str] = Field(
        default=None, description="Verbatim quote about pricing"
    )

    # Meta
    interviewer_notes: str = Field(
        default="", description="Additional notes from interviewer"
    )
    follow_up_candidate: bool = Field(
        default=False, description="Should follow up with this participant"
    )

    @property
    def has_wtp_data(self) -> bool:
        """Check if willingness to pay data is available."""
        return self.wtp_amount_low is not None or self.wtp_amount_high is not None

    @property
    def wtp_midpoint(self) -> Optional[float]:
        """Calculate midpoint of WTP range if available."""
        if self.wtp_amount_low is not None and self.wtp_amount_high is not None:
            return (self.wtp_amount_low + self.wtp_amount_high) / 2
        return self.wtp_amount_low or self.wtp_amount_high


class CorrelationReport(BaseModel):
    """Report correlating interview data with scraped insights."""

    validated: list[str] = Field(
        default_factory=list,
        description="Pain points appearing in both interviews and scraping",
    )
    interview_only: list[str] = Field(
        default_factory=list,
        description="Pain points discovered only through interviews",
    )
    scraped_only: list[str] = Field(
        default_factory=list,
        description="Pain points appearing only in scraped data",
    )
    wtp_validated: list[str] = Field(
        default_factory=list,
        description="Pain points with confirmed willingness to pay",
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)
