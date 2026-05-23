"""
Unit tests for the services layer (AIService, FetchService configuration).

All tests are fully offline — no real HTTP calls, no real AI provider calls.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from ai.schemas import Article, LabeledSummary, Topic, Sentiment
from ai.providers.base import ProviderError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article(title: str = "Sample Article", source: str = "TestFeed") -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        source=source,
        content=f"Detailed content about {title}. More words to pass min length.",
    )


def _make_labeled() -> LabeledSummary:
    return LabeledSummary(
        summary="Summary text.",
        topic=Topic("Tech"),
        sentiment=Sentiment("neutral"),
    )


# ---------------------------------------------------------------------------
# AIService unit tests
# ---------------------------------------------------------------------------

class TestAIServiceLabel:
    """Tests for AIService.label() — caching, retries, timeout, logging."""

    def test_cache_is_written_after_first_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After a successful label call, a JSON file is written to the cache dir."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        from src.services.ai_service import AIService

        labeled = _make_labeled()
        article = _make_article()

        with patch("src.services.ai_service.summarize_and_label", return_value=labeled):
            svc = AIService(cache_dir=tmp_path)
            asyncio.get_event_loop().run_until_complete(svc.label(article))

        cache_files = list((tmp_path / "labeled").glob("*.json"))
        assert len(cache_files) == 1

    def test_second_call_uses_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Calling label() twice for the same article only invokes the AI once."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        from src.services.ai_service import AIService

        labeled = _make_labeled()
        article = _make_article()

        call_count = 0

        def _fake_provider(art: Article) -> LabeledSummary:
            nonlocal call_count
            call_count += 1
            return labeled

        with patch("src.services.ai_service.summarize_and_label", side_effect=_fake_provider):
            svc = AIService(cache_dir=tmp_path)
            loop = asyncio.new_event_loop()
            loop.run_until_complete(svc.label(article))
            loop.run_until_complete(svc.label(article))
            loop.close()

        assert call_count == 1, "AI provider should only be called once; second call hits cache"

    def test_corrupt_cache_file_is_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A corrupt cache file is deleted and the AI call is re-issued."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        from src.services.ai_service import AIService
        import hashlib

        article = _make_article()
        labeled = _make_labeled()

        # Write garbage to the cache slot
        cache_labeled_dir = tmp_path / "labeled"
        cache_labeled_dir.mkdir(parents=True)
        key = hashlib.sha256(article.content.encode()).hexdigest()
        (cache_labeled_dir / f"{key}.json").write_text("NOT VALID JSON", encoding="utf-8")

        with patch("src.services.ai_service.summarize_and_label", return_value=labeled):
            svc = AIService(cache_dir=tmp_path)
            result = asyncio.get_event_loop().run_until_complete(svc.label(article))

        assert result.topic == labeled.topic

    def test_provider_error_is_surfaced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ProviderError propagates after all retries are exhausted."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MAX_RETRIES", "1")

        from src.services.ai_service import AIService
        from src.config import get_settings
        get_settings.cache_clear()

        with patch(
            "src.services.ai_service.summarize_and_label",
            side_effect=ProviderError("rate limited"),
        ):
            svc = AIService(cache_dir=tmp_path)
            with pytest.raises(ProviderError):
                asyncio.get_event_loop().run_until_complete(svc.label(_make_article()))

        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# FetchService configuration unit tests
# ---------------------------------------------------------------------------

class TestFetchServiceConfig:
    """Tests that FetchService reads settings correctly."""

    def test_rss_feeds_file_path_is_configurable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FetchService uses the rss_feeds_file from settings."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        from src.config import get_settings, Settings
        get_settings.cache_clear()

        from src.services.fetch_service import FetchService
        svc = FetchService(get_settings())
        # The attribute exists and is a non-empty string
        assert isinstance(svc._cfg.rss_feeds_file, str)
        assert len(svc._cfg.rss_feeds_file) > 0

        get_settings.cache_clear()

    def test_timeout_is_configurable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FetchService timeout is taken from settings.fetch_timeout_seconds."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("FETCH_TIMEOUT_SECONDS", "42")

        from src.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert s.fetch_timeout_seconds == 42
        get_settings.cache_clear()

    def test_semaphore_limit_is_configurable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """max_parallel_fetches is read from settings."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("MAX_PARALLEL_FETCHES", "4")

        from src.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert s.max_parallel_fetches == 4
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Error-path: Settings validation
# ---------------------------------------------------------------------------

class TestSettingsValidation:
    """Settings rejects invalid configuration at construction time."""

    def test_invalid_log_level_raises(self) -> None:
        """log_level must be a valid Python logging constant."""
        import pydantic
        from src.config import Settings

        with pytest.raises((pydantic.ValidationError, ValueError)):
            Settings(
                log_level="VERBOSE",
                anthropic_api_key="key",
                openai_api_key="key",
                google_api_key="key",
            )

    def test_fetch_timeout_below_minimum_raises(self) -> None:
        """fetch_timeout_seconds must be >= 1."""
        import pydantic
        from src.config import Settings

        with pytest.raises((pydantic.ValidationError, ValueError)):
            Settings(
                fetch_timeout_seconds=0,
                anthropic_api_key="key",
                openai_api_key="key",
                google_api_key="key",
            )
