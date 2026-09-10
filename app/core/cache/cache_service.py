# app/core/cache/cache_service.py
#
# Cache service for RAG queries.
#
# Provides cache helpers that use hash-based keys to uniquely identify
# query results by their inputs (user_id, question, document_ids).

import hashlib
import json
from typing import Dict, Any, Optional

from app.core.cache.redis_client import CacheClient
from app.config import settings


class RAGCacheService:
    """
    Cache service for RAG query results.

    Cache key format: rag:query:{hash(user_id, question, document_ids, top_k)}
    This ensures:
    - Same query by same user → cache hit
    - Different user → cache miss (multi-tenant isolation)
    - Different question → cache miss
    - Different document_ids → cache miss
    - Different top_k → cache miss (though we could ignore this)
    """

    def __init__(self, cache_client: CacheClient = None):
        """
        Initialize with optional CacheClient.

        Args:
            cache_client: CacheClient instance. If None, creates new one.
        """
        self.client = cache_client or CacheClient()

    def _generate_cache_key(
        self,
        user_id: int,
        question: str,
        document_ids: Optional[list[int]] = None,
        top_k: int = 5,
    ) -> str:
        """
        Generate a unique cache key for the given query parameters.

        Args:
            user_id: The user's ID.
            question: The query question.
            document_ids: Optional list of document IDs to search.
            top_k: Number of chunks to retrieve.

        Returns:
            Cache key string: rag:query:{hash}
        """
        # Normalize document_ids to a stable string
        doc_ids_str = json.dumps(sorted(document_ids)) if document_ids else "all"
        params = f"{user_id}:{question}:{doc_ids_str}:{top_k}"
        hash_val = hashlib.sha256(params.encode()).hexdigest()[:16]
        return f"rag:query:{hash_val}"

    async def get_result(
        self,
        user_id: int,
        question: str,
        document_ids: Optional[list[int]] = None,
        top_k: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result for a query.

        Args:
            user_id: The user's ID.
            question: The query question.
            document_ids: Optional list of document IDs to search.
            top_k: Number of chunks to retrieve.

        Returns:
            Cached result dict, or None if not cached.
        """
        key = self._generate_cache_key(user_id, question, document_ids, top_k)
        cached = await self.client.get(key)
        if cached:
            return json.loads(cached)
        return None

    async def set_result(
        self,
        result: Dict[str, Any],
        user_id: int,
        question: str,
        document_ids: Optional[list[int]] = None,
        top_k: int = 5,
        ttl: int = None,  # Uses settings.CACHE_TTL_SECONDS if None
    ) -> None:
        """
        Cache a query result.

        Args:
            result: The result dict to cache.
            user_id: The user's ID.
            question: The query question.
            document_ids: Optional list of document IDs to search.
            top_k: Number of chunks to retrieve.
            ttl: Time-to-live in seconds (default: settings.CACHE_TTL_SECONDS).
        """
        key = self._generate_cache_key(user_id, question, document_ids, top_k)
        if ttl is None:
            ttl = settings.CACHE_TTL_SECONDS
        await self.client.set(key, json.dumps(result), ttl)

    async def delete_user_cache(self, user_id: int) -> int:
        """
        Delete all cached results for a user.

        Useful for cache invalidation when user uploads new documents.

        Args:
            user_id: The user's ID.

        Returns:
            Number of keys deleted.
        """
        # Pattern: rag:query:{hash} where hash starts with user_id
        pattern = f"rag:query:*{user_id}:*"
        # Note: In production, you might want to store user IDs in a Set
        # for O(1) deletion instead of pattern matching
        raise NotImplementedError(
            "Pattern-based deletion not implemented. "
            "Use delete_cache_for_document() instead."
        )

    async def delete_cache_for_document(
        self,
        user_id: int,
        document_id: int,
    ) -> int:
        """
        Delete cached results that include a specific document.

        When a document is updated or deleted, we should invalidate
        any cached results that might include chunks from it.

        Args:
            user_id: The user's ID.
            document_id: The document ID to invalidate.

        Returns:
            Number of keys deleted.
        """
        # Store cached query keys in a Redis Set for easy invalidation
        # This is a simplified approach - see note in delete_user_cache
        raise NotImplementedError(
            "Pattern-based deletion not implemented. "
            "Consider storing cached keys per document for invalidation."
        )
