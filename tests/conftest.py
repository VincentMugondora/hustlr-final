"""
Pytest fixtures and async in-memory Mongo fakes for FastAPI endpoint tests.
"""

from __future__ import annotations

import copy
import re
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.auth import create_access_token, get_current_user
from backend.main import app
from backend.models import User


class FakeInsertResult:
    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, matched_count: int, modified_count: int):
        self.matched_count = matched_count
        self.modified_count = modified_count


class FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs
        self._idx = 0

    def limit(self, n: int) -> "FakeCursor":
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._docs):
            raise StopAsyncIteration
        value = self._docs[self._idx]
        self._idx += 1
        return copy.deepcopy(value)


class FakeCollection:
    def __init__(self):
        self.docs: list[dict] = []

    @staticmethod
    def _get_value(doc: dict, dotted_key: str):
        value = doc
        for part in dotted_key.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    def _matches(self, doc: dict, query: dict) -> bool:
        if not query:
            return True

        for key, expected in query.items():
            value = self._get_value(doc, key)

            if isinstance(expected, dict):
                if "$regex" in expected:
                    flags = re.IGNORECASE if expected.get("$options") == "i" else 0
                    if value is None or re.search(expected["$regex"], str(value), flags) is None:
                        return False
                    continue
                if "$in" in expected:
                    if value not in expected["$in"]:
                        return False
                    continue
                if "$ne" in expected:
                    if value == expected["$ne"]:
                        return False
                    continue
                if "$exists" in expected:
                    exists = self._get_value(doc, key) is not None
                    if bool(expected["$exists"]) != exists:
                        return False
                    continue

            if value != expected:
                return False

        return True

    async def find_one(self, query: dict):
        for doc in self.docs:
            if self._matches(doc, query):
                return copy.deepcopy(doc)
        return None

    def find(self, query: dict):
        matched = [copy.deepcopy(doc) for doc in self.docs if self._matches(doc, query)]
        return FakeCursor(matched)

    async def insert_one(self, doc: dict):
        stored = copy.deepcopy(doc)
        if "_id" not in stored:
            stored["_id"] = str(uuid4())
        self.docs.append(stored)
        return FakeInsertResult(stored["_id"])

    async def update_one(self, query: dict, update: dict):
        for idx, doc in enumerate(self.docs):
            if self._matches(doc, query):
                if "$set" in update:
                    self.docs[idx] = {**doc, **copy.deepcopy(update["$set"])}
                return FakeUpdateResult(matched_count=1, modified_count=1)
        return FakeUpdateResult(matched_count=0, modified_count=0)

    async def count_documents(self, query: dict):
        return sum(1 for doc in self.docs if self._matches(doc, query))

    async def create_index(self, *args, **kwargs):
        return "fake_index"


class FakeDB:
    def __init__(self):
        self.users = FakeCollection()
        self.service_providers = FakeCollection()
        self.bookings = FakeCollection()
        self.conversations = FakeCollection()
        self.ratings = FakeCollection()


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeDB()

    async def _noop_async():
        return None

    monkeypatch.setattr("backend.db.db", db)
    monkeypatch.setattr("backend.routes.auth.db", db)
    monkeypatch.setattr("backend.routes.providers.db", db)
    monkeypatch.setattr("backend.routes.bookings.db", db)
    monkeypatch.setattr("backend.routes.whatsapp.db", db)
    monkeypatch.setattr("backend.routes.admin.db", db)

    monkeypatch.setattr("backend.main.connect_to_mongo", _noop_async)
    monkeypatch.setattr("backend.main.create_indexes", _noop_async)
    monkeypatch.setattr("backend.main.close_mongo_connection", _noop_async)

    return db


@pytest_asyncio.fixture
async def async_client(fake_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def override_current_user():
    def _set(user: User):
        async def _dependency_override():
            return user

        app.dependency_overrides[get_current_user] = _dependency_override

    yield _set
    app.dependency_overrides.clear()


@pytest.fixture
def make_user():
    def _make_user(user_id: str, role: str, phone: str = "+15550000000") -> User:
        return User(
            _id=user_id,
            phone_number=phone,
            name=f"{role.title()} User",
            role=role,
            is_active=True,
            created_at=datetime.utcnow(),
        )

    return _make_user


@pytest.fixture
def auth_headers():
    def _make_headers(sub: str = "+15551111111") -> dict[str, str]:
        token = create_access_token({"sub": sub})
        return {"Authorization": f"Bearer {token}"}

    return _make_headers


@pytest_asyncio.fixture
async def seeded_provider(fake_db):
    provider = {
        "_id": "provider-1",
        "user_id": "provider-user-1",
        "service_type": "electrician",
        "location": "midtown",
        "description": "Licensed electrician",
        "hourly_rate": 80.0,
        "availability": {"monday": "09:00-17:00"},
        "is_verified": True,
        "verification_status": "verified",
        "rating": 4.5,
        "total_ratings": 2,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await fake_db.service_providers.insert_one(provider)
    return provider


@pytest_asyncio.fixture
async def seeded_completed_booking(fake_db, seeded_provider):
    booking = {
        "_id": "booking-completed-1",
        "customer_id": "customer-1",
        "provider_id": seeded_provider["_id"],
        "service_type": "electrician",
        "date": "2099-01-01",
        "time": "10:00",
        "duration_hours": 1.0,
        "status": "completed",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await fake_db.bookings.insert_one(booking)
    return booking
