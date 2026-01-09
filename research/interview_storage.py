"""Storage operations for interview research data."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import settings
from analysis.classifier import ProblemCategory
from research.interview_schema import (
    InterviewParticipant,
    InterviewInsight,
    InterviewFrequency,
    BusinessImpact,
    CorrelationReport,
)


class InterviewStorage:
    """Storage backend for interview research data."""

    def __init__(self, db_path: str | None = None):
        """Initialize interview storage.

        Args:
            db_path: Path to SQLite database file. Defaults to settings or ./data/shopify.db
        """
        if db_path is None:
            db_path = getattr(settings, "sqlite_db_path", None) or "./data/shopify.db"

        self.db_path = Path(db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # -------------------------------------------------------------------------
    # Participants
    # -------------------------------------------------------------------------

    def save_participant(self, participant: InterviewParticipant) -> str:
        """Save an interview participant.

        Args:
            participant: The participant data.

        Returns:
            The participant_id.
        """
        conn = self._get_connection()
        try:
            # Check for existing participant
            cursor = conn.execute(
                "SELECT id FROM interview_participants WHERE participant_id = ?",
                (participant.participant_id,)
            )
            existing = cursor.fetchone()
            if existing:
                # Update existing record
                conn.execute(
                    """
                    UPDATE interview_participants SET
                        interview_date = ?,
                        store_vertical = ?,
                        monthly_gmv_range = ?,
                        store_age_months = ?,
                        team_size = ?,
                        app_count = ?,
                        monthly_app_budget = ?,
                        beta_tester = ?
                    WHERE participant_id = ?
                    """,
                    (
                        participant.interview_date.isoformat(),
                        participant.store_vertical,
                        participant.monthly_gmv_range,
                        participant.store_age_months,
                        participant.team_size,
                        participant.app_count,
                        participant.monthly_app_budget,
                        participant.beta_tester,
                        participant.participant_id,
                    )
                )
            else:
                conn.execute(
                    """
                    INSERT INTO interview_participants
                    (participant_id, interview_date, store_vertical, monthly_gmv_range,
                     store_age_months, team_size, app_count, monthly_app_budget, beta_tester)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        participant.participant_id,
                        participant.interview_date.isoformat(),
                        participant.store_vertical,
                        participant.monthly_gmv_range,
                        participant.store_age_months,
                        participant.team_size,
                        participant.app_count,
                        participant.monthly_app_budget,
                        participant.beta_tester,
                    )
                )
            conn.commit()
            return participant.participant_id
        finally:
            conn.close()

    def get_participant(self, participant_id: str) -> Optional[InterviewParticipant]:
        """Get a participant by ID.

        Args:
            participant_id: The participant ID.

        Returns:
            InterviewParticipant or None if not found.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM interview_participants WHERE participant_id = ?",
                (participant_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return InterviewParticipant(
                participant_id=row["participant_id"],
                interview_date=datetime.fromisoformat(row["interview_date"]),
                store_vertical=row["store_vertical"],
                monthly_gmv_range=row["monthly_gmv_range"],
                store_age_months=row["store_age_months"],
                team_size=row["team_size"],
                app_count=row["app_count"],
                monthly_app_budget=row["monthly_app_budget"],
                beta_tester=bool(row["beta_tester"]),
            )
        finally:
            conn.close()

    def get_all_participants(self) -> list[InterviewParticipant]:
        """Get all participants.

        Returns:
            List of all participants.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM interview_participants ORDER BY interview_date DESC"
            )
            participants = []
            for row in cursor.fetchall():
                participants.append(InterviewParticipant(
                    participant_id=row["participant_id"],
                    interview_date=datetime.fromisoformat(row["interview_date"]),
                    store_vertical=row["store_vertical"],
                    monthly_gmv_range=row["monthly_gmv_range"],
                    store_age_months=row["store_age_months"],
                    team_size=row["team_size"],
                    app_count=row["app_count"],
                    monthly_app_budget=row["monthly_app_budget"],
                    beta_tester=bool(row["beta_tester"]),
                ))
            return participants
        finally:
            conn.close()

    def get_beta_testers(self) -> list[InterviewParticipant]:
        """Get all participants interested in beta testing.

        Returns:
            List of beta tester participants.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM interview_participants WHERE beta_tester = TRUE"
            )
            participants = []
            for row in cursor.fetchall():
                participants.append(InterviewParticipant(
                    participant_id=row["participant_id"],
                    interview_date=datetime.fromisoformat(row["interview_date"]),
                    store_vertical=row["store_vertical"],
                    monthly_gmv_range=row["monthly_gmv_range"],
                    store_age_months=row["store_age_months"],
                    team_size=row["team_size"],
                    app_count=row["app_count"],
                    monthly_app_budget=row["monthly_app_budget"],
                    beta_tester=True,
                ))
            return participants
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Interview Insights
    # -------------------------------------------------------------------------

    def save_insight(self, insight: InterviewInsight) -> str:
        """Save an interview insight.

        Args:
            insight: The insight data.

        Returns:
            The record ID as string.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO interview_insights
                (interview_id, participant_id, recording_url, pain_category, pain_summary,
                 verbatim_quotes, frustration_level, frequency, business_impact,
                 current_workaround, apps_tried, ideal_solution, wtp_amount_low,
                 wtp_amount_high, wtp_quote, interviewer_notes, follow_up_candidate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    insight.interview_id,
                    insight.participant_id,
                    insight.recording_url,
                    insight.pain_category.value,
                    insight.pain_summary,
                    json.dumps(insight.verbatim_quotes),
                    insight.frustration_level,
                    insight.frequency.value,
                    insight.business_impact.value,
                    insight.current_workaround,
                    json.dumps(insight.apps_tried),
                    insight.ideal_solution,
                    insight.wtp_amount_low,
                    insight.wtp_amount_high,
                    insight.wtp_quote,
                    insight.interviewer_notes,
                    insight.follow_up_candidate,
                )
            )
            conn.commit()
            return str(cursor.lastrowid)
        finally:
            conn.close()

    def get_insights_by_participant(self, participant_id: str) -> list[InterviewInsight]:
        """Get all insights from a specific participant.

        Args:
            participant_id: The participant ID.

        Returns:
            List of insights.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM interview_insights WHERE participant_id = ?",
                (participant_id,)
            )
            return [self._row_to_insight(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_insights_by_category(self, category: ProblemCategory) -> list[InterviewInsight]:
        """Get all interview insights for a specific category.

        Args:
            category: The category to filter by.

        Returns:
            List of insights.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM interview_insights WHERE pain_category = ?",
                (category.value,)
            )
            return [self._row_to_insight(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_insights(self) -> list[InterviewInsight]:
        """Get all interview insights.

        Returns:
            List of all insights.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM interview_insights ORDER BY created_at DESC"
            )
            return [self._row_to_insight(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_insights_with_wtp(self) -> list[InterviewInsight]:
        """Get insights that have willingness to pay data.

        Returns:
            List of insights with WTP data.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM interview_insights
                WHERE wtp_amount_low IS NOT NULL OR wtp_amount_high IS NOT NULL
                """
            )
            return [self._row_to_insight(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_high_frustration_insights(self, min_level: int = 4) -> list[InterviewInsight]:
        """Get insights with high frustration levels.

        Args:
            min_level: Minimum frustration level (1-5).

        Returns:
            List of high-frustration insights.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM interview_insights WHERE frustration_level >= ?",
                (min_level,)
            )
            return [self._row_to_insight(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _row_to_insight(self, row: sqlite3.Row) -> InterviewInsight:
        """Convert a database row to InterviewInsight.

        Args:
            row: Database row.

        Returns:
            InterviewInsight instance.
        """
        return InterviewInsight(
            interview_id=row["interview_id"],
            participant_id=row["participant_id"],
            recording_url=row["recording_url"],
            pain_category=ProblemCategory(row["pain_category"]),
            pain_summary=row["pain_summary"],
            verbatim_quotes=json.loads(row["verbatim_quotes"] or "[]"),
            frustration_level=row["frustration_level"],
            frequency=InterviewFrequency(row["frequency"]),
            business_impact=BusinessImpact(row["business_impact"]),
            current_workaround=row["current_workaround"],
            apps_tried=json.loads(row["apps_tried"] or "[]"),
            ideal_solution=row["ideal_solution"],
            wtp_amount_low=row["wtp_amount_low"],
            wtp_amount_high=row["wtp_amount_high"],
            wtp_quote=row["wtp_quote"],
            interviewer_notes=row["interviewer_notes"] or "",
            follow_up_candidate=bool(row["follow_up_candidate"]),
        )

    # -------------------------------------------------------------------------
    # Analysis
    # -------------------------------------------------------------------------

    def get_category_summary(self) -> dict[str, dict]:
        """Get summary of insights by category.

        Returns:
            Dictionary with category stats.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT
                    pain_category,
                    COUNT(*) as count,
                    AVG(frustration_level) as avg_frustration,
                    SUM(CASE WHEN wtp_amount_low IS NOT NULL OR wtp_amount_high IS NOT NULL THEN 1 ELSE 0 END) as wtp_count,
                    AVG(COALESCE(wtp_amount_low, wtp_amount_high)) as avg_wtp
                FROM interview_insights
                GROUP BY pain_category
                ORDER BY count DESC
                """
            )
            result = {}
            for row in cursor.fetchall():
                result[row["pain_category"]] = {
                    "count": row["count"],
                    "avg_frustration": round(row["avg_frustration"], 2) if row["avg_frustration"] else 0,
                    "wtp_count": row["wtp_count"],
                    "avg_wtp": round(row["avg_wtp"], 2) if row["avg_wtp"] else None,
                }
            return result
        finally:
            conn.close()

    def get_interview_stats(self) -> dict:
        """Get overall interview research statistics.

        Returns:
            Dictionary with stats.
        """
        conn = self._get_connection()
        try:
            participants = conn.execute(
                "SELECT COUNT(*) FROM interview_participants"
            ).fetchone()[0]
            insights = conn.execute(
                "SELECT COUNT(*) FROM interview_insights"
            ).fetchone()[0]
            beta_testers = conn.execute(
                "SELECT COUNT(*) FROM interview_participants WHERE beta_tester = TRUE"
            ).fetchone()[0]
            wtp_insights = conn.execute(
                """
                SELECT COUNT(*) FROM interview_insights
                WHERE wtp_amount_low IS NOT NULL OR wtp_amount_high IS NOT NULL
                """
            ).fetchone()[0]

            # Average insights per interview
            avg_insights = insights / participants if participants > 0 else 0

            # WTP statistics
            wtp_stats = conn.execute(
                """
                SELECT
                    AVG(COALESCE(wtp_amount_low, wtp_amount_high)) as avg_wtp,
                    MIN(wtp_amount_low) as min_wtp,
                    MAX(wtp_amount_high) as max_wtp
                FROM interview_insights
                WHERE wtp_amount_low IS NOT NULL OR wtp_amount_high IS NOT NULL
                """
            ).fetchone()

            return {
                "total_participants": participants,
                "total_insights": insights,
                "avg_insights_per_interview": round(avg_insights, 1),
                "beta_testers": beta_testers,
                "insights_with_wtp": wtp_insights,
                "wtp_rate": round(wtp_insights / insights * 100, 1) if insights > 0 else 0,
                "avg_wtp_amount": round(wtp_stats["avg_wtp"], 2) if wtp_stats["avg_wtp"] else None,
                "wtp_range": (wtp_stats["min_wtp"], wtp_stats["max_wtp"]) if wtp_stats["min_wtp"] else None,
            }
        finally:
            conn.close()

    def generate_correlation_report(self, scraped_categories: set[str]) -> CorrelationReport:
        """Generate a correlation report comparing interview and scraped data.

        Args:
            scraped_categories: Set of category names from scraped data.

        Returns:
            CorrelationReport instance.
        """
        conn = self._get_connection()
        try:
            # Get interview categories
            cursor = conn.execute(
                "SELECT DISTINCT pain_category FROM interview_insights"
            )
            interview_categories = {row["pain_category"] for row in cursor.fetchall()}

            # Get categories with WTP
            cursor = conn.execute(
                """
                SELECT DISTINCT pain_category FROM interview_insights
                WHERE wtp_amount_low IS NOT NULL OR wtp_amount_high IS NOT NULL
                """
            )
            wtp_categories = {row["pain_category"] for row in cursor.fetchall()}

            return CorrelationReport(
                validated=list(interview_categories & scraped_categories),
                interview_only=list(interview_categories - scraped_categories),
                scraped_only=list(scraped_categories - interview_categories),
                wtp_validated=list(wtp_categories),
            )
        finally:
            conn.close()
