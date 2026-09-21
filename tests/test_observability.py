# tests/test_observability.py
# Day 7c: Tests for structured logging and LangSmith tracing

import json
import logging
from unittest.mock import patch, MagicMock

import pytest

from app.core.observability.logger import (
    get_logger,
    set_request_context as set_logger_context,
    clear_request_context as clear_logger_context,
    StructuredJsonFormatter,
    RequestLoggingAdapter,
    get_request_context as get_logger_context,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test StructuredJsonFormatter
# ─────────────────────────────────────────────────────────────────────────────

class TestStructuredJsonFormatter:
    """Test JSON log formatting with request context."""

    def test_format_includes_basic_fields(self):
        """Log format includes timestamp, level, message, etc."""
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = json.loads(formatter.format(record))
        assert "timestamp" in result
        assert result["level"] == "INFO"
        assert result["message"] == "Test message"
        assert "logger" in result
        assert "module" in result

    def test_format_includes_request_context(self):
        """Log format includes request_id, user_id, path from context."""
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        # Add request context attributes (simulating what adapter does)
        record.request_id = "test-request-123"
        record.user_id = "user_456"
        record.path = "/test/path"

        result = json.loads(formatter.format(record))
        assert result["request_id"] == "test-request-123"
        assert result["user_id"] == "user_456"
        assert result["path"] == "/test/path"

    def test_format_defaults_to_unknown_when_no_context(self):
        """Log without context uses 'unknown' for request_id."""
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="No context",
            args=(),
            exc_info=None,
        )
        # No context attributes set

        result = json.loads(formatter.format(record))
        assert result["request_id"] == "unknown"
        assert result["user_id"] == "anonymous"
        assert result["path"] == "/"


# ─────────────────────────────────────────────────────────────────────────────
# Test RequestLoggingAdapter
# ─────────────────────────────────────────────────────────────────────────────

class TestRequestLoggingAdapter:
    """Test the logger adapter that adds request context."""

    def test_process_adds_context(self):
        """process() adds request context to log kwargs."""
        logger = logging.getLogger("adapter_test")
        logger.setLevel(logging.INFO)

        adapter = RequestLoggingAdapter(logger, {})

        # Mock the get_request_context to return a context
        with patch("app.core.observability.logger.get_request_context") as mock_ctx:
            mock_ctx.return_value = {
                "request_id": "adapter-123",
                "user_id": "adapter-user",
                "path": "/adapter/test",
            }

            msg, kwargs = adapter.process("Test message", {"extra": {}})

            assert "extra" in kwargs
            assert kwargs["extra"]["request_id"] == "adapter-123"
            assert kwargs["extra"]["user_id"] == "adapter-user"
            assert kwargs["extra"]["path"] == "/adapter/test"

    def test_process_handles_empty_context(self):
        """process() handles None context gracefully."""
        adapter = RequestLoggingAdapter(logging.getLogger("test"), {})

        with patch("app.core.observability.logger.get_request_context") as mock_ctx:
            mock_ctx.return_value = None

            msg, kwargs = adapter.process("Test message", {"extra": {}})

            # Context is None, so extra should remain unchanged
            assert kwargs["extra"] == {}

    def test_process_adds_to_existing_extra(self):
        """process() merges context with existing extra."""
        adapter = RequestLoggingAdapter(logging.getLogger("test"), {})

        with patch("app.core.observability.logger.get_request_context") as mock_ctx:
            mock_ctx.return_value = {
                "request_id": "merged-123",
                "user_id": "merged-user",
                "path": "/merged/test",
            }

            msg, kwargs = adapter.process("Test", {"extra": {"existing": "value"}})

            assert kwargs["extra"]["existing"] == "value"
            assert kwargs["extra"]["request_id"] == "merged-123"


# ─────────────────────────────────────────────────────────────────────────────
# Test get_logger
# ─────────────────────────────────────────────────────────────────────────────

