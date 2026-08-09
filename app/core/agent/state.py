# app/core/agent/state.py
#
# State schema for the LangGraph agent.
#
# WHY THIS FILE:
# - LangGraph's `create_react_agent` prebuilt uses a standard message-passing state.
# - TypedDict gives us type hints without runtime overhead.
# - `Annotated[list, add_messages]` is LangGraph's reducer — it tells the graph
#   "when a node returns new messages, APPEND them to the list, don't replace it."
#
# If we ever build a custom graph (Day 8+), we'd add more fields here:
#   e.g., `retrieved_docs: list[dict]`, `iteration_count: int`

from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    State passed between nodes in the agent graph.

    Fields:
        messages: The conversation history. Each message is a LangChain message
                  (HumanMessage, AIMessage, ToolMessage). The `add_messages` reducer
                  appends new messages rather than overwriting — this is what
                  makes the ReAct loop work: tool results get appended after
                  the assistant's tool-call message.
    """

    messages: Annotated[list, add_messages]