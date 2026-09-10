# DocuMind 🧠

> AI-powered document intelligence platform — upload documents, ask questions, compare clauses, and get cited answers powered by a LangGraph agent with hybrid RAG.

![Build Status](https://github.com/yourusername/documind/actions/workflows/deploy.yml/badge.svg)

## 🚀 Live Demo

**Coming Day 13** — [documind.vercel.app](https://documind.vercel.app)

---

## ✨ Features

- **LangGraph Agent** — multi-step reasoning with custom tools *(Day 6)*
- **Clause Comparison** — compare sections across two documents *(Day 8)*
- **Streaming API** — token-by-token response via SSE *(Day 7)*
- **RAGAS Evaluation** — faithfulness + relevance scored on every query *(Day 9)*
- **LangSmith Tracing** — full observability on every agent run *(Day 10)*
- **Frontend** — Next.js UI with Vercel deployment *(Days 11-13)*

---

## 📋 Development Status

### Completed (Days 1-6)

| Day | Topic | Status |
|-----|-------|--------|
| 1 | Python + FastAPI | ✅ |
| 2 | Authentication (JWT, bcrypt) | ✅ |
| 3 | Database (PostgreSQL, SQLAlchemy) | ✅ |
| 4 | Documents & Embeddings (Pinecone) | ✅ |
| 4.5 | Free LLM (Groq) + Embeddings (HF) | ✅ |
| 5 | Complete RAG Pipeline | ✅ |
| 6 | LangGraph Agent | ✅ |

### In Progress (Days 7-10)

| Day | Topic | Status |
|-----|-------|--------|
| 7 | Production I (Caching, Streaming, Logging) | 🔜 |
| 8 | Clause Comparison | 🔜 |
| 9 | RAGAS Evaluation | 🔜 |
| 10 | LangSmith Tracing | 🔜 |

### Upcoming (Days 11-14)

| Day | Topic | Status |
|-----|-------|--------|
| 11 | Frontend I (Next.js) | 🔜 |
| 12 | Frontend II | 🔜 |
| 13 | Frontend III + Deployment | 🔜 |
| 14 | Portfolio & CI/CD | 🔜 |

**See [docs/plans/](docs/plans/) for full timeline details.**

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| AI Agent | LangGraph + LangChain (Day 6) |
| LLM | Groq — Llama 3.3 70B Versatile (free, tool-calling) |
| Embeddings | HuggingFace Inference API (free) |
| Vector DB | Pinecone |
| Retrieval | Semantic search over Pinecone |
| Evaluation | RAGAS + LangSmith (Days 9-10) |
| Database | PostgreSQL + SQLAlchemy |
| Queue | Redis |
| Frontend | Next.js + Vercel (Days 11-13) |
| Deploy | Railway + GitHub Actions CI/CD |

---

## 🏃 Local Setup

### Prerequisites

- Python 3.10+
- PostgreSQL 15+
- Redis 7+
- API keys from [Groq](https://console.groq.com/keys) and [HuggingFace](https://huggingface.co/settings/tokens)

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
│   ├── api/              # FastAPI routes
│   ├── core/             # Business logic
│   │   ├── agent/        # LangGraph agent
│   │   ├── generation/   # LLM integration
│   │   ├── ingestion/    # PDF parsing, chunking, embeddings
│   │   └── retrieval/    # Vector search
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic schemas
│   └── services/         # Business logic
├── tests/                # pytest tests
├── docs/
│   └── plans/            # Development timeline
├── workers/              # Parallel development branches
├── .env                  # Environment variables (gitignored)
├── Dockerfile
├── docker-compose.yml
└── main.py
```

---

## 📚 Development Plan

See [docs/plans/README.md](docs/plans/README.md) for the full 14-day development plan.

**Current Progress:** 6/14 days complete (Backend + RAG engine done)

---

*Built as a portfolio project — Day 6 of 14*
