import json
import logging
from abc import ABC, abstractmethod
from src.models import UserProfile

logger = logging.getLogger(__name__)


class BaseUserRepository(ABC):
    @abstractmethod
    async def get_user_profile(self, username: str) -> UserProfile:
        pass


class PostgresUserRepository(BaseUserRepository):
    def __init__(self, db_connection):
        self.db_connection = db_connection

    async def initialize_db(self):
        try:
            create_table_query = """
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(100) PRIMARY KEY,
                preferred_topics JSONB NOT NULL DEFAULT '[]',
                excluded_sources JSONB NOT NULL DEFAULT '[]'
            );
            """
            await self.db_connection.execute(create_table_query)

            seed_query = """
            INSERT INTO users (username, preferred_topics, excluded_sources)
            VALUES ('khagani', '["AI", "Tech"]', '["FakeNews.com"]')
            ON CONFLICT (username) DO NOTHING;
            """
            await self.db_connection.execute(seed_query)
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise e

    async def get_user_profile(self, username: str) -> UserProfile:
        try:
            query = "SELECT preferred_topics, excluded_sources FROM users WHERE username = $1"
            row = await self.db_connection.fetchrow(query, username)

            if not row:
                logger.warning(f"User {username} not found in database.")
                return UserProfile(username=username, preferred_topics=[], excluded_sources=[])

            topics = row['preferred_topics']
            sources = row['excluded_sources']

            return UserProfile(
                username=username,
                preferred_topics=json.loads(topics) if isinstance(topics, str) else topics,
                excluded_sources=json.loads(sources) if isinstance(sources, str) else sources
            )
        except Exception as e:
            logger.error(f"Database error fetching user profile for {username}: {str(e)}")
            raise e