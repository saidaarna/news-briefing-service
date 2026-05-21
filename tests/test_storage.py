import pytest
from unittest.mock import AsyncMock

from ai import Topic
from src.storage.repository import PostgresUserRepository


@pytest.mark.asyncio
async def test_postgres_user_repository_initialize():
    """Ensures that the database initialization executes both table creation and seeding queries."""
    mock_conn = AsyncMock()
    repo = PostgresUserRepository(db_connection=mock_conn)
    await repo.initialize_db()
    assert mock_conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_postgres_user_repository_success():
    """Validates successful mapping of database rows to a complete UserProfile model with Enums."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "username": "test_user",
        "preferred_topics": ["Tech"],
        "excluded_sources": ["FakeNews"],
        "max_items_per_topic": 5
    }

    repo = PostgresUserRepository(db_connection=mock_conn)
    profile = await repo.get_user_profile("test_user")

    assert profile.username == "test_user"
    assert Topic.TECH in profile.preferred_topics
    assert "FakeNews" in profile.excluded_sources
    # New assertion: Verify that max_items_per_topic is correctly mapped from DB
    assert profile.max_items_per_topic == 5


@pytest.mark.asyncio
async def test_postgres_user_repository_not_found():
    """Verifies that a fallback empty profile is returned when a user does not exist in the database."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    repo = PostgresUserRepository(db_connection=mock_conn)
    profile = await repo.get_user_profile("unknown_user")
    assert profile.username == "unknown_user"
    assert len(profile.preferred_topics) == 0


@pytest.mark.asyncio
async def test_postgres_user_repository_failure():
    """Ensures that database connection exceptions are properly captured and raised up the stack."""
    mock_conn = AsyncMock()
    # Simulate a database crash or connection loss
    mock_conn.fetchrow.side_effect = Exception("Database connection lost")

    repo = PostgresUserRepository(db_connection=mock_conn)
    with pytest.raises(Exception) as exc_info:
        await repo.get_user_profile("test_user")

    assert "Database connection lost" in str(exc_info.value)