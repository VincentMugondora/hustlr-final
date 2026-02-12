"""
WhatsApp webhook routes for Hustlr.
Handles incoming messages from WhatsApp and returns Bedrock-generated replies.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db import db
from bedrock.agent import AgentResponse, invoke_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

DEFAULT_ERROR_REPLY = (
    "Sorry, I am having trouble processing your request right now. "
    "Please try again in a moment."
)


class WhatsAppMessage(BaseModel):
    """Incoming WhatsApp message payload."""

    sender: str
    message: str
    messageId: str
    timestamp: str
    source: str = "whatsapp"


class WhatsAppResponse(BaseModel):
    """Response consumed by the Baileys bridge."""

    success: bool
    message: Optional[str] = None
    reply_text: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    deduplicated: bool = False
    error: Optional[str] = None


def _extract_phone_number(sender: str) -> str:
    return sender.split("@")[0] if "@" in sender else sender


def _normalize_agent_reply(agent_response: AgentResponse) -> str:
    if not agent_response.success:
        return DEFAULT_ERROR_REPLY

    raw_text = (agent_response.response or "").strip()
    if not raw_text:
        return "I received your message. How can I help you today?"

    if raw_text.startswith("{"):
        try:
            payload = json.loads(raw_text)
            candidate = payload.get("message")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        except json.JSONDecodeError:
            logger.warning("Agent response looked like JSON but failed to parse")

    return raw_text


@router.post("/webhook", response_model=WhatsAppResponse)
async def whatsapp_webhook(message: WhatsAppMessage):
    """
    Process incoming WhatsApp message through Bedrock and return a reply payload.
    """
    conversation_id: Optional[str] = None

    try:
        if not message.message or not message.message.strip():
            raise HTTPException(status_code=400, detail="Empty message")

        phone_number = _extract_phone_number(message.sender)
        session_id = f"whatsapp_{phone_number}"

        logger.info(
            "Incoming WhatsApp message sender=%s message_id=%s",
            message.sender,
            message.messageId,
        )

        # Idempotency guard: if we have already processed this message ID,
        # return the previous reply and do not invoke the agent again.
        existing_conversation = await db.conversations.find_one(
            {"source": message.source, "message_id": message.messageId}
        )
        if existing_conversation:
            existing_reply = existing_conversation.get("response") or DEFAULT_ERROR_REPLY
            return WhatsAppResponse(
                success=True,
                message="Duplicate message already processed",
                reply_text=existing_reply,
                conversation_id=str(existing_conversation.get("_id")),
                message_id=message.messageId,
                deduplicated=True,
            )

        conversation_doc = {
            "user_id": phone_number,
            "message": message.message.strip(),
            "timestamp": message.timestamp,
        }
        conversation_doc["source"] = message.source
        conversation_doc["sender"] = message.sender
        conversation_doc["message_id"] = message.messageId
        conversation_doc["processing_status"] = "received"

        insert_result = await db.conversations.insert_one(conversation_doc)
        conversation_id = str(insert_result.inserted_id)

        agent_response = await invoke_agent(message.message.strip(), session_id)
        reply_text = _normalize_agent_reply(agent_response)

        await db.conversations.update_one(
            {"_id": conversation_id},
            {
                "$set": {
                    "response": reply_text,
                    "agent_success": agent_response.success,
                    "action_group": agent_response.action_group,
                    "agent_error": agent_response.error_message,
                    "processing_status": "completed",
                }
            },
        )

        return WhatsAppResponse(
            success=True,
            message="Message processed",
            reply_text=reply_text,
            conversation_id=conversation_id,
            message_id=message.messageId,
            deduplicated=False,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error processing WhatsApp webhook message_id=%s", message.messageId)

        if conversation_id:
            try:
                await db.conversations.update_one(
                    {"_id": conversation_id},
                    {
                        "$set": {
                            "response": DEFAULT_ERROR_REPLY,
                            "processing_error": str(exc),
                            "processing_status": "failed",
                        }
                    },
                )
            except Exception:
                logger.exception("Failed to update conversation with fallback error response")

        return WhatsAppResponse(
            success=False,
            message="Failed to process message",
            reply_text=DEFAULT_ERROR_REPLY,
            message_id=message.messageId,
            conversation_id=conversation_id,
            deduplicated=False,
            error="internal_error",
        )


@router.get("/health")
async def whatsapp_health():
    """Health check for WhatsApp integration."""
    return {
        "status": "healthy",
        "service": "WhatsApp Integration",
        "message": "WhatsApp webhook is operational",
    }
