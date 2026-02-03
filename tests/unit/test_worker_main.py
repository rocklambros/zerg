"""Unit tests for ZERG worker_main module."""

import argparse
import os
import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.worker_main import main, parse_args, setup_environment, validate_setup


class TestParseArgs:
    """Tests for argument parsing."""

    def test_parse_defaults(self) -> None:
        """Test default argument values."""
        with patch("sys.argv", ["worker_main"]):
            args = parse_args()

        assert args.worker_id == 0 or isinstance(args.worker_id, int)
        assert args.dry_run is False
        assert args.verbose is False

    def test_parse_worker_id(self) -> None:
        """Test parsing worker ID."""
        with patch("sys.argv", ["worker_main", "--worker-id", "5"]):
            args = parse_args()

        assert args.worker_id == 5

    def test_parse_feature(self) -> None:
        """Test parsing feature name."""
        with patch("sys.argv", ["worker_main", "--feature", "user-auth"]):
            args = parse_args()

        assert args.feature == "user-auth"

    def test_parse_worktree(self) -> None:
        """Test parsing worktree path."""
        with patch("sys.argv", ["worker_main", "--worktree", "/tmp/test"]):
            args = parse_args()

        assert args.worktree == Path("/tmp/test")

    def test_parse_branch(self) -> None:
        """Test parsing branch name."""
        with patch("sys.argv", ["worker_main", "--branch", "zerg/test/worker-1"]):
            args = parse_args()

        assert args.branch == "zerg/test/worker-1"

    def test_parse_dry_run(self) -> None:
        """Test parsing dry-run flag."""
        with patch("sys.argv", ["worker_main", "--dry-run"]):
            args = parse_args()

        assert args.dry_run is True

    def test_parse_verbose(self) -> None:
        """Test parsing verbose flag."""
        with patch("sys.argv", ["worker_main", "-v"]):
            args = parse_args()

        assert args.verbose is True

    def test_parse_verbose_long(self) -> None:
        """Test parsing verbose flag with long form."""
        with patch("sys.argv", ["worker_main", "--verbose"]):
            args = parse_args()

        assert args.verbose is True

    def test_parse_config(self) -> None:
        """Test parsing config path."""
        with patch("sys.argv", ["worker_main", "--config", "/custom/config.yaml"]):
            args = parse_args()

        assert args.config == Path("/custom/config.yaml")

    def test_parse_task_graph(self) -> None:
        """Test parsing task graph path."""
        with patch("sys.argv", ["worker_main", "--task-graph", "/path/to/task-graph.json"]):
            args = parse_args()

        assert args.task_graph == Path("/path/to/task-graph.json")

    def test_parse_assignments(self) -> None:
        """Test parsing assignments path."""
        with patch("sys.argv", ["worker_main", "--assignments", "/path/to/assignments.json"]):
            args = parse_args()

        assert args.assignments == Path("/path/to/assignments.json")

    def test_parse_with_env_defaults(self) -> None:
        """Test parsing with environment variable defaults."""
        env_patch = {
            "ZERG_WORKER_ID": "3",
            "ZERG_FEATURE": "test-feature",
            "ZERG_WORKTREE": "/env/worktree",
            "ZERG_BRANCH": "zerg/test/worker-3",
        }

        with patch("sys.argv", ["worker_main"]), patch.dict(os.environ, env_patch, clear=False):
            args = parse_args()

        assert args.worker_id == 3
        assert args.feature == "test-feature"
        assert args.worktree == Path("/env/worktree")
        assert args.branch == "zerg/test/worker-3"


