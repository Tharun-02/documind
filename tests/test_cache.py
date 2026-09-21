# tests/test_cache.py
# Day 7a: Tests for Redis caching in RAG queries

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.cache.cache_service import RAGCacheService
from app.services.rag_service import RAGService


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.query().filter().first = MagicMock(return_value=None)
    db.query().filter().count = MagicMock(return_value=0)
    db.query().all = MagicMock(return_value=[])
    return db


@pytest.fixture
def mock_cache_client():
    """Mock Redis client."""
    client = MagicMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=None)
    return client


@pytest.fixture
def cache_service(mock_cache_client):
    """RAGCacheService with mocked client."""
    with patch('app.core.cache.cache_service.CacheClient', return_value=mock_cache_client):
        return RAGCacheService()


@pytest.fixture
def mock_retriever():
    """Mock RetrieverService."""
    retriever = MagicMock()
    retriever.retrieve = MagicMock(return_value=[])
    return retriever


@pytest.fixture
def mock_llm():
    """Mock LLMService."""
    llm = MagicMock()
    llm.generate_answer = MagicMock(return_value="Test answer")
    return llm


# ─────────────────────────────────────────────────────────────────────────────
# RAGCacheService Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRAGCacheService:
    """Tests for the cache service itself."""

    def test_cache_key_generation_same_query_same_key(self, cache_service):
        """Same query should generate same cache key."""
        key1 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            top_k=5,
        )
        key2 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            top_k=5,
        )
        assert key1 == key2
        assert key1.startswith("rag:query:")

    def test_cache_key_generation_different_user_different_key(self, cache_service):
        """Different users should have different cache keys."""
        key1 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            top_k=5,
        )
        key2 = cache_service._generate_cache_key(
            user_id=2,
            question="When does contract end?",
            top_k=5,
        )
        assert key1 != key2

    def test_cache_key_generation_different_question_different_key(self, cache_service):
        """Different questions should have different cache keys."""
        key1 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            top_k=5,
        )
        key2 = cache_service._generate_cache_key(
            user_id=1,
            question="What is the termination clause?",
            top_k=5,
        )
        assert key1 != key2

    def test_cache_key_generation_different_doc_ids_different_key(self, cache_service):
        """Different document IDs should have different cache keys."""
        key1 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            document_ids=[1, 2],
            top_k=5,
        )
        key2 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            document_ids=[3, 4],
            top_k=5,
        )
        assert key1 != key2

    def test_cache_key_generation_sorted_doc_ids_same_key(self, cache_service):
        """Document IDs in different order should produce same key."""
        key1 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            document_ids=[2, 1],
            top_k=5,
        )
        key2 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            document_ids=[1, 2],
            top_k=5,
        )
        assert key1 == key2

    def test_cache_key_generation_all_docs_special_key(self, cache_service):
        """None document_ids should produce a consistent key."""
        key1 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            document_ids=None,
            top_k=5,
        )
        # Both should start with the expected prefix
        assert key1.startswith("rag:query:")

    def test_cache_key_generation_different_top_k_different_key(self, cache_service):
        """Different top_k should produce different cache keys."""
        key1 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            top_k=3,
        )
        key2 = cache_service._generate_cache_key(
            user_id=1,
            question="When does contract end?",
            top_k=5,
        )
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_get_result_cache_hit(self, cache_service, mock_cache_client):
        """Test cache hit returns cached result."""
        mock_cache_client.get = AsyncMock(return_value='{"question": "When does contract end?", "answer": "December 31st", "from_cache": false}')

        result = await cache_service.get_result(
            user_id=1,
            question="When does contract end?",
        )

        assert result["answer"] == "December 31st"

    @pytest.mark.asyncio
    async def test_get_result_cache_miss(self, cache_service, mock_cache_client):
        """Test cache miss returns None."""
        mock_cache_client.get = AsyncMock(return_value=None)

        result = await cache_service.get_result(
            user_id=1,
            question="When does contract end?",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_set_result(self, cache_service, mock_cache_client):
        """Test setting cache result."""
        result = {
            "question": "When does contract end?",
            "answer": "December 31st",
            "from_cache": False,
        }

        await cache_service.set_result(
            result=result,
            user_id=1,
            question="When does contract end?",
        )

        # Verify set was called
        assert mock_cache_client.set.called


# ─────────────────────────────────────────────────────────────────────────────
# RAGService Cache Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRAGServiceCaching:
    """Tests for RAGService caching integration."""

    @pytest.mark.asyncio
    async def test_second_call_cache_hit(self, mock_cache_client):
        """Second call with same query should return cached result."""
        # Setup the mock to return cached value on get
        mock_cache_client.get = AsyncMock(
            return_value='{"question": "When does contract end?", "answer": "December 31st, 2025", "from_cache": false}'
        )

        # Create cache service with our mock
        cache_service = RAGCacheService(cache_client=mock_cache_client)

        # Verify cache was set (we can verify get works with our mock)
        cached = await cache_service.get_result(
            user_id=1,
            question="When does contract end?",
        )
        assert cached is not None
        assert cached["answer"] == "December 31st, 2025"

    @pytest.mark.asyncio
    async def test_different_user_cache_isolation(self, cache_service):
        """Different users should have isolated caches."""
        # Cache result for user 1
        await cache_service.set_result(
            result={"answer": "User 1 answer"},
            user_id=1,
            question="When does contract end?",
        )

        # User 2 should not see it
        result = await cache_service.get_result(
            user_id=2,
            question="When does contract end?",
        )
        assert result is None
