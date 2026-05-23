"""
Tests for the fetch service — 100% offline (no live network).

All HTTP calls are mocked using pytest-httpx or aiohttp-style mocking.
No real DNS/TCP connection is ever made.

Coverage targets:
  - Happy path: RSS feed returns valid XML → articles parsed correctly.
  - Happy path: HTML page returns valid HTML → article parsed correctly.
  - Error path: HTTP 500 → FetchResult.ok is False, error is logged.
  - Error path: Timeout → FetchResult captured, pipeline continues.
  - Error path: Malformed RSS → empty article list, no crash.
  - Error path: HTML with no <h1> or <title> → parse error captured.
  - Concurrency: fetch_all with multiple sources calls gather correctly.
  - collect_articles: skips failed results, flattens successes.
  - load_rss_sources: reads file, skips comments and blank lines.
  - Source validation: rejects invalid 'kind' values.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.schemas import Article
from src.config import Settings
from src.models import FetchResult, Source
from src.services.fetch_service import (
    FetchService,
    _parse_html_to_article,
    _parse_rss_entries,
    load_rss_sources,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RSS_XML_VALID = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Article One</title>
      <link>https://example.com/article-1</link>
      <description>Body of article one.</description>
      <pubDate>Mon, 19 May 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/article-2</link>
      <description>Body of article two.</description>
    </item>
  </channel>
</rss>"""

RSS_XML_MALFORMED = "NOT XML AT ALL <garbage"

HTML_VALID = """<!DOCTYPE html>
<html>
<head>
  <title>Test Article</title>
  <meta property="article:published_time" content="2026-05-19T10:00:00Z">
</head>
<body>
  <article>
    <h1>Test Article Heading</h1>
    <p>This is a meaningful body of text that is longer than fifty characters.</p>
  </article>
</body>
</html>"""

HTML_NO_TITLE = """<html><body><p>No heading here.</p></body></html>"""
HTML_TINY_BODY = """<html><head><title>Tiny</title></head><body><p>Hi.</p></body></html>"""


def _make_settings(**overrides) -> Settings:
    """Create Settings with dummy API key so model_validator passes."""
    defaults = {
        "llm_provider": "anthropic",
        "llm_model": "claude-sonnet-4-6",
        "anthropic_api_key": "sk-ant-test-key",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "openai_api_key": "sk-test-key",
        "fetch_timeout_seconds": 10,
        "max_parallel_fetches": 4,
        "rss_feeds_file": "data/rss_feeds.txt",
        "log_level": "DEBUG",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def cfg() -> Settings:
    return _make_settings()


@pytest.fixture
def rss_source() -> Source:
    return Source(name="Test Feed", url="https://example.com/feed.rss", kind="rss")


@pytest.fixture
def html_source() -> Source:
    return Source(name="Test HTML", url="https://example.com/page", kind="html")


# ---------------------------------------------------------------------------
# Unit tests: _parse_rss_entries
# ---------------------------------------------------------------------------


class TestParseRssEntries:
    def test_happy_path_parses_all_entries(self):
        articles = _parse_rss_entries(RSS_XML_VALID, "TestFeed")
        assert len(articles) == 2
        assert articles[0].title == "Article One"
        assert articles[0].url == "https://example.com/article-1"
        assert articles[0].source == "TestFeed"
        assert "Body of article one" in articles[0].content

    def test_malformed_xml_returns_empty_list(self):
        articles = _parse_rss_entries(RSS_XML_MALFORMED, "TestFeed")
        assert articles == []

    def test_entry_missing_url_is_skipped(self):
        xml = """<rss version="2.0"><channel>
          <item><title>No URL</title></item>
        </channel></rss>"""
        articles = _parse_rss_entries(xml, "TestFeed")
        assert len(articles) == 0

    def test_entry_missing_title_is_skipped(self):
        xml = """<rss version="2.0"><channel>
          <item><link>https://example.com/no-title</link></item>
        </channel></rss>"""
        articles = _parse_rss_entries(xml, "TestFeed")
        assert len(articles) == 0

    def test_html_in_description_is_stripped(self):
        xml = """<rss version="2.0"><channel>
          <item>
            <title>HTML Test</title>
            <link>https://example.com/html-test</link>
            <description><![CDATA[<p>Plain <b>text</b> content.</p>]]></description>
          </item>
        </channel></rss>"""
        articles = _parse_rss_entries(xml, "TestFeed")
        assert len(articles) == 1
        assert "<p>" not in articles[0].content
        assert "Plain" in articles[0].content


# ---------------------------------------------------------------------------
# Unit tests: _parse_html_to_article
# ---------------------------------------------------------------------------


class TestParseHtmlToArticle:
    def test_happy_path_extracts_title_and_body(self):
        article = _parse_html_to_article(HTML_VALID, "https://example.com/page", "TestSite")
        assert article.title == "Test Article Heading"
        assert "meaningful body" in article.content
        assert article.source == "TestSite"
        assert article.published_at is not None

    def test_falls_back_to_title_tag_when_no_h1(self):
        html = """<html><head><title>Page Title</title></head>
        <body><p>{"x": "y"} This is a long enough body text here and it has more than fifty characters.</p></body></html>"""
        article = _parse_html_to_article(html, "https://example.com/page", "TestSite")
        assert article.title == "Page Title"

    def test_raises_when_no_title_found(self):
        with pytest.raises(ValueError, match="title"):
            _parse_html_to_article(HTML_NO_TITLE, "https://example.com/page", "TestSite")

    def test_raises_when_content_too_short(self):
        with pytest.raises(ValueError, match="body text"):
            _parse_html_to_article(HTML_TINY_BODY, "https://example.com/page", "TestSite")

    def test_content_truncated_at_4000_chars(self):
        long_body = "x" * 5000
        html = f"<html><head><title>T</title></head><body><article><h1>T</h1><p>{long_body}</p></article></body></html>"
        article = _parse_html_to_article(html, "https://example.com", "TestSite")
        assert len(article.content) <= 4000


# ---------------------------------------------------------------------------
# Unit tests: load_rss_sources
# ---------------------------------------------------------------------------


class TestLoadRssSources:
    def test_reads_valid_file(self, tmp_path: Path):
        feeds = tmp_path / "feeds.txt"
        feeds.write_text(
            "# comment\n"
            "https://example.com/rss1\n"
            "\n"
            "https://example.com/rss2\n"
        )
        sources = load_rss_sources(feeds)
        assert len(sources) == 2
        assert all(s.kind == "rss" for s in sources)
        assert sources[0].url == "https://example.com/rss1"

    def test_returns_empty_list_for_missing_file(self):
        sources = load_rss_sources("/nonexistent/path/feeds.txt")
        assert sources == []

    def test_skips_blank_lines_and_comments(self, tmp_path: Path):
        feeds = tmp_path / "feeds.txt"
        feeds.write_text("# comment\n\nhttps://example.com/only-one\n")
        sources = load_rss_sources(feeds)
        assert len(sources) == 1


# ---------------------------------------------------------------------------
# Unit tests: Source model validation
# ---------------------------------------------------------------------------


class TestSourceModel:
    def test_valid_rss_source(self):
        s = Source(name="BBC", url="https://bbc.com/rss", kind="rss")
        assert s.kind == "rss"

    def test_valid_html_source(self):
        s = Source(name="CNN", url="https://cnn.com/article", kind="html")
        assert s.kind == "html"

    def test_invalid_kind_raises(self):
        with pytest.raises(Exception):
            Source(name="X", url="https://x.com", kind="graphql")

    def test_empty_url_raises(self):
        with pytest.raises(Exception):
            Source(name="X", url="   ", kind="rss")


# ---------------------------------------------------------------------------
# Unit tests: FetchResult model
# ---------------------------------------------------------------------------


class TestFetchResult:
    def test_ok_is_true_when_no_error(self, rss_source):
        r = FetchResult(source=rss_source, articles=[], error=None)
        assert r.ok is True

    def test_ok_is_false_when_error_set(self, rss_source):
        r = FetchResult(source=rss_source, articles=[], error="Timeout")
        assert r.ok is False

    def test_collect_articles_flattens_successes(self, rss_source, html_source):
        a1 = Article(title="A1", url="https://a.com/1", source="A", content="body one here")
        a2 = Article(title="A2", url="https://a.com/2", source="A", content="body two here")
        results = [
            FetchResult(source=rss_source, articles=[a1]),
            FetchResult(source=html_source, articles=[a2]),
        ]
        collected = FetchService.collect_articles(results)
        assert len(collected) == 2

    def test_collect_articles_skips_failures(self, rss_source, html_source):
        a1 = Article(title="A1", url="https://a.com/1", source="A", content="body one here")
        results = [
            FetchResult(source=rss_source, articles=[a1]),
            FetchResult(source=html_source, error="HTTP 500"),
        ]
        collected = FetchService.collect_articles(results)
        assert len(collected) == 1
        assert collected[0].title == "A1"


# ---------------------------------------------------------------------------
# Integration / concurrency tests: FetchService._fetch_rss / _fetch_html
# ---------------------------------------------------------------------------


class TestFetchServiceIntegration:
    """Tests that mock aiohttp at the session level — zero live network."""

    def _make_mock_response(self, text: str, status: int = 200):
        """Build a mock aiohttp response context manager."""
        mock_resp = AsyncMock()
        mock_resp.status = status
        mock_resp.text = AsyncMock(return_value=text)
        if status >= 400:
            from aiohttp import ClientResponseError
            mock_resp.raise_for_status = MagicMock(
                side_effect=ClientResponseError(None, None, status=status)
            )
        else:
            mock_resp.raise_for_status = MagicMock()

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    @pytest.mark.asyncio
    async def test_fetch_rss_happy_path(self, cfg, rss_source):
        svc = FetchService(cfg)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=self._make_mock_response(RSS_XML_VALID))

        result = await svc._fetch_rss(mock_session, rss_source)

        assert result.ok
        assert len(result.articles) == 2
        assert result.articles[0].title == "Article One"

    @pytest.mark.asyncio
    async def test_fetch_rss_http_500_captured(self, cfg, rss_source):
        svc = FetchService(cfg)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=self._make_mock_response("error", status=500))

        result = await svc._fetch_rss(mock_session, rss_source)

        assert not result.ok
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_fetch_html_happy_path(self, cfg, html_source):
        svc = FetchService(cfg)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=self._make_mock_response(HTML_VALID))

        result = await svc._fetch_html(mock_session, html_source)

        assert result.ok
        assert len(result.articles) == 1
        assert result.articles[0].title == "Test Article Heading"

    @pytest.mark.asyncio
    async def test_fetch_html_parse_error_captured(self, cfg, html_source):
        svc = FetchService(cfg)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=self._make_mock_response(HTML_NO_TITLE))

        result = await svc._fetch_html(mock_session, html_source)

        assert not result.ok
        assert "Parse error" in result.error

    @pytest.mark.asyncio
    async def test_fetch_rss_timeout_captured(self, cfg, rss_source):
        svc = FetchService(cfg)
        mock_session = MagicMock()

        async def _raise_timeout(*args, **kwargs):
            raise asyncio.TimeoutError()

        ctx = MagicMock()
        ctx.__aenter__ = _raise_timeout
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=ctx)

        result = await svc._fetch_rss(mock_session, rss_source)

        assert not result.ok
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_fetch_all_runs_concurrently(self, cfg, tmp_path):
        """asyncio.gather over multiple sources completes without blocking."""
        feeds_file = tmp_path / "feeds.txt"
        feeds_file.write_text(
            "https://example.com/feed1.rss\n"
            "https://example.com/feed2.rss\n"
        )
        cfg2 = _make_settings(rss_feeds_file=str(feeds_file))
        svc = FetchService(cfg2)

        call_count = 0

        async def _fake_fetch_one(session, source):
            nonlocal call_count
            call_count += 1
            return FetchResult(source=source, articles=[])

        svc._fetch_one = _fake_fetch_one  # type: ignore[method-assign]

        import aiohttp as _aiohttp

        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def close(self):
                pass

        with patch("src.services.fetch_service.aiohttp.ClientSession") as mock_cs:
            mock_cs.return_value = _FakeSession()
            results = await svc.fetch_all()

        assert call_count == 2
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_fetch_all_one_source_fails_others_succeed(self, cfg, tmp_path):
        """One failed source does not abort the whole gather."""
        feeds_file = tmp_path / "feeds.txt"
        feeds_file.write_text("https://example.com/good.rss\nhttps://example.com/bad.rss\n")
        cfg2 = _make_settings(rss_feeds_file=str(feeds_file))
        svc = FetchService(cfg2)

        call_index = 0

        async def _alternating_fetch(session, source):
            nonlocal call_index
            call_index += 1
            if "bad" in source.url:
                return FetchResult(source=source, error="Simulated failure")
            a = Article(title="Good", url="https://example.com/g", source="G", content="good content here")
            return FetchResult(source=source, articles=[a])

        svc._fetch_one = _alternating_fetch  # type: ignore[method-assign]

        class _FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

        with patch("src.services.fetch_service.aiohttp.ClientSession") as mock_cs:
            mock_cs.return_value = _FakeSession()
            results = await svc.fetch_all()

        articles = FetchService.collect_articles(results)
        assert len(articles) == 1
        assert articles[0].title == "Good"
