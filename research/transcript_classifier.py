"""LLM-based classifier for extracting insights from interview transcripts.

Takes a Transcript object and uses Claude to extract:
- Multiple pain points with categories, frustration levels, quotes
- WTP (willingness to pay) signals
- Participant profile information
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import anthropic
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from analysis.classifier import ProblemCategory
from config import settings
from research.interview_schema import (
    BusinessImpact,
    InterviewFrequency,
    InterviewInsight,
)
from research.transcription import Transcript


class ExtractedPainPoint(BaseModel):
    """A pain point extracted from a transcript."""

    category: str = Field(description="Pain point category")
    summary: str = Field(description="1-2 sentence summary")
    verbatim_quote: str = Field(description="Exact quote from transcript")
    frustration_level: int = Field(ge=1, le=5)
    urgency_score: int = Field(ge=1, le=5)
    frequency: str = Field(description="daily/weekly/monthly/occasionally")
    business_impact: str = Field(description="high/medium/low")
    current_workaround: Optional[str] = None
    competitor_mentions: list[str] = Field(default_factory=list)


class ExtractedWTPSignal(BaseModel):
    """A willingness-to-pay signal extracted from a transcript."""

    context: str = Field(description="What solution they'd pay for")
    amount_mentioned: Optional[str] = Field(default=None)
    verbatim_quote: str
    confidence: str = Field(description="high/medium/low")


class ExtractedProfile(BaseModel):
    """Participant profile information extracted from transcript."""

    store_vertical: Optional[str] = None
    app_count_mentioned: Optional[int] = None
    monthly_app_spend: Optional[str] = None
    team_size: Optional[str] = None
    key_quotes: list[str] = Field(default_factory=list)


class TranscriptAnalysis(BaseModel):
    """Complete analysis of an interview transcript."""

    pain_points: list[ExtractedPainPoint] = Field(default_factory=list)
    wtp_signals: list[ExtractedWTPSignal] = Field(default_factory=list)
    participant_profile: ExtractedProfile = Field(default_factory=ExtractedProfile)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    transcript_source: str = Field(description="Source file of transcript")


TRANSCRIPT_CLASSIFICATION_PROMPT = """Analyze this interview transcript with a Shopify merchant. Extract all pain points, insights, and business signals.

<transcript>
{transcript_text}
</transcript>

For EACH distinct pain point or insight mentioned, extract the information below. Look for:
- Frustrations with Shopify or apps
- Feature requests or wishes
- Workflow inefficiencies
- Pricing complaints
- Integration issues

Respond with ONLY valid JSON, no other text:

{{
  "pain_points": [
    {{
      "category": "<category from: admin, analytics, marketing, loyalty, payments, fulfillment, inventory, customer_support, design, seo, integrations, performance, pricing, other>",
      "summary": "<1-2 sentence description of the pain point>",
      "verbatim_quote": "<exact quote from transcript that shows this pain point>",
      "frustration_level": <1-5, where 5 is most frustrated>,
      "urgency_score": <1-5, where 5 is most urgent>,
      "frequency": "<daily|weekly|monthly|occasionally>",
      "business_impact": "<high|medium|low>",
      "current_workaround": "<what they're doing to cope, or null>",
      "competitor_mentions": ["<apps or tools mentioned as alternatives>"]
    }}
  ],
  "wtp_signals": [
    {{
      "context": "<what solution they'd pay for>",
      "amount_mentioned": "<dollar amount if stated, or null>",
      "verbatim_quote": "<exact quote>",
      "confidence": "<high|medium|low>"
    }}
  ],
  "participant_profile": {{
    "store_vertical": "<their product category if mentioned>",
    "app_count_mentioned": <number if mentioned, or null>,
    "monthly_app_spend": "<if mentioned>",
    "team_size": "<if mentioned>",
    "key_quotes": ["<notable quotes for reference>"]
  }}
}}

