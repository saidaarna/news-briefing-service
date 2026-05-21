"""
Typed configuration for the SE layer — reads from environment / .env file.

Usage (anywhere in src/):
    from src.config import settings

    db_url = settings.database_url
    timeout = settings.fetch_timeout_seconds

All fields have sane defaults except secrets (LLM keys) — those raise
at startup if the selected provider's key is missing.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables / .env.

    Pydantic-settings automatically reads from a `.env` file in the working
    directory (or the path specified by `env_file`).  Environment variables
    override `.env` values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # tolerate unknown vars in .env without crashing
    )

    # ------------------------------------------------------------------
    # LLM provider
    # ------------------------------------------------------------------
    llm_provider: Literal["anthropic", "openai", "gemini"] = Field(
        default="anthropic",
        description="Which LLM backend to use (anthropic | openai | gemini).",
    )
    llm_model: str = Field(
        default="claude-sonnet-4-6",
        description="Provider-specific model identifier.",
    )
    anthropic_api_key: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)
    google_api_key: str = Field(default="", repr=False)

    # ------------------------------------------------------------------
    # Embedding provider
    # ------------------------------------------------------------------
    embedding_provider: Literal["openai", "gemini"] = Field(
        default="openai",
        description="Embedding backend (openai | gemini).",
    )
    embedding_model: str = Field(default="text-embedding-3-small")

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:dev@localhost:5432/newsbrief",
        description="AsyncPG-compatible connection string.",
    )

    # ------------------------------------------------------------------
    # Digest output
    # ------------------------------------------------------------------
    digests_dir: str = Field(
        default="./digests",
        description="Directory where daily digest .md files are written.",
    )

    # ------------------------------------------------------------------
    # Fetch service
    # ------------------------------------------------------------------
    fetch_timeout_seconds: int = Field(
        default=15,
        ge=1,
        le=120,
        description="Per-source HTTP timeout in seconds.",
    )
    max_parallel_fetches: int = Field(
        default=8,
        ge=1,
        le=50,
        description="asyncio.Semaphore bound for concurrent source fetches.",
    )
    rss_feeds_file: str = Field(
        default="data/rss_feeds.txt",
        description="Path to the newline-separated RSS feed list.",
    )

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------
    dedup_near_duplicate_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Jaccard similarity cutoff for near-duplicate detection.",
    )

    # ------------------------------------------------------------------
    # AI service retries / rate-limiting
    # ------------------------------------------------------------------
    ai_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for transient AI API errors.",
    )
    # Alias used by ai_service.py (tests monkeypatch this name)
    llm_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Alias for ai_max_retries used by ai_service internals.",
    )
    ai_semaphore_limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent in-flight AI API calls (rate-limit guard).",
    )
    llm_concurrency: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Alias for ai_semaphore_limit used by ai_service internals.",
    )
    llm_timeout_seconds: float = Field(
        default=30.0,
        ge=0.5,
        le=300.0,
        description="Hard timeout (seconds) per single AI API call attempt.",
    )
    llm_retry_backoff_base: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Base multiplier for exponential backoff between AI retries.",
    )
    ai_cache_dir: str = Field(
        default=".cache/newsbrief",
        description="Directory for file-based AI label cache.",
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field(
        default="INFO",
        description="Python logging level (DEBUG | INFO | WARNING | ERROR).",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        """Ensure the log level is a valid Python logging constant."""
        upper = v.upper()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}, got {v!r}")
        return upper

    @model_validator(mode="after")
    def _check_api_keys(self) -> "Settings":
        """Fail fast if the selected provider's API key is missing.

        This check only applies when running outside the test suite (i.e. when
        a real provider call would actually be made).  Offline / mocked tests
        set dummy env values, which is fine.
        """
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file."
            )
        if self.llm_provider in ("openai",) and not self.openai_api_key:
            raise ValueError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
                "Add it to your .env file."
            )
        if self.llm_provider == "gemini" and not self.google_api_key:
            raise ValueError(
                "LLM_PROVIDER=gemini but GOOGLE_API_KEY is not set. "
                "Add it to your .env file."
            )
        if self.embedding_provider == "openai" and not self.openai_api_key:
            raise ValueError(
                "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is not set."
            )
        if self.embedding_provider == "gemini" and not self.google_api_key:
            raise ValueError(
                "EMBEDDING_PROVIDER=gemini but GOOGLE_API_KEY is not set."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call).

    Use this factory rather than constructing Settings() directly so that
    all modules share the same object and tests can clear the cache easily.
    To override in tests::

        get_settings.cache_clear()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    """
    return Settings()


class _LazySettings:
    """Lazy proxy so that `from src.config import settings` does NOT
    trigger Settings() construction (and API-key validation) at import time.
    Actual construction is deferred until the first attribute access.
    """

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)

    def __repr__(self) -> str:  # pragma: no cover
        return repr(get_settings())


# Module-level alias for convenience:  `from src.config import settings`
# This is a lazy proxy — safe to import in tests without a .env file.
settings: Settings = _LazySettings()  # type: ignore[assignment]


def configure_logging() -> None:
    """Apply the log_level from settings to the root logger.

    Call once at application startup (in cli.py or api.py).
    """
    level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
