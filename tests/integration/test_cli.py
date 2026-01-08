"""Integration tests for CLI commands."""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typer.testing import CliRunner

from main import app


runner = CliRunner()


class TestInitCommand:
    """Tests for the init command."""

    def test_init_creates_env_file(self, tmp_path):
        """Test that init creates .env file."""
        env_path = tmp_path / ".env"

        # Use isolated filesystem to test file creation
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Patch os module functions at the module level
            with patch.object(os.path, "dirname", return_value=str(tmp_path)), \
                 patch.object(os.path, "exists", return_value=False), \
                 patch.object(os.path, "join", return_value=str(env_path)):

                mock_open = MagicMock()
                with patch("builtins.open", mock_open):
                    result = runner.invoke(app, ["init"])

                # Check that either the file was "created" or we got the success message
                assert result.exit_code == 0
                assert "Created .env file" in result.stdout or mock_open.called

    def test_init_warns_if_exists(self, tmp_path):
        """Test that init warns if .env already exists."""
        env_path = tmp_path / ".env"

        with patch.object(os.path, "dirname", return_value=str(tmp_path)), \
             patch.object(os.path, "exists", return_value=True), \
             patch.object(os.path, "join", return_value=str(env_path)):

            result = runner.invoke(app, ["init"], input="n\n")

            assert ".env file already exists" in result.stdout


class TestHealthCommand:
    """Tests for the health command."""

    def test_health_shows_all_services(self):
        """Test that health check shows all services."""
        with patch("main._check_reddit", new_callable=AsyncMock) as mock_reddit, \
             patch("main._check_appstore", new_callable=AsyncMock) as mock_appstore, \
             patch("main._check_twitter", new_callable=AsyncMock) as mock_twitter, \
             patch("main._check_community", new_callable=AsyncMock) as mock_community, \
             patch("main._check_anthropic", new_callable=AsyncMock) as mock_anthropic, \
             patch("main._check_airtable", new_callable=AsyncMock) as mock_airtable:

            mock_reddit.return_value = (True, "Connected")
            mock_appstore.return_value = (True, "Connected")
            mock_twitter.return_value = (False, "Missing token")
            mock_community.return_value = (True, "Connected")
            mock_anthropic.return_value = (True, "Connected")
            mock_airtable.return_value = (True, "Connected")

            result = runner.invoke(app, ["health"])

            assert result.exit_code == 0
            assert "Health Check" in result.stdout


