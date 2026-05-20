"""
Tests for AIService.
All offline — the real summarize_and_label is replaced with a fake function.
"""
import asyncio
import pytest
from unittest.mock import patch

from ai import Article, LabeledSummary, Topic, Sentiment
from ai.providers.base import ProviderError
from src.services.ai_service import AIService


# ── Fixtures: reusable test data ──────────────────────────────────────────────

@pytest.fixture
def sample_article() -> Article:
    """A fake article. Note: field is 'source', NOT 'source_name'."""
    return Article(
        title="Test Article",
        url="https://example.com/article-1",
        content="Body of the article. " * 20,
        source="example",
    )


@pytest.fixture
def fake_summary() -> LabeledSummary:
    """A fake AI result we return instead of calling the real AI."""
    return LabeledSummary(
        summary="A test summary.",
        topic=Topic.TECH,
        sentiment=Sentiment.NEUTRAL,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_hit_skips_provider(tmp_path, sample_article, fake_summary):
    """Calling label() twice with the same article should only call AI once."""
    svc = AIService(cache_dir=tmp_path)

    with patch(
        "src.services.ai_service.summarize_and_label",
        return_value=fake_summary,
    ) as mock_llm:
        first  = await svc.label(sample_article)
        second = await svc.label(sample_article)  # same article → cache hit

    assert first  == fake_summary
    assert second == fake_summary
    assert mock_llm.call_count == 1  # AI called once, second call used cache


@pytest.mark.asyncio
async def test_retries_on_provider_error(tmp_path, sample_article, fake_summary):
    """Should retry on ProviderError and succeed when AI eventually works."""
    svc = AIService(cache_dir=tmp_path)

    # Two failures then one success
    responses = [ProviderError("429"), ProviderError("429"), fake_summary]

    with patch(
        "src.services.ai_service.summarize_and_label",
        side_effect=responses,
    ) as mock_llm:
        result = await svc.label(sample_article)

    assert result == fake_summary
    assert mock_llm.call_count == 3  # failed twice, succeeded on third try


@pytest.mark.asyncio
async def test_gives_up_after_max_retries(tmp_path, sample_article, monkeypatch):
    """After max retries all fail, should raise ProviderError (not hang)."""
    monkeypatch.setattr("src.services.ai_service.settings.llm_max_retries", 2)
    svc = AIService(cache_dir=tmp_path)

    with patch(
        "src.services.ai_service.summarize_and_label",
        side_effect=ProviderError("always fails"),
    ):
        with pytest.raises(ProviderError):
            await svc.label(sample_article)