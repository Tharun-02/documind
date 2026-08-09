# app/services/agent_service.py
#
# The AgentService is the public API for running the agent.
# Routes call this — they don't touch LangGraph directly.
#
# LOCATION RATIONALE:
# - Lives in app/services/ alongside RAGService — its closest sibling.
# - Both orchestrate the same retrieval + generation stack; both are
#   called from routes; both hide LangChain/LangGraph internals behind
#   a clean async API.
# - The domain primitives (build_agent, tools, chat model) stay in
#   app/core/agent/ — AgentService composes them.
#
# RESPONSIBILITIES:
# 1. Build the agent (delegating to core.agent.graph.build_agent)
# 2. Run it with the user's question
# 3. Walk the resulting message history to extract:
#    - The final answer (last AIMessage with no tool_calls)
#    - The steps the agent took (each tool call + result)
#    - The sources (deduplicated from retrieval results)
# 4. Return a clean AgentResult dict
#
# WHY THIS LAYER EXISTS:
# - Routes shouldn't have to know about LangGraph message types.
# - If we swap the graph implementation later, only this file changes.
# - Makes testing easier — you can mock AgentService entirely.

import time
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from sqlalchemy.orm import Session

from app.core.agent.graph import build_agent
from app.core.agent.tools import _request_state


class AgentStep:
    """One step the agent took (a tool invocation)."""

    def __init__(self, tool: str, tool_input: str, output_summary: str):
        self.tool = tool
        self.tool_input = tool_input
        self.output_summary = output_summary

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "input": self.tool_input,
            "output_summary": self.output_summary,
        }


class AgentResult:
    """Structured result from running the agent."""

    def __init__(
        self,
        answer: str,
        sources: list[dict],
        steps: list[AgentStep],
        response_time_ms: float,
    ):
        self.answer = answer
        self.sources = sources
        self.steps = steps
        self.response_time_ms = response_time_ms

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "steps": [s.to_dict() for s in self.steps],
            "response_time_ms": self.response_time_ms,
        }


class AgentService:
    """
    High-level wrapper for running the LangGraph agent.

    Usage:
        service = AgentService(db)
        result = await service.run(
            question="When does the contract expire?",
            user_id=1,
        )
        return result.to_dict()
    """

    def __init__(self, db: Session):
        self.db = db

    async def run(
        self,
        question: str,
        user_id: int,
        document_ids: Optional[list[int]] = None,
        top_k: int = 5,
    ) -> AgentResult:
        """
        Run the agent on a user's question.

        Args:
            question: the user's question
            user_id: document owner
            document_ids: optional filter to specific documents
            top_k: chunks to retrieve per search

        Returns:
            AgentResult with answer, sources, steps, and timing.

        Raises:
            ValueError: on agent failure (Groq errors, etc.)
        """
        start_time = time.time()

        # Build a fresh agent per request — tools are bound to this user's
        # session and we don't want to share state across requests.
        agent = build_agent(
            db=self.db,
            user_id=user_id,
            document_ids=document_ids,
            top_k=top_k,
        )

        # Invoke the agent. `ainvoke` is async — routes must `await` this.
        try:
            result = await agent.ainvoke({
                "messages": [HumanMessage(content=question)]
            })
        except Exception as e:
            raise ValueError(f"Agent invocation failed: {str(e)}") from e

        # Walk the message history to extract answer, steps, sources.
        messages = result.get("messages", [])
        answer, steps, sources = self._extract_from_messages(messages)

        elapsed_ms = (time.time() - start_time) * 1000

        return AgentResult(
            answer=answer,
            sources=sources,
            steps=steps,
            response_time_ms=elapsed_ms,
        )

    def _extract_from_messages(
        self,
        messages: list,
    ) -> tuple[str, list[AgentStep], list[dict]]:
        """
        Walk the agent's message history to extract structured outputs.

        Returns:
            (answer, steps, sources)

        - `answer`: content of the last AIMessage that has no tool_calls
        - `steps`: one entry per tool call (with tool name, input, output summary)
        - `sources`: deduplicated doc references from retrieval results
        """
        steps: list[AgentStep] = []
        sources_seen: dict[int, dict] = {}
        answer: str = ""

        # Index ToolMessages by their tool_call_id so we can pair them with
        # the AIMessage's tool_calls.
        tool_results_by_id: dict[str, ToolMessage] = {
            m.tool_call_id: m
            for m in messages
            if isinstance(m, ToolMessage)
        }

        for msg in messages:
            # Track tool calls (the assistant decided to use a tool)
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get("name", "unknown")
                    tool_input = tool_call.get("args", {})
                    tool_call_id = tool_call.get("id")

                    # Find the corresponding ToolMessage with the result
                    result_msg = tool_results_by_id.get(tool_call_id)
                    if result_msg:
                        output_summary = self._summarize_tool_output(
                            tool_name, result_msg.content
                        )
                    else:
                        output_summary = "(no result)"

                    steps.append(AgentStep(
                        tool=tool_name,
                        tool_input=str(tool_input),
                        output_summary=output_summary,
                    ))

                    # If this was a retrieval, also grab the sources
                    if tool_name == "retrieve_documents":
                        self._collect_sources_from_state(sources_seen)

            # The final answer is the last AIMessage with no tool_calls
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                answer = msg.content or ""

        # Also pull sources from the module state in case the final answer
        # came via answer_question without re-retrieving
        self._collect_sources_from_state(sources_seen)

        sources = list(sources_seen.values())
        return answer, steps, sources

    def _summarize_tool_output(self, tool_name: str, content: str) -> str:
        """Create a short human-readable summary of a tool's output."""
        if tool_name == "retrieve_documents":
            # Count chunks by counting "[Doc N]" markers
            chunk_count = content.count("[Doc ")
            if chunk_count == 0:
                return "No relevant documents"
            return f"{chunk_count} chunk(s) retrieved"
        elif tool_name == "answer_question":
            # Just show a preview
            preview = content[:80] + "..." if len(content) > 80 else content
            return f"Generated answer: {preview}"
        else:
            return content[:80] + "..." if len(content) > 80 else content

    def _collect_sources_from_state(self, sources_seen: dict[int, dict]) -> None:
        """Pull sources from the tool's stashed retrieval result."""
        chunks = _request_state.get("last_retrieval") or []
        for chunk in chunks:
            doc_id = chunk.get("document_id")
            if doc_id and doc_id not in sources_seen:
                sources_seen[doc_id] = {
                    "document_id": doc_id,
                    "filename": chunk.get("filename"),
                    "score": chunk.get("score"),
                    "page_number": chunk.get("page_number"),
                }