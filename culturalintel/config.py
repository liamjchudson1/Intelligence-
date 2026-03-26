"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All platform configuration, loaded from env vars / .env file."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Claude API
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 16000

    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "culturalintel/0.1"

    # Twitter / X
    twitter_bearer_token: str = ""

    # Discord
    discord_bot_token: str = ""

    # Delivery
    beehiiv_api_key: str = ""
    beehiiv_publication_id: str = ""
    slack_webhook_url: str = ""
    teams_webhook_url: str = ""

    # Database
    database_url: str = "sqlite:///data/culturalintel.db"

    # Scheduler (cron: minute hour day month day-of-week)
    report_schedule_cron: str = Field(default="0 8 * * 1", description="Weekly Monday 8am")


settings = Settings()