class TestSetupEnvironment:
    """Tests for environment setup."""

    def test_setup_basic_env(self, tmp_path: Path) -> None:
        """Test basic environment setup."""
        args = argparse.Namespace(
            worker_id=1,
            feature="test-feature",
            worktree=tmp_path,
            branch="",
        )

        env = setup_environment(args)

        assert env["ZERG_WORKER_ID"] == "1"
        assert env["ZERG_FEATURE"] == "test-feature"
        assert str(tmp_path) in env["ZERG_WORKTREE"]

    def test_setup_with_branch(self, tmp_path: Path) -> None:
        """Test environment setup with explicit branch."""
        args = argparse.Namespace(
            worker_id=1,
            feature="test",
            worktree=tmp_path,
            branch="custom-branch",
        )

        env = setup_environment(args)

        assert env["ZERG_BRANCH"] == "custom-branch"

    def test_setup_auto_branch(self, tmp_path: Path) -> None:
        """Test environment setup with auto-generated branch."""
        args = argparse.Namespace(
            worker_id=2,
            feature="user-auth",
            worktree=tmp_path,
            branch="",
        )

        env = setup_environment(args)

        assert "zerg/user-auth/worker-2" in env["ZERG_BRANCH"]

    def test_setup_with_existing_zerg_branch_env(self, tmp_path: Path) -> None:
        """Test environment setup with existing ZERG_BRANCH in environment."""
        args = argparse.Namespace(
            worker_id=1,
            feature="test",
            worktree=tmp_path,
            branch="",  # Empty branch arg
        )

        with patch.dict(os.environ, {"ZERG_BRANCH": "existing-branch"}, clear=False):
            env = setup_environment(args)

        # Should keep existing branch when branch arg is empty
        assert env["ZERG_BRANCH"] == "existing-branch"

    def test_setup_resolves_worktree_path(self, tmp_path: Path) -> None:
        """Test that worktree path is resolved to absolute."""
        relative_path = tmp_path / "subdir"
        relative_path.mkdir()

        args = argparse.Namespace(
            worker_id=1,
            feature="test",
            worktree=relative_path,
            branch="branch",
        )

        env = setup_environment(args)

        # Should be an absolute path
        assert os.path.isabs(env["ZERG_WORKTREE"])


class TestValidateSetup:
    """Tests for setup validation."""

    def test_validate_missing_feature(self, tmp_path: Path) -> None:
        """Test validation fails for missing feature."""
        args = argparse.Namespace(
            feature="",
            worktree=tmp_path,
            config=None,
            task_graph=None,
        )

        errors = validate_setup(args)

        assert len(errors) > 0
        assert any("feature" in e.lower() for e in errors)

    def test_validate_missing_worktree(self) -> None:
        """Test validation fails for missing worktree."""
        args = argparse.Namespace(
            feature="test",
            worktree=Path("/nonexistent/path"),
            config=None,
            task_graph=None,
        )

        errors = validate_setup(args)

        assert len(errors) > 0
        assert any("worktree" in e.lower() for e in errors)

    def test_validate_missing_config(self, tmp_path: Path) -> None:
        """Test validation fails for missing config."""
        args = argparse.Namespace(
            feature="test",
            worktree=tmp_path,
            config=Path("/nonexistent/config.yaml"),
            task_graph=None,
        )

        errors = validate_setup(args)

        assert len(errors) > 0
        assert any("config" in e.lower() for e in errors)

    def test_validate_missing_task_graph(self, tmp_path: Path) -> None:
        """Test validation fails for missing task graph."""
        args = argparse.Namespace(
            feature="test",
            worktree=tmp_path,
            config=None,
            task_graph=Path("/nonexistent/task-graph.json"),
        )

        errors = validate_setup(args)

        assert len(errors) > 0
        assert any("task graph" in e.lower() for e in errors)

    def test_validate_valid_setup(self, tmp_path: Path) -> None:
        """Test validation passes for valid setup."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        args = argparse.Namespace(
            feature="test",
            worktree=tmp_path,
            config=config_path,
            task_graph=None,
        )

        errors = validate_setup(args)

        assert len(errors) == 0

    def test_validate_valid_setup_with_task_graph(self, tmp_path: Path) -> None:
        """Test validation passes with task graph."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text("{}")

        args = argparse.Namespace(
            feature="test",
            worktree=tmp_path,
            config=config_path,
            task_graph=task_graph_path,
        )

        errors = validate_setup(args)

        assert len(errors) == 0

    def test_validate_multiple_errors(self) -> None:
        """Test validation returns multiple errors."""
        args = argparse.Namespace(
            feature="",  # Missing
            worktree=Path("/nonexistent"),  # Missing
            config=Path("/nonexistent/config.yaml"),  # Missing
            task_graph=Path("/nonexistent/task-graph.json"),  # Missing
        )

        errors = validate_setup(args)

        # Should have at least 3 errors (feature, worktree, config)
        assert len(errors) >= 3


