"""
Stash - Ephemeral Agent RAM
Main application entry point
"""

from fastapi import FastAPI
import secrets
from datetime import datetime, timezone
from app.core.config import get_settings
from app.models.schemas import (
    StashRequest,
    StashResponse,
    RecallResponse,
    ExtendRequest,
    ExtendResponse
)

# Create the FastAPI application instance
# This is the core object that handles all routing and middleware

# Get settings instance
settings = get_settings()

app = FastAPI(
    title="Stash",
    description="Ephemeral key-value store for AI agents",
    version="0.1.0"
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

    # Generate a simple ID (we'll improve this later)
    expires_at = datetime.now(timezone.utc)

    # Store temporarily (replace with Redis later)
    _temp_storage[memory_id] = {
        "data": request.data,
        "ttl": request.ttl,
        "expires_at": expires_at,
    }

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
    if memory_id not in _temp_storage:
        raise HTTPException(
            status_code=404,
            detail=f"Memory '{memory_id}' not found or expired."
        )
    
    stored = _temp_storage[memory_id]

    return RecallResponse(
        memory_id=memory_id,
        data=stored["data"],
        ttl_remaining=stored["ttl"] # simplified for now
    )

@app.patch("/extend/{memory_id}", response_model=ExtendResponse)
async def extend(memory_id: str, request: ExtendRequest):
    """
    Extend the TTL of an existing memory
    """

    if memory_id not in _temp_storage:
        raise HTTPException(
            status_code=404,
            detail=f"Memory '{memory_id}' not found or expired"
        )
    
    stored = _temp_storage[memory_id]
    new_ttl = stored['ttl'] + request.extra_seconds
    stored['ttl'] = new_ttl

    return ExtendResponse(
        memory_id=memory_id,
        new_ttl=new_ttl,
        expires_at=datetime.now(),
    )


@app.get("/health")
async def health_check():
    """
    Detailed health check.
    In production, this would check Redis connectivity
    """
    return {
        "status": "healthy",
        "version": "0.1.0",
        "mode": "local"
    }