"""Unit tests for SQLite storage module."""

import pytest
import tempfile
import os
from datetime import datetime
from pathlib import Path

from scrapers.base import RawDataPoint, DataSource
from analysis.classifier import ClassifiedInsight, ProblemCategory
from storage.sqlite import SQLiteStorage


class TestSQLiteStorageInit:
    """Tests for SQLiteStorage initialization."""

    def test_creates_db_file(self):
        """Test that SQLite database file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            storage = SQLiteStorage(db_path=db_path)
            assert os.path.exists(db_path)

    def test_creates_parent_directories(self):
        """Test that parent directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "subdir", "nested", "test.db")
            storage = SQLiteStorage(db_path=db_path)
            assert os.path.exists(db_path)

    def test_creates_tables(self):
        """Test that all required tables are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            storage = SQLiteStorage(db_path=db_path)

            conn = storage._get_connection()
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            assert "raw_sources" in tables
            assert "insights" in tables
            assert "clusters" in tables
            assert "opportunity_scores" in tables

    def test_creates_indexes(self):
        """Test that indexes are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            storage = SQLiteStorage(db_path=db_path)

            conn = storage._get_connection()
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = [row[0] for row in cursor.fetchall()]
            conn.close()

            assert "idx_raw_sources_processed" in indexes
            assert "idx_raw_sources_source" in indexes
            assert "idx_insights_category" in indexes
            assert "idx_opportunity_scores_total" in indexes


class TestSaveRawDatapoint:
    """Tests for save_raw_datapoint method."""

    @pytest.fixture
    def storage(self):
        """Create SQLite storage with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield SQLiteStorage(db_path=db_path)

    def test_save_new_datapoint(self, storage, sample_raw_datapoint):
        """Test saving a new datapoint."""
        result = storage.save_raw_datapoint(sample_raw_datapoint)

        assert result is not None
        assert result.isdigit()  # SQLite returns integer IDs

    def test_save_returns_id(self, storage, sample_raw_datapoint):
        """Test that save returns a valid ID."""
        record_id = storage.save_raw_datapoint(sample_raw_datapoint)

        conn = storage._get_connection()
        cursor = conn.execute("SELECT * FROM raw_sources WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row["source_id"] == sample_raw_datapoint.source_id

    def test_save_duplicate_returns_existing_id(self, storage, sample_raw_datapoint):
        """Test that saving duplicate returns existing record ID."""
        id1 = storage.save_raw_datapoint(sample_raw_datapoint)
        id2 = storage.save_raw_datapoint(sample_raw_datapoint)

        assert id1 == id2

    def test_save_truncates_long_content(self, storage):
        """Test that very long content is truncated."""
        long_content = "x" * 150000  # Over 100k limit
        dp = RawDataPoint(
            source=DataSource.REDDIT,
            source_id="test_long",
            url="https://example.com",
            content=long_content,
            created_at=datetime.now(),
        )

        record_id = storage.save_raw_datapoint(dp)

        conn = storage._get_connection()
        cursor = conn.execute("SELECT content FROM raw_sources WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        assert len(row["content"]) == 100000

    def test_save_stores_all_fields(self, storage, sample_raw_datapoint):
        """Test that all fields are stored correctly."""
        record_id = storage.save_raw_datapoint(sample_raw_datapoint)

        conn = storage._get_connection()
        cursor = conn.execute("SELECT * FROM raw_sources WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        assert row["source_id"] == sample_raw_datapoint.source_id
        assert row["source"] == "reddit"
        assert row["url"] == sample_raw_datapoint.url
        assert row["title"] == sample_raw_datapoint.title
        assert row["author"] == sample_raw_datapoint.author
        assert row["processed"] == 0  # False

    def test_save_stores_metadata_as_json(self, storage, sample_raw_datapoint):
        """Test that metadata is stored as JSON."""
        record_id = storage.save_raw_datapoint(sample_raw_datapoint)

        conn = storage._get_connection()
        cursor = conn.execute("SELECT metadata FROM raw_sources WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        import json
        metadata = json.loads(row["metadata"])
        assert metadata["subreddit"] == "shopify"
        assert metadata["score"] == 45


class TestGetUnprocessedRawData:
    """Tests for get_unprocessed_raw_data method."""

    @pytest.fixture
    def storage(self):
        """Create SQLite storage with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield SQLiteStorage(db_path=db_path)

    def test_get_unprocessed_returns_list(self, storage, sample_raw_datapoint):
        """Test that unprocessed data is returned as list."""
        storage.save_raw_datapoint(sample_raw_datapoint)

        result = storage.get_unprocessed_raw_data()

        assert isinstance(result, list)
        assert len(result) == 1

    def test_get_unprocessed_respects_limit(self, storage):
        """Test that limit parameter is respected."""
        for i in range(10):
            dp = RawDataPoint(
                source=DataSource.REDDIT,
                source_id=f"test_{i}",
                url=f"https://example.com/{i}",
                content="Test content",
                created_at=datetime.now(),
            )
            storage.save_raw_datapoint(dp)

        result = storage.get_unprocessed_raw_data(limit=5)

        assert len(result) == 5

    def test_get_unprocessed_excludes_processed(self, storage, sample_raw_datapoint):
        """Test that processed records are excluded."""
        storage.save_raw_datapoint(sample_raw_datapoint)
        storage.mark_as_processed(sample_raw_datapoint.source_id)

        result = storage.get_unprocessed_raw_data()

        assert len(result) == 0


