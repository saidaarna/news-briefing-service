import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ContentCache:
    """In-memory content-hash cache. Prevents re-labeling articles seen this run."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def get(self, content_hash: str) -> Optional[str]:
        """Return the cached summary for *content_hash*, or None if not cached."""
        if not content_hash:
            return None
        summary = self._cache.get(content_hash)
        if summary:
            logger.info("cache_hit hash=%s", content_hash)
        return summary

    def set(self, content_hash: str, summary: str) -> None:
        """Store *summary* under *content_hash* for this run."""
        if content_hash and summary:
            logger.info("cache_set hash=%s", content_hash)
            self._cache[content_hash] = summary