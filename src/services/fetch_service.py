"""
Async fetch service — concurrent ingestion of RSS feeds and HTML pages.

This module is Saida's core responsibility.  It:
  1. Reads the list of sources (RSS + HTML).
  2. Fetches all of them concurrently with a Semaphore-bounded asyncio.gather.
  3. Parses each response into a list of ai.schemas.Article objects.
  4. Returns a FetchResult per source — failures are logged and wrapped,
     never propagated (graceful degradation).

Usage:
    from src.services.fetch_service import FetchService
    from src.config import settings

    svc = FetchService(settings)
    results = await svc.fetch_all()          # List[FetchResult]
    articles = svc.collect_articles(results) # List[Article], skips failures
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import feedparser
from bs4 import BeautifulSoup

from ai.schemas import Article
from src.config import Settings
from src.models import FetchResult, Source

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML scrape helpers
# ---------------------------------------------------------------------------

_HTML_TITLE_SELECTORS = ["h1", "title"]
_HTML_BODY_SELECTORS = ["article", "main", "div.article-body", "div.content", "body"]


def _parse_html_to_article(html: str, url: str, source_name: str) -> Article:
    """Extract title + body text from raw HTML using BeautifulSoup.

    Strategy (best-effort):
      - Title:   first <h1>, fallback to <title> tag.
      - Content: first semantic container found in _HTML_BODY_SELECTORS.
      - Date:    <meta property="article:published_time"> if present.

    Raises ValueError if neither title nor content can be extracted.
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- Title ---
    title: str = ""
    for sel in _HTML_TITLE_SELECTORS:
        tag = soup.find(sel)
        if tag and tag.get_text(strip=True):
            title = tag.get_text(strip=True)
            break
    if not title:
        raise ValueError(f"Cannot extract a title from HTML at {url!r}")

    # --- Content ---
    content: str = ""
    for sel in _HTML_BODY_SELECTORS:
        tag = soup.select_one(sel)
        if tag:
            content = tag.get_text(separator=" ", strip=True)
            if len(content) > 50:  # skip tiny fragments
                break
    if not content or len(content) < 50:
        raise ValueError(f"Cannot extract meaningful body text from HTML at {url!r} (must be at least 50 characters)")

    # --- Published date (optional) ---
    published_at: Optional[datetime] = None
    meta = soup.find("meta", {"property": "article:published_time"})
    if meta and meta.get("content"):
        try:
            published_at = datetime.fromisoformat(str(meta["content"]).rstrip("Z"))
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return Article(
        title=title,
        url=url,
        source=source_name,
        content=content[:4000],  # guard against oversized payloads
        published_at=published_at,
    )


def _parse_rss_entries(feed_text: str, source_name: str) -> list[Article]:
    """Parse an RSS/Atom feed string into Article objects.

    feedparser does most of the heavy lifting.  We skip entries that lack a
    title or URL.  Non-fatal errors are logged, not raised.
    """
    feed = feedparser.parse(feed_text)
    articles: list[Article] = []

    if feed.bozo and not feed.entries:
        # bozo=True means feedparser found a parse problem.  If there are still
        # entries, feedparser handled it gracefully; if not, the feed is broken.
        logger.warning(
            "feedparser flagged a malformed feed for source %r: %s",
            source_name,
            feed.bozo_exception,
        )
        return articles

    for entry in feed.entries:
        try:
            url: str = entry.get("link", "").strip()
            title: str = entry.get("title", "").strip()
            if not url or not title:
                continue  # skip incomplete entries silently

            # Content: prefer "content" field, fall back to "summary"
            raw_content: str = ""
            if entry.get("content"):
                raw_content = entry["content"][0].get("value", "")
            if not raw_content:
                raw_content = entry.get("summary", "")

            # Strip HTML from content if present
            if raw_content:
                raw_content = BeautifulSoup(raw_content, "html.parser").get_text(
                    separator=" ", strip=True
                )

            published_at: Optional[datetime] = None
            if entry.get("published_parsed"):
                try:
                    published_at = datetime(
                        *entry.published_parsed[:6]
                    ).replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            articles.append(
                Article(
                    title=title,
                    url=url,
                    source=source_name,
                    content=raw_content[:4000],
                    published_at=published_at,
                )
            )
        except Exception as exc:
            logger.warning(
                "Skipping malformed RSS entry from %r: %s", source_name, exc
            )

    return articles


# ---------------------------------------------------------------------------
# Source loader helpers
# ---------------------------------------------------------------------------


def load_rss_sources(feeds_file: str | Path) -> list[Source]:
    """Read the sources file and return a list of Source objects.

    Supports either a single URL (defaults to kind='rss') or the format:
    `url | kind | name` (e.g. `https://oxu.az | html | Oxu.az`)

    Lines starting with '#' and blank lines are ignored.
    """
    path = Path(feeds_file)
    if not path.exists():
        logger.warning("Sources file not found: %s", path)
        return []

    sources: list[Source] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            url = parts[0]
            kind = parts[1] if len(parts) > 1 else "rss"
            name = parts[2] if len(parts) > 2 else (urlparse(url).hostname or url)
            sources.append(Source(name=name, url=url, kind=kind))
        else:
            hostname = urlparse(line).hostname or line
            sources.append(Source(name=hostname, url=line, kind="rss"))

    logger.debug("Loaded %d sources from %s", len(sources), path)
    return sources


# ---------------------------------------------------------------------------
# Main fetch service
# ---------------------------------------------------------------------------


