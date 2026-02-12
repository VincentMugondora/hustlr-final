"""
Tests for authentication endpoints and token security.
"""

from __future__ import annotations

import pytest

from backend.auth import verify_password


@pytest.mark.asyncio
async def test_register_success(async_client, fake_db):
    payload = {
        "phone_number": "+15551110001",
        "name": "Alice",
        "password": "strongpass1",
        "role": "customer",
    }

    response = await async_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    created = await fake_db.users.find_one({"phone_number": payload["phone_number"]})
    assert created is not None
    assert created["name"] == "Alice"
    assert created["role"] == "customer"
    assert "hashed_password" in created
    assert verify_password(payload["password"], created["hashed_password"])


@pytest.mark.asyncio
async def test_register_duplicate_phone_rejected(async_client, fake_db):
    await fake_db.users.insert_one(
        {
            "_id": "user-dup",
            "phone_number": "+15551110002",
            "name": "Existing",
            "role": "customer",
            "hashed_password": "hashed",
        }
    )

    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "phone_number": "+15551110002",
            "name": "Duplicate",
            "password": "strongpass2",
            "role": "customer",
        },
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success(async_client, fake_db):
    registration = {
        "phone_number": "+15551110003",
        "name": "Bob",
        "password": "strongpass3",
        "role": "customer",
    }
    await async_client.post("/api/v1/auth/register", json=registration)

    response = await async_client.post(
        "/api/v1/auth/login",
        data={"username": registration["phone_number"], "password": registration["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(async_client):
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "phone_number": "+15551110004",
            "name": "Carol",
            "password": "strongpass4",
            "role": "customer",
        },
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        data={"username": "+15551110004", "password": "wrongpass"},
    )

    assert response.status_code == 401
    assert "incorrect phone number or password" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_token_blocked_on_protected_endpoint(async_client):
    response = await async_client.get(
        "/api/v1/bookings/",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_auth_header_blocked(async_client):
    response = await async_client.get("/api/v1/bookings/")
    assert response.status_code in (401, 403)