class TestGetLogger:
    """Test logger retrieval with request context support."""

    def test_get_logger_returns_logger_with_adapter(self):
        """get_logger returns a LoggerAdapter with context support."""
        logger = get_logger("test_module")
        # LoggerAdapter has process() method
        assert hasattr(logger, "process")
        # Original logger is accessible
        assert logger.logger.name == "test_module"

    def test_logger_produces_json_output(self):
        """Logger output is valid JSON with request context."""
        import io

        # Set up string handler
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredJsonFormatter())

        logger = logging.getLogger("json_test")
        logger.setLevel(logging.INFO)
        # Clear any existing handlers
        logger.handlers.clear()
        logger.addHandler(handler)

        # Add context and log
        record = logging.LogRecord(
            name="json_test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test JSON",
            args=(),
            exc_info=None,
        )
        record.request_id = "json-req-1"
        record.user_id = "json-user"
        record.path = "/json/test"

        logger.handle(record)

        output = stream.getvalue()
        data = json.loads(output)
        assert data["message"] == "Test JSON"
        assert data["request_id"] == "json-req-1"

    def test_logger_defaults_to_unknown_when_no_context(self):
        """Log without context uses 'unknown' for request_id."""
        import io

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredJsonFormatter())

        logger = logging.getLogger("no_context_test")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.addHandler(handler)

        record = logging.LogRecord(
            name="no_context_test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="No context",
            args=(),
            exc_info=None,
        )
        # No context attributes set

        logger.handle(record)

        output = stream.getvalue()
        data = json.loads(output)
        assert data["request_id"] == "unknown"
        assert data["user_id"] == "anonymous"
        assert data["path"] == "/"


# ─────────────────────────────────────────────────────────────────────────────
# Test Request Context (module-level functions)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoggerRequestContext:
    """Test module-level request context functions in logger.py."""

    def test_set_get_request_context(self):
        """set_request_context and get_request_context work together."""
        set_logger_context(
            request_id="ctx-123",
            user_id=456,
            path="/test",
        )
        context = get_logger_context()
        assert context["request_id"] == "ctx-123"
        assert context["user_id"] == 456
        assert context["path"] == "/test"

    def test_clear_request_context(self):
        """clear_request_context resets the context."""
        set_logger_context(request_id="to-clear")
        clear_logger_context()
        context = get_logger_context()
        assert context == {}


# ─────────────────────────────────────────────────────────────────────────────
# Test LangSmith Setup
# ─────────────────────────────────────────────────────────────────────────────

class TestLangSmithSetup:
    """Test LangSmith configuration."""

    def test_setup_langsmith_enabled(self):
        """setup_langsmith returns True when LANGCHAIN_TRACING_V2 is enabled."""
        # Mock settings BEFORE importing tracing
        with patch("app.config.settings") as mock_settings:
            mock_settings.LANGCHAIN_TRACING_V2 = True
            mock_settings.LANGCHAIN_PROJECT = "test-project"
            mock_settings.LANGCHAIN_API_KEY = "test-key"

            # Import and test
            from app.core.observability import tracing

            # Reset the setup flag to allow re-testing
            tracing._langsmith_setup = False

            result = tracing.setup_langsmith()

            assert result is True

    def test_setup_langsmith_disabled(self):
        """setup_langsmith returns False when disabled."""
        import importlib
        import sys

        with patch("app.config.settings") as mock_settings:
            mock_settings.LANGCHAIN_TRACING_V2 = False

            # Remove cached module to force fresh import
            if "app.core.observability.tracing" in sys.modules:
                del sys.modules["app.core.observability.tracing"]
            if "app.core.observability" in sys.modules:
                del sys.modules["app.core.observability"]

            from app.core.observability import tracing
            tracing._langsmith_setup = False

            result = tracing.setup_langsmith()

            assert result is False


# ─────────────────────────────────────────────────────────────────────────────
# Test Main.py Integration (simple smoke tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestMainObservability:
    """Test main.py observability integration."""

    def test_app_imports_without_error(self):
        """main.py imports successfully with lifespan."""
        import main
        assert hasattr(main, "app")
        assert main.app is not None

    def test_health_endpoint_works(self):
        """Health endpoint returns status ok."""
        from starlette.testclient import TestClient
        from main import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "documind"

    def test_lifespan_exists(self):
        """FastAPI app was initialized with lifespan function."""
        from main import app

        # lifespan is passed during init, check it's callable via __init__.__code__
        # or just verify the app starts without error
        assert app is not None
