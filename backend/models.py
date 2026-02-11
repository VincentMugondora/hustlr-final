"""
Pydantic models for Hustlr API.
Defines data structures for users, providers, bookings, etc.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    CUSTOMER = "customer"
    PROVIDER = "provider"
    ADMIN = "admin"


class UserBase(BaseModel):
    phone_number: str = Field(..., description="WhatsApp phone number")
    name: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    role: UserRole = UserRole.CUSTOMER


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Password for authentication")


class User(UserBase):
    id: str = Field(..., alias="_id")
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True


class ServiceProviderBase(BaseModel):
    user_id: str
    service_type: str = Field(..., description="Type of service (e.g., plumber, electrician)")
    location: str = Field(..., description="Service location")
    description: Optional[str] = None
    hourly_rate: Optional[float] = Field(None, gt=0)
    availability: Optional[dict] = None  # e.g., {"monday": "9-17", ...}


class ServiceProviderCreate(ServiceProviderBase):
    pass


class ServiceProvider(ServiceProviderBase):
    id: str = Field(..., alias="_id")
    is_verified: bool = False
    rating: float = 0.0
    total_ratings: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BookingBase(BaseModel):
    customer_id: str
    provider_id: str
    service_type: str
    date: str  # ISO date string
    time: str  # e.g., "14:00"
    duration_hours: float = Field(default=1.0, gt=0)
    notes: Optional[str] = None


class BookingCreate(BookingBase):
    pass


class Booking(BookingBase):
    id: str = Field(..., alias="_id")
    status: BookingStatus = BookingStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True


class ProviderSearchRequest(BaseModel):
    """Request model for searching service providers."""
    service_type: str = Field(..., min_length=1, max_length=50, description="Type of service needed")
    location: str = Field(..., min_length=1, max_length=100, description="Service location")
    date: Optional[str] = Field(None, description="Preferred date (YYYY-MM-DD)")
    time: Optional[str] = Field(None, description="Preferred time (HH:MM)")
    max_results: int = Field(default=10, ge=1, le=50, description="Maximum number of results")


class ProviderSearchResult(BaseModel):
    """Response model for provider search results."""
    id: str
    user_id: str
    service_type: str
    location: str
    description: Optional[str]
    hourly_rate: Optional[float]
    rating: float
    total_ratings: int
    availability: Optional[dict]
    is_verified: bool
    created_at: datetime


class BookingCancellationRequest(BaseModel):
    """Request model for booking cancellation/rescheduling."""
    reason: Optional[str] = Field(None, max_length=500, description="Reason for cancellation")
    new_date: Optional[str] = Field(None, description="New date for rescheduling (YYYY-MM-DD)")
    new_time: Optional[str] = Field(None, description="New time for rescheduling (HH:MM)")
    action: str = Field(..., pattern="^(cancel|reschedule)$", description="Action to perform")


class BookingResponse(BaseModel):
    """Response model for booking operations."""
    success: bool
    message: str
    booking_id: Optional[str] = None
    booking: Optional[Booking] = None


class RatingBase(BaseModel):
    booking_id: str
    customer_id: str
    provider_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class RatingCreate(RatingBase):
    pass


class Rating(RatingBase):
    id: str = Field(..., alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True


class ConversationBase(BaseModel):
    user_id: str
    message: str
    response: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationCreate(ConversationBase):
    pass


class Conversation(ConversationBase):
    id: str = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True


# Token models for authentication
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    phone_number: Optional[str] = None