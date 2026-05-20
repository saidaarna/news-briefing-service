import asyncio
import logging
from src.models import UserProfile, ProcessedArticle
from src.config import settings
from src.services.fetch_service import FetchService
# These come from Nigar — stub with None until Day 6
# from src.core.dedup import run_dedup
# from src.services.ai_service import AIService

logger = logging.getLogger(__name__)

async def run_pipeline(user: UserProfile) -> str:
    logger.info("pipeline_start user=%s", user.username)

    # 1. Fetch
    fetch_svc = FetchService(settings)
    raw_results = await fetch_svc.fetch_all()
    raw_articles = FetchService.collect_articles(raw_results)

    # 2. Dedup (Nigar)
    from src.core.dedup import run_dedup
    unique = run_dedup(raw_articles)
    logger.info("dedup before=%d after=%d", len(raw_articles), len(unique))

    # 3. Cache filter (Ləman)
    from src.core.caching import ContentCache
    cache = ContentCache()
    new_articles = [a for a in unique if not cache.get(a.content_hash)]

    # 4. AI label (Nigar)
    from src.services.ai_service import AIService
    ai_svc = AIService(settings)
    processed = await ai_svc.process(new_articles)

    # 5. Save to cache
    for p in processed:
        cache.set(p.content_hash, p.labeled.summary)

    # 6. Build digest (Ləman)
    from src.core.digest_builder import DigestBuilder
    digest_path = DigestBuilder().create_markdown(processed, user)

    logger.info("pipeline_done digest=%s", digest_path)
    return digest_path