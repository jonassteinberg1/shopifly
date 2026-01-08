"""E2E test fixtures and configuration."""

import os
import tempfile
import pytest
from pathlib import Path

from config import settings
from storage.sqlite import SQLiteStorage


# E2E test configuration with small limits
E2E_CONFIG = {
    "reddit_limit": 3,
    "appstore_limit": 3,
    "twitter_limit": 3,
    "community_limit": 3,
    "classify_limit": 5,
}


def has_reddit_credentials() -> bool:
    """Check if Reddit API credentials are configured."""
    return bool(settings.reddit_client_id and settings.reddit_client_secret)


def has_twitter_credentials() -> bool:
    """Check if Twitter API credentials are configured."""
    return bool(settings.twitter_bearer_token)


def has_anthropic_credentials() -> bool:
    """Check if Anthropic API credentials are configured."""
    return bool(settings.anthropic_api_key)


def has_airtable_credentials() -> bool:
    """Check if Airtable API credentials are configured."""
    return bool(settings.airtable_api_key and settings.airtable_base_id)


# Skip decorators for missing credentials
skip_without_reddit = pytest.mark.skipif(
    not has_reddit_credentials(),
    reason="Reddit API credentials not configured"
)

skip_without_twitter = pytest.mark.skipif(
    not has_twitter_credentials(),
    reason="Twitter API credentials not configured"
)

skip_without_anthropic = pytest.mark.skipif(
    not has_anthropic_credentials(),
    reason="Anthropic API credentials not configured"
)

skip_without_airtable = pytest.mark.skipif(
    not has_airtable_credentials(),
    reason="Airtable API credentials not configured"
)


@pytest.fixture
def e2e_config():
    """Return E2E test configuration."""
    return E2E_CONFIG.copy()


@pytest.fixture
def sqlite_storage(tmp_path):
    """Create a temporary SQLite storage for E2E tests."""
    db_path = tmp_path / "e2e_test.db"
    storage = SQLiteStorage(db_path=str(db_path))
    yield storage
    # Cleanup is automatic when tmp_path is cleaned up


@pytest.fixture
def persistent_sqlite_storage():
    """Create a SQLite storage in a persistent temp directory for multi-step tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "e2e_persistent.db")
        storage = SQLiteStorage(db_path=db_path)
        yield storage, db_path


@pytest.fixture
def e2e_db_path(tmp_path):
    """Return a path for E2E test database."""
    return str(tmp_path / "e2e_test.db")