class TestMarkAsProcessed:
    """Tests for mark_as_processed method."""

    @pytest.fixture
    def storage(self):
        """Create SQLite storage with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield SQLiteStorage(db_path=db_path)

    def test_mark_as_processed(self, storage, sample_raw_datapoint):
        """Test marking a record as processed."""
        storage.save_raw_datapoint(sample_raw_datapoint)
        storage.mark_as_processed(sample_raw_datapoint.source_id)

        conn = storage._get_connection()
        cursor = conn.execute(
            "SELECT processed FROM raw_sources WHERE source_id = ?",
            (sample_raw_datapoint.source_id,)
        )
        row = cursor.fetchone()
        conn.close()

        assert row["processed"] == 1  # True

    def test_mark_nonexistent_does_nothing(self, storage):
        """Test that marking non-existent record doesn't raise error."""
        storage.mark_as_processed("nonexistent_id")  # Should not raise


class TestSaveInsight:
    """Tests for save_insight method."""

    @pytest.fixture
    def storage(self):
        """Create SQLite storage with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield SQLiteStorage(db_path=db_path)

    def test_save_new_insight(self, storage, sample_classified_insight):
        """Test saving a new insight."""
        result = storage.save_insight(sample_classified_insight)

        assert result is not None
        assert result.isdigit()

    def test_save_duplicate_insight_returns_existing(self, storage, sample_classified_insight):
        """Test that saving duplicate insight returns existing ID."""
        id1 = storage.save_insight(sample_classified_insight)
        id2 = storage.save_insight(sample_classified_insight)

        assert id1 == id2

    def test_save_insight_stores_all_fields(self, storage, sample_classified_insight):
        """Test that all insight fields are stored correctly."""
        record_id = storage.save_insight(sample_classified_insight)

        conn = storage._get_connection()
        cursor = conn.execute("SELECT * FROM insights WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        assert row["source_id"] == sample_classified_insight.source_id
        assert row["source_url"] == sample_classified_insight.source_url
        assert row["problem_statement"] == sample_classified_insight.problem_statement
        assert row["category"] == "analytics"
        assert row["frustration_level"] == 4
        assert row["clarity_score"] == 5
        assert row["willingness_to_pay"] == 1  # True

    def test_save_insight_with_raw_record_link(self, storage, sample_raw_datapoint, sample_classified_insight):
        """Test saving insight with link to raw record."""
        raw_id = storage.save_raw_datapoint(sample_raw_datapoint)
        insight_id = storage.save_insight(sample_classified_insight, raw_record_id=raw_id)

        conn = storage._get_connection()
        cursor = conn.execute("SELECT raw_source_id FROM insights WHERE id = ?", (insight_id,))
        row = cursor.fetchone()
        conn.close()

        assert row["raw_source_id"] == int(raw_id)

    def test_save_insight_formats_secondary_categories(self, storage, sample_classified_insight):
        """Test that secondary categories are stored as comma-separated."""
        record_id = storage.save_insight(sample_classified_insight)

        conn = storage._get_connection()
        cursor = conn.execute("SELECT secondary_categories FROM insights WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        assert row["secondary_categories"] == "pricing"

    def test_save_insight_formats_wtp_quotes(self, storage, sample_classified_insight):
        """Test that WTP quotes are joined with newlines."""
        record_id = storage.save_insight(sample_classified_insight)

        conn = storage._get_connection()
        cursor = conn.execute("SELECT wtp_quotes FROM insights WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        assert "I'd happily pay $20/month" in row["wtp_quotes"]

    def test_save_insight_formats_keywords(self, storage, sample_classified_insight):
        """Test that keywords are stored as comma-separated."""
        record_id = storage.save_insight(sample_classified_insight)

        conn = storage._get_connection()
        cursor = conn.execute("SELECT keywords FROM insights WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        assert "analytics" in row["keywords"]
        assert "conversion tracking" in row["keywords"]


class TestGetInsights:
    """Tests for insight getter methods."""

    @pytest.fixture
    def storage(self):
        """Create SQLite storage with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield SQLiteStorage(db_path=db_path)

    def test_get_insights_by_category(self, storage):
        """Test fetching insights by category."""
        # Create insights in different categories
        insight1 = ClassifiedInsight(
            source_id="test_1",
            source_url="https://example.com/1",
            problem_statement="Test 1",
            category=ProblemCategory.ANALYTICS,
            secondary_categories=[],
            frustration_level=3,
            clarity_score=4,
            willingness_to_pay=False,
            wtp_quotes=[],
            current_workaround=None,
            keywords=[],
            original_title="Test 1",
            content_snippet="Test 1",
        )
        insight2 = ClassifiedInsight(
            source_id="test_2",
            source_url="https://example.com/2",
            problem_statement="Test 2",
            category=ProblemCategory.MARKETING,
            secondary_categories=[],
            frustration_level=3,
            clarity_score=4,
            willingness_to_pay=False,
            wtp_quotes=[],
            current_workaround=None,
            keywords=[],
            original_title="Test 2",
            content_snippet="Test 2",
        )
        storage.save_insight(insight1)
        storage.save_insight(insight2)

        result = storage.get_insights_by_category(ProblemCategory.ANALYTICS)

        assert len(result) == 1
        assert result[0]["category"] == "analytics"

    def test_get_all_insights(self, storage, sample_classified_insight):
        """Test fetching all insights."""
        storage.save_insight(sample_classified_insight)

        result = storage.get_all_insights()

        assert len(result) == 1
        assert result[0]["source_id"] == sample_classified_insight.source_id


