"""
Service provider routes for Hustlr.
Handles provider registration, search, and management.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from backend.models import ServiceProvider, ServiceProviderCreate, User
from backend.auth import get_current_user
from backend.db import db

router = APIRouter(prefix="/providers", tags=["Service Providers"])


@router.post("/register", response_model=ServiceProvider)
async def register_provider(
    provider: ServiceProviderCreate,
    current_user: User = Depends(get_current_user)
):
    """Register a new service provider."""
    # Check if user is authorized (only customers can become providers?)
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

    # Create provider document
    provider_doc = provider.dict()
    provider_doc["is_verified"] = False
    provider_doc["rating"] = 0.0
    provider_doc["total_ratings"] = 0

    result = await db.service_providers.insert_one(provider_doc)
    provider_doc["_id"] = str(result.inserted_id)

    return ServiceProvider(**provider_doc)


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


@router.get("/{provider_id}", response_model=ServiceProvider)
async def get_provider(
    provider_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get details of a specific provider."""
    provider = await db.service_providers.find_one({"_id": provider_id})
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    provider["_id"] = str(provider["_id"])
    return ServiceProvider(**provider)