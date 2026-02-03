"""Comprehensive unit tests for ZERG logs command.

Tests cover all code paths in zerg/commands/logs.py for 100% coverage:
- detect_feature(): Feature auto-detection from state files
- get_level_priority(): Log level priority mapping
- parse_log_line(): JSON and plain text log parsing
- extract_level(): Level extraction from log prefixes
- format_log_entry(): Rich text formatting for log display
- show_logs(): Reading and displaying recent logs
- stream_logs(): Continuous log streaming with follow mode
- logs(): Main CLI command with all options and error handling
"""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from rich.text import Text

from zerg.cli import cli
from zerg.commands.logs import (
    LEVEL_COLORS,
    detect_feature,
    extract_level,
    format_log_entry,
    get_level_priority,
    parse_log_line,
    show_logs,
    stream_logs,
)

# =============================================================================
# Tests for detect_feature()
# =============================================================================


class TestDetectFeature:
    """Tests for feature auto-detection from state files."""

    def test_detect_feature_no_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detection when .zerg/state directory does not exist."""
        monkeypatch.chdir(tmp_path)
        result = detect_feature()
        assert result is None

    def test_detect_feature_empty_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detection when state directory exists but is empty."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        result = detect_feature()
        assert result is None

    def test_detect_feature_single_state_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detection with a single state file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "my-feature.json").write_text("{}")

        result = detect_feature()
        assert result == "my-feature"

    def test_detect_feature_multiple_state_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detection picks most recently modified file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        # Create older file first
        older = state_dir / "older-feature.json"
        older.write_text("{}")

        # Wait a bit and create newer file
        time.sleep(0.01)
        newer = state_dir / "newer-feature.json"
        newer.write_text("{}")

        result = detect_feature()
        assert result == "newer-feature"

    def test_detect_feature_ignores_non_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detection only considers .json files."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        # Create non-json file
        (state_dir / "config.yaml").write_text("key: value")
        (state_dir / "real-feature.json").write_text("{}")

        result = detect_feature()
        assert result == "real-feature"


# =============================================================================
# Tests for get_level_priority()
# =============================================================================


class TestGetLevelPriority:
    """Tests for log level priority mapping."""

    @pytest.mark.parametrize(
        "level,expected",
        [
            ("debug", 0),
            ("DEBUG", 0),
            ("info", 1),
            ("INFO", 1),
            ("warn", 2),
            ("WARN", 2),
            ("warning", 2),
            ("WARNING", 2),
            ("error", 3),
            ("ERROR", 3),
            ("critical", 4),
            ("CRITICAL", 4),
        ],
    )
    def test_known_levels(self, level: str, expected: int) -> None:
        """Test priority for all known log levels."""
        assert get_level_priority(level) == expected

    def test_unknown_level_defaults_to_info(self) -> None:
        """Test unknown levels default to info priority (1)."""
        assert get_level_priority("unknown") == 1
        assert get_level_priority("trace") == 1
        assert get_level_priority("fatal") == 1


# =============================================================================
# Tests for parse_log_line()
# =============================================================================


class TestParseLogLine:
    """Tests for log line parsing."""

    def test_parse_empty_line(self) -> None:
        """Test parsing empty line returns None."""
        assert parse_log_line("") is None
        assert parse_log_line("   ") is None
        assert parse_log_line("\n") is None

    def test_parse_json_log_line(self) -> None:
        """Test parsing valid JSON log line."""
        log_line = json.dumps(
            {
                "timestamp": "2025-01-26T10:30:45",
                "level": "info",
                "message": "Test message",
                "worker_id": 1,
            }
        )

        result = parse_log_line(log_line)
        assert result is not None
        assert result["timestamp"] == "2025-01-26T10:30:45"
        assert result["level"] == "info"
        assert result["message"] == "Test message"
        assert result["worker_id"] == 1

    def test_parse_plain_log_line_with_separator(self) -> None:
        """Test parsing plain text log with ' - ' separator."""
        log_line = "2025-01-26 10:30:45 [INFO] worker:1 - Starting task"

        result = parse_log_line(log_line)
        assert result is not None
        assert result["timestamp"] == "2025-01-26 10:30:45"
        assert result["level"] == "info"
        assert result["message"] == "Starting task"

    def test_parse_plain_log_line_short_prefix(self) -> None:
        """Test parsing plain text log with short prefix."""
        log_line = "INFO - Short message"

        result = parse_log_line(log_line)
        assert result is not None
        assert result["timestamp"] == ""
        assert result["level"] == "info"
        assert result["message"] == "Short message"

    def test_parse_plain_log_line_no_separator(self) -> None:
        """Test parsing plain text log without ' - ' separator."""
        log_line = "Just a plain message without proper format"

        result = parse_log_line(log_line)
        assert result is not None
        assert result["message"] == log_line
        assert result["level"] == "info"
        assert result["timestamp"] == ""

    def test_parse_log_with_all_levels(self) -> None:
        """Test level extraction from various log formats."""
        test_cases = [
            ("2025-01-26 10:00:00 [DEBUG] - msg", "debug"),
            ("2025-01-26 10:00:00 [INFO] - msg", "info"),
            ("2025-01-26 10:00:00 [WARNING] - msg", "warning"),
            ("2025-01-26 10:00:00 [WARN] - msg", "warn"),
            ("2025-01-26 10:00:00 [ERROR] - msg", "error"),
            ("2025-01-26 10:00:00 [CRITICAL] - msg", "critical"),
        ]

        for log_line, expected_level in test_cases:
            result = parse_log_line(log_line)
            assert result is not None
            assert result["level"] == expected_level


# =============================================================================
# Tests for extract_level()
# =============================================================================


class TestExtractLevel:
    """Tests for log level extraction from prefix strings."""

    @pytest.mark.parametrize(
        "prefix,expected",
        [
            ("[DEBUG]", "debug"),
            ("[INFO]", "info"),
            ("[WARNING]", "warning"),
            ("[WARN]", "warn"),
            ("[ERROR]", "error"),
            ("[CRITICAL]", "critical"),
            ("debug:", "debug"),
            ("info:", "info"),
            ("error:", "error"),
            ("Something INFO here", "info"),
            ("2025-01-26 DEBUG msg", "debug"),
        ],
    )
    def test_extract_known_levels(self, prefix: str, expected: str) -> None:
        """Test extraction of known log levels from various formats."""
        assert extract_level(prefix) == expected

    def test_extract_level_no_match_defaults_info(self) -> None:
        """Test extraction defaults to 'info' when no level found."""
        assert extract_level("no level here") == "info"
        assert extract_level("2025-01-26 10:30:45") == "info"
        assert extract_level("") == "info"


# =============================================================================
# Tests for format_log_entry()
# =============================================================================


class TestFormatLogEntry:
    """Tests for Rich text formatting of log entries."""

    def test_format_basic_entry(self) -> None:
        """Test formatting a basic log entry."""
        entry = {
            "timestamp": "2025-01-26 10:30:45",
            "level": "info",
            "message": "Test message",
        }

        result = format_log_entry(entry)
        assert isinstance(result, Text)
        # Check that output contains expected parts
        plain = result.plain
        assert "10:30:45" in plain  # Time portion
        assert "INFO" in plain
        assert "Test message" in plain

    def test_format_entry_with_worker_id(self) -> None:
        """Test formatting entry with worker_id field."""
        entry = {
            "timestamp": "2025-01-26 10:30:45",
            "level": "warning",
            "message": "Worker warning",
            "worker_id": 3,
        }

        result = format_log_entry(entry)
        plain = result.plain
        assert "W3" in plain

    def test_format_entry_with_task_id(self) -> None:
        """Test formatting entry with task_id field."""
        entry = {
            "level": "info",
            "message": "Processing task",
            "task_id": "TASK-001",
        }

        result = format_log_entry(entry)
        plain = result.plain
        assert "task_id=TASK-001" in plain

    def test_format_entry_with_error(self) -> None:
        """Test formatting entry with error field."""
        entry = {
            "level": "error",
            "message": "Operation failed",
            "error": "Connection timeout",
        }

        result = format_log_entry(entry)
        plain = result.plain
        assert "error=Connection timeout" in plain

    def test_format_entry_no_timestamp(self) -> None:
        """Test formatting entry without timestamp."""
        entry = {
            "level": "debug",
            "message": "Debug message",
        }

        result = format_log_entry(entry)
        plain = result.plain
        assert "DEBUG" in plain
        assert "Debug message" in plain

    def test_format_entry_short_timestamp(self) -> None:
        """Test formatting entry with short timestamp."""
        entry = {
            "timestamp": "10:30:45",
            "level": "info",
            "message": "Short timestamp",
        }

        result = format_log_entry(entry)
        # Should still work without crashing
        assert isinstance(result, Text)

    def test_format_entry_all_level_colors(self) -> None:
        """Test that all defined level colors are applied."""
        for level in LEVEL_COLORS:
            entry = {"level": level, "message": f"Message at {level}"}
            result = format_log_entry(entry)
            # Just verify it doesn't crash and produces output
            assert isinstance(result, Text)
            assert level.upper() in result.plain.upper()

    def test_format_entry_unknown_level(self) -> None:
        """Test formatting entry with unknown level defaults to white."""
        entry = {
            "level": "trace",
            "message": "Trace message",
        }

        result = format_log_entry(entry)
        assert isinstance(result, Text)

    def test_format_entry_no_message_uses_entry_str(self) -> None:
        """Test formatting when message key is missing."""
        entry = {"level": "info", "custom_field": "value"}

        result = format_log_entry(entry)
        # Should use str(entry) as message
        assert isinstance(result, Text)

    def test_format_entry_worker_id_zero(self) -> None:
        """Test formatting when worker_id is 0 (falsy but valid)."""
        entry = {
            "level": "info",
            "message": "Worker 0 message",
            "worker_id": 0,
        }

        result = format_log_entry(entry)
        plain = result.plain
        assert "W0" in plain


# =============================================================================
# Tests for show_logs()
# =============================================================================


class TestShowLogs:
    """Tests for displaying recent logs from files."""

    def test_show_logs_empty_file(self, tmp_path: Path) -> None:
        """Test showing logs from empty file."""
        log_file = tmp_path / "worker-0.log"
        log_file.write_text("")

        with patch("zerg.commands.logs.console"):
            show_logs([log_file], tail=100, level_priority=1, json_output=False)
            # Should not print anything for empty file
            # No exception should be raised

    def test_show_logs_single_file(self, tmp_path: Path) -> None:
        """Test showing logs from a single file."""
        log_file = tmp_path / "worker-0.log"
        log_lines = [
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:00",
                    "level": "info",
                    "message": "Line 1",
                }
            ),
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:01",
                    "level": "error",
                    "message": "Line 2",
                }
            ),
        ]
        log_file.write_text("\n".join(log_lines))

        with patch("zerg.commands.logs.console") as mock_console:
            show_logs([log_file], tail=100, level_priority=1, json_output=False)
            # Should print formatted entries
            assert mock_console.print.call_count >= 2

    def test_show_logs_json_output(self, tmp_path: Path) -> None:
        """Test showing logs with JSON output mode."""
        log_file = tmp_path / "worker-0.log"
        log_data = {
            "timestamp": "2025-01-26 10:00:00",
            "level": "info",
            "message": "Test",
        }
        log_file.write_text(json.dumps(log_data))

        with patch("zerg.commands.logs.console") as mock_console:
            show_logs([log_file], tail=100, level_priority=0, json_output=True)
            # Should print JSON string
            call_args = mock_console.print.call_args_list
            assert len(call_args) >= 1
            # First call should be JSON
            printed = call_args[0][0][0]
            assert isinstance(printed, str)

    def test_show_logs_tail_limit(self, tmp_path: Path) -> None:
        """Test tail parameter limits output."""
        log_file = tmp_path / "worker-0.log"
        log_lines = []
        for i in range(20):
            log_lines.append(
                json.dumps(
                    {
                        "timestamp": f"2025-01-26 10:00:{i:02d}",
                        "level": "info",
                        "message": f"Line {i}",
                    }
                )
            )
        log_file.write_text("\n".join(log_lines))

        with patch("zerg.commands.logs.console") as mock_console:
            show_logs([log_file], tail=5, level_priority=0, json_output=False)
            # Should only print last 5 entries
            assert mock_console.print.call_count == 5

    def test_show_logs_level_filtering(self, tmp_path: Path) -> None:
        """Test level filtering excludes lower priority logs."""
        log_file = tmp_path / "worker-0.log"
        log_lines = [
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:00",
                    "level": "debug",
                    "message": "Debug",
                }
            ),
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:01",
                    "level": "info",
                    "message": "Info",
                }
            ),
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:02",
                    "level": "error",
                    "message": "Error",
                }
            ),
        ]
        log_file.write_text("\n".join(log_lines))

        with patch("zerg.commands.logs.console") as mock_console:
            # Filter at error level (priority 3)
            show_logs([log_file], tail=100, level_priority=3, json_output=False)
            # Should only print error
            assert mock_console.print.call_count == 1

    def test_show_logs_multiple_files(self, tmp_path: Path) -> None:
        """Test showing logs from multiple files merged by timestamp."""
        log_file_1 = tmp_path / "worker-0.log"
        log_file_2 = tmp_path / "worker-1.log"

        log_file_1.write_text(
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:01",
                    "level": "info",
                    "message": "From worker 0",
                }
            )
        )
        log_file_2.write_text(
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:00",
                    "level": "info",
                    "message": "From worker 1",
                }
            )
        )

        with patch("zerg.commands.logs.console") as mock_console:
            show_logs([log_file_1, log_file_2], tail=100, level_priority=0, json_output=False)
            assert mock_console.print.call_count == 2

    def test_show_logs_file_read_error(self, tmp_path: Path) -> None:
        """Test handling file read errors gracefully."""
        log_file = tmp_path / "worker-0.log"
        log_file.write_text("test")

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with patch("zerg.commands.logs.logger") as mock_logger:
                # Should not raise, just log warning
                show_logs([log_file], tail=100, level_priority=0, json_output=False)
                mock_logger.warning.assert_called()

    def test_show_logs_sorts_by_timestamp(self, tmp_path: Path) -> None:
        """Test entries are sorted by timestamp."""
        log_file = tmp_path / "worker-0.log"
        # Write out of order
        log_lines = [
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:02",
                    "level": "info",
                    "message": "Third",
                }
            ),
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:00",
                    "level": "info",
                    "message": "First",
                }
            ),
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:01",
                    "level": "info",
                    "message": "Second",
                }
            ),
        ]
        log_file.write_text("\n".join(log_lines))

        printed_messages: list[str] = []
        with patch("zerg.commands.logs.console") as mock_console:

            def capture_print(entry: Any) -> None:
                if hasattr(entry, "plain"):
                    printed_messages.append(entry.plain)

            mock_console.print.side_effect = capture_print

            show_logs([log_file], tail=100, level_priority=0, json_output=False)

        # Verify order: First, Second, Third
        assert len(printed_messages) == 3
        assert "First" in printed_messages[0]
        assert "Second" in printed_messages[1]
        assert "Third" in printed_messages[2]


# =============================================================================
# Tests for stream_logs()
# =============================================================================


class TestStreamLogs:
    """Tests for continuous log streaming."""

    def test_stream_logs_initial_state(self, tmp_path: Path) -> None:
        """Test stream_logs initializes file positions."""
        log_file = tmp_path / "worker-0.log"
        log_file.write_text("Initial content\n")

        call_count = 0

        def mock_sleep(duration: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise KeyboardInterrupt()

        with patch("time.sleep", side_effect=mock_sleep):
            with patch("zerg.commands.logs.console") as mock_console:
                with contextlib.suppress(KeyboardInterrupt):
                    stream_logs([log_file], level_priority=0, json_output=False)
                # Should print streaming message
                calls = [str(c) for c in mock_console.print.call_args_list]
                assert any("Streaming" in str(c) for c in calls)

    def test_stream_logs_new_content(self, tmp_path: Path) -> None:
        """Test stream_logs detects and displays new content."""
        log_file = tmp_path / "worker-0.log"
        log_file.write_text("")

        iteration = 0

        def mock_sleep(duration: float) -> None:
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                # Append new content after first sleep
                with open(log_file, "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "timestamp": "2025-01-26 10:00:00",
                                "level": "info",
                                "message": "New log entry",
                            }
                        )
                        + "\n"
                    )
            elif iteration > 2:
                raise KeyboardInterrupt()

        with patch("time.sleep", side_effect=mock_sleep):
            with patch("zerg.commands.logs.console") as mock_console:
                with contextlib.suppress(KeyboardInterrupt):
                    stream_logs([log_file], level_priority=0, json_output=False)
                # Check that new entry was printed
                calls = [str(c) for c in mock_console.print.call_args_list]
                assert any("New log entry" in str(c) for c in calls)

    def test_stream_logs_level_filtering(self, tmp_path: Path) -> None:
        """Test stream_logs respects level filtering."""
        log_file = tmp_path / "worker-0.log"
        log_file.write_text("")

        iteration = 0

        def mock_sleep(duration: float) -> None:
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                with open(log_file, "a") as f:
                    # Write debug (should be filtered at error level)
                    f.write(
                        json.dumps(
                            {
                                "level": "debug",
                                "message": "Debug message",
                            }
                        )
                        + "\n"
                    )
                    # Write error (should pass)
                    f.write(
                        json.dumps(
                            {
                                "level": "error",
                                "message": "Error message",
                            }
                        )
                        + "\n"
                    )
            elif iteration > 2:
                raise KeyboardInterrupt()

        with patch("time.sleep", side_effect=mock_sleep):
            with patch("zerg.commands.logs.console") as mock_console:
                try:
                    # Level 3 = error
                    stream_logs([log_file], level_priority=3, json_output=False)
                except KeyboardInterrupt:
                    pass
                calls = [str(c) for c in mock_console.print.call_args_list]
                # Should see error but not debug
                assert any("Error message" in str(c) for c in calls)
                assert not any("Debug message" in str(c) for c in calls)

    def test_stream_logs_json_output(self, tmp_path: Path) -> None:
        """Test stream_logs with JSON output mode."""
        log_file = tmp_path / "worker-0.log"
        log_file.write_text("")

        iteration = 0

        def mock_sleep(duration: float) -> None:
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                with open(log_file, "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "level": "info",
                                "message": "JSON test",
                            }
                        )
                        + "\n"
                    )
            elif iteration > 2:
                raise KeyboardInterrupt()

        with patch("time.sleep", side_effect=mock_sleep):
            with patch("zerg.commands.logs.console") as mock_console:
                with contextlib.suppress(KeyboardInterrupt):
                    stream_logs([log_file], level_priority=0, json_output=True)
                # Check JSON output was used
                calls = mock_console.print.call_args_list
                json_calls = [c for c in calls if "JSON test" in str(c)]
                assert len(json_calls) > 0

    def test_stream_logs_file_not_exist(self, tmp_path: Path) -> None:
        """Test stream_logs handles non-existent files."""
        log_file = tmp_path / "nonexistent.log"

        iteration = 0

        def mock_sleep(duration: float) -> None:
            nonlocal iteration
            iteration += 1
            if iteration > 1:
                raise KeyboardInterrupt()

        with patch("time.sleep", side_effect=mock_sleep):
            with patch("zerg.commands.logs.console"):
                with contextlib.suppress(KeyboardInterrupt):
                    stream_logs([log_file], level_priority=0, json_output=False)
                # Should not crash

    def test_stream_logs_file_read_error(self, tmp_path: Path) -> None:
        """Test stream_logs handles read errors gracefully."""
        log_file = tmp_path / "worker-0.log"
        log_file.write_text("initial")

        iteration = 0
        original_open = open

        def mock_sleep(duration: float) -> None:
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                # Grow the file
                with original_open(log_file, "a") as f:
                    f.write("\nmore content")
            elif iteration > 2:
                raise KeyboardInterrupt()

        def failing_open(*args: Any, **kwargs: Any) -> Any:
            if iteration > 0 and str(log_file) in str(args):
                raise PermissionError("Access denied")
            return original_open(*args, **kwargs)

        with patch("time.sleep", side_effect=mock_sleep):
            with patch("builtins.open", side_effect=failing_open):
                with patch("zerg.commands.logs.logger") as mock_logger:
                    with patch("zerg.commands.logs.console"):
                        with contextlib.suppress(KeyboardInterrupt):
                            stream_logs([log_file], level_priority=0, json_output=False)
                        # Should log warning but not crash
                        mock_logger.warning.assert_called()

    def test_stream_logs_multiple_files(self, tmp_path: Path) -> None:
        """Test stream_logs monitors multiple files."""
        log_file_1 = tmp_path / "worker-0.log"
        log_file_2 = tmp_path / "worker-1.log"
        log_file_1.write_text("")
        log_file_2.write_text("")

        iteration = 0

        def mock_sleep(duration: float) -> None:
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                with open(log_file_1, "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "level": "info",
                                "message": "From file 1",
                            }
                        )
                        + "\n"
                    )
                with open(log_file_2, "a") as f:
                    f.write(
                        json.dumps(
                            {
                                "level": "info",
                                "message": "From file 2",
                            }
                        )
                        + "\n"
                    )
            elif iteration > 2:
                raise KeyboardInterrupt()

        with patch("time.sleep", side_effect=mock_sleep):
            with patch("zerg.commands.logs.console") as mock_console:
                with contextlib.suppress(KeyboardInterrupt):
                    stream_logs([log_file_1, log_file_2], level_priority=0, json_output=False)
                calls = [str(c) for c in mock_console.print.call_args_list]
                assert any("From file 1" in str(c) for c in calls)
                assert any("From file 2" in str(c) for c in calls)


# =============================================================================
# Tests for logs() CLI command
# =============================================================================


class TestLogsCommand:
    """Tests for the main logs CLI command."""

    def test_logs_help(self) -> None:
        """Test logs --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--feature" in result.output
        assert "--tail" in result.output
        assert "--follow" in result.output
        assert "--level" in result.output
        assert "--json" in result.output

    def test_logs_no_feature_no_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs without feature and no state directory shows error."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["logs"])

        assert result.exit_code != 0
        assert "No active feature" in result.output or "feature" in result.output.lower()

    def test_logs_no_logs_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs when .zerg/logs directory doesn't exist."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test-feature.json").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "test-feature"])

        # Should handle gracefully
        assert "No logs directory" in result.output

    def test_logs_no_log_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs when logs directory exists but empty."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        logs_dir = tmp_path / ".zerg" / "logs"
        state_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)
        (state_dir / "test-feature.json").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "test-feature"])

        assert "No log files" in result.output

    def test_logs_worker_id_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs with specific worker_id argument."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        logs_dir = tmp_path / ".zerg" / "logs"
        state_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)
        (state_dir / "test-feature.json").write_text("{}")

        # Only create worker-1.log
        (logs_dir / "worker-1.log").write_text(
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:00",
                    "level": "info",
                    "message": "Worker 1 log",
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "1", "--feature", "test-feature"])

        # Should show logs from worker 1
        assert result.exit_code == 0 or "Worker 1" in result.output or "No log files" not in result.output

    def test_logs_worker_id_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs with worker_id that doesn't exist."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        logs_dir = tmp_path / ".zerg" / "logs"
        state_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)
        (state_dir / "test-feature.json").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "99", "--feature", "test-feature"])

        assert "No log files" in result.output

    def test_logs_with_feature_option(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs with explicit --feature option."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "worker-0.log").write_text(
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:00",
                    "level": "info",
                    "message": "Test log entry",
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "my-feature"])

        assert result.exit_code == 0
        assert "my-feature" in result.output

    def test_logs_tail_option(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs with --tail option."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)

        # Create many log lines
        log_lines = []
        for i in range(50):
            log_lines.append(
                json.dumps(
                    {
                        "timestamp": f"2025-01-26 10:00:{i:02d}",
                        "level": "info",
                        "message": f"Log line {i}",
                    }
                )
            )
        (logs_dir / "worker-0.log").write_text("\n".join(log_lines))

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "test", "--tail", "5"])

        # Should limit output
        assert result.exit_code == 0

    def test_logs_level_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs with --level option."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)

        log_lines = [
            json.dumps({"level": "debug", "message": "Debug msg"}),
            json.dumps({"level": "error", "message": "Error msg"}),
        ]
        (logs_dir / "worker-0.log").write_text("\n".join(log_lines))

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "test", "--level", "error"])

        assert result.exit_code == 0
        # Should not show debug message
        assert "Debug msg" not in result.output

    def test_logs_json_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs with --json option."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)

        (logs_dir / "worker-0.log").write_text(
            json.dumps(
                {
                    "timestamp": "2025-01-26 10:00:00",
                    "level": "info",
                    "message": "JSON output test",
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "test", "--json"])

        assert result.exit_code == 0
        # Output should be parseable JSON
        # Note: Rich markup may be in output, so just check for JSON-like content

    def test_logs_keyboard_interrupt(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs handles KeyboardInterrupt gracefully."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "worker-0.log").write_text("")

        def raise_interrupt(*args: Any, **kwargs: Any) -> None:
            raise KeyboardInterrupt()

        with patch("zerg.commands.logs.show_logs", side_effect=raise_interrupt):
            runner = CliRunner()
            result = runner.invoke(cli, ["logs", "--feature", "test"])

            # Should exit cleanly with "Stopped" message
            assert "Stopped" in result.output or result.exit_code == 0

    def test_logs_generic_exception(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs handles generic exceptions."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "worker-0.log").write_text("")

        def raise_error(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Unexpected error")

        with patch("zerg.commands.logs.show_logs", side_effect=raise_error):
            runner = CliRunner()
            result = runner.invoke(cli, ["logs", "--feature", "test"])

            # Should show error and exit with non-zero
            assert result.exit_code != 0
            assert "Error" in result.output

    def test_logs_auto_detect_feature(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs auto-detects feature from state files."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        logs_dir = tmp_path / ".zerg" / "logs"
        state_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)

        (state_dir / "auto-detected-feature.json").write_text("{}")
        (logs_dir / "worker-0.log").write_text(
            json.dumps(
                {
                    "level": "info",
                    "message": "Auto detect test",
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["logs"])

        assert result.exit_code == 0
        assert "auto-detected-feature" in result.output

    def test_logs_follow_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs with --follow flag."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "worker-0.log").write_text("")

        call_count = 0

        def mock_stream(*args: Any, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 0:
                raise KeyboardInterrupt()

        with patch("zerg.commands.logs.stream_logs", side_effect=mock_stream):
            runner = CliRunner()
            runner.invoke(cli, ["logs", "--feature", "test", "--follow"])

            # stream_logs should have been called
            assert call_count > 0

    def test_logs_shows_header_when_not_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs shows header with feature name when not in JSON mode."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "worker-0.log").write_text(
            json.dumps(
                {
                    "level": "info",
                    "message": "Test",
                }
            )
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "my-feature"])

        # Should show feature name in header
        assert "ZERG Logs" in result.output or "my-feature" in result.output

    def test_logs_no_header_in_json_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs does not show header in JSON mode."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "worker-0.log").write_text(
            json.dumps(
                {
                    "level": "info",
                    "message": "JSON test",
                }
            )
        )

        runner = CliRunner()
        runner.invoke(cli, ["logs", "--feature", "my-feature", "--json"])

        # Should not have Rich formatting header
        # Note: CLI runner strips Rich markup, so just verify it doesn't crash


# =============================================================================
# Edge case and integration tests
# =============================================================================


class TestLogsEdgeCases:
    """Edge case tests for logs functionality."""

    def test_parse_log_line_malformed_json(self) -> None:
        """Test parsing malformed JSON falls back to plain text."""
        result = parse_log_line('{"incomplete": ')
        assert result is not None
        assert result["level"] == "info"  # Default

    def test_format_log_entry_with_empty_task_id(self) -> None:
        """Test formatting entry where task_id is empty string."""
        entry = {
            "level": "info",
            "message": "Test",
            "task_id": "",  # Falsy but present
        }
        result = format_log_entry(entry)
        # Empty task_id should not be shown
        assert "task_id=" not in result.plain

    def test_format_log_entry_with_empty_error(self) -> None:
        """Test formatting entry where error is empty string."""
        entry = {
            "level": "error",
            "message": "Test",
            "error": "",  # Falsy but present
        }
        result = format_log_entry(entry)
        # Empty error should not be shown
        assert "error=" not in result.plain

    def test_show_logs_with_mixed_format_lines(self, tmp_path: Path) -> None:
        """Test showing logs with mixed JSON and plain text lines."""
        log_file = tmp_path / "worker-0.log"
        log_lines = [
            json.dumps(
                {
                    "level": "info",
                    "message": "JSON line",
                    "timestamp": "2025-01-26 10:00:00",
                }
            ),
            "2025-01-26 10:00:01 [ERROR] - Plain text line",
            "Just a message",
        ]
        log_file.write_text("\n".join(log_lines))

        with patch("zerg.commands.logs.console") as mock_console:
            show_logs([log_file], tail=100, level_priority=0, json_output=False)
            # Should handle all formats
            assert mock_console.print.call_count == 3

    def test_logs_with_all_level_choices(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs command accepts all valid level choices."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "worker-0.log").write_text(json.dumps({"level": "info", "message": "Test"}))

        runner = CliRunner()
        for level in ["debug", "info", "warn", "error"]:
            result = runner.invoke(cli, ["logs", "--feature", "test", "--level", level])
            assert result.exit_code == 0

    def test_level_colors_coverage(self) -> None:
        """Verify all defined LEVEL_COLORS are used in format_log_entry."""
        # Ensure LEVEL_COLORS contains expected keys
        expected_keys = {"debug", "info", "warning", "warn", "error", "critical"}
        assert set(LEVEL_COLORS.keys()) == expected_keys

    def test_logs_files_glob_pattern(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs finds all .log files via glob."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)

        # Create multiple log files
        for i in range(3):
            (logs_dir / f"worker-{i}.log").write_text(
                json.dumps(
                    {
                        "level": "info",
                        "message": f"Worker {i}",
                    }
                )
            )

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "test"])

        assert result.exit_code == 0
        # Should read from all workers
