import pytest
from unittest.mock import AsyncMock
from src.storage.repository import PostgresUserRepository


@pytest.mark.asyncio
async def test_postgres_user_repository_initialize():
    mock_conn = AsyncMock()
    repo = PostgresUserRepository(db_connection=mock_conn)
    await repo.initialize_db()
    assert mock_conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_postgres_user_repository_success():
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "preferred_topics": ["AI"],
        "excluded_sources": ["FakeNews"]
    }

    repo = PostgresUserRepository(db_connection=mock_conn)
    profile = await repo.get_user_profile("test_user")

    assert profile.username == "test_user"
    assert "AI" in profile.preferred_topics
    assert "FakeNews" in profile.excluded_sources


@pytest.mark.asyncio
async def test_postgres_user_repository_not_found():
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    repo = PostgresUserRepository(db_connection=mock_conn)
    profile = await repo.get_user_profile("unknown_user")
    assert profile.username == "unknown_user"
    assert len(profile.preferred_topics) == 0