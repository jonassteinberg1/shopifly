"""Unit tests for classifier module."""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from scrapers.base import RawDataPoint, DataSource
from analysis.classifier import (
    Classifier,
    ClassifiedInsight,
    ProblemCategory,
    CLASSIFICATION_PROMPT,
)


class TestClassificationPrompt:
    """Tests for the classification prompt template."""

    def test_prompt_has_placeholders(self):
        """Test that prompt has required placeholders."""
        assert "{title}" in CLASSIFICATION_PROMPT
        assert "{source}" in CLASSIFICATION_PROMPT
        assert "{content}" in CLASSIFICATION_PROMPT

    def test_prompt_requests_json(self):
        """Test that prompt requests JSON output."""
        assert "JSON" in CLASSIFICATION_PROMPT
        assert "problem_statement" in CLASSIFICATION_PROMPT
        assert "category" in CLASSIFICATION_PROMPT
        assert "frustration_level" in CLASSIFICATION_PROMPT

    def test_prompt_includes_all_categories(self):
        """Test that prompt lists all valid categories."""
        for cat in ProblemCategory:
            assert cat.value in CLASSIFICATION_PROMPT


class TestClassifier:
    """Tests for Classifier class."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create a mock Anthropic client."""
        with patch("analysis.classifier.anthropic.Anthropic") as mock:
            yield mock

    @pytest.fixture
    def classifier(self, mock_anthropic_client):
        """Create a Classifier with mocked client."""
        with patch("analysis.classifier.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            mock_settings.anthropic_model = "claude-3-haiku-20240307"
            return Classifier()

    def test_classifier_initialization(self, classifier):
        """Test classifier initializes with correct model."""
        assert classifier.model == "claude-3-haiku-20240307"

    @pytest.mark.asyncio
    async def test_classify_success(
        self, classifier, sample_raw_datapoint, mock_anthropic_response
    ):
        """Test successful classification."""
        # Mock the API response
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_anthropic_response))]
        classifier.client.messages.create = MagicMock(return_value=mock_message)

        result = await classifier.classify(sample_raw_datapoint)

        assert result is not None
        assert isinstance(result, ClassifiedInsight)
        assert result.source_id == sample_raw_datapoint.source_id
        assert result.category == ProblemCategory.ANALYTICS
        assert result.frustration_level == 4
        assert result.willingness_to_pay is True

    @pytest.mark.asyncio
    async def test_classify_handles_markdown_code_blocks(
        self, classifier, sample_raw_datapoint, mock_anthropic_response
    ):
        """Test handling of JSON wrapped in markdown code blocks."""
        json_with_markdown = f"```json\n{json.dumps(mock_anthropic_response)}\n```"

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json_with_markdown)]
        classifier.client.messages.create = MagicMock(return_value=mock_message)

        result = await classifier.classify(sample_raw_datapoint)

        assert result is not None
        assert result.category == ProblemCategory.ANALYTICS

    @pytest.mark.asyncio
    async def test_classify_invalid_json_returns_none(
        self, classifier, sample_raw_datapoint
    ):
        """Test that invalid JSON returns None."""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="This is not valid JSON")]
        classifier.client.messages.create = MagicMock(return_value=mock_message)

        result = await classifier.classify(sample_raw_datapoint)

        assert result is None

    @pytest.mark.asyncio
    async def test_classify_api_error_returns_none(
        self, classifier, sample_raw_datapoint
    ):
        """Test that API errors return None."""
        classifier.client.messages.create = MagicMock(
            side_effect=Exception("API Error")
        )

        result = await classifier.classify(sample_raw_datapoint)

        assert result is None

    @pytest.mark.asyncio
    async def test_classify_truncates_long_content(
        self, classifier, mock_anthropic_response
    ):
        """Test that long content is truncated."""
        long_content = "x" * 5000  # Longer than 2000 char limit
        dp = RawDataPoint(
            source=DataSource.REDDIT,
            source_id="test",
            url="https://example.com",
            content=long_content,
            created_at=datetime.now(),
        )

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_anthropic_response))]
        classifier.client.messages.create = MagicMock(return_value=mock_message)

        await classifier.classify(dp)

        # Check that the prompt was called with truncated content
        call_args = classifier.client.messages.create.call_args
        messages = call_args.kwargs["messages"]
        prompt_content = messages[0]["content"]
        # Content in prompt should be truncated
        assert len(prompt_content) < len(long_content) + 500  # Allow for template

    @pytest.mark.asyncio
    async def test_classify_preserves_source_info(
        self, classifier, sample_raw_datapoint, mock_anthropic_response
    ):
        """Test that source info is preserved in result."""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_anthropic_response))]
        classifier.client.messages.create = MagicMock(return_value=mock_message)

        result = await classifier.classify(sample_raw_datapoint)

        assert result.source_id == sample_raw_datapoint.source_id
        assert result.source_url == sample_raw_datapoint.url
        assert result.original_title == sample_raw_datapoint.title
        assert result.content_snippet == sample_raw_datapoint.content[:500]

    @pytest.mark.asyncio
    async def test_classify_batch_yields_results(
        self, classifier, mock_anthropic_response
    ):
        """Test classify_batch yields results for valid inputs."""
        datapoints = [
            RawDataPoint(
                source=DataSource.REDDIT,
                source_id=f"test_{i}",
                url=f"https://example.com/{i}",
                content=f"Test content {i}",
                created_at=datetime.now(),
            )
            for i in range(3)
        ]

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_anthropic_response))]
        classifier.client.messages.create = MagicMock(return_value=mock_message)

        results = []
        async for result in classifier.classify_batch(datapoints, concurrency=2):
            results.append(result)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_classify_batch_handles_partial_failures(
        self, classifier, mock_anthropic_response
    ):
        """Test classify_batch handles some failures gracefully."""
        datapoints = [
            RawDataPoint(
                source=DataSource.REDDIT,
                source_id=f"test_{i}",
                url=f"https://example.com/{i}",
                content=f"Test content {i}",
                created_at=datetime.now(),
            )
            for i in range(3)
        ]

        # First call succeeds, second fails, third succeeds
        mock_success = MagicMock()
        mock_success.content = [MagicMock(text=json.dumps(mock_anthropic_response))]

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("API Error")
            return mock_success

        classifier.client.messages.create = MagicMock(side_effect=side_effect)

        results = []
        async for result in classifier.classify_batch(datapoints, concurrency=1):
            results.append(result)

        # Should get 2 results (1 failure skipped)
        assert len(results) == 2


