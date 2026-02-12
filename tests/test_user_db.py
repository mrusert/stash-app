"""
Tests for UserDB service operations.
"""

import pytest
from app.services.user_db import user_db


@pytest.mark.anyio
async def test_get_user(client):
    """Verify get_user returns correct user data."""
    result = await user_db.get_user("test_free")

    assert result is not None
    assert result["id"] == "test_free"
    assert result["tier"] == "free"
    assert "created_at" in result
    assert "key_created_at" in result


@pytest.mark.anyio
async def test_get_user_nonexistent(client):
    """Verify get_user returns None for unknown user."""
    result = await user_db.get_user("user_does_not_exist")

    assert result is None


@pytest.mark.anyio
async def test_duplicate_user_creation(client):
    """Verify creating a duplicate user returns None."""
    # test_free already exists from the fixture
    result = await user_db.create_user("test_free", "free")

    assert result is None


@pytest.mark.anyio
async def test_regenerate_api_key(client):
    """Verify regenerating an API key returns a new key that works."""
    from app.main import app

    # Get the old key
    old_key = app.state.test_free_key

    # Regenerate
    new_key = await user_db.regenerate_api_key("test_free")

    assert new_key is not None
    assert new_key != old_key
    assert new_key.startswith("sk_")

    # New key should work for auth
    user = await user_db.get_user_by_api_key(new_key)
    assert user is not None
    assert user["id"] == "test_free"

    # Old key should no longer work
    old_user = await user_db.get_user_by_api_key(old_key)
    assert old_user is None

    # Restore the old key so other tests aren't affected
    # (regenerate again and update app state)
    restored_key = await user_db.regenerate_api_key("test_free")
    app.state.test_free_key = restored_key


@pytest.mark.anyio
async def test_regenerate_api_key_nonexistent(client):
    """Verify regenerating key for unknown user returns None."""
    result = await user_db.regenerate_api_key("user_does_not_exist")

    assert result is None
