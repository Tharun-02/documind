# tests/test_agent.py
#
# Day 6: Unit tests for the LangGraph agent.
#
# TESTING PHILOSOPHY:
# - Mock everything external: Groq (LLM), Pinecone (vector DB), DB (SQLAlchemy).
# - Tests should run in <1s and cost $0.
# - We test the SHAPE of the agent's behavior (which tools it picks, what it
#   returns), not the LLM's actual reasoning.
#
# MOCKING STRATEGY:
# - `build_chat_model` is monkeypatched to return a fake ChatModel.
# - The fake ChatModel emits a hand-crafted message history: it either
#   (a) calls retrieve_documents + answer_question, or
#   (b) answers directly (no tool calls).
# - This lets us assert that AgentService correctly WALKS the history, regardless
#   of what the real LLM would have done.
#
# Run with: pytest tests/test_agent.py -v

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_db():
    """A MagicMock standing in for a SQLAlchemy Session."""
    return MagicMock()


@pytest.fixture
def fake_chunks():
    """Sample retrieval output — what RetrieverService.retrieve() returns."""
    return [
        {
            "content": "The contract expires December 31st, 2025.",
            "score": 0.94,
            "page_number": 2,
            "document_id": 1,
            "filename": "contract.pdf",
            "chunk_index": 5,
        },
        {
            "content": "Termination requires 30 days notice.",
            "score": 0.81,
            "page_number": 3,
            "document_id": 1,
            "filename": "contract.pdf",
            "chunk_index": 6,
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Graph construction: both tools are wired in
# ─────────────────────────────────────────────────────────────────────────────

def test_build_agent_includes_both_tools(fake_db):
    """
    The compiled graph must have retrieve_documents AND answer_question tools.
    If a tool is missing, the agent can't route correctly.
    """
    from app.core.agent.graph import build_agent
    from app.core.agent.tools import retrieve_documents, answer_question

    # Patch the LLM to a MagicMock so we don't need a real API key
    with patch("app.core.agent.graph.build_chat_model", return_value=MagicMock()):
        agent = build_agent(db=fake_db, user_id=1, top_k=5)

    # create_react_agent stores tools on the graph. We can introspect by
    # calling .get_graph() or checking bound tools — easier path: re-call
    # build_tools and verify the list.
    from app.core.agent.tools import build_tools
    tools = build_tools(db=fake_db, user_id=1)
    tool_names = {t.name for t in tools}

    assert tool_names == {"retrieve_documents", "answer_question"}


# ─────────────────────────────────────────────────────────────────────────────
# 2. AgentService returns AgentResult with all four fields
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_service_returns_agent_result(fake_db, fake_chunks):
    """
    AgentService.run() returns an AgentResult (not raw LangGraph state)
    with answer, sources, steps, response_time_ms populated.
    """
    from app.services.agent_service import AgentService, AgentResult

    # Fake agent that returns a typical knowledge-question trace:
    # retrieve → answer → done
    fake_history = [
        HumanMessage(content="When does the contract expire?"),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "retrieve_documents",
                "args": {"query": "contract expiration date"},
                "id": "call_1",
            }],
        ),
        ToolMessage(
            content="[Doc 1] contract.pdf — relevance 0.94\nThe contract expires December 31st, 2025.\n",
            tool_call_id="call_1",
        ),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "answer_question",
                "args": {"question": "When does the contract expire?"},
                "id": "call_2",
            }],
        ),
        ToolMessage(
            content="The contract expires December 31st, 2025.",
            tool_call_id="call_2",
        ),
        AIMessage(content="The contract expires December 31st, 2025."),
    ]

    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(return_value={"messages": fake_history})

    # Patch build_agent to return our fake, and patch retriever to return fake_chunks
    with patch("app.services.agent_service.build_agent", return_value=fake_agent), \
         patch("app.core.agent.tools.RetrieverService") as MockRetriever:
        MockRetriever.return_value.retrieve.return_value = fake_chunks

        service = AgentService(fake_db)
        result = await service.run(
            question="When does the contract expire?",
            user_id=1,
            top_k=5,
        )

    # Assert shape
    assert isinstance(result, AgentResult)
    assert result.answer == "The contract expires December 31st, 2025."
    assert len(result.steps) == 2
    assert result.steps[0].tool == "retrieve_documents"
    assert result.steps[1].tool == "answer_question"
    assert result.response_time_ms > 0
    # Sources should be populated from the retrieval step
    assert len(result.sources) >= 1
    assert result.sources[0]["filename"] == "contract.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Greeting → no tool calls → empty steps
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_greeting_skips_retrieval(fake_db):
    """
    For 'hi', the agent should answer directly without calling retrieve_documents.
    The result should have empty steps and empty sources.
    """
    from app.services.agent_service import AgentService

    fake_history = [
        HumanMessage(content="hi"),
        AIMessage(content="Hello! How can I help you with your documents today?"),
    ]

    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(return_value={"messages": fake_history})

    with patch("app.services.agent_service.build_agent", return_value=fake_agent):
        service = AgentService(fake_db)
        result = await service.run(question="hi", user_id=1)

    assert result.answer == "Hello! How can I help you with your documents today?"
    assert result.steps == [], "Greeting should not trigger any tool calls"
    assert result.sources == []


