# app/services/rag_service.py
# Day 5: Orchestrate Retrieval + Generation
# Day 7: Added Redis caching via RAGCacheService

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.core.retrieval.retriever import RetrieverService
from app.core.generation.llm_service import LLMService
from app.core.cache.cache_service import RAGCacheService
from app.config import settings
import time


class RAGService:
    """
    Complete RAG (Retrieval-Augmented Generation) pipeline.

    Flow:
    1. User asks question
    2. Check Redis cache (Day 7)
    3. If cache miss: Retrieve relevant chunks (via RetrieverService)
    4. Format chunks as context
    5. Pass to LLM with context
    6. LLM generates answer
    7. Cache result (Day 7)
    8. Return answer with sources
    """

    def __init__(self, db: Session, cache_service: RAGCacheService = None):
        """
        Initialize RAGService with optional cache.

        Args:
            db: SQLAlchemy session.
            cache_service: RAGCacheService instance. If None, caching is disabled.
        """
        self.retriever = RetrieverService(db)
        self.llm = LLMService()
        self.db = db
        self.cache = cache_service

    async def answer_question(
        self,
        question: str,
        user_id: int,
        document_ids: List[int] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Generate answer to a question using RAG.

        Day 7: Added Redis caching to skip expensive Pinecone + Groq calls
        on repeated queries.

        Returns:
        {
            "question": "When does contract end?",
            "answer": "Based on the documents, it expires December 31st...",
            "retrieved_chunks": [...],
            "response_time_ms": 5234,
            "sources": [{"document_id": 1, "filename": "contract.pdf", ...}],
            "from_cache": False  # Day 7: indicates if result was cached
        }
        """
        # Day 7: Check cache first
        if self.cache:
            cached_result = await self.cache.get_result(
                user_id=user_id,
                question=question,
                document_ids=document_ids,
                top_k=top_k,
            )
            if cached_result:
                cached_result["from_cache"] = True
                return cached_result

        start_time = time.time()

        # Step 1: Retrieve relevant chunks
        retrieved_chunks = self.retriever.retrieve(
            query=question,
            user_id=user_id,
            document_ids=document_ids,
            top_k=top_k,
        )

        if not retrieved_chunks:
            result = {
                "question": question,
                "answer": "No relevant documents found for your question.",
                "retrieved_chunks": [],
                "response_time_ms": (time.time() - start_time) * 1000,
                "sources": [],
                "from_cache": False,
            }
            # Day 7: Cache empty results too (shorter TTL)
            if self.cache:
                await self.cache.set_result(result, user_id, question, document_ids, top_k, ttl=300)
            return result

        # Step 2: Generate answer using LLM
        try:
            answer = self.llm.generate_answer(
                question=question,
                retrieved_chunks=retrieved_chunks,
                stream=False,
            )
        except Exception as e:
            answer = f"Error generating answer: {str(e)}"

        # Step 3: Extract unique sources
        sources = self._extract_sources(retrieved_chunks)

        elapsed_ms = (time.time() - start_time) * 1000

        result = {
            "question": question,
            "answer": answer,
            "retrieved_chunks": retrieved_chunks,
            "response_time_ms": elapsed_ms,
            "sources": sources,
            "chunk_count": len(retrieved_chunks),
            "from_cache": False,
        }

        # Day 7: Cache the result
        if self.cache:
            await self.cache.set_result(result, user_id, question, document_ids, top_k)

        return result

    def answer_question_streaming(
        self,
        question: str,
        user_id: int,
        document_ids: List[int] = None,
        top_k: int = 5,
    ):
        """
        Stream answer tokens as they arrive from LLM.
        Better for real-time UX.
        
        Yields: {"token": "text", "retrieved_chunks": [...]}
        """

        # Step 1: Retrieve chunks
        retrieved_chunks = self.retriever.retrieve(
            query=question,
            user_id=user_id,
            document_ids=document_ids,
            top_k=top_k,
        )

        # Yield retrieved chunks first
        yield {
            "type": "chunks",
            "retrieved_chunks": retrieved_chunks,
        }

        if not retrieved_chunks:
            yield {
                "type": "answer",
                "token": "No relevant documents found.",
            }
            return

        # Step 2: Stream answer generation
        try:
            token_generator = self.llm.generate_answer(
                question=question,
                retrieved_chunks=retrieved_chunks,
                stream=True,
            )

            for token in token_generator:
                yield {
                    "type": "token",
                    "token": token,
                }

        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
            }

    def _extract_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Extract unique sources from retrieved chunks."""
        sources = {}

        for chunk in chunks:
            doc_id = chunk.get('document_id')
            if doc_id not in sources:
                sources[doc_id] = {
                    "document_id": doc_id,
                    "filename": chunk.get('filename'),
                    "page_number": chunk.get('page_number'),
                    "relevance": chunk.get('similarity_score'),
                }

        return list(sources.values())