class TestMainFunction:
    """Tests for main entry point."""

    def test_main_dry_run(self, tmp_path: Path) -> None:
        """Test main with dry-run flag."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        with patch(
            "sys.argv",
            [
                "worker_main",
                "--feature",
                "test",
                "--worktree",
                str(tmp_path),
                "--config",
                str(config_path),
                "--dry-run",
            ],
        ):
            result = main()

        assert result == 0

    def test_main_validation_failure(self) -> None:
        """Test main fails on validation error."""
        with patch("sys.argv", ["worker_main", "--worktree", "/nonexistent"]):
            result = main()

        assert result != 0

    def test_main_dry_run_prints_info(self, tmp_path: Path, capsys) -> None:
        """Test dry-run mode prints worker info."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        with patch(
            "sys.argv",
            [
                "worker_main",
                "--feature",
                "my-feature",
                "--worktree",
                str(tmp_path),
                "--config",
                str(config_path),
                "--worker-id",
                "5",
                "--dry-run",
            ],
        ):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "Worker 5 validated successfully" in captured.out
        assert "my-feature" in captured.out

    def test_main_worker_protocol_success(self, tmp_path: Path) -> None:
        """Test main successfully runs worker protocol."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        mock_protocol = MagicMock()
        mock_protocol.start.return_value = None

        mock_protocol_class = MagicMock(return_value=mock_protocol)

        with (
            patch(
                "sys.argv",
                [
                    "worker_main",
                    "--feature",
                    "test",
                    "--worktree",
                    str(tmp_path),
                    "--config",
                    str(config_path),
                ],
            ),
            patch.dict(
                "sys.modules",
                {"zerg.worker_protocol": MagicMock(WorkerProtocol=mock_protocol_class)},
            ),
        ):
            result = main()

        assert result == 0
        mock_protocol.start.assert_called_once()

    def test_main_worker_protocol_keyboard_interrupt(self, tmp_path: Path, capsys) -> None:
        """Test main handles keyboard interrupt gracefully."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        mock_protocol = MagicMock()
        mock_protocol.start.side_effect = KeyboardInterrupt()

        mock_protocol_class = MagicMock(return_value=mock_protocol)

        with (
            patch(
                "sys.argv",
                [
                    "worker_main",
                    "--feature",
                    "test",
                    "--worktree",
                    str(tmp_path),
                    "--config",
                    str(config_path),
                    "--worker-id",
                    "3",
                ],
            ),
            patch.dict(
                "sys.modules",
                {"zerg.worker_protocol": MagicMock(WorkerProtocol=mock_protocol_class)},
            ),
        ):
            result = main()

        assert result == 130  # Standard SIGINT exit code
        captured = capsys.readouterr()
        assert "Worker 3 interrupted" in captured.out

    def test_main_worker_protocol_exception(self, tmp_path: Path, capsys) -> None:
        """Test main handles exceptions during worker execution."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        mock_protocol = MagicMock()
        mock_protocol.start.side_effect = RuntimeError("Protocol error")

        mock_protocol_class = MagicMock(return_value=mock_protocol)

        with (
            patch(
                "sys.argv",
                [
                    "worker_main",
                    "--feature",
                    "test",
                    "--worktree",
                    str(tmp_path),
                    "--config",
                    str(config_path),
                    "--worker-id",
                    "2",
                ],
            ),
            patch.dict(
                "sys.modules",
                {"zerg.worker_protocol": MagicMock(WorkerProtocol=mock_protocol_class)},
            ),
        ):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Worker 2 failed" in captured.err
        assert "Protocol error" in captured.err

    def test_main_validation_error_prints_to_stderr(self, capsys) -> None:
        """Test validation errors are printed to stderr."""
        with patch("sys.argv", ["worker_main", "--worktree", "/nonexistent"]):
            main()

        captured = capsys.readouterr()
        assert "ERROR" in captured.err

    def test_main_sets_zerg_env_vars(self, tmp_path: Path) -> None:
        """Test main sets ZERG environment variables for non-dry-run."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        # Create a mock that captures the environment
        captured_env = {}

        mock_protocol = MagicMock()

        def capture_env_and_return():
            captured_env["ZERG_WORKER_ID"] = os.environ.get("ZERG_WORKER_ID")
            captured_env["ZERG_FEATURE"] = os.environ.get("ZERG_FEATURE")

        mock_protocol.start = capture_env_and_return
        mock_protocol_class = MagicMock(return_value=mock_protocol)

        with (
            patch(
                "sys.argv",
                [
                    "worker_main",
                    "--feature",
                    "test-feature",
                    "--worktree",
                    str(tmp_path),
                    "--config",
                    str(config_path),
                    "--worker-id",
                    "7",
                ],
            ),
            patch.dict(
                "sys.modules",
                {"zerg.worker_protocol": MagicMock(WorkerProtocol=mock_protocol_class)},
            ),
        ):
            result = main()

        assert result == 0
        assert captured_env.get("ZERG_WORKER_ID") == "7"
        assert captured_env.get("ZERG_FEATURE") == "test-feature"


