# DocuMind 🧠

> AI-powered document intelligence platform — upload documents, ask questions, compare clauses, and get cited answers powered by a LangGraph agent with hybrid RAG.

![Build Status](https://github.com/yourusername/documind/actions/workflows/deploy.yml/badge.svg)

## 🚀 Live Demo
**Coming Day 12** — [documind.railway.app](https://documind.railway.app)

---

## ✨ Features
- **Hybrid RAG** — BM25 + semantic search + cross-encoder reranking
- **LangGraph Agent** — multi-step reasoning with custom tools
- **Clause Comparison** — compare sections across two documents
- **Streaming API** — token-by-token response via FastAPI StreamingResponse
- **RAGAS Evaluation** — faithfulness + relevance scored on every query
- **LangSmith Tracing** — full observability on every agent run

## 🛠 Tech Stack
| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| AI Agent | LangGraph + LangChain |
| LLM | OpenAI GPT-4o |
| Embeddings | text-embedding-3-small |
| Vector DB | Pinecone |
| Retrieval | BM25 + Semantic + Cross-encoder reranking |
| Evaluation | RAGAS + LangSmith |
| Database | PostgreSQL + SQLAlchemy |
| Queue | Redis |
| Deploy | Railway + GitHub Actions CI/CD |

## 🏃 Local Setup (5 commands)
```bash
git clone https://github.com/yourusername/documind
cd documind
cp .env.example .env        # fill in your API keys
docker-compose up --build   # starts app + postgres + redis
# visit http://localhost:8000/docs
```

## 📁 Architecture
*(diagram coming Day 13)*

---
*Built as a portfolio project — Day 1 of 14*
