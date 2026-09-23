# DocuMind 🧠

> AI-powered document intelligence platform — upload documents, ask questions, compare clauses, and get cited answers powered by a LangGraph agent with hybrid RAG.

## 🚀 Live Demo

**Backend API:** `https://documind-api.onrender.com` (Render free tier)
**Frontend:** `https://documind-frontend.onrender.com` (Render static site)
**API Docs:** `https://documind-api.onrender.com/docs`

---

## ✨ Features

- **Authentication** — JWT-based register/login with bcrypt password hashing
- **Document Upload** — PDF/DOCX parsing, chunking, and embedding storage
- **RAG Query** — Semantic search over uploaded documents with cited answers
- **LangGraph Agent** — Multi-step reasoning with custom tools (retrieve_documents, answer_question)
- **Document Comparison** — Cosine similarity comparison of clauses across two documents
- **Streaming API** — Token-by-token response via SSE for real-time UX
- **Redis Caching** — Query results cached for <10ms repeated hits
- **Structured Logging** — JSON logs with request context (request_id, user_id, path)
- **LangSmith Tracing** — Full observability on every agent run (optional, disabled by default)
- **Frontend** — Vanilla HTML/CSS/JS served as static files from FastAPI

---

## 📋 Development Status

### Completed (Days 1-7)

| Day | Topic | Status |
|-----|-------|--------|
| 1 | Python + FastAPI + Project Setup | ✅ |
| 2 | Authentication (JWT, bcrypt) | ✅ |
| 3 | Database (PostgreSQL, SQLAlchemy, Alembic) | ✅ |
| 4 | Documents & Embeddings (Pinecone) | ✅ |
| 4.5 | Free LLM (Groq) + Embeddings (HuggingFace) | ✅ |
| 5 | Complete RAG Pipeline (answer generation, sources) | ✅ |
| 6 | LangGraph Agent (tool-calling, multi-step reasoning) | ✅ |
| 7 | Production I (Redis caching, Streaming SSE, Structured logging, LangSmith) | ✅ |

### In Progress / Next

| Day | Topic | Status |
|-----|-------|--------|
| 8 | Clause Comparison (already implemented in Day 5+) | ✅ (early) |
| 9 | RAGAS Evaluation | 🔜 |
| 10 | Full LangSmith Integration | 🔜 |
| 11-13 | Enhanced Frontend (chat UI, better UX) | 🔜 |
| 14 | Portfolio Polish & CI/CD | 🔜 |

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| AI Agent | LangGraph + LangChain |
| LLM | Groq — Llama 3.3 70B Versatile (free, tool-calling) |
| Embeddings | HuggingFace Inference API (free, sentence-transformers/all-MiniLM-L6-v2) |
| Vector DB | Pinecone |
| Retrieval | Semantic search over Pinecone + keyword hybrid |
| Database | PostgreSQL + SQLAlchemy 2.0 (psycopg3 driver) |
| Cache | Redis (async, allkeys-lru eviction) |
| Frontend | Vanilla HTML/CSS/JS (served as static files) |
| Deploy | Render (Blueprint: API + Static Site + Redis + PostgreSQL) |
| Observability | Structured logging + LangSmith (optional) |

---

