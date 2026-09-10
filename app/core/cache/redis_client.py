# app/core/cache/redis_client.py
#
# Redis client configuration for caching RAG queries.

import redis.asyncio as redis
from app.config import settings
from functools import lru_cache


@lru_cache
def get_redis_client() -> redis.Redis:
    """
    Get a Redis client instance.

    Uses lru_cache to ensure we only create one client per process,
    which is important for connection pooling.

    Returns:
        redis.Redis: A Redis client connected to the configured URL.
    """
    return redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


class CacheClient:
    """
    Redis client wrapper with async support.

    Provides a simple interface for caching operations:
    - get(key) -> value or None
    - set(key, value, ttl=3600) -> None
    - delete(key) -> None
    """

    def __init__(self, client: redis.Redis = None):
        """
        Initialize with optional Redis client.

        Args:
            client: Redis client instance. If None, creates new one.
        """
        self.client = client or get_redis_client()

    async def get(self, key: str) -> str | None:
        """
        Get a value from cache.

        Args:
            key: The cache key.

        Returns:
            The cached value, or None if not found.
        """
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """
        Set a value in cache with optional TTL.

        Args:
            key: The cache key.
            value: The value to cache.
            ttl: Time-to-live in seconds (default: 1 hour).
        """
        await self.client.setex(key, ttl, value)

    async def delete(self, key: str) -> None:
        """
        Delete a key from cache.

        Args:
            key: The cache key to delete.
        """
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.

        Args:
            key: The cache key.

        Returns:
            True if key exists, False otherwise.
        """
        return await self.client.exists(key) > 0
