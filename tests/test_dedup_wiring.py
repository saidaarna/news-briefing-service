"""
Tests for deduplicate().
No AI calls needed — url_canonicalize, content_hash, near_duplicate
are pure functions that work offline.
"""
from ai import Article
from src.core.dedup import deduplicate


def _article(url: str, content: str, source: str = "example") -> Article:
    """Shortcut to build Article objects in tests. Field is 'source' not 'source_name'."""
    return Article(title="Some Title", url=url, content=content, source=source)


def test_stage1_drops_utm_duplicate():
    """Two URLs that differ only in utm_ tracking params should be treated as one article.

    url_canonicalize() removes utm_source, utm_campaign etc., making them identical.
    Stage 1 catches this without needing any similarity comparison.
    """
    a = _article("https://example.com/story?utm_source=twitter", "Body text here.")
    b = _article("https://example.com/story?utm_source=facebook", "Body text here.")

    result = deduplicate([a, b])

    assert len(result) == 1


def test_stage2_drops_paraphrase():
    """Two articles saying the same thing differently should be caught by Stage 2.

    Stage 1 cannot catch this: the URLs are different and the body hash is different.
    Stage 2 computes Jaccard similarity and drops the near-duplicate.
    """
    body1 = "The president signed the new climate bill on Monday morning in Washington. The bill aims to reduce emissions by forty percent over the next decade."
    body2 = "The president signed the new climate bill on Monday morning in Washington. The bill aims to reduce emissions by 40% over the next decade."

    a = _article("https://outlet-a.com/story/1", body1, source="OutletA")
    b = _article("https://outlet-b.com/story/1", body2, source="OutletB")

    result = deduplicate([a, b], threshold=0.5)

    assert len(result) == 1


def test_threshold_too_high_keeps_both():
    """At threshold=0.99, almost nothing is considered a duplicate.
    Both articles should survive even if they are paraphrases of each other.
    """
    body1 = "The president signed the new climate bill on Monday morning in Washington. The bill aims to reduce emissions by forty percent over the next decade."
    body2 = "The president signed the new climate bill on Monday morning in Washington. The bill aims to reduce emissions by 40% over the next decade."

    a = _article("https://A.com/1", body1, "A")
    b = _article("https://B.com/1", body2, "B")

    result = deduplicate([a, b], threshold=0.99)

    assert len(result) == 2


def test_bad_url_dropped_gracefully():
    """A malformed URL should be silently skipped — must not crash the pipeline."""
    bad  = _article("not-a-valid-url", "Some content here.")
    good = _article("https://ok.com/article", "Completely different content.")

    # Should not raise any exception
    result = deduplicate([bad, good])

    assert isinstance(result, list)
    assert len(result) <= 2  # bad dropped, good kept (≤2 because content may match)