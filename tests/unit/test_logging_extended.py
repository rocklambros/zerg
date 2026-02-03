"""Unit tests for structured logging integration (setup_structured_logging)."""

import json
import logging
from pathlib import Path

from zerg.logging import (
    StructuredFileHandler,
    clear_worker_context,
    get_logger,
    setup_structured_logging,
)


class TestSetupStructuredLogging:
    """Tests for setup_structured_logging function."""

    def test_creates_handler_and_writer(self, tmp_path: Path) -> None:
        """Test setup_structured_logging creates a handler attached to zerg logger."""
        writer = setup_structured_logging(
            log_dir=tmp_path,
            worker_id=0,
            feature="test-feature",
        )
        try:
            root = logging.getLogger("zerg")
            structured_handlers = [h for h in root.handlers if isinstance(h, StructuredFileHandler)]
            assert len(structured_handlers) >= 1
        finally:
            # Clean up: remove the handler and close the writer
            root = logging.getLogger("zerg")
            root.handlers = [h for h in root.handlers if not isinstance(h, StructuredFileHandler)]
            writer.close()
            clear_worker_context()

    def test_log_entries_written_to_jsonl(self, tmp_path: Path) -> None:
        """Test log entries are written to worker JSONL file via standard logging."""
        # Ensure root logger level allows info+ messages
        root = logging.getLogger("zerg")
        original_level = root.level

        writer = setup_structured_logging(
            log_dir=tmp_path,
            worker_id=1,
            feature="my-feature",
            level="debug",
        )
        try:
            # Ensure root logger level is low enough
            root.setLevel(logging.DEBUG)

            logger = get_logger("test_structured")
            logger.info("Structured log message")
            logger.warning("A warning")

            # Flush the writer to ensure data is written
            writer.close()

            jsonl_file = tmp_path / "workers" / "worker-1.jsonl"
            assert jsonl_file.exists()

            content = jsonl_file.read_text().strip()
            assert content, "JSONL file should not be empty"
            lines = content.split("\n")
            assert len(lines) >= 2

            entry = json.loads(lines[0])
            assert entry["level"] == "info"
            assert "Structured log message" in entry["message"]
            assert entry["worker_id"] == 1
            assert entry["feature"] == "my-feature"
        finally:
            root.handlers = [h for h in root.handlers if not isinstance(h, StructuredFileHandler)]
            root.setLevel(original_level)
            clear_worker_context()

    def test_worker_context_injection(self, tmp_path: Path) -> None:
        """Test worker_id and feature are injected into log entries."""
        root = logging.getLogger("zerg")
        original_level = root.level

        writer = setup_structured_logging(
            log_dir=tmp_path,
            worker_id=3,
            feature="context-test",
        )
        try:
            root.setLevel(logging.DEBUG)
            logger = get_logger("test_context")
            logger.info("context check")
            writer.close()

            jsonl_file = tmp_path / "workers" / "worker-3.jsonl"
            content = jsonl_file.read_text().strip()
            assert content, "JSONL file should not be empty"
            entry = json.loads(content.split("\n")[0])
            assert entry["worker_id"] == 3
            assert entry["feature"] == "context-test"
        finally:
            root.handlers = [h for h in root.handlers if not isinstance(h, StructuredFileHandler)]
            root.setLevel(original_level)
            clear_worker_context()

    def test_returns_writer_instance(self, tmp_path: Path) -> None:
        """Test function returns StructuredLogWriter that can be closed."""
        from zerg.log_writer import StructuredLogWriter

        writer = setup_structured_logging(
            log_dir=tmp_path,
            worker_id=0,
            feature="test",
        )
        try:
            assert isinstance(writer, StructuredLogWriter)
        finally:
            root = logging.getLogger("zerg")
            root.handlers = [h for h in root.handlers if not isinstance(h, StructuredFileHandler)]
            writer.close()
            clear_worker_context()


class TestStructuredFileHandler:
    """Tests for StructuredFileHandler."""

    def test_emit_writes_to_writer(self, tmp_path: Path) -> None:
        """Test handler emit writes entries through writer."""
        from zerg.log_writer import StructuredLogWriter

        writer = StructuredLogWriter(tmp_path, worker_id=0, feature="test")
        handler = StructuredFileHandler(writer)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="handler test",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        writer.close()

        jsonl_file = tmp_path / "workers" / "worker-0.jsonl"
        entry = json.loads(jsonl_file.read_text().strip())
        assert "handler test" in entry["message"]

    def test_emit_extracts_extra_fields(self, tmp_path: Path) -> None:
        """Test handler extracts task_id, phase, event from record."""
        from zerg.log_writer import StructuredLogWriter

        writer = StructuredLogWriter(tmp_path, worker_id=0, feature="test")
        handler = StructuredFileHandler(writer)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="with extras",
            args=(),
            exc_info=None,
        )
        record.task_id = "T1.1"
        record.phase = "execute"
        record.event = "task_started"

        handler.emit(record)
        writer.close()

        jsonl_file = tmp_path / "workers" / "worker-0.jsonl"
        entry = json.loads(jsonl_file.read_text().strip())
        assert entry["task_id"] == "T1.1"
        assert entry["phase"] == "execute"
        assert entry["event"] == "task_started"
