# app/api/routes/answer.py
# Day 5: Endpoints for RAG answer generation

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models.user import User
from app.dependencies import get_current_user
from app.schemas.answer_schemas import AnswerRequest, AnswerResponse, StreamingAnswerChunk
from app.services.rag_service import RAGService


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# ANSWER ENDPOINT (Main RAG endpoint - synchronous)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=AnswerResponse,
    status_code=status.HTTP_200_OK,
)
def answer_question(
    request: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Answer a question using retrieved document context.
    This is the MAIN RAG endpoint.
    
    How it works:
    1. Retrieves relevant chunks from documents
    2. Passes chunks to LLM
    3. LLM reads chunks and generates answer
    4. Returns answer with sources
    
    Example:
        curl -X POST http://localhost:8000/answer/ \\
          -H "Authorization: Bearer <token>" \\
          -H "Content-Type: application/json" \\
          -d '{
            "question": "When does the contract end?",
            "top_k": 5
          }'
    
    Response:
        {
            "question": "When does the contract end?",
            "answer": "Based on the contract, it expires on December 31st, 2025.",
            "retrieved_chunks": [
                {"content": "...", "similarity_score": 0.94, ...},
                ...
            ],
            "sources": [
                {"document_id": 1, "filename": "contract.pdf", "relevance": 0.94}
            ],
            "chunk_count": 5,
            "response_time_ms": 5234
        }
    """

    try:
        # Create RAG service
        rag = RAGService(db)

        # Generate answer
        result = rag.answer_question(
            question=request.question,
            user_id=current_user.id,
            document_ids=request.document_ids,
            top_k=request.top_k,
        )

        # Convert to response model
        response = AnswerResponse(
            question=result['question'],
            answer=result['answer'],
            retrieved_chunks=result['retrieved_chunks'],
            sources=result['sources'],
            chunk_count=result['chunk_count'],
            response_time_ms=result['response_time_ms'],
        )

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating answer: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# STREAMING ANSWER ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
)
def stream_answer(
    request: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stream answer tokens as they're generated.
    Better for real-time UI (shows answer appearing word-by-word).
    
    Response is server-sent events (SSE) format.
    Each line is a JSON object with type and content.
    
    Example client (JavaScript):
        const es = new EventSource('/answer/stream?...');
        es.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'token') {
                console.log(data.token);
            }
        };
    """

    try:
        rag = RAGService(db)

        def generate():
            """Generate streaming response."""
            for chunk in rag.answer_question_streaming(
                question=request.question,
                user_id=current_user.id,
                document_ids=request.document_ids,
                top_k=request.top_k,
            ):
                # Convert to JSON and send as SSE event
                yield f"data: {json.dumps(chunk)}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ─────────────────────────────────────────────────────────────────────────────
# ANSWER STATUS (Check if user has enough documents)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
)
def answer_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check if user has documents and can use answer endpoint.
    """

    from app.models.document import Document

    documents = db.query(Document).filter(
        Document.user_id == current_user.id
    ).all()

    total_chunks = sum(doc.chunk_count for doc in documents)

    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "documents_count": len(documents),
        "total_chunks": total_chunks,
        "can_answer": total_chunks > 0,
        "message": "Ready to answer questions" if total_chunks > 0 else "Upload documents first"
    }
