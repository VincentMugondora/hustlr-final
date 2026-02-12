"""
Unit tests that assert async MongoDB interactions in endpoint handlers.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.models import BookingCreate, RatingCreate, User, UserCreate
from backend.routes import auth as auth_routes
from backend.routes import bookings as booking_routes


@pytest.mark.asyncio
async def test_auth_register_awaits_async_db_calls(monkeypatch):
    users_collection = SimpleNamespace(
        find_one=AsyncMock(return_value=None),
        insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id="user-async-1")),
    )
    mock_db = SimpleNamespace(users=users_collection)
    monkeypatch.setattr(auth_routes, "db", mock_db)
    monkeypatch.setattr(auth_routes, "get_password_hash", lambda password: f"fake-hash::{password}")

    user = UserCreate(
        phone_number="+15556660001",
        name="Unit Test",
        password="unitpass1",
        role="customer",
    )

    result = await auth_routes.register(user)

    assert result.token_type == "bearer"
    users_collection.find_one.assert_awaited_once()
    users_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_booking_awaits_insert_one(monkeypatch):
    providers_collection = SimpleNamespace(
        find_one=AsyncMock(return_value={"_id": "provider-async-1", "is_verified": True})
    )
    bookings_collection = SimpleNamespace(
        find_one=AsyncMock(return_value=None),
        insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id="booking-async-1")),
    )

    mock_db = SimpleNamespace(
        service_providers=providers_collection,
        bookings=bookings_collection,
    )
    monkeypatch.setattr(booking_routes, "db", mock_db)

    future = datetime.utcnow() + timedelta(days=14)
    booking = BookingCreate(
        customer_id="ignored",
        provider_id="provider-async-1",
        service_type="electrician",
        date=future.strftime("%Y-%m-%d"),
        time=future.strftime("%H:%M"),
        duration_hours=1.0,
    )
    current_user = User(_id="customer-async-1", phone_number="+15557770001", name="Customer", role="customer")

    result = await booking_routes.create_booking(booking=booking, current_user=current_user)

    assert result.id == "booking-async-1"
    providers_collection.find_one.assert_awaited_once()
    bookings_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_rate_booking_awaits_rating_insert_and_provider_update(monkeypatch):
    booking_doc = {
        "_id": "booking-rate-1",
        "customer_id": "customer-rate-1",
        "provider_id": "provider-rate-1",
        "status": "completed",
    }
    ratings_collection = SimpleNamespace(
        find_one=AsyncMock(return_value=None),
        insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id="rating-1")),
    )
    providers_collection = SimpleNamespace(
        find_one=AsyncMock(return_value={"_id": "provider-rate-1", "rating": 4.0, "total_ratings": 1}),
        update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)),
    )
    bookings_collection = SimpleNamespace(find_one=AsyncMock(return_value=booking_doc))

    mock_db = SimpleNamespace(
        bookings=bookings_collection,
        ratings=ratings_collection,
        service_providers=providers_collection,
    )
    monkeypatch.setattr(booking_routes, "db", mock_db)

    rating_data = RatingCreate(
        booking_id="booking-rate-1",
        customer_id="customer-rate-1",
        provider_id="provider-rate-1",
        rating=5,
        comment="Great",
    )
    current_user = User(_id="customer-rate-1", phone_number="+15558880001", name="Customer", role="customer")

    result = await booking_routes.rate_booking(
        booking_id="booking-rate-1",
        rating_data=rating_data,
        current_user=current_user,
    )

    assert result.id == "rating-1"
    ratings_collection.insert_one.assert_awaited_once()
    providers_collection.update_one.assert_awaited_once()
