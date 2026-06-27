# app/schemas/query.py
#
# WHY THIS FILE EXISTS:
# Pydantic schemas for query-related API operations.
# Validates request bodies and shapes response data for HTTP.
#
# KEY DISTINCTION (like Day 3):
# Schema (this file) = HTTP request/response validation (Pydantic)
# Service (retriever.py) = business logic (no HTTP)
# Routes (query_routes.py) = HTTP endpoints (FastAPI)

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ═════════════════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS (what comes IN from the user)
# ═════════════════════════════════════════════════════════════════════════════

class QueryRequest(BaseModel):
    """
    Request body for POST /query
    User asks a question, optionally filters by specific documents.
    """

    question: str = Field(
        ...,  # ... means required
        min_length=3,
        max_length=1000,
        description="The question to ask about documents"
    )
    # Example: "When does the contract expire?"

    document_ids: Optional[List[int]] = Field(
        None,
        description="Filter search to specific documents (optional)"
    )
    # Example: [1, 2, 3] = only search documents with these IDs
    # None = search all user's documents

    top_k: Optional[int] = Field(
        5,
        ge=1,  # greater than or equal to 1
        le=20,  # less than or equal to 20
        description="Number of chunks to retrieve (default 5, max 20)"
    )
    # Why max 20? Prevents LLM context overload
    # Why min 1? Need at least one result for useful answer


# ═════════════════════════════════════════════════════════════════════════════
# RESPONSE SCHEMAS (what goes OUT to the user)
# ═════════════════════════════════════════════════════════════════════════════

class RetrievedChunk(BaseModel):
    """
    A single chunk returned during retrieval.
    Includes content, source info, and relevance score.
    """

    content: str = Field(
        description="Text content of the chunk"
    )

    similarity_score: float = Field(
        description="0-1, higher = more relevant (cosine similarity)"
    )

    document_id: int = Field(
        description="Which document this chunk came from"
    )

    filename: str = Field(
        description="Human-readable filename"
    )

    page_number: Optional[int] = Field(
        None,
        description="Which page in the document (if applicable)"
    )

    chunk_index: int = Field(
        description="Chunk position within document (0-indexed)"
    )


class QueryResponse(BaseModel):
    """
    Response body for POST /query
    Returns what chunks were retrieved (before LLM processes them).
    
    Note: This response shows only retrieval results.
    In later days (Day 7), we'll add the LLM answer here too.
    """

    question: str = Field(
        description="The question that was asked"
    )

    retrieved_chunks: List[RetrievedChunk] = Field(
        description="Chunks retrieved and ranked by relevance"
    )

    total_chunks_retrieved: int = Field(
        description="How many chunks were returned"
    )

    max_similarity_score: Optional[float] = Field(
        None,
        description="Highest similarity score among retrieved chunks"
    )

    min_similarity_score: Optional[float] = Field(
        None,
        description="Lowest similarity score among retrieved chunks"
    )

    # Metadata for debugging
    retrieval_time_ms: float = Field(
        description="How long retrieval took (milliseconds)"
    )

    documents_searched: int = Field(
        description="How many documents were searched"
    )


# ═════════════════════════════════════════════════════════════════════════════
# ERROR SCHEMAS (what goes OUT when something goes wrong)
# ═════════════════════════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    """
    Error response format (handled by global exception handler, but documented here)
    """

    detail: str = Field(
        description="Error message"
    )

    error_type: str = Field(
        description="Type of error (e.g., 'ValueError', 'NotFound')"
    )

    status_code: int = Field(
        description="HTTP status code"
    )
