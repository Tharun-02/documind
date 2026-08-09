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
# WHY llama-3.3-70b-versatile:
# - Groq's free tier; reliably supports tool-calling (mixtral does not).
# - 70B parameters = strong enough for multi-step reasoning.
# - See docs/plans/day-6-langgraph-agent.md for the model-selection reasoning.

from langchain_groq import ChatGroq
from app.config import settings


# Default model if GROQ_MODEL isn't set in env. Hardcoded as a safety net.
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


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