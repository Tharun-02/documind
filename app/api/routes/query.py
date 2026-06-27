# app/api/routes/query.py
#
# WHY THIS FILE EXISTS:
# The POST /query endpoint - where users ask questions about their documents.
# This is where Days 1-4 come together:
#   Day 1: Docker provides infrastructure
#   Day 2: JWT authenticates the user
#   Day 3: Chunks from parsed PDFs
#   Day 4: Retrieve relevant chunks via semantic search
#
# FLOW:
# User POST /query with question + JWT
#   ↓
# Verify JWT (get current_user)
#   ↓
# Embed question with OpenAI API
#   ↓
# Search Pinecone for similar chunks
#   ↓
# Enrich results with full text from Postgres
#   ↓
# Verify user owns these documents (security)
#   ↓
# Return chunks to user

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.dependencies import get_current_user
from app.schemas.query import QueryRequest, QueryResponse, RetrievedChunk
from app.core.ingestion.embedder import EmbeddingService, PineconeService
from app.core.retrieval.retriever import RetrieverService


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# QUERY ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
)
def query_documents(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Query documents semantically.
    
    The user asks a question about their uploaded documents.
    We retrieve relevant chunks based on semantic similarity (embeddings).
    
    Steps:
    1. Verify user has documents
    2. Embed the question
    3. Search Pinecone for similar chunks
    4. Verify user owns the returned documents
    5. Return chunks ranked by relevance
    
    Requires: valid JWT token
    
    Example:
        curl -X POST http://localhost:8000/query \\
          -H "Authorization: Bearer <token>" \\
          -H "Content-Type: application/json" \\
          -d '{
            "question": "When does the contract end?",
            "top_k": 5
          }'
    
    Response:
        {
            "question": "When does the contract end?",
            "retrieved_chunks": [
                {
                    "content": "The contract expires on December 31st...",
                    "similarity_score": 0.94,
                    "document_id": 1,
                    "filename": "contract.pdf",
                    "page_number": 2,
                    "chunk_index": 5
                },
                ...
            ],
            "total_chunks_retrieved": 5,
            "max_similarity_score": 0.94,
            "min_similarity_score": 0.82,
            "retrieval_time_ms": 234.5,
            "documents_searched": 3
        }
    """

    start_time = time.time()

    # ── STEP 1: VERIFY USER HAS DOCUMENTS ───────────────────────────────────

    # Check if user has any documents at all
    user_document_count = db.query(Document).filter(
        Document.user_id == current_user.id
    ).count()

    if user_document_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have no documents uploaded. Upload a PDF first.",
        )

    # If document_ids filter is specified, verify they exist and belong to user
    if request.document_ids:
        verified_doc_ids = []
        for doc_id in request.document_ids:
            doc = db.query(Document).filter(
                Document.id == doc_id,
                Document.user_id == current_user.id,
            ).first()

            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document {doc_id} not found or you don't own it",
                )

            verified_doc_ids.append(doc_id)

        document_ids_to_search = verified_doc_ids
    else:
        # Search all user's documents
        document_ids_to_search = [
            doc.id for doc in db.query(Document).filter(
                Document.user_id == current_user.id
            ).all()
        ]

    # ── STEP 2: EMBED THE QUESTION ──────────────────────────────────────────

    try:
        embedding_service = EmbeddingService()
        question_embedding = embedding_service.embed_text(request.question)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed question: {str(e)}",
        )

    # ── STEP 3: SEARCH PINECONE ─────────────────────────────────────────────

    try:
        pinecone_service = PineconeService()
        pinecone_results = pinecone_service.search(
            query_embedding=question_embedding,
            top_k=request.top_k * 2,  # Get extra to filter by user/document
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search documents: {str(e)}",
        )

    # ── STEP 4: ENRICH RESULTS + VERIFY OWNERSHIP ──────────────────────────

    retrieved_chunks = []

    for pinecone_result in pinecone_results:
        metadata = pinecone_result["metadata"]
        chunk_id = metadata.get("chunk_id")
        document_id = metadata.get("document_id")
        score = pinecone_result["score"]

        # CRITICAL: Verify user owns this document
        # (security - even if Pinecone is compromised, we filter at app level)
        chunk = db.query(DocumentChunk).filter(
            DocumentChunk.id == chunk_id,
        ).first()

        if not chunk:
            continue  # chunk was deleted

        # Verify document ownership
        if chunk.document_id not in document_ids_to_search:
            continue  # user doesn't own this document

        # Build result object
        retrieved_chunk = RetrievedChunk(
            content=chunk.content,
            similarity_score=score,
            document_id=chunk.document_id,
            filename=chunk.document.filename,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
        )

        retrieved_chunks.append(retrieved_chunk)

        # Stop when we have enough
        if len(retrieved_chunks) >= request.top_k:
            break

    # ── STEP 5: PREPARE RESPONSE ────────────────────────────────────────────

    elapsed_ms = (time.time() - start_time) * 1000

    # Calculate min/max scores
    if retrieved_chunks:
        scores = [chunk.similarity_score for chunk in retrieved_chunks]
        max_score = max(scores)
        min_score = min(scores)
    else:
        max_score = None
        min_score = None

    response = QueryResponse(
        question=request.question,
        retrieved_chunks=retrieved_chunks,
        total_chunks_retrieved=len(retrieved_chunks),
        max_similarity_score=max_score,
        min_similarity_score=min_score,
        retrieval_time_ms=elapsed_ms,
        documents_searched=len(document_ids_to_search),
    )

    return response


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK ENDPOINT (for debugging)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/status",
    tags=["System"],
)
def query_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check query system status for current user.
    
    Useful for debugging:
    - How many documents do I have?
    - How many chunks total?
    - When was my last query?
    """

    documents = db.query(Document).filter(
        Document.user_id == current_user.id
    ).all()

    total_chunks = sum(doc.chunk_count for doc in documents)

    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "documents_count": len(documents),
        "total_chunks": total_chunks,
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at,
            }
            for doc in documents
        ],
    }
