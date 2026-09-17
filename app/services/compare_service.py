# app/services/compare_service.py
#
# Day 8: Clause Comparison Service
# Compares clauses across two documents for similarity.
#
# Uses cross-document retrieval:
# - Embed all chunks from both documents
# - Compute pairwise similarities
# - Return clauses that match above threshold

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import time

from app.core.ingestion.embedder import EmbeddingService
from app.models.document import Document, DocumentChunk


class CompareService:
    """
    Compares clauses across two documents.
    """

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService()

    def compare_documents(
        self,
        document_id_1: int,
        document_id_2: int,
        user_id: int,
        threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Compare two documents for clause similarity.

        Args:
            document_id_1: First document to compare
            document_id_2: Second document to compare
            user_id: User making the request (for ownership verification)
            threshold: Similarity threshold (0-1)

        Returns:
            {
                "document_1_id": 1,
                "document_2_id": 2,
                "document_1_filename": "contract.pdf",
                "document_2_filename": "agreement.pdf",
                "total_comparisons": 250,
                "similar_clauses": [
                    {
                        "clause_1": "...",
                        "clause_2": "...",
                        "similarity_score": 0.92,
                        ...
                    },
                    ...
                ],
                "comparison_time_ms": 1234.5
            }

        Raises:
            HTTPException: If documents not found or user doesn't own them
        """
        start_time = time.time()

        # Verify both documents exist and belong to user
        doc_1 = self._get_verified_document(document_id_1, user_id)
        doc_2 = self._get_verified_document(document_id_2, user_id)

        # Get all chunks for both documents
        chunks_1 = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id_1
        ).all()
        chunks_2 = self.db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id_2
        ).all()

        if not chunks_1 or not chunks_2:
            return {
                "document_1_id": document_id_1,
                "document_2_id": document_id_2,
                "document_1_filename": doc_1.filename,
                "document_2_filename": doc_2.filename,
                "total_comparisons": 0,
                "similar_clauses": [],
                "comparison_time_ms": 0,
            }

        # Embed all chunks from both documents
        # ponytail: batch embedding would be faster but simple loop works
        embeddings_1 = []
        for chunk in chunks_1:
            try:
                embedding = self.embedding_service.embed_text(chunk.content)
                embeddings_1.append((chunk, embedding))
            except Exception:
                continue  # Skip chunks that fail to embed

        embeddings_2 = []
        for chunk in chunks_2:
            try:
                embedding = self.embedding_service.embed_text(chunk.content)
                embeddings_2.append((chunk, embedding))
            except Exception:
                continue

        # Compute pairwise similarities
        similar_clauses = []
        total_comparisons = len(embeddings_1) * len(embeddings_2)

        for chunk_1, emb_1 in embeddings_1:
            for chunk_2, emb_2 in embeddings_2:
                # cosine similarity
                similarity = self._cosine_similarity(emb_1, emb_2)

                if similarity >= threshold:
                    similar_clauses.append({
                        "clause_1": chunk_1.content,
                        "clause_2": chunk_2.content,
                        "similarity_score": round(similarity, 4),
                        "document_1_chunk_id": chunk_1.id,
                        "document_2_chunk_id": chunk_2.id,
                        "document_1_page": chunk_1.page_number,
                        "document_2_page": chunk_2.page_number,
                    })

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "document_1_id": document_id_1,
            "document_2_id": document_id_2,
            "document_1_filename": doc_1.filename,
            "document_2_filename": doc_2.filename,
            "total_comparisons": total_comparisons,
            "similar_clauses": similar_clauses,
            "comparison_time_ms": round(elapsed_ms, 2),
        }

    def _get_verified_document(self, document_id: int, user_id: int) -> Document:
        """Get document and verify user owns it."""
        doc = self.db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == user_id,
        ).first()

        if not doc:
            raise ValueError(f"Document {document_id} not found or access denied")

        return doc

    def _cosine_similarity(self, vec_1: List[float], vec_2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        # ponytail: use numpy if available, else simple computation
        dot_product = sum(a * b for a, b in zip(vec_1, vec_2))
        norm_1 = sum(a * a for a in vec_1) ** 0.5
        norm_2 = sum(b * b for b in vec_2) ** 0.5

        if norm_1 == 0 or norm_2 == 0:
            return 0.0

        return dot_product / (norm_1 * norm_2)