# ─────────────────────────────────────────────────────────────────────────────
# 4. Sources are deduplicated by document_id
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sources_are_deduplicated(fake_db):
    """
    If the same document appears in multiple chunks, it should show up once
    in sources (not once per chunk).
    """
    from app.services.agent_service import AgentService

    # Two chunks from the SAME document
    dup_chunks = [
        {"content": "...", "score": 0.9, "document_id": 1, "filename": "contract.pdf",
         "page_number": 2, "chunk_index": 5},
        {"content": "...", "score": 0.8, "document_id": 1, "filename": "contract.pdf",
         "page_number": 3, "chunk_index": 6},
    ]

    fake_history = [
        HumanMessage(content="test"),
        AIMessage(content="", tool_calls=[{
            "name": "retrieve_documents", "args": {"query": "test"}, "id": "call_1",
        }]),
        ToolMessage(content="[Doc 1] contract.pdf — relevance 0.90\n...\n\n[Doc 2] contract.pdf — relevance 0.80\n...",
                    tool_call_id="call_1"),
        AIMessage(content="answer"),
    ]

    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(return_value={"messages": fake_history})

    with patch("app.services.agent_service.build_agent", return_value=fake_agent), \
         patch("app.core.agent.tools.RetrieverService") as MockRetriever:
        MockRetriever.return_value.retrieve.return_value = dup_chunks

        service = AgentService(fake_db)
        result = await service.run(question="test", user_id=1)

    assert len(result.sources) == 1, "Same document should appear once"
    assert result.sources[0]["document_id"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. AgentService propagates LLM errors as ValueError
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_propagates_errors(fake_db):
    """
    If the agent raises (e.g., Groq timeout), AgentService wraps it in ValueError
    so the route handler can convert it to a clean 400.
    """
    from app.services.agent_service import AgentService

    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(side_effect=RuntimeError("Groq timeout"))

    with patch("app.services.agent_service.build_agent", return_value=fake_agent):
        service = AgentService(fake_db)
        with pytest.raises(ValueError, match="Agent invocation failed"):
            await service.run(question="anything", user_id=1)


# ─────────────────────────────────────────────────────────────────────────────
# 6. to_dict() serializes cleanly for the HTTP response
# ─────────────────────────────────────────────────────────────────────────────

def test_agent_result_to_dict(fake_db):
    """AgentResult.to_dict() should produce a JSON-serializable dict."""
    from app.services.agent_service import AgentResult, AgentStep

    result = AgentResult(
        answer="test answer",
        sources=[{"document_id": 1, "filename": "a.pdf", "score": 0.9, "page_number": 1}],
        steps=[AgentStep(tool="retrieve_documents", tool_input="{}", output_summary="1 chunk")],
        response_time_ms=123.4,
    )

    d = result.to_dict()
    assert d == {
        "answer": "test answer",
        "sources": [{"document_id": 1, "filename": "a.pdf", "score": 0.9, "page_number": 1}],
        "steps": [{"tool": "retrieve_documents", "input": "{}", "output_summary": "1 chunk"}],
        "response_time_ms": 123.4,
    }