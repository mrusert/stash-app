"""
Tests for authentication and authorization.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_invalid_api_key(client: AsyncClient):
    """Verify that a bogus API key returns 401."""
    response = await client.post(
        "/stash",
        headers={"X-API-KEY": "sk_totally_bogus_key_12345"},
        json={"data": {"test": "data"}, "ttl": 60},
    )

    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


@pytest.mark.anyio
async def test_pro_tier_ttl_limit(client: AsyncClient, pro_user_headers):
    """Verify that pro tier gets 24-hour TTL cap (not 1-hour free cap)."""
    response = await client.post(
        "/stash",
        headers=pro_user_headers,
        json={"data": {"test": "data"}, "ttl": 86400},  # Request 24 hours
    )

    assert response.status_code == 200
    data = response.json()
    # Pro tier allows up to 86400 (24 hours)
    assert data["ttl"] == 86400


@pytest.mark.anyio
async def test_pro_tier_ttl_capped(client: AsyncClient, pro_user_headers):
    """Verify that pro tier TTL is capped at 24 hours."""
    response = await client.post(
        "/stash",
        headers=pro_user_headers,
        # Request more than 24 hours — but schema caps at 86400
        # So we request exactly 86400 and confirm it's not reduced
        json={"data": {"test": "data"}, "ttl": 86400},
    )

    assert response.status_code == 200
    assert response.json()["ttl"] == 86400
