"""Unit tests for storage module."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from scrapers.base import RawDataPoint, DataSource
from analysis.classifier import ClassifiedInsight, ProblemCategory
from storage.airtable import AirtableStorage


class TestAirtableStorage:
    """Tests for AirtableStorage class."""

    @pytest.fixture
    def mock_api(self):
        """Create mock Airtable API."""
        with patch("storage.airtable.Api") as mock:
            yield mock

    @pytest.fixture
    def storage(self, mock_api):
        """Create AirtableStorage with mocked API."""
        with patch("storage.airtable.settings") as mock_settings:
            mock_settings.airtable_api_key = "test-key"
            mock_settings.airtable_base_id = "test-base"
            return AirtableStorage()

    def test_table_names_defined(self):
        """Test that table names are defined."""
        assert AirtableStorage.RAW_SOURCES_TABLE == "Raw Sources"
        assert AirtableStorage.INSIGHTS_TABLE == "Insights"
        assert AirtableStorage.CLUSTERS_TABLE == "Problem Clusters"
        assert AirtableStorage.SCORES_TABLE == "Opportunity Scores"

    def test_get_table_caches_reference(self, storage, mock_api):
        """Test that table references are cached."""
        mock_table = MagicMock()
        storage.api.table = MagicMock(return_value=mock_table)

        # Get same table twice
        table1 = storage._get_table("Test Table")
        table2 = storage._get_table("Test Table")

        # Should only call api.table once
        assert storage.api.table.call_count == 1
        assert table1 is table2

    def test_get_table_different_tables(self, storage, mock_api):
        """Test getting different tables."""
        storage.api.table = MagicMock(side_effect=lambda base, name: MagicMock(name=name))

        table1 = storage._get_table("Table 1")
        table2 = storage._get_table("Table 2")

        assert storage.api.table.call_count == 2


class TestSaveRawDatapoint:
    """Tests for save_raw_datapoint method."""

    @pytest.fixture
    def storage(self):
        """Create storage with mocked internals."""
        with patch("storage.airtable.Api"), \
             patch("storage.airtable.settings") as mock_settings:
            mock_settings.airtable_api_key = "test-key"
            mock_settings.airtable_base_id = "test-base"
            storage = AirtableStorage()
            storage._tables = {}
            return storage

    def test_save_new_datapoint(self, storage, sample_raw_datapoint):
        """Test saving a new datapoint."""
        mock_table = MagicMock()
        mock_table.first.return_value = None  # No existing record
        mock_table.create.return_value = {"id": "rec123"}
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.save_raw_datapoint(sample_raw_datapoint)

        assert result == "rec123"
        mock_table.create.assert_called_once()

        # Verify the data structure
        call_args = mock_table.create.call_args[0][0]
        assert call_args["source_id"] == sample_raw_datapoint.source_id
        assert call_args["source"] == "reddit"
        assert call_args["url"] == sample_raw_datapoint.url

    def test_save_duplicate_returns_existing_id(self, storage, sample_raw_datapoint):
        """Test that saving duplicate returns existing record ID."""
        mock_table = MagicMock()
        mock_table.first.return_value = {"id": "existing_rec"}
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.save_raw_datapoint(sample_raw_datapoint)

        assert result == "existing_rec"
        mock_table.create.assert_not_called()

    def test_save_truncates_long_content(self, storage):
        """Test that very long content is truncated."""
        long_content = "x" * 150000  # Over 100k limit
        dp = RawDataPoint(
            source=DataSource.REDDIT,
            source_id="test",
            url="https://example.com",
            content=long_content,
            created_at=datetime.now(),
        )

        mock_table = MagicMock()
        mock_table.first.return_value = None
        mock_table.create.return_value = {"id": "rec123"}
        storage._get_table = MagicMock(return_value=mock_table)

        storage.save_raw_datapoint(dp)

        call_args = mock_table.create.call_args[0][0]
        assert len(call_args["content"]) == 100000


class TestSaveInsight:
    """Tests for save_insight method."""

    @pytest.fixture
    def storage(self):
        """Create storage with mocked internals."""
        with patch("storage.airtable.Api"), \
             patch("storage.airtable.settings") as mock_settings:
            mock_settings.airtable_api_key = "test-key"
            mock_settings.airtable_base_id = "test-base"
            storage = AirtableStorage()
            storage._tables = {}
            return storage

    def test_save_new_insight(self, storage, sample_classified_insight):
        """Test saving a new insight."""
        mock_table = MagicMock()
        mock_table.first.return_value = None
        mock_table.create.return_value = {"id": "rec_insight_123"}
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.save_insight(sample_classified_insight)

        assert result == "rec_insight_123"
        mock_table.create.assert_called_once()

        call_args = mock_table.create.call_args[0][0]
        assert call_args["source_id"] == sample_classified_insight.source_id
        assert call_args["category"] == "analytics"
        assert call_args["frustration_level"] == 4
        assert call_args["willingness_to_pay"] is True

    def test_save_insight_with_raw_record_link(self, storage, sample_classified_insight):
        """Test saving insight with link to raw record."""
        mock_table = MagicMock()
        mock_table.first.return_value = None
        mock_table.create.return_value = {"id": "rec_insight_123"}
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.save_insight(sample_classified_insight, raw_record_id="rec_raw_456")

        call_args = mock_table.create.call_args[0][0]
        assert call_args["raw_source"] == ["rec_raw_456"]

    def test_save_insight_formats_secondary_categories(self, storage, sample_classified_insight):
        """Test that secondary categories are formatted as comma-separated."""
        mock_table = MagicMock()
        mock_table.first.return_value = None
        mock_table.create.return_value = {"id": "rec123"}
        storage._get_table = MagicMock(return_value=mock_table)

        storage.save_insight(sample_classified_insight)

        call_args = mock_table.create.call_args[0][0]
        assert call_args["secondary_categories"] == "pricing"

    def test_save_insight_formats_wtp_quotes(self, storage, sample_classified_insight):
        """Test that WTP quotes are joined with newlines."""
        mock_table = MagicMock()
        mock_table.first.return_value = None
        mock_table.create.return_value = {"id": "rec123"}
        storage._get_table = MagicMock(return_value=mock_table)

        storage.save_insight(sample_classified_insight)

        call_args = mock_table.create.call_args[0][0]
        assert "I'd happily pay $20/month" in call_args["wtp_quotes"]


class TestGetMethods:
    """Tests for getter methods."""

    @pytest.fixture
    def storage(self):
        """Create storage with mocked internals."""
        with patch("storage.airtable.Api"), \
             patch("storage.airtable.settings") as mock_settings:
            mock_settings.airtable_api_key = "test-key"
            mock_settings.airtable_base_id = "test-base"
            storage = AirtableStorage()
            storage._tables = {}
            return storage

    def test_get_unprocessed_raw_data(self, storage, mock_airtable_records):
        """Test fetching unprocessed raw data."""
        mock_table = MagicMock()
        mock_table.all.return_value = mock_airtable_records
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.get_unprocessed_raw_data(limit=50)

        assert len(result) == 2
        assert result[0]["source_id"] == "reddit_post_abc123"
        mock_table.all.assert_called_once()

    def test_get_insights_by_category(self, storage):
        """Test fetching insights by category."""
        mock_records = [
            {"id": "rec1", "fields": {"category": "analytics", "problem_statement": "Test 1"}},
            {"id": "rec2", "fields": {"category": "analytics", "problem_statement": "Test 2"}},
        ]
        mock_table = MagicMock()
        mock_table.all.return_value = mock_records
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.get_insights_by_category(ProblemCategory.ANALYTICS)

        assert len(result) == 2

    def test_get_all_insights(self, storage):
        """Test fetching all insights."""
        mock_records = [
            {"id": "rec1", "fields": {"category": "analytics"}},
            {"id": "rec2", "fields": {"category": "marketing"}},
        ]
        mock_table = MagicMock()
        mock_table.all.return_value = mock_records
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.get_all_insights()

        assert len(result) == 2

    def test_get_ranked_opportunities(self, storage):
        """Test fetching ranked opportunities."""
        mock_records = [
            {"id": "rec1", "fields": {"cluster_name": "Analytics", "total_score": 85}},
            {"id": "rec2", "fields": {"cluster_name": "Loyalty", "total_score": 72}},
        ]
        mock_table = MagicMock()
        mock_table.all.return_value = mock_records
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.get_ranked_opportunities()

        assert len(result) == 2
        mock_table.all.assert_called_once_with(sort=["-total_score"])


class TestSaveCluster:
    """Tests for save_cluster method."""

    @pytest.fixture
    def storage(self):
        """Create storage with mocked internals."""
        with patch("storage.airtable.Api"), \
             patch("storage.airtable.settings") as mock_settings:
            mock_settings.airtable_api_key = "test-key"
            mock_settings.airtable_base_id = "test-base"
            storage = AirtableStorage()
            storage._tables = {}
            return storage

    def test_save_cluster(self, storage):
        """Test saving a problem cluster."""
        mock_table = MagicMock()
        mock_table.create.return_value = {"id": "rec_cluster_123"}
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.save_cluster(
            name="Analytics Gap",
            description="Merchants need better analytics",
            category=ProblemCategory.ANALYTICS,
            insight_ids=["rec1", "rec2", "rec3"],
            frequency=45,
        )

        assert result == "rec_cluster_123"
        call_args = mock_table.create.call_args[0][0]
        assert call_args["name"] == "Analytics Gap"
        assert call_args["category"] == "analytics"
        assert call_args["insights"] == ["rec1", "rec2", "rec3"]
        assert call_args["frequency"] == 45


class TestSaveOpportunityScore:
    """Tests for save_opportunity_score method."""

    @pytest.fixture
    def storage(self):
        """Create storage with mocked internals."""
        with patch("storage.airtable.Api"), \
             patch("storage.airtable.settings") as mock_settings:
            mock_settings.airtable_api_key = "test-key"
            mock_settings.airtable_base_id = "test-base"
            storage = AirtableStorage()
            storage._tables = {}
            return storage

    def test_save_opportunity_score(self, storage):
        """Test saving an opportunity score."""
        mock_table = MagicMock()
        mock_table.create.return_value = {"id": "rec_score_123"}
        storage._get_table = MagicMock(return_value=mock_table)

        result = storage.save_opportunity_score(
            cluster_id="rec_cluster_456",
            cluster_name="Analytics Gap",
            frequency_score=80.0,
            intensity_score=75.0,
            wtp_score=90.0,
            competition_gap_score=85.0,
            total_score=82.5,
            notes="High opportunity",
        )

        assert result == "rec_score_123"
        call_args = mock_table.create.call_args[0][0]
        assert call_args["cluster"] == ["rec_cluster_456"]
        assert call_args["total_score"] == 82.5
        assert call_args["notes"] == "High opportunity"


class TestGetStats:
    """Tests for get_stats method."""

    @pytest.fixture
    def storage(self):
        """Create storage with mocked internals."""
        with patch("storage.airtable.Api"), \
             patch("storage.airtable.settings") as mock_settings:
            mock_settings.airtable_api_key = "test-key"
            mock_settings.airtable_base_id = "test-base"
            storage = AirtableStorage()
            storage._tables = {}
            return storage

    def test_get_stats(self, storage):
        """Test getting statistics."""
        # Mock different tables with different record counts
        def mock_get_table(name):
            mock_table = MagicMock()
            if name == "Raw Sources":
                mock_table.all.return_value = [{"id": f"rec{i}"} for i in range(100)]
            elif name == "Insights":
                mock_table.all.return_value = [
                    {"id": "rec1", "fields": {"category": "analytics"}},
                    {"id": "rec2", "fields": {"category": "analytics"}},
                    {"id": "rec3", "fields": {"category": "marketing"}},
                ]
            elif name == "Problem Clusters":
                mock_table.all.return_value = [{"id": "rec1"}, {"id": "rec2"}]
            elif name == "Opportunity Scores":
                mock_table.all.return_value = [{"id": "rec1"}]
            return mock_table

        storage._get_table = mock_get_table

        stats = storage.get_stats()

        assert stats["raw_data_points"] == 100
        assert stats["classified_insights"] == 3
        assert stats["problem_clusters"] == 2
        assert stats["scored_opportunities"] == 1
        assert stats["category_breakdown"]["analytics"] == 2
        assert stats["category_breakdown"]["marketing"] == 1
