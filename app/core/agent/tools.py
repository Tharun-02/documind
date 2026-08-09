# app/core/agent/tools.py
#
# The agent's two tools. Each tool is a LangChain `@tool` that the LLM can invoke.
#
# WHY TWO TOOLS (not one):
# - A single `answer_question` tool would force retrieval for everything including
#   "hi" or "thanks". Two tools let the LLM decide:
#     - Knowledge question → call `retrieve_documents`, then `answer_question`
#     - Greeting → no tools at all, just respond
#     - Future (Day 8): "compare docs 1 and 2" → `compare_clauses`, no retrieval
#
# HOW TOOLS ARE BUILT:
# - `build_tools(db, user_id, ...)` closes over the request context (db session,
#   user_id, document filter). Returns a list of `@tool`-decorated functions.
# - This pattern is called "tool factories" — each request gets fresh tools
#   bound to the right user's data. Never share tools across users.
#
# TOOL DESCRIPTIONS ARE PROMPTS:
# - The LLM reads the docstring to decide when to call each tool.
# - Be specific. "Use this for X. Do NOT use for Y." Bad descriptions = bad routing.

from typing import Optional
import json

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.core.retrieval.retriever import RetrieverService
from app.core.generation.llm_service import LLMService


# Module-level state — gets set by build_tools() per request.
# Yes, global state feels gross. But LangChain tools are designed as standalone
# callables; closing over request state cleanly requires either:
#   (a) Module globals (what we do here) — simple, works
#   (b) functools.partial + serialization (breaks tool schema)
#   (c) Custom tool class with .invoke() (overkill for Day 6)
#
# If you build a custom graph (Day 8+), consider option (c).
_request_state: dict = {}


def _format_chunks_for_llm(chunks: list) -> str:
    """
    Format retrieved chunks into a string the LLM can read as context.

    We return a STRING (not a list of dicts) because LangChain tool outputs
    are str-typed by convention. The `answer_question` tool will receive this
    string and pass it to the LLM as context.
    """
    if not chunks:
        return "No relevant documents found."

    parts = ["RETRIEVED DOCUMENTS:\n"]
    for i, chunk in enumerate(chunks, 1):
        filename = chunk.get("filename", "Unknown")
        score = chunk.get("score", 0.0)
        content = chunk.get("content", "")
        page = chunk.get("page_number")

        page_str = f" (page {page})" if page else ""
        parts.append(
            f"[Doc {i}] {filename}{page_str} — relevance {score:.2f}\n{content}\n"
        )
    return "\n".join(parts)


def build_tools(
    db: Session,
    user_id: int,
    document_ids: Optional[list[int]] = None,
    top_k: int = 5,
) -> list:
    """
    Build the agent's tools, bound to this request's context.

    Args:
        db: SQLAlchemy session (request-scoped)
        user_id: owner of the documents to search
        document_ids: optional filter — only search these documents
        top_k: how many chunks to retrieve

    Returns:
        list of LangChain `@tool` callables, ready for `create_react_agent`.
    """
    # Store request context so the @tool functions can access it.
    # Tools are defined at module level (LangChain requirement) but read
    # context from this dict at call time.
    _request_state.update({
        "db": db,
        "user_id": user_id,
        "document_ids": document_ids,
        "top_k": top_k,
        # We stash the LAST retrieval result so `answer_question` can reuse it
        # without re-querying. The agent should call retrieve first, then answer.
        "last_retrieval": None,
    })

    return [retrieve_documents, answer_question]


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1: Retrieve documents
# ─────────────────────────────────────────────────────────────────────────────

@tool
def retrieve_documents(query: str) -> str:
    """
    Search the user's documents for chunks relevant to the query.

    Use this when the user asks a question that requires looking up information
    from their uploaded documents (contracts, reports, manuals, etc.).

    Do NOT use this for greetings, small talk, or questions you can answer from
    your own knowledge (e.g., "what is 2+2", "what's the capital of France").

    Args:
        query: the search query — rephrase the user's question as a focused
               search string. Example: "When does the contract expire?" →
               "contract expiration date termination".

    Returns:
        Formatted text containing the most relevant chunks, or a message
        saying no relevant documents were found.
    """
    state = _request_state
    retriever = RetrieverService(state["db"])

    chunks = retriever.retrieve(
        query=query,
        user_id=state["user_id"],
        document_ids=state["document_ids"],
        top_k=state["top_k"],
    )

    # Stash for answer_question to reuse without a second retrieval.
    state["last_retrieval"] = chunks

    return _format_chunks_for_llm(chunks)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2: Answer question using retrieved context
# ─────────────────────────────────────────────────────────────────────────────

@tool
def answer_question(question: str) -> str:
    """
    Generate a final answer to the user's question using retrieved context.

    Use this AFTER calling `retrieve_documents`. Pass the user's original
    question (not the search query) — the retrieval already happened.

    If no retrieval was performed (e.g., for a greeting), this tool will still
    work but will answer without document context.

    Args:
        question: the user's original question, verbatim.

    Returns:
        A natural-language answer grounded in the retrieved documents.
    """
    state = _request_state

    # Reuse the chunks from the most recent retrieve_documents call.
    # If the agent skipped retrieval (e.g., for "hi"), chunks is empty
    # and the LLM will answer without context — which is fine for small talk.
    chunks = state.get("last_retrieval") or []

    llm = LLMService()
    return llm.generate_answer(
        question=question,
        retrieved_chunks=chunks,
        stream=False,
    )