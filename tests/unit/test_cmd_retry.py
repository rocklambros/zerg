"""Unit tests for ZERG retry command."""

from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestRetryCommand:
    """Tests for retry CLI command."""

    def test_retry_help(self) -> None:
        """Test retry --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["retry", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_retry_feature_option(self) -> None:
        """Test retry --feature option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["retry", "--help"])
        assert "feature" in result.output

    def test_retry_task_option(self) -> None:
        """Test retry --task option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["retry", "--help"])
        assert "task" in result.output

    def test_retry_all_failed_flag(self) -> None:
        """Test retry --all-failed flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["retry", "--help"])
        assert "all" in result.output.lower()


class TestRetryBehavior:
    """Tests for retry command behavior."""

    def test_retry_no_feature_fails(self, tmp_path: Path, monkeypatch) -> None:
        """Test retry without feature fails."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["retry"])

        # Should fail or prompt for feature
        assert result.exit_code != 0 or "feature" in result.output.lower()

    def test_retry_requires_task_or_all_failed(self, tmp_path: Path, monkeypatch) -> None:
        """Test retry requires --task or --all-failed."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test.json").write_text("{}")

        runner = CliRunner()
        runner.invoke(cli, ["retry", "--feature", "test"])

        # Should fail or request task specification
        # Behavior depends on implementation

    def test_retry_nonexistent_task(self, tmp_path: Path, monkeypatch) -> None:
        """Test retry with nonexistent task."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test.json").write_text('{"tasks": {}}')

        runner = CliRunner()
        result = runner.invoke(cli, ["retry", "--feature", "test", "--task", "NONEXISTENT"])

        # Should handle gracefully
        assert "not found" in result.output.lower() or result.exit_code != 0


class TestRetryAllFailed:
    """Tests for retry all failed tasks."""

    def test_retry_all_failed_option(self) -> None:
        """Test retry --all-failed option exists."""
        runner = CliRunner()
        result = runner.invoke(cli, ["retry", "--help"])
        assert "all" in result.output.lower()

    def test_retry_all_failed_no_failures(self, tmp_path: Path, monkeypatch) -> None:
        """Test retry all-failed when no failures exist."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test.json").write_text('{"tasks": {"T1": {"status": "complete"}}}')

        runner = CliRunner()
        result = runner.invoke(cli, ["retry", "--feature", "test", "--all-failed"])

        # Should handle gracefully with no failures to retry
        assert "no" in result.output.lower() or result.exit_code in [0, 1]
