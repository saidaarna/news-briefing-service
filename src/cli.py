import asyncio
import argparse
import logging
import os

from src.config import configure_logging, settings
from src.services.fetch_service import FetchService

def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser(prog="newsbrief")
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("run-daily", help="Run the full pipeline for a user")
    daily.add_argument("--user", required=True, help="Username to generate digest for")

    args = parser.parse_args()

    if args.command == "run-daily":
        _run_daily(args.user)

def _run_daily(username: str) -> None:
    # Import here so tests can monkeypatch before import
    from src.concurrency.pipeline import run_pipeline

    # When Ləman's DB is ready, replace this with real repo call
    from src.models import UserProfile, Topic
    user = UserProfile(
        username=username,
        preferred_topics=[Topic.Tech, Topic.Science],
        excluded_sources=[],
    )

    fetch_svc = FetchService(settings)
    digest_path = asyncio.run(run_pipeline(user, fetch_svc))
    print(f"Digest written: {digest_path}")

if __name__ == "__main__":
    main()