"""
Comprehensive tests for provider registration and verification endpoints.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from httpx import AsyncClient

from backend.main import app
from backend.models import User, ServiceProvider
from backend.auth import create_access_token


@pytest.fixture
async def test_db():
    """Create a test database connection."""
    from motor.motor_asyncio import AsyncIOMotorClient
    import os

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    test_db_name = "hustlr_test_providers"

    client = AsyncIOMotorClient(mongo_uri)
    db = client[test_db_name]

    yield db

    # Clean up after tests
    client.drop_database(test_db_name)
    client.close()


@pytest.fixture
async def test_user_customer(test_db):
    """Create a test customer user."""
    user_data = {
        "phone_number": "+5555555555",
        "name": "Test Customer",
        "password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfLkIwXH7iN8K2",
        "role": "customer",
        "created_at": datetime.utcnow()
    }

    result = await test_db.users.insert_one(user_data)
    user_data["_id"] = str(result.inserted_id)
    return User(**user_data)


@pytest.fixture
async def test_user_provider(test_db):
    """Create a test provider user."""
    user_data = {
        "phone_number": "+6666666666",
        "name": "Test Provider User",
        "password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfLkIwXH7iN8K2",
        "role": "provider",
        "created_at": datetime.utcnow()
    }

    result = await test_db.users.insert_one(user_data)
    user_data["_id"] = str(result.inserted_id)
    return User(**user_data)


@pytest.fixture
async def test_provider(test_db, test_user_provider):
    """Create a test service provider."""
    provider_data = {
        "user_id": str(test_user_provider.id),
        "service_type": "electrician",
        "location": "midtown",
        "description": "Licensed electrical services",
        "hourly_rate": 75.0,
        "business_name": "Test Electric",
        "contact_phone": "+6666666666",
        "contact_email": "test@electric.com",
        "years_experience": 15,
        "license_number": "EL789012",
        "insurance_info": "Fully insured for electrical work",
        "verification_documents": ["license.pdf", "insurance.pdf"],
        "is_verified": True,
        "verification_status": "verified",
        "rating": 4.8,
        "total_ratings": 25,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await test_db.service_providers.insert_one(provider_data)
    provider_data["_id"] = str(result.inserted_id)
    return ServiceProvider(**provider_data)


@pytest.fixture
def customer_headers(test_user_customer):
    """Create authentication headers for customer."""
    token = create_access_token({"sub": str(test_user_customer.id), "role": test_user_customer.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def provider_headers(test_user_provider):
    """Create authentication headers for provider."""
    token = create_access_token({"sub": str(test_user_provider.id), "role": test_user_provider.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    """Create authentication headers for admin."""
    token = create_access_token({"sub": "admin123", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


class TestProviderRegistration:
    """Test provider registration functionality."""

    @pytest.mark.asyncio
    async def test_register_provider_complete_info(self, async_client, test_user_customer, customer_headers, test_db):
        """Test registering a provider with complete information."""
        provider_data = {
            "service_type": "carpenter",
            "location": "suburb",
            "description": "Custom furniture and woodworking",
            "hourly_rate": 60.0,
            "business_name": "Craft Woodworking",
            "contact_phone": "+1555123456",
            "contact_email": "craft@woodworking.com",
            "years_experience": 12,
            "license_number": "CW345678",
            "insurance_info": "General liability insurance",
            "verification_documents": ["license.pdf", "portfolio.pdf"]
        }

        response = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["service_type"] == provider_data["service_type"]
        assert data["location"] == provider_data["location"]
        assert data["business_name"] == provider_data["business_name"]
        assert data["is_verified"] is False
        assert data["verification_status"] == "pending"
        assert "id" in data

        # Verify provider was created in database
        provider_in_db = await test_db.service_providers.find_one({"_id": data["id"]})
        assert provider_in_db is not None
        assert provider_in_db["user_id"] == str(test_user_customer.id)
        assert provider_in_db["license_number"] == provider_data["license_number"]

    @pytest.mark.asyncio
    async def test_register_provider_minimal_info(self, async_client, test_user_customer, customer_headers, test_db):
        """Test registering a provider with minimal required information."""
        provider_data = {
            "service_type": "painter",
            "location": "downtown",
            "description": "Interior and exterior painting"
        }

        response = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["service_type"] == provider_data["service_type"]
        assert data["hourly_rate"] is None  # Optional field
        assert data["is_verified"] is False

    @pytest.mark.asyncio
    async def test_register_provider_duplicate(self, async_client, test_user_customer, customer_headers, test_db):
        """Test registering a provider when one already exists for the user."""
        # First registration
        provider_data = {
            "service_type": "plumber",
            "location": "uptown"
        }

        response1 = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=customer_headers
        )
        assert response1.status_code == 200

        # Second registration attempt
        response2 = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=customer_headers
        )
        assert response2.status_code == 400
        assert "already registered" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_provider_invalid_email(self, async_client, test_user_customer, customer_headers):
        """Test registering provider with invalid email."""
        provider_data = {
            "service_type": "plumber",
            "location": "downtown",
            "contact_email": "invalid-email"  # Missing @ symbol
        }

        response = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=customer_headers
        )
        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_provider_high_risk_without_license(self, async_client, test_user_customer, customer_headers):
        """Test registering high-risk service provider without license."""
        provider_data = {
            "service_type": "electrician",
            "location": "downtown",
            "description": "Electrical services"
            # Missing license_number and insurance_info
        }

        response = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=customer_headers
        )
        assert response.status_code == 400
        assert "license" in response.json()["detail"].lower()

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
    async def test_register_provider_invalid_service_type(self, async_client, test_user_customer, customer_headers):
        """Test registering provider with invalid service type."""
        provider_data = {
            "service_type": "",  # Empty service type
            "location": "downtown"
        }

        response = await async_client.post(
            "/api/v1/providers/register",
            json=provider_data,
            headers=customer_headers
        )
        assert response.status_code == 422  # Validation error


class TestProviderProfileManagement:
    """Test provider profile retrieval and updates."""

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
        assert data["business_name"] == test_provider.business_name
        assert data["license_number"] == test_provider.license_number
        assert data["is_verified"] == test_provider.is_verified

    @pytest.mark.asyncio
    async def test_get_provider_profile_not_exists(self, async_client, customer_headers):
        """Test getting provider profile when none exists."""
        response = await async_client.get(
            "/api/v1/providers/me",
            headers=customer_headers
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_provider_profile(self, async_client, test_provider, provider_headers, test_db):
        """Test updating provider profile."""
        update_data = {
            "description": "Updated electrical services with new equipment",
            "hourly_rate": 80.0,
            "contact_email": "updated@electric.com",
            "years_experience": 16
        }

        response = await async_client.put(
            "/api/v1/providers/me",
            json=update_data,
            headers=provider_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["description"] == update_data["description"]
        assert data["hourly_rate"] == update_data["hourly_rate"]
        assert data["contact_email"] == update_data["contact_email"]
        assert data["years_experience"] == update_data["years_experience"]

        # Verify in database
        updated_provider = await test_db.service_providers.find_one({"_id": test_provider.id})
        assert updated_provider["description"] == update_data["description"]
        assert updated_provider["updated_at"] > test_provider.updated_at

    @pytest.mark.asyncio
    async def test_update_provider_profile_unauthorized_fields(self, async_client, test_provider, provider_headers):
        """Test that providers cannot update verification fields."""
        update_data = {
            "is_verified": True,
            "verification_status": "verified",
            "description": "Updated description"
        }

        response = await async_client.put(
            "/api/v1/providers/me",
            json=update_data,
            headers=provider_headers
        )
        assert response.status_code == 200

        data = response.json()
        # Verification fields should not be updated by providers
        assert data["is_verified"] == test_provider.is_verified  # Should remain unchanged
        assert data["description"] == update_data["description"]  # Should be updated

    @pytest.mark.asyncio
    async def test_update_provider_profile_validation(self, async_client, test_provider, provider_headers):
        """Test validation when updating provider profile."""
        update_data = {
            "hourly_rate": -50.0,  # Invalid negative rate
            "contact_email": "invalid-email"
        }

        response = await async_client.put(
            "/api/v1/providers/me",
            json=update_data,
            headers=provider_headers
        )
        assert response.status_code == 422  # Validation error


class TestProviderSearch:
    """Test provider search functionality."""

    @pytest.mark.asyncio
    async def test_search_providers_basic(self, async_client, test_provider, customer_headers):
        """Test basic provider search."""
        search_data = {
            "service_type": "electrician",
            "location": "midtown"
        }

        response = await async_client.get(
            "/api/v1/providers/search",
            params=search_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Check that our test provider is in results
        provider_ids = [p["id"] for p in data]
        assert str(test_provider.id) in provider_ids

    @pytest.mark.asyncio
    async def test_search_providers_regex(self, async_client, test_provider, customer_headers):
        """Test provider search with regex matching."""
        # Search for partial matches
        search_data = {
            "service_type": "electri",  # Partial match
            "location": "mid"  # Partial match
        }

        response = await async_client.get(
            "/api/v1/providers/search",
            params=search_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_search_providers_only_verified(self, async_client, customer_headers, test_db):
        """Test that search only returns verified providers."""
        # Create an unverified provider
        unverified_provider_data = {
            "user_id": "test_user",
            "service_type": "plumber",
            "location": "downtown",
            "is_verified": False,
            "created_at": datetime.utcnow()
        }

        result = await test_db.service_providers.insert_one(unverified_provider_data)

        search_data = {
            "service_type": "plumber",
            "location": "downtown"
        }

        response = await async_client.get(
            "/api/v1/providers/search",
            params=search_data,
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        # Should not include unverified provider
        provider_ids = [p["id"] for p in data]
        assert str(result.inserted_id) not in provider_ids

    @pytest.mark.asyncio
    async def test_get_specific_provider(self, async_client, test_provider, customer_headers):
        """Test getting a specific provider by ID."""
        response = await async_client.get(
            f"/api/v1/providers/{test_provider.id}",
            headers=customer_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(test_provider.id)
        assert data["service_type"] == test_provider.service_type

    @pytest.mark.asyncio
    async def test_get_nonexistent_provider(self, async_client, customer_headers):
        """Test getting a non-existent provider."""
        response = await async_client.get(
            "/api/v1/providers/507f1f77bcf86cd799439011",  # Random ObjectId
            headers=customer_headers
        )
        assert response.status_code == 404


class TestAdminProviderVerification:
    """Test admin provider verification functionality."""

    @pytest.mark.asyncio
    async def test_get_pending_providers(self, async_client, admin_headers, test_db):
        """Test getting list of pending provider verifications."""
        # Create a pending provider
        pending_provider_data = {
            "user_id": "test_user",
            "service_type": "mechanic",
            "location": "rural",
            "is_verified": False,
            "verification_status": "pending",
            "created_at": datetime.utcnow()
        }

        result = await test_db.service_providers.insert_one(pending_provider_data)

        response = await async_client.get(
            "/api/v1/admin/providers/pending",
            headers=admin_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Check that pending provider is included
        provider_ids = [p["id"] for p in data]
        assert str(result.inserted_id) in provider_ids

    @pytest.mark.asyncio
    async def test_verify_provider_success(self, async_client, test_provider, admin_headers, test_db):
        """Test successful provider verification."""
        # First set provider to unverified
        await test_db.service_providers.update_one(
            {"_id": test_provider.id},
            {"$set": {"is_verified": False, "verification_status": "pending"}}
        )

        verify_data = {
            "verified": True,
            "notes": "All documents verified. License and insurance confirmed."
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

        # Verify in database
        updated_provider = await test_db.service_providers.find_one({"_id": test_provider.id})
        assert updated_provider["is_verified"] is True
        assert updated_provider["verification_status"] == "verified"
        assert updated_provider["verification_notes"] == verify_data["notes"]
        assert updated_provider["verified_at"] is not None

    @pytest.mark.asyncio
    async def test_reject_provider(self, async_client, test_provider, admin_headers, test_db):
        """Test rejecting a provider application."""
        # First set provider to unverified
        await test_db.service_providers.update_one(
            {"_id": test_provider.id},
            {"$set": {"is_verified": False, "verification_status": "pending"}}
        )

        verify_data = {
            "verified": False,
            "notes": "Insurance document expired. Please provide updated insurance."
        }

        response = await async_client.put(
            f"/api/v1/admin/providers/{test_provider.id}/verify",
            json=verify_data,
            headers=admin_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "rejected" in data["message"]
        assert data["verification_status"] == "rejected"

        # Verify in database
        updated_provider = await test_db.service_providers.find_one({"_id": test_provider.id})
        assert updated_provider["is_verified"] is False
        assert updated_provider["verification_status"] == "rejected"
        assert updated_provider["verification_notes"] == verify_data["notes"]

    @pytest.mark.asyncio
    async def test_verify_nonexistent_provider(self, async_client, admin_headers):
        """Test verifying a non-existent provider."""
        verify_data = {
            "verified": True,
            "notes": "Test verification"
        }

        response = await async_client.put(
            "/api/v1/admin/providers/507f1f77bcf86cd799439011/verify",  # Random ObjectId
            json=verify_data,
            headers=admin_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_verify_already_verified_provider(self, async_client, test_provider, admin_headers):
        """Test verifying an already verified provider."""
        verify_data = {
            "verified": True,
            "notes": "Double verification attempt"
        }

        response = await async_client.put(
            f"/api/v1/admin/providers/{test_provider.id}/verify",
            json=verify_data,
            headers=admin_headers
        )
        assert response.status_code == 400
        assert "already been verified" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_verify_provider_unauthorized(self, async_client, test_provider, customer_headers):
        """Test provider verification by non-admin."""
        verify_data = {
            "verified": True,
            "notes": "Unauthorized verification attempt"
        }

        response = await async_client.put(
            f"/api/v1/admin/providers/{test_provider.id}/verify",
            json=verify_data,
            headers=customer_headers
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

        # All counts should be non-negative
        assert data["total_users"] >= 0
        assert data["total_providers"] >= 0
        assert data["pending_providers"] >= 0
        assert data["total_bookings"] >= 0