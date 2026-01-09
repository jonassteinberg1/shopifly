"""Abstract base class for storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from scrapers.base import RawDataPoint
from analysis.classifier import ClassifiedInsight, ProblemCategory


class StorageBackend(ABC):
    """Abstract base class defining the storage interface."""

    # -------------------------------------------------------------------------
    # Raw Sources
    # -------------------------------------------------------------------------

    @abstractmethod
    def save_raw_datapoint(self, datapoint: RawDataPoint) -> str:
        """Save a raw data point.

        Args:
            datapoint: The raw scraped data.

        Returns:
            The record ID.
        """
        pass

    @abstractmethod
    def get_unprocessed_raw_data(self, limit: int = 100) -> list[dict]:
        """Get raw data points that haven't been classified yet.

        Args:
            limit: Maximum records to return.

        Returns:
            List of raw data records.
        """
        pass

    @abstractmethod
    def mark_as_processed(self, source_id: str) -> None:
        """Mark a raw data point as processed.

        Args:
            source_id: The source_id of the record.
        """
        pass

    # -------------------------------------------------------------------------
    # Insights
    # -------------------------------------------------------------------------

    @abstractmethod
    def save_insight(self, insight: ClassifiedInsight, raw_record_id: str | None = None) -> str:
        """Save a classified insight.

        Args:
            insight: The classified insight.
            raw_record_id: Optional link to raw source record.

        Returns:
            The record ID.
        """
        pass

    @abstractmethod
    def get_insights_by_category(self, category: ProblemCategory) -> list[dict]:
        """Get all insights for a specific category.

        Args:
            category: The category to filter by.

        Returns:
            List of insight records.
        """
        pass

    @abstractmethod
    def get_all_insights(self) -> list[dict]:
        """Get all insights.

        Returns:
            List of all insight records.
        """
        pass

    # -------------------------------------------------------------------------
    # Clusters (placeholder for future)
    # -------------------------------------------------------------------------

    @abstractmethod
    def save_cluster(
        self,
        name: str,
        description: str,
        category: ProblemCategory,
        insight_ids: list[str],
        frequency: int,
    ) -> str:
        """Save a problem cluster.

        Args:
            name: Cluster name.
            description: Description of the problem cluster.
            category: Primary category.
            insight_ids: List of linked insight record IDs.
            frequency: Number of mentions.

        Returns:
            The record ID.
        """
        pass

    @abstractmethod
    def get_clusters(self) -> list[dict]:
        """Get all problem clusters.

        Returns:
            List of cluster records.
        """
        pass

    # -------------------------------------------------------------------------
    # Opportunity Scores (placeholder for future)
    # -------------------------------------------------------------------------

    @abstractmethod
    def save_opportunity_score(
        self,
        cluster_id: str,
        cluster_name: str,
        frequency_score: float,
        intensity_score: float,
        wtp_score: float,
        competition_gap_score: float,
        total_score: float,
        notes: str = "",
    ) -> str:
        """Save an opportunity score for a problem cluster.

        Args:
            cluster_id: Link to the cluster record.
            cluster_name: Name of the cluster.
            frequency_score: Score based on mention frequency (0-100).
            intensity_score: Score based on frustration level (0-100).
            wtp_score: Score based on willingness to pay (0-100).
            competition_gap_score: Score based on competition analysis (0-100).
            total_score: Weighted total score.
            notes: Additional notes.

        Returns:
            The record ID.
        """
        pass

    @abstractmethod
    def get_ranked_opportunities(self) -> list[dict]:
        """Get opportunities ranked by total score.

        Returns:
            List of opportunity records sorted by score descending.
        """
        pass

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_stats(self) -> dict:
        """Get summary statistics.

        Returns:
            Dictionary with counts and stats.
        """
        pass
