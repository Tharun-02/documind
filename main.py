# main.py
# UPDATED for Day 4: include query router
# UPDATED for Day 7c: observability (structured logging + LangSmith)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.database import create_tables
from app.api.routes import auth, documents, query, answer
from app.core.observability.tracing import setup_langsmith
from app.core.observability.logger import get_logger, set_request_context, clear_request_context
import uuid
import os


# ── Lifespan (startup/shutdown) ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - runs on startup and shutdown.
    """
    # Startup: initialize LangSmith tracing
    setup_langsmith()

    # Create database tables
    create_tables()

    # Log startup
    logger = get_logger(__name__)
    logger.info("DocuMind API starting up")

    yield

    # Shutdown
    logger.info("DocuMind API shutting down")


app = FastAPI(
    title="DocuMind API",
    description="""
    AI-powered document intelligence platform.

    ## Features
    - Upload and parse PDF/Word documents
    - Ask questions with cited answers (RAG)
    - Compare clauses across documents (LangGraph Agent)
    - Streaming API (SSE for agent responses)
    - Redis-backed caching (repeated queries hit memory in <10ms)
    - Structured logging + LangSmith tracing on every request
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ─────────────────────────────────────────────────────────────
app.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

app.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"],
)

# NEW: include query router at /query prefix
app.include_router(
    query.router,
    prefix="/query",
    tags=["Query & Retrieval"],
)

# Day 6 fix: mount /answer router (existed but was never included)
app.include_router(
    answer.router,
    prefix="/answer",
    tags=["Answer Generation"],
)


# ── Health Check ─────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "documind"}


# ── Request Context Middleware ──────────────────────────────────────────
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """
    Middleware to set request context for logging and tracing.
    """
    request_id = str(uuid.uuid4())
    user_id = None  # Will be set by auth middleware if available

    set_request_context(
        request_id=request_id,
        user_id=user_id,
        path=str(request.url.path),
    )

    # Attach request_id to request state for later access
    request.state.request_id = request_id

    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(
            f"Request error: {request.url.path}",
            extra={"request_id": request_id, "error": str(e)}
        )
        raise
    finally:
        clear_request_context()


# ── Global Exception Handler ─────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = get_logger(__name__)
    logger.error(
        f"Global exception handler caught: {type(exc).__name__}",
        extra={"request_id": getattr(request.state, "request_id", "unknown"), "error": str(exc)}
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
    )


# Serve frontend static files (must be after API routes)
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")