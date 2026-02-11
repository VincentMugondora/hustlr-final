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


@router.put("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: str,
    cancellation_request: BookingCancellationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Cancel or reschedule a booking.
    Customers can cancel their own bookings or request rescheduling.
    """
    try:
        # Find booking
        booking = await db.bookings.find_one({"_id": booking_id})
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )

        # Ensure only the customer who made the booking can cancel it
        if current_user.role != "customer" or booking["customer_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to cancel this booking"
            )

        # Check if booking can be cancelled (not already completed or cancelled)
        if booking["status"] in [BookingStatus.COMPLETED, BookingStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel a completed or already cancelled booking"
            )

        update_data = {
            "updated_at": datetime.utcnow()
        }

        if cancellation_request.new_date:
            # Rescheduling logic
            try:
                new_booking_date = datetime.strptime(cancellation_request.new_date, "%Y-%m-%d").date()
                if cancellation_request.new_time:
                    new_booking_time = datetime.strptime(cancellation_request.new_time, "%H:%M").time()
                else:
                    # Keep existing time if not specified
                    new_booking_time = datetime.strptime(booking["time"], "%H:%M").time()

                # Check if new date/time is in the future
                new_datetime = datetime.combine(new_booking_date, new_booking_time)
                if new_datetime <= datetime.now():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="New booking date/time must be in the future"
                    )

                # Check for conflicts at new date/time
                existing_booking = await db.bookings.find_one({
                    "provider_id": booking["provider_id"],
                    "date": cancellation_request.new_date,
                    "time": cancellation_request.new_time or booking["time"],
                    "status": {"$in": [BookingStatus.PENDING, BookingStatus.CONFIRMED]},
                    "_id": {"$ne": booking_id}  # Exclude current booking
                })
                if existing_booking:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Provider is not available at the new date and time"
                    )

                # Update booking with new date/time
                update_data["date"] = cancellation_request.new_date
                if cancellation_request.new_time:
                    update_data["time"] = cancellation_request.new_time
                update_data["status"] = BookingStatus.PENDING  # Reset to pending for rescheduled booking

                logger.info(f"Rescheduled booking {booking_id} to {cancellation_request.new_date} {cancellation_request.new_time or booking['time']}")

            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date or time format for rescheduling"
                )
        else:
            # Cancellation logic
            update_data["status"] = BookingStatus.CANCELLED
            logger.info(f"Cancelled booking {booking_id}")

        # Add cancellation reason if provided
        if cancellation_request.reason:
            update_data["cancellation_reason"] = cancellation_request.reason

        # Update the booking
        await db.bookings.update_one(
            {"_id": booking_id},
            {"$set": update_data}
        )

        # Get updated booking
        updated_booking = await db.bookings.find_one({"_id": booking_id})
        updated_booking["_id"] = str(updated_booking["_id"])

        return BookingResponse(**updated_booking)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling/rescheduling booking: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel or reschedule booking"
        )


async def get_provider_ids_for_user(user_id: str) -> List[str]:
    """Get provider IDs for a user."""
    providers = []
    async for provider in db.service_providers.find({"user_id": user_id}):
        providers.append(str(provider["_id"]))
    return providers