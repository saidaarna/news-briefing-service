"""
End-to-end pipeline tests — fully offline (no HTTP, no AI provider calls).

These tests exercise the full run_pipeline() call stack with mocked
fetch and AI services so the full integration path is covered without
any external dependencies.
"""
from __future__ import annotations

import asyncio
import os
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from ai.schemas import Article, LabeledSummary, Topic, Sentiment
from src.models import UserProfile, ProcessedArticle, FetchResult, Source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article(title: str = "Test Article", source: str = "TestSrc") -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        source=source,
        content=f"Content about {title}. This is a full sentence of article body text.",
    )


def _make_labeled(topic: str = "Tech", sentiment: str = "neutral") -> LabeledSummary:
    return LabeledSummary(
        summary="A short summary of the article.",
        topic=Topic(topic),
        sentiment=Sentiment(sentiment),
    )


def _make_user(preferred_topics: list[str] | None = None) -> UserProfile:
    return UserProfile(
        username="testuser",
        preferred_topics=[Topic(t) for t in (preferred_topics or [])],
        excluded_sources=[],
    )


# ---------------------------------------------------------------------------
# Happy-path end-to-end test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_pipeline_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full pipeline produces a Markdown digest file with no external calls."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)

    from src.config import get_settings
    get_settings.cache_clear()

    articles = [
        _make_article("AI Breakthrough", "TechCrunch"),
        _make_article("Space Discovery", "ScienceDaily"),
    ]
    labeled = _make_labeled("Tech")

    # Mock FetchService.fetch_all to return our articles
    mock_fetch_svc = MagicMock()
    mock_fetch_svc.fetch_all = AsyncMock(return_value=[
        FetchResult(
            source=Source(name="TechCrunch", url="https://techcrunch.com/feed", kind="rss"),
            articles=articles,
        )
    ])

    # Mock AIService.label to return a LabeledSummary
    with patch("src.concurrency.pipeline.AIService") as MockAI, \
         patch("src.concurrency.pipeline.ContentCache") as MockCache, \
         patch("src.core.digest_builder.DigestBuilder.create_markdown") as mock_digest:

        # cache always misses so all articles go through AI
        cache_instance = MagicMock()
        cache_instance.get.return_value = None
        MockCache.return_value = cache_instance

        ai_instance = MagicMock()
        ai_instance.label = AsyncMock(return_value=labeled)
        MockAI.return_value = ai_instance

        mock_digest.return_value = str(tmp_path / "digest.md")

        from src.concurrency.pipeline import run_pipeline
        result = await run_pipeline(_make_user(), fetch_svc=mock_fetch_svc)

    assert result == str(tmp_path / "digest.md")
    assert ai_instance.label.call_count == len(articles)


@pytest.mark.asyncio
async def test_run_pipeline_all_sources_fail_produces_empty_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When every source fails, the pipeline still produces a digest (graceful degradation)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)

    from src.config import get_settings
    get_settings.cache_clear()

    mock_fetch_svc = MagicMock()
    mock_fetch_svc.fetch_all = AsyncMock(return_value=[
        FetchResult(
            source=Source(name="BadFeed", url="https://broken.example.com", kind="rss"),
            articles=[],
            error="Connection refused",
        )
    ])

    with patch("src.concurrency.pipeline.AIService") as MockAI, \
         patch("src.concurrency.pipeline.ContentCache") as MockCache, \
         patch("src.core.digest_builder.DigestBuilder.create_markdown") as mock_digest:

        cache_instance = MagicMock()
        cache_instance.get.return_value = None
        MockCache.return_value = cache_instance

        mock_digest.return_value = str(tmp_path / "empty_digest.md")

        from src.concurrency.pipeline import run_pipeline
        result = await run_pipeline(_make_user(), fetch_svc=mock_fetch_svc)

    # Digest was still created (graceful degradation)
    assert result == str(tmp_path / "empty_digest.md")
    # AI was never called (no articles to label)
    MockAI.return_value.label.assert_not_called()


@pytest.mark.asyncio
async def test_run_pipeline_ai_failure_skips_article(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An AI labeling failure for one article does not abort the whole pipeline."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)

    from src.config import get_settings
    get_settings.cache_clear()
    articles = [_make_article("Good Article"), _make_article("Bad Article")]

    mock_fetch_svc = MagicMock()
    mock_fetch_svc.fetch_all = AsyncMock(return_value=[
        FetchResult(
            source=Source(name="Feed", url="https://example.com/feed", kind="rss"),
            articles=articles,
        )
    ])

    with patch("src.concurrency.pipeline.AIService") as MockAI, \
         patch("src.concurrency.pipeline.ContentCache") as MockCache, \
         patch("src.core.digest_builder.DigestBuilder.create_markdown") as mock_digest:

        cache_instance = MagicMock()
        cache_instance.get.return_value = None
        MockCache.return_value = cache_instance

        ai_instance = MagicMock()
        # First article succeeds, second raises
        ai_instance.label = AsyncMock(side_effect=[
            _make_labeled("Tech"),
            RuntimeError("provider timeout"),
        ])
        MockAI.return_value = ai_instance

        captured_processed: list[ProcessedArticle] = []

        def _capture(processed, user):
            captured_processed.extend(processed)
            return str(tmp_path / "partial.md")

        mock_digest.side_effect = _capture

        from src.concurrency.pipeline import run_pipeline
        result = await run_pipeline(_make_user(), fetch_svc=mock_fetch_svc)

    # Only 1 processed article (the one that succeeded)
    assert len(captured_processed) == 1
    assert captured_processed[0].article.title == "Good Article"


# ---------------------------------------------------------------------------
# Digest file format tests
# ---------------------------------------------------------------------------

def test_digest_builder_writes_markdown_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """DigestBuilder writes a valid .md file with expected section headers."""
    monkeypatch.chdir(tmp_path)

    article = _make_article("Test Headline", "Reuters")
    labeled = _make_labeled("Tech", "positive")
    pa = ProcessedArticle(
        article=article,
        labeled=labeled,
        content_hash="abc123",
    )
    user = _make_user()

    from src.core.digest_builder import DigestBuilder
    path_str = DigestBuilder().create_markdown([pa], user)
    path = Path(path_str)

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Test Headline" in text
    assert "Reuters" in text
    assert "TECH" in text.upper()  # Topic renders as Topic.TECH or Tech depending on version


def test_digest_builder_empty_articles_produces_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DigestBuilder with zero articles still writes a valid .md file."""
    monkeypatch.chdir(tmp_path)
    user = _make_user()

    from src.core.digest_builder import DigestBuilder
    path_str = DigestBuilder().create_markdown([], user)
    assert Path(path_str).exists()


# ---------------------------------------------------------------------------
# Error-path: malformed UserProfile is rejected at validation time
# ---------------------------------------------------------------------------

def test_user_profile_rejects_empty_username() -> None:
    """UserProfile must have a non-empty username."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        UserProfile(username="")


def test_user_profile_rejects_negative_max_items() -> None:
    """max_items_per_topic must be >= 1."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        UserProfile(username="alice", max_items_per_topic=0)
