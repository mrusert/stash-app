"""
Redis service for ephemeral storage.

This module handles all Redis operations with automatic TTL management.
It also provides a fallback to fakeredis for local development. 
"""

import json
import redis.asyncio as redis
from redis.asyncio import Redis
from typing import Any, Optional
from datetime import datetime, timezone
import fakeredis.aioredis

from app.core.config import get_settings

class RedisService:
    """
    Async Redis client wrapper with TTL-aware operations.
    
    Key format: user:{user_id}:{memory_id}
    This prevents namespace collisions between users.
    """

    def __init__(self):
        self._client: Optional[Redis] = None
        self._settings = get_settings()
    
    async def connect(self) -> None:
        """
        Initialize Redis Connection.

        Called once at application startup.
        """

        try:
            self._client = redis.from_url(
                self._settings.redis_url,
                encoding="utf-8",
                decode_responses=True, # Return strings, not bytes
            )

            # Test the connection
            await self._client.ping()
            print(f"✓ Connected to Redis at {self._settings.redis_url}")
        except redis.ConnectionError:
            print("✗ Redis not available, using fakeredis")
            # Fall back to fakeredis for local development
            self._client = fakeredis.aioredis.FakeRedis(
                encoding="utf-8",
                decode_responses=True,
            )
    
    async def disconnect(self) -> None:
        """
        Close Redis connection.
        """
        if self._client:
            await self._client.close()
    
    def _make_key(self, user_id: str, memory_id: str) -> str:
        """
        Create a namespace Redis Key.

        Format: user:{user_id}:{memory_id}
        This ensures User A can't access User B's data.
        """

        return f"user:{user_id}:{memory_id}"
    
    async def stash(self, user_id: str, memory_id: str, data: Any, ttl_seconds: int) -> bool:
        """
        Store data with automatic expiration.

        Uses Redis SETEX for atomic set-with-expiry.

        Args:
            user_id: The authenticated user's ID
            memory_id: Unique identifier for this memory
            data: Any JSON-serializable data
            ttl_seconds: Time until automatic deletion
            
        Returns:
            True if stored successfully
        """

        key = self._make_key(user_id, memory_id)

        # Serialize to JSON string
        value = json.dumps({
            "data": data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # SETEX: SET with Expiry - atomic operation
        await self._client.setex(key, ttl_seconds, value)
        return True
    
    async def recall(self, user_id: str, memory_id: str) -> Optional[dict]:
        """
        Retrieve stored data if it exists and hasn't expired.
        
        Args:
            user_id: The authenticated user's ID
            memory_id: The memory to retrieve
            
        Returns:
            Dict with 'data' and 'ttl_remaining', or None if not found
        """

        key = self._make_key(user_id, memory_id)

        # Get the value
        value = await self._client.get(key)
        if value is None:
            return None
        
        # Get remaining TTL
        ttl = await self._client.ttl(key)

        if ttl < 0: # -1 means no expiry, -2 means doesn't exist
            return None
        
        # Parse JSON
        parsed = json.loads(value)

        return {
            "data": parsed["data"],
            "ttl_remaining": ttl,
            "created_at": parsed.get("created_at"),
        }
    
    async def update(self, user_id: str, memory_id: str, data: Optional[Any] = None, extra_time: Optional[int] = None ) -> Optional[dict]:
        """
        Update stored data and/or extend TTL.
        
        Args:
            user_id: The authenticated user's ID
            memory_id: The memory to update
            data: If provided, replaces entire stored data
            extra_seconds: If provided, adds to remaining TTL
            
        Returns:
            Dict with 'ttl_remaining', or None if memory not found
        """

        key = self._make_key(user_id, memory_id)

        # Get Current Value
        value = await self._client.get(key)
        if value is None:
            return None
        
        # Get Current TTL
        current_ttl = await self._client.ttl(key)
        if current_ttl < 0:
            return None
        
        # Parse existing data
        parsed = json.loads(value)

        if data is not None:
            parsed["data"] = data
        
        # Calculate new TTL
        new_ttl = current_ttl
        if extra_time is not None:
            new_ttl = current_ttl + extra_time
        
        # Update the record
        parsed["updated_at"] = datetime.now(timezone.utc).isoformat()
        new_value = json.dumps(parsed)

        # Save with new TTL
        await self._client.setex(key, new_ttl, new_value)

        return {
            "data": parsed["data"],
            "ttl_remaining": new_ttl
        }

    async def delete(self, user_id: str, memory_id: str) -> bool:
        """Delete a memory immediately."""
        key = self._make_key(user_id, memory_id)
        result = await self._client.delete(key)
        return result > 0

# Singleton instance
redis_service = RedisService()