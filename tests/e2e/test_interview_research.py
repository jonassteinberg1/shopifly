"""End-to-end tests for interview research functionality.

These tests verify the full interview research pipeline works end-to-end:
- Storage operations (participants, insights)
- Interview-enhanced reranking
- Report export functionality
- CLI commands

Run with: pytest tests/e2e/test_interview_research.py -v -m e2e
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from analysis.classifier import ProblemCategory
from analysis.interview_reranker import (
    InterviewReranker,
    RankedOpportunity,
    format_opportunity_report,
)
from research.interview_schema import (
    InterviewParticipant,
    InterviewInsight,
    InterviewFrequency,
    BusinessImpact,
)
from research.interview_storage import InterviewStorage
from storage.sqlite import SQLiteStorage


@pytest.fixture
def interview_storage(tmp_path):
    """Create a temporary SQLite storage for interview tests."""
    db_path = tmp_path / "interview_test.db"
    # Initialize the main SQLite storage first (creates tables)
    main_storage = SQLiteStorage(db_path=str(db_path))
    # Then create interview storage
    storage = InterviewStorage(db_path=str(db_path))
    return storage, main_storage, str(db_path)


@pytest.fixture
def sample_participant():
    """Create a sample interview participant."""
    return InterviewParticipant(
        participant_id="P001",
        interview_date=datetime.utcnow(),
        store_vertical="fashion",
        monthly_gmv_range="$10K-$30K",
        store_age_months=18,
        team_size=2,
        app_count=5,
        monthly_app_budget=150,
        beta_tester=True,
    )


@pytest.fixture
def sample_insight():
    """Create a sample interview insight."""
    return InterviewInsight(
        interview_id="INT001",
        participant_id="P001",
        recording_url=None,
        pain_category=ProblemCategory.ANALYTICS,
        pain_summary="Unable to track customer lifetime value effectively",
        verbatim_quotes=[
            "I have no idea which customers are actually profitable",
            "I'd pay $30/month for proper LTV tracking",
        ],
        frustration_level=4,
        frequency=InterviewFrequency.DAILY,
        business_impact=BusinessImpact.HIGH,
        current_workaround="Manual spreadsheet tracking",
        apps_tried=["Lifetimely", "OrderMetrics"],
        ideal_solution="Automatic LTV calculation with cohort analysis",
        wtp_amount_low=20,
        wtp_amount_high=40,
        wtp_quote="I'd easily pay $30/month for this",
        interviewer_notes="Very frustrated, actively looking for solutions",
        follow_up_candidate=True,
    )


@pytest.mark.e2e
class TestInterviewStorageOperations:
    """E2E tests for interview storage operations."""

    def test_e2e_participant_roundtrip(self, interview_storage, sample_participant):
        """Test full participant save and retrieve flow."""
        storage, _, _ = interview_storage

        # Save participant
        result_id = storage.save_participant(sample_participant)
        assert result_id == sample_participant.participant_id

        # Retrieve participant
        retrieved = storage.get_participant(sample_participant.participant_id)
        assert retrieved is not None
        assert retrieved.participant_id == sample_participant.participant_id
        assert retrieved.store_vertical == sample_participant.store_vertical
        assert retrieved.monthly_gmv_range == sample_participant.monthly_gmv_range
        assert retrieved.beta_tester == sample_participant.beta_tester

    def test_e2e_insight_roundtrip(self, interview_storage, sample_participant, sample_insight):
        """Test full insight save and retrieve flow."""
        storage, _, _ = interview_storage

        # Save participant first (foreign key)
        storage.save_participant(sample_participant)

        # Save insight
        result_id = storage.save_insight(sample_insight)
        assert result_id is not None

        # Retrieve insights by participant
        insights = storage.get_insights_by_participant(sample_participant.participant_id)
        assert len(insights) == 1
        assert insights[0].pain_category == ProblemCategory.ANALYTICS
        assert insights[0].pain_summary == sample_insight.pain_summary
        assert insights[0].wtp_amount_low == 20
        assert insights[0].wtp_amount_high == 40

    def test_e2e_multiple_participants_and_insights(self, interview_storage):
        """Test with multiple participants and insights."""
        storage, _, _ = interview_storage

        # Create multiple participants
        participants = [
            InterviewParticipant(
                participant_id=f"P00{i}",
                interview_date=datetime.utcnow() - timedelta(days=i),
                store_vertical=vertical,
                monthly_gmv_range="$10K-$30K",
                store_age_months=12 + i,
                team_size=i + 1,  # team_size must be >= 1
                app_count=5 + i,
                monthly_app_budget=100 + i * 50,
                beta_tester=i % 2 == 0,
            )
            for i, vertical in enumerate(["fashion", "electronics", "home_goods", "beauty"])
        ]

        for p in participants:
            storage.save_participant(p)

        # Create insights for each participant
        categories = [
            ProblemCategory.ANALYTICS,
            ProblemCategory.INVENTORY,
            ProblemCategory.MARKETING,
            ProblemCategory.LOYALTY,
        ]

        for i, (p, cat) in enumerate(zip(participants, categories)):
            insight = InterviewInsight(
                interview_id=f"INT00{i}",
                participant_id=p.participant_id,
                pain_category=cat,
                pain_summary=f"Pain point about {cat.value}",
                verbatim_quotes=[f"Quote about {cat.value}"],
                frustration_level=3 + (i % 3),
                frequency=InterviewFrequency.WEEKLY,
                business_impact=BusinessImpact.MEDIUM,
                wtp_amount_low=10 * (i + 1),
                wtp_amount_high=30 * (i + 1),
            )
            storage.save_insight(insight)

        # Verify all data
        all_participants = storage.get_all_participants()
        assert len(all_participants) == 4

        all_insights = storage.get_all_insights()
        assert len(all_insights) == 4

        beta_testers = storage.get_beta_testers()
        assert len(beta_testers) == 2  # P000 and P002

    def test_e2e_category_queries(self, interview_storage, sample_participant, sample_insight):
        """Test querying insights by category."""
        storage, _, _ = interview_storage

        storage.save_participant(sample_participant)
        storage.save_insight(sample_insight)

        # Add another insight with different category
        insight2 = InterviewInsight(
            interview_id="INT002",
            participant_id=sample_participant.participant_id,
            pain_category=ProblemCategory.INVENTORY,
            pain_summary="Stock sync issues",
            verbatim_quotes=["Inventory never matches"],
            frustration_level=5,
            frequency=InterviewFrequency.DAILY,
            business_impact=BusinessImpact.HIGH,
        )
        storage.save_insight(insight2)

        # Query by category
        analytics_insights = storage.get_insights_by_category(ProblemCategory.ANALYTICS)
        assert len(analytics_insights) == 1

        inventory_insights = storage.get_insights_by_category(ProblemCategory.INVENTORY)
        assert len(inventory_insights) == 1

    def test_e2e_wtp_and_frustration_queries(self, interview_storage, sample_participant):
        """Test WTP and frustration level queries."""
        storage, _, _ = interview_storage

        storage.save_participant(sample_participant)

        # Add insights with varying WTP and frustration
        insights = [
            InterviewInsight(
                interview_id=f"INT{i}",
                participant_id=sample_participant.participant_id,
                pain_category=ProblemCategory.ANALYTICS,
                pain_summary=f"Pain {i}",
                verbatim_quotes=[],
                frustration_level=i + 1,
                frequency=InterviewFrequency.WEEKLY,
                business_impact=BusinessImpact.MEDIUM,
                wtp_amount_low=10 if i > 2 else None,
                wtp_amount_high=30 if i > 2 else None,
            )
            for i in range(5)
        ]

        for insight in insights:
            storage.save_insight(insight)

        # Test WTP queries
        wtp_insights = storage.get_insights_with_wtp()
        assert len(wtp_insights) == 2  # Only i=3 and i=4 have WTP

        # Test high frustration
        high_frustration = storage.get_high_frustration_insights(min_level=4)
        assert len(high_frustration) == 2  # i=3 (level 4) and i=4 (level 5)

    def test_e2e_statistics(self, interview_storage, sample_participant, sample_insight):
        """Test statistics generation."""
        storage, _, _ = interview_storage

        storage.save_participant(sample_participant)
        storage.save_insight(sample_insight)

        # Get stats
        stats = storage.get_interview_stats()

        assert stats["total_participants"] == 1
        assert stats["total_insights"] == 1
        assert stats["beta_testers"] == 1
        assert stats["insights_with_wtp"] == 1
        assert stats["wtp_rate"] == 100.0
        # avg_wtp uses COALESCE(wtp_amount_low, wtp_amount_high), so it's the low value
        assert stats["avg_wtp_amount"] == 20.0

    def test_e2e_category_summary(self, interview_storage, sample_participant):
        """Test category summary generation."""
        storage, _, _ = interview_storage

        storage.save_participant(sample_participant)

        # Add multiple insights in same category
        for i in range(3):
            insight = InterviewInsight(
                interview_id=f"INT{i}",
                participant_id=sample_participant.participant_id,
                pain_category=ProblemCategory.ANALYTICS,
                pain_summary=f"Analytics pain {i}",
                verbatim_quotes=[],
                frustration_level=3 + i,
                frequency=InterviewFrequency.WEEKLY,
                business_impact=BusinessImpact.MEDIUM,
                wtp_amount_low=20,
                wtp_amount_high=40,
            )
            storage.save_insight(insight)

        summary = storage.get_category_summary()

        assert "analytics" in summary
        assert summary["analytics"]["count"] == 3
        assert summary["analytics"]["avg_frustration"] == 4.0  # (3+4+5)/3
        assert summary["analytics"]["wtp_count"] == 3


@pytest.mark.e2e
class TestInterviewReranker:
    """E2E tests for interview-enhanced reranker."""

    def test_e2e_reranker_with_real_data(self, interview_storage, sample_participant, sample_insight):
        """Test reranker with real storage data."""
        storage, main_storage, _ = interview_storage

        # Add interview data
        storage.save_participant(sample_participant)
        storage.save_insight(sample_insight)

        # Add scraped data that matches the category
        from scrapers.base import RawDataPoint, DataSource
        from analysis.classifier import ClassifiedInsight

        raw = RawDataPoint(
            source=DataSource.REDDIT,
            source_id="test_scraped_1",
            url="https://reddit.com/r/shopify/test",
            title="Analytics frustration",
            content="I can't track LTV on Shopify",
            author="user1",
            created_at=datetime.now(),
        )
        raw_id = main_storage.save_raw_datapoint(raw)

        insight = ClassifiedInsight(
            source_id="test_scraped_1",
            source_url="https://reddit.com/r/shopify/test",
            problem_statement="Cannot track customer LTV",
            category=ProblemCategory.ANALYTICS,
            frustration_level=4,
            clarity_score=4,
            willingness_to_pay=True,
            wtp_quotes=["I'd pay for this"],
            content_snippet="I can't track LTV on Shopify",
        )
        main_storage.save_insight(insight, raw_record_id=raw_id)

        # Get all data for reranker
        scraped_insights = main_storage.get_all_insights()
        interview_insights = storage.get_all_insights()

        # Run reranker
        reranker = InterviewReranker(scraped_insights, interview_insights)
        opportunities = reranker.rank_opportunities()

        assert len(opportunities) > 0

        # Find analytics opportunity
        analytics_opp = next(
            (o for o in opportunities if o.category == ProblemCategory.ANALYTICS),
            None
        )
        assert analytics_opp is not None
        assert analytics_opp.interview_validated is True
        assert analytics_opp.interview_wtp_confirmed is True
        assert analytics_opp.interview_avg_wtp == 30.0  # (20+40)/2
        assert analytics_opp.interview_bonus > 0

    def test_e2e_reranker_validated_opportunities(self, interview_storage, sample_participant):
        """Test getting only validated opportunities."""
        storage, main_storage, _ = interview_storage

        # Add interview data for one category
        storage.save_participant(sample_participant)
        insight = InterviewInsight(
            interview_id="INT001",
            participant_id=sample_participant.participant_id,
            pain_category=ProblemCategory.LOYALTY,
            pain_summary="Need better loyalty program",
            verbatim_quotes=[],
            frustration_level=4,
            frequency=InterviewFrequency.WEEKLY,
            business_impact=BusinessImpact.HIGH,
            wtp_amount_low=25,
            wtp_amount_high=50,
        )
        storage.save_insight(insight)

        # Add scraped data for multiple categories
        from scrapers.base import RawDataPoint, DataSource
        from analysis.classifier import ClassifiedInsight

        categories = [ProblemCategory.LOYALTY, ProblemCategory.INVENTORY, ProblemCategory.MARKETING]
        for i, cat in enumerate(categories):
            raw = RawDataPoint(
                source=DataSource.REDDIT,
                source_id=f"scraped_{i}",
                url=f"https://reddit.com/test/{i}",
                title=f"Test {cat.value}",
                content=f"Issue with {cat.value}",
                author="user",
                created_at=datetime.now(),
            )
            raw_id = main_storage.save_raw_datapoint(raw)
            main_storage.save_insight(
                ClassifiedInsight(
                    source_id=f"scraped_{i}",
                    source_url=f"https://reddit.com/test/{i}",
                    problem_statement=f"Problem with {cat.value}",
                    category=cat,
                    frustration_level=4,
                    clarity_score=4,
                    willingness_to_pay=False,
                    content_snippet=f"Issue with {cat.value}",
                ),
                raw_record_id=raw_id,
            )

        # Get validated opportunities only
        scraped = main_storage.get_all_insights()
        interviews = storage.get_all_insights()
        reranker = InterviewReranker(scraped, interviews)

        validated = reranker.get_validated_opportunities()
        assert len(validated) == 1
        assert validated[0].category == ProblemCategory.LOYALTY

    def test_e2e_reranker_format_report(self, interview_storage, sample_participant, sample_insight):
        """Test opportunity report formatting."""
        storage, main_storage, _ = interview_storage

        storage.save_participant(sample_participant)
        storage.save_insight(sample_insight)

        interview_insights = storage.get_all_insights()
        reranker = InterviewReranker([], interview_insights)
        opportunities = reranker.rank_opportunities()

        report = format_opportunity_report(opportunities)

        assert "RANKED PRODUCT OPPORTUNITIES" in report
        assert "ANALYTICS" in report
        assert "Interview Validation: YES" in report


@pytest.mark.e2e
class TestReportExport:
    """E2E tests for report export functionality."""

    def test_e2e_weekly_summary_report(self, interview_storage, sample_participant, sample_insight):
        """Test weekly summary report generation."""
        storage, main_storage, db_path = interview_storage

        storage.save_participant(sample_participant)
        storage.save_insight(sample_insight)

        from scripts.export_interview_report import generate_weekly_summary

        report = generate_weekly_summary(storage, main_storage)

        assert "WEEKLY INTERVIEW RESEARCH SUMMARY" in report
        assert "Total Participants: 1" in report
        assert "Total Insights: 1" in report
        assert "Beta Testers: 1" in report
        assert "analytics" in report.lower()

    def test_e2e_correlation_report(self, interview_storage, sample_participant, sample_insight):
        """Test correlation report generation."""
        storage, main_storage, _ = interview_storage

        storage.save_participant(sample_participant)
        storage.save_insight(sample_insight)

        # Add scraped data
        from scrapers.base import RawDataPoint, DataSource
        from analysis.classifier import ClassifiedInsight

        raw = RawDataPoint(
            source=DataSource.REDDIT,
            source_id="corr_test",
            url="https://reddit.com/test",
            title="Test",
            content="Test content",
            author="user",
            created_at=datetime.now(),
        )
        raw_id = main_storage.save_raw_datapoint(raw)
        main_storage.save_insight(
            ClassifiedInsight(
                source_id="corr_test",
                source_url="https://reddit.com/test",
                problem_statement="Analytics issue",
                category=ProblemCategory.ANALYTICS,
                frustration_level=4,
                clarity_score=4,
                willingness_to_pay=False,
                content_snippet="Test content about analytics",
            ),
            raw_record_id=raw_id,
        )

        from scripts.export_interview_report import generate_correlation_report

        report = generate_correlation_report(storage, main_storage)

        assert "CORRELATION REPORT" in report
        assert "Validated Pain Points" in report
        assert "analytics" in report.lower()

    def test_e2e_opportunity_report(self, interview_storage, sample_participant, sample_insight):
        """Test opportunity report generation."""
        storage, main_storage, _ = interview_storage

        storage.save_participant(sample_participant)
        storage.save_insight(sample_insight)

        from scripts.export_interview_report import generate_opportunity_report

        report = generate_opportunity_report(storage, main_storage, top_n=5)

        assert "RANKED PRODUCT OPPORTUNITIES" in report

    def test_e2e_json_export(self, interview_storage, sample_participant, sample_insight):
        """Test JSON export functionality."""
        storage, main_storage, _ = interview_storage

        storage.save_participant(sample_participant)
        storage.save_insight(sample_insight)

        from scripts.export_interview_report import export_json

        json_str = export_json(storage, main_storage)
        data = json.loads(json_str)

        assert "generated_at" in data
        assert "stats" in data
        assert data["stats"]["total_participants"] == 1
        assert len(data["participants"]) == 1
        assert len(data["insights"]) == 1
        assert data["insights"][0]["pain_category"] == "analytics"

    def test_e2e_export_script_cli(self, interview_storage, sample_participant, sample_insight):
        """Test export script via subprocess."""
        storage, main_storage, db_path = interview_storage

        storage.save_participant(sample_participant)
        storage.save_insight(sample_insight)

        import subprocess
        import sys
        import os

        # Determine project root (works in Docker /app or local paths)
        # Find project root by looking for pyproject.toml
        project_root = Path(__file__).parent.parent.parent
        if not (project_root / "pyproject.toml").exists():
            # Fallback for Docker environment
            project_root = Path("/app")

        # Test weekly report
        result = subprocess.run(
            [sys.executable, "scripts/export_interview_report.py", "--format", "weekly", "--db-path", db_path],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        assert result.returncode == 0, f"Failed with stderr: {result.stderr}"
        assert "WEEKLY INTERVIEW RESEARCH SUMMARY" in result.stdout

        # Test JSON export to file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        result = subprocess.run(
            [
                sys.executable, "scripts/export_interview_report.py",
                "--format", "json",
                "--db-path", db_path,
                "--output", output_path,
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        assert result.returncode == 0, f"Failed with stderr: {result.stderr}"

        # Verify file was created
        with open(output_path) as f:
            data = json.load(f)
        assert data["stats"]["total_participants"] == 1

        Path(output_path).unlink()


@pytest.mark.e2e
class TestInterviewCLI:
    """E2E tests for interview CLI commands."""

    @pytest.fixture
    def cli_runner(self):
        """Create CLI runner."""
        return CliRunner()

    @pytest.fixture
    def cli_db_path(self, tmp_path):
        """Create temp database and initialize it."""
        db_path = str(tmp_path / "cli_test.db")
        # Initialize storage to create tables
        SQLiteStorage(db_path=db_path)
        return db_path

    def test_e2e_cli_add_participant(self, cli_runner, cli_db_path):
        """Test adding a participant via CLI."""
        from main import app

        result = cli_runner.invoke(
            app,
            [
                "interview", "add-participant",
                "--id", "P001",
                "--vertical", "fashion",
                "--gmv", "$10K-$30K",
                "--age", "18",
                "--team", "2",
                "--apps", "5",
                "--budget", "150",
                "--beta",
                "--db-path", cli_db_path,
            ],
        )

        assert result.exit_code == 0
        assert "Added participant P001" in result.stdout

        # Verify in storage
        storage = InterviewStorage(db_path=cli_db_path)
        participant = storage.get_participant("P001")
        assert participant is not None
        assert participant.store_vertical == "fashion"
        assert participant.beta_tester is True

    def test_e2e_cli_add_insight(self, cli_runner, cli_db_path):
        """Test adding an insight via CLI."""
        from main import app

        # First add participant
        cli_runner.invoke(
            app,
            [
                "interview", "add-participant",
                "--id", "P001",
                "--vertical", "fashion",
                "--gmv", "$10K-$30K",
                "--age", "12",
                "--db-path", cli_db_path,
            ],
        )

        # Add insight
        result = cli_runner.invoke(
            app,
            [
                "interview", "add-insight",
                "--interview", "INT001",
                "--participant", "P001",
                "--category", "analytics",
                "--summary", "Cannot track LTV",
                "--frustration", "4",
                "--frequency", "daily",
                "--impact", "high",
                "--wtp-low", "20",
                "--wtp-high", "40",
                "--db-path", cli_db_path,
            ],
        )

        assert result.exit_code == 0
        assert "Added insight" in result.stdout

        # Verify in storage
        storage = InterviewStorage(db_path=cli_db_path)
        insights = storage.get_insights_by_participant("P001")
        assert len(insights) == 1
        assert insights[0].pain_category == ProblemCategory.ANALYTICS

    def test_e2e_cli_stats(self, cli_runner, cli_db_path):
        """Test stats command."""
        from main import app

        # Add some data first
        cli_runner.invoke(
            app,
            [
                "interview", "add-participant",
                "--id", "P001",
                "--vertical", "fashion",
                "--gmv", "$10K-$30K",
                "--age", "12",
                "--beta",
                "--db-path", cli_db_path,
            ],
        )

        cli_runner.invoke(
            app,
            [
                "interview", "add-insight",
                "--interview", "INT001",
                "--participant", "P001",
                "--category", "analytics",
                "--summary", "Test pain point",
                "--wtp-low", "25",
                "--db-path", cli_db_path,
            ],
        )

        result = cli_runner.invoke(
            app,
            ["interview", "stats", "--db-path", cli_db_path],
        )

        assert result.exit_code == 0
        assert "Interview Research Stats" in result.stdout
        assert "Total Participants" in result.stdout
        assert "1" in result.stdout

    def test_e2e_cli_list(self, cli_runner, cli_db_path):
        """Test list command."""
        from main import app

        # Add participants
        for i in range(3):
            cli_runner.invoke(
                app,
                [
                    "interview", "add-participant",
                    "--id", f"P00{i}",
                    "--vertical", "fashion",
                    "--gmv", "$10K-$30K",
                    "--age", "12",
                    "--db-path", cli_db_path,
                ],
            )

        result = cli_runner.invoke(
            app,
            ["interview", "list", "--db-path", cli_db_path],
        )

        assert result.exit_code == 0
        assert "P000" in result.stdout
        assert "P001" in result.stdout
        assert "P002" in result.stdout

    def test_e2e_cli_beta_testers(self, cli_runner, cli_db_path):
        """Test beta-testers command."""
        from main import app

        # Add mix of beta and non-beta
        cli_runner.invoke(
            app,
            [
                "interview", "add-participant",
                "--id", "P001",
                "--vertical", "fashion",
                "--gmv", "$10K-$30K",
                "--age", "12",
                "--beta",
                "--db-path", cli_db_path,
            ],
        )
        cli_runner.invoke(
            app,
            [
                "interview", "add-participant",
                "--id", "P002",
                "--vertical", "electronics",
                "--gmv", "$10K-$30K",
                "--age", "12",
                "--db-path", cli_db_path,
            ],
        )

        result = cli_runner.invoke(
            app,
            ["interview", "beta-testers", "--db-path", cli_db_path],
        )

        assert result.exit_code == 0
        assert "P001" in result.stdout
        assert "P002" not in result.stdout

    def test_e2e_cli_opportunities(self, cli_runner, cli_db_path):
        """Test opportunities command with interview data."""
        from main import app

        # Add participant and insight
        cli_runner.invoke(
            app,
            [
                "interview", "add-participant",
                "--id", "P001",
                "--vertical", "fashion",
                "--gmv", "$10K-$30K",
                "--age", "12",
                "--db-path", cli_db_path,
            ],
        )

        cli_runner.invoke(
            app,
            [
                "interview", "add-insight",
                "--interview", "INT001",
                "--participant", "P001",
                "--category", "analytics",
                "--summary", "Cannot track LTV",
                "--frustration", "5",
                "--impact", "high",
                "--wtp-low", "30",
                "--wtp-high", "50",
                "--db-path", cli_db_path,
            ],
        )

        result = cli_runner.invoke(
            app,
            ["interview", "opportunities", "--db-path", cli_db_path],
        )

        assert result.exit_code == 0
        # Should show opportunities or indicate none found
        assert "opportunities" in result.stdout.lower() or "no insights" in result.stdout.lower()


@pytest.mark.e2e
class TestCorrelationReport:
    """E2E tests for correlation between scraped and interview data."""

    def test_e2e_correlation_validated_categories(self, interview_storage):
        """Test that categories appearing in both sources are marked as validated."""
        storage, main_storage, _ = interview_storage

        # Add interview data
        participant = InterviewParticipant(
            participant_id="P001",
            interview_date=datetime.utcnow(),
            store_vertical="fashion",
            monthly_gmv_range="$10K-$30K",
            store_age_months=12,
            team_size=1,
            app_count=5,
            beta_tester=False,
        )
        storage.save_participant(participant)

        insight = InterviewInsight(
            interview_id="INT001",
            participant_id="P001",
            pain_category=ProblemCategory.ANALYTICS,
            pain_summary="Analytics issues",
            verbatim_quotes=[],
            frustration_level=4,
            frequency=InterviewFrequency.WEEKLY,
            business_impact=BusinessImpact.MEDIUM,
        )
        storage.save_insight(insight)

        # Scraped data includes analytics and inventory
        scraped_categories = {"analytics", "inventory", "marketing"}

        # Generate correlation report
        correlation = storage.generate_correlation_report(scraped_categories)

        assert "analytics" in correlation.validated
        assert "inventory" in correlation.scraped_only
        assert "marketing" in correlation.scraped_only
        assert len(correlation.interview_only) == 0  # All interview cats are in scraped

    def test_e2e_correlation_interview_only(self, interview_storage):
        """Test categories discovered only through interviews."""
        storage, main_storage, _ = interview_storage

        participant = InterviewParticipant(
            participant_id="P001",
            interview_date=datetime.utcnow(),
            store_vertical="fashion",
            monthly_gmv_range="$10K-$30K",
            store_age_months=12,
            team_size=1,
            app_count=5,
            beta_tester=False,
        )
        storage.save_participant(participant)

        # Add insight for category not in scraped data
        insight = InterviewInsight(
            interview_id="INT001",
            participant_id="P001",
            pain_category=ProblemCategory.CUSTOMER_SUPPORT,
            pain_summary="Customer support issues",
            verbatim_quotes=[],
            frustration_level=4,
            frequency=InterviewFrequency.WEEKLY,
            business_impact=BusinessImpact.MEDIUM,
        )
        storage.save_insight(insight)

        # Scraped data doesn't include customer_support
        scraped_categories = {"analytics", "inventory"}

        correlation = storage.generate_correlation_report(scraped_categories)

        assert "customer_support" in correlation.interview_only
        assert len(correlation.validated) == 0
