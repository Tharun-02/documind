# app/services/rag_service.py
# Day 5: Orchestrate Retrieval + Generation

from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.core.retrieval.retriever import RetrieverService
from app.core.generation.llm_service import LLMService
import time


class RAGService:
    """
    Complete RAG (Retrieval-Augmented Generation) pipeline.
    
    Flow:
    1. User asks question
    2. Retrieve relevant chunks (via RetrieverService)
    3. Format chunks as context
    4. Pass to LLM with context
    5. LLM generates answer
    6. Return answer with sources
    """

    def __init__(self, db: Session):
        self.retriever = RetrieverService(db)
        self.llm = LLMService()
        self.db = db

    def answer_question(
        self,
        question: str,
        user_id: int,
        document_ids: List[int] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Generate answer to a question using RAG.
        
        Returns:
        {
            "question": "When does contract end?",
            "answer": "Based on the documents, it expires December 31st...",
            "retrieved_chunks": [...],
            "response_time_ms": 5234,
            "sources": [{"document_id": 1, "filename": "contract.pdf", ...}]
        }
        """

        start_time = time.time()

        # Step 1: Retrieve relevant chunks
        retrieved_chunks = self.retriever.retrieve(
            query=question,
            user_id=user_id,
            document_ids=document_ids,
            top_k=top_k,
        )

        if not retrieved_chunks:
            return {
                "question": question,
                "answer": "No relevant documents found for your question.",
                "retrieved_chunks": [],
                "response_time_ms": (time.time() - start_time) * 1000,
                "sources": [],
            }

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

        return {
            "question": question,
            "answer": answer,
            "retrieved_chunks": retrieved_chunks,
            "response_time_ms": elapsed_ms,
            "sources": sources,
            "chunk_count": len(retrieved_chunks),
        }

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
