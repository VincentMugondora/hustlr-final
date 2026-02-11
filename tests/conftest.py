"""
Pytest configuration and fixtures for Hustlr backend tests.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os
from backend.models import User, ServiceProvider, Booking
from backend.auth import create_access_token


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db():
    """Create a test database connection."""
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    test_db_name = "hustlr_test"

    client = AsyncIOMotorClient(mongo_uri)
    db = client[test_db_name]

    yield db

    # Clean up after tests
    client.drop_database(test_db_name)
    client.close()


@pytest.fixture
async def async_client():
    """Create an async test client."""
    from httpx import AsyncClient
    from backend.main import app

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def test_user_customer(test_db):
    """Create a test customer user."""
    user_data = {
        "phone_number": "+15551111111",
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
        "phone_number": "+15552222222",
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
        "contact_phone": "+15552222222",
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
async def test_booking(test_db, test_user_customer, test_provider):
    """Create a test booking."""
    booking_data = {
        "customer_id": str(test_user_customer.id),
        "provider_id": str(test_provider.id),
        "service_type": "electrician",
        "date": "2026-02-20",
        "time": "14:00",
        "duration_hours": 2.0,
        "status": "completed",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await test_db.bookings.insert_one(booking_data)
    booking_data["_id"] = str(result.inserted_id)
    return Booking(**booking_data)


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