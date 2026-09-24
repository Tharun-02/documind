# app/core/agent/llm.py
#
# Thin wrapper around ChatGroq that the agent uses.
#
# WHY A SEPARATE FILE:
# - The agent needs tool-calling support (the linear RAG in llm_service.py uses raw
#   `requests` and can't do tool-calling).
# - ChatGroq is LangChain's wrapper that exposes tool-calling, streaming, and message
#   types properly.
# - Keeping it separate means: Day 6+ agent code can evolve independently of the
#   Day 5 RAG codepath. We can swap models, add retry logic, etc. without touching
#   the linear pipeline.
#
# WHY temperature=0:
# - Agent routing decisions should be DETERMINISTIC. We want the same question to
#   always pick the same tool. Creative variation belongs in the answer (which
#   uses a higher temp in llm_service.py).
#
# WHY qwen/qwen3.8-27b:
# - Only chat model with tool-calling available on this Groq key (as of 2025).
# - llama-3.3-70b-versatile was decommissioned / not available on this account.
# - See https://console.groq.com/docs/models for current model availability.

from langchain_groq import ChatGroq
from app.config import settings


# Default model if GROQ_MODEL isn't set in env. Hardcoded as a safety net.
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"


def build_chat_model() -> ChatGroq:
    """
    Build the ChatGroq chat model used by the agent.

    Returns:
        ChatGroq: a LangChain chat model with tool-calling enabled.

    Raises:
        ValueError: if GROQ_API_KEY is missing.
    """
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not set. Add it to your .env file. "
            "Get a free key at https://console.groq.com/keys"
        )

    model_name = settings.GROQ_MODEL or DEFAULT_GROQ_MODEL

    return ChatGroq(
        model=model_name,
        groq_api_key=api_key,
        temperature=0.0,        # deterministic tool routing
        max_tokens=1024,
    )