"""
Tests for the /stash endpoint
"""

import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_stash_requires_auth(client: AsyncClient):
    """Verify that stash endpoint requires API key."""
    response = await client.post(
        "/stash",
        json={"data": {"test": "data"}, "ttl": 60}
    )

    assert response.status_code == 401
    assert "Missing API key" in response.json()["detail"]

@pytest.mark.anyio
async def test_stash_creates_memory(client: AsyncClient, free_user_headers):
    """Verify that stash creates a retrievable memory"""

    # Create a stash
    response = await client.post(
        "/stash",
        headers=free_user_headers,
        json={"data": {"hello": "world"}, "ttl": 60}
    )

    assert response.status_code == 200
    data = response.json()
    assert "memory_id" in data
    assert data["ttl"] == 60

@pytest.mark.anyio
async def test_stash_enforces_ttl_limit(client: AsyncClient, free_user_headers):
    """Verify that free tier TTL is capped at 1 hour."""
    response = await client.post(
        "/stash",
        headers=free_user_headers,
        json={"data": {"test": "data"}, "ttl": 86400}  # Request 24 hours
    )

    assert response.status_code == 200
    data = response.json()
    # Should be capped at 3600 (1 hour) for free tier
    assert data["ttl"] == 3600

@pytest.mark.anyio
async def test_recall_returns_data(client: AsyncClient, free_user_headers):
    """Verify that recall returns the stored data."""
    
    # Create a stash
    stash_response = await client.post(
        "/stash",
        headers=free_user_headers,
        json={"data": {"secret": "message"}, "ttl": 60}
    )
    memory_id = stash_response.json()["memory_id"]

    # Recall it
    recall_response = await client.get(
        f"/recall/{memory_id}",
        headers=free_user_headers,
    )

    assert recall_response.status_code == 200
    data = recall_response.json()
    assert data["data"] == {"secret": "message"}

@pytest.mark.anyio
async def test_wall_isolation(client: AsyncClient, free_user_headers, pro_user_headers):
    """
    The Wall Test: Verify User A cannot acces User B's data.
    """

    # User A creates a stash
    stash_response = await client.post(
        "/stash",
        headers=free_user_headers,
        json={"data": {"private": "data"}, "ttl": 60}
    )
    memory_id = stash_response.json()["memory_id"]
    
    # User B tries to recall it
    recall_response = await client.get(
        f"/recall/{memory_id}",
        headers=pro_user_headers,  # Different user!
    )
    
    # Should NOT find it
    assert recall_response.status_code == 404

@pytest.mark.anyio
async def test_recall_nonexistent_memory(client: AsyncClient, free_user_headers):
    """Verify that recalling a nonexistent memory returns 404."""
    response = await client.get(
        "/recall/nonexistent123",
        headers=free_user_headers,
    )
    
    assert response.status_code == 404

@pytest.mark.anyio
async def test_update_data(client, free_user_headers):
    """Test updating stash data."""
    # Create a stash first
    response = await client.post(
        "/stash",
        json={"data": {"version": 1}, "ttl": 300},
        headers=free_user_headers,
    )
    memory_id = response.json()["memory_id"]
    
    # Update the data
    response = await client.patch(
        f"/update/{memory_id}",
        json={"data": {"version": 2}},
        headers=free_user_headers,
    )
    
    assert response.status_code == 200
    
    # Verify the update
    response = await client.get(f"/recall/{memory_id}", headers=free_user_headers)
    assert response.json()["data"]["version"] == 2


@pytest.mark.anyio
async def test_update_extend_ttl(client, free_user_headers):
    """Test extending TTL."""
    # Create a stash
    response = await client.post(
        "/stash",
        json={"data": {"test": "data"}, "ttl": 60},
        headers=free_user_headers,
    )
    memory_id = response.json()["memory_id"]
    original_ttl = response.json()["ttl"]
    
    # Extend TTL
    response = await client.patch(
        f"/update/{memory_id}",
        json={"extra_time": 120},
        headers=free_user_headers,
    )
    
    assert response.status_code == 200
    assert response.json()["ttl_remaining"] > original_ttl


@pytest.mark.anyio
async def test_update_nonexistent(client, free_user_headers):
    """Test updating non-existent memory."""
    response = await client.patch(
        "/update/nonexistent123",
        json={"data": {"test": "data"}},
        headers=free_user_headers,
    )
    
    assert response.status_code == 404
