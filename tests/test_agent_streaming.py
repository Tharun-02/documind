# tests/test_agent_streaming.py
# Day 7b: Tests for SSE streaming agent responses

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.agent_service import AgentService


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def agent_service(mock_db):
    """AgentService instance with mocked dependencies."""
    return AgentService(db=mock_db)


# ─────────────────────────────────────────────────────────────────────────────
# Streaming Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentStreaming:
    """Tests for agent streaming functionality."""

    @pytest.mark.asyncio
    async def test_run_stream_yields_chunks(self, agent_service, mock_db):
        """Test that run_stream yields chunks in expected format."""
        # Mock build_agent to return a mock agent
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [
                MagicMock(
                    content="Test answer",
                    tool_calls=[],
                    __class__=MagicMock(__name__="AIMessage")
                )
            ]
        })

        with patch('app.services.agent_service.build_agent', return_value=mock_agent):
            chunks = []
            async for chunk in agent_service.run_stream(
                question="test question",
                user_id=1,
            ):
                chunks.append(chunk)

        # Verify we got at least a token and done
        assert len(chunks) >= 2
        assert any(c.get("type") == "token" for c in chunks)
        assert any(c.get("type") == "done" for c in chunks)

    @pytest.mark.asyncio
    async def test_run_stream_yields_token_with_answer(self, agent_service, mock_db):
        """Test that token chunk contains the answer."""
        from langchain_core.messages import AIMessage

        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [
                AIMessage(content="The contract expires on December 31st")
            ]
        })

        with patch('app.services.agent_service.build_agent', return_value=mock_agent):
            chunks = []
            async for chunk in agent_service.run_stream(
                question="When does contract end?",
                user_id=1,
            ):
                chunks.append(chunk)

        # Find the token chunk
        token_chunks = [c for c in chunks if c.get("type") == "token"]
        assert len(token_chunks) > 0
        assert "December 31st" in token_chunks[0].get("token", "")

    @pytest.mark.asyncio
    async def test_run_stream_yields_done_at_end(self, agent_service, mock_db):
        """Test that stream ends with done=True."""
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [
                MagicMock(
                    content="Answer",
                    tool_calls=[],
                    __class__=MagicMock(__name__="AIMessage")
                )
            ]
        })

        with patch('app.services.agent_service.build_agent', return_value=mock_agent):
            chunks = []
            async for chunk in agent_service.run_stream(
                question="test",
                user_id=1,
            ):
                chunks.append(chunk)

        # Last chunk should be done
        last_chunk = chunks[-1]
        assert last_chunk.get("type") == "done"
        assert last_chunk.get("done") is True

    @pytest.mark.asyncio
    async def test_run_stream_handles_agent_error(self, agent_service, mock_db):
        """Test that agent errors are yielded as error chunks."""
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(side_effect=Exception("Agent failed"))

        with patch('app.services.agent_service.build_agent', return_value=mock_agent):
            chunks = []
            async for chunk in agent_service.run_stream(
                question="test",
                user_id=1,
            ):
                chunks.append(chunk)

        # Should have an error chunk
        error_chunks = [c for c in chunks if c.get("type") == "error"]
        assert len(error_chunks) > 0
        assert "Agent failed" in error_chunks[0].get("error", "")

    @pytest.mark.asyncio
    async def test_run_stream_handles_build_error(self, agent_service, mock_db):
        """Test that build errors are yielded as error chunks."""
        with patch('app.services.agent_service.build_agent', side_effect=Exception("Build failed")):
            chunks = []
            async for chunk in agent_service.run_stream(
                question="test",
                user_id=1,
            ):
                chunks.append(chunk)

        # Should have an error chunk
        error_chunks = [c for c in chunks if c.get("type") == "error"]
        assert len(error_chunks) > 0
        assert "Build failed" in error_chunks[0].get("error", "")
