# app/core/retrieval/retriever.py
#
# WHY THIS FILE EXISTS:
# Takes a question, embeds it, searches Pinecone, returns relevant chunks.
# This is the "R" in RAG — retrieval.
#
# FLOW:
# Question → embed → search Pinecone → get similar chunks → return with metadata

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.ingestion.embedder import EmbeddingService, PineconeService
from app.models.document import DocumentChunk


class RetrieverService:
    """
    Retrieves relevant chunks based on semantic similarity.
    
    Uses embeddings to find chunks most likely to answer a question.
    """

    def __init__(self, db: Session):
        self.embedding_service = EmbeddingService()
        self.pinecone_service = PineconeService()
        self.db = db

    def retrieve(
        self,
        query: str,
        user_id: int,
        document_ids: List[int] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: the user's question (e.g., "What's the termination date?")
            user_id: only retrieve from this user's documents (security)
            document_ids: optional filter (only search specific documents)
            top_k: how many chunks to return
        
        Returns:
            [
                {
                    "content": "The contract expires on December 31st, 2025",
                    "score": 0.95,
                    "page_number": 5,
                    "document_id": 1,
                    "filename": "contract.pdf",
                    "chunk_index": 12,
                },
                ...
            ]
        
        Example:
            retriever = RetrieverService(db)
            results = retriever.retrieve(
                query="When does contract end?",
                user_id=1,
                top_k=5,
            )
            # results[0] = {
            #     "content": "...",
            #     "score": 0.95,
            #     ...
            # }
        """

        # Step 1: Embed the question
        try:
            query_embedding = self.embedding_service.embed_text(query)
        except Exception as e:
            raise ValueError(f"Failed to embed query: {str(e)}")

        # Step 2: Search Pinecone for similar vectors
        try:
            pinecone_results = self.pinecone_service.search(
                query_embedding=query_embedding,
                top_k=top_k * 2,  # Get extra to filter by user/document
            )
        except Exception as e:
            raise ValueError(f"Failed to search Pinecone: {str(e)}")

        # Step 3: Enrich results with full chunk data from Postgres
        # Why fetch from Postgres?
        # Pinecone only returned the ID + score + metadata we stored.
        # Some fields (full content if truncated, etc.) might need DB fetch.
        enriched_results = []

        for pinecone_result in pinecone_results:
            metadata = pinecone_result["metadata"]
            chunk_id = metadata.get("chunk_id")
            document_id = metadata.get("document_id")

            # Security check: only return chunks from user's documents
            # Fetch the chunk and verify ownership
            chunk = self.db.query(DocumentChunk).filter(
                DocumentChunk.id == chunk_id,
                DocumentChunk.document.has(user_id=user_id),  # verify user owns doc
            ).first()

            if not chunk:
                continue  # Skip if user doesn't own this document

            # Optional: filter by specific document IDs
            if document_ids and document_id not in document_ids:
                continue

            # Build result with all available info
            enriched_results.append({
                "content": chunk.content,
                "score": pinecone_result["score"],
                "page_number": chunk.page_number,
                "document_id": chunk.document_id,
                "document": chunk.document,  # SQLAlchemy relationship
                "chunk_index": chunk.chunk_index,
                "filename": chunk.document.filename,
            })

            if len(enriched_results) >= top_k:
                break

        return enriched_results


class HybridRetriever:
    """
    Advanced retriever combining semantic + keyword search.
    (For Day 5, we'll add BM25 keyword search)
    
    For now, just semantic search is fine.
    """
    pass
