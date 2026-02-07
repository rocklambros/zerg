"""Integration tests for rush command mode flag."""

import pytest
from click.testing import CliRunner

from zerg.cli import cli

pytestmark = pytest.mark.docker


class TestRushCommand:
    """Test suite for rush command --mode option."""

    def test_rush_help_shows_mode_option(self) -> None:
        """Rush command help shows --mode option with all choices.

        Verifies that running 'zerg rush --help' displays:
        - The --mode or -m flag
        - All three mode choices: subprocess, container, auto
        """
        runner = CliRunner()
        result = runner.invoke(cli, ["rush", "--help"])

        assert result.exit_code == 0, f"Help command failed: {result.output}"

        # Check for mode flag
        has_mode_flag = "--mode" in result.output or "-m" in result.output
        assert has_mode_flag, f"Expected --mode flag in help:\n{result.output}"

        # Check for all mode choices
        assert "subprocess" in result.output, f"Expected 'subprocess' in help:\n{result.output}"
        assert "container" in result.output, f"Expected 'container' in help:\n{result.output}"
        assert "auto" in result.output, f"Expected 'auto' in help:\n{result.output}"
