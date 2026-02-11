"""
Admin routes for Hustlr.
Handles provider verification and admin operations.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from backend.models import ServiceProvider, User, ProviderVerificationRequest
from backend.auth import get_current_user
from backend.db import db

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/providers/pending", response_model=List[ServiceProvider])
async def get_pending_providers(
    current_user: User = Depends(get_current_user)
):
    """Get list of pending provider verifications."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    providers = []
    async for provider in db.service_providers.find({"is_verified": False}):
        provider["_id"] = str(provider["_id"])
        providers.append(ServiceProvider(**provider))

    return providers


@router.put("/providers/{provider_id}/verify")
async def verify_provider(
    provider_id: str,
    verification_request: ProviderVerificationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Verify or reject a service provider application.
    Updates verification status, notes, and timestamps.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        # Find the provider
        provider = await db.service_providers.find_one({"_id": provider_id})
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        # Check if already verified/rejected
        if provider.get("verification_status") in ["verified", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider has already been verified or rejected"
            )

        # Prepare update data
        update_data = {
            "is_verified": verification_request.verified,
            "verification_status": "verified" if verification_request.verified else "rejected",
            "verification_notes": verification_request.notes,
            "verified_at": datetime.utcnow(),
            "verified_by": current_user.id,
            "updated_at": datetime.utcnow()
        }

        # Update the provider
        result = await db.service_providers.update_one(
            {"_id": provider_id},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        action = "verified" if verification_request.verified else "rejected"
        logger.info(f"Provider {provider_id} {action} by admin {current_user.id}")

        return {
            "message": f"Provider {action} successfully",
            "provider_id": provider_id,
            "verification_status": update_data["verification_status"],
            "verified_at": update_data["verified_at"].isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying provider {provider_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify provider"
        )


@router.get("/stats")
async def get_system_stats(
    current_user: User = Depends(get_current_user)
):
    """Get system statistics."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    total_users = await db.users.count_documents({})
    total_providers = await db.service_providers.count_documents({"is_verified": True})
    pending_providers = await db.service_providers.count_documents({"is_verified": False})
    total_bookings = await db.bookings.count_documents({})

    return {
        "total_users": total_users,
        "total_providers": total_providers,
        "pending_providers": pending_providers,
        "total_bookings": total_bookings
    }