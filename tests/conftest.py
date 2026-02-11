import asyncio
import pytest
from httpx import AsyncClient

from backend.main import app


class FakeCollection:
    def __init__(self):
        self._data = {}
        self._auto = 1

    async def insert_one(self, doc):
        _id = doc.get("_id") or str(self._auto)
        self._auto += 1
        doc_copy = dict(doc)
        doc_copy["_id"] = _id
        self._data[_id] = doc_copy
        class Res: pass
        res = Res()
        res.inserted_id = _id
        res.matched_count = 1
        return res

    async def find_one(self, query):
        # naive matching for equality and _id
        for d in list(self._data.values()):
            ok = True
            for k, v in query.items():
                if k == "_id":
                    if d.get("_id") != v:
                        ok = False
                        break
                elif isinstance(v, dict) and "$in" in v:
                    if d.get(k) not in v["$in"]:
                        ok = False
                        break
                else:
                    if d.get(k) != v:
                        ok = False
                        break
            if ok:
                return dict(d)
        return None

    def _match(self, query):
        results = []
        for d in list(self._data.values()):
            ok = True
            for k, v in query.items():
                if isinstance(v, dict) and "$regex" in v:
                    if v["$regex"].lower() not in str(d.get(k, "")).lower():
                        ok = False
                        break
                elif isinstance(v, dict) and "$exists" in v:
                    exists = k in d and d.get(k) is not None
                    if exists != v["$exists"]:
                        ok = False
                        break
                else:
                    if d.get(k) != v:
                        ok = False
                        break
            if ok:
                results.append(dict(d))
        return results

    def find(self, query=None):
        query = query or {}
        items = self._match(query)

        async def _gen():
            for it in items:
                yield it

        return _gen()

    async def update_one(self, query, update):
        doc = await self.find_one(query)
        class Res: pass
        res = Res()
        if not doc:
            res.matched_count = 0
            return res
        # apply $set
        for op, payload in update.items():
            if op == "$set":
                for k, v in payload.items():
                    doc[k] = v
        self._data[doc["_id"]] = doc
        res.matched_count = 1
        return res

    async def count_documents(self, query):
        return len(self._match(query))

    async def create_index(self, *args, **kwargs):
        return None


class FakeDB:
    def __init__(self):
        self.users = FakeCollection()
        self.service_providers = FakeCollection()
        self.bookings = FakeCollection()
        self.conversations = FakeCollection()
        self.ratings = FakeCollection()


@pytest.fixture(autouse=True)
def patch_db(monkeypatch):
    import backend.db as _db
    fake = FakeDB()
    monkeypatch.setattr(_db, "db", fake)
    return fake


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac
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


@pytest_asyncio.fixture(scope="session")
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


@pytest_asyncio.fixture
async def async_client():
    """Create an async test client."""
    from httpx import AsyncClient
    from backend.main import app

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
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