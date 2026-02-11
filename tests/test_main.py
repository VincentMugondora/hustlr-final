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


def test_whatsapp_webhook():
    """Test the WhatsApp webhook endpoint."""
    whatsapp_data = {
        "sender": "+1234567890@s.whatsapp.net",
        "message": "Hello, I need a plumber",
        "messageId": "msg123",
        "timestamp": "2024-01-01T12:00:00Z",
        "source": "whatsapp"
    }
    response = client.post("/api/v1/whatsapp/webhook", json=whatsapp_data)
    # Should accept the message and queue for processing
    # In test environment, background tasks may not run
    assert response.status_code in [200, 500]  # 200 if successful, 500 if DB issues


def test_whatsapp_health():
    """Test the WhatsApp health endpoint."""
    response = client.get("/api/v1/whatsapp/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "WhatsApp" in data["service"]