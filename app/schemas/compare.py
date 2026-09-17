# app/schemas/compare.py
#
# Pydantic schemas for clause comparison feature (Day 8).
# Compares clauses across two documents for similarity.

from pydantic import BaseModel, Field
from typing import List, Optional


class CompareRequest(BaseModel):
    """
    Request schema for comparing two documents.
    """

    document_id_1: int = Field(
        ..., description="First document ID to compare"
    )
    document_id_2: int = Field(
        ..., description="Second document ID to compare"
    )
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Similarity threshold (0-1, default 0.7)"
    )


class ClauseComparison(BaseModel):
    """
    Comparison result for a single clause pair.
    """

    clause_1: str = Field(description="First clause text")
    clause_2: str = Field(description="Second clause text")
    similarity_score: float = Field(description="Similarity score (0-1)")
    document_1_chunk_id: Optional[int] = Field(
        None, description="Chunk ID from document 1"
    )
    document_2_chunk_id: Optional[int] = Field(
        None, description="Chunk ID from document 2"
    )
    document_1_page: Optional[int] = Field(
        None, description="Page number from document 1"
    )
    document_2_page: Optional[int] = Field(
        None, description="Page number from document 2"
    )


class CompareResponse(BaseModel):
    """
    Response schema for comparison results.
    """

    document_1_id: int = Field(description="First document ID")
    document_2_id: int = Field(description="Second document ID")
    document_1_filename: str = Field(description="First document filename")
    document_2_filename: str = Field(description="Second document filename")
    total_comparisons: int = Field(description="Total clause pairs compared")
    similar_clauses: List[ClauseComparison] = Field(
        description="List of similar clause pairs above threshold"
    )
    comparison_time_ms: float = Field(description="Comparison duration in ms")
