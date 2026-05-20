"""
Tests for apply_user_preferences().
Uses real DigestItem and Article objects — no mocking needed.
"""
from ai import Article, DigestItem, LabeledSummary, Topic, Sentiment
from src.core.filter import apply_user_preferences, User


def _make_item(topic: Topic, source: str = "some_source") -> DigestItem:
    """Build a DigestItem. Notice DigestItem wraps Article + LabeledSummary."""
    article = Article(
        title="Some Title",
        url=f"https://{source}.com/article",
        content="Article body text.",
        source=source,           # field is 'source', not 'source_name'
    )
    labeled = LabeledSummary(
        summary="A summary.",
        topic=topic,
        sentiment=Sentiment.NEUTRAL,
    )
    return DigestItem(article=article, labeled=labeled)


def test_excluded_sources_are_dropped():
    """Items from excluded sources must not appear in the output."""
    user = User(
        username="testuser",
        preferred_topics=[],
        excluded_sources=["badnews"],
        max_items_per_topic=10,
    )
    items = [
        _make_item(Topic.TECH, source="goodnews"),
        _make_item(Topic.TECH, source="badnews"),   # should be dropped
    ]

    result = apply_user_preferences(items, user)

    assert len(result) == 1
    assert result[0].article.source == "goodnews"


def test_preferred_topics_filter():
    """When preferred_topics is set, only matching topics survive."""
    user = User(
        username="testuser",
        preferred_topics=["tech"],   # lowercase — filter is case-insensitive
        excluded_sources=[],
        max_items_per_topic=10,
    )
    items = [
        _make_item(Topic.TECH),       # keep
        _make_item(Topic.POLITICS),   # drop
        _make_item(Topic.TECH),       # keep
    ]

    result = apply_user_preferences(items, user)

    assert len(result) == 2
    assert all(item.labeled.topic == Topic.TECH for item in result)


def test_max_items_per_topic_cap():
    """Should never return more than max_items_per_topic for one topic."""
    user = User(
        username="testuser",
        preferred_topics=[],
        excluded_sources=[],
        max_items_per_topic=2,
    )
    items = [_make_item(Topic.TECH) for _ in range(5)]  # 5 tech items

    result = apply_user_preferences(items, user)

    assert len(result) == 2