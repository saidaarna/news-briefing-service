"""
Full pipeline: fetch → dedup → AI label → digest.

Usage:
    from src.concurrency.pipeline import run_pipeline
    digest_path = await run_pipeline(user_profile, fetch_svc)
"""
import asyncio
import logging

from ai import content_hash as compute_content_hash

from src.models import UserProfile, ProcessedArticle
from src.config import settings
from src.services.fetch_service import FetchService
from src.core.dedup import deduplicate
from src.services.ai_service import AIService
from src.core.caching import ContentCache
from src.core.digest_builder import DigestBuilder

logger = logging.getLogger(__name__)


async def run_pipeline(
    user: UserProfile,
    fetch_svc: FetchService | None = None,
) -> str:
    """Run the full news-briefing pipeline for *user*.

    Steps:
        1. Fetch articles from all configured sources concurrently.
        2. Two-stage deduplication (URL + hash, then Jaccard similarity).
        3. Skip articles already in the file-based label cache.
        4. Call AI labeling service for new articles (with retry + semaphore).
        5. Persist labeled results to the cache.
        6. Build and write a Markdown digest file.

    Returns:
        Path of the written digest file (e.g. ``digests/2026-05-20-khagani.md``).
    """
    logger.info("pipeline_start user=%s", user.username)

    # ── 1. Fetch ───────────────────────────────────────────────────────────────
    if fetch_svc is None:
        fetch_svc = FetchService(settings)

    raw_results = await fetch_svc.fetch_all()
    raw_articles = FetchService.collect_articles(raw_results)
    logger.info("fetch total=%d sources=%d", len(raw_articles), len(raw_results))

    # ── 2. Dedup ───────────────────────────────────────────────────────────────
    unique = deduplicate(raw_articles)
    logger.info("dedup before=%d after=%d", len(raw_articles), len(unique))

    # ── 3. Cache filter — skip articles we have already labeled ────────────────
    cache = ContentCache()
    new_articles = [
        a for a in unique if not cache.get(compute_content_hash(a.content))
    ]
    logger.info("cache_filter new=%d cached=%d", len(new_articles), len(unique) - len(new_articles))

    # ── 4. AI label ────────────────────────────────────────────────────────────
    ai_svc = AIService()
    label_results = await asyncio.gather(
        *[ai_svc.label(a) for a in new_articles],
        return_exceptions=True,
    )

    # ── 5. Build ProcessedArticle list and update cache ────────────────────────
    processed: list[ProcessedArticle] = []
    for article, result in zip(new_articles, label_results):
        if isinstance(result, Exception):
            logger.warning("ai_label_failed url=%s error=%s", article.url, result)
            continue
        content_hash_val = compute_content_hash(article.content)
        pa = ProcessedArticle(
            article=article,
            labeled=result,
            content_hash=content_hash_val,
        )
        cache.set(pa.content_hash, pa.labeled.summary)
        processed.append(pa)

    logger.info("ai_labeled processed=%d failed=%d", len(processed), len(new_articles) - len(processed))

    # ── 6. Build digest ────────────────────────────────────────────────────────
    digest_path = DigestBuilder().create_markdown(processed, user)
    logger.info("pipeline_done digest=%s", digest_path)
    return digest_path