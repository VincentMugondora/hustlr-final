"""
Admin routes for Hustlr.
Handles provider verification and admin operations.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from backend.models import ServiceProvider, User
from backend.auth import get_current_user
from backend.db import db

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
    verified: bool,
    current_user: User = Depends(get_current_user)
):
    """Verify or reject a service provider."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # Update verification status
    result = await db.service_providers.update_one(
        {"_id": provider_id},
        {"$set": {"is_verified": verified}}
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    return {"message": f"Provider {'verified' if verified else 'rejected'}"}


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