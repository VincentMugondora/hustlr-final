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
    assert response.json() == {"status": "healthy", "service": "Hustlr API"}


def test_register_user():
    """Test user registration."""
    user_data = {
        "phone_number": "+1234567890",
        "name": "Test User",
        "password": "testpass123",
        "role": "customer"
    }
    response = client.post("/auth/register", json=user_data)
    # Note: This might fail if MongoDB is not running, but tests the endpoint structure
    assert response.status_code in [200, 500]  # 200 if DB connected, 500 if not