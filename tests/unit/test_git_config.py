"""Tests for GitConfig and sub-config models."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from zerg.git.config import (
    GitCommitConfig,
    GitConfig,
    GitPRConfig,
    GitReleaseConfig,
    GitRescueConfig,
    GitReviewConfig,
    detect_context,
)


class TestGitCommitConfig:
    """Tests for GitCommitConfig."""

    def test_defaults(self) -> None:
        cfg = GitCommitConfig()
        assert cfg.mode == "confirm"
        assert cfg.conventional is True
        assert cfg.sign is False

    def test_valid_modes(self) -> None:
        for mode in ("auto", "confirm", "suggest"):
            cfg = GitCommitConfig(mode=mode)
            assert cfg.mode == mode

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GitCommitConfig(mode="yolo")


class TestGitPRConfig:
    """Tests for GitPRConfig."""

    def test_defaults(self) -> None:
        cfg = GitPRConfig()
        assert cfg.context_depth == "full"
        assert cfg.auto_label is True
        assert cfg.size_warning_loc == 400
        assert cfg.reviewer_suggestion is True

    def test_size_warning_bounds(self) -> None:
        cfg = GitPRConfig(size_warning_loc=100)
        assert cfg.size_warning_loc == 100
        cfg = GitPRConfig(size_warning_loc=5000)
        assert cfg.size_warning_loc == 5000

    def test_size_warning_out_of_bounds(self) -> None:
        with pytest.raises(ValidationError):
            GitPRConfig(size_warning_loc=50)
        with pytest.raises(ValidationError):
            GitPRConfig(size_warning_loc=10000)

    def test_invalid_context_depth(self) -> None:
        with pytest.raises(ValidationError):
            GitPRConfig(context_depth="minimal")


class TestGitReleaseConfig:
    """Tests for GitReleaseConfig."""

    def test_defaults(self) -> None:
        cfg = GitReleaseConfig()
        assert cfg.changelog_file == "CHANGELOG.md"
        assert cfg.tag_prefix == "v"
        assert cfg.github_release is True


class TestGitRescueConfig:
    """Tests for GitRescueConfig."""

    def test_defaults(self) -> None:
        cfg = GitRescueConfig()
        assert cfg.auto_snapshot is True
        assert cfg.ops_log == ".zerg/git-ops.log"
        assert cfg.max_snapshots == 20

    def test_max_snapshots_bounds(self) -> None:
        cfg = GitRescueConfig(max_snapshots=1)
        assert cfg.max_snapshots == 1
        cfg = GitRescueConfig(max_snapshots=100)
        assert cfg.max_snapshots == 100
        with pytest.raises(ValidationError):
            GitRescueConfig(max_snapshots=0)
        with pytest.raises(ValidationError):
            GitRescueConfig(max_snapshots=101)


class TestGitReviewConfig:
    """Tests for GitReviewConfig."""

    def test_defaults(self) -> None:
        cfg = GitReviewConfig()
        assert "security" in cfg.domains
        assert cfg.confidence_threshold == 0.8

    def test_confidence_bounds(self) -> None:
        cfg = GitReviewConfig(confidence_threshold=0.5)
        assert cfg.confidence_threshold == 0.5
        cfg = GitReviewConfig(confidence_threshold=1.0)
        assert cfg.confidence_threshold == 1.0
        with pytest.raises(ValidationError):
            GitReviewConfig(confidence_threshold=0.3)
        with pytest.raises(ValidationError):
            GitReviewConfig(confidence_threshold=1.1)


class TestGitConfig:
    """Tests for top-level GitConfig."""

    def test_defaults(self) -> None:
        cfg = GitConfig()
        assert isinstance(cfg.commit, GitCommitConfig)
        assert isinstance(cfg.pr, GitPRConfig)
        assert isinstance(cfg.release, GitReleaseConfig)
        assert isinstance(cfg.rescue, GitRescueConfig)
        assert isinstance(cfg.review, GitReviewConfig)
        assert cfg.context_mode == "auto"

    def test_valid_context_modes(self) -> None:
        for mode in ("solo", "team", "swarm", "auto"):
            cfg = GitConfig(context_mode=mode)
            assert cfg.context_mode == mode

    def test_invalid_context_mode(self) -> None:
        with pytest.raises(ValidationError):
            GitConfig(context_mode="chaos")

    def test_serialization_roundtrip(self) -> None:
        cfg = GitConfig(
            commit=GitCommitConfig(mode="auto", sign=True),
            context_mode="team",
        )
        data = cfg.model_dump()
        restored = GitConfig(**data)
        assert restored.commit.mode == "auto"
        assert restored.commit.sign is True
        assert restored.context_mode == "team"


class TestDetectContext:
    """Tests for detect_context function."""

    def _make_runner(self, stdout: str) -> MagicMock:
        runner = MagicMock()
        result = MagicMock()
        result.stdout = stdout
        runner._run.return_value = result
        return runner

    def test_solo_no_branches(self) -> None:
        runner = self._make_runner("")
        assert detect_context(runner) == "solo"

    def test_team_few_branches(self) -> None:
        runner = self._make_runner("  zerg/feat/worker-0\n  zerg/feat/worker-1\n")
        assert detect_context(runner) == "team"

    def test_swarm_many_branches(self) -> None:
        lines = "\n".join(f"  zerg/feat/worker-{i}" for i in range(5))
        runner = self._make_runner(lines)
        assert detect_context(runner) == "swarm"

    def test_exception_returns_solo(self) -> None:
        runner = MagicMock()
        runner._run.side_effect = Exception("git failed")
        assert detect_context(runner) == "solo"
