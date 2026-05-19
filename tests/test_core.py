import pytest
from unittest.mock import patch, mock_open
from src.models import UserProfile, Article
from src.core.caching import ContentCache
from src.core.digest_builder import DigestBuilder


def test_content_cache_operations():
    cache = ContentCache()
    assert cache.get("non_existent_hash") is None

    cache.set("hash123", "Summary text")
    assert cache.get("hash123") == "Summary text"
    assert cache.get("") is None


def test_digest_builder_filtering():
    builder = DigestBuilder()
    profile = UserProfile(username="laman", preferred_topics=[], excluded_sources=["BadSource"])
    articles = [
        Article(title="Good News", url="http://ok.com", content="Summary 1", source_name="GoodSource"),
        Article(title="Bad News", url="http://bad.com", content="Summary 2", source_name="BadSource")
    ]

    with patch("os.makedirs"), patch("builtins.open", mock_open()):
        filename = builder.create_markdown(articles, profile)
        assert "laman.md" in filename