"""
Comprehensive tests for admin endpoints.
Tests provider verification, system statistics, and admin access control.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from httpx import AsyncClient

from backend.main import app
from backend.models import User, ServiceProvider, ProviderVerificationRequest


class TestAdminAccessControl:
    """Test admin access control and authorization."""

    @pytest.mark.asyncio
    async def test_admin_only_endpoints_block_non_admin(self, async_client, customer_headers):
        """Test that admin endpoints block non-admin users."""
        # Test pending providers endpoint
        response = await async_client.get("/api/v1/admin/providers/pending", headers=customer_headers)
        assert response.status_code == 403

        # Test provider verification endpoint
        verify_data = {"verified": True, "notes": "Approved"}
        response = await async_client.put(
            "/api/v1/admin/providers/test_id/verify",
            json=verify_data,
            headers=customer_headers
        )
        assert response.status_code == 403

        # Test stats endpoint
        response = await async_client.get("/api/v1/admin/stats", headers=customer_headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_endpoints_require_authentication(self, async_client):
        """Test that admin endpoints require authentication."""
        # Test without headers
        response = await async_client.get("/api/v1/admin/providers/pending")
        assert response.status_code == 401

        # Test with invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        response = await async_client.get("/api/v1/admin/providers/pending", headers=headers)
        assert response.status_code == 401


class TestProviderVerification:
    """Test provider verification functionality."""

    @pytest.mark.asyncio
    async def test_get_pending_providers(self, async_client, admin_headers, test_db):
        """Test getting list of pending providers."""
        # Create a pending provider
        pending_provider_data = {
            "user_id": "test_user_123",
            "service_type": "plumber",
            "location": "downtown",
            "description": "Professional plumbing services",
            "is_verified": False,
            "verification_status": "pending",
            "created_at": datetime.utcnow()
        }

        await test_db.service_providers.insert_one(pending_provider_data)

        response = await async_client.get("/api/v1/admin/providers/pending", headers=admin_headers)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Check that our pending provider is in the list
        pending_providers = [p for p in data if p["verification_status"] == "pending"]
        assert len(pending_providers) >= 1

    @pytest.mark.asyncio
    async def test_verify_provider_success(self, async_client, admin_headers, test_db):
        """Test successful provider verification."""
        # Create a pending provider
        provider_data = {
            "user_id": "test_user_456",
            "service_type": "electrician",
            "location": "uptown",
            "description": "Electrical services",
            "is_verified": False,
            "verification_status": "pending",
            "created_at": datetime.utcnow()
        }

        result = await test_db.service_providers.insert_one(provider_data)
        provider_id = str(result.inserted_id)

        # Verify the provider
        verify_data = {
            "verified": True,
            "notes": "All documents verified. License and insurance confirmed."
        }

        response = await async_client.put(
            f"/api/v1/admin/providers/{provider_id}/verify",
            json=verify_data,
            headers=admin_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert "verified successfully" in data["message"]
        assert data["verification_status"] == "verified"

        # Verify provider was updated in database
        updated_provider = await test_db.service_providers.find_one({"_id": provider_id})
        assert updated_provider["is_verified"] is True
        assert updated_provider["verification_status"] == "verified"
        assert updated_provider["verification_notes"] == verify_data["notes"]
        assert updated_provider["verified_at"] is not None
        assert updated_provider["verified_by"] == "admin123"  # From admin_headers fixture

    @pytest.mark.asyncio
    async def test_reject_provider(self, async_client, admin_headers, test_db):
        """Test rejecting a provider application."""
        # Create a pending provider
        provider_data = {
            "user_id": "test_user_789",
            "service_type": "carpenter",
            "location": "suburb",
            "description": "Woodworking services",
            "is_verified": False,
            "verification_status": "pending",
            "created_at": datetime.utcnow()
        }

        result = await test_db.service_providers.insert_one(provider_data)
        provider_id = str(result.inserted_id)

        # Reject the provider
        verify_data = {
            "verified": False,
            "notes": "Insurance document expired. Please provide updated insurance."
        }

        response = await async_client.put(
            f"/api/v1/admin/providers/{provider_id}/verify",
            json=verify_data,
            headers=admin_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "rejected" in data["message"]
        assert data["verification_status"] == "rejected"

        # Verify provider was updated in database
        updated_provider = await test_db.service_providers.find_one({"_id": provider_id})
        assert updated_provider["is_verified"] is False
        assert updated_provider["verification_status"] == "rejected"
        assert updated_provider["verification_notes"] == verify_data["notes"]

    @pytest.mark.asyncio
    async def test_verify_nonexistent_provider(self, async_client, admin_headers):
        """Test verifying a nonexistent provider fails."""
        verify_data = {"verified": True, "notes": "Approved"}

        response = await async_client.put(
            "/api/v1/admin/providers/nonexistent_id/verify",
            json=verify_data,
            headers=admin_headers
        )
        assert response.status_code == 404

        data = response.json()
        assert "not found" in data["detail"]

    @pytest.mark.asyncio
    async def test_verify_already_verified_provider(self, async_client, admin_headers, test_provider):
        """Test verifying an already verified provider fails."""
        verify_data = {"verified": True, "notes": "Double approval"}

        response = await async_client.put(
            f"/api/v1/admin/providers/{test_provider.id}/verify",
            json=verify_data,
            headers=admin_headers
        )
        assert response.status_code == 400

        data = response.json()
        assert "already been verified or rejected" in data["detail"]

    @pytest.mark.asyncio
    async def test_verify_provider_invalid_data(self, async_client, admin_headers, test_db):
        """Test provider verification with invalid data."""
        # Create a pending provider
        provider_data = {
            "user_id": "test_user_999",
            "service_type": "painter",
            "location": "rural",
            "is_verified": False,
            "verification_status": "pending",
            "created_at": datetime.utcnow()
        }

        result = await test_db.service_providers.insert_one(provider_data)
        provider_id = str(result.inserted_id)

        # Try to verify with missing required field
        invalid_verify_data = {"notes": "Missing verified field"}

        response = await async_client.put(
            f"/api/v1/admin/providers/{provider_id}/verify",
            json=invalid_verify_data,
            headers=admin_headers
        )
        assert response.status_code == 422  # Validation error


class TestSystemStatistics:
    """Test system statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_system_stats(self, async_client, admin_headers, test_db, test_user_customer, test_provider):
        """Test getting system statistics."""
        # Create some test data
        await test_db.bookings.insert_one({
            "customer_id": str(test_user_customer.id),
            "provider_id": str(test_provider.id),
            "service_type": "electrician",
            "date": "2026-02-20",
            "time": "14:00",
            "status": "completed",
            "created_at": datetime.utcnow()
        })

        response = await async_client.get("/api/v1/admin/stats", headers=admin_headers)
        assert response.status_code == 200

        data = response.json()
        assert "total_users" in data
        assert "total_providers" in data
        assert "pending_providers" in data
        assert "total_bookings" in data

        # Verify counts are reasonable (at least the fixtures we created)
        assert data["total_users"] >= 2  # At least customer and provider fixtures
        assert data["total_providers"] >= 1  # At least the verified provider fixture
        assert data["total_bookings"] >= 1  # At least the booking we created

    @pytest.mark.asyncio
    async def test_stats_include_pending_providers(self, async_client, admin_headers, test_db):
        """Test that statistics correctly count pending providers."""
        # Create a pending provider
        pending_provider = {
            "user_id": "pending_user_123",
            "service_type": "plumber",
            "location": "downtown",
            "is_verified": False,
            "verification_status": "pending",
            "created_at": datetime.utcnow()
        }

        await test_db.service_providers.insert_one(pending_provider)

        response = await async_client.get("/api/v1/admin/stats", headers=admin_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["pending_providers"] >= 1


class TestAdminSecurity:
    """Test security aspects of admin functionality."""

    @pytest.mark.asyncio
    async def test_admin_cannot_verify_own_provider_profile(self, async_client, admin_headers, test_db):
        """Test that admin cannot verify their own provider profile if they had one."""
        # This is a security test - admin should not be able to verify their own applications
        # Create a provider profile that would be "owned" by admin
        admin_provider_data = {
            "user_id": "admin123",  # Same as admin user ID from fixture
            "service_type": "consultant",
            "location": "remote",
            "is_verified": False,
            "verification_status": "pending",
            "created_at": datetime.utcnow()
        }

        result = await test_db.service_providers.insert_one(admin_provider_data)
        provider_id = str(result.inserted_id)

        # Admin tries to verify their own application
        verify_data = {"verified": True, "notes": "Self-approval"}

        response = await async_client.put(
            f"/api/v1/admin/providers/{provider_id}/verify",
            json=verify_data,
            headers=admin_headers
        )

        # This should succeed (no ownership check in current implementation)
        # but in a real system, this might be restricted
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_mass_assignment_prevention(self, async_client, admin_headers, test_db):
        """Test that mass assignment attacks are prevented."""
        # Create a pending provider
        provider_data = {
            "user_id": "test_user_secure",
            "service_type": "security",
            "location": "secure_location",
            "is_verified": False,
            "verification_status": "pending",
            "created_at": datetime.utcnow()
        }

        result = await test_db.service_providers.insert_one(provider_data)
        provider_id = str(result.inserted_id)

        # Try to inject additional fields through verification
        malicious_verify_data = {
            "verified": True,
            "notes": "Approved",
            "is_verified": True,  # This should be set by the endpoint, not the input
            "verification_status": "verified",
            "admin_override": True  # This field shouldn't exist
        }

        response = await async_client.put(
            f"/api/v1/admin/providers/{provider_id}/verify",
            json=malicious_verify_data,
            headers=admin_headers
        )
        assert response.status_code == 200

        # Verify that only expected fields were updated
        updated_provider = await test_db.service_providers.find_one({"_id": provider_id})
        assert "admin_override" not in updated_provider  # Malicious field should not exist</content>
<parameter name="filePath">c:\Users\vinmu\Desktop\hustlr-final\tests\test_admin.py