Important:
- Extract ALL distinct pain points, not just one
- Use exact quotes from the transcript
- Only include wtp_signals if there's actual evidence of willingness to pay
- If information is not mentioned, use null or empty arrays"""


class TranscriptClassifier:
    """Classifies interview transcripts to extract structured insights."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def classify_transcript(self, transcript: Transcript) -> TranscriptAnalysis:
        """Classify a transcript and extract insights.

        Args:
            transcript: Transcript object to analyze

        Returns:
            TranscriptAnalysis with extracted pain points and signals
        """
        # Truncate transcript if too long (Claude has context limits)
        text = transcript.full_text
        if len(text) > 15000:
            text = text[:15000] + "\n\n[Transcript truncated...]"

        prompt = TRANSCRIPT_CLASSIFICATION_PROMPT.format(transcript_text=text)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract JSON from response
        response_text = response.content[0].text.strip()

        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Find the end of the code block
            end_idx = len(lines) - 1
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "```":
                    end_idx = i
                    break
            response_text = "\n".join(lines[1:end_idx])

        result = json.loads(response_text)

        # Parse pain points
        pain_points = []
        for pp in result.get("pain_points", []):
            pain_points.append(
                ExtractedPainPoint(
                    category=pp.get("category", "other"),
                    summary=pp.get("summary", ""),
                    verbatim_quote=pp.get("verbatim_quote", ""),
                    frustration_level=min(5, max(1, pp.get("frustration_level", 3))),
                    urgency_score=min(5, max(1, pp.get("urgency_score", 3))),
                    frequency=pp.get("frequency", "occasionally"),
                    business_impact=pp.get("business_impact", "medium"),
                    current_workaround=pp.get("current_workaround"),
                    competitor_mentions=pp.get("competitor_mentions", []),
                )
            )

        # Parse WTP signals
        wtp_signals = []
        for wtp in result.get("wtp_signals", []):
            wtp_signals.append(
                ExtractedWTPSignal(
                    context=wtp.get("context", ""),
                    amount_mentioned=wtp.get("amount_mentioned"),
                    verbatim_quote=wtp.get("verbatim_quote", ""),
                    confidence=wtp.get("confidence", "medium"),
                )
            )

        # Parse profile
        profile_data = result.get("participant_profile", {})
        profile = ExtractedProfile(
            store_vertical=profile_data.get("store_vertical"),
            app_count_mentioned=profile_data.get("app_count_mentioned"),
            monthly_app_spend=profile_data.get("monthly_app_spend"),
            team_size=profile_data.get("team_size"),
            key_quotes=profile_data.get("key_quotes", []),
        )

        return TranscriptAnalysis(
            pain_points=pain_points,
            wtp_signals=wtp_signals,
            participant_profile=profile,
            transcript_source=transcript.source_file,
        )

    def convert_to_interview_insights(
        self,
        analysis: TranscriptAnalysis,
        interview_id: str,
        participant_id: str,
    ) -> list[InterviewInsight]:
        """Convert extracted pain points to InterviewInsight objects for storage.

        Args:
            analysis: TranscriptAnalysis from classification
            interview_id: ID for this interview session
            participant_id: ID of the participant

        Returns:
            List of InterviewInsight objects ready for storage
        """
        insights = []

        for i, pp in enumerate(analysis.pain_points):
            # Map category string to enum
            try:
                category = ProblemCategory(pp.category)
            except ValueError:
                category = ProblemCategory.OTHER

            # Map frequency string to enum
            try:
                frequency = InterviewFrequency(pp.frequency)
            except ValueError:
                frequency = InterviewFrequency.OCCASIONALLY

            # Map impact string to enum
            try:
                impact = BusinessImpact(pp.business_impact)
            except ValueError:
                impact = BusinessImpact.MEDIUM

            # Find matching WTP signals for this pain point
            wtp_low = None
            wtp_high = None
            wtp_quote = None

            for wtp in analysis.wtp_signals:
                # Check if WTP relates to this category
                if pp.category.lower() in wtp.context.lower() or pp.summary.lower() in wtp.context.lower():
                    wtp_quote = wtp.verbatim_quote
                    # Try to extract dollar amounts
                    if wtp.amount_mentioned:
                        try:
                            # Handle formats like "$30", "30", "$20-$40"
                            amount_str = wtp.amount_mentioned.replace("$", "").replace(",", "")
                            if "-" in amount_str:
                                parts = amount_str.split("-")
                                wtp_low = int(float(parts[0].strip()))
                                wtp_high = int(float(parts[1].strip()))
                            else:
                                amount = int(float(amount_str))
                                wtp_low = amount
                                wtp_high = amount
                        except (ValueError, IndexError):
                            pass
                    break

            insight = InterviewInsight(
                interview_id=f"{interview_id}_{i}",
                participant_id=participant_id,
                pain_category=category,
                pain_summary=pp.summary,
                verbatim_quotes=[pp.verbatim_quote] if pp.verbatim_quote else [],
                frustration_level=pp.frustration_level,
                frequency=frequency,
                business_impact=impact,
                current_workaround=pp.current_workaround,
                apps_tried=pp.competitor_mentions,
                wtp_amount_low=wtp_low,
                wtp_amount_high=wtp_high,
                wtp_quote=wtp_quote,
                interviewer_notes=f"Auto-extracted from transcript. Urgency: {pp.urgency_score}/5",
            )
            insights.append(insight)

        return insights