class TestSaveCluster:
    """Tests for save_cluster method."""

    @pytest.fixture
    def storage(self):
        """Create SQLite storage with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield SQLiteStorage(db_path=db_path)

    def test_save_cluster(self, storage):
        """Test saving a problem cluster."""
        result = storage.save_cluster(
            name="Analytics Gap",
            description="Merchants need better analytics",
            category=ProblemCategory.ANALYTICS,
            insight_ids=["1", "2", "3"],
            frequency=45,
        )

        assert result is not None
        assert result.isdigit()

    def test_save_cluster_stores_all_fields(self, storage):
        """Test that all cluster fields are stored correctly."""
        record_id = storage.save_cluster(
            name="Analytics Gap",
            description="Merchants need better analytics",
            category=ProblemCategory.ANALYTICS,
            insight_ids=["1", "2", "3"],
            frequency=45,
        )

        conn = storage._get_connection()
        cursor = conn.execute("SELECT * FROM clusters WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        assert row["name"] == "Analytics Gap"
        assert row["description"] == "Merchants need better analytics"
        assert row["category"] == "analytics"
        assert row["frequency"] == 45

    def test_save_cluster_stores_insight_ids_as_json(self, storage):
        """Test that insight IDs are stored as JSON."""
        record_id = storage.save_cluster(
            name="Test",
            description="Test",
            category=ProblemCategory.ANALYTICS,
            insight_ids=["1", "2", "3"],
            frequency=10,
        )

        conn = storage._get_connection()
        cursor = conn.execute("SELECT insight_ids FROM clusters WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        import json
        insight_ids = json.loads(row["insight_ids"])
        assert insight_ids == ["1", "2", "3"]

    def test_get_clusters(self, storage):
        """Test fetching all clusters."""
        storage.save_cluster(
            name="Cluster 1",
            description="Description 1",
            category=ProblemCategory.ANALYTICS,
            insight_ids=["1"],
            frequency=10,
        )
        storage.save_cluster(
            name="Cluster 2",
            description="Description 2",
            category=ProblemCategory.MARKETING,
            insight_ids=["2"],
            frequency=20,
        )

        result = storage.get_clusters()

        assert len(result) == 2


class TestSaveOpportunityScore:
    """Tests for save_opportunity_score method."""

    @pytest.fixture
    def storage(self):
        """Create SQLite storage with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield SQLiteStorage(db_path=db_path)

    def test_save_opportunity_score(self, storage):
        """Test saving an opportunity score."""
        # First create a cluster
        cluster_id = storage.save_cluster(
            name="Analytics Gap",
            description="Test",
            category=ProblemCategory.ANALYTICS,
            insight_ids=[],
            frequency=10,
        )

        result = storage.save_opportunity_score(
            cluster_id=cluster_id,
            cluster_name="Analytics Gap",
            frequency_score=80.0,
            intensity_score=75.0,
            wtp_score=90.0,
            competition_gap_score=85.0,
            total_score=82.5,
            notes="High opportunity",
        )

        assert result is not None
        assert result.isdigit()

    def test_save_opportunity_score_stores_all_fields(self, storage):
        """Test that all score fields are stored correctly."""
        cluster_id = storage.save_cluster(
            name="Test",
            description="Test",
            category=ProblemCategory.ANALYTICS,
            insight_ids=[],
            frequency=10,
        )

        record_id = storage.save_opportunity_score(
            cluster_id=cluster_id,
            cluster_name="Test",
            frequency_score=80.0,
            intensity_score=75.0,
            wtp_score=90.0,
            competition_gap_score=85.0,
            total_score=82.5,
            notes="Test notes",
        )

        conn = storage._get_connection()
        cursor = conn.execute("SELECT * FROM opportunity_scores WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        conn.close()

        assert row["cluster_name"] == "Test"
        assert row["frequency_score"] == 80.0
        assert row["intensity_score"] == 75.0
        assert row["wtp_score"] == 90.0
        assert row["competition_gap_score"] == 85.0
        assert row["total_score"] == 82.5
        assert row["notes"] == "Test notes"

    def test_get_ranked_opportunities(self, storage):
        """Test fetching ranked opportunities."""
        cluster1_id = storage.save_cluster(
            name="Cluster 1",
            description="Test",
            category=ProblemCategory.ANALYTICS,
            insight_ids=[],
            frequency=10,
        )
        cluster2_id = storage.save_cluster(
            name="Cluster 2",
            description="Test",
            category=ProblemCategory.MARKETING,
            insight_ids=[],
            frequency=20,
        )

        storage.save_opportunity_score(
            cluster_id=cluster1_id,
            cluster_name="Cluster 1",
            frequency_score=50.0,
            intensity_score=50.0,
            wtp_score=50.0,
            competition_gap_score=50.0,
            total_score=50.0,
        )
        storage.save_opportunity_score(
            cluster_id=cluster2_id,
            cluster_name="Cluster 2",
            frequency_score=90.0,
            intensity_score=90.0,
            wtp_score=90.0,
            competition_gap_score=90.0,
            total_score=90.0,
        )

        result = storage.get_ranked_opportunities()

        assert len(result) == 2
        assert result[0]["total_score"] == 90.0  # Higher score first
        assert result[1]["total_score"] == 50.0


class TestGetStats:
    """Tests for get_stats method."""

    @pytest.fixture
    def storage(self):
        """Create SQLite storage with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield SQLiteStorage(db_path=db_path)

    def test_get_stats_empty_db(self, storage):
        """Test stats for empty database."""
        stats = storage.get_stats()

        assert stats["raw_data_points"] == 0
        assert stats["classified_insights"] == 0
        assert stats["problem_clusters"] == 0
        assert stats["scored_opportunities"] == 0
        assert stats["category_breakdown"] == {}

    def test_get_stats_with_data(self, storage, sample_raw_datapoint, sample_classified_insight):
        """Test stats with data."""
        storage.save_raw_datapoint(sample_raw_datapoint)
        storage.save_insight(sample_classified_insight)
        storage.save_cluster(
            name="Test",
            description="Test",
            category=ProblemCategory.ANALYTICS,
            insight_ids=[],
            frequency=10,
        )

        stats = storage.get_stats()

        assert stats["raw_data_points"] == 1
        assert stats["classified_insights"] == 1
        assert stats["problem_clusters"] == 1
        assert stats["scored_opportunities"] == 0
        assert stats["category_breakdown"]["analytics"] == 1


class TestClearAll:
    """Tests for clear_all method."""

    @pytest.fixture
    def storage(self):
        """Create SQLite storage with temp database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield SQLiteStorage(db_path=db_path)

    def test_clear_all(self, storage, sample_raw_datapoint, sample_classified_insight):
        """Test that clear_all removes all data."""
        storage.save_raw_datapoint(sample_raw_datapoint)
        storage.save_insight(sample_classified_insight)
        storage.save_cluster(
            name="Test",
            description="Test",
            category=ProblemCategory.ANALYTICS,
            insight_ids=[],
            frequency=10,
        )

        storage.clear_all()

        stats = storage.get_stats()
        assert stats["raw_data_points"] == 0
        assert stats["classified_insights"] == 0
        assert stats["problem_clusters"] == 0
        assert stats["scored_opportunities"] == 0


class TestStorageFactoryFunction:
    """Tests for get_storage factory function."""

    def test_get_storage_sqlite(self):
        """Test getting SQLite storage backend."""
        from storage import get_storage

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            storage = get_storage(backend="sqlite", db_path=db_path)

            assert isinstance(storage, SQLiteStorage)

    def test_get_storage_unknown_raises(self):
        """Test that unknown backend raises ValueError."""
        from storage import get_storage

        with pytest.raises(ValueError, match="Unknown storage backend"):
            get_storage(backend="unknown")
