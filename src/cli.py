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
        asyncio.run(_run_daily(args.user))

async def _run_daily(username: str) -> None:
    from src.concurrency.pipeline import run_pipeline
    from src.storage.repository import PostgresUserRepository
    import asyncpg
    
    # 1. Connect to DB and fetch the user profile
    try:
        conn = await asyncpg.connect(settings.database_url)
        repo = PostgresUserRepository(conn)
        
        # Ensures table exists and seeds 'khagani'
        await repo.initialize_db()
        
        user = await repo.get_user_profile(username)
        await conn.close()
    except Exception as e:
        logging.getLogger(__name__).error(
            "Database connection failed: %s — ensure PostgreSQL is running.", e
        )
        return

    # 2. Run pipeline
    fetch_svc = FetchService(settings)
    digest_path = await run_pipeline(user, fetch_svc)
    print(f"Digest written: {digest_path}")

if __name__ == "__main__":
    main()