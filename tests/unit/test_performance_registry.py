"""Tests for zerg.performance.tool_registry module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rich.console import Console

from zerg.performance.tool_registry import ToolRegistry
from zerg.performance.types import ToolStatus


class TestToolRegistryInit:
    """Tests for ToolRegistry initialization."""

    def test_has_11_tool_specs(self) -> None:
        registry = ToolRegistry()
        assert len(registry.TOOL_SPECS) == 11

    def test_all_specs_have_names(self) -> None:
        registry = ToolRegistry()
        for key, spec in registry.TOOL_SPECS.items():
            assert spec.name == key


class TestCheckAvailability:
    """Tests for ToolRegistry.check_availability()."""

    @patch("shutil.which", return_value=None)
    def test_all_unavailable_when_which_returns_none(self, mock_which: MagicMock) -> None:
        registry = ToolRegistry()
        statuses = registry.check_availability()
        assert len(statuses) == 11
        for status in statuses:
            assert status.available is False

    @patch("shutil.which", return_value=None)
    def test_get_available_empty_when_nothing_found(self, mock_which: MagicMock) -> None:
        registry = ToolRegistry()
        available = registry.get_available()
        assert available == []


class TestGetAvailable:
    """Tests for ToolRegistry.get_available() with mocked tools."""

    def test_returns_available_tool_names(self) -> None:
        registry = ToolRegistry()
        target_tools = {"semgrep", "radon", "cloc"}

        def mock_which(cmd: str) -> str | None:
            if cmd in target_tools:
                return f"/usr/bin/{cmd}"
            return None

        with (
            patch("zerg.performance.tool_registry.shutil.which", side_effect=mock_which),
            patch("zerg.performance.tool_registry.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(stdout="1.0.0\n", stderr="")
            available = registry.get_available()

        assert "semgrep" in available
        assert "radon" in available
        assert "cloc" in available


class TestPrintAdvisory:
    """Tests for ToolRegistry.print_advisory()."""

    def test_print_advisory_does_not_crash(self) -> None:
        registry = ToolRegistry()
        console = Console(file=MagicMock(), force_terminal=False)
        missing = [
            ToolStatus(name="semgrep", available=False),
            ToolStatus(name="radon", available=False),
        ]
        # Should not raise
        registry.print_advisory(console, missing)

    def test_print_advisory_empty_missing(self) -> None:
        registry = ToolRegistry()
        console = Console(file=MagicMock(), force_terminal=False)
        # Should not raise and should return early
        registry.print_advisory(console, [])
