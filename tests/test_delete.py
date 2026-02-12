"""
Tests for the DELETE /stash/{memory_id} endpoint.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_delete_nonexistent_memory(client: AsyncClient, free_user_headers):
    """Verify that deleting a nonexistent memory returns 404."""
    response = await client.delete(
        "/stash/nonexistent123",
        headers=free_user_headers,
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.anyio
async def test_delete_other_users_memory(client: AsyncClient, free_user_headers, pro_user_headers):
    """Verify that a user cannot delete another user's stash."""
    # Free user creates a stash
    response = await client.post(
        "/stash",
        headers=free_user_headers,
        json={"data": {"private": "data"}, "ttl": 300},
    )
    memory_id = response.json()["memory_id"]

    # Pro user tries to delete it
    response = await client.delete(
        f"/stash/{memory_id}",
        headers=pro_user_headers,
    )

    assert response.status_code == 404

    # Verify original user can still recall it
    response = await client.get(
        f"/recall/{memory_id}",
        headers=free_user_headers,
    )
    assert response.status_code == 200
