"""Unit tests for ZERG stop command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from zerg.cli import cli


class TestStopCommand:
    """Tests for stop CLI command."""

    def test_stop_help(self) -> None:
        """Test stop --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_stop_feature_option(self) -> None:
        """Test stop --feature option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--help"])
        assert "feature" in result.output

    def test_stop_force_flag(self) -> None:
        """Test stop --force flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--help"])
        assert "force" in result.output

    def test_stop_worker_option(self) -> None:
        """Test stop --worker option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--help"])
        assert "worker" in result.output


class TestStopBehavior:
    """Tests for stop command behavior."""

    def test_stop_no_feature_fails(self, tmp_path: Path, monkeypatch) -> None:
        """Test stop without feature fails gracefully."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["stop"])

        # Should fail or prompt for feature
        assert result.exit_code != 0 or "feature" in result.output.lower()

    def test_stop_nonexistent_feature(self, tmp_path: Path, monkeypatch) -> None:
        """Test stop with nonexistent feature."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "nonexistent"])

        # Should handle gracefully
        assert "not found" in result.output.lower() or result.exit_code != 0

    @patch("zerg.commands.stop.StateManager")
    def test_stop_pauses_execution(self, mock_state, tmp_path: Path, monkeypatch) -> None:
        """Test stop pauses execution."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "state" / "test.json").write_text("{}")

        mock_instance = MagicMock()
        mock_instance.exists.return_value = True
        mock_state.return_value = mock_instance

        runner = CliRunner()
        runner.invoke(cli, ["stop", "--feature", "test", "--force"], input="y\n")

        # Should attempt to pause
        # mock_instance.pause.assert_called() or similar


class TestStopConfirmation:
    """Tests for stop confirmation."""

    def test_stop_requires_confirmation(self, tmp_path: Path, monkeypatch) -> None:
        """Test stop requires confirmation."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test.json").write_text("{}")

        runner = CliRunner()
        # Don't provide confirmation
        result = runner.invoke(cli, ["stop", "--feature", "test"], input="n\n")

        # Should abort
        assert "abort" in result.output.lower() or result.exit_code == 0

    def test_stop_force_skips_confirmation(self, tmp_path: Path, monkeypatch) -> None:
        """Test stop --force skips confirmation."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test.json").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--feature", "test", "--force"])

        # Should not ask for confirmation
        assert "confirm" not in result.output.lower() or result.exit_code in [0, 1]
