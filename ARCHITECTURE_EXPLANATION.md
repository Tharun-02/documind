# DocuMind Architecture Explanation

## 1. Docker-Compose Usage (Local Development Only)

**Important:** Docker-compose is **NOT used in Render deployment**. It's exclusively for local development.

### What Docker-Compose Does Locally:
- Defines 3 services in `docker-compose.yml`:
  - `app`: FastAPI backend (built from Dockerfile)
  - `db`: PostgreSQL 15 database
  - `redis`: Redis 7 cache

### Local Development Flow:
```bash
docker-compose up --build
```
- Starts all 3 services with hot reload
- Backend connects to `db` and `redis` using Docker service names
- Frontend served by FastAPI at `http://localhost:8000`

### Render Deployment (Different Architecture):
Render uses **managed services** instead of Docker-compose:
- **Backend Service**: FastAPI app (from `render.yaml`)
- **Database**: Render PostgreSQL (managed)
- **Cache**: Render Redis (managed)
- **Static Site**: Render Static Site (serves `frontend/` folder)
- **Build**: Single `pip install -r requirements.txt` command

## 2. Pinecone vs PostgreSQL: Separation of Concerns

These serve completely different purposes and are used together in the RAG pipeline:

| **PostgreSQL (Relational)** | **Pinecone (Vector)** |
|-----------------------------|------------------------|
| Stores **metadata** about users, documents, and chunks | Stores **embeddings** (384-dim vectors) for semantic search |
| Tables: `users`, `documents`, `document_chunks` | Index: `documind` (1536-dim for HF, 384-dim for others) |
| Fields: file paths, chunk text, page numbers, ownership, timestamps | Fields: vector values + metadata (chunk_id, document_id, page) |
| ACID transactions, joins, complex queries | Approximate Nearest Neighbor (ANN) search, high-speed retrieval |
| Source of truth for document ownership & permissions | Optimized for similarity search (cosine distance) |
| Used for: authentication, file management, filtering results | Used for: finding semantically similar chunks |

### Data Flow:
1. **Upload PDF** → Save to PostgreSQL (`documents` table)
2. **Parse & Chunk** → Save chunks to PostgreSQL (`document_chunks` table)  
3. **Embed Chunks** → Generate vectors using HuggingFace model
4. **Upsert to Pinecone** → Store vectors with `chunk_id` + `document_id` metadata
5. **Query Process**:
   - Embed question → Same HF model
   - Search Pinecone → Get top-k similar chunk IDs
   - Filter by user ownership → PostgreSQL join on `document_chunks`
   - Return enriched results → Send to LLM (Groq)

## 3. Redis Functionality

Redis implements **asynchronous, LRU caching** for RAG query results:

### Purpose:
Cache expensive RAG operations (question + user context → answer) to avoid:
- Repeated Pinecone vector searches
- Repeated Groq LLM calls
- Repeated chunk retrieval & context assembly

### Implementation:
- **Client**: `redis.asyncio` via `CacheClient` singleton (in `app/core/cache/redis_client.py`)
- **Service**: `RAGCacheService` (in `app/services/rag_service.py`)
- **Key Format**: Hash-based for security & uniformity
  ```
  rag:query:{sha256(user_id:question:document_ids:top_k)[:16]}
  ```
- **TTL**: 1 hour default (configurable via `CACHE_TTL_SECONDS`)
- **Cache Hit**: Returns answer in <10ms, skips Pinecone + Groq entirely
- **Cache Miss**: Proceeds with normal RAG flow, then stores result

### Current Limitations:
- **Invalidation**: Stubbed with `NotImplementedError` (would need to clear cache on document upload/delete)
- **Serialization**: Uses JSON for cached values
- **Connection**: Singleton pattern via `@lru_cache()` on `get_redis_client()`

## 4. Complete Request Flow Example

### User Asks: "What does the contract say about termination?"
1. **Authentication Check**: JWT token validated → `user_id: 123`
2. **Cache Check**: 
   - Compute hash of `"123:What does the contract say about termination?:[45,67]:5"`
   - Check Redis → MISS (not cached)
3. **Question Embedding**: 
   - HuggingFace model → 384-dim vector
