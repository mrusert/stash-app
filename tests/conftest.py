"""
Pytest configuration and fixtures.

Fixtures are reusable test setup/teardown functions.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

# Import the FastAPI app
from app.main import app
from app.services.redis_service import redis_service
from app.services.user_db import user_db

@pytest.fixture
def anyio_backend():
    """Use asyncio for async tests."""
    return "asyncio"

@pytest.fixture
async def client():
    """
    Async HTTP client for testing the API.

    Sets up both fakeredis for stash data and SQLite for auth.
    """

    # Use fakeredis for stash data
    import fakeredis.aioredis
    redis_service._client = fakeredis.aioredis.FakeRedis(
        encoding="utf-8",
        decode_responses=True,
    )

    # Use in-memory SQLite for user auth
    import aiosqlite
    user_db._db_path = ":memory"
    await user_db.connect()

    # Create test users
    await user_db.create_user("test_free", "free")
    await user_db.create_user("test_pro", "pro")

    # Create test API keys (We'll store these for fixtures)
    free_key = await user_db.create_api_key("test_free", "test_free_key")
    pro_key = await user_db.create_api_key("test_pro", "test_pro_key")

    # Store keys for fixtures to access
    app.state.test_free_key = free_key
    app.state.test_pro_key = pro_key

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
    
    # Cleanup
    await user_db.disconnect()

@pytest.fixture
async def free_user_headers(client):
    """Headers for free tier user"""
    return {"X-API-KEY": app.state.test_free_key}

@pytest.fixture
async def pro_user_headers(client):
    """Headers for pro tier user"""
    return {"X-API-KEY": app.state.test_pro_key}