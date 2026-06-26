# app/api/routes/documents.py
#
# WHY THIS FILE EXISTS:
# HTTP endpoints for document management:
#   POST /documents/upload  → user uploads a PDF
#   GET /documents/         → list user's documents
#   GET /documents/{id}     → details of one document
#   DELETE /documents/{id}  → delete a document
#
# INTEGRATION WITH PREVIOUS DAYS:
# Day 2: get_current_user dependency ensures only logged-in users access this
# Day 3: parser + chunker process the uploaded PDF
# Day 4: embedder will process these chunks
#
# FLOW:
#   User calls POST /documents/upload with JWT + PDF file
#   ↓
#   FastAPI validates JWT (Day 2 dependency)
#   ↓
#   FastAPI validates file is actually a PDF
#   ↓
#   Parser extracts text
#   ↓
#   Chunker splits into pieces
#   ↓
#   Save Document + chunks to database
#   ↓
#   Return success with chunk count

import os
from datetime import datetime
from typing import List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.dependencies import get_current_user
from app.config import settings
from app.core.ingestion.parser import PDFParser
from app.core.ingestion.chunker import DocumentChunker
from app.schemas.document import DocumentResponse, DocumentListResponse


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────
# UPLOAD ENDPOINT
# ─────────────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: UploadFile = File(...),  # File(...) means required
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF document.
    
    The system will:
    1. Validate it's a PDF
    2. Parse the PDF → extract text
    3. Chunk the text
    4. Store in database
    5. Return document details
    
    Requires: valid JWT token in Authorization header
    
    Example:
        curl -X POST http://localhost:8000/documents/upload \\
          -H "Authorization: Bearer <token>" \\
          -F "file=@contract.pdf"
    
    Returns 201 Created with:
        {
            "id": 1,
            "filename": "contract.pdf",
            "chunk_count": 50,
            "file_size": 102400,
            "created_at": "2026-06-25T..."
        }
    """

    # ── STEP 1: VALIDATE FILE ───────────────────────────────────────────

    # Check file exists
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided",
        )

    # Check filename is safe (not empty, doesn't contain path traversal)
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a name",
        )

    # Check file is actually a PDF (by extension)
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    # ── STEP 2: SAVE FILE TO DISK ───────────────────────────────────────

    # Create unique filename: user_id_timestamp_originalname
    # This prevents collisions (two users upload "contract.pdf" → different files)
    timestamp = int(datetime.now().timestamp())
    safe_filename = f"{current_user.id}_{timestamp}_{file.filename}"

    # Create uploads directory if it doesn't exist
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Full path to save the file
    file_path = upload_dir / safe_filename

    try:
        # Write file to disk
        # file.file is a SpooledTemporaryFile from FastAPI
        # Read in chunks to avoid loading huge files into memory at once
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                buffer.write(chunk)

        # Get file size (useful for metadata)
        file_size = file_path.stat().st_size

    except Exception as e:
        # If write fails, clean up and return error
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        )

    # ── STEP 3: PARSE PDF ───────────────────────────────────────────────

    try:
        # Parser extracts text from PDF
        parse_result = PDFParser.extract_text(str(file_path))

        if not parse_result["success"]:
            file_path.unlink()  # clean up
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to parse PDF",
            )

        extracted_text = parse_result["text"]
        page_count = parse_result["page_count"]

    except Exception as e:
        file_path.unlink()  # clean up
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PDF file: {str(e)}",
        )

    # ── STEP 4: CHUNK THE TEXT ─────────────────────────────────────────

    try:
        # Create in-memory Document object (not in DB yet)
        # This is just for chunker to reference
        chunks_data = DocumentChunker.split_text(
            text=extracted_text,
            document_id=0,  # will be updated after we create the Document
            filename=file.filename,
            page_count=page_count,
        )

        # Calculate chunk count for the document
        chunk_count = len(chunks_data)

        if chunk_count == 0:
            file_path.unlink()  # clean up
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF has no extractable text",
            )

    except Exception as e:
        file_path.unlink()  # clean up
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to chunk document: {str(e)}",
        )

    # ── STEP 5: SAVE TO DATABASE ───────────────────────────────────────

    try:
        # Create Document row
        document = Document(
            user_id=current_user.id,
            filename=file.filename,
            file_path=str(file_path),
            chunk_count=chunk_count,
            file_size=file_size,
        )

        # Add to session and flush (insert but don't commit yet)
        # We need the document.id for the chunks
        db.add(document)
        db.flush()  # generates the id

        # Now update chunk_data with correct document_id
        for chunk_data in chunks_data:
            chunk_data["document_id"] = document.id

        # Create DocumentChunk rows
        for chunk_data in chunks_data:
            chunk = DocumentChunk(
                document_id=chunk_data["document_id"],
                content=chunk_data["content"],
                chunk_index=chunk_data["chunk_index"],
                page_number=chunk_data["page_number"],
            )
            db.add(chunk)

        # Commit everything at once
        db.commit()
        db.refresh(document)

    except Exception as e:
        db.rollback()  # undo any partial writes
        file_path.unlink()  # clean up file
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save document: {str(e)}",
        )

    # Return the document (serialized through DocumentResponse schema)
    return document


# ─────────────────────────────────────────────────────────────────────────
# LIST DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=DocumentListResponse,
)
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all documents uploaded by the current user.
    
    Returns:
        {
            "documents": [
                {"id": 1, "filename": "contract.pdf", "chunk_count": 50, ...},
                {"id": 2, "filename": "report.pdf", "chunk_count": 30, ...},
            ],
            "total": 2,
        }
    """

    # Query all documents for this user
    documents = db.query(Document).filter(
        Document.user_id == current_user.id
    ).all()

    return DocumentListResponse(
        documents=documents,
        total=len(documents),
    )


# ─────────────────────────────────────────────────────────────────────────
# GET DOCUMENT DETAILS
# ─────────────────────────────────────────────────────────────────────────

@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get details of a specific document.
    Users can only access their own documents.
    """

    # Fetch document and verify it belongs to current user
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


# ─────────────────────────────────────────────────────────────────────────
# DELETE DOCUMENT
# ─────────────────────────────────────────────────────────────────────────

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a document and all its chunks.
    Users can only delete their own documents.
    
    Note: cascading delete (defined in Document model)
    automatically deletes all DocumentChunks for this document.
    """

    # Fetch and verify ownership
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Delete from database (chunks auto-delete via cascade)
    db.delete(document)
    db.commit()

    # Delete file from disk
    file_path = Path(document.file_path)
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception:
            # If file deletion fails, don't crash the API
            # (DB is already deleted, file cleanup can happen later)
            pass

    # 204 No Content — successful deletion, no body to return
