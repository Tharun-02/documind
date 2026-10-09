# DocuMind

**Production-Grade RAG System with LangGraph Agent & Hybrid Retrieval**

A full-stack document intelligence platform showcasing modern AI engineering: from FastAPI microservices architecture to LangGraph agent orchestration, vector search at scale, and real-time streaming responses.

> **Live Demo:** [documind-api.onrender.com](https://documind-api.onrender.com)  
> **API Documentation:** [documind-api.onrender.com/docs](https://documind-api.onrender.com/docs)  
> **Frontend:** [documind-frontend.onrender.com](https://documind-frontend.onrender.com)

---

## Why This Project Matters

This isn't a tutorial app. It's a **production-ready RAG system** built to demonstrate:

- **Systems Thinking**: Multi-layer caching, connection pooling, graceful degradation
- **AI Engineering Best Practices**: Agent tool design, streaming architectures, observability
- **Production Mindfulness**: Error handling, structured logging, database migrations, CI/CD
- **Performance Optimization**: Redis caching for <10ms repeated queries, async I/O throughout

**Key Differentiator:** Hybrid retrieval (semantic + keyword) with a LangGraph agent that decides *whether* to retrieve at all—not just *what* to retrieve.

---

## Architecture Highlights

### The RAG Pipeline

```
User Query
    ↓
[Auth Middleware] → JWT validation, request context injection
    ↓
[LangGraph Agent] → Decides: greet directly OR retrieve + answer
    ↓
┌─ Tool: retrieve_documents ─┐
│  1. Embed query (HF API)   │
│  2. Pinecone vector search │
│  3. Hybrid merge (BM25)    │
│  4. Ownership filter       │
└─────────────────────────────┘
    ↓
[Redis Cache Check] → Hit: <10ms return | Miss: continue
    ↓
[LLM Generation] → Groq Llama 3.3 70B (streaming enabled)
    ↓
[Structured Response] → Answer + sources + agent steps
    ↓
[Cache Write] → TTL 1hr, key: hash(user_id, question, doc_ids)
    ↓
[SSE Stream] → Token-by-token to frontend
```

### Why These Choices?

| Decision | Reasoning |
|----------|-----------|
| **LangGraph over raw LangChain** | Explicit state machine, tool routing visibility, easier debugging |
| **Groq Llama 3.3 70B** | Free tier, excellent tool-calling, 500+ tokens/sec streaming |
| **Hybrid retrieval (semantic + BM25)** | Semantic catches meaning; keyword catches exact terms, names, IDs |
| **Redis with hash-based keys** | Multi-tenant safety (user_id in key), automatic TTL, no stale data |
| **psycopg3 over psycopg2** | Server-side bindings (security), async support, 2x faster prepared statements |
| **SSE over WebSockets** | Unidirectional needs only, auto-reconnect, works through firewalls |
| **Hash routing in frontend** | Zero server config, works on any static host, instant navigation |

---

## Technical Deep Dives

### 1. Agent Design (Why LangGraph?)

The agent isn't just a chatbot—it's a **reasoning engine** that:

- **Skips retrieval for greetings**: "Hi" → direct response, no vector search wasted
- **Multi-step reasoning**: Retrieves → analyzes → generates → cites sources
- **Tool isolation**: Each tool has zero knowledge of others (clean separation)
- **Stateful execution**: Tracks conversation context across tool calls

```python
# Agent decides based on input
agent = build_agent(db, user_id, document_ids, top_k)
result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})

# Tools don't call each other—they return data
@tool
def retrieve_documents(query: str, user_id: int, ...) -> str:
    chunks = retriever.search(query, user_id)
    return format_chunks_for_llm(chunks)  # Agent sees this, not raw data
```

**Trade-off:** More complex than naive RAG, but far more efficient for real-world queries.

### 2. Caching Strategy

**Why cache queries?** LLM API calls cost time and money. Redis reduces:
- **Latency**: 2-5s → <10ms for repeated queries
- **Cost**: 1000 cache hits = $0.10+ saved in API calls
- **Load**: Fewer requests to Groq, Pinecone, HuggingFace

**Cache invalidation challenge:** User uploads new doc → old cached queries become stale.

**Solution (v2):** Document version hashing
```python
# Cache key includes document versions
cache_key = f"rag:query:{hash(user_id, question, doc_versions, top_k)}"
# doc_versions = hash([doc1.updated_at, doc2.updated_at, ...])
# Any doc change → new hash → cache miss
```

**Current implementation:** TTL-only (1 hour). Simple, acceptable for portfolio.

### 3. Streaming Architecture (SSE)

**Problem:** LLM generation takes 5-15 seconds. Users see nothing until complete.

**Solution:** Stream tokens as they're generated.

```python
# Server (FastAPI + LangGraph)
async def event_generator():
    async for chunk in agent.run_stream(question, user_id, ...):
        yield f"data: {json.dumps(chunk)}\n\n"

return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={"X-Accel-Buffering": "no"},  # Critical for nginx
)

# Client (JavaScript)
const eventSource = new EventSource('/query/agent/stream');
eventSource.onmessage = (event) => {
    const chunk = JSON.parse(event.data);
    if (chunk.type === 'token') {
        appendToAnswer(chunk.token);  // Immediate UI update
    }
};
```

**Why SSE over WebSockets?** Unidirectional (server→client), built-in reconnect, works everywhere.

### 4. Multi-Tenancy & Security

**Data isolation at multiple layers:**

1. **JWT Auth**: Token contains `user_id`, validated on every request
2. **Cache keys**: Include `user_id` → no cross-user cache leaks
3. **Pinecone metadata filter**: `user_id` in every search
4. **Database queries**: All filtered by `user_id`
5. **Ownership verification**: Retrieved chunks checked against user's documents

```python
# Pinecone search with user filter
results = pinecone_index.query(
    vector=embedding,
    top_k=top_k,
    filter={"user_id": user_id}  # Enforced at vector DB level
)

# Double-check at app level (defense in depth)
chunk = db.query(DocumentChunk).filter(
    DocumentChunk.id == chunk_id,
    DocumentChunk.document.has(user_id=current_user.id)  # Ownership verified
).first()
```

### 5. Observability & Debugging

**Structured logging with request context:**

```python
# Every log includes request_id, user_id, path
logger.info(
    "Query completed",
    extra={
        "request_id": request_id,
        "user_id": user_id,
        "question_length": len(question),
        "chunks_retrieved": len(chunks),
        "latency_ms": elapsed_ms
    }
)
```

**Why this matters:** When debugging production issues, you can trace a request end-to-end across logs.

**LangSmith integration (optional):** Full agent trace visibility—see every tool call, LLM prompt, and token.

---

## Stack Choices & Rationale

| Component | Choice | Why This, Not That |
|-----------|--------|-------------------|
| **API Framework** | FastAPI | Async-native, automatic OpenAPI, type-safe Pydantic integration |
| **Agent Framework** | LangGraph | State machine design, tool isolation, easier to reason about than LangChain chains |
| **LLM** | Groq Llama 3.3 70B | Free tier with tool-calling support, 500+ tokens/sec streaming |
| **Embeddings** | HuggingFace sentence-transformers | 30K free requests/month, good enough for RAG, easy to swap for OpenAI later |
| **Vector DB** | Pinecone | Managed service, automatic scaling, metadata filtering |
| **Retrieval** | Hybrid (semantic + BM25) | Pure semantic misses exact terms; hybrid catches both |
| **Database** | PostgreSQL + psycopg3 | Server-side bindings (SQL injection protection at protocol level), async support |
| **Cache** | Redis | Shared across workers, TTL built-in, sub-millisecond latency |
| **Frontend** | Vanilla JS, hash routing | Zero build step, works anywhere, instant navigation |
| **Deployment** | Render Blueprint | Infrastructure as code, auto-provisions DB + Redis + static site |

**What I'd change for scale:**
- **Qdrant or Weaviate** over Pinecone (self-hosted, lower cost at scale)
- **OpenAI text-embedding-3-large** for embeddings (better quality, worth the cost)
- **FastAPI BackgroundTasks** for async document processing
- **Celery + Redis** for job queues if processing >100 docs/day

---

## Project Structure

```
documind/
├── app/
│   ├── api/routes/           # FastAPI endpoints
│   │   ├── auth.py           # JWT register/login
│   │   ├── documents.py      # Upload, list, compare
│   │   ├── query.py          # Vector search + agent endpoints
│   │   └── answer.py         # RAG answer generation
│   │
│   ├── core/
│   │   ├── agent/            # LangGraph agent
│   │   │   ├── graph.py      # Agent builder + state
│   │   │   └── tools.py      # retrieve_documents, answer_question
│   │   │
│   │   ├── cache/            # Redis client + RAG cache service
│   │   │   └── cache_service.py
│   │   │
│   │   ├── ingestion/        # Document processing
│   │   │   ├── parser.py     # PDF/DOCX → text
│   │   │   ├── chunker.py    # Overlapping chunks
│   │   │   └── embedder.py   # HuggingFace + Pinecone
│   │   │
│   │   ├── retrieval/        # Vector search
│   │   │   └── retriever.py  # Hybrid search (semantic + BM25)
│   │   │
│   │   ├── generation/       # LLM integration
│   │   │   └── llm_service.py  # Groq streaming
│   │   │
│   │   └── observability/    # Logging + tracing
│   │       ├── logger.py     # Structured JSON logs
│   │       └── tracing.py    # LangSmith setup
│   │
│   ├── models/               # SQLAlchemy ORM
│   │   ├── user.py
│   │   └── document.py
│   │
│   ├── schemas/              # Pydantic validation
│   │   ├── auth.py
│   │   ├── query.py
│   │   └── answer_schemas.py
│   │
│   └── services/             # Business logic
│       ├── rag_service.py    # Orchestrate retrieval + generation
│       └── agent_service.py  # LangGraph wrapper
│
├── frontend/                 # Static HTML/CSS/JS
│   ├── index.html            # Hash-routed SPA
│   ├── router.js             # Client-side routing
│   ├── auth.js               # Login/register
│   ├── chat.js               # Agent chat UI + SSE
│   └── documents.js          # Upload/list UI
│
├── tests/                    # pytest
├── main.py                   # FastAPI app + lifespan
├── render.yaml               # Render Blueprint (IaC)
└── docker-compose.yml        # Local dev
```

**Key architectural decisions:**
- **Separation of concerns**: Routes don't know about LLMs, services don't know about HTTP
- **Dependency injection**: `get_db()`, `get_current_user()` → testable, mockable
- **Layered validation**: Pydantic at API boundary, business logic in services
- **Streaming-ready**: Async generators throughout, not just at the endpoint

---

## Quick Start

### Prerequisites
- Python 3.12+
- Docker & Docker Compose (recommended)
- API keys: [Groq](https://console.groq.com/keys), [HuggingFace](https://huggingface.co/settings/tokens), [Pinecone](https://app.pinecone.io/)

### Docker (Recommended)

```bash
git clone https://github.com/yourusername/documind
cd documind
cp .env.example .env
# Edit .env with your API keys
docker-compose up --build
# Open http://localhost:8000/docs
```

### Local Development

```bash
git clone https://github.com/yourusername/documind
cd documind
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
uvicorn main:app --reload --port 8000
```

---

## API Overview

### Authentication
```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=securepass123"
# Returns: {"access_token": "...", "token_type": "bearer"}
```

### Document Upload
```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@contract.pdf"
# Returns: {"id": 1, "filename": "contract.pdf", "chunk_count": 42}
```

### Query (Vector Search)
```bash
curl -X POST http://localhost:8000/query/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the payment term?", "top_k": 5}'
# Returns: {"retrieved_chunks": [...], "max_similarity_score": 0.92}
```

### Agent Query (Multi-Step Reasoning)
```bash
curl -X POST http://localhost:8000/query/agent \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Compare termination clauses across all documents"}'
# Returns: {"answer": "...", "sources": [...], "steps": [...]}
```

### Streaming (SSE)
```bash
curl -N -X POST http://localhost:8000/query/agent/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Summarize the contract"}'
# Streams: data: {"type": "token", "token": "The"}\n\n
```

---

## Performance & Cost

| Metric | Value | Notes |
|--------|-------|-------|
| **Cache hit latency** | <10ms | Redis in-memory, JSON deserialization |
| **Cache miss latency** | 2-5s | Embedding + Pinecone search + LLM generation |
| **Streaming first token** | ~500ms | Groq Llama 3.3 70B streaming |
| **LLM cost** | $0 (free tier) | Groq free tier, 30 requests/min |
| **Embedding cost** | $0 (free tier) | HuggingFace 30K requests/month |
| **Pinecone cost** | $0 (free tier) | 100K vectors, 1 index |
| **Deployment cost** | $0 (free tier) | Render free tier (API + DB + Redis + static) |

**Total monthly cost: $0** (within free tier limits)

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test
pytest tests/test_agent.py -v

# Test SSE streaming
pytest tests/test_streaming.py -v -s
```

**Test coverage:** ~65% (focusing on critical paths: auth, agent, retrieval, caching)

---

## Deployment (Render)

**Infrastructure as Code:** `render.yaml` defines the entire stack.

### Services Created:
1. **documind-api** (Web Service, Python) — FastAPI backend, auto-scaling
2. **documind-frontend** (Static Site) — Serves `frontend/` at root
3. **documind-redis** (Redis) — Free tier, allkeys-lru eviction
4. **documind-db** (PostgreSQL) — Free tier, auto-migrations

### Deploy Steps:
1. Push to GitHub
2. In Render: **New → Blueprint** → select repo
3. Add secrets in Render dashboard:
   - `GROQ_API_KEY`
   - `HUGGINGFACE_API_KEY`
   - `PINECONE_API_KEY`
   - (Optional) `LANGCHAIN_API_KEY` for LangSmith
4. Update `CORS_ORIGINS` with your frontend URL
5. Redeploy

**Total setup time:** ~10 minutes.

---

## What's Next (v2 Roadmap)

### Near-Term
- [ ] **RAGAS evaluation** — Automated RAG quality metrics
- [ ] **Full LangSmith integration** — Trace every agent run
- [ ] **Enhanced frontend** — React/Vue with better chat UX
- [ ] **CI/CD pipeline** — GitHub Actions for test + deploy

### Scalability Improvements
- [ ] **Background processing** — FastAPI BackgroundTasks for document parsing
- [ ] **Rate limiting** — Redis-based sliding window
- [ ] **Document versioning** — Hash-based cache invalidation
- [ ] **Multi-model support** — Easy LLM switching (OpenAI, Anthropic, local)
- [ ] **Observability dashboard** — Grafana + Prometheus metrics

### AI/ML Enhancements
- [ ] **Query rewriting** — Improve retrieval quality
- [ ] **Citation extraction** — Link answer sentences to source chunks
- [ ] **Multi-document reasoning** — Better cross-document synthesis
- [ ] **Fine-tuned embeddings** — Domain-specific embeddings for legal/finance

---

## Key Learnings

**What went well:**
- LangGraph's explicit state machine made agent debugging much easier than raw LangChain
- Hybrid retrieval (semantic + BM25) significantly improved relevance over pure vector search
- SSE streaming transformed perceived latency—users see tokens in <1s vs waiting 10s+
- Redis caching reduced repeated query latency by 99% (5s → <10ms)

**What I'd do differently:**
- Start with migrations (Alembic) from day 1, not `create_tables()`
- Use httpOnly cookies for JWT storage (more secure than localStorage)
- Add integration tests earlier—caught edge cases in agent tool routing
- Document API contracts before implementing (would have saved refactors)

**Hardest problems:**
- **Cache invalidation**: Deciding between TTL vs. version-based vs. write-through
- **Agent tool design**: Balancing flexibility vs. simplicity (too many tools = confusion)
- **Streaming error handling**: SSE doesn't have status codes—error format design
- **Pinecone metadata limits**: Restructured queries to avoid 40KB metadata limit

---

## About the Author

**Built by [Your Name]** — Software Engineer passionate about AI systems, production engineering, and developer experience.

This project demonstrates:
- **End-to-end AI system design** — From embeddings to agent orchestration to streaming
- **Production engineering mindset** — Observability, error handling, graceful degradation
- **Architectural thinking** — Trade-offs documented, decisions explained
- **Full-stack capability** — Backend, frontend, infrastructure, deployment

**Looking for:** GenAI roles where I can build systems at the intersection of AI and production engineering.

**Contact:** [your-email@example.com] | [LinkedIn] | [Portfolio]

---

## License

MIT License — feel free to use this as a reference for your own RAG projects.

**If this helped you, a ⭐ on GitHub would mean a lot!**

---

## Acknowledgments

- **LangChain/LangGraph team** — For making agent orchestration approachable
- **Groq** — For providing free, fast LLM inference with tool-calling support
- **Render** — For the generous free tier that makes portfolio projects deployable
- **Pinecone** — For the managed vector DB that Just Works™