class TestClassifiedInsightFromResponse:
    """Tests for creating ClassifiedInsight from API responses."""

    def test_all_categories_parseable(self):
        """Test that all category values can create insights."""
        for category in ProblemCategory:
            response = {
                "problem_statement": "Test problem",
                "category": category.value,
                "secondary_categories": [],
                "frustration_level": 3,
                "clarity_score": 3,
                "willingness_to_pay": False,
                "wtp_quotes": [],
                "current_workaround": None,
                "keywords": ["test"],
            }

            insight = ClassifiedInsight(
                source_id="test",
                source_url="https://example.com",
                problem_statement=response["problem_statement"],
                category=ProblemCategory(response["category"]),
                secondary_categories=[],
                frustration_level=response["frustration_level"],
                clarity_score=response["clarity_score"],
                willingness_to_pay=response["willingness_to_pay"],
                content_snippet="Test",
            )

            assert insight.category == category

    def test_secondary_categories_parsing(self):
        """Test parsing multiple secondary categories."""
        insight = ClassifiedInsight(
            source_id="test",
            source_url="https://example.com",
            problem_statement="Test",
            category=ProblemCategory.ANALYTICS,
            secondary_categories=[
                ProblemCategory.PRICING,
                ProblemCategory.ADMIN,
            ],
            frustration_level=3,
            clarity_score=3,
            willingness_to_pay=False,
            content_snippet="Test",
        )

        assert len(insight.secondary_categories) == 2
        assert ProblemCategory.PRICING in insight.secondary_categories
        assert ProblemCategory.ADMIN in insight.secondary_categories