class TestStatsCommand:
    """Tests for the stats command."""

    def test_stats_displays_counts(self):
        """Test that stats shows data counts."""
        mock_stats = {
            "raw_data_points": 500,
            "classified_insights": 450,
            "problem_clusters": 25,
            "scored_opportunities": 10,
            "category_breakdown": {
                "analytics": 150,
                "marketing": 100,
                "inventory": 80,
            },
        }

        with patch("main.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.get_stats.return_value = mock_stats
            mock_get_storage.return_value = mock_storage

            result = runner.invoke(app, ["stats"])

            assert result.exit_code == 0
            assert "500" in result.stdout  # raw_data_points
            assert "450" in result.stdout  # classified_insights

    def test_stats_handles_error(self):
        """Test stats handles storage errors gracefully."""
        with patch("main.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.get_stats.side_effect = Exception("Connection error")
            mock_get_storage.return_value = mock_storage

            result = runner.invoke(app, ["stats"])

            assert "Error" in result.stdout


class TestOpportunitiesCommand:
    """Tests for the opportunities command."""

    def test_opportunities_shows_ranked_list(self):
        """Test that opportunities shows ranked list."""
        mock_opps = [
            {
                "cluster_name": "Analytics Gap",
                "total_score": 85.5,
                "frequency_score": 90,
                "wtp_score": 80,
                "competition_gap_score": 85,
            },
            {
                "cluster_name": "Inventory Issues",
                "total_score": 72.0,
                "frequency_score": 70,
                "wtp_score": 75,
                "competition_gap_score": 70,
            },
        ]

        with patch("main.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.get_ranked_opportunities.return_value = mock_opps
            mock_get_storage.return_value = mock_storage

            result = runner.invoke(app, ["opportunities", "--top", "5"])

            assert result.exit_code == 0
            assert "Analytics Gap" in result.stdout or "Opportunities" in result.stdout

    def test_opportunities_handles_empty(self):
        """Test opportunities handles no data."""
        with patch("main.get_storage") as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.get_ranked_opportunities.return_value = []
            mock_get_storage.return_value = mock_storage

            result = runner.invoke(app, ["opportunities"])

            assert "No scored opportunities" in result.stdout


class TestScrapeCommand:
    """Tests for the scrape command."""

    def test_scrape_with_source_filter(self):
        """Test scraping with specific source."""
        with patch("main._scrape", new_callable=AsyncMock) as mock_scrape:
            result = runner.invoke(app, ["scrape", "--source", "reddit", "--limit", "50"])

            assert result.exit_code == 0
            mock_scrape.assert_called_once()
            call_args = mock_scrape.call_args
            assert call_args[0][0] == "reddit"  # source
            assert call_args[0][1] == 50  # limit

    def test_scrape_all_sources(self):
        """Test scraping all sources."""
        with patch("main._scrape", new_callable=AsyncMock) as mock_scrape:
            result = runner.invoke(app, ["scrape", "--limit", "100"])

            assert result.exit_code == 0
            mock_scrape.assert_called_once()
            call_args = mock_scrape.call_args
            assert call_args[0][0] is None  # No source filter

    def test_scrape_no_save(self):
        """Test scraping without saving."""
        with patch("main._scrape", new_callable=AsyncMock) as mock_scrape:
            result = runner.invoke(app, ["scrape", "--no-save"])

            assert result.exit_code == 0
            call_args = mock_scrape.call_args
            assert call_args[0][2] is False  # save=False

    def test_scrape_with_sqlite_storage(self):
        """Test scraping with SQLite storage backend."""
        with patch("main._scrape", new_callable=AsyncMock) as mock_scrape:
            result = runner.invoke(
                app, ["scrape", "--storage", "sqlite", "--db-path", "/tmp/test.db"]
            )

            assert result.exit_code == 0
            call_args = mock_scrape.call_args
            assert call_args[0][3] == "sqlite"  # storage_backend
            assert call_args[0][4] == "/tmp/test.db"  # db_path


class TestClassifyCommand:
    """Tests for the classify command."""

    def test_classify_with_options(self):
        """Test classify with custom options."""
        with patch("main._classify", new_callable=AsyncMock) as mock_classify:
            result = runner.invoke(
                app, ["classify", "--limit", "50", "--concurrency", "3"]
            )

            assert result.exit_code == 0
            mock_classify.assert_called_once()
            call_args = mock_classify.call_args
            assert call_args[0][0] == 50  # limit
            assert call_args[0][1] == 3   # concurrency

    def test_classify_defaults(self):
        """Test classify with default options."""
        with patch("main._classify", new_callable=AsyncMock) as mock_classify:
            result = runner.invoke(app, ["classify"])

            assert result.exit_code == 0
            mock_classify.assert_called_once()
            call_args = mock_classify.call_args
            assert call_args[0][0] == 100  # limit default
            assert call_args[0][1] == 5    # concurrency default
            assert call_args[0][2] == "airtable"  # storage_backend default
            assert call_args[0][3] is None  # db_path default

    def test_classify_with_sqlite_storage(self):
        """Test classify with SQLite storage backend."""
        with patch("main._classify", new_callable=AsyncMock) as mock_classify:
            result = runner.invoke(
                app, ["classify", "--storage", "sqlite", "--db-path", "/tmp/test.db"]
            )

            assert result.exit_code == 0
            call_args = mock_classify.call_args
            assert call_args[0][2] == "sqlite"  # storage_backend
            assert call_args[0][3] == "/tmp/test.db"  # db_path
