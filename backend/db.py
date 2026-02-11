"""
Database connection and setup for Hustlr backend.
Uses Motor for async MongoDB operations.
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

# MongoDB connection settings
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
    """Create necessary indexes for performance."""
    # Index for service providers search by service type and location
    await db.service_providers.create_index([
        ("service_type", ASCENDING),
        ("location", ASCENDING)
    ])
    # Index for bookings by customer and provider
    await db.bookings.create_index("customer_id")
    await db.bookings.create_index("provider_id")
    # Index for conversations by user
    await db.conversations.create_index("user_id")
    print("Database indexes created")