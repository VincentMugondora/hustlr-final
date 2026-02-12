"""
Integration tests for WhatsApp webhook route with mocked Bedrock agent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bedrock.agent import AgentResponse


@pytest.mark.asyncio
async def test_whatsapp_webhook_success(async_client, fake_db, monkeypatch):
    invoke_mock = AsyncMock(
        return_value=AgentResponse(success=True, response="Hello from agent", session_id="s1")
    )
    monkeypatch.setattr("backend.routes.whatsapp.invoke_agent", invoke_mock)

    payload = {
        "sender": "+15551110001@s.whatsapp.net",
        "message": "Need a plumber",
        "messageId": "msg-001",
        "timestamp": "2026-02-12T10:00:00Z",
        "source": "whatsapp",
    }

    response = await async_client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert body["reply_text"] == "Hello from agent"
    assert body["deduplicated"] is False
    assert body["conversation_id"]

    stored = await fake_db.conversations.find_one({"message_id": "msg-001"})
    assert stored is not None
    assert stored["source"] == "whatsapp"
    assert stored["response"] == "Hello from agent"
    assert stored["processing_status"] == "completed"
    invoke_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_whatsapp_webhook_parses_json_agent_message(async_client, monkeypatch):
    invoke_mock = AsyncMock(
        return_value=AgentResponse(
            success=True,
            response='{"message":"Found three providers near you."}',
            session_id="s2",
        )
    )
    monkeypatch.setattr("backend.routes.whatsapp.invoke_agent", invoke_mock)

    response = await async_client.post(
        "/api/v1/whatsapp/webhook",
        json={
            "sender": "+15551110002@s.whatsapp.net",
            "message": "Find electricians",
            "messageId": "msg-002",
            "timestamp": "2026-02-12T10:01:00Z",
            "source": "whatsapp",
        },
    )
    assert response.status_code == 200
    assert response.json()["reply_text"] == "Found three providers near you."


@pytest.mark.asyncio
async def test_whatsapp_webhook_deduplicates_by_message_id(async_client, fake_db, monkeypatch):
    await fake_db.conversations.insert_one(
        {
            "_id": "conv-existing",
            "user_id": "+15551110003",
            "message": "Original",
            "response": "Cached reply",
            "message_id": "msg-dup-1",
            "source": "whatsapp",
        }
    )

    invoke_mock = AsyncMock(
        return_value=AgentResponse(success=True, response="Should not be called", session_id="s3")
    )
    monkeypatch.setattr("backend.routes.whatsapp.invoke_agent", invoke_mock)

    response = await async_client.post(
        "/api/v1/whatsapp/webhook",
        json={
            "sender": "+15551110003@s.whatsapp.net",
            "message": "Retry delivery",
            "messageId": "msg-dup-1",
            "timestamp": "2026-02-12T10:02:00Z",
            "source": "whatsapp",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["deduplicated"] is True
    assert body["reply_text"] == "Cached reply"
    invoke_mock.assert_not_awaited()

    all_docs = fake_db.conversations.docs
    assert len([d for d in all_docs if d.get("message_id") == "msg-dup-1"]) == 1


@pytest.mark.asyncio
async def test_whatsapp_webhook_agent_exception_returns_fallback(async_client, fake_db, monkeypatch):
    invoke_mock = AsyncMock(side_effect=RuntimeError("Bedrock down"))
    monkeypatch.setattr("backend.routes.whatsapp.invoke_agent", invoke_mock)

    response = await async_client.post(
        "/api/v1/whatsapp/webhook",
        json={
            "sender": "+15551110004@s.whatsapp.net",
            "message": "Book a service",
            "messageId": "msg-err-1",
            "timestamp": "2026-02-12T10:03:00Z",
            "source": "whatsapp",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "internal_error"
    assert "Sorry" in body["reply_text"]

    stored = await fake_db.conversations.find_one({"message_id": "msg-err-1"})
    assert stored is not None
    assert stored["processing_status"] == "failed"
    assert "processing_error" in stored


@pytest.mark.asyncio
async def test_whatsapp_webhook_rejects_empty_message(async_client, monkeypatch):
    invoke_mock = AsyncMock()
    monkeypatch.setattr("backend.routes.whatsapp.invoke_agent", invoke_mock)

    response = await async_client.post(
        "/api/v1/whatsapp/webhook",
        json={
            "sender": "+15551110005@s.whatsapp.net",
            "message": "   ",
            "messageId": "msg-empty-1",
            "timestamp": "2026-02-12T10:04:00Z",
            "source": "whatsapp",
        },
    )
    assert response.status_code == 400
    invoke_mock.assert_not_awaited()
