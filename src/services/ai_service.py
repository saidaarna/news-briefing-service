import asyncio
import hashlib
import logging
from pathlib import Path

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai import Article, LabeledSummary, summarize_and_label
from ai.providers.base import ProviderError

# ── Temporary settings shim ───────────────────────────────────────────────────
# TODO: Replace these two lines with "from config import settings"
#       once Nəzrin's config.py is merged into main.
from types import SimpleNamespace
settings = SimpleNamespace(
    llm_concurrency=5,
    llm_max_retries=4,
    llm_retry_backoff_base=1.0,
    llm_timeout_seconds=30,
    cache_dir=".cache/newsbrief",
)
# ─────────────────────────────────────────────────────────────────────────────

log = logging.getLogger(__name__)


class AIService:
    """Wraps ai.summarize_and_label with:
    - File-based cache  (same article body → skips the AI call entirely)
    - Semaphore         (max llm_concurrency parallel AI calls at once)
    - Retry + backoff   (handles 429 rate-limit errors automatically)
    - Per-call timeout  (raises TimeoutError if one call hangs)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        llm_semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self._sem = llm_semaphore or asyncio.Semaphore(settings.llm_concurrency)
        # Cache lives at  .cache/newsbrief/labeled/<sha256>.json
        self._cache_dir = (cache_dir or Path(settings.cache_dir)) / "labeled"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    async def label(self, article: Article) -> LabeledSummary:
        """Summarize and topic-label one article.

        Flow:
          1. Check cache first — cache hit costs nothing (no semaphore slot used)
          2. Acquire semaphore slot (blocks if llm_concurrency calls already running)
          3. Call AI with retry logic
          4. Save result to cache
          5. Return result

        Raises:
            ProviderError   if all retries are exhausted
            TimeoutError    if a single attempt exceeds llm_timeout_seconds
        """
        cached = self._cache_get(article)
        if cached is not None:
            log.debug("ai_cache_hit url=%s", article.url)
            return cached

        async with self._sem:
            result = await self._call_with_retry(article)
            self._cache_put(article, result)
            return result

    async def _call_with_retry(self, article: Article) -> LabeledSummary:
        """Calls summarize_and_label with exponential backoff retry.

        Retry schedule (with default settings):
          attempt 1 → fails → wait 1s
          attempt 2 → fails → wait 2s
          attempt 3 → fails → wait 4s
          attempt 4 → fails → raises ProviderError (gives up)
        """
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(
                multiplier=settings.llm_retry_backoff_base, min=1, max=30
            ),
            retry=retry_if_exception_type(ProviderError),
            reraise=True,
        ):
            with attempt:
                log.info(
                    "ai_call url=%s attempt=%d content_len=%d",
                    article.url,
                    attempt.retry_state.attempt_number,
                    len(article.content),
                )
                # summarize_and_label is SYNCHRONOUS (blocking HTTP under the hood).
                # asyncio.to_thread() runs it in a background thread so it does
                # not freeze the async event loop while other articles are fetched.
                # asyncio.wait_for() enforces the hard per-attempt timeout.
                result = await asyncio.wait_for(
                    asyncio.to_thread(summarize_and_label, article),
                    timeout=settings.llm_timeout_seconds,
                )
                log.info(
                    "ai_done url=%s topic=%s sentiment=%s",
                    article.url,
                    result.topic,
                    result.sentiment,
                )
                return result
        raise RuntimeError("unreachable")  # keeps mypy happy

    # ── Cache helpers ──────────────────────────────────────────────────────────

    def _cache_key(self, article: Article) -> str:
        """SHA-256 of the article body.
        Keyed on CONTENT not URL — so two outlets publishing the same
        press release verbatim share one cache entry.
        """
        return hashlib.sha256(article.content.encode("utf-8")).hexdigest()

    def _cache_get(self, article: Article) -> LabeledSummary | None:
        """Load a cached LabeledSummary. Returns None if not found."""
        path = self._cache_dir / f"{self._cache_key(article)}.json"
        if not path.exists():
            return None
        try:
            return LabeledSummary.model_validate_json(path.read_text("utf-8"))
        except Exception:
            # Corrupt JSON — delete and let the AI re-run.
            # Never crash the whole pipeline over one bad cache file.
            log.warning("ai_cache_corrupt path=%s — dropping", path)
            path.unlink(missing_ok=True)
            return None

    def _cache_put(self, article: Article, result: LabeledSummary) -> None:
        """Save a LabeledSummary to disk as JSON."""
        path = self._cache_dir / f"{self._cache_key(article)}.json"
        path.write_text(result.model_dump_json(), encoding="utf-8")