4. **Vector Search**:
   - Query Pinecone → Returns top 5 chunk IDs: `[c101, c205, c312, c109, c401]`
5. **Ownership Filter**:
   - PostgreSQL: `SELECT * FROM document_chunks WHERE id IN (...) AND document_id IN (SELECT id FROM documents WHERE user_id = 123)`
   - Returns: `[c101 (doc 45), c205 (doc 67)]` - both owned by user
6. **Context Assembly**:
   - Fetch chunk text + metadata for `c101`, `c205`
   - Build prompt: "Based on these chunks: [text1] [text2]... Answer: What does the contract say about termination?"
7. **LLM Generation**:
   - Send to Groq (llama-3.3-70b-versatile) → Streaming response
8. **Streaming Back**:
   - SSE tokens sent to frontend as they're generated
9. **Cache Store**:
   - Store final answer in Redis with 1-hour TTL
10. **Frontend Display**:
    - Show tokens as they arrive (typewriter effect)
    - Show retrieved chunks as collapsible "agent steps"

## 5. Current Implementation Status

✅ **Backend Complete** (Days 1-7):
- Auth: JWT + bcrypt (login/register)
- Documents: Upload, parse, chunk, metadata storage
- RAG: HuggingFace embeddings → Pinecone → Groq LLM
- Agent: LangGraph with tool routing (search, compare)
- Caching: Redis async client with hash-based keys
- Streaming: SSE endpoints for real-time token display
- Observability: Structured logging + LangSmith tracing
- Comparison: Document-document clause analysis

✅ **Frontend Redesign Complete**:
- Hash-routed SPA (`#/auth`, `#/chat`, `#/documents`, `#/compare`)
- Auth view: Register/Login forms with validation
- Chat view: 
  - Streaming message display (SSE)
  - Floating document picker (modal)
  - Message bubbles with user/assistant styling
  - Agent steps visualization (collapsible details)
- Documents view: Upload/list/delete with feedback
- Compare view: Notice explaining integration into chat
- Shared: API helpers, router, responsive styling

## 6. Next Steps for Render Deployment

1. **Local Testing**:
   ```bash
   # Kill any existing processes on port 8000
   # Then:
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   - Test: http://localhost:8000
   - Flow: Register → Login → Upload PDF → Chat → Ask questions

2. **Prepare for Render**:
   - Ensure `app/database.py` uses `postgresql+psycopg://` dialect (already updated)
   - Verify `requirements.txt` has `psycopg[binary]` (not `psycopg2-binary`)
   - Confirm `render.yaml` has correct build command

3. **Render Dashboard Setup**:
   - Add environment variables:
     - `GROQ_API_KEY` (from console.groq.com)
     - `HUGGINGFACE_API_KEY` (from huggingface.co)
     - `PINECONE_API_KEY` (from app.pinecone.io)
     - `SECRET_KEY` (generate: `python -c "import secrets; print(secrets.token_hex(32))"`)
   - Set `CORS_ORIGINS` to your Render static site URL (e.g., `https://documind.onrender.com`)

4. **Deploy & Monitor**:
   - Push to GitHub → Trigger Render build
   - Watch build logs for psycopg3 compatibility
   - After deploy: Test health endpoint (`/health`)
   - Complete user flow: Register → Login → Upload → Chat

## 7. Key Architecture Benefits

### Separation of Concerns:
- **PostgreSQL**: Reliable metadata storage (relational strengths)
- **Pinecone**: Fast semantic search (vector DB strengths)  
- **Redis**: Fast caching (in-memory strengths)
- **Groq**: Low-latency LLM inference (specialized hardware)
- **LangGraph**: Predictable agent reasoning (workflow engine)

### Scalability:
- Each service scales independently
- Cache reduces load on expensive components (Pinecone + Groq)
- Stateless backend enables horizontal scaling

### Security:
- JWT tokens for stateless authentication
- Passwords bcrypt-hashed
- Document ownership enforced at query time
- API endpoints protected by auth middleware

### Performance:
- Cache hits return answers in <10ms
- Streaming provides immediate feedback
- Vector search optimized for similarity queries
- Chunking strategy balances context size with relevance

This architecture provides a robust foundation for a production document intelligence platform while leveraging managed services on Render for simplified operations.