# app/schemas/document.py
#
# WHY THIS FILE EXISTS:
# Pydantic schemas for document-related API requests/responses.
# Separate from auth.py because they're for different features.
#
# SCHEMAS DEFINE:
# - What request data looks like (file upload)
# - What response data looks like (document JSON)

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class DocumentResponse(BaseModel):
    """
    Response schema for a single document.
    Returned by POST /documents/upload and GET /documents/{id}
    """

    id: int = Field(description="Document ID in database")
    filename: str = Field(description="Original filename uploaded by user")
    chunk_count: int = Field(description="Number of chunks created from this document")
    file_size: int = Field(description="File size in bytes")
    created_at: datetime = Field(description="When the document was uploaded")

    # Allows reading from SQLAlchemy model
    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """
    Response schema for listing documents.
    Returned by GET /documents/
    """

    documents: List[DocumentResponse] = Field(description="List of user's documents")
    total: int = Field(description="Total number of documents")


class DocumentChunkResponse(BaseModel):
    """
    Response schema for a single chunk.
    Used when we want to return chunk details (Day 4+).
    """

    id: int = Field(description="Chunk ID")
    document_id: int = Field(description="ID of the parent document")
    content: str = Field(description="Text content of this chunk")
    chunk_index: int = Field(description="Sequence number within document (0-indexed)")
    page_number: int = Field(description="Page number where this chunk came from")
    created_at: datetime = Field(description="When the chunk was created")

    model_config = {"from_attributes": True}
