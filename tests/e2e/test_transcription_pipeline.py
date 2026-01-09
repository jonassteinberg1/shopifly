"""End-to-end tests for the transcription pipeline.

Tests both transcription paths:
- Path A: Zoom VTT import
- Path B: Whisper transcription (marked as slow)

Run with: pytest tests/e2e/test_transcription_pipeline.py -v -m e2e
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from research.transcription import (
    Transcript,
    TranscriptSegment,
    parse_vtt,
    import_vtt_file,
    get_default_transcript_dir,
)
from research.transcript_classifier import (
    TranscriptClassifier,
    TranscriptAnalysis,
    ExtractedPainPoint,
)
from research.interview_storage import InterviewStorage
from storage.sqlite import SQLiteStorage


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_VTT = FIXTURES_DIR / "sample_interview.vtt"
SAMPLE_TRANSCRIPT = FIXTURES_DIR / "sample_transcript.json"


@pytest.fixture
def sample_vtt_content():
    """Load sample VTT content."""
    return SAMPLE_VTT.read_text()


@pytest.fixture
def sample_transcript():
    """Load sample transcript."""
    return Transcript.from_json_file(SAMPLE_TRANSCRIPT)


@pytest.fixture
def cli_runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_db(tmp_path):
    """Create temporary database."""
    db_path = str(tmp_path / "test.db")
    # Initialize storage to create tables
    SQLiteStorage(db_path=db_path)
    return db_path


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create temporary output directory."""
    out_dir = tmp_path / "transcripts"
    out_dir.mkdir()
    return out_dir


@pytest.mark.e2e
class TestVTTParser:
    """Tests for VTT parsing functionality."""

    def test_parse_vtt_basic(self, sample_vtt_content):
        """Test basic VTT parsing."""
        segments = parse_vtt(sample_vtt_content)

        assert len(segments) > 0
        assert all(isinstance(s, TranscriptSegment) for s in segments)

    def test_parse_vtt_timestamps(self, sample_vtt_content):
        """Test VTT timestamp parsing is correct."""
        segments = parse_vtt(sample_vtt_content)

        # First segment should start at 0
        assert segments[0].start == 0.0

        # Timestamps should be in order
        for i in range(1, len(segments)):
            assert segments[i].start >= segments[i - 1].start

    def test_parse_vtt_text_content(self, sample_vtt_content):
        """Test VTT text content is extracted."""
        segments = parse_vtt(sample_vtt_content)

        # Check for expected content
        full_text = " ".join(s.text for s in segments)
        assert "inventory management" in full_text.lower()
        assert "thirty to fifty dollars" in full_text.lower()

    def test_parse_vtt_handles_empty(self):
        """Test VTT parser handles empty content."""
        segments = parse_vtt("")
        assert segments == []

    def test_parse_vtt_handles_header_only(self):
        """Test VTT parser handles header-only content."""
        segments = parse_vtt("WEBVTT\n\n")
        assert segments == []


@pytest.mark.e2e
class TestVTTImport:
    """Tests for VTT file import."""

    def test_import_vtt_file_creates_transcript(self, temp_output_dir):
        """Test importing VTT file creates valid transcript."""
        transcript = import_vtt_file(SAMPLE_VTT, output_dir=temp_output_dir)

        assert transcript.method == "zoom_vtt"
        assert len(transcript.segments) > 0
        assert len(transcript.full_text) > 0

    def test_import_vtt_file_with_participant(self, temp_output_dir):
        """Test VTT import with participant ID."""
        transcript = import_vtt_file(
            SAMPLE_VTT, participant_id="P001", output_dir=temp_output_dir
        )

        assert transcript.participant_id == "P001"

    def test_import_vtt_file_saves_json(self, temp_output_dir):
        """Test VTT import saves JSON file."""
        transcript = import_vtt_file(SAMPLE_VTT, output_dir=temp_output_dir)

        json_path = temp_output_dir / f"{SAMPLE_VTT.stem}.json"
        assert json_path.exists()

        # Load and verify
        loaded = Transcript.from_json_file(json_path)
        assert loaded.full_text == transcript.full_text

    def test_import_vtt_file_not_found(self, temp_output_dir):
        """Test VTT import with missing file."""
        with pytest.raises(FileNotFoundError):
            import_vtt_file(Path("/nonexistent/file.vtt"), output_dir=temp_output_dir)


