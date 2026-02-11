"""
WhatsApp webhook routes for Hustlr.
Handles incoming messages from WhatsApp service and processes them.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from backend.db import db
from backend.models import Conversation
from bedrock.agent import invoke_agent
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


class WhatsAppMessage(BaseModel):
    """Incoming WhatsApp message payload."""
    sender: str
    message: str
    messageId: str
    timestamp: str
    source: str = "whatsapp"


class WhatsAppResponse(BaseModel):
    """Response to WhatsApp service."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


@router.post("/webhook", response_model=WhatsAppResponse)
async def whatsapp_webhook(
    message: WhatsAppMessage,
    background_tasks: BackgroundTasks
):
    """
    Handle incoming WhatsApp messages.

    This endpoint receives messages from the WhatsApp service,
    processes them through the Bedrock agent, and queues responses.
    """
    try:
        logger.info(f"📨 Received WhatsApp message from {message.sender}: {message.message[:100]}...")

        # Validate message
        if not message.message or not message.message.strip():
            raise HTTPException(status_code=400, detail="Empty message")

        # Extract phone number from sender (remove @s.whatsapp.net)
        phone_number = message.sender.split('@')[0] if '@' in message.sender else message.sender

        # Create session ID from phone number
        session_id = f"whatsapp_{phone_number}"

        # Store conversation in database
        conversation = Conversation(
            user_id=phone_number,
            message=message.message,
            timestamp=message.timestamp
        )

        # Insert conversation (we'll update with response later)
        result = await db.conversations.insert_one(conversation.dict())
        conversation_id = str(result.inserted_id)

        # Process message in background to avoid timeout
        background_tasks.add_task(
            process_whatsapp_message,
            phone_number,
            message.message,
            session_id,
            conversation_id
        )

        logger.info(f"✅ WhatsApp message queued for processing: {conversation_id}")

        return WhatsAppResponse(
            success=True,
            message="Message received and queued for processing"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing WhatsApp webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def process_whatsapp_message(
    phone_number: str,
    user_message: str,
    session_id: str,
    conversation_id: str
):
    """
    Process WhatsApp message through Bedrock agent.

    This function runs in the background to handle AI processing
    and response generation without blocking the webhook response.
    """
    try:
        logger.info(f"🤖 Processing message for session: {session_id}")

        # Invoke Bedrock agent
        agent_response = await invoke_agent(user_message, session_id)

        # Prepare response message
        if agent_response.success:
            response_message = agent_response.response or "I received your message. How can I help you today?"

            # Log action group if triggered
            if agent_response.action_group:
                logger.info(f"🎯 Action triggered: {agent_response.action_group}")
                # Here you could trigger specific backend actions based on the action group
                # e.g., search_providers, create_booking, etc.

        else:
            response_message = "I'm sorry, I'm having trouble processing your request right now. Please try again later."
            logger.error(f"❌ Agent processing failed: {agent_response.error_message}")

        # Update conversation with response
        await db.conversations.update_one(
            {"_id": conversation_id},
            {"$set": {"response": response_message}}
        )

        # TODO: Send response back to WhatsApp
        # This would require implementing a callback to the WhatsApp service
        # or storing the response for the WhatsApp service to poll

        logger.info(f"✅ Message processed successfully for {phone_number}")

    except Exception as e:
        logger.error(f"❌ Error in background message processing: {e}")

        # Update conversation with error
        try:
            await db.conversations.update_one(
                {"_id": conversation_id},
                {"$set": {"response": "Sorry, an error occurred while processing your message."}}
            )
        except Exception as db_error:
            logger.error(f"❌ Failed to update conversation with error: {db_error}")


@router.get("/health")
async def whatsapp_health():
    """
    Health check for WhatsApp integration.
    """
    return {
        "status": "healthy",
        "service": "WhatsApp Integration",
        "message": "WhatsApp webhook is operational"
    }