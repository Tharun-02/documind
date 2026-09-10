# app/core/observability/request_context.py
#
# Request context management using ContextVar.
#
# Provides thread-local storage for request-scoped data like request_id and user_id.

import time
from contextvars import ContextVar
from typing import Optional, Dict, Any


class RequestContext:
    """
    Request context containing trace information.

    Fields:
        request_id: Unique identifier for this request
        user_id: User ID (if authenticated)
        path: Request path
        start_time: Request start timestamp
        latency_ms: Request latency
    """

    def __init__(
        self,
        request_id: str,
        user_id: Optional[int] = None,
        path: str = "/",
        start_time: float = None,
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.path = path
        self.start_time = start_time or time.time()
        self.latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "path": self.path,
            "start_time": self.start_time,
            "latency_ms": self.latency_ms,
        }


# Module-level context var (async-safe, thread-local)
_request_context: ContextVar[Optional[RequestContext]] = ContextVar(
    "request_context",
    default=None
)


def get_request_context() -> Optional[RequestContext]:
    """
    Get the current request context.

    Returns:
        RequestContext if set, None otherwise
    """
    return _request_context.get()


def set_request_context(
    request_id: str,
    user_id: Optional[int] = None,
    path: str = "/",
) -> RequestContext:
    """
    Set the request context for the current request.

    Args:
        request_id: Unique request identifier
        user_id: Optional user ID
        path: Request path

    Returns:
        The created RequestContext
    """
    context = RequestContext(
        request_id=request_id,
        user_id=user_id,
        path=path,
    )
    _request_context.set(context)
    return context


def update_request_context(**kwargs) -> None:
    """
    Update the current request context with new values.

    Args:
        **kwargs: Context fields to update (request_id, user_id, path)
    """
    context = _request_context.get()
    if context:
        for key, value in kwargs.items():
            if hasattr(context, key):
                setattr(context, key, value)


def clear_request_context() -> None:
    """
    Clear the request context (called after request completes).
    """
    _request_context.set(None)
