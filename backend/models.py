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
    service_type: str = Field(..., min_length=2, max_length=50, description="Type of service (e.g., plumber, electrician)")
    location: str = Field(..., min_length=2, max_length=100, description="Service location")
    description: Optional[str] = Field(None, max_length=500, description="Detailed service description")
    hourly_rate: Optional[float] = Field(None, gt=0, le=1000, description="Hourly rate in local currency")
    availability: Optional[dict] = Field(None, description="Availability schedule (e.g., {'monday': '9-17', ...})")
    business_name: Optional[str] = Field(None, max_length=100, description="Business/legal name")
    contact_phone: Optional[str] = Field(None, pattern=r'^\+?[\d\s\-\(\)]+$', description="Contact phone number")
    contact_email: Optional[str] = Field(None, description="Contact email address")
    years_experience: Optional[int] = Field(None, ge=0, le=50, description="Years of experience")
    license_number: Optional[str] = Field(None, max_length=50, description="Professional license number")
    insurance_info: Optional[str] = Field(None, max_length=200, description="Insurance information")
    verification_documents: Optional[List[str]] = Field(None, description="URLs or paths to verification documents")


class ServiceProviderCreate(ServiceProviderBase):
    pass


class ServiceProvider(ServiceProviderBase):
    id: str = Field(..., alias="_id")
    is_verified: bool = False
    verification_status: str = Field(default="pending", description="Verification status: pending, verified, rejected")
    verification_notes: Optional[str] = Field(None, max_length=500, description="Admin notes on verification")
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    rating: float = Field(default=0.0, ge=0.0, le=5.0)
    total_ratings: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True


class ProviderVerificationRequest(BaseModel):
    """Request model for provider verification by admin."""
    verified: bool = Field(..., description="Whether to verify or reject the provider")
    notes: Optional[str] = Field(None, max_length=500, description="Verification notes or rejection reason")


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