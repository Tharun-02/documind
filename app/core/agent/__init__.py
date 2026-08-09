# app/core/agent/__init__.py
#
# Public exports for the agent DOMAIN primitives.
# AgentService lives in app.services (orchestration layer), not here.
#
# Usage:
#     from app.services.agent_service import AgentService     # orchestration
#     from app.core.agent import build_agent, build_tools     # domain primitives
#
# WHY LAZY IMPORTS:
# `build_agent` and `build_tools` pull in `RetrieverService` → `DocumentChunk`
# → `app.database` → SQLAlchemy engine. At import time we'd force a DB driver
# (psycopg2) to be present even in scripts that just want to inspect the module.
# Lazy __getattr__ defers that until the symbol is actually used.
#
# This is the standard pattern for breaking circular/heavy import chains
# without sacrificing the public import path.

from typing import TYPE_CHECKING

__all__ = ["build_agent", "build_tools"]


def __getattr__(name: str):
    if name == "build_agent":
        from app.core.agent.graph import build_agent
        return build_agent
    if name == "build_tools":
        from app.core.agent.tools import build_tools
        return build_tools
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Type checkers can still see the attributes without paying the runtime cost.
if TYPE_CHECKING:
    from app.core.agent.graph import build_agent
    from app.core.agent.tools import build_tools