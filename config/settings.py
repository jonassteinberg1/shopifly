"""Configuration settings for the Shopify requirements gatherer."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Reddit API
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ShopifyRequirementsGatherer/1.0"

    # Twitter/X API
    twitter_bearer_token: str = ""

    # Anthropic API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-haiku-20240307"

    # Airtable
    airtable_api_key: str = ""
    airtable_base_id: str = ""

    # Scraping settings
    request_delay_seconds: float = 1.0
    max_retries: int = 3

    # Target subreddits
    reddit_subreddits: list[str] = [
        "shopify",
        "ecommerce",
        "dropship",
        "smallbusiness",
        "Entrepreneur",
    ]


settings = Settings()
