# app/models/document.py
#
# WHY THIS FILE EXISTS:
# Defines two tables:
#   1. Document — represents an uploaded PDF/file
#   2. DocumentChunk — represents a piece of that document
#
# Relationship: One Document has many DocumentChunks (1-to-many)
# When user uploads "contract.pdf" → creates 1 Document row
# Parser splits it into 50 chunks → creates 50 DocumentChunk rows
# Each chunk references the document via document_id (foreign key)

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Document(Base):
    """
    Represents an uploaded document (PDF, Word file, etc.)
    Stores metadata about the file.
    """
    __tablename__ = "documents"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Who uploaded this document (foreign key to users table)
    # Django-style naming: lowercase model name + _id
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),  # if user deleted → delete their docs
        nullable=False,
        index=True,
    )

    # Original filename the user uploaded (for reference)
    filename = Column(
        String,
        nullable=False,
    )

    # Unique internal name for storage (so two files named "contract.pdf" don't collide)
    # Typically: user_id_timestamp_originalname
    # Example: 1_1719274800_contract.pdf
    file_path = Column(
        String,
        nullable=False,
        unique=True,  # no two documents share a file path
        index=True,
    )

    # How many chunks were created from this document
    # Useful for the UI to show "contract.pdf: 50 chunks"
    chunk_count = Column(
        Integer,
        default=0,
    )

    # File size in bytes (metadata)
    file_size = Column(
        Integer,
    )

    # When was this document uploaded
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationship: access the chunks of this document
    # Usage: doc.chunks → returns all DocumentChunk rows for this doc
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",  # if document deleted → delete its chunks
    )

    def __repr__(self):
        return f"<Document id={self.id} filename={self.filename} chunks={self.chunk_count}>"


class DocumentChunk(Base):
    """
    Represents a single chunk/piece of a document.
    Created by splitting the document's text.
    
    One document can have hundreds of chunks.
    Each chunk is independently stored in the vector DB (Day 4).
    """
    __tablename__ = "document_chunks"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Which document does this chunk belong to
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The actual text content of this chunk
    # Text type allows larger strings than String
    content = Column(
        Text,
        nullable=False,
    )

    # Sequential index within the document
    # Chunk 0, Chunk 1, Chunk 2, etc.
    # Useful for ordering when we retrieve chunks
    chunk_index = Column(
        Integer,
        nullable=False,
    )

    # What page did this chunk come from (if PDF)
    # Useful for citations: "This quote is from page 5"
    page_number = Column(
        Integer,
    )

    # Start character position in the full document text
    # Useful for exact location tracking
    start_char = Column(
        Integer,
    )

    # End character position in the full document text
    end_char = Column(
        Integer,
    )

    # When was this chunk created (will match document.created_at usually)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationship back to the document
    # Usage: chunk.document → returns the Document this chunk belongs to
    document = relationship(
        "Document",
        back_populates="chunks",
    )

    def __repr__(self):
        return f"<DocumentChunk id={self.id} doc_id={self.document_id} chunk={self.chunk_index}>"
