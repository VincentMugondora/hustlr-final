"""
Main FastAPI application for Hustlr.
WhatsApp-based service marketplace backend with JWT authentication and MongoDB integration.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from backend.db import connect_to_mongo, close_mongo_connection, create_indexes
from backend.routes import auth, providers, bookings, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle application startup and shutdown events.
    Manages MongoDB connection lifecycle and index creation.
    """
    # Startup
    try:
        await connect_to_mongo()
        await create_indexes()
        print("✅ Hustlr API started successfully")
    except Exception as e:
        print(f"❌ Failed to start Hustlr API: {e}")
        raise

    yield

    # Shutdown
    try:
        await close_mongo_connection()
        print("✅ Hustlr API shut down gracefully")
    except Exception as e:
        print(f"❌ Error during shutdown: {e}")


# Create FastAPI app with lifespan management
app = FastAPI(
    title="Hustlr API",
    description="Backend API for Hustlr - WhatsApp Service Marketplace",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
)

# Security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])  # Configure for production

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(
    auth.router,
    prefix="/api/v1",
    tags=["Authentication"]
)
app.include_router(
    providers.router,
    prefix="/api/v1",
    tags=["Service Providers"]
)
app.include_router(
    bookings.router,
    prefix="/api/v1",
    tags=["Bookings"]
)
app.include_router(
    admin.router,
    prefix="/api/v1",
    tags=["Administration"]
)


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify API status.
    Returns service health information.
    """
    return {
        "status": "healthy",
        "service": "Hustlr API",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint providing API information.
    """
    return {
        "message": "Welcome to Hustlr API",
        "description": "WhatsApp-based service marketplace backend",
        "docs": "/docs",
        "health": "/health"
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    """
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "server_error"
        }
    )


if __name__ == "__main__":
    import uvicorn

    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("ENVIRONMENT", "development") == "development"

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )