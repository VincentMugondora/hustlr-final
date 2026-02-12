"""
Comprehensive tests for authentication endpoints.
Tests user registration, login, and security features.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from jose import jwt

from backend.main import app
from backend.models import User
from backend.auth import create_access_token, verify_password
from backend.config import SECRET_KEY, ALGORITHM


class TestUserRegistration:
    """Test user registration functionality."""

    @pytest.mark.asyncio
    async def test_register_customer_success(self, async_client, test_db):
        """Test successful customer registration."""
        user_data = {
            "phone_number": "+15551111111",
            "name": "John Doe",
            "password": "securepass123",
            "role": "customer"
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

        # Verify user was created in database
        user = await test_db.users.find_one({"phone_number": user_data["phone_number"]})
        assert user is not None
        assert user["name"] == user_data["name"]
        assert user["role"] == user_data["role"]
        assert "password" in user  # Password should be hashed

        # Verify password was hashed
        assert user["password"] != user_data["password"]
        assert verify_password(user_data["password"], user["password"])

    @pytest.mark.asyncio
    async def test_register_provider_success(self, async_client, test_db):
        """Test successful provider registration."""
        user_data = {
            "phone_number": "+15552222222",
            "name": "Jane Smith",
            "password": "providerpass456",
            "role": "provider"
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data

        # Verify user was created
        user = await test_db.users.find_one({"phone_number": user_data["phone_number"]})
        assert user is not None
        assert user["role"] == "provider"

    @pytest.mark.asyncio
    async def test_register_duplicate_phone_number(self, async_client, test_user_customer):
        """Test registration with duplicate phone number fails."""
        user_data = {
            "phone_number": test_user_customer.phone_number,
            "name": "Duplicate User",
            "password": "anypassword",
            "role": "customer"
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 400

        data = response.json()
        assert "already registered" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_role(self, async_client):
        """Test registration with invalid role fails."""
        user_data = {
            "phone_number": "+15553333333",
            "name": "Invalid Role User",
            "password": "password123",
            "role": "invalid_role"
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_register_weak_password(self, async_client):
        """Test registration with weak password fails."""
        user_data = {
            "phone_number": "+15554444444",
            "name": "Weak Password User",
            "password": "123",  # Too short
            "role": "customer"
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_register_invalid_phone_format(self, async_client):
        """Test registration with invalid phone format fails."""
        user_data = {
            "phone_number": "invalid_phone",
            "name": "Invalid Phone User",
            "password": "password123",
            "role": "customer"
        }

        response = await async_client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 422  # Validation error


class TestUserLogin:
    """Test user login functionality."""

    @pytest.mark.asyncio
    async def test_login_success(self, async_client, test_user_customer):
        """Test successful login."""
        login_data = {
            "phone_number": test_user_customer.phone_number,
            "password": "testpass123"  # This matches the hashed password in conftest.py
        }

        response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

        # Verify token is valid
        token = data["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == str(test_user_customer.id)
        assert payload["role"] == test_user_customer.role

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client, test_user_customer):
        """Test login with wrong password fails."""
        login_data = {
            "phone_number": test_user_customer.phone_number,
            "password": "wrongpassword"
        }

        response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401

        data = response.json()
        assert "invalid credentials" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, async_client):
        """Test login with nonexistent user fails."""
        login_data = {
            "phone_number": "+15559999999",
            "password": "password123"
        }

        response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401

        data = response.json()
        assert "invalid credentials" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_invalid_phone_format(self, async_client):
        """Test login with invalid phone format fails."""
        login_data = {
            "phone_number": "invalid_phone",
            "password": "password123"
        }

        response = await async_client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 422  # Validation error


class TestTokenValidation:
    """Test JWT token validation and security."""

    @pytest.mark.asyncio
    async def test_valid_token_access(self, async_client, customer_headers):
        """Test accessing protected endpoint with valid token."""
        response = await async_client.get("/api/v1/bookings/", headers=customer_headers)
        # Should succeed (may return empty list, but not auth error)
        assert response.status_code in [200, 404]  # 200 with data, 404 if no bookings

    @pytest.mark.asyncio
    async def test_invalid_token_access(self, async_client):
        """Test accessing protected endpoint with invalid token fails."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = await async_client.get("/api/v1/bookings/", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_access(self, async_client):
        """Test accessing protected endpoint with expired token fails."""
        # Create expired token
        expired_payload = {
            "sub": "test_user",
            "role": "customer",
            "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        }
        expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await async_client.get("/api/v1/bookings/", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_token_access(self, async_client):
        """Test accessing protected endpoint without token fails."""
        response = await async_client.get("/api/v1/bookings/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_authorization_header(self, async_client):
        """Test malformed authorization header fails."""
        headers = {"Authorization": "InvalidFormat token123"}
        response = await async_client.get("/api/v1/bookings/", headers=headers)
        assert response.status_code == 401


class TestSecurity:
    """Test security features and input validation."""

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, async_client):
        """Test that SQL injection attempts are prevented."""
        # This should fail validation, not execute SQL
        malicious_data = {
            "phone_number": "+15551111111'; DROP TABLE users; --",
            "name": "Hacker",
            "password": "password123",
            "role": "customer"
        }

        response = await async_client.post("/api/v1/auth/register", json=malicious_data)
        # Should fail validation due to phone format, not execute SQL
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_xss_prevention(self, async_client):
        """Test that XSS attempts are prevented."""
        xss_data = {
            "phone_number": "+15551111111",
            "name": "<script>alert('XSS')</script>",
            "password": "password123",
            "role": "customer"
        }

        response = await async_client.post("/api/v1/auth/register", json=xss_data)
        assert response.status_code == 200  # Name field allows special chars

        # Verify data is stored as-is (XSS prevention is handled by frontend/output encoding)
        user = await async_client.app.state.db.users.find_one({"phone_number": xss_data["phone_number"]})
        if user:
            assert user["name"] == xss_data["name"]

    @pytest.mark.asyncio
    async def test_rate_limiting_placeholder(self, async_client):
        """Placeholder for rate limiting tests (would need middleware)."""
        # Multiple rapid requests should be rate limited
        # This is a placeholder - actual implementation would require rate limiting middleware
        pass</content>
<parameter name="filePath">c:\Users\vinmu\Desktop\hustlr-final\tests\test_auth.py
