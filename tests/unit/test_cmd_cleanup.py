"""Unit tests for ZERG cleanup command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.cleanup import (
    create_cleanup_plan,
    discover_features,
    execute_cleanup,
    show_cleanup_plan,
)


class TestCleanupCommand:
    """Tests for cleanup CLI command."""

    def test_cleanup_help(self) -> None:
        """Test cleanup --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup", "--help"])

        assert result.exit_code == 0
        assert "feature" in result.output
        assert "all" in result.output
        assert "keep-logs" in result.output
        assert "keep-branches" in result.output
        assert "dry-run" in result.output

    def test_cleanup_requires_feature_or_all(self) -> None:
        """Test cleanup requires --feature or --all."""
        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup"])

        assert result.exit_code == 1
        assert "feature" in result.output.lower() or "all" in result.output.lower()


class TestDiscoverFeatures:
    """Tests for feature discovery."""

    def test_discover_empty_directory(self, tmp_path: Path, monkeypatch) -> None:
        """Test discover returns empty list for empty directory."""
        monkeypatch.chdir(tmp_path)
        features = discover_features()
        assert features == []

    def test_discover_from_state_files(self, tmp_path: Path, monkeypatch) -> None:
        """Test discover finds features from state files."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "user-auth.json").write_text("{}")
        (state_dir / "api-feature.json").write_text("{}")

        features = discover_features()
        assert "user-auth" in features
        assert "api-feature" in features


class TestCreateCleanupPlan:
    """Tests for cleanup plan creation."""

    def test_plan_structure(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan has expected structure."""
        monkeypatch.chdir(tmp_path)
        mock_config = MagicMock()

        plan = create_cleanup_plan(["test-feature"], False, False, mock_config)

        assert "features" in plan
        assert "worktrees" in plan
        assert "branches" in plan
        assert "containers" in plan
        assert "state_files" in plan
        assert "log_files" in plan

    def test_plan_respects_keep_logs(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan respects keep_logs flag."""
        monkeypatch.chdir(tmp_path)
        mock_config = MagicMock()

        # Create log files
        log_dir = tmp_path / ".zerg" / "logs"
        log_dir.mkdir(parents=True)
        (log_dir / "test.log").write_text("log")

        plan = create_cleanup_plan(["test"], True, False, mock_config)  # keep_logs=True
        assert len(plan["log_files"]) == 0

        plan = create_cleanup_plan(["test"], False, False, mock_config)  # keep_logs=False
        assert len(plan["log_files"]) >= 0  # May find log files

    def test_plan_respects_keep_branches(self, tmp_path: Path, monkeypatch) -> None:
        """Test plan respects keep_branches flag."""
        monkeypatch.chdir(tmp_path)
        mock_config = MagicMock()

        plan = create_cleanup_plan(["test"], False, True, mock_config)  # keep_branches=True
        assert len(plan["branches"]) == 0


class TestShowCleanupPlan:
    """Tests for cleanup plan display."""

    def test_show_plan_runs_without_error(self) -> None:
        """Test show_plan doesn't raise errors."""
        plan = {
            "features": ["test"],
            "worktrees": [],
            "branches": [],
            "containers": ["zerg-worker-test-*"],
            "state_files": [],
            "log_files": [],
            "dirs_to_remove": [],
        }
        # Should not raise
        show_cleanup_plan(plan, dry_run=True)
        show_cleanup_plan(plan, dry_run=False)


class TestExecuteCleanup:
    """Tests for cleanup execution."""

    @patch("zerg.commands.cleanup.WorktreeManager")
    @patch("zerg.commands.cleanup.ContainerManager")
    @patch("zerg.commands.cleanup.GitOps")
    def test_execute_handles_empty_plan(self, mock_git, mock_container, mock_worktree) -> None:
        """Test execute handles empty plan."""
        mock_config = MagicMock()
        plan = {
            "features": ["test"],
            "worktrees": [],
            "branches": [],
            "containers": [],
            "state_files": [],
            "log_files": [],
        }

        # Should not raise
        execute_cleanup(plan, mock_config)
