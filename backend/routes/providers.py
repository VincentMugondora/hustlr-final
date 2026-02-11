"""
Service provider routes for Hustlr.
Handles provider registration, search, and management.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from backend.models import ServiceProvider, ServiceProviderCreate, User
from backend.auth import get_current_user
from backend.db import db

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["Service Providers"])


@router.post("/register", response_model=ServiceProvider)
async def register_provider(
    provider: ServiceProviderCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Register a new service provider with comprehensive information.
    Includes business details, contact info, and optional verification documents.
    """
    try:
        # Check if user is authorized (customers and existing providers can register)
        if current_user.role not in ["customer", "provider"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to register as provider"
            )

        # Check if provider already exists for this user
        existing = await db.service_providers.find_one({"user_id": current_user.id})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider already registered for this user"
            )

        # Validate contact email format if provided
        if provider.contact_email and "@" not in provider.contact_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid contact email format"
            )

        # Validate business requirements for certain service types
        high_risk_services = ["electrician", "plumber", "carpenter", "hvac"]
        if provider.service_type.lower() in high_risk_services:
            if not provider.license_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"License number is required for {provider.service_type} services"
                )
            if not provider.insurance_info:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insurance information is required for {provider.service_type} services"
                )

        # Create provider document with enhanced fields
        provider_doc = provider.dict()
        provider_doc.update({
            "is_verified": False,
            "verification_status": "pending",
            "verification_notes": None,
            "verified_at": None,
            "verified_by": None,
            "rating": 0.0,
            "total_ratings": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        # Insert into database
        result = await db.service_providers.insert_one(provider_doc)
        provider_doc["_id"] = str(result.inserted_id)

        logger.info(f"Provider registered successfully: {provider_doc['_id']} for user {current_user.id}")

        return ServiceProvider(**provider_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register provider"
        )


@router.get("/search", response_model=List[ServiceProvider])
async def search_providers(
    service_type: str,
    location: str,
    current_user: User = Depends(get_current_user)
):
    """Search for service providers by type and location."""
    query = {
        "service_type": {"$regex": service_type, "$options": "i"},
        "location": {"$regex": location, "$options": "i"},
        "is_verified": True
    }

    providers = []
    async for provider in db.service_providers.find(query):
        provider["_id"] = str(provider["_id"])
        providers.append(ServiceProvider(**provider))

    return providers


@router.get("/me", response_model=ServiceProvider)
async def get_my_provider_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current user's provider profile.
    Returns provider details including verification status.
    """
    try:
        provider = await db.service_providers.find_one({"user_id": current_user.id})
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider profile not found. Please register as a provider first."
            )

        provider["_id"] = str(provider["_id"])
        return ServiceProvider(**provider)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider profile"
        )


@router.put("/me", response_model=ServiceProvider)
async def update_provider_profile(
    updates: ServiceProviderCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Update the current user's provider profile.
    Note: Verification status cannot be updated through this endpoint.
    """
    try:
        # Check if provider exists
        provider = await db.service_providers.find_one({"user_id": current_user.id})
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider profile not found. Please register as a provider first."
            )

        # Validate contact email format if provided
        if updates.contact_email and "@" not in updates.contact_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid contact email format"
            )

        # Prepare update data (exclude verification fields)
        update_data = updates.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        # Remove fields that shouldn't be updated by providers
        update_data.pop("user_id", None)  # Cannot change user association

        # Update the provider
        result = await db.service_providers.update_one(
            {"user_id": current_user.id},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider profile not found"
            )

        # Get updated provider
        updated_provider = await db.service_providers.find_one({"user_id": current_user.id})
        updated_provider["_id"] = str(updated_provider["_id"])

        logger.info(f"Provider profile updated for user {current_user.id}")

        return ServiceProvider(**updated_provider)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating provider profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update provider profile"
        )