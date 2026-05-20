import asyncio
import logging
from src.models import UserProfile, ProcessedArticle
from src.config import settings
from src.services.fetch_service import FetchService
# These come from Nigar — stub with None until Day 6
# from src.core.dedup import run_dedup
# from src.services.ai_service import AIService

logger = logging.getLogger(__name__)

async def run_pipeline(
    user: UserProfile,
    fetch_svc: FetchService,
    # dedup_fn,       # Nigar
    # ai_svc,         # Nigar
    # cache,          # Ləman — ContentCache instance
    # digest_builder, # Ləman — DigestBuilder instance
) -> str:
    logger.info("pipeline_start user=%s", user.username)

    # Step 1: Fetch
    raw_results = await fetch_svc.fetch_all()
    raw_articles = FetchService.collect_articles(raw_results)
    logger.info("fetched total=%d", len(raw_articles))

    # Step 2: Dedup (Nigar)
    # unique = run_dedup(raw_articles)

    # Step 3: Cache filter (Ləman)
    # new_articles = [a for a in unique if not cache.get(a.content_hash)]

    # Step 4: AI label (Nigar)
    # processed: list[ProcessedArticle] = await ai_svc.process(new_articles)

    # Step 5: Save to cache (Ləman)
    # for p in processed:
    #     cache.set(p.content_hash, p.labeled.summary)

    # Step 6: Build digest (Ləman)
    # digest_path = digest_builder.create_markdown(processed, user)

    # return digest_path
    raise NotImplementedError("wire teammates' modules on Day 6")