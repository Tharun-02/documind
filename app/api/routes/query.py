# app/api/routes/query.py
#
# WHY THIS FILE EXISTS:
# Query endpoints — where users ask questions about their documents.
# This is where Days 1-6 come together:
#   Day 1: Docker provides infrastructure
#   Day 2: JWT authenticates the user
#   Day 3: Chunks from parsed PDFs
#   Day 4: Retrieve relevant chunks via semantic search
#   Day 5: Full RAG via Groq LLM
#   Day 6: LangGraph agent for multi-step reasoning + tool routing
#
# ENDPOINTS:
#   POST /query         → linear retrieval (chunks only, no LLM)
#   POST /query/agent   → LangGraph agent (decides which tools to call)
#   GET  /query/status  → debug info for the current user

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.dependencies import get_current_user
from app.schemas.query import QueryRequest, QueryResponse, RetrievedChunk
from app.core.ingestion.embedder import EmbeddingService, PineconeService
from app.core.retrieval.retriever import RetrieverService
from app.services.agent_service import AgentService
from app.core.observability.tracing import trace_request
from app.core.observability.logger import get_logger


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
# AGENT ENDPOINT (Day 6: LangGraph agent)
# ─────────────────────────────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    """Request body for POST /query/agent."""
    question: str = Field(..., min_length=3, max_length=1000)
    document_ids: Optional[List[int]] = Field(
        None, description="Optional filter to specific documents"
    )
    top_k: Optional[int] = Field(
        5, ge=1, le=20, description="Chunks to retrieve per search"
    )


class AgentSource(BaseModel):
    document_id: int
    filename: Optional[str] = None
    score: Optional[float] = None
    page_number: Optional[int] = None


class AgentStepResponse(BaseModel):
    tool: str
    input: str
    output_summary: str


class AgentResponse(BaseModel):
    answer: str
    sources: List[AgentSource] = []
    steps: List[AgentStepResponse] = []
    response_time_ms: float


@router.post(
    "/agent",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    tags=["Query & Retrieval"],
)
async def query_agent(
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ask a question via the LangGraph agent.

    Unlike the linear /query and /answer endpoints, the agent decides:
    - Whether to retrieve at all (skips for greetings, etc.)
    - Which tool(s) to call (retrieve_documents, answer_question)
    - When to stop

    The response includes a `steps` trace showing what the agent did.
    Empty steps = no tools were called (e.g., for "hi").

    Requires: valid JWT token.
    """
    service = AgentService(db)
    result = await service.run(
        question=request.question,
        user_id=current_user.id,
        document_ids=request.document_ids,
        top_k=request.top_k,
    )
    return AgentResponse(**result.to_dict())


# ─────────────────────────────────────────────────────────────────────────────
# AGENT STREAMING ENDPOINT (Day 7b: SSE)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/agent/stream",
    status_code=status.HTTP_200_OK,
    tags=["Query & Retrieval"],
)
async def query_agent_stream(
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ask a question via the LangGraph agent with streaming responses (SSE).

    Returns a Server-Sent Events stream with chunks:
    - type="token": Each token of the answer as it's generated
    - type="done": Stream is complete

    Example SSE output:
        data: {"type": "token", "token": "The"}

        data: {"type": "token", "token": " contract"}

        data: {"type": "done", "done": true}

    Requires: valid JWT token.

    Usage:
        curl -N -X POST http://localhost:8000/query/agent/stream \\
          -H "Authorization: Bearer <token>" \\
          -H "Content-Type: application/json" \\
          -d '{"question": "When does contract end?"}'
    """
    service = AgentService(db)

    async def event_generator():
        """Generate SSE events from agent stream."""
        try:
            async for chunk in service.run_stream(
                question=request.question,
                user_id=current_user.id,
                document_ids=request.document_ids,
                top_k=request.top_k,
            ):
                # Format as SSE: "data: {json}\n\n"
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            # Send error as SSE event
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


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
