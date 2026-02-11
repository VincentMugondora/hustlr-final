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


@router.post("/search_providers", response_model=List[ProviderSearchResult])
async def search_providers(
    search_request: ProviderSearchRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Search for verified service providers by service type, location, date, and time.
    Returns providers available at the specified date/time.
    """
    try:
        # Build base query for verified providers
        query = {
            "service_type": {"$regex": search_request.service_type, "$options": "i"},
            "location": {"$regex": search_request.location, "$options": "i"},
            "is_verified": True
        }

        # If date and time are specified, filter by availability
        if search_request.date and search_request.time:
            try:
                # Parse date and time
                booking_date = datetime.strptime(search_request.date, "%Y-%m-%d").date()
                booking_time = datetime.strptime(search_request.time, "%H:%M").time()

                # Check if the requested date/time falls within provider availability
                # This is a simplified check - in production, you'd want more sophisticated availability logic
                day_of_week = booking_date.strftime("%A").lower()

                # Add availability filter to query
                query[f"availability.{day_of_week}"] = {"$exists": True}

            except ValueError as e:
                logger.warning(f"Invalid date/time format: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time."
                )

        # Search for providers
        providers = []
        async for provider in db.service_providers.find(query).limit(search_request.max_results):
            provider["_id"] = str(provider["_id"])

            # Convert to ProviderSearchResult
            result = ProviderSearchResult(
                id=provider["_id"],
                user_id=provider["user_id"],
                service_type=provider["service_type"],
                location=provider["location"],
                description=provider.get("description"),
                hourly_rate=provider.get("hourly_rate"),
                rating=provider.get("rating", 0.0),
                total_ratings=provider.get("total_ratings", 0),
                availability=provider.get("availability"),
                is_verified=provider["is_verified"],
                created_at=provider["created_at"]
            )
            providers.append(result)

        logger.info(f"Found {len(providers)} providers for search: {search_request.service_type} in {search_request.location}")
        return providers

    except Exception as e:
        logger.error(f"Error searching providers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search providers"
        )


@router.post("/", response_model=BookingResponse)
async def create_booking(
    booking: BookingCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new booking with customer_id, provider_id, date, and time.
    Validates provider availability, checks for conflicts, and ensures user authorization.
    """
    # Ensure only customers can create bookings
    if current_user.role != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can create bookings"
        )

    try:
        # Verify provider exists and is verified
        provider = await db.service_providers.find_one({
            "_id": booking.provider_id,
            "is_verified": True
        })
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found or not verified"
            )

        # Validate date and time format
        try:
            booking_date = datetime.strptime(booking.date, "%Y-%m-%d").date()
            booking_time = datetime.strptime(booking.time, "%H:%M").time()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time."
            )

        # Check if booking is in the future
        booking_datetime = datetime.combine(booking_date, booking_time)
        if booking_datetime <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking must be scheduled for a future date and time"
            )

        # Check for booking conflicts (same provider, same date/time)
        existing_booking = await db.bookings.find_one({
            "provider_id": booking.provider_id,
            "date": booking.date,
            "time": booking.time,
            "status": {"$in": ["pending", "confirmed"]}
        })
        if existing_booking:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Provider is not available at this date and time"
            )

        # Create booking document
        booking_doc = booking.dict()
        booking_doc["customer_id"] = current_user.id
        booking_doc["status"] = BookingStatus.PENDING
        booking_doc["created_at"] = datetime.utcnow()
        booking_doc["updated_at"] = datetime.utcnow()

        result = await db.bookings.insert_one(booking_doc)
        booking_doc["_id"] = str(result.inserted_id)

        logger.info(f"Created booking {booking_doc['_id']} for customer {current_user.id} with provider {booking.provider_id}")

        return BookingResponse(**booking_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking"
        )


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