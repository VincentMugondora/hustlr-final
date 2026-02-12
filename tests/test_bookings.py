"""
Tests for booking creation, cancellation/reschedule, rating, and booking security.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_search_providers_for_booking(async_client, override_current_user, make_user, seeded_provider):
    override_current_user(make_user("customer-1", "customer"))

    response = await async_client.post(
        "/api/v1/bookings/search_providers",
        json={
            "service_type": "electric",
            "location": "town",
            "date": "2099-01-01",
            "time": "10:00",
            "max_results": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == seeded_provider["_id"]


@pytest.mark.asyncio
async def test_create_booking_success(async_client, override_current_user, make_user, seeded_provider, fake_db):
    customer = make_user("customer-42", "customer")
    override_current_user(customer)

    future = datetime.utcnow() + timedelta(days=10)
    booking_date = future.strftime("%Y-%m-%d")
    booking_time = future.strftime("%H:%M")

    response = await async_client.post(
        "/api/v1/bookings/",
        json={
            "customer_id": "ignored-by-endpoint",
            "provider_id": seeded_provider["_id"],
            "service_type": "electrician",
            "date": booking_date,
            "time": booking_time,
            "duration_hours": 2.0,
            "notes": "Need outlet replacement",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["customer_id"] == customer.id
    assert body["provider_id"] == seeded_provider["_id"]
    assert body["status"] == "pending"

    stored = await fake_db.bookings.find_one({"_id": body["id"]})
    assert stored is not None


@pytest.mark.asyncio
async def test_create_booking_conflict_returns_409(async_client, override_current_user, make_user, seeded_provider, fake_db):
    customer = make_user("customer-43", "customer")
    override_current_user(customer)

    future = datetime.utcnow() + timedelta(days=7)
    booking_date = future.strftime("%Y-%m-%d")
    booking_time = future.strftime("%H:%M")

    await fake_db.bookings.insert_one(
        {
            "_id": "existing-booking",
            "customer_id": "other-customer",
            "provider_id": seeded_provider["_id"],
            "service_type": "electrician",
            "date": booking_date,
            "time": booking_time,
            "duration_hours": 1.0,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    response = await async_client.post(
        "/api/v1/bookings/",
        json={
            "customer_id": "ignored",
            "provider_id": seeded_provider["_id"],
            "service_type": "electrician",
            "date": booking_date,
            "time": booking_time,
            "duration_hours": 1.0,
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_booking_creation_forbidden_for_provider_role(async_client, override_current_user, make_user, seeded_provider):
    override_current_user(make_user("provider-user-22", "provider"))

    future = datetime.utcnow() + timedelta(days=3)
    response = await async_client.post(
        "/api/v1/bookings/",
        json={
            "customer_id": "ignored",
            "provider_id": seeded_provider["_id"],
            "service_type": "electrician",
            "date": future.strftime("%Y-%m-%d"),
            "time": future.strftime("%H:%M"),
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cancel_booking_success(async_client, override_current_user, make_user, fake_db, seeded_provider):
    customer = make_user("customer-50", "customer")
    override_current_user(customer)

    await fake_db.bookings.insert_one(
        {
            "_id": "booking-to-cancel",
            "customer_id": customer.id,
            "provider_id": seeded_provider["_id"],
            "service_type": "electrician",
            "date": "2099-02-01",
            "time": "10:00",
            "duration_hours": 1.0,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    response = await async_client.put(
        "/api/v1/bookings/booking-to-cancel/cancel",
        json={"action": "cancel", "reason": "No longer needed"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_reschedule_booking_success(async_client, override_current_user, make_user, fake_db, seeded_provider):
    customer = make_user("customer-51", "customer")
    override_current_user(customer)

    await fake_db.bookings.insert_one(
        {
            "_id": "booking-to-reschedule",
            "customer_id": customer.id,
            "provider_id": seeded_provider["_id"],
            "service_type": "electrician",
            "date": "2099-03-01",
            "time": "10:00",
            "duration_hours": 1.0,
            "status": "confirmed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    response = await async_client.put(
        "/api/v1/bookings/booking-to-reschedule/cancel",
        json={
            "action": "reschedule",
            "new_date": "2099-03-02",
            "new_time": "11:30",
            "reason": "Schedule changed",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["date"] == "2099-03-02"
    assert body["time"] == "11:30"


@pytest.mark.asyncio
async def test_cancel_booking_requires_owner(async_client, override_current_user, make_user, fake_db, seeded_provider):
    await fake_db.bookings.insert_one(
        {
            "_id": "booking-ownership",
            "customer_id": "customer-real-owner",
            "provider_id": seeded_provider["_id"],
            "service_type": "electrician",
            "date": "2099-04-01",
            "time": "10:00",
            "duration_hours": 1.0,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    override_current_user(make_user("customer-wrong", "customer"))
    response = await async_client.put(
        "/api/v1/bookings/booking-ownership/cancel",
        json={"action": "cancel", "reason": "Attempt unauthorized cancel"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rate_completed_booking_success(
    async_client, override_current_user, make_user, fake_db, seeded_completed_booking, seeded_provider
):
    customer = make_user(seeded_completed_booking["customer_id"], "customer")
    override_current_user(customer)

    response = await async_client.post(
        f"/api/v1/bookings/{seeded_completed_booking['_id']}/rate",
        json={
            "booking_id": seeded_completed_booking["_id"],
            "customer_id": seeded_completed_booking["customer_id"],
            "provider_id": seeded_provider["_id"],
            "rating": 5,
            "comment": "Excellent service",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rating"] == 5

    stored_rating = await fake_db.ratings.find_one({"booking_id": seeded_completed_booking["_id"]})
    assert stored_rating is not None

    updated_provider = await fake_db.service_providers.find_one({"_id": seeded_provider["_id"]})
    assert updated_provider["total_ratings"] == 3
    assert updated_provider["rating"] == pytest.approx(4.67, rel=1e-2)


@pytest.mark.asyncio
async def test_rating_rejects_duplicate(async_client, override_current_user, make_user, fake_db, seeded_completed_booking, seeded_provider):
    customer = make_user(seeded_completed_booking["customer_id"], "customer")
    override_current_user(customer)

    first = {
        "booking_id": seeded_completed_booking["_id"],
        "customer_id": seeded_completed_booking["customer_id"],
        "provider_id": seeded_provider["_id"],
        "rating": 4,
    }

    await async_client.post(f"/api/v1/bookings/{seeded_completed_booking['_id']}/rate", json=first)
    second_response = await async_client.post(
        f"/api/v1/bookings/{seeded_completed_booking['_id']}/rate",
        json=first,
    )

    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_rating_access_control_and_validation(async_client, override_current_user, make_user, seeded_completed_booking, seeded_provider):
    override_current_user(make_user("different-customer", "customer"))

    unauthorized = await async_client.post(
        f"/api/v1/bookings/{seeded_completed_booking['_id']}/rate",
        json={
            "booking_id": seeded_completed_booking["_id"],
            "customer_id": "different-customer",
            "provider_id": seeded_provider["_id"],
            "rating": 5,
        },
    )
    assert unauthorized.status_code == 403

    override_current_user(make_user(seeded_completed_booking["customer_id"], "customer"))
    invalid_value = await async_client.post(
        f"/api/v1/bookings/{seeded_completed_booking['_id']}/rate",
        json={
            "booking_id": seeded_completed_booking["_id"],
            "customer_id": seeded_completed_booking["customer_id"],
            "provider_id": seeded_provider["_id"],
            "rating": 10,
        },
    )
    assert invalid_value.status_code == 422


@pytest.mark.asyncio
async def test_security_input_validation_for_cancel_and_booking(async_client, override_current_user, make_user, seeded_provider):
    override_current_user(make_user("customer-90", "customer"))

    bad_date = await async_client.post(
        "/api/v1/bookings/",
        json={
            "customer_id": "x",
            "provider_id": seeded_provider["_id"],
            "service_type": "electrician",
            "date": "not-a-date",
            "time": "10:00",
        },
    )
    assert bad_date.status_code == 400

    bad_cancel_action = await async_client.put(
        "/api/v1/bookings/nonexistent/cancel",
        json={"action": "delete", "reason": "invalid action"},
    )
    assert bad_cancel_action.status_code == 422
