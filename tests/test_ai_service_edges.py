"""Edge case tests — timeout and corrupt cache file."""
import asyncio
import pytest
from unittest.mock import patch

from ai import Article, LabeledSummary, Topic, Sentiment
from src.services.ai_service import AIService


@pytest.fixture
def sample_article() -> Article:
    return Article(
        title="Test",
        url="https://example.com/a",
        content="Body of the article. " * 20,
        source="example",
    )


@pytest.fixture
def fake_summary() -> LabeledSummary:
    return LabeledSummary(
        summary="A test summary.",
        topic=Topic.TECH,
        sentiment=Sentiment.NEUTRAL,
    )


@pytest.mark.asyncio
async def test_timeout_raises_error(tmp_path, sample_article, monkeypatch):
    """If AI call takes longer than the timeout, TimeoutError must be raised."""
    # Set timeout to 10ms so we can trigger it instantly in tests
    monkeypatch.setattr("src.services.ai_service.settings.llm_timeout_seconds", 0.01)

    async def forever(_article):
        await asyncio.sleep(10)   # 10 seconds — way longer than 0.01s limit
        return None

    with patch("src.services.ai_service.asyncio.to_thread", side_effect=forever):
        svc = AIService(cache_dir=tmp_path)
        with pytest.raises(asyncio.TimeoutError):
            await svc.label(sample_article)


@pytest.mark.asyncio
async def test_corrupt_cache_is_recovered(tmp_path, sample_article, fake_summary):
    """If the cache file has invalid JSON, delete it and call AI again — don't crash."""
    svc = AIService(cache_dir=tmp_path)

    # Write garbage into exactly where the cache file would be
    cache_file = svc._cache_dir / f"{svc._cache_key(sample_article)}.json"
    cache_file.write_text("{ NOT VALID JSON !!!", encoding="utf-8")

    with patch(
        "src.services.ai_service.summarize_and_label",
        return_value=fake_summary,
    ):
        result = await svc.label(sample_article)

    assert result == fake_summary  # recovered correctly