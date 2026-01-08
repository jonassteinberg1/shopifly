"""Airtable storage integration."""

from datetime import datetime
from typing import Any

from pyairtable import Api, Table
from pyairtable.formulas import match

from config import settings
from scrapers.base import RawDataPoint
from analysis.classifier import ClassifiedInsight, ProblemCategory
from storage.base import StorageBackend


class AirtableStorage(StorageBackend):
    """Storage backend using Airtable."""

    # Table names
    RAW_SOURCES_TABLE = "Raw Sources"
    INSIGHTS_TABLE = "Insights"
    CLUSTERS_TABLE = "Problem Clusters"
    SCORES_TABLE = "Opportunity Scores"

    def __init__(self):
        self.api = Api(settings.airtable_api_key)
        self.base_id = settings.airtable_base_id
        self._tables: dict[str, Table] = {}

    def _get_table(self, table_name: str) -> Table:
        """Get or create a table reference."""
        if table_name not in self._tables:
            self._tables[table_name] = self.api.table(self.base_id, table_name)
        return self._tables[table_name]

    # -------------------------------------------------------------------------
    # Raw Sources
    # -------------------------------------------------------------------------

    def save_raw_datapoint(self, datapoint: RawDataPoint) -> str:
        """Save a raw data point to Airtable.

        Args:
            datapoint: The raw scraped data.

        Returns:
            The Airtable record ID.
        """
        table = self._get_table(self.RAW_SOURCES_TABLE)

        # Check for duplicates
        existing = table.first(formula=match({"source_id": datapoint.source_id}))
        if existing:
            return existing["id"]

        record = table.create(
            {
                "source_id": datapoint.source_id,
                "source": datapoint.source.value,
                "url": datapoint.url,
                "title": datapoint.title or "",
                "content": datapoint.content[:100000],  # Airtable field limit
                "author": datapoint.author or "",
                "created_at": datapoint.created_at.isoformat(),
                "scraped_at": datapoint.scraped_at.isoformat(),
                "metadata": str(datapoint.metadata),
            }
        )
        return record["id"]

    def get_unprocessed_raw_data(self, limit: int = 100) -> list[dict]:
        """Get raw data points that haven't been classified yet.

        Args:
            limit: Maximum records to return.

        Returns:
            List of raw data records.
        """
        table = self._get_table(self.RAW_SOURCES_TABLE)
        # Get records where 'processed' field is empty or false
        records = table.all(
            formula="{processed} = ''",
            max_records=limit,
        )
        return [r["fields"] for r in records]

    def mark_as_processed(self, source_id: str) -> None:
        """Mark a raw data point as processed.

        Args:
            source_id: The source_id of the record.
        """
        table = self._get_table(self.RAW_SOURCES_TABLE)
        record = table.first(formula=match({"source_id": source_id}))
        if record:
            table.update(record["id"], {"processed": True})

    # -------------------------------------------------------------------------
    # Insights
    # -------------------------------------------------------------------------

    def save_insight(self, insight: ClassifiedInsight, raw_record_id: str = None) -> str:
        """Save a classified insight to Airtable.

        Args:
            insight: The classified insight.
            raw_record_id: Optional link to raw source record.

        Returns:
            The Airtable record ID.
        """
        table = self._get_table(self.INSIGHTS_TABLE)

        # Check for duplicates
        existing = table.first(formula=match({"source_id": insight.source_id}))
        if existing:
            return existing["id"]

        fields: dict[str, Any] = {
            "source_id": insight.source_id,
            "source_url": insight.source_url,
            "problem_statement": insight.problem_statement,
            "category": insight.category.value,
            "secondary_categories": ", ".join(c.value for c in insight.secondary_categories),
            "frustration_level": insight.frustration_level,
            "clarity_score": insight.clarity_score,
            "willingness_to_pay": insight.willingness_to_pay,
            "wtp_quotes": "\n".join(insight.wtp_quotes),
            "current_workaround": insight.current_workaround or "",
            "keywords": ", ".join(insight.keywords),
            "original_title": insight.original_title or "",
            "content_snippet": insight.content_snippet,
        }

        if raw_record_id:
            fields["raw_source"] = [raw_record_id]

        record = table.create(fields)
        return record["id"]

    def get_insights_by_category(self, category: ProblemCategory) -> list[dict]:
        """Get all insights for a specific category.

        Args:
            category: The category to filter by.

        Returns:
            List of insight records.
        """
        table = self._get_table(self.INSIGHTS_TABLE)
        records = table.all(formula=match({"category": category.value}))
        return [r["fields"] for r in records]

    def get_all_insights(self) -> list[dict]:
        """Get all insights.

        Returns:
            List of all insight records.
        """
        table = self._get_table(self.INSIGHTS_TABLE)
        records = table.all()
        return [r["fields"] for r in records]

    # -------------------------------------------------------------------------
    # Problem Clusters
    # -------------------------------------------------------------------------

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
            The Airtable record ID.
        """
        table = self._get_table(self.CLUSTERS_TABLE)

        record = table.create(
            {
                "name": name,
                "description": description,
                "category": category.value,
                "insights": insight_ids,
                "frequency": frequency,
                "created_at": datetime.utcnow().isoformat(),
            }
        )
        return record["id"]

    def get_clusters(self) -> list[dict]:
        """Get all problem clusters.

        Returns:
            List of cluster records.
        """
        table = self._get_table(self.CLUSTERS_TABLE)
        records = table.all()
        return [r["fields"] for r in records]

    # -------------------------------------------------------------------------
    # Opportunity Scores
    # -------------------------------------------------------------------------

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
            The Airtable record ID.
        """
        table = self._get_table(self.SCORES_TABLE)

        record = table.create(
            {
                "cluster": [cluster_id],
                "cluster_name": cluster_name,
                "frequency_score": frequency_score,
                "intensity_score": intensity_score,
                "wtp_score": wtp_score,
                "competition_gap_score": competition_gap_score,
                "total_score": total_score,
                "notes": notes,
                "scored_at": datetime.utcnow().isoformat(),
            }
        )
        return record["id"]

    def get_ranked_opportunities(self) -> list[dict]:
        """Get opportunities ranked by total score.

        Returns:
            List of opportunity records sorted by score descending.
        """
        table = self._get_table(self.SCORES_TABLE)
        records = table.all(sort=["-total_score"])
        return [r["fields"] for r in records]

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get summary statistics.

        Returns:
            Dictionary with counts and stats.
        """
        raw_table = self._get_table(self.RAW_SOURCES_TABLE)
        insights_table = self._get_table(self.INSIGHTS_TABLE)
        clusters_table = self._get_table(self.CLUSTERS_TABLE)
        scores_table = self._get_table(self.SCORES_TABLE)

        raw_count = len(raw_table.all())
        insights_count = len(insights_table.all())
        clusters_count = len(clusters_table.all())
        scores_count = len(scores_table.all())

        # Category breakdown
        insights = insights_table.all()
        category_counts: dict[str, int] = {}
        for record in insights:
            cat = record["fields"].get("category", "other")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "raw_data_points": raw_count,
            "classified_insights": insights_count,
            "problem_clusters": clusters_count,
            "scored_opportunities": scores_count,
            "category_breakdown": category_counts,
        }
