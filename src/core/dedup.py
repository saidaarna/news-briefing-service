import logging

from ai import Article, url_canonicalize, content_hash, near_duplicate

from src.config import settings

log = logging.getLogger(__name__)


def deduplicate(
    articles: list[Article], threshold: float | None = None
) -> list[Article]:
    """Remove duplicate articles in two stages.

    Stage 1 — URL + hash  (O(n), very fast):
        Strips tracking params from URLs (utm_source, utm_campaign …) and
        hashes the article body. Drops any article whose canonical URL or
        body hash we have already seen.
        Catches: same article shared via different social-media links,
                 exact copy-pastes across outlets.

    Stage 2 — Semantic similarity  (O(n²), slower but smarter):
        Uses word k-shingle Jaccard similarity (ai.near_duplicate).
        Drops an article if it is "close enough" to any article already kept.
        Catches: paraphrased re-posts, wire stories republished with minor edits.

    Args:
        articles:  raw list from the fetch stage
        threshold: Jaccard threshold 0–1. Higher = only drop near-identical
                   text. Lower = also drop loosely similar text. Default 0.7.

    Returns:
        Deduplicated list of Article objects (same objects, not copies).
    """
    threshold = (
        threshold if threshold is not None else settings.dedup_near_duplicate_threshold
    )

    # ── Stage 1: URL canonicalization + body hash ──────────────────────────────
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    stage1: list[Article] = []

    for art in articles:
        try:
            canon = url_canonicalize(art.url)
        except ValueError:
            # Malformed URL — skip silently with a warning, never crash
            log.warning("dedup_bad_url url=%r", art.url)
            continue

        h = content_hash(art.content)

        if canon in seen_urls or h in seen_hashes:
            log.debug(
                "dedup_stage1_drop url=%s reason=%s",
                art.url,
                "url" if canon in seen_urls else "hash",
            )
            continue

        seen_urls.add(canon)
        seen_hashes.add(h)
        stage1.append(art)

    log.info("dedup_stage1 in=%d out=%d", len(articles), len(stage1))

    # ── Stage 2: Semantic near-duplicate check ─────────────────────────────────
    stage2: list[Article] = []
    for art in stage1:
        # Compare against every article we have already decided to keep
        if any(
            near_duplicate(art.content, kept.content, threshold=threshold)
            for kept in stage2
        ):
            log.debug("dedup_stage2_drop url=%s", art.url)
            continue
        stage2.append(art)

    log.info(
        "dedup_stage2 in=%d out=%d threshold=%.2f",
        len(stage1),
        len(stage2),
        threshold,
    )
    return stage2