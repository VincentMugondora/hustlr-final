"""
Database connection and setup for Hustlr backend.
Uses Motor for async MongoDB operations.

Collections:
- users: Stores customer, provider, and admin user accounts
- service_providers: Stores service provider profiles and verification status
- bookings: Stores service booking requests and their status
- conversations: Stores WhatsApp conversation logs for AI processing
- ratings: Stores customer ratings and feedback for providers
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

# MongoDB connection settings with secure environment variable handling
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "hustlr"

# Global client and database instances
client: AsyncIOMotorClient = None
db = None


async def connect_to_mongo():
    """Connect to MongoDB and initialize the database."""
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    print(f"Connected to MongoDB: {DB_NAME}")


async def close_mongo_connection():
    """Close the MongoDB connection."""
    global client
    if client:
        client.close()
        print("MongoDB connection closed")


async def create_indexes():
    """Create necessary indexes for performance optimization."""
    # Index for service providers search by service type and location
    # Used when customers search for providers (e.g., "plumber in downtown")
    await db.service_providers.create_index([
        ("service_type", ASCENDING),
        ("location", ASCENDING)
    ])

    # Index for bookings by customer_id
    # Used to quickly find all bookings for a specific customer
    await db.bookings.create_index("customer_id")

    # Index for bookings by provider_id
    # Used to quickly find all bookings for a specific service provider
    await db.bookings.create_index("provider_id")

    # Index for conversations by user_id
    # Used to retrieve conversation history for AI context
    await db.conversations.create_index("user_id")

    # Index for ratings by provider_id
    # Used to quickly calculate average ratings for providers
    await db.ratings.create_index("provider_id")

    print("Database indexes created for optimal query performance")