## 🏃 Local Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+
- API keys from [Groq](https://console.groq.com/keys), [HuggingFace](https://huggingface.co/settings/tokens), [Pinecone](https://app.pinecone.io/)

### Option 1: Docker Compose (Recommended)

```bash
git clone https://github.com/yourusername/documind
cd documind
cp .env.example .env        # fill in your API keys
docker-compose up --build   # starts app + postgres + redis
# visit http://localhost:8000/docs
```

### Option 2: Local Development

```bash
git clone https://github.com/yourusername/documind
cd documind
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env     # fill in your API keys
uvicorn main:app --reload --port 8000
# visit http://localhost:8000/docs
```

---

## 📁 Project Structure

```
documind/
├── app/
│   ├── api/              # FastAPI routes (auth, documents, query, answer)
│   ├── core/             # Business logic
│   │   ├── agent/        # LangGraph agent (tools, service)
│   │   ├── cache/        # Redis client + RAG cache service
│   │   ├── ingestion/    # PDF parsing, chunking, embeddings (Pinecone)
│   │   ├── observability/# Structured logging + LangSmith tracing
│   │   └── retrieval/    # Vector search (Pinecone + hybrid)
│   ├── models/           # SQLAlchemy models (User, Document, DocumentChunk)
│   ├── schemas/          # Pydantic request/response schemas
│   └── services/         # Business logic (RAG service)
├── frontend/             # Static HTML/CSS/JS (served at /)
├── tests/                # pytest tests
├── docs/
│   └── plans/            # Development timeline
├── workers/              # Parallel development branches
├── .env                  # Environment variables (gitignored)
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── main.py               # FastAPI app + lifespan + static file mount
├── render.yaml           # Render Blueprint (IaC)
├── requirements.txt      # Python dependencies
└── Procfile              # For platform deployment
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (auto-set by Render) |
| `REDIS_URL` | Yes | Redis connection string (auto-set by Render) |
| `SECRET_KEY` | Yes | JWT signing key (auto-generated by Render) |
| `GROQ_API_KEY` | Yes | Groq API key for LLM (get from console.groq.com) |
| `HUGGINGFACE_API_KEY` | Yes | HuggingFace token for embeddings (get from huggingface.co/settings/tokens) |
| `PINECONE_API_KEY` | Yes | Pinecone API key for vector storage |
| `PINECONE_INDEX_NAME` | No | Pinecone index name (default: documind) |
| `PINECONE_ENVIRONMENT` | No | Pinecone environment (default: us-east-1-aws) |
| `LANGCHAIN_API_KEY` | No | LangSmith API key (only if enabling tracing) |
| `LANGCHAIN_TRACING_V2` | No | Enable LangSmith tracing (default: false) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: *) |

---

## 📚 API Endpoints

### Authentication
- `POST /auth/register` — Register new user
- `POST /auth/login` — Login, returns JWT access token

### Documents
- `POST /documents/upload` — Upload PDF/DOCX, returns chunk count
- `GET /documents/` — List user's documents
- `POST /documents/compare` — Compare two documents (cosine similarity)

### Query & Retrieval
- `POST /query/` — Semantic search over documents
- `POST /query/agent` — LangGraph agent multi-step reasoning
- `POST /query/agent/stream` — Streaming agent response (SSE)
- `GET /query/status` — Check user's document status

### Answer Generation
- `POST /answer/` — RAG answer with citations
- `POST /answer/stream` — Streaming RAG answer (SSE)
- `GET /answer/status` — Check if user can answer questions

### System
- `GET /health` — Health check
- `GET /docs` — Swagger UI
- `GET /redoc` — ReDoc

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_health.py -v
```

---

## 🚢 Deployment (Render)

The project uses a **Render Blueprint** (`render.yaml`) defining 4 services:

1. **documind-api** (Web Service, Python) — FastAPI backend
2. **documind-frontend** (Static Site) — Serves frontend/ at root
3. **documind-redis** (Redis) — Free tier, allkeys-lru
4. **documind-db** (PostgreSQL) — Free tier

### Deploy Steps

1. Push to GitHub
2. In Render dashboard: **New → Blueprint** → select repo
3. Render provisions all 4 services automatically
4. Add required secret environment variables in Render dashboard:
   - `GROQ_API_KEY`
   - `HUGGINGFACE_API_KEY`
   - `PINECONE_API_KEY`
   - (Optional) `LANGCHAIN_API_KEY`
5. Update `CORS_ORIGINS` to your frontend URL once known
6. Redeploy

---

## 📈 Current Progress

**Backend:** ~90% complete (Days 1-7 done)
**Frontend:** Basic static UI served from API (~40% complete)
**Deployment:** Configured via Render Blueprint, awaiting secret injection

Built as a portfolio project — currently at Day 7 of 14.