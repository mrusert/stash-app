"""
Pytest configuration and fixtures.

Uses a temporary PostgreSQL db for testing.
"""

import pytest
import asyncio
import os
from httpx import AsyncClient, ASGITransport
import fakeredis.aioredis

# Import the FastAPI app
from app.main import app
from app.services.redis_service import redis_service
from app.services.user_db import user_db

# Use a test database URL - can be overridden by environment variable
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/stash_test"
)

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def anyio_backend():
    """Use asyncio for async tests."""
    return "asyncio"

@pytest.fixture
async def client():
    """
    Async HTTP client for testing.
    
    Sets up:
    - Fakeredis for stash data (fast, isolated)
    - Real PostgreSQL for auth (test database)
    """

    # Use fakeredis for stash data
    redis_service._client = fakeredis.aioredis.FakeRedis(
        encoding="utf-8",
        decode_responses=True,
    )

    # Connect to test PostgreSQL database
    original_db_url = user_db._settings.database_url
    user_db._settings.database_url = TEST_DATABASE_URL
    await user_db.connect()

    # Clean up any existing test data
    async with user_db._pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE id LIKE 'test_%'")

    # Create test users (create_user returns the API key)
    free_key = await user_db.create_user("test_free", "free")
    pro_key = await user_db.create_user("test_pro", "pro")

    # Store keys for fixtures to access
    app.state.test_free_key = free_key
    app.state.test_pro_key = pro_key

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
    
    # Cleanup
    async with user_db._pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE id LIKE 'test_%'")
    
    await user_db.disconnect()
    user_db._settings.database_url = original_db_url

@pytest.fixture
async def free_user_headers(client):
    """Headers for free tier user"""
    return {"X-API-KEY": app.state.test_free_key}

@pytest.fixture
async def pro_user_headers(client):
    """Headers for pro tier user"""
    return {"X-API-KEY": app.state.test_pro_key}