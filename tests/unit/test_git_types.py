"""Tests for ZERG git types."""

import pytest

from zerg.git.types import (
    CommitInfo,
    CommitType,
    DiffAnalysis,
    RescueSnapshot,
    ReviewFinding,
)


class TestCommitType:
    def test_all_conventional_types(self) -> None:
        expected = {"feat", "fix", "docs", "style", "refactor", "test", "chore", "perf", "ci", "build", "revert"}
        assert {ct.value for ct in CommitType} == expected

    def test_from_string_and_invalid(self) -> None:
        assert CommitType("feat") is CommitType.FEAT
        with pytest.raises(ValueError):
            CommitType("invalid")


class TestCommitInfo:
    def test_creation_and_frozen(self) -> None:
        info = CommitInfo(
            sha="abc123",
            message="feat: add",
            author="dev",
            date="2026-01-01",
            files=("a.py",),
            commit_type=CommitType.FEAT,
        )
        assert info.sha == "abc123" and info.files == ("a.py",)
        minimal = CommitInfo(sha="x", message="m", author="a", date="d")
        assert minimal.files == () and minimal.commit_type is None
        with pytest.raises(AttributeError):
            minimal.sha = "y"  # type: ignore[misc]


class TestDiffAnalysis:
    def test_defaults_and_populated(self) -> None:
        assert DiffAnalysis().files_changed == [] and DiffAnalysis().insertions == 0
        diff = DiffAnalysis(files_changed=["a.py"], insertions=10, deletions=5)
        assert diff.insertions == 10


class TestReviewFinding:
    def test_creation(self) -> None:
        f = ReviewFinding(
            domain="security",
            severity="high",
            file="app.py",
            line=42,
            message="SQL injection risk",
            suggestion="Use params",
        )
        assert f.rule_id is None and f.line == 42


class TestRescueSnapshot:
    def test_creation(self) -> None:
        snap = RescueSnapshot(
            timestamp="2026-01-01T00:00:00Z",
            branch="main",
            commit="abc123",
            operation="merge",
            tag="rescue/20260101",
            description="Before merge",
        )
        assert snap.branch == "main" and snap.operation == "merge"
