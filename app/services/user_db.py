"""
User database service using PostgreSQL

Production-ready persistent storage for user and API keys
"""

import asyncpg
import hashlib
import secrets
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class UserDB:
    """
    PostgreSQL-based user and API key storage

    Tables:
    - users: id, tier, created_At
    - api_keys: id, key_hash, user_id, name, created_at, last_used_at
    """

    def __init__(self):
        self._settings = get_settings()
        self._pool: Optional[asyncpg.Pool] = None
    
    @staticmethod
    def hash_key(api_key: str) -> str:
        """Hash an API key for secure storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    async def connect(self) -> None:
        """Initialize the database connection pool and create tables"""
        self._pool = await asyncpg.create_pool(
            self._settings.database_url,
            min_size=2,
            max_size=10,
        )

        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    tier TEXT NOT NULL DEFAULT 'free',
                    api_key_hash TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    key_created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_api_key_hash 
                ON users(api_key_hash)
            """)
        
        logger.info("user_db_connected", database="postgresql")
    
    async def disconnect(self) -> None:
        """Close the database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("user_db_disconnected")
    
    async def get_user_by_api_key(self, api_key: str) -> Optional[dict]:
        """
        Look up a user by their API key.
        
        Returns dict with user info, or None if key is invalid.
        """
        key_hash = self.hash_key(api_key)
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, tier, created_at
                FROM users
                WHERE api_key_hash = $1
            """, key_hash)
            
            if row is None:
                logger.info("api_key_invalid", key_prefix=api_key[:10])
                return None
        
        logger.info("api_key_used", user_id=row["id"])
        
        return {
            "id": row["id"],
            "tier": row["tier"],
            "created_at": row["created_at"].isoformat(),
        }
    
    async def create_user(self, user_id: str, tier: str = "free") -> Optional[str]:
        """
        Create a new user with an API key.
        
        Returns the plaintext API key, or None if user already exists.
        """
        api_key = f"sk_{secrets.token_urlsafe(24)}"
        key_hash = self.hash_key(api_key)
        
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO users (id, tier, api_key_hash)
                    VALUES ($1, $2, $3)
                """, user_id, tier, key_hash)
            
            logger.info("user_created", user_id=user_id, tier=tier)
            return api_key
            
        except asyncpg.UniqueViolationError:
            logger.info("user_exists", user_id=user_id)
            return None
    

    async def get_user(self, user_id: str) -> Optional[dict]:
        """Get user by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, tier, created_at, key_created_at
                FROM users
                WHERE id = $1
            """, user_id)
        
        if row is None:
            return None
        
        return {
            "id": row["id"],
            "tier": row["tier"],
            "created_at": row["created_at"].isoformat(),
            "key_created_at": row["key_created_at"].isoformat(),
        }
    
    async def regenerate_api_key(self, user_id: str) -> Optional[str]:
        """
        Generate a new API key for an existing user.
        
        The old key immediately stops working.
        Returns the new plaintext key, or None if user doesn't exist.
        """
        api_key = f"sk_{secrets.token_urlsafe(24)}"
        key_hash = self.hash_key(api_key)
        
        async with self._pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE users 
                SET api_key_hash = $1, key_created_at = NOW()
                WHERE id = $2
            """, key_hash, user_id)
        
        # Check if any row was updated
        if result.split()[-1] == "0":
            return None
        
        logger.info("api_key_regenerated", user_id=user_id)
        return api_key
    
    async def seed_demo_users(self) -> dict:
        """
        Create demo users for development.
        
        Returns dict of tier -> api_key for newly created users.
        """
        demo_keys = {}
        
        demo_users = [
            ("user_free_001", "free"),
            ("user_pro_001", "pro"),
            ("user_ent_001", "enterprise"),
        ]
        
        for user_id, tier in demo_users:
            api_key = await self.create_user(user_id, tier)
            if api_key:
                demo_keys[tier] = api_key
        
        return demo_keys


# Singleton instance
user_db = UserDB()