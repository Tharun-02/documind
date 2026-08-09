# DocuMind 🧠

> AI-powered document intelligence platform — upload documents, ask questions, compare clauses, and get cited answers powered by a LangGraph agent with hybrid RAG.

![Build Status](https://github.com/yourusername/documind/actions/workflows/deploy.yml/badge.svg)

## 🚀 Live Demo
**Coming Day 12** — [documind.railway.app](https://documind.railway.app)

---

## ✨ Features
- **Hybrid RAG** — semantic search over Pinecone *(BM25 + cross-encoder reranking planned)*
- **LangGraph Agent** — multi-step reasoning with custom tools *(Day 6)*
- **Clause Comparison** — compare sections across two documents *(Day 8)*
- **Streaming API** — token-by-token response via FastAPI StreamingResponse
- **RAGAS Evaluation** — faithfulness + relevance scored on every query *(Day 9)*
- **LangSmith Tracing** — full observability on every agent run *(Day 10)*

## 🛠 Tech Stack
| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| AI Agent | LangGraph + LangChain (Day 6) |
| LLM | Groq — Llama 3.3 70B Versatile (free, tool-calling) |
| Embeddings | HuggingFace Inference API (sentence-transformers/all-MiniLM-L6-v2, free) |
| Vector DB | Pinecone |
| Retrieval | Semantic search over Pinecone |
| Evaluation | RAGAS + LangSmith (Day 9+) |
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
*Built as a portfolio project — Day 6 of 14*
