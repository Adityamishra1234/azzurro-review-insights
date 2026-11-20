"""Application configuration.

Loaded from environment variables via pydantic-settings so the same codebase
runs locally, in Docker, and on Render without changes.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    """Runtime configuration.

    Values may be overridden by an .env file or process environment. Defaults are
    chosen so the app runs with zero configuration against a local SQLite file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage
    database_url: str = Field(
        default=f"sqlite:///{DATA_DIR / 'reviews.db'}",
        description="SQLAlchemy database URL. Defaults to a SQLite file under data/.",
    )

    # Scraper behaviour
    scrape_headless: bool = Field(default=True, description="Run Playwright headless.")
    scrape_max_pages_per_property: int = Field(
        default=20,
        ge=1,
        description="Hard cap on review pages pulled per property per run. Prevents runaway jobs.",
    )
    scrape_page_delay_seconds: float = Field(
        default=1.5,
        ge=0,
        description="Polite delay between review page fetches. Reduces the chance of rate limiting.",
    )
    scrape_request_timeout_seconds: int = Field(default=30, ge=5)
    scrape_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    )

    # Topic classifier
    enable_llm_topics: bool = Field(
        default=False,
        description="When true, use an OpenAI-compatible LLM for topic tagging as well as keywords.",
    )
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    # API
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:4173"]
    )


settings = Settings()
