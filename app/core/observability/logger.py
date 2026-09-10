# app/core/observability/logger.py
#
# Structured logging with request context.
#
# Provides JSON-formatted logs with request_id, user_id, path, and latency_ms
# for traceability across the application.

import json
import time
import logging
from typing import Optional
from contextvars import ContextVar

from app.config import settings

# ContextVar for request context (thread-local, async-safe)
_request_context: ContextVar[dict] = ContextVar("request_context", default={})


class RequestLoggingAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds request context to log messages.
    """

    def process(self, msg, kwargs):
        """Add request context to log message."""
        context = get_request_context()
        if context:
            extra = kwargs.get("extra", {})
            extra["request_id"] = context.get("request_id", "unknown")
            extra["user_id"] = context.get("user_id", "anonymous")
            extra["path"] = context.get("path", "/")
            kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> logging.LoggerAdapter:
    """
    Get a logger with request context support.

    Args:
        name: Logger name (usually __name__)

    Returns:
        LoggerAdapter with context support
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Only add handler if not already added
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)

        # JSON formatter for structured logging
        formatter = StructuredJsonFormatter()
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return RequestLoggingAdapter(logger, {})


def get_request_context() -> dict:
    """
    Get current request context.

    Returns:
        Dict with request_id, user_id, path
    """
    return _request_context.get()


def set_request_context(
    request_id: str,
    user_id: Optional[int] = None,
    path: str = "/",
) -> None:
    """
    Set request context for logging.

    Args:
        request_id: Unique request identifier
        user_id: Optional user ID
        path: Request path
    """
    _request_context.set({
        "request_id": request_id,
        "user_id": user_id,
        "path": path,
    })


def clear_request_context() -> None:
    """
    Clear request context (called after request completes).
    """
    _request_context.set({})


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            # Request context fields (added by adapter)
            "request_id": getattr(record, "request_id", "unknown"),
            "user_id": getattr(record, "user_id", "anonymous"),
            "path": getattr(record, "path", "/"),
        }

        return json.dumps(log_data)
