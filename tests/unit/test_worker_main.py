"""Unit tests for ZERG worker_main module."""

import argparse
import os
from pathlib import Path
from unittest.mock import patch

from zerg.worker_main import parse_args, setup_environment, validate_setup


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


class TestMainFunction:
    """Tests for main entry point."""

    def test_main_dry_run(self, tmp_path: Path) -> None:
        """Test main with dry-run flag."""
        from zerg.worker_main import main

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
        from zerg.worker_main import main

        with patch("sys.argv", ["worker_main", "--worktree", "/nonexistent"]):
            result = main()

        assert result != 0
