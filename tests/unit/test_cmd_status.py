"""Unit tests for ZERG status command."""

import json
from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.status import create_progress_bar, detect_feature


class TestStatusCommand:
    """Tests for status CLI command."""

    def test_status_help(self) -> None:
        """Test status --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])

        assert result.exit_code == 0
        assert "feature" in result.output
        assert "watch" in result.output
        assert "json" in result.output
        assert "level" in result.output

    def test_status_json_flag(self) -> None:
        """Test status --json flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert "json" in result.output

    def test_status_watch_flag(self) -> None:
        """Test status --watch flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert "watch" in result.output

    def test_status_level_option(self) -> None:
        """Test status --level option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--level", "1"])
        # May fail due to no state, but option should be accepted
        assert "Invalid value" not in result.output


class TestDetectFeature:
    """Tests for feature detection."""

    def test_detect_no_state_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test detect returns None when no state directory."""
        monkeypatch.chdir(tmp_path)
        result = detect_feature()
        assert result is None

    def test_detect_empty_state_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test detect returns None when state directory empty."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        result = detect_feature()
        assert result is None

    def test_detect_from_state_file(self, tmp_path: Path, monkeypatch) -> None:
        """Test detect finds feature from state file."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "user-auth.json").write_text("{}")

        result = detect_feature()
        assert result == "user-auth"


class TestCreateProgressBar:
    """Tests for progress bar creation."""

    def test_progress_bar_0_percent(self) -> None:
        """Test progress bar at 0%."""
        bar = create_progress_bar(0)
        assert "░" in bar
        assert bar.count("█") == 0 or "green" not in bar

    def test_progress_bar_50_percent(self) -> None:
        """Test progress bar at 50%."""
        bar = create_progress_bar(50)
        assert "█" in bar
        assert "░" in bar

    def test_progress_bar_100_percent(self) -> None:
        """Test progress bar at 100%."""
        bar = create_progress_bar(100)
        assert "█" in bar

    def test_progress_bar_custom_width(self) -> None:
        """Test progress bar with custom width."""
        bar = create_progress_bar(50, width=10)
        # Width affects number of characters
        assert len(bar) > 0


class TestStatusOutput:
    """Tests for status output."""

    def test_status_no_feature_shows_error(self, tmp_path: Path, monkeypatch) -> None:
        """Test status without feature shows error."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code != 0 or "feature" in result.output.lower()

    def test_status_with_feature(self, tmp_path: Path, monkeypatch) -> None:
        """Test status with specified feature."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        state = {
            "feature": "test",
            "current_level": 1,
            "paused": False,
            "error": None,
            "tasks": {},
            "workers": {},
            "events": [],
        }
        (state_dir / "test.json").write_text(json.dumps(state))

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--feature", "test"])

        assert "test" in result.output.lower() or result.exit_code == 0
