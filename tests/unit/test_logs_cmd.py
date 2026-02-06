"""Unit tests for ZERG logs command - thinned per TSR2-L3-002."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from rich.text import Text

from zerg.cli import cli
from zerg.commands.logs import (
    detect_feature,
    extract_level,
    format_log_entry,
    get_level_priority,
    parse_log_line,
    show_logs,
    stream_logs,
)


class TestDetectFeature:
    """Tests for feature auto-detection from state files."""

    def test_detect_feature_no_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test detection when .zerg/state directory does not exist."""
        monkeypatch.chdir(tmp_path)
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


class TestGetLevelPriority:
    """Tests for log level priority mapping."""

    @pytest.mark.parametrize(
        "level,expected",
        [
            ("debug", 0),
            ("DEBUG", 0),
            ("info", 1),
            ("warning", 2),
            ("error", 3),
            ("critical", 4),
        ],
    )
    def test_known_levels(self, level: str, expected: int) -> None:
        """Test priority for known log levels."""
        assert get_level_priority(level) == expected

    def test_unknown_level_defaults_to_info(self) -> None:
        """Test unknown levels default to info priority (1)."""
        assert get_level_priority("unknown") == 1


class TestParseLogLine:
    """Tests for log line parsing."""

    def test_parse_empty_line(self) -> None:
        """Test parsing empty line returns None."""
        assert parse_log_line("") is None
        assert parse_log_line("   ") is None

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
        assert result["level"] == "info"
        assert result["message"] == "Test message"

    def test_parse_plain_log_line_with_separator(self) -> None:
        """Test parsing plain text log with ' - ' separator."""
        result = parse_log_line("2025-01-26 10:30:45 [INFO] worker:1 - Starting task")
        assert result is not None
        assert result["level"] == "info"
        assert result["message"] == "Starting task"


class TestExtractLevel:
    """Tests for log level extraction from prefix strings."""

    @pytest.mark.parametrize(
        "prefix,expected",
        [
            ("[DEBUG]", "debug"),
            ("[INFO]", "info"),
            ("[WARNING]", "warning"),
            ("[ERROR]", "error"),
            ("[CRITICAL]", "critical"),
            ("debug:", "debug"),
        ],
    )
    def test_extract_known_levels(self, prefix: str, expected: str) -> None:
        """Test extraction of known log levels from various formats."""
        assert extract_level(prefix) == expected

    def test_extract_level_no_match_defaults_info(self) -> None:
        """Test extraction defaults to 'info' when no level found."""
        assert extract_level("no level here") == "info"


class TestFormatLogEntry:
    """Tests for Rich text formatting of log entries."""

    def test_format_basic_entry(self) -> None:
        """Test formatting a basic log entry."""
        entry = {"timestamp": "2025-01-26 10:30:45", "level": "info", "message": "Test message"}
        result = format_log_entry(entry)
        assert isinstance(result, Text)
        plain = result.plain
        assert "INFO" in plain
        assert "Test message" in plain

    def test_format_entry_with_worker_id(self) -> None:
        """Test formatting entry with worker_id field."""
        entry = {"level": "warning", "message": "Worker warning", "worker_id": 3}
        result = format_log_entry(entry)
        assert "W3" in result.plain

    def test_format_entry_with_error(self) -> None:
        """Test formatting entry with error field."""
        entry = {"level": "error", "message": "Operation failed", "error": "Connection timeout"}
        result = format_log_entry(entry)
        assert "error=Connection timeout" in result.plain


class TestShowLogs:
    """Tests for displaying recent logs from files."""

    def test_show_logs_single_file(self, tmp_path: Path) -> None:
        """Test showing logs from a single file."""
        log_file = tmp_path / "worker-0.log"
        log_lines = [
            json.dumps({"timestamp": "2025-01-26 10:00:00", "level": "info", "message": "Line 1"}),
            json.dumps({"timestamp": "2025-01-26 10:00:01", "level": "error", "message": "Line 2"}),
        ]
        log_file.write_text("\n".join(log_lines))

        with patch("zerg.commands.logs.console") as mock_console:
            show_logs([log_file], tail=100, level_priority=1, json_output=False)
            assert mock_console.print.call_count >= 2

    def test_show_logs_level_filtering(self, tmp_path: Path) -> None:
        """Test level filtering excludes lower priority logs."""
        log_file = tmp_path / "worker-0.log"
        log_lines = [
            json.dumps({"timestamp": "2025-01-26 10:00:00", "level": "debug", "message": "Debug"}),
            json.dumps({"timestamp": "2025-01-26 10:00:01", "level": "error", "message": "Error"}),
        ]
        log_file.write_text("\n".join(log_lines))

        with patch("zerg.commands.logs.console") as mock_console:
            show_logs([log_file], tail=100, level_priority=3, json_output=False)
            assert mock_console.print.call_count == 1

    def test_show_logs_tail_limit(self, tmp_path: Path) -> None:
        """Test tail parameter limits output."""
        log_file = tmp_path / "worker-0.log"
        log_lines = [
            json.dumps({"timestamp": f"2025-01-26 10:00:{i:02d}", "level": "info", "message": f"Line {i}"})
            for i in range(20)
        ]
        log_file.write_text("\n".join(log_lines))

        with patch("zerg.commands.logs.console") as mock_console:
            show_logs([log_file], tail=5, level_priority=0, json_output=False)
            assert mock_console.print.call_count == 5

    def test_show_logs_file_read_error(self, tmp_path: Path) -> None:
        """Test handling file read errors gracefully."""
        log_file = tmp_path / "worker-0.log"
        log_file.write_text("test")

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with patch("zerg.commands.logs.logger") as mock_logger:
                show_logs([log_file], tail=100, level_priority=0, json_output=False)
                mock_logger.warning.assert_called()


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
                with open(log_file, "a") as f:
                    f.write(
                        json.dumps({"timestamp": "2025-01-26 10:00:00", "level": "info", "message": "New log entry"})
                        + "\n"
                    )
            elif iteration > 2:
                raise KeyboardInterrupt()

        with patch("time.sleep", side_effect=mock_sleep):
            with patch("zerg.commands.logs.console") as mock_console:
                with contextlib.suppress(KeyboardInterrupt):
                    stream_logs([log_file], level_priority=0, json_output=False)
                calls = [str(c) for c in mock_console.print.call_args_list]
                assert any("New log entry" in str(c) for c in calls)


class TestLogsCLI:
    """Tests for the main logs CLI command."""

    def test_logs_help(self) -> None:
        """Test logs --help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--help"])
        assert result.exit_code == 0
        assert "--feature" in result.output
        assert "--follow" in result.output

    def test_logs_no_feature_no_state_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs without feature and no state directory shows error."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["logs"])
        assert result.exit_code != 0

    def test_logs_with_feature_option(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logs with explicit --feature option."""
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / ".zerg" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "worker-0.log").write_text(
            json.dumps({"timestamp": "2025-01-26 10:00:00", "level": "info", "message": "Test log entry"})
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "my-feature"])
        assert result.exit_code == 0

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
            assert result.exit_code != 0
