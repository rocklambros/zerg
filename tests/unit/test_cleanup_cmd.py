"""Unit tests for ZERG cleanup command - thinned per TSR2-L3-002."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zerg.cli import cli
from zerg.commands.cleanup import (
    create_cleanup_plan,
    discover_features,
    execute_cleanup,
    show_cleanup_plan,
)


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock ZergConfig."""
    config = MagicMock()
    config.workers = MagicMock()
    config.workers.max_concurrent = 5
    return config


class TestDiscoverFeatures:
    """Tests for discover_features function."""

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

    @patch("zerg.commands.cleanup.GitOps")
    def test_discover_from_branches(self, mock_git_cls: MagicMock, tmp_path: Path, monkeypatch) -> None:
        """Test discover finds features from git branches."""
        monkeypatch.chdir(tmp_path)
        mock_git = MagicMock()
        mock_git_cls.return_value = mock_git

        from zerg.git_ops import BranchInfo

        mock_git.list_branches.return_value = [
            BranchInfo(name="zerg/feature-one/worker-0", commit="abc123"),
            BranchInfo(name="zerg/feature-two/staging", commit="def456"),
            BranchInfo(name="main", commit="789abc"),
        ]

        features = discover_features()
        assert "feature-one" in features
        assert "feature-two" in features

    @patch("zerg.commands.cleanup.GitOps")
    def test_discover_handles_git_error(self, mock_git_cls: MagicMock, tmp_path: Path, monkeypatch) -> None:
        """Test discover handles git errors gracefully."""
        monkeypatch.chdir(tmp_path)
        mock_git_cls.side_effect = Exception("Git error")
        features = discover_features()
        assert isinstance(features, list)


class TestCreateCleanupPlan:
    """Tests for create_cleanup_plan function."""

    def test_plan_structure(self, tmp_path: Path, monkeypatch, mock_config) -> None:
        """Test plan has expected structure."""
        monkeypatch.chdir(tmp_path)
        plan = create_cleanup_plan(["test-feature"], False, False, mock_config)

        assert "features" in plan
        assert "worktrees" in plan
        assert "branches" in plan
        assert "containers" in plan
        assert "state_files" in plan
        assert "log_files" in plan

    def test_plan_includes_worktrees(self, tmp_path: Path, monkeypatch, mock_config) -> None:
        """Test plan finds worktree directories."""
        monkeypatch.chdir(tmp_path)
        worktree_dir = tmp_path / ".zerg" / "worktrees"
        worktree_dir.mkdir(parents=True)
        (worktree_dir / "my-feature-worker-0").mkdir()
        (worktree_dir / "my-feature-worker-1").mkdir()

        plan = create_cleanup_plan(["my-feature"], False, False, mock_config)
        assert len(plan["worktrees"]) == 2

    def test_plan_respects_keep_logs(self, tmp_path: Path, monkeypatch, mock_config) -> None:
        """Test plan respects keep_logs flag."""
        monkeypatch.chdir(tmp_path)
        log_dir = tmp_path / ".zerg" / "logs"
        log_dir.mkdir(parents=True)
        (log_dir / "test.log").write_text("log")

        plan = create_cleanup_plan(["test"], True, False, mock_config)
        assert len(plan["log_files"]) == 0

    def test_plan_respects_keep_branches(self, tmp_path: Path, monkeypatch, mock_config) -> None:
        """Test plan respects keep_branches flag."""
        monkeypatch.chdir(tmp_path)
        plan = create_cleanup_plan(["test"], False, True, mock_config)
        assert len(plan["branches"]) == 0


class TestShowCleanupPlan:
    """Tests for show_cleanup_plan function."""

    def test_show_plan_runs_without_error(self) -> None:
        """Test show_plan doesn't raise errors with empty plan."""
        plan = {
            "features": ["test"],
            "worktrees": [],
            "branches": [],
            "containers": [],
            "state_files": [],
            "log_files": [],
            "dirs_to_remove": [],
        }
        show_cleanup_plan(plan, dry_run=True)
        show_cleanup_plan(plan, dry_run=False)

    def test_show_plan_with_content(self) -> None:
        """Test show_plan displays populated plan."""
        plan = {
            "features": ["test-feature"],
            "worktrees": [".zerg/worktrees/test-feature-worker-0"],
            "branches": ["zerg/test-feature/worker-0"],
            "containers": ["zerg-worker-test-feature-*"],
            "state_files": [".zerg/state/test-feature.json"],
            "log_files": [".zerg/logs/worker-0.log"],
            "dirs_to_remove": [],
        }
        show_cleanup_plan(plan, dry_run=False)


