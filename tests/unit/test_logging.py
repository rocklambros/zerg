"""Unit tests for ZERG logging module."""

import json
import logging
from pathlib import Path

from zerg.logging import (
    ConsoleFormatter,
    JsonFormatter,
    LoggerAdapter,
    clear_worker_context,
    get_logger,
    get_task_logger,
    set_worker_context,
    setup_logging,
)


class TestJsonFormatter:
    """Tests for JSON log formatter."""

    def test_format_basic_message(self) -> None:
        """Test formatting basic log message."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["message"] == "Test message"
        assert data["level"] == "info"
        assert data["logger"] == "test"
        assert "ts" in data

    def test_format_with_exception(self) -> None:
        """Test formatting message with exception."""
        formatter = JsonFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "error"
        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_format_with_extra_fields(self) -> None:
        """Test formatting with extra fields."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Task message",
            args=(),
            exc_info=None,
        )
        record.task_id = "TASK-001"
        record.worker_id = 1

        result = formatter.format(record)
        data = json.loads(result)

        assert data["task_id"] == "TASK-001"
        assert data["worker_id"] == 1


class TestConsoleFormatter:
    """Tests for console log formatter."""

    def test_format_basic_message(self) -> None:
        """Test formatting basic console message."""
        formatter = ConsoleFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "Test message" in result
        assert "INFO" in result

    def test_format_includes_color(self) -> None:
        """Test formatting includes color codes."""
        formatter = ConsoleFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should contain ANSI escape code for red
        assert "\033[31m" in result


class TestWorkerContext:
    """Tests for worker context management."""

    def test_set_worker_context(self) -> None:
        """Test setting worker context."""
        clear_worker_context()
        set_worker_context(worker_id=1, feature="test")
        # Context is global, affects logging
        clear_worker_context()

    def test_clear_worker_context(self) -> None:
        """Test clearing worker context."""
        set_worker_context(worker_id=1)
        clear_worker_context()
        # Should be cleared

    def test_set_context_with_kwargs(self) -> None:
        """Test setting context with additional kwargs."""
        clear_worker_context()
        set_worker_context(worker_id=1, custom_field="value")
        clear_worker_context()


class TestGetLogger:
    """Tests for logger retrieval."""

    def test_get_logger_returns_logger(self) -> None:
        """Test get_logger returns a logger instance."""
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)
        assert "zerg.test" in logger.name

    def test_get_logger_with_worker_id(self) -> None:
        """Test get_logger with worker ID."""
        clear_worker_context()
        logger = get_logger("test", worker_id=1)
        assert isinstance(logger, logging.Logger)
        clear_worker_context()


class TestGetTaskLogger:
    """Tests for task logger retrieval."""

    def test_get_task_logger_returns_adapter(self) -> None:
        """Test get_task_logger returns LoggerAdapter."""
        clear_worker_context()
        logger = get_task_logger("TASK-001")
        assert isinstance(logger, LoggerAdapter)
        clear_worker_context()

    def test_get_task_logger_with_worker_id(self) -> None:
        """Test get_task_logger with worker ID."""
        clear_worker_context()
        logger = get_task_logger("TASK-001", worker_id=1)
        assert isinstance(logger, LoggerAdapter)
        assert logger.extra["task_id"] == "TASK-001"
        clear_worker_context()


class TestSetupLogging:
    """Tests for logging setup."""

    def test_setup_default_logging(self) -> None:
        """Test default logging setup."""
        setup_logging(console_output=True, json_output=False)
        logger = get_logger("test")
        assert logger is not None

    def test_setup_with_file_output(self, tmp_path: Path) -> None:
        """Test logging setup with file output."""
        setup_logging(
            level="debug",
            log_dir=str(tmp_path),
            json_output=True,
            console_output=True,
        )
        logger = get_logger("test")
        logger.info("Test message")

        # Check log file created
        log_file = tmp_path / "zerg.log"
        assert log_file.exists()

    def test_setup_log_levels(self) -> None:
        """Test different log levels."""
        for level in ["debug", "info", "warn", "error"]:
            setup_logging(level=level, console_output=True, json_output=False)
