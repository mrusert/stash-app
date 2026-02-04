"""
Stash - Ephemeral Agent RAM
Main application entry point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import secrets
from datetime import datetime, timezone, timedelta
from app.core.config import get_settings
from app.models.schemas import (
    StashRequest,
    StashResponse,
    RecallResponse,
    UpdateRequest,
    UpdateResponse,
)
from app.services.redis_service import redis_service

# Create the FastAPI application instance
# This is the core object that handles all routing and middleware

# Get settings instance
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI application.

    Code before 'yield' runs at startup
    Code after 'yield' runs at shutdown
    """
    # startup
    await redis_service.connect()
    yield # Application runs here
    # shutdown
    await redis_service.disconnect()

app = FastAPI(
    title="Stash",
    description="Working memory for AI developers and agents",
    version="0.1.0",
     lifespan=lifespan,
)

# Temporary in-memory storage (we'll replace with Redis later)
# This is just for testing our endpoints work
_temp_storage: dict = {}

# Define a route using a "@decorator"
# The @app.get("/") decorator tells FastAPI:
# "When someone makes a GET request to /, call this function"
@app.get("/")
# Asynchronous (non-blocking) - handle other requests while waiting
async def root():
    """
    Health check endpoint.
    Returns a simple message to confirm the API is running
    """
    return {
        "status": "ok",
        "message": "Stash is running",
        "mode": settings.stash_mode,
    }

@app.post("/stash", response_model=StashResponse)
async def stash(request: StashRequest):
    """
    Store a JSON block with automatic expiration.

    The data will be deleted after the TTL expires.
    """
    # Generate a simple ID (we'll improve this later)
    memory_id = secrets.token_urlsafe(6) # ~8 characters

    # TODO: Get user_id from authentication (Module 5)
    # For now, user is a placeholder
    user_id = "anonymous"

    # Store in Redis
    await redis_service.stash(
        user_id=user_id,
        memory_id=memory_id,
        data=request.data,
        ttl_seconds=request.ttl
    )

    # Calculate expiration time
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.ttl) 

    return StashResponse(
        memory_id=memory_id,
        ttl = request.ttl,
        expires_at=expires_at,
    )

@app.get("/recall/{memory_id}", response_model=RecallResponse)
async def recall(memory_id: str):
    """
    Retrieve a stored memory by ID.
    Returns 404 if the memory doesn't exist or has expired.
    """
    # TODO: From auth
    user_id = "anonymous"

    result = await redis_service.recall(user_id, memory_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Memory '{memory_id}' not found or expired."
        )

    return RecallResponse(
        memory_id=memory_id,
        data=result["data"],
        ttl_remaining=result["ttl_remaining"]
    )

@app.patch("/update/{memory_id}", response_model=UpdateResponse)
async def update(memory_id: str, request: UpdateRequest):
    """
    Update stored data, extend TTL, or both.
    """
    # TODO: From auth
    user_id = "anonymous"

    result = await redis_service.update(
        user_id=user_id,
        memory_id=memory_id,
        data=request.data,
        extra_time=request.extra_time,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Memory '{memory_id}' not found or expired"
        )
    
    expires_at = datetime.now(timezone.utc) + + timedelta(seconds=result["ttl_remaining"])

    return UpdateResponse(
        memory_id=memory_id,
        data=result["data"],
        ttl_remaining=result["ttl_remaining"],
        expires_at= expires_at,
    )


@app.get("/health")
async def health_check():
    try:
        pong = await redis_service.client.ping()
        redis_status = "connected" if pong else "unreachable"
    except Exception:
        redis_status = "unreachable"

    return {
        "status": "healthy",
        "version": "0.1.0",
        "redis": redis_status,
        "mode": settings.stash_mode,
    }