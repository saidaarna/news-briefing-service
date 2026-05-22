import json
import logging
from abc import ABC, abstractmethod
from typing import Any
from src.models import UserProfile

logger = logging.getLogger(__name__)


class BaseUserRepository(ABC):
    """Abstract base class defining the contract for user profile storage operations."""

    @abstractmethod
    async def get_user_profile(self, username: str) -> UserProfile:
        """Fetch the user profile associated with the given username."""
        pass


class PostgresUserRepository(BaseUserRepository):
    """PostgreSQL implementation of the user repository using asyncpg connection."""

    def __init__(self, db_connection: Any):
        """Initialize the repository with an active database connection."""
        self.db_connection = db_connection

    async def initialize_db(self) -> None:
        """
        Creates the users table if it does not exist and inserts default seed data
        for testing and verification purposes.
        """
        try:
            create_table_query = """
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(100) PRIMARY KEY,
                preferred_topics JSONB NOT NULL DEFAULT '[]',
                excluded_sources JSONB NOT NULL DEFAULT '[]'
            );
            """
            await self.db_connection.execute(create_table_query)

            # Seed all team users from data/user_profile.json
            seed_query = """
            INSERT INTO users (username, preferred_topics, excluded_sources)
            VALUES
                ('saida',  '["Tech", "Science"]',          '[]'),
                ('laman',  '["Business", "Politics"]',     '["tabloid_news"]'),
                ('nazrin', '["Tech", "Business"]',         '["clickbait.com"]'),
                ('nigar',  '["Science", "Politics"]',      '["low_quality_source"]'),
                ('khagani','["Tech", "Science"]',          '["FakeNews.com"]')
            ON CONFLICT (username) DO NOTHING;
            """
            await self.db_connection.execute(seed_query)
            logger.info("Database schema and seed data initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize user database: {str(e)}")
            raise e

    async def get_user_profile(self, username: str) -> UserProfile:
        """
        Retrieves a user profile from the database by username.
        Returns an empty profile if the user does not exist.
        """
        try:
            query = "SELECT preferred_topics, excluded_sources FROM users WHERE username = $1"
            row = await self.db_connection.fetchrow(query, username)

            if not row:
                logger.warning(f"User '{username}' not found in database. Returning fallback profile.")
                return UserProfile(username=username, preferred_topics=[], excluded_sources=[])

            topics = row['preferred_topics']
            sources = row['excluded_sources']

            return UserProfile(
                username=username,
                preferred_topics=json.loads(topics) if isinstance(topics, str) else topics,
                excluded_sources=json.loads(sources) if isinstance(sources, str) else sources
            )
        except Exception as e:
            logger.error(f"Database error fetching user profile for '{username}': {str(e)}")
            raise e