class TestExecuteCleanup:
    """Tests for execute_cleanup function."""

    @patch("zerg.commands.cleanup.WorktreeManager")
    @patch("zerg.commands.cleanup.ContainerManager")
    @patch("zerg.commands.cleanup.GitOps")
    def test_execute_handles_empty_plan(self, mock_git_cls, mock_container_cls, mock_worktree_cls, mock_config) -> None:
        """Test execute handles empty plan."""
        plan = {
            "features": ["test"],
            "worktrees": [],
            "branches": [],
            "containers": [],
            "state_files": [],
            "log_files": [],
        }
        execute_cleanup(plan, mock_config)

    @patch("zerg.commands.cleanup.WorktreeManager")
    @patch("zerg.commands.cleanup.ContainerManager")
    def test_execute_removes_worktrees(
        self,
        mock_container_cls: MagicMock,
        mock_worktree_cls: MagicMock,
        tmp_path: Path,
        mock_config,
    ) -> None:
        """Test execute removes worktrees."""
        mock_worktree = MagicMock()
        mock_worktree_cls.return_value = mock_worktree
        mock_container_cls.return_value = MagicMock()

        wt_path = tmp_path / ".zerg" / "worktrees" / "test-worker-0"
        wt_path.mkdir(parents=True)

        plan = {
            "features": ["test"],
            "worktrees": [str(wt_path)],
            "branches": [],
            "containers": [],
            "state_files": [],
            "log_files": [],
        }
        execute_cleanup(plan, mock_config)
        assert mock_worktree.delete.call_count == 1

    @patch("zerg.commands.cleanup.WorktreeManager")
    @patch("zerg.commands.cleanup.ContainerManager")
    def test_execute_handles_worktree_error(
        self,
        mock_container_cls: MagicMock,
        mock_worktree_cls: MagicMock,
        tmp_path: Path,
        mock_config,
    ) -> None:
        """Test execute handles worktree removal errors."""
        mock_worktree = MagicMock()
        mock_worktree.delete.side_effect = Exception("Worktree error")
        mock_worktree_cls.return_value = mock_worktree
        mock_container_cls.return_value = MagicMock()

        wt_path = tmp_path / ".zerg" / "worktrees" / "test-worker-0"
        wt_path.mkdir(parents=True)

        plan = {
            "features": ["test"],
            "worktrees": [str(wt_path)],
            "branches": [],
            "containers": [],
            "state_files": [],
            "log_files": [],
        }
        execute_cleanup(plan, mock_config)

    @patch("zerg.commands.cleanup.WorktreeManager")
    @patch("zerg.commands.cleanup.ContainerManager")
    @patch("zerg.commands.cleanup.GitOps")
    def test_execute_removes_branches(
        self,
        mock_git_cls: MagicMock,
        mock_container_cls: MagicMock,
        mock_worktree_cls: MagicMock,
        mock_config,
    ) -> None:
        """Test execute removes git branches."""
        mock_git = MagicMock()
        mock_git_cls.return_value = mock_git
        mock_worktree_cls.return_value = MagicMock()
        mock_container_cls.return_value = MagicMock()

        plan = {
            "features": ["test"],
            "worktrees": [],
            "branches": ["zerg/test/worker-0", "zerg/test/worker-1"],
            "containers": [],
            "state_files": [],
            "log_files": [],
        }
        execute_cleanup(plan, mock_config)
        assert mock_git.delete_branch.call_count == 2

    @patch("zerg.commands.cleanup.WorktreeManager")
    @patch("zerg.commands.cleanup.ContainerManager")
    def test_execute_removes_state_files(
        self,
        mock_container_cls: MagicMock,
        mock_worktree_cls: MagicMock,
        tmp_path: Path,
        mock_config,
    ) -> None:
        """Test execute removes state files."""
        mock_worktree_cls.return_value = MagicMock()
        mock_container_cls.return_value = MagicMock()

        state_file = tmp_path / ".zerg" / "state" / "test.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("{}")

        plan = {
            "features": ["test"],
            "worktrees": [],
            "branches": [],
            "containers": [],
            "state_files": [str(state_file)],
            "log_files": [],
        }
        execute_cleanup(plan, mock_config)
        assert not state_file.exists()

    @patch("zerg.commands.cleanup.WorktreeManager")
    @patch("zerg.commands.cleanup.ContainerManager")
    def test_execute_clears_current_feature(
        self,
        mock_container_cls: MagicMock,
        mock_worktree_cls: MagicMock,
        tmp_path: Path,
        mock_config,
    ) -> None:
        """Test execute clears .current-feature when it points to a cleaned feature."""
        mock_worktree_cls.return_value = MagicMock()
        mock_container_cls.return_value = MagicMock()

        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True)
        current_feature_file = gsd_dir / ".current-feature"
        current_feature_file.write_text("test-feature")

        plan = {
            "features": ["test-feature"],
            "worktrees": [],
            "branches": [],
            "containers": [],
            "state_files": [],
            "log_files": [],
        }

        original = os.getcwd()
        os.chdir(tmp_path)
        try:
            execute_cleanup(plan, mock_config)
        finally:
            os.chdir(original)

        assert not current_feature_file.exists()


class TestCleanupCLI:
    """Tests for cleanup CLI command."""

    def test_cleanup_help(self) -> None:
        """Test cleanup --help shows all available options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup", "--help"])
        assert result.exit_code == 0
        assert "--all" in result.output
        assert "--dry-run" in result.output

    def test_cleanup_requires_feature_or_all(self) -> None:
        """Test cleanup fails without --feature or --all."""
        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup"])
        assert result.exit_code == 1

    @patch("zerg.commands.cleanup.ZergConfig")
    @patch("zerg.commands.cleanup.discover_features")
    @patch("zerg.commands.cleanup.create_cleanup_plan")
    @patch("zerg.commands.cleanup.show_cleanup_plan")
    def test_cleanup_dry_run_skips_execution(
        self,
        mock_show,
        mock_plan,
        mock_discover,
        mock_config_cls,
    ) -> None:
        """Test cleanup --dry-run shows plan but doesn't execute."""
        mock_config_cls.load.return_value = MagicMock()
        mock_discover.return_value = ["test-feature"]
        mock_plan.return_value = {
            "features": ["test-feature"],
            "worktrees": [],
            "branches": [],
            "containers": [],
            "state_files": [],
            "log_files": [],
            "dirs_to_remove": [],
        }

        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup", "--all", "--dry-run"])
        assert result.exit_code == 0
        assert "dry run" in result.output.lower()

    @patch("zerg.commands.cleanup.ZergConfig")
    def test_cleanup_handles_exception(self, mock_config_cls: MagicMock) -> None:
        """Test cleanup handles unexpected exceptions."""
        mock_config_cls.load.side_effect = Exception("Config error")
        runner = CliRunner()
        result = runner.invoke(cli, ["cleanup", "--all"])
        assert result.exit_code == 1
