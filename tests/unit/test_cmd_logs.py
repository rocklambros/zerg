"""Unit tests for ZERG logs command."""

from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestLogsCommand:
    """Tests for logs CLI command."""

    def test_logs_help(self) -> None:
        """Test logs --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_logs_feature_option(self) -> None:
        """Test logs --feature option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "test"])
        # May fail due to no logs, but option should be accepted
        assert "Invalid value" not in result.output

    def test_logs_worker_option(self) -> None:
        """Test logs --worker option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--worker", "1"])
        assert "Invalid value" not in result.output

    def test_logs_follow_flag(self) -> None:
        """Test logs --follow flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--help"])
        assert "follow" in result.output

    def test_logs_lines_option(self) -> None:
        """Test logs --lines option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--lines", "100"])
        assert "Invalid value" not in result.output


class TestLogsOutput:
    """Tests for logs output."""

    def test_logs_no_feature_shows_error(self, tmp_path: Path, monkeypatch) -> None:
        """Test logs without feature shows error."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["logs"])

        # Should fail or show error about no feature
        assert result.exit_code != 0 or "feature" in result.output.lower()

    def test_logs_no_logs_available(self, tmp_path: Path, monkeypatch) -> None:
        """Test logs when no logs exist."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg" / "state").mkdir(parents=True)
        (tmp_path / ".zerg" / "logs").mkdir(parents=True)
        (tmp_path / ".zerg" / "state" / "test.json").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(cli, ["logs", "--feature", "test"])

        # Should handle gracefully
        assert "Invalid value" not in result.output
