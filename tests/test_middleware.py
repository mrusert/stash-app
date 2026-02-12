"""
Tests for middleware (payload size limits).
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_oversized_payload_returns_413(client: AsyncClient, free_user_headers):
    """Verify that payloads exceeding 1MB are rejected with 413."""
    response = await client.post(
        "/stash",
        headers={**free_user_headers, "content-length": "2000000"},
        json={"data": {"test": "data"}, "ttl": 60},
    )

    assert response.status_code == 413
    data = response.json()
    assert data["error"] == "Payload Too Large"
    assert "limit_bytes" in data
