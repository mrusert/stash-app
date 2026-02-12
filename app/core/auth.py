"""
Authentication and authorization

Uses API key authentication with tiered access levels.
User data is stored in SQLite (local) and PostreSQL (production).
"""

from fastapi import HTTPException, Security, Request, Depends
from fastapi.security import APIKeyHeader
from typing import Optional
from pydantic import BaseModel
from enum import Enum

from app.services.user_db import user_db

class UserTier(str, Enum):
    """
    Service tiers with different limits.
    """
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class User(BaseModel):
    """
    Authenticated user with tier information.
    """
    id: str
    tier: UserTier

    @property
    def max_payload_bytes(self) -> int:
        """Maximum payload size for this tier."""
        limits = {
            UserTier.FREE: 1_048_576,        # 1 MB
            UserTier.PRO: 52_428_800,        # 50 MB
            UserTier.ENTERPRISE: 524_288_000, # 500 MB
        }
        return limits[self.tier]
    
    @property
    def max_ttl_seconds(self) -> int:
        """Maximum allowed TTL for this tier."""
        limits = {
            UserTier.FREE: 3600,        # 1 hour max
            UserTier.PRO: 86400,        # 24 hours max
            UserTier.ENTERPRISE: 604800, # 7 days max
        }
        return limits[self.tier]
    
    @property
    def max_stashes(self) -> int:
        limits = {
            UserTier.FREE: 100,
            UserTier.PRO: 1000,
            UserTier.ENTERPRISE: 10000,
        }
        return limits[self.tier]
    
    @property
    def rate_limit_per_minute(self) -> int:
        limits = {
            UserTier.FREE: 60,
            UserTier.PRO: 300,
            UserTier.ENTERPRISE: 1000,
        }
        return limits[self.tier]

# Define where to look for the API Key
api_key_header = APIKeyHeader(
    name="X-API-KEY",
    auto_error=False, # We'll handle missing keys ourselves
)

async def get_current_user(api_key: Optional[str] = Security(api_key_header),) -> User:
    """
    Dependency that extracts and validates the API key.
    """

    if api_key is None:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include 'X-API-Key' in header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Look up in database
    user_data = await user_db.get_user_by_api_key(api_key)

    if user_data is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return User(
        id=user_data["id"],
        tier=UserTier(user_data["tier"]),
    )