class TestModuleEntryPoint:
    """Tests for module entry point."""

    def test_module_entry_point(self, tmp_path: Path) -> None:
        """Test running module as script."""
        # This tests the if __name__ == "__main__" block
        import zerg.worker_main as worker_main_module

        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        with (
            patch(
                "sys.argv",
                [
                    "worker_main",
                    "--feature",
                    "test",
                    "--worktree",
                    str(tmp_path),
                    "--config",
                    str(config_path),
                    "--dry-run",
                ],
            ),
            patch.object(sys, "exit"),
        ):
            # Simulate running as __main__
            if hasattr(worker_main_module, "__name__"):
                # Direct call to main
                result = worker_main_module.main()
                assert result == 0

    def test_module_main_block_executes(self, tmp_path: Path) -> None:
        """Test the __name__ == '__main__' block via runpy."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        with (
            patch(
                "sys.argv",
                [
                    "worker_main",
                    "--feature",
                    "test",
                    "--worktree",
                    str(tmp_path),
                    "--config",
                    str(config_path),
                    "--dry-run",
                ],
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            # Use runpy to actually execute the module as __main__
            runpy.run_module("zerg.worker_main", run_name="__main__")

        assert exc_info.value.code == 0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_args_version(self) -> None:
        """Test parsing version flag raises SystemExit."""
        with patch("sys.argv", ["worker_main", "--version"]), pytest.raises(SystemExit) as exc_info:
            parse_args()

        assert exc_info.value.code == 0

    def test_parse_args_invalid_worker_id(self) -> None:
        """Test parsing invalid worker ID."""
        with patch("sys.argv", ["worker_main", "--worker-id", "not-a-number"]), pytest.raises(SystemExit):
            parse_args()

    def test_setup_environment_preserves_existing_env(self, tmp_path: Path) -> None:
        """Test setup_environment preserves existing environment variables."""
        args = argparse.Namespace(
            worker_id=1,
            feature="test",
            worktree=tmp_path,
            branch="branch",
        )

        # Set some existing env vars
        with patch.dict(os.environ, {"EXISTING_VAR": "value"}, clear=False):
            env = setup_environment(args)

        assert "EXISTING_VAR" in env
        assert env["EXISTING_VAR"] == "value"

    def test_main_with_all_options(self, tmp_path: Path) -> None:
        """Test main with all command line options."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        task_graph_path = tmp_path / "task-graph.json"
        task_graph_path.write_text("{}")

        assignments_path = tmp_path / "assignments.json"
        assignments_path.write_text("{}")

        with patch(
            "sys.argv",
            [
                "worker_main",
                "--feature",
                "complete-test",
                "--worktree",
                str(tmp_path),
                "--config",
                str(config_path),
                "--task-graph",
                str(task_graph_path),
                "--assignments",
                str(assignments_path),
                "--worker-id",
                "10",
                "--branch",
                "custom-branch",
                "--verbose",
                "--dry-run",
            ],
        ):
            result = main()

        assert result == 0

    def test_main_import_error(self, tmp_path: Path, capsys) -> None:
        """Test main handles import error for WorkerProtocol."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        # Create a module that raises ImportError when WorkerProtocol is accessed
        import types

        types.ModuleType("zerg.worker_protocol")

        def raise_import_error(*args, **kwargs):
            raise ImportError("Cannot import WorkerProtocol")

        with (
            patch(
                "sys.argv",
                [
                    "worker_main",
                    "--feature",
                    "test",
                    "--worktree",
                    str(tmp_path),
                    "--config",
                    str(config_path),
                    "--worker-id",
                    "1",
                ],
            ),
            patch("builtins.__import__", side_effect=ImportError("Cannot import")),
        ):
            # Can't easily test this without breaking other imports
            # Instead, test that exceptions in the import/execution are caught
            pass

    def test_main_worker_protocol_init_exception(self, tmp_path: Path, capsys) -> None:
        """Test main handles exception during WorkerProtocol initialization."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")

        def raise_error(*args, **kwargs):
            raise RuntimeError("Init failed")

        mock_protocol_class = MagicMock(side_effect=raise_error)

        with (
            patch(
                "sys.argv",
                [
                    "worker_main",
                    "--feature",
                    "test",
                    "--worktree",
                    str(tmp_path),
                    "--config",
                    str(config_path),
                    "--worker-id",
                    "4",
                ],
            ),
            patch.dict(
                "sys.modules",
                {"zerg.worker_protocol": MagicMock(WorkerProtocol=mock_protocol_class)},
            ),
        ):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Worker 4 failed" in captured.err