@pytest.mark.e2e
class TestVTTImportCLI:
    """CLI tests for VTT import."""

    def test_cli_import_vtt(self, cli_runner, temp_output_dir):
        """Test import-vtt CLI command."""
        from main import app

        result = cli_runner.invoke(
            app,
            [
                "interview",
                "import-vtt",
                str(SAMPLE_VTT),
                "--output",
                str(temp_output_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Imported VTT transcript" in result.stdout

    def test_cli_import_vtt_with_participant(self, cli_runner, temp_output_dir):
        """Test import-vtt CLI with participant."""
        from main import app

        result = cli_runner.invoke(
            app,
            [
                "interview",
                "import-vtt",
                str(SAMPLE_VTT),
                "--participant",
                "P001",
                "--output",
                str(temp_output_dir),
            ],
        )

        assert result.exit_code == 0
        assert "P001" in result.stdout

    def test_cli_import_vtt_missing_file(self, cli_runner):
        """Test import-vtt CLI with missing file."""
        from main import app

        result = cli_runner.invoke(
            app,
            ["interview", "import-vtt", "/nonexistent/file.vtt"],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout


@pytest.mark.e2e
class TestTranscriptModel:
    """Tests for Transcript model."""

    def test_transcript_from_json_file(self):
        """Test loading transcript from JSON file."""
        transcript = Transcript.from_json_file(SAMPLE_TRANSCRIPT)

        assert transcript.method == "zoom_vtt"
        assert len(transcript.segments) > 0
        assert "inventory" in transcript.full_text.lower()

    def test_transcript_to_json_file(self, temp_output_dir):
        """Test saving transcript to JSON file."""
        transcript = Transcript(
            source_file="test.vtt",
            method="zoom_vtt",
            segments=[
                TranscriptSegment(start=0, end=5, text="Hello world"),
            ],
            full_text="Hello world",
        )

        output_path = temp_output_dir / "test.json"
        transcript.to_json_file(output_path)

        assert output_path.exists()

        # Reload and verify
        loaded = Transcript.from_json_file(output_path)
        assert loaded.full_text == transcript.full_text

    def test_transcript_roundtrip(self, sample_transcript, temp_output_dir):
        """Test transcript save/load roundtrip."""
        output_path = temp_output_dir / "roundtrip.json"
        sample_transcript.to_json_file(output_path)

        loaded = Transcript.from_json_file(output_path)

        assert loaded.full_text == sample_transcript.full_text
        assert len(loaded.segments) == len(sample_transcript.segments)


@pytest.mark.e2e
class TestTranscriptClassification:
    """Tests for transcript classification with LLM.

    Note: These tests require a valid ANTHROPIC_API_KEY.
    """

    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return TranscriptClassifier()

    def test_classify_transcript_extracts_pain_points(self, classifier, sample_transcript):
        """Test classification extracts pain points."""
        analysis = classifier.classify_transcript(sample_transcript)

        assert len(analysis.pain_points) >= 1
        # Should find inventory-related pain point
        categories = [pp.category.lower() for pp in analysis.pain_points]
        assert any("inventory" in c for c in categories)

    def test_classify_transcript_extracts_wtp(self, classifier, sample_transcript):
        """Test classification extracts WTP signals."""
        analysis = classifier.classify_transcript(sample_transcript)

        # Transcript has clear WTP signals about $30-50/month
        assert len(analysis.wtp_signals) >= 1

    def test_classify_transcript_has_quotes(self, classifier, sample_transcript):
        """Test classification includes verbatim quotes."""
        analysis = classifier.classify_transcript(sample_transcript)

        for pp in analysis.pain_points:
            assert pp.verbatim_quote, "Pain point should have verbatim quote"

    def test_convert_to_interview_insights(self, classifier, sample_transcript):
        """Test converting analysis to InterviewInsight objects."""
        analysis = classifier.classify_transcript(sample_transcript)
        insights = classifier.convert_to_interview_insights(
            analysis, interview_id="INT001", participant_id="P001"
        )

        assert len(insights) == len(analysis.pain_points)
        for insight in insights:
            assert insight.participant_id == "P001"
            assert insight.interview_id.startswith("INT001")


@pytest.mark.e2e
class TestClassifyTranscriptCLI:
    """CLI tests for transcript classification."""

    def test_cli_classify_transcript_dry_run(self, cli_runner):
        """Test classify-transcript CLI in dry run mode."""
        from main import app

        result = cli_runner.invoke(
            app,
            [
                "interview",
                "classify-transcript",
                str(SAMPLE_TRANSCRIPT),
                "--participant",
                "P001",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Analysis complete" in result.stdout
        assert "Pain points found" in result.stdout
        assert "not saved" in result.stdout.lower()

    def test_cli_classify_transcript_saves_to_db(self, cli_runner, temp_db):
        """Test classify-transcript CLI saves to database."""
        from main import app

        result = cli_runner.invoke(
            app,
            [
                "interview",
                "classify-transcript",
                str(SAMPLE_TRANSCRIPT),
                "--participant",
                "P001",
                "--db-path",
                temp_db,
            ],
        )

        assert result.exit_code == 0
        assert "Saved" in result.stdout

        # Verify in database
        storage = InterviewStorage(db_path=temp_db)
        insights = storage.get_all_insights()
        assert len(insights) > 0


@pytest.mark.e2e
class TestFullVTTPipeline:
    """End-to-end tests for the full VTT pipeline."""

    def test_vtt_to_insights_pipeline(self, temp_output_dir, temp_db):
        """Test full pipeline: VTT -> JSON -> Classify -> DB."""
        # Step 1: Import VTT
        transcript = import_vtt_file(SAMPLE_VTT, participant_id="P001", output_dir=temp_output_dir)

        # Step 2: Classify
        classifier = TranscriptClassifier()
        analysis = classifier.classify_transcript(transcript)

        assert len(analysis.pain_points) >= 1

        # Step 3: Convert and save
        insights = classifier.convert_to_interview_insights(
            analysis, interview_id="INT001", participant_id="P001"
        )

        storage = InterviewStorage(db_path=temp_db)
        for insight in insights:
            storage.save_insight(insight)

        # Verify
        saved_insights = storage.get_all_insights()
        assert len(saved_insights) == len(insights)

    def test_vtt_pipeline_cli(self, cli_runner, temp_output_dir, temp_db):
        """Test VTT pipeline via CLI commands."""
        from main import app

        # Step 1: Import VTT
        result1 = cli_runner.invoke(
            app,
            [
                "interview",
                "import-vtt",
                str(SAMPLE_VTT),
                "--participant",
                "P001",
                "--output",
                str(temp_output_dir),
            ],
        )
        assert result1.exit_code == 0

        # Step 2: Classify transcript
        json_path = temp_output_dir / f"{SAMPLE_VTT.stem}.json"
        result2 = cli_runner.invoke(
            app,
            [
                "interview",
                "classify-transcript",
                str(json_path),
                "--participant",
                "P001",
                "--db-path",
                temp_db,
            ],
        )
        assert result2.exit_code == 0
        assert "Saved" in result2.stdout

    def test_insights_appear_in_opportunities(self, temp_output_dir, temp_db):
        """Test transcribed insights appear in opportunities report."""
        # Run full pipeline
        transcript = import_vtt_file(SAMPLE_VTT, participant_id="P001", output_dir=temp_output_dir)
        classifier = TranscriptClassifier()
        analysis = classifier.classify_transcript(transcript)
        insights = classifier.convert_to_interview_insights(
            analysis, interview_id="INT001", participant_id="P001"
        )

        storage = InterviewStorage(db_path=temp_db)
        for insight in insights:
            storage.save_insight(insight)

        # Check opportunities
        all_insights = storage.get_all_insights()
        assert len(all_insights) > 0

        # Check categories are populated
        categories = {i.pain_category for i in all_insights}
        assert len(categories) >= 1


@pytest.mark.e2e
@pytest.mark.slow
class TestWhisperTranscription:
    """Tests for Whisper transcription.

    These tests are marked as slow and require:
    1. openai-whisper installed
    2. A sample audio file

    Skip with: pytest -m "not slow"
    """

    @pytest.fixture
    def sample_audio_path(self):
        """Path to sample audio (if exists)."""
        audio_path = FIXTURES_DIR / "sample_interview.mp3"
        if not audio_path.exists():
            pytest.skip("Sample audio file not available")
        return audio_path

    def test_whisper_transcription(self, sample_audio_path, temp_output_dir):
        """Test Whisper transcription of audio file."""
        try:
            from research.transcription import transcribe_audio_whisper
        except ImportError:
            pytest.skip("openai-whisper not installed")

        transcript = transcribe_audio_whisper(
            sample_audio_path, model_name="tiny", output_dir=temp_output_dir
        )

        assert transcript.method == "whisper"
        assert transcript.model == "tiny"
        assert len(transcript.segments) > 0
        assert len(transcript.full_text) > 0

    def test_whisper_cli(self, cli_runner, sample_audio_path, temp_output_dir):
        """Test Whisper transcription via CLI."""
        from main import app

        result = cli_runner.invoke(
            app,
            [
                "interview",
                "transcribe",
                str(sample_audio_path),
                "--model",
                "tiny",
                "--output",
                str(temp_output_dir),
            ],
        )

        # May fail if whisper not installed
        if "not installed" in result.stdout:
            pytest.skip("openai-whisper not installed")

        assert result.exit_code == 0
        assert "Transcription complete" in result.stdout


@pytest.mark.e2e
class TestTranscriptFixtures:
    """Tests to verify test fixtures are valid."""

    def test_sample_vtt_exists(self):
        """Test sample VTT fixture exists."""
        assert SAMPLE_VTT.exists()

    def test_sample_vtt_is_valid(self):
        """Test sample VTT fixture is valid VTT format."""
        content = SAMPLE_VTT.read_text()
        assert content.startswith("WEBVTT")
        assert "-->" in content

    def test_sample_transcript_exists(self):
        """Test sample transcript fixture exists."""
        assert SAMPLE_TRANSCRIPT.exists()

    def test_sample_transcript_is_valid(self):
        """Test sample transcript fixture is valid JSON."""
        transcript = Transcript.from_json_file(SAMPLE_TRANSCRIPT)
        assert transcript.method == "zoom_vtt"
        assert len(transcript.segments) > 0
