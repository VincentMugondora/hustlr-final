"""
Basic API surface tests for root and health endpoints.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_check(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "Hustlr API"


@pytest.mark.asyncio
async def test_root(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "message" in body
    assert body["docs"] == "/docs"
    assert body["health"] == "/health"
