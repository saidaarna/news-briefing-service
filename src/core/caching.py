import logging

logger = logging.getLogger(__name__)

class ContentCache:
    def __init__(self):
        self._cache = {}

    def get(self, content_hash: str) -> str:
        if not content_hash:
            return None
        summary = self._cache.get(content_hash)
        if summary:
            logger.info(f"Cache hit for hash: {content_hash}")
        return summary

    def set(self, content_hash: str, summary: str):
        if content_hash and summary:
            logger.info(f"Caching summary for hash: {content_hash}")
            self._cache[content_hash] = summary