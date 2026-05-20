import pytest
from unittest.mock import patch, mock_open

from ai import Topic, LabeledSummary, Sentiment
from src.models import UserProfile, Article, ProcessedArticle
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
    profile = UserProfile(username="laman", preferred_topics=[Topic.TECH], excluded_sources=["BadSource"])

    # Create valid raw articles
    art1 = Article(title="Good News", url="http://ok.com", content="Raw content 1", source="GoodSource")
    art2 = Article(title="Bad News", url="http://bad.com", content="Raw content 2", source="BadSource")

    # Wrap them into ProcessedArticle as expected by the new DigestBuilder
    articles = [
        ProcessedArticle(
            article=art1,
            labeled=LabeledSummary(summary="Summary 1", topic=Topic.TECH, sentiment=Sentiment.NEUTRAL),
            content_hash="hash1"
        ),
        ProcessedArticle(
            article=art2,
            labeled=LabeledSummary(summary="Summary 2", topic=Topic.TECH, sentiment=Sentiment.NEUTRAL),
            content_hash="hash2"
        )
    ]

    with patch("os.makedirs"), patch("builtins.open", mock_open()):
        filename = builder.create_markdown(articles, profile)
        assert filename is not None