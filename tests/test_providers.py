"""
Tests for provider registration, profile management, and provider search endpoints.
"""

from __future__ import annotations

from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_provider_registration_success(async_client, override_current_user, make_user, fake_db):
    user = make_user("customer-1", "customer", "+15552220001")
    override_current_user(user)

    payload = {
        "user_id": user.id,
        "service_type": "plumber",
        "location": "downtown",
        "description": "Emergency plumbing",
        "contact_email": "plumber@example.com",
        "license_number": "LIC-100",
        "insurance_info": "Insured",
    }

    response = await async_client.post("/api/v1/providers/register", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["service_type"] == "plumber"
    assert body["is_verified"] is False
    assert body["verification_status"] == "pending"

    stored = await fake_db.service_providers.find_one({"user_id": user.id})
    assert stored is not None


@pytest.mark.asyncio
async def test_provider_registration_high_risk_requires_license_and_insurance(
    async_client, override_current_user, make_user
):
    override_current_user(make_user("customer-2", "customer"))

    response = await async_client.post(
        "/api/v1/providers/register",
        json={
            "user_id": "customer-2",
            "service_type": "electrician",
            "location": "midtown",
        },
    )

    assert response.status_code == 400
    assert "license" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_provider_registration_forbidden_for_admin(async_client, override_current_user, make_user):
    override_current_user(make_user("admin-1", "admin"))

    response = await async_client.post(
        "/api/v1/providers/register",
        json={
            "user_id": "admin-1",
            "service_type": "cleaner",
            "location": "midtown",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_and_update_my_provider_profile(async_client, override_current_user, make_user, fake_db):
    user = make_user("provider-user-10", "provider")
    override_current_user(user)

    await fake_db.service_providers.insert_one(
        {
            "_id": "provider-10",
            "user_id": user.id,
            "service_type": "carpenter",
            "location": "queens",
            "description": "Woodwork",
            "hourly_rate": 70.0,
            "is_verified": False,
            "verification_status": "pending",
            "rating": 0.0,
            "total_ratings": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    get_response = await async_client.get("/api/v1/providers/me")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == "provider-10"

    update_response = await async_client.put(
        "/api/v1/providers/me",
        json={
            "user_id": "malicious-user-id",
            "service_type": "carpenter",
            "location": "brooklyn",
            "description": "Updated",
            "contact_email": "new@example.com",
        },
    )

    assert update_response.status_code == 200
    updated = await fake_db.service_providers.find_one({"_id": "provider-10"})
    assert updated["location"] == "brooklyn"
    assert updated["user_id"] == user.id


@pytest.mark.asyncio
async def test_provider_search_returns_only_verified(async_client, override_current_user, make_user, fake_db):
    override_current_user(make_user("customer-3", "customer"))

    await fake_db.service_providers.insert_one(
        {
            "_id": "provider-verified",
            "user_id": "u1",
            "service_type": "electrician",
            "location": "midtown",
            "is_verified": True,
            "verification_status": "verified",
            "rating": 4.0,
            "total_ratings": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )
    await fake_db.service_providers.insert_one(
        {
            "_id": "provider-unverified",
            "user_id": "u2",
            "service_type": "electrician",
            "location": "midtown",
            "is_verified": False,
            "verification_status": "pending",
            "rating": 0.0,
            "total_ratings": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    response = await async_client.get(
        "/api/v1/providers/search",
        params={"service_type": "electric", "location": "town"},
    )

    assert response.status_code == 200
    results = response.json()
    ids = {item["id"] for item in results}
    assert "provider-verified" in ids
    assert "provider-unverified" not in ids


@pytest.mark.asyncio
async def test_provider_endpoints_require_auth(async_client):
    response = await async_client.post(
        "/api/v1/providers/register",
        json={"user_id": "u", "service_type": "cleaner", "location": "uptown"},
    )
    assert response.status_code in (401, 403)
