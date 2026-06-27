# main.py
# UPDATED for Day 4: include query router

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import create_tables
from app.api.routes import auth, documents, query  # NEW: import query


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ───────────────────────────────────────────────────────────
    print("🚀 DocuMind starting up...")
    create_tables()
    print("✅ Database tables ready")

    yield  # app runs here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────
    print("🛑 DocuMind shutting down...")


app = FastAPI(
    title="DocuMind API",
    description="""
    AI-powered document intelligence platform.

    ## Features
    - Upload and parse PDF/Word documents
    - Ask questions with cited answers (RAG)
    - Compare clauses across documents (LangGraph Agent)
    - Real-time eval metrics (RAGAS + LangSmith)
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
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


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "documind"}


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "DocuMind API",
        "docs": "/docs",
        "health": "/health",
    }
