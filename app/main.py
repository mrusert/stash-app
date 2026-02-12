"""
Stash - Ephemeral Agent RAM
Main application entry point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
import secrets
from datetime import datetime, timezone, timedelta
from app.core.config import get_settings
from app.core.auth import get_current_user, User
from app.core.logging import setup_logging, get_logger
from app.models.schemas import (
    StashRequest,
    StashResponse,
    RecallResponse,
    UpdateRequest,
    UpdateResponse,
)
from app.services.redis_service import redis_service
from app.services.user_db import user_db
from app.core.middleware import PayloadSizeMiddleware

logger = get_logger(__name__)

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
    setup_logging()
    logger.info("application starting", mode=settings.stash_mode)
    await user_db.connect()
    await redis_service.connect()
    logger.info("redis_connected")

    # Seed demo users in local mode
    if settings.stash_mode == "local":
        demo_keys = await user_db.seed_demo_users()
        if demo_keys:
            print("\n📦 Created demo users:")
            for tier, key in demo_keys.items():
                print(f"  {tier.upper()}: {key}")
            print("   (Save these keys - they won't be shown again!)\n")
    
    yield # Application runs here
    # shutdown
    logger.info("application_stopping")
    await user_db.disconnect()
    await redis_service.disconnect()

app = FastAPI(
    title="Stash",
    description="Working memory for AI developers and agents",
    version="0.2.0",
     lifespan=lifespan,
)

# Middleware
app.add_middleware(PayloadSizeMiddleware)

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
async def stash(request: StashRequest, user: User = Depends(get_current_user)):
    """
    Store a JSON block with automatic expiration.
    The data will be deleted after the TTL expires.
    Requires Auth -> user: User = Depends(get_current_user)
    """
    # Generate a simple ID (we'll improve this later)
    memory_id = secrets.token_urlsafe(6) # ~8 characters

    # Enfore tier-based TTL limits
    ttl = min(request.ttl, user.max_ttl_seconds)

    # Store in Redis
    await redis_service.stash(
        user_id=user.id,
        memory_id=memory_id,
        data=request.data,
        ttl_seconds=ttl
    )

    # Calculate expiration time
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.ttl) 

    return StashResponse(
        memory_id=memory_id,
        ttl = ttl,
        expires_at=expires_at,
    )

@app.get("/recall/{memory_id}", response_model=RecallResponse)
async def recall(memory_id: str, user: User = Depends(get_current_user)):
    """
    Retrieve a stored memory by ID.
    Returns 404 if the memory doesn't exist or has expired.
    Requires Auth -> user: User = Depends(get_current_user)
    """
    result = await redis_service.recall(user.id, memory_id)

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
async def update(memory_id: str, request: UpdateRequest, user: User = Depends(get_current_user)):
    """
    Update stored data, extend TTL, or both.
    Requires Auth -> user: User = Depends(get_current_user)
    """

    result = await redis_service.update(
        user_id=user.id,
        memory_id=memory_id,
        data=request.data,
        extra_time=request.extra_time,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Memory '{memory_id}' not found or expired"
        )
    
    # Enfore tier limits on extended TTL
    new_ttl = result["ttl_remaining"]
    if new_ttl > user.max_ttl_seconds:
        new_ttl = user.max_ttl_seconds
        await redis_service._client.expire(
            redis_service._make_key(user.id, memory_id),
            new_ttl
        )

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=result["ttl_remaining"])

    return UpdateResponse(
        memory_id=memory_id,
        data=result["data"],
        ttl_remaining=new_ttl,
        expires_at= expires_at,
    )

@app.delete("/stash/{memory_id}", status_code=204)
async def delete_stash(
    memory_id: str,
    user: User = Depends(get_current_user),
):
    """Delete a stash immediately."""
    deleted = await redis_service.delete(user.id, memory_id)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Memory '{memory_id}' not found or expired"
        )
    
    return None  # 204 No Content

@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""

    try:
        await redis_service._client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"
    
    try:
        async with user_db._db.execute("SELECT 1") as cursor:
            await cursor.fetchone()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "version": "0.1.0",
        "mode": settings.stash_mode,
        "checks": {
            "redis": redis_status,
            "user_db": db_status,
        }
    }