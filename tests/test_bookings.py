"""
Comprehensive tests for booking-related endpoints.
Tests booking creation, management, ratings, and cancellations.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from httpx import AsyncClient

from backend.main import app
from backend.models import User, ServiceProvider, Booking, Rating, BookingStatus
from backend.auth import create_access_token


@pytest.fixture
async def test_db():
    """Create a test database connection."""
    from motor.motor_asyncio import AsyncIOMotorClient
    import os

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    test_db_name = "hustlr_test_bookings"

    client = AsyncIOMotorClient(mongo_uri)
    db = client[test_db_name]

    yield db

    # Clean up after tests
    client.drop_database(test_db_name)
    client.close()


@pytest.fixture
async def test_customer(test_db):
    """Create a test customer."""
    user_data = {
        "phone_number": "+1111111111",
        "name": "Test Customer",
        "password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfLkIwXH7iN8K2",
        "role": "customer",
        "created_at": datetime.utcnow()
    }

    result = await test_db.users.insert_one(user_data)
    user_data["_id"] = str(result.inserted_id)
    return User(**user_data)


@pytest.fixture
async def test_service_provider(test_db):
    """Create a test service provider."""
    user_data = {
        "phone_number": "+2222222222",
        "name": "Test Provider",
        "password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfLkIwXH7iN8K2",
        "role": "provider",
        "created_at": datetime.utcnow()
    }

    result = await test_db.users.insert_one(user_data)
    user_data["_id"] = str(result.inserted_id)

    provider_data = {
        "user_id": str(result.inserted_id),
        "service_type": "plumber",
        "location": "downtown",
        "description": "Professional plumbing services",
        "hourly_rate": 50.0,
        "business_name": "Test Plumbing Co",
        "contact_phone": "+2222222222",
        "contact_email": "test@plumbing.com",
        "years_experience": 10,
        "license_number": "PL123456",
        "insurance_info": "Fully insured",
        "is_verified": True,
        "verification_status": "verified",
        "rating": 4.5,
        "total_ratings": 10,
        "availability": {"monday": "9-17", "tuesday": "9-17"},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await test_db.service_providers.insert_one(provider_data)
    provider_data["_id"] = str(result.inserted_id)
    return ServiceProvider(**provider_data)


@pytest.fixture
def customer_headers(test_customer):
    """Create authentication headers for customer."""
    token = create_access_token({"sub": str(test_customer.id), "role": test_customer.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def provider_headers(test_service_provider):
    """Create authentication headers for provider."""
    token = create_access_token({"sub": str(test_service_provider.user_id), "role": "provider"})
    return {"Authorization": f"Bearer {token}"}


class TestProviderSearch:
    """Test provider search functionality."""

    @pytest.mark.asyncio
    async def test_search_providers_basic(self, async_client, test_service_provider, customer_headers):
        """Test basic provider search."""
        search_data = {
            "service_type": "plumber",
            "location": "downtown",
            "max_results": 10
        }

        response = await async_client.post(
            "/api/v1/bookings/search_providers",
            json=search_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Check that our test provider is in results
        provider_ids = [p["id"] for p in data]
        assert str(test_service_provider.id) in provider_ids

    @pytest.mark.asyncio
    async def test_search_providers_with_date_time(self, async_client, test_service_provider, customer_headers):
        """Test provider search with date and time filtering."""
        search_data = {
            "service_type": "plumber",
            "location": "downtown",
            "date": "2026-02-15",  # A Saturday
            "time": "14:00",
            "max_results": 5
        }

        response = await async_client.post(
            "/api/v1/bookings/search_providers",
            json=search_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_search_providers_no_matches(self, async_client, customer_headers):
        """Test search with no matching providers."""
        search_data = {
            "service_type": "nonexistent_service",
            "location": "nowhere",
            "max_results": 10
        }

        response = await async_client.post(
            "/api/v1/bookings/search_providers",
            json=search_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_search_providers_unauthorized(self, async_client):
        """Test provider search without authentication."""
        search_data = {
            "service_type": "plumber",
            "location": "downtown"
        }

        response = await async_client.post(
            "/api/v1/bookings/search_providers",
            json=search_data
        )
        assert response.status_code == 401


class TestBookingCreation:
    """Test booking creation functionality."""

    @pytest.mark.asyncio
    async def test_create_booking_success(self, async_client, test_customer, test_service_provider, customer_headers, test_db):
        """Test successful booking creation."""
        booking_data = {
            "provider_id": str(test_service_provider.id),
            "service_type": "plumber",
            "date": "2026-02-20",
            "time": "14:00",
            "duration_hours": 2.0,
            "notes": "Fix kitchen sink leak"
        }

        response = await async_client.post(
            "/api/v1/bookings/",
            json=booking_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["customer_id"] == str(test_customer.id)
        assert data["provider_id"] == str(test_service_provider.id)
        assert data["status"] == "pending"
        assert data["service_type"] == booking_data["service_type"]
        assert data["date"] == booking_data["date"]
        assert data["time"] == booking_data["time"]
        assert "id" in data

        # Verify booking was created in database
        booking_in_db = await test_db.bookings.find_one({"_id": data["id"]})
        assert booking_in_db is not None
        assert booking_in_db["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_booking_unverified_provider(self, async_client, customer_headers, test_db):
        """Test booking creation with unverified provider (should fail)."""
        # Create an unverified provider
        unverified_provider_data = {
            "user_id": "test_user",
            "service_type": "electrician",
            "location": "uptown",
            "is_verified": False,
            "created_at": datetime.utcnow()
        }

        result = await test_db.service_providers.insert_one(unverified_provider_data)
        provider_id = str(result.inserted_id)

        booking_data = {
            "provider_id": provider_id,
            "service_type": "electrician",
            "date": "2026-02-20",
            "time": "10:00"
        }

        response = await async_client.post(
            "/api/v1/bookings/",
            json=booking_data,
            headers=customer_headers
        )
        assert response.status_code == 404  # Provider not found (since unverified)

    @pytest.mark.asyncio
    async def test_create_booking_past_date(self, async_client, test_service_provider, customer_headers):
        """Test booking creation with past date."""
        booking_data = {
            "provider_id": str(test_service_provider.id),
            "service_type": "plumber",
            "date": "2020-01-01",  # Past date
            "time": "10:00"
        }

        response = await async_client.post(
            "/api/v1/bookings/",
            json=booking_data,
            headers=customer_headers
        )
        assert response.status_code == 400
        assert "future" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_booking_invalid_time_format(self, async_client, test_service_provider, customer_headers):
        """Test booking creation with invalid time format."""
        booking_data = {
            "provider_id": str(test_service_provider.id),
            "service_type": "plumber",
            "date": "2026-02-20",
            "time": "25:00"  # Invalid time
        }

        response = await async_client.post(
            "/api/v1/bookings/",
            json=booking_data,
            headers=customer_headers
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_booking_provider_only(self, async_client, test_service_provider, provider_headers):
        """Test that only customers can create bookings."""
        booking_data = {
            "provider_id": str(test_service_provider.id),
            "service_type": "plumber",
            "date": "2026-02-20",
            "time": "14:00"
        }

        response = await async_client.post(
            "/api/v1/bookings/",
            json=booking_data,
            headers=provider_headers
        )
        assert response.status_code == 403
        assert "customers can create bookings" in response.json()["detail"].lower()


class TestBookingManagement:
    """Test booking status updates and retrieval."""

    @pytest.fixture
    async def test_booking(self, test_db, test_customer, test_service_provider):
        """Create a test booking."""
        booking_data = {
            "customer_id": str(test_customer.id),
            "provider_id": str(test_service_provider.id),
            "service_type": "plumber",
            "date": "2026-02-20",
            "time": "14:00",
            "duration_hours": 2.0,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await test_db.bookings.insert_one(booking_data)
        booking_data["_id"] = str(result.inserted_id)
        return Booking(**booking_data)

    @pytest.mark.asyncio
    async def test_get_customer_bookings(self, async_client, test_booking, customer_headers):
        """Test getting customer bookings."""
        response = await async_client.get(
            "/api/v1/bookings/",
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Check that our booking is included
        booking_ids = [b["id"] for b in data]
        assert str(test_booking.id) in booking_ids

    @pytest.mark.asyncio
    async def test_get_provider_bookings(self, async_client, test_booking, provider_headers):
        """Test getting provider bookings."""
        response = await async_client.get(
            "/api/v1/bookings/",
            headers=provider_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Should include bookings for this provider
        booking_ids = [b["id"] for b in data]
        assert str(test_booking.id) in booking_ids

    @pytest.mark.asyncio
    async def test_update_booking_status_by_provider(self, async_client, test_booking, provider_headers, test_db):
        """Test provider updating booking status."""
        # Update status to confirmed
        response = await async_client.put(
            f"/api/v1/bookings/{test_booking.id}/status?status=confirmed",
            headers=provider_headers
        )
        assert response.status_code == 200

        # Verify status was updated in database
        updated_booking = await test_db.bookings.find_one({"_id": test_booking.id})
        assert updated_booking["status"] == "confirmed"

    @pytest.mark.asyncio
    async def test_update_booking_status_unauthorized(self, async_client, test_booking, customer_headers):
        """Test unauthorized booking status update."""
        # Customer trying to update status (should fail)
        response = await async_client.put(
            f"/api/v1/bookings/{test_booking.id}/status?status=confirmed",
            headers=customer_headers
        )
        assert response.status_code == 403


class TestBookingCancellation:
    """Test booking cancellation and rescheduling."""

    @pytest.fixture
    async def pending_booking(self, test_db, test_customer, test_service_provider):
        """Create a pending booking for cancellation tests."""
        booking_data = {
            "customer_id": str(test_customer.id),
            "provider_id": str(test_service_provider.id),
            "service_type": "plumber",
            "date": "2026-02-20",
            "time": "14:00",
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await test_db.bookings.insert_one(booking_data)
        booking_data["_id"] = str(result.inserted_id)
        return Booking(**booking_data)

    @pytest.mark.asyncio
    async def test_cancel_booking(self, async_client, pending_booking, customer_headers, test_db):
        """Test booking cancellation."""
        cancel_data = {
            "reason": "Schedule conflict"
        }

        response = await async_client.put(
            f"/api/v1/bookings/{pending_booking.id}/cancel",
            json=cancel_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "cancelled"

        # Verify in database
        updated_booking = await test_db.bookings.find_one({"_id": pending_booking.id})
        assert updated_booking["status"] == "cancelled"
        assert updated_booking["cancellation_reason"] == "Schedule conflict"

    @pytest.mark.asyncio
    async def test_reschedule_booking(self, async_client, pending_booking, customer_headers, test_db):
        """Test booking rescheduling."""
        reschedule_data = {
            "new_date": "2026-02-21",
            "new_time": "16:00",
            "reason": "Need to change time"
        }

        response = await async_client.put(
            f"/api/v1/bookings/{pending_booking.id}/cancel",
            json=reschedule_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "pending"  # Reset to pending for rescheduled booking
        assert data["date"] == "2026-02-21"
        assert data["time"] == "16:00"

    @pytest.mark.asyncio
    async def test_cancel_completed_booking(self, async_client, test_db, test_customer, test_service_provider, customer_headers):
        """Test canceling a completed booking (should fail)."""
        # Create a completed booking
        booking_data = {
            "customer_id": str(test_customer.id),
            "provider_id": str(test_service_provider.id),
            "service_type": "plumber",
            "date": "2026-02-15",
            "time": "10:00",
            "status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await test_db.bookings.insert_one(booking_data)
        booking_id = str(result.inserted_id)

        cancel_data = {"reason": "Changed mind"}

        response = await async_client.put(
            f"/api/v1/bookings/{booking_id}/cancel",
            json=cancel_data,
            headers=customer_headers
        )
        assert response.status_code == 400
        assert "completed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cancel_booking_wrong_customer(self, async_client, pending_booking, test_db):
        """Test canceling booking by wrong customer."""
        # Create another customer
        other_customer_data = {
            "phone_number": "+3333333333",
            "name": "Other Customer",
            "password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfLkIwXH7iN8K2",
            "role": "customer",
            "created_at": datetime.utcnow()
        }

        result = await test_db.users.insert_one(other_customer_data)
        other_customer_id = str(result.inserted_id)

        # Create token for other customer
        token = create_access_token({"sub": other_customer_id, "role": "customer"})
        headers = {"Authorization": f"Bearer {token}"}

        cancel_data = {"reason": "Test"}

        response = await async_client.put(
            f"/api/v1/bookings/{pending_booking.id}/cancel",
            json=cancel_data,
            headers=headers
        )
        assert response.status_code == 403


class TestBookingRating:
    """Test booking rating functionality."""

    @pytest.fixture
    async def completed_booking(self, test_db, test_customer, test_service_provider):
        """Create a completed booking for rating tests."""
        booking_data = {
            "customer_id": str(test_customer.id),
            "provider_id": str(test_service_provider.id),
            "service_type": "plumber",
            "date": "2026-02-10",
            "time": "14:00",
            "status": "completed",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await test_db.bookings.insert_one(booking_data)
        booking_data["_id"] = str(result.inserted_id)
        return Booking(**booking_data)

    @pytest.mark.asyncio
    async def test_rate_completed_booking(self, async_client, completed_booking, test_customer, test_service_provider, customer_headers, test_db):
        """Test rating a completed booking."""
        rating_data = {
            "booking_id": str(completed_booking.id),
            "customer_id": str(test_customer.id),
            "provider_id": str(test_service_provider.id),
            "rating": 5,
            "comment": "Excellent service! Very professional and punctual."
        }

        response = await async_client.post(
            f"/api/v1/bookings/{completed_booking.id}/rate",
            json=rating_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["rating"] == 5
        assert data["comment"] == rating_data["comment"]
        assert "id" in data

        # Verify rating was created in database
        rating_in_db = await test_db.ratings.find_one({"booking_id": str(completed_booking.id)})
        assert rating_in_db is not None
        assert rating_in_db["rating"] == 5

        # Verify provider rating was updated
        updated_provider = await test_db.service_providers.find_one({"_id": test_service_provider.id})
        # Rating should be updated (calculation depends on existing ratings)
        assert "rating" in updated_provider
        assert "total_ratings" in updated_provider

    @pytest.mark.asyncio
    async def test_rate_pending_booking(self, async_client, test_customer, test_service_provider, customer_headers, test_db):
        """Test rating a pending booking (should fail)."""
        # Create a pending booking
        booking_data = {
            "customer_id": str(test_customer.id),
            "provider_id": str(test_service_provider.id),
            "service_type": "plumber",
            "date": "2026-02-20",
            "time": "14:00",
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = await test_db.bookings.insert_one(booking_data)
        booking_id = str(result.inserted_id)

        rating_data = {
            "booking_id": booking_id,
            "customer_id": str(test_customer.id),
            "provider_id": str(test_service_provider.id),
            "rating": 4
        }

        response = await async_client.post(
            f"/api/v1/bookings/{booking_id}/rate",
            json=rating_data,
            headers=customer_headers
        )
        assert response.status_code == 400
        assert "completed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_duplicate_rating(self, async_client, completed_booking, test_customer, test_service_provider, customer_headers, test_db):
        """Test submitting duplicate rating for same booking."""
        # First rating
        rating_data = {
            "booking_id": str(completed_booking.id),
            "customer_id": str(test_customer.id),
            "provider_id": str(test_service_provider.id),
            "rating": 4,
            "comment": "Good service"
        }

        # Submit first rating
        response1 = await async_client.post(
            f"/api/v1/bookings/{completed_booking.id}/rate",
            json=rating_data,
            headers=customer_headers
        )
        assert response1.status_code == 200

        # Try to submit second rating
        response2 = await async_client.post(
            f"/api/v1/bookings/{completed_booking.id}/rate",
            json=rating_data,
            headers=customer_headers
        )
        assert response2.status_code == 409
        assert "already submitted" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_rate_invalid_rating_value(self, async_client, completed_booking, test_customer, test_service_provider, customer_headers):
        """Test rating with invalid value (should fail validation)."""
        rating_data = {
            "booking_id": str(completed_booking.id),
            "customer_id": str(test_customer.id),
            "provider_id": str(test_service_provider.id),
            "rating": 10,  # Invalid: should be 1-5
            "comment": "Test rating"
        }

        response = await async_client.post(
            f"/api/v1/bookings/{completed_booking.id}/rate",
            json=rating_data,
            headers=customer_headers
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_rate_wrong_customer(self, async_client, completed_booking, test_db):
        """Test rating by wrong customer."""
        # Create another customer
        other_customer_data = {
            "phone_number": "+4444444444",
            "name": "Wrong Customer",
            "password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfLkIwXH7iN8K2",
            "role": "customer",
            "created_at": datetime.utcnow()
        }

        result = await test_db.users.insert_one(other_customer_data)
        other_customer_id = str(result.inserted_id)

        token = create_access_token({"sub": other_customer_id, "role": "customer"})
        headers = {"Authorization": f"Bearer {token}"}

        rating_data = {
            "booking_id": str(completed_booking.id),
            "customer_id": other_customer_id,
            "provider_id": str(completed_booking.provider_id),
            "rating": 3
        }

        response = await async_client.post(
            f"/api/v1/bookings/{completed_booking.id}/rate",
            json=rating_data,
            headers=headers
        )
        assert response.status_code == 403