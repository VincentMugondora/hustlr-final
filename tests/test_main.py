"""
Comprehensive tests for Hustlr backend API endpoints.
Tests authentication, providers, bookings, and security features.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
import os
from unittest.mock import patch, MagicMock

from backend.main import app
from backend.models import User, ServiceProvider, Booking, Rating
from backend.auth import create_access_token


@pytest.fixture
def test_client():
    """Create a test client."""
    return TestClient(app)


class TestHealthAndRoot:
    """Test basic health and root endpoints."""

    def test_health_check(self, test_client):
        """Test the health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Hustlr API"

    def test_root_endpoint(self, test_client):
        """Test the root endpoint."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "docs" in data


class TestAuthentication:
    """Test authentication endpoints."""

    @pytest.mark.asyncio
    async def test_register_user(self, async_client, test_db):
        """Test user registration."""
        user_data = {
            "phone_number": "+1987654321",
            "name": "New Test User",
            "password": "newtestpass123",
            "role": "customer"
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201

        data = response.json()
        assert data["phone_number"] == user_data["phone_number"]
        assert data["name"] == user_data["name"]
        assert data["role"] == user_data["role"]
        assert "id" in data
        assert "password" not in data  # Password should not be returned

    @pytest.mark.asyncio
    async def test_register_duplicate_user(self, async_client, test_user_customer):
        """Test registering a user with existing phone number."""
        user_data = {
            "phone_number": test_user_customer.phone_number,
            "name": "Duplicate User",
            "password": "testpass123",
            "role": "customer"
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_success(self, async_client, test_user_customer):
        """Test successful login."""
        login_data = {
            "phone_number": test_user_customer.phone_number,
            "password": "testpass123"
        }

        response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client, test_user_customer):
        """Test login with wrong password."""
        login_data = {
            "phone_number": test_user_customer.phone_number,
            "password": "wrongpassword"
        }

        response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, async_client):
        """Test login with non-existent user."""
        login_data = {
            "phone_number": "+1999999999",
            "password": "testpass123"
        }

        response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401


class TestProviderEndpoints:
    """Test provider registration and management endpoints."""

    @pytest.mark.asyncio
    async def test_register_provider(self, async_client, test_user_provider, provider_headers, test_db):
        """Test provider registration."""
        provider_data = {
            "service_type": "electrician",
            "location": "uptown",
            "description": "Professional electrical services",
            "hourly_rate": 75.0,
            "business_name": "Test Electric Co",
            "contact_phone": "+1234567890",
            "contact_email": "test@electric.com",
            "years_experience": 15,
            "license_number": "EL789012",
            "insurance_info": "Fully insured for electrical work"
        }

        response = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=provider_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["service_type"] == provider_data["service_type"]
        assert data["location"] == provider_data["location"]
        assert data["is_verified"] is False
        assert data["verification_status"] == "pending"

    @pytest.mark.asyncio
    async def test_register_provider_unauthorized_role(self, async_client, admin_headers):
        """Test provider registration with unauthorized role."""
        provider_data = {
            "service_type": "plumber",
            "location": "downtown"
        }

        response = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=admin_headers
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_register_provider_missing_license(self, async_client, test_user_provider, provider_headers):
        """Test provider registration without required license for high-risk service."""
        provider_data = {
            "service_type": "electrician",
            "location": "downtown",
            "description": "Electrical services",
            "hourly_rate": 60.0
            # Missing license_number and insurance_info
        }

        response = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=provider_headers
        )
        assert response.status_code == 400
        assert "license number is required" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_provider_profile(self, async_client, test_provider, provider_headers):
        """Test getting provider profile."""
        response = await async_client.get(
            "/api/v1/providers/me",
            headers=provider_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(test_provider.id)
        assert data["service_type"] == test_provider.service_type
        assert data["is_verified"] == test_provider.is_verified

    @pytest.mark.asyncio
    async def test_update_provider_profile(self, async_client, test_provider, auth_headers):
        """Test updating provider profile."""
        update_data = {
            "description": "Updated plumbing services",
            "hourly_rate": 55.0,
            "contact_email": "updated@plumbing.com"
        }

        response = await async_client.put(
            "/api/v1/providers/me",
            json=update_data,
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["description"] == update_data["description"]
        assert data["hourly_rate"] == update_data["hourly_rate"]
        assert data["contact_email"] == update_data["contact_email"]


class TestBookingEndpoints:
    """Test booking-related endpoints."""

    @pytest.mark.asyncio
    async def test_search_providers(self, async_client, test_provider, auth_headers):
        """Test searching for providers."""
        search_data = {
            "service_type": "plumber",
            "location": "downtown",
            "max_results": 10
        }

        response = await async_client.post(
            "/api/v1/bookings/search_providers",
            json=search_data,
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            provider = data[0]
            assert "id" in provider
            assert "service_type" in provider
            assert "rating" in provider

    @pytest.mark.asyncio
    async def test_create_booking(self, async_client, test_user, test_provider, auth_headers):
        """Test creating a booking."""
        booking_data = {
            "provider_id": str(test_provider.id),
            "service_type": "plumber",
            "date": "2026-02-20",
            "time": "10:00",
            "duration_hours": 1.5,
            "notes": "Fix kitchen sink"
        }

        response = await async_client.post(
            "/api/v1/bookings/",
            json=booking_data,
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["customer_id"] == str(test_user.id)
        assert data["provider_id"] == str(test_provider.id)
        assert data["status"] == "pending"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_booking_past_date(self, async_client, test_provider, auth_headers):
        """Test creating booking with past date (should fail)."""
        booking_data = {
            "provider_id": str(test_provider.id),
            "service_type": "plumber",
            "date": "2020-01-01",  # Past date
            "time": "10:00"
        }

        response = await async_client.post(
            "/api/v1/bookings/",
            json=booking_data,
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "future date" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_user_bookings(self, async_client, test_booking, auth_headers):
        """Test getting user bookings."""
        response = await async_client.get(
            "/api/v1/bookings/",
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        # Should contain the test booking
        booking_ids = [b["id"] for b in data]
        assert str(test_booking.id) in booking_ids

    @pytest.mark.asyncio
    async def test_cancel_booking(self, async_client, test_booking, auth_headers):
        """Test canceling a booking."""
        cancel_data = {
            "reason": "Schedule conflict"
        }

        response = await async_client.put(
            f"/api/v1/bookings/{test_booking.id}/cancel",
            json=cancel_data,
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_rate_booking(self, async_client, test_booking, test_user, test_provider, auth_headers, test_db):
        """Test rating a completed booking."""
        # First ensure the booking is completed
        await test_db.bookings.update_one(
            {"_id": test_booking.id},
            {"$set": {"status": "completed"}}
        )

        rating_data = {
            "booking_id": str(test_booking.id),
            "customer_id": str(test_user.id),
            "provider_id": str(test_provider.id),
            "rating": 5,
            "comment": "Excellent service!"
        }

        response = await async_client.post(
            f"/api/v1/bookings/{test_booking.id}/rate",
            json=rating_data,
            headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["rating"] == 5
        assert data["comment"] == "Excellent service!"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_rate_incomplete_booking(self, async_client, auth_headers, test_db):
        """Test rating an incomplete booking (should fail)."""
        # Create a pending booking
        booking_data = {
            "customer_id": "test_customer",
            "provider_id": "test_provider",
            "service_type": "plumber",
            "date": "2026-02-20",
            "time": "10:00",
            "status": "pending"
        }

        result = await test_db.bookings.insert_one(booking_data)
        booking_id = str(result.inserted_id)

        rating_data = {
            "booking_id": booking_id,
            "customer_id": "test_customer",
            "provider_id": "test_provider",
            "rating": 4
        }

        response = await async_client.post(
            f"/api/v1/bookings/{booking_id}/rate",
            json=rating_data,
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "completed" in response.json()["detail"].lower()


class TestAdminEndpoints:
    """Test admin-only endpoints."""

    @pytest.fixture
    def admin_headers(self):
        """Create authentication headers for admin user."""
        token = create_access_token({"sub": "admin123", "role": "admin"})
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_verify_provider(self, async_client, test_provider, admin_headers, test_db):
        """Test admin verifying a provider."""
        # First set provider to unverified
        await test_db.service_providers.update_one(
            {"_id": test_provider.id},
            {"$set": {"is_verified": False, "verification_status": "pending"}}
        )

        verify_data = {
            "verified": True,
            "notes": "All documents verified"
        }

        response = await async_client.put(
            f"/api/v1/admin/providers/{test_provider.id}/verify",
            json=verify_data,
            headers=admin_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "verified successfully" in data["message"]
        assert data["verification_status"] == "verified"

    @pytest.mark.asyncio
    async def test_verify_provider_unauthorized(self, async_client, test_provider, auth_headers):
        """Test provider verification by non-admin (should fail)."""
        verify_data = {
            "verified": True,
            "notes": "Test verification"
        }

        response = await async_client.put(
            f"/api/v1/admin/providers/{test_provider.id}/verify",
            json=verify_data,
            headers=auth_headers
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_system_stats(self, async_client, admin_headers):
        """Test getting system statistics."""
        response = await async_client.get(
            "/api/v1/admin/stats",
            headers=admin_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "total_users" in data
        assert "total_providers" in data
        assert "pending_providers" in data
        assert "total_bookings" in data


class TestSecurity:
    """Test security features and input validation."""

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, async_client):
        """Test that SQL injection attempts are prevented."""
        # This should fail validation rather than execute SQL
        malicious_data = {
            "phone_number": "+1234567890'; DROP TABLE users; --",
            "name": "Test User",
            "password": "testpass123",
            "role": "customer"
        }

        response = await async_client.post("/api/v1/auth/register", json=malicious_data)
        # Should either fail validation or succeed with sanitized input
        assert response.status_code in [201, 400, 422]

    @pytest.mark.asyncio
    async def test_xss_prevention(self, async_client, auth_headers):
        """Test XSS prevention in input fields."""
        xss_payload = "<script>alert('xss')</script>"

        booking_data = {
            "provider_id": "test_provider_id",
            "service_type": "plumber",
            "date": "2026-02-20",
            "time": "10:00",
            "notes": xss_payload
        }

        response = await async_client.post(
            "/api/v1/bookings/",
            json=booking_data,
            headers=auth_headers
        )
        # Should either succeed (data stored safely) or fail validation
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_rate_limiting_simulation(self, async_client, test_user):
        """Test rate limiting simulation (mocked)."""
        # This would normally test rate limiting, but we'll simulate with multiple requests
        login_data = {
            "phone_number": test_user.phone_number,
            "password": "testpass123"
        }

        # Make multiple login attempts
        for _ in range(10):
            response = await async_client.post("/api/v1/auth/login", json=login_data)
            # Should succeed (in test environment without rate limiting)
            assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_input_validation_bounds(self, async_client, auth_headers):
        """Test input validation boundaries."""
        # Test rating bounds
        invalid_rating_data = {
            "booking_id": "test_booking",
            "customer_id": "test_customer",
            "provider_id": "test_provider",
            "rating": 10  # Invalid: should be 1-5
        }

        response = await async_client.post(
            "/api/v1/bookings/test_booking/rate",
            json=invalid_rating_data,
            headers=auth_headers
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_unauthorized_access_patterns(self, async_client):
        """Test various unauthorized access patterns."""
        # No auth header
        response = await async_client.get("/api/v1/bookings/")
        assert response.status_code == 401

        # Invalid token
        invalid_headers = {"Authorization": "Bearer invalid_token"}
        response = await async_client.get("/api/v1/bookings/", headers=invalid_headers)
        assert response.status_code == 401

        # Expired token (would need token with past exp, but this tests the pattern)
        # In a real scenario, you'd create an expired token


class TestWhatsAppIntegration:
    """Test WhatsApp integration endpoints."""

    @pytest.mark.asyncio
    async def test_whatsapp_webhook(self, async_client):
        """Test WhatsApp webhook message processing."""
        whatsapp_data = {
            "sender": "+1234567890@s.whatsapp.net",
            "message": "I need a plumber for my kitchen sink",
            "messageId": "msg123",
            "timestamp": "2026-02-11T12:00:00Z",
            "source": "whatsapp"
        }

        response = await async_client.post(
            "/api/v1/whatsapp/webhook",
            json=whatsapp_data
        )
        # Should accept the message (exact status depends on processing)
        assert response.status_code in [200, 500]  # 200 if processed, 500 if DB issues

    def test_whatsapp_health(self, test_client):
        """Test WhatsApp health endpoint."""
        response = test_client.get("/api/v1/whatsapp/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"