"""
User database service using SQLite.

Handles persistent storage of users and API keys.
For production, this would be replaced with PostgreSQL.
"""

import aiosqlite
import hashlib
import secrets
from typing import Optional
from pathlib import Path

from app.core.config import get_settings

# TODO: Add structured logging in Module 7, use print statements for now

class UserDB:
    """
    SQLite-based user and API key storage.

    Tables:
    - users: id, tier, created_at
    - api_key: key_hash, user_id, created_at, last_used_at
    """

    def __init__(self):
        self._settings = get_settings()
        self._db_path = getattr(self._settings, 'users_b_path', "users.db")
        self._db: Optional[aiosqlite.Connection] = None
    
    @staticmethod
    def hash_key(api_key: str) -> str:
        """
        Hash an API key for secure storage.

        We use SHA-256 - fast enough for lookups, secure enough for API keys.
        In production, you might use bcrypt for user passwords, but for 
        API keys that are already high-entropy, SHA-256 is fine.
        """

        return hashlib.sha256(api_key.encode()).hexdigest()

    async def connect(self) -> None:
        """
        Initialize the database and create tables.
        """
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row

        # Create users table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                tier TEXT NOT NULL DEFAULT 'free',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create api_keys table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_used_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Create index for faster lookups
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_user 
            ON api_keys(user_id)
        """)

        await self._db.commit()
        print(f"✓ Connected to user database: {self._db_path}")
    
    async def disconnect(self) -> None:
        """
        Close the db connection.
        """

        if self._db:
            await self._db.close()
            print("✓ Disconnected from user database")
        
    async def get_user_by_api_key(self, api_key: str) -> Optional[dict]:
        """
        Look up user by their API key.

        Returns dict with user info, or None if key is invalid.
        """

        key_hash = self.hash_key(api_key)

        async with self._db.execute("""
            SELECT u.id, u.tier, ak.name as key_name
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.id
            WHERE ak.key_hash = ?
        """, (key_hash,)) as cursor:
            row = await cursor.fetchone()
        
        if row is None:
            return None
        
        # Update last_used_at
        await self._db.execute("""
            UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP
            WHERE key_hash = ?
        """, (key_hash,))
        await self._db.commit()
        
        return {
            "id": row["id"],
            "tier": row["tier"],
            "key_name": row["key_name"],
        }
    
    async def create_user(self, user_id: str, tier: str = "free") -> bool:
        """
        Create a new user.
        """
        try:
            await self._db.execute(
                "INSERT INTO users (id, tier) VALUES (?,?)",
                (user_id, tier)
            )
            await self._db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False # user already exists
    
    async def create_api_key(self, user_id: str, name: Optional[str] = None) -> Optional[str]:
        """
        Create a new API key for a user.

        Returns the plaintext key (only time it's available) or None if user doesn't exist.
        """

        # Verify user exists
        async with self._db.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            if await cursor.fetchone() is None:
                return None

        # Generate a secure API key
        # Format: sk_{random} for readability
        api_key = f"sk_{secrets.token_urlsafe(24)}"
        key_hash = self.hash_key(api_key)

        await self._db.execute(
            "INSERT INTO api_keys (key_hash, user_id, name) VALUES (?,?,?)", (key_hash, user_id, name)
        )
        await self._db.commit()

        # Return plaintext key - user must save this!
        return api_key
    
    async def seed_demo_users(self) -> dict:
        """
        Create demo users and API keys for development.

        Return dict of tier -> api_key for testing
        """

        demo_keys = {}
        
        demo_users = [
            ("user_free_001", "free"),
            ("user_pro_001", "pro"),
            ("user_ent_001", "enterprise"),
        ]

        for user_id, tier in demo_users:
            # Create user (ignore if exists)
            await self.create_user(user_id, tier)
            
            # Check if demo key already exists
            async with self._db.execute(
                "SELECT key_hash FROM api_keys WHERE user_id = ? AND name = ?",
                (user_id, f"demo_{tier}")
            ) as cursor:
                if await cursor.fetchone() is None:
                    # Create new demo key
                    api_key = await self.create_api_key(user_id, f"demo_{tier}")
                    demo_keys[tier] = api_key
                    print(f"  {tier.upper()}: {api_key}")
        
        return demo_keys

# Singleton Instance
user_db = UserDB()