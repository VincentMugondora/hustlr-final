import pytest


def test_register_and_login(client):
    # Register a user
    user = {
        "email": "cust@example.com",
        "password": "strongpassword",
        "role": "customer",
        "name": "Test Customer"
    }

    resp = pytest.raises is None
    
    # Register via API
    import asyncio
    async def _run():
        r = await client.post("/auth/register", json=user)
        assert r.status_code == 201

        # Login
        lr = await client.post("/auth/login", data={"username": user["email"], "password": user["password"]})
        assert lr.status_code == 200
        body = lr.json()
        assert "access_token" in body

    asyncio.get_event_loop().run_until_complete(_run())
