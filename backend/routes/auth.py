"""
Authentication routes for Hustlr.
Handles user registration and login.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from backend.auth import create_access_token, get_password_hash, verify_password
from backend.models import UserCreate, Token
from backend.db import db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    """Register a new user."""
    # Check if user already exists
    existing_user = await db.users.find_one({"phone_number": user.phone_number})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )

    # Hash password
    hashed_password = get_password_hash(user.password)

    # Create user document
    user_doc = {
        "phone_number": user.phone_number,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "hashed_password": hashed_password,
        "is_active": True,
        "created_at": user.created_at if hasattr(user, 'created_at') else None
    }

    # Insert into database
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Create access token
    access_token = create_access_token(data={"sub": user.phone_number})

    return Token(access_token=access_token, token_type="bearer")


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return access token."""
    user = await db.users.find_one({"phone_number": form_data.username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user["phone_number"]})
    return Token(access_token=access_token, token_type="bearer")