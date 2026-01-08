"""SQLite storage backend for local development and testing."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from config import settings
from scrapers.base import RawDataPoint
from analysis.classifier import ClassifiedInsight, ProblemCategory
from storage.base import StorageBackend


class SQLiteStorage(StorageBackend):
    """Storage backend using SQLite."""

    def __init__(self, db_path: str | None = None):
        """Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file. Defaults to settings or ./data/shopify.db
        """
        if db_path is None:
            db_path = getattr(settings, "sqlite_db_path", None) or "./data/shopify.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                -- Raw scraped data
                CREATE TABLE IF NOT EXISTS raw_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT UNIQUE NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    author TEXT,
                    created_at TIMESTAMP NOT NULL,
                    scraped_at TIMESTAMP NOT NULL,
                    metadata TEXT,
                    processed BOOLEAN DEFAULT FALSE
                );

                -- Classified insights
                CREATE TABLE IF NOT EXISTS insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT UNIQUE NOT NULL,
                    source_url TEXT NOT NULL,
                    problem_statement TEXT NOT NULL,
                    category TEXT NOT NULL,
                    secondary_categories TEXT,
                    frustration_level INTEGER NOT NULL,
                    clarity_score INTEGER NOT NULL,
                    willingness_to_pay BOOLEAN NOT NULL,
                    wtp_quotes TEXT,
                    current_workaround TEXT,
                    keywords TEXT,
                    original_title TEXT,
                    content_snippet TEXT NOT NULL,
                    raw_source_id INTEGER REFERENCES raw_sources(id)
                );

                -- Problem clusters
                CREATE TABLE IF NOT EXISTS clusters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    insight_ids TEXT,
                    frequency INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL
                );

                -- Opportunity scores
                CREATE TABLE IF NOT EXISTS opportunity_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cluster_id INTEGER REFERENCES clusters(id),
                    cluster_name TEXT NOT NULL,
                    frequency_score REAL NOT NULL,
                    intensity_score REAL NOT NULL,
                    wtp_score REAL NOT NULL,
                    competition_gap_score REAL NOT NULL,
                    total_score REAL NOT NULL,
                    notes TEXT,
                    scored_at TIMESTAMP NOT NULL
                );

                -- Indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_raw_sources_processed ON raw_sources(processed);
                CREATE INDEX IF NOT EXISTS idx_raw_sources_source ON raw_sources(source);
                CREATE INDEX IF NOT EXISTS idx_insights_category ON insights(category);
                CREATE INDEX IF NOT EXISTS idx_opportunity_scores_total ON opportunity_scores(total_score DESC);
            """)
            conn.commit()
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Raw Sources
    # -------------------------------------------------------------------------

    def save_raw_datapoint(self, datapoint: RawDataPoint) -> str:
        """Save a raw data point to SQLite.

        Args:
            datapoint: The raw scraped data.

        Returns:
            The record ID as string.
        """
        conn = self._get_connection()
        try:
            # Check for duplicates
            cursor = conn.execute(
                "SELECT id FROM raw_sources WHERE source_id = ?",
                (datapoint.source_id,)
            )
            existing = cursor.fetchone()
            if existing:
                return str(existing["id"])

            cursor = conn.execute(
                """
                INSERT INTO raw_sources
                (source_id, source, url, title, content, author, created_at, scraped_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datapoint.source_id,
                    datapoint.source.value,
                    datapoint.url,
                    datapoint.title or "",
                    datapoint.content[:100000],
                    datapoint.author or "",
                    datapoint.created_at.isoformat(),
                    datapoint.scraped_at.isoformat(),
                    json.dumps(datapoint.metadata),
                )
            )
            conn.commit()
            return str(cursor.lastrowid)
        finally:
            conn.close()

    def get_unprocessed_raw_data(self, limit: int = 100) -> list[dict]:
        """Get raw data points that haven't been classified yet.

        Args:
            limit: Maximum records to return.

        Returns:
            List of raw data records.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT source_id, source, url, title, content, author, created_at, metadata
                FROM raw_sources
                WHERE processed = FALSE OR processed IS NULL
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def mark_as_processed(self, source_id: str) -> None:
        """Mark a raw data point as processed.

        Args:
            source_id: The source_id of the record.
        """
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE raw_sources SET processed = TRUE WHERE source_id = ?",
                (source_id,)
            )
            conn.commit()
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Insights
    # -------------------------------------------------------------------------

    def save_insight(self, insight: ClassifiedInsight, raw_record_id: str | None = None) -> str:
        """Save a classified insight to SQLite.

        Args:
            insight: The classified insight.
            raw_record_id: Optional link to raw source record.

        Returns:
            The record ID as string.
        """
        conn = self._get_connection()
        try:
            # Check for duplicates
            cursor = conn.execute(
                "SELECT id FROM insights WHERE source_id = ?",
                (insight.source_id,)
            )
            existing = cursor.fetchone()
            if existing:
                return str(existing["id"])

            cursor = conn.execute(
                """
                INSERT INTO insights
                (source_id, source_url, problem_statement, category, secondary_categories,
                 frustration_level, clarity_score, willingness_to_pay, wtp_quotes,
                 current_workaround, keywords, original_title, content_snippet, raw_source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    insight.source_id,
                    insight.source_url,
                    insight.problem_statement,
                    insight.category.value,
                    ", ".join(c.value for c in insight.secondary_categories),
                    insight.frustration_level,
                    insight.clarity_score,
                    insight.willingness_to_pay,
                    "\n".join(insight.wtp_quotes),
                    insight.current_workaround or "",
                    ", ".join(insight.keywords),
                    insight.original_title or "",
                    insight.content_snippet,
                    int(raw_record_id) if raw_record_id else None,
                )
            )
            conn.commit()
            return str(cursor.lastrowid)
        finally:
            conn.close()

    def get_insights_by_category(self, category: ProblemCategory) -> list[dict]:
        """Get all insights for a specific category.

        Args:
            category: The category to filter by.

        Returns:
            List of insight records.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM insights WHERE category = ?",
                (category.value,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_all_insights(self) -> list[dict]:
        """Get all insights.

        Returns:
            List of all insight records.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM insights")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

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
            The record ID as string.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO clusters
                (name, description, category, insight_ids, frequency, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    description,
                    category.value,
                    json.dumps(insight_ids),
                    frequency,
                    datetime.utcnow().isoformat(),
                )
            )
            conn.commit()
            return str(cursor.lastrowid)
        finally:
            conn.close()

    def get_clusters(self) -> list[dict]:
        """Get all problem clusters.

        Returns:
            List of cluster records.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM clusters")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

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
            The record ID as string.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO opportunity_scores
                (cluster_id, cluster_name, frequency_score, intensity_score,
                 wtp_score, competition_gap_score, total_score, notes, scored_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(cluster_id),
                    cluster_name,
                    frequency_score,
                    intensity_score,
                    wtp_score,
                    competition_gap_score,
                    total_score,
                    notes,
                    datetime.utcnow().isoformat(),
                )
            )
            conn.commit()
            return str(cursor.lastrowid)
        finally:
            conn.close()

    def get_ranked_opportunities(self) -> list[dict]:
        """Get opportunities ranked by total score.

        Returns:
            List of opportunity records sorted by score descending.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM opportunity_scores ORDER BY total_score DESC"
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get summary statistics.

        Returns:
            Dictionary with counts and stats.
        """
        conn = self._get_connection()
        try:
            raw_count = conn.execute("SELECT COUNT(*) FROM raw_sources").fetchone()[0]
            insights_count = conn.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
            clusters_count = conn.execute("SELECT COUNT(*) FROM clusters").fetchone()[0]
            scores_count = conn.execute("SELECT COUNT(*) FROM opportunity_scores").fetchone()[0]

            # Category breakdown
            cursor = conn.execute(
                "SELECT category, COUNT(*) as count FROM insights GROUP BY category"
            )
            category_counts = {row["category"]: row["count"] for row in cursor.fetchall()}

            return {
                "raw_data_points": raw_count,
                "classified_insights": insights_count,
                "problem_clusters": clusters_count,
                "scored_opportunities": scores_count,
                "category_breakdown": category_counts,
            }
        finally:
            conn.close()

    def clear_all(self) -> None:
        """Clear all data from the database. Useful for testing."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                DELETE FROM opportunity_scores;
                DELETE FROM clusters;
                DELETE FROM insights;
                DELETE FROM raw_sources;
            """)
            conn.commit()
        finally:
            conn.close()
