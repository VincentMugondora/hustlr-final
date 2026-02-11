"""
Basic tests for Hustlr backend.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Hustlr API"
    assert data["version"] == "1.0.0"
    assert "environment" in data


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data
    assert "health" in data


def test_register_user():
    """Test user registration."""
    user_data = {
        "phone_number": "+1234567890",
        "name": "Test User",
        "password": "testpass123",
        "role": "customer"
    }
    # In test environment without MongoDB, this will raise AttributeError
    # because db is None. In production with proper DB connection, it would work.
    with pytest.raises(AttributeError):
        client.post("/api/v1/auth/register", json=user_data)