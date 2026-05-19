"""
SE-layer Pydantic models for Topic 3 — AI News Briefing Service.

These models extend / complement the AI module's own schemas (ai.schemas).
They are used by storage, services, and the pipeline — NOT by ai/ internals.

Rules:
  - No naked dicts across module boundaries (rubric requirement).
  - Every public field is typed.
  - Import AI schemas from ai.schemas, not from here; these add SE-layer fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

# Re-export AI-provided types so the rest of src/ can import from one place.
from ai.schemas import (
    Article,
    Digest,
    DigestItem,
    LabeledSummary,
    Sentiment,
    Topic,
)

__all__ = [
    # Re-exports from ai.schemas
    "Article",
    "LabeledSummary",
    "DigestItem",
    "Digest",
    "Topic",
    "Sentiment",
    # SE-layer models
    "Source",
    "UserProfile",
    "ProcessedArticle",
    "FetchResult",
]


# ---------------------------------------------------------------------------
# Source — represents a configured news source (RSS feed or HTML page).
# ---------------------------------------------------------------------------


class Source(BaseModel):
    """A configured news source.

    Discriminator field `kind` allows the fetch service to dispatch
    the correct fetcher without isinstance() checks.
    """

    name: str = Field(..., description="Human-readable label, e.g. 'BBC News'")
    url: str = Field(..., description="Full URL of the feed or HTML page")
    kind: str = Field(
        ...,
        description="'rss' for RSS/Atom feeds, 'html' for direct HTML scrape",
        pattern="^(rss|html)$",
    )

    @field_validator("url")
    @classmethod
    def _url_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Source URL must not be empty")
        return v.strip()


# ---------------------------------------------------------------------------
# UserProfile — stored in DB or JSON; controls digest personalization.
# ---------------------------------------------------------------------------


class UserProfile(BaseModel):
    """A user's digest preferences loaded from persistent storage."""

    username: str = Field(..., min_length=1)
    preferred_topics: list[Topic] = Field(
        default_factory=list,
        description="Only articles with these topics appear in the digest.",
    )
    excluded_sources: list[str] = Field(
        default_factory=list,
        description="Articles whose source name matches any entry are dropped.",
    )
    max_items_per_topic: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Cap on digest items per topic section.",
    )

    @field_validator("username")
    @classmethod
    def _username_stripped(cls, v: str) -> str:
        return v.strip()


# ---------------------------------------------------------------------------
# FetchResult — raw output of one fetch task before dedup / AI processing.
# ---------------------------------------------------------------------------


class FetchResult(BaseModel):
    """The outcome of fetching a single Source.

    On success, `articles` is populated and `error` is None.
    On failure, `articles` is empty and `error` describes what went wrong.
    This enables graceful degradation: a failed source doesn't abort the run.
    """

    source: Source
    articles: list[Article] = Field(default_factory=list)
    error: Optional[str] = Field(
        default=None,
        description="Set when fetching/parsing failed; None on success.",
    )
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def ok(self) -> bool:
        """True when the fetch succeeded."""
        return self.error is None


# ---------------------------------------------------------------------------
# ProcessedArticle — article after dedup check and AI labeling.
# Stored in the DB; referenced by digest entries.
# ---------------------------------------------------------------------------


class ProcessedArticle(BaseModel):
    """An Article that has survived dedup and been labeled by the AI.

    `content_hash` is the SHA-256 from ai.content_hash — used as the cache key
    so we never re-call the LLM for an article we've already seen.
    """

    article: Article
    labeled: LabeledSummary
    content_hash: str = Field(..., description="SHA-256 of normalized body text")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

