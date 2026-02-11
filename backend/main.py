"""
Main FastAPI application for Hustlr.
WhatsApp-based service marketplace backend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db import connect_to_mongo, close_mongo_connection, create_indexes
from backend.routes import auth, providers, bookings, admin

# Create FastAPI app
app = FastAPI(
    title="Hustlr API",
    description="Backend API for Hustlr - WhatsApp Service Marketplace",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(providers.router)
app.include_router(bookings.router)
app.include_router(admin.router)


@app.on_event("startup")
async def startup_event():
    """Initialize database connection and create indexes."""
    await connect_to_mongo()
    await create_indexes()


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection."""
    await close_mongo_connection()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Hustlr API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)