"""
Booking routes for Hustlr.
Handles provider search, booking creation, management, and cancellation.
"""

import logging
from datetime import datetime, time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from backend.models import (
    Booking, BookingCreate, BookingStatus, BookingCancellationRequest, BookingResponse,
    ProviderSearchRequest, ProviderSearchResult, User
)
from backend.auth import get_current_user
from backend.db import db

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("/", response_model=Booking)
async def create_booking(
    booking: BookingCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new booking."""
    # Verify provider exists
    provider = await db.service_providers.find_one({"_id": booking.provider_id})
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    # Create booking document
    booking_doc = booking.dict()
    booking_doc["customer_id"] = current_user.id
    booking_doc["status"] = "pending"

    result = await db.bookings.insert_one(booking_doc)
    booking_doc["_id"] = str(result.inserted_id)

    return Booking(**booking_doc)


@router.get("/", response_model=List[Booking])
async def get_user_bookings(
    current_user: User = Depends(get_current_user)
):
    """Get bookings for the current user."""
    bookings = []
    if current_user.role == "customer":
        query = {"customer_id": current_user.id}
    elif current_user.role == "provider":
        query = {"provider_id": {"$in": await get_provider_ids_for_user(current_user.id)}}
    else:  # admin
        query = {}

    async for booking in db.bookings.find(query):
        booking["_id"] = str(booking["_id"])
        bookings.append(Booking(**booking))

    return bookings


@router.put("/{booking_id}/status")
async def update_booking_status(
    booking_id: str,
    status: str,
    current_user: User = Depends(get_current_user)
):
    """Update booking status (confirm, cancel, etc.)."""
    # Find booking
    booking = await db.bookings.find_one({"_id": booking_id})
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )

    # Check permissions
    if current_user.role == "customer" and booking["customer_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this booking"
        )
    elif current_user.role == "provider":
        provider_ids = await get_provider_ids_for_user(current_user.id)
        if booking["provider_id"] not in provider_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this booking"
            )

    # Update status
    valid_statuses = ["pending", "confirmed", "completed", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status"
        )

    await db.bookings.update_one(
        {"_id": booking_id},
        {"$set": {"status": status}}
    )

    return {"message": "Booking status updated"}


async def get_provider_ids_for_user(user_id: str) -> List[str]:
    """Get provider IDs for a user."""
    providers = []
    async for provider in db.service_providers.find({"user_id": user_id}):
        providers.append(str(provider["_id"]))
    return providers