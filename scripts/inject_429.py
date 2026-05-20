"""
Simulates 3 rate-limit errors then a success. Save output for the report.

HOW TO RUN (from your project root folder):
    python scripts/inject_429.py 2>&1 | tee artifacts/failure_llm_429.log

What each part means:
    2>&1              → also capture log lines (they go to stderr by default)
    | tee <file>      → show output on screen AND save to file at the same time
"""
import asyncio
import logging
from unittest.mock import patch

from ai import Article, LabeledSummary, Topic, Sentiment
from ai.providers.base import ProviderError
from src.services.ai_service import AIService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

call_count = {"n": 0}


def flaky_summarize(article: Article) -> LabeledSummary:
    """Fake AI: fails 3 times with 429, then succeeds on attempt 4."""
    call_count["n"] += 1
    if call_count["n"] < 4:
        raise ProviderError(f"429 Rate Limit — simulated attempt {call_count['n']}")
    return LabeledSummary(
        summary="Successfully summarized after retries.",
        topic=Topic.TECH,
        sentiment=Sentiment.NEUTRAL,
    )


async def main() -> None:
    article = Article(
        title="Test Article",
        url="https://example.com/test",
        content="x" * 500,
        source="example",
    )
    with patch("src.services.ai_service.summarize_and_label", side_effect=flaky_summarize):
        svc = AIService()
        result = await svc.label(article)

    print(f"\nFinal result: {result.summary}")
    print(f"Total provider calls made: {call_count['n']}")
    print("Retry with backoff is working correctly.")


if __name__ == "__main__":
    asyncio.run(main())