class FetchService:
    """Concurrent fetcher for RSS feeds and HTML news pages.

    All network I/O is bounded by a semaphore (``settings.max_parallel_fetches``)
    to avoid hammering publishers or triggering rate limits.

    Parameters
    ----------
    settings:
        The application settings.  The fetch timeout and semaphore size are
        read from here.

    Example
    -------
    ::

        svc = FetchService(settings)
        results = await svc.fetch_all()
        articles = FetchService.collect_articles(results)
    """

    def __init__(self, cfg: Settings) -> None:
        self._cfg = cfg
        self._semaphore = asyncio.Semaphore(cfg.max_parallel_fetches)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_all(
        self, extra_sources: list[Source] | None = None
    ) -> list[FetchResult]:
        """Fetch all configured sources concurrently.

        Reads RSS sources from the file specified in settings plus any
        ``extra_sources`` passed in (useful for tests or dynamic configs).

        Returns one ``FetchResult`` per source.  Failures are captured inside
        the result rather than raised — graceful degradation.
        """
        sources: list[Source] = load_rss_sources(self._cfg.rss_feeds_file)
        if extra_sources:
            sources.extend(extra_sources)

        if not sources:
            logger.warning("No sources configured — returning empty fetch results.")
            return []

        logger.info("Fetching %d sources (max_parallel=%d) …", len(sources), self._cfg.max_parallel_fetches)

        timeout = aiohttp.ClientTimeout(total=self._cfg.fetch_timeout_seconds)
        connector = aiohttp.TCPConnector(limit=self._cfg.max_parallel_fetches)

        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        ) as session:
            tasks = [
                self._fetch_one(session, source)
                for source in sources
            ]
            results: list[FetchResult] = await asyncio.gather(*tasks)

        ok_count = sum(1 for r in results if r.ok)
        total_articles = sum(len(r.articles) for r in results)
        logger.info(
            "Fetch complete: %d/%d sources OK, %d articles collected.",
            ok_count, len(results), total_articles,
        )
        return results

    async def fetch_html_source(
        self, session: aiohttp.ClientSession, source: Source
    ) -> FetchResult:
        """Fetch a single HTML page and parse it into articles.

        Exposed as a public method so tests can call it directly.
        """
        return await self._fetch_html(session, source)

    @staticmethod
    def collect_articles(results: list[FetchResult]) -> list[Article]:
        """Flatten all successful FetchResults into a single article list.

        Sources that returned errors are silently skipped here; their errors
        were already logged during fetching.
        """
        articles: list[Article] = []
        for result in results:
            if result.ok:
                articles.extend(result.articles)
            else:
                logger.debug(
                    "Skipping failed source %r: %s", result.source.name, result.error
                )
        return articles

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_one(
        self, session: aiohttp.ClientSession, source: Source
    ) -> FetchResult:
        """Dispatch to the correct fetcher based on source.kind, with semaphore."""
        async with self._semaphore:
            if source.kind == "rss":
                return await self._fetch_rss(session, source)
            elif source.kind == "html":
                return await self._fetch_html(session, source)
            else:
                # Should never happen because Source validates kind.
                return FetchResult(
                    source=source,
                    error=f"Unknown source kind: {source.kind!r}",
                )

    async def _fetch_rss(
        self, session: aiohttp.ClientSession, source: Source
    ) -> FetchResult:
        """Fetch and parse a single RSS/Atom feed."""
        logger.debug("Fetching RSS: %s", source.url)
        try:
            async with session.get(source.url) as response:
                response.raise_for_status()
                text = await response.text(encoding="utf-8", errors="replace")

            articles = _parse_rss_entries(text, source.name)
            logger.info("RSS %r → %d articles", source.name, len(articles))
            return FetchResult(source=source, articles=articles)

        except aiohttp.ClientResponseError as exc:
            msg = f"HTTP {exc.status} from {source.url}"
            logger.error("Failed RSS fetch for %r: %s", source.name, msg)
            return FetchResult(source=source, error=msg)

        except asyncio.TimeoutError:
            msg = f"Timeout after {self._cfg.fetch_timeout_seconds}s for {source.url}"
            logger.error("Timeout fetching RSS %r: %s", source.name, msg)
            return FetchResult(source=source, error=msg)

        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            logger.error("Unexpected error fetching RSS %r: %s", source.name, msg)
            return FetchResult(source=source, error=msg)

    async def _fetch_html(
        self, session: aiohttp.ClientSession, source: Source
    ) -> FetchResult:
        """Fetch and parse a single HTML news page."""
        logger.debug("Fetching HTML: %s", source.url)
        try:
            async with session.get(source.url) as response:
                response.raise_for_status()
                html = await response.text(encoding="utf-8", errors="replace")

            article = _parse_html_to_article(html, source.url, source.name)
            logger.info("HTML %r → 1 article: %r", source.name, article.title)
            return FetchResult(source=source, articles=[article])

        except aiohttp.ClientResponseError as exc:
            msg = f"HTTP {exc.status} from {source.url}"
            logger.error("Failed HTML fetch for %r: %s", source.name, msg)
            return FetchResult(source=source, error=msg)

        except asyncio.TimeoutError:
            msg = f"Timeout after {self._cfg.fetch_timeout_seconds}s for {source.url}"
            logger.error("Timeout fetching HTML %r: %s", source.name, msg)
            return FetchResult(source=source, error=msg)

        except ValueError as exc:
            # Parsing error (no title, no content, etc.)
            msg = f"Parse error: {exc}"
            logger.error("HTML parse failed for %r: %s", source.name, msg)
            return FetchResult(source=source, error=msg)

        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            logger.error("Unexpected error fetching HTML %r: %s", source.name, msg)
            return FetchResult(source=source, error=msg)
