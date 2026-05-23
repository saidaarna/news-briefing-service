import asyncio
import argparse
import json
import logging
from pathlib import Path

from src.config import configure_logging, settings
from src.services.fetch_service import FetchService


def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser(prog="newsbrief")
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("run-daily", help="Run the full pipeline for a user")
    daily.add_argument("--user", required=True, help="Username to generate digest for")
    daily.add_argument(
        "--no-db",
        action="store_true",
        help="Load user profile from data/user_profile.json (no PostgreSQL needed)",
    )

    args = parser.parse_args()

    if args.command == "run-daily":
        asyncio.run(_run_daily(args.user, no_db=getattr(args, "no_db", False)))


async def _run_daily(username: str, no_db: bool = False) -> None:
    from src.concurrency.pipeline import run_pipeline
    from src.models import UserProfile
    from ai.schemas import Topic

    log = logging.getLogger(__name__)
    user: UserProfile | None = None

    # ── 1. Try PostgreSQL (skip if --no-db) ──────────────────────────────────
    if not no_db:
        try:
            import asyncpg
            from src.storage.repository import PostgresUserRepository

            conn = await asyncpg.connect(settings.database_url)
            repo = PostgresUserRepository(conn)
            await repo.initialize_db()
            user = await repo.get_user_profile(username)
            await conn.close()
        except Exception as e:
            log.warning("DB unavailable (%s) — falling back to data/user_profile.json", e)

    # ── 2. Fallback: load from data/user_profile.json ─────────────────────────
    if user is None:
        profile_path = Path("data/user_profile.json")
        if not profile_path.exists():
            log.error("data/user_profile.json not found and DB is unavailable.")
            return
        profiles = json.loads(profile_path.read_text(encoding="utf-8"))
        match = next((p for p in profiles if p["username"] == username), None)
        if match is None:
            log.warning("User '%s' not in JSON — using empty profile.", username)
            match = {"username": username, "preferred_topics": [], "excluded_sources": []}
        user = UserProfile(
            username=match["username"],
            preferred_topics=[Topic(t) for t in match.get("preferred_topics", [])],
            excluded_sources=match.get("excluded_sources", []),
            max_items_per_topic=match.get("max_items_per_topic", 5),
        )
        log.info(
            "Loaded '%s' from JSON: topics=%s",
            username, [t.value for t in user.preferred_topics],
        )

    # ── 3. Run pipeline ───────────────────────────────────────────────────────
    fetch_svc = FetchService(settings)
    digest_path = await run_pipeline(user, fetch_svc)
    print(f"Digest written: {digest_path}")


if __name__ == "__main__":
    main()