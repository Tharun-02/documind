# app/core/observability/tracing.py
#
# LangSmith tracing setup and decorator.
#
# Provides automatic tracing of agent runs and request-level observability.

import time
from functools import wraps
from typing import Optional, Callable, Any

from app.config import settings
from app.core.observability.logger import get_logger

logger = get_logger(__name__)

# LangSmith setup flag
_langsmith_setup = False


def setup_langsmith() -> bool:
    """
    Configure LangSmith tracing environment variables.

    Returns:
        True if LangSmith is enabled and configured, False otherwise
    """
    global _langsmith_setup

    if not settings.LANGCHAIN_TRACING_V2:
        logger.info("LangSmith tracing is disabled (LANGCHAIN_TRACING_V2=false)")
        _langsmith_setup = False
        return False

    import os
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.LANGCHAIN_TRACING_V2)
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT or "documind"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY or ""

    _langsmith_setup = True
    logger.info("LangSmith tracing enabled")
    return True


def trace_request(
    request_id: str,
    fn: Callable,
) -> Callable:
    """
    Decorator to trace a function with timing and logging.

    Args:
        request_id: Request identifier for correlation
        fn: Function to trace

    Returns:
        Wrapped function with timing and logging
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        path = kwargs.get("path", "/unknown")

        logger.info(
            f"Request started: {path}",
            extra={"request_id": request_id, "event": "request_start"}
        )

        try:
            result = fn(*args, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Request completed: {path}",
                extra={
                    "request_id": request_id,
                    "event": "request_complete",
                    "latency_ms": elapsed_ms,
                    "status": "success"
                }
            )
            return result

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000

            logger.error(
                f"Request failed: {path}",
                extra={
                    "request_id": request_id,
                    "event": "request_error",
                    "latency_ms": elapsed_ms,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise

    return wrapper


def trace_async_request(
    request_id: str,
) -> Callable:
    """
    Decorator factory for async functions.

    Args:
        request_id: Request identifier for correlation

    Returns:
        Decorator function for async functions
    """
    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            path = kwargs.get("path", "/unknown")

            logger.info(
                f"Request started: {path}",
                extra={"request_id": request_id, "event": "request_start"}
            )

            try:
                result = await fn(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                logger.info(
                    f"Request completed: {path}",
                    extra={
                        "request_id": request_id,
                        "event": "request_complete",
                        "latency_ms": elapsed_ms,
                        "status": "success"
                    }
                )
                return result

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000

                logger.error(
                    f"Request failed: {path}",
                    extra={
                        "request_id": request_id,
                        "event": "request_error",
                        "latency_ms": elapsed_ms,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
                raise

        return wrapper
    return decorator
