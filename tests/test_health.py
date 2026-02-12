"""Tests for the health endpoint."""

import pytest


@pytest.mark.anyio
async def test_health_returns_status(client):
    """Health endpoint should return healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "mode" in data


@pytest.mark.anyio
async def test_health_checks_services(client):
    """Health endpoint should report Redis and DB connection status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    checks = data["checks"]
    assert checks["redis"] == "connected"
    assert checks["user_db"] == "connected"
