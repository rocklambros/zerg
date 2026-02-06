"""Unit tests for ZERG worker_main module."""

import argparse
import os
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
        assert args.dry_run is False
        assert args.verbose is False

    @pytest.mark.parametrize(
        "cli_args, attr, expected",
        [
            (["--worker-id", "5"], "worker_id", 5),
            (["--feature", "user-auth"], "feature", "user-auth"),
            (["--worktree", "/tmp/test"], "worktree", Path("/tmp/test")),
            (["--branch", "zerg/test/worker-1"], "branch", "zerg/test/worker-1"),
            (["--dry-run"], "dry_run", True),
            (["-v"], "verbose", True),
            (["--verbose"], "verbose", True),
        ],
        ids=["worker_id", "feature", "worktree", "branch", "dry_run", "verbose_short", "verbose_long"],
    )
    def test_parse_individual_args(self, cli_args, attr, expected) -> None:
        """Test parsing individual arguments."""
        with patch("sys.argv", ["worker_main"] + cli_args):
            args = parse_args()
        assert getattr(args, attr) == expected

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


class TestSetupEnvironment:
    """Tests for environment setup."""

    def test_setup_basic_env(self, tmp_path: Path) -> None:
        """Test basic environment setup."""
        args = argparse.Namespace(worker_id=1, feature="test-feature", worktree=tmp_path, branch="")
        env = setup_environment(args)
        assert env["ZERG_WORKER_ID"] == "1"
        assert env["ZERG_FEATURE"] == "test-feature"

    def test_setup_auto_branch(self, tmp_path: Path) -> None:
        """Test environment setup with auto-generated branch."""
        args = argparse.Namespace(worker_id=2, feature="user-auth", worktree=tmp_path, branch="")
        env = setup_environment(args)
        assert "zerg/user-auth/worker-2" in env["ZERG_BRANCH"]


class TestValidateSetup:
    """Tests for setup validation."""

    @pytest.mark.parametrize(
        "args_overrides, error_keyword",
        [
            ({"feature": ""}, "feature"),
            ({"worktree": Path("/nonexistent/path")}, "worktree"),
            ({"config": Path("/nonexistent/config.yaml")}, "config"),
            ({"task_graph": Path("/nonexistent/task-graph.json")}, "task graph"),
        ],
        ids=["missing_feature", "missing_worktree", "missing_config", "missing_task_graph"],
    )
    def test_validate_missing_fields(self, tmp_path: Path, args_overrides, error_keyword) -> None:
        """Test validation fails for missing fields."""
        defaults = {"feature": "test", "worktree": tmp_path, "config": None, "task_graph": None}
        defaults.update(args_overrides)
        args = argparse.Namespace(**defaults)
        errors = validate_setup(args)
        assert len(errors) > 0
        assert any(error_keyword in e.lower() for e in errors)

    def test_validate_valid_setup(self, tmp_path: Path) -> None:
        """Test validation passes for valid setup."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")
        args = argparse.Namespace(feature="test", worktree=tmp_path, config=config_path, task_graph=None)
        errors = validate_setup(args)
        assert len(errors) == 0


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

    def test_main_worker_protocol_success(self, tmp_path: Path) -> None:
        """Test main successfully runs worker protocol."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("workers: 5")
        mock_protocol = MagicMock()
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
            patch.dict("sys.modules", {"zerg.protocol_state": MagicMock(WorkerProtocol=mock_protocol_class)}),
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
            patch.dict("sys.modules", {"zerg.protocol_state": MagicMock(WorkerProtocol=mock_protocol_class)}),
        ):
            result = main()
        assert result == 130
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
            patch.dict("sys.modules", {"zerg.protocol_state": MagicMock(WorkerProtocol=mock_protocol_class)}),
        ):
            result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "Worker 2 failed" in captured.err


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_args_invalid_worker_id(self) -> None:
        """Test parsing invalid worker ID."""
        with patch("sys.argv", ["worker_main", "--worker-id", "not-a-number"]), pytest.raises(SystemExit):
            parse_args()

    def test_setup_environment_preserves_existing_env(self, tmp_path: Path) -> None:
        """Test setup_environment preserves existing environment variables."""
        args = argparse.Namespace(worker_id=1, feature="test", worktree=tmp_path, branch="branch")
        with patch.dict(os.environ, {"EXISTING_VAR": "value"}, clear=False):
            env = setup_environment(args)
        assert env["EXISTING_VAR"] == "value"
