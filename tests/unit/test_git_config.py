"""Tests for GitConfig and sub-config models."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from zerg.git.config import (
    GitCommitConfig,
    GitConfig,
    GitPRConfig,
    GitRescueConfig,
    detect_context,
)


class TestGitCommitConfig:
    def test_defaults(self) -> None:
        cfg = GitCommitConfig()
        assert cfg.mode == "confirm" and cfg.conventional is True and cfg.sign is False

    def test_valid_modes(self) -> None:
        for mode in ("auto", "confirm", "suggest"):
            assert GitCommitConfig(mode=mode).mode == mode

    def test_invalid_mode(self) -> None:
        with pytest.raises(ValidationError):
            GitCommitConfig(mode="yolo")


class TestGitPRConfig:
    def test_defaults_and_bounds(self) -> None:
        cfg = GitPRConfig()
        assert cfg.context_depth == "full" and cfg.size_warning_loc == 400
        with pytest.raises(ValidationError):
            GitPRConfig(size_warning_loc=50)


class TestGitRescueConfig:
    def test_defaults_and_bounds(self) -> None:
        cfg = GitRescueConfig()
        assert cfg.auto_snapshot is True and cfg.max_snapshots == 20
        with pytest.raises(ValidationError):
            GitRescueConfig(max_snapshots=0)


class TestGitConfig:
    def test_defaults(self) -> None:
        cfg = GitConfig()
        assert isinstance(cfg.commit, GitCommitConfig) and cfg.context_mode == "auto"

    def test_invalid_context_mode(self) -> None:
        with pytest.raises(ValidationError):
            GitConfig(context_mode="chaos")

    def test_serialization_roundtrip(self) -> None:
        cfg = GitConfig(commit=GitCommitConfig(mode="auto", sign=True), context_mode="team")
        restored = GitConfig(**cfg.model_dump())
        assert restored.commit.mode == "auto" and restored.context_mode == "team"


class TestDetectContext:
    def test_solo_and_swarm(self) -> None:
        runner = MagicMock()
        runner._run.return_value = MagicMock(stdout="")
        assert detect_context(runner) == "solo"

        lines = "\n".join(f"  zerg/feat/worker-{i}" for i in range(5))
        runner._run.return_value = MagicMock(stdout=lines)
        assert detect_context(runner) == "swarm"

    def test_exception_returns_solo(self) -> None:
        runner = MagicMock()
        runner._run.side_effect = Exception("git failed")
        assert detect_context(runner) == "solo"
