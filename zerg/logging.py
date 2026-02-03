"""ZERG structured logging with JSON output and worker context."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import MutableMapping
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zerg.log_writer import StructuredLogWriter

# Thread-local storage for worker context
_worker_context: dict[str, Any] = {}


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add worker context if set
        if _worker_context:
            log_data.update(_worker_context)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        for key in ["task_id", "worker_id", "feature", "level", "gate", "command"]:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """Colored console formatter for human-readable output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.

        Args:
            record: Log record to format

        Returns:
            Colored log string
        """
        color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Build context string
        context_parts = []
        if "worker_id" in _worker_context:
            context_parts.append(f"W{_worker_context['worker_id']}")
        if hasattr(record, "task_id"):
            context_parts.append(record.task_id)

        context = f"[{':'.join(context_parts)}]" if context_parts else ""

        return f"{color}{timestamp} {record.levelname:8s}{self.RESET} {context} {record.getMessage()}"


def set_worker_context(
    worker_id: int | str | None = None,
    feature: str | None = None,
    **kwargs: Any,
) -> None:
    """Set context for all subsequent log messages.

    Args:
        worker_id: Worker ID to include in logs
        feature: Feature name to include in logs
        **kwargs: Additional context fields
    """
    global _worker_context
    _worker_context = {}

    if worker_id is not None:
        _worker_context["worker_id"] = worker_id
    if feature is not None:
        _worker_context["feature"] = feature
    _worker_context.update(kwargs)


def clear_worker_context() -> None:
    """Clear all worker context."""
    global _worker_context
    _worker_context = {}


def get_logger(
    name: str,
    worker_id: int | None = None,
) -> logging.Logger:
    """Get a logger instance with optional worker ID context.

    Args:
        name: Logger name (typically module name)
        worker_id: Optional worker ID for context

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(f"zerg.{name}")

    # Set worker context if provided
    if worker_id is not None:
        set_worker_context(worker_id=worker_id)

    return logger


def setup_logging(
    level: str = "info",
    log_dir: str | Path | None = None,
    json_output: bool = True,
    console_output: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """Set up logging configuration.

    Args:
        level: Log level (debug, info, warn, error)
        log_dir: Directory for log files
        json_output: Whether to output JSON logs to file
        console_output: Whether to output to console
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Get root zerg logger
    root_logger = logging.getLogger("zerg")
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(ConsoleFormatter())
        root_logger.addHandler(console_handler)

    # File handler
    if log_dir and json_output:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path / "zerg.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(file_handler)

    # Prevent propagation to root logger
    root_logger.propagate = False


class LoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """Logger adapter that adds task context to log messages."""

    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        """Process log message with extra context.

        Args:
            msg: Log message
            kwargs: Keyword arguments

        Returns:
            Processed message and kwargs
        """
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs


def get_task_logger(task_id: str, worker_id: int | None = None) -> LoggerAdapter:
    """Get a logger adapter for a specific task.

    Args:
        task_id: Task ID for context
        worker_id: Optional worker ID

    Returns:
        LoggerAdapter with task context
    """
    logger = get_logger("task", worker_id)
    extra: dict[str, Any] = {"task_id": task_id}
    if worker_id is not None:
        extra["worker_id"] = worker_id
    return LoggerAdapter(logger, extra)


class StructuredFileHandler(logging.Handler):
    """Logging handler that writes to a StructuredLogWriter.

    Bridges Python's logging module with ZERG's structured JSONL logging.
    """

    def __init__(self, writer: StructuredLogWriter) -> None:
        """Initialize handler.

        Args:
            writer: StructuredLogWriter to write to
        """
        super().__init__()
        self._writer = writer

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the structured writer.

        Args:
            record: Log record to emit
        """
        try:
            level = record.levelname.lower()
            message = self.format(record) if self.formatter else record.getMessage()
            task_id = getattr(record, "task_id", None)
            phase = getattr(record, "phase", None)
            event = getattr(record, "event", None)
            data = getattr(record, "data", None)
            duration_ms = getattr(record, "duration_ms", None)

            self._writer.emit(
                level=level,
                message=message,
                task_id=task_id,
                phase=phase,
                event=event,
                data=data,
                duration_ms=duration_ms,
            )
        except Exception:
            self.handleError(record)


def setup_structured_logging(
    log_dir: str | Path,
    worker_id: int | str,
    feature: str,
    level: str = "info",
    max_size_mb: int = 50,
) -> StructuredLogWriter:
    """Set up structured JSONL logging for a worker.

    Creates a StructuredLogWriter and attaches a StructuredFileHandler
    to the zerg root logger. Also sets worker context.

    Args:
        log_dir: Base log directory (.zerg/logs)
        worker_id: Worker identifier (int or "orchestrator")
        feature: Feature name
        level: Log level
        max_size_mb: Max file size before rotation

    Returns:
        The StructuredLogWriter instance (caller should close on shutdown)
    """
    from zerg.log_writer import StructuredLogWriter

    writer = StructuredLogWriter(
        log_dir=log_dir,
        worker_id=worker_id,
        feature=feature,
        max_size_mb=max_size_mb,
    )

    log_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger("zerg")
    handler = StructuredFileHandler(writer)
    handler.setLevel(log_level)
    root_logger.addHandler(handler)

    set_worker_context(worker_id=worker_id, feature=feature)

    return writer


# Initialize default logging on import
setup_logging(console_output=True, json_output=False)
