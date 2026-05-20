import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.models import UserProfile, Topic, FetchResult, Source, Article

def _make_user():
    return UserProfile(username="test", preferred_topics=[Topic.Tech], excluded_sources=[])

def _make_article():
    return Article(title="T", url="https://x.com/1", source="X", content="body text here ok")

@pytest.mark.asyncio
async def test_pipeline_fetch_failure_does_not_crash():
    """If all sources fail, pipeline should not raise — just produce empty digest."""
    from src.services.fetch_service import FetchService
    source = Source(name="Bad", url="https://bad.com/rss", kind="rss")
    
    svc = MagicMock(spec=FetchService)
    svc.fetch_all = AsyncMock(return_value=[
        FetchResult(source=source, error="HTTP 500")
    ])
    FetchService.collect_articles = MagicMock(return_value=[])

    # Once pipeline is wired, assert digest is still produced (empty)
    # digest = await run_pipeline(_make_user(), svc, ...)
    # assert "No articles" in open(digest).read()