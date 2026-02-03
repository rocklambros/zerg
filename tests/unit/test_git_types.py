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
    """Tests for CommitType enum."""

    def test_all_conventional_types_present(self) -> None:
        expected = {
            "feat",
            "fix",
            "docs",
            "style",
            "refactor",
            "test",
            "chore",
            "perf",
            "ci",
            "build",
            "revert",
        }
        actual = {ct.value for ct in CommitType}
        assert actual == expected

    def test_string_value(self) -> None:
        assert CommitType.FEAT == "feat"
        assert CommitType.FIX == "fix"

    def test_from_string(self) -> None:
        assert CommitType("feat") is CommitType.FEAT

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            CommitType("invalid")


class TestCommitInfo:
    """Tests for CommitInfo dataclass."""

    def test_minimal(self) -> None:
        info = CommitInfo(sha="abc123", message="msg", author="a", date="2026-01-01")
        assert info.sha == "abc123"
        assert info.files == ()
        assert info.commit_type is None

    def test_full(self) -> None:
        info = CommitInfo(
            sha="abc123",
            message="feat: add login",
            author="dev",
            date="2026-01-01",
            files=("a.py", "b.py"),
            commit_type=CommitType.FEAT,
        )
        assert info.files == ("a.py", "b.py")
        assert info.commit_type is CommitType.FEAT

    def test_frozen(self) -> None:
        info = CommitInfo(sha="x", message="m", author="a", date="d")
        with pytest.raises(AttributeError):
            info.sha = "y"  # type: ignore[misc]


class TestDiffAnalysis:
    """Tests for DiffAnalysis dataclass."""

    def test_defaults(self) -> None:
        diff = DiffAnalysis()
        assert diff.files_changed == []
        assert diff.insertions == 0
        assert diff.deletions == 0
        assert diff.by_extension == {}
        assert diff.by_directory == {}

    def test_populated(self) -> None:
        diff = DiffAnalysis(
            files_changed=["a.py", "b.js"],
            insertions=10,
            deletions=5,
            by_extension={".py": ["a.py"], ".js": ["b.js"]},
            by_directory={"src": ["a.py", "b.js"]},
        )
        assert len(diff.files_changed) == 2
        assert diff.insertions == 10


class TestReviewFinding:
    """Tests for ReviewFinding dataclass."""

    def test_minimal(self) -> None:
        f = ReviewFinding(
            domain="security",
            severity="high",
            file="app.py",
            line=42,
            message="SQL injection risk",
            suggestion="Use parameterized queries",
        )
        assert f.rule_id is None
        assert f.line == 42

    def test_with_rule_id(self) -> None:
        f = ReviewFinding(
            domain="quality",
            severity="medium",
            file="utils.py",
            line=None,
            message="Function too long",
            suggestion="Extract helper",
            rule_id="Q001",
        )
        assert f.rule_id == "Q001"


class TestRescueSnapshot:
    """Tests for RescueSnapshot dataclass."""

    def test_creation(self) -> None:
        snap = RescueSnapshot(
            timestamp="2026-01-01T00:00:00Z",
            branch="main",
            commit="abc123",
            operation="merge",
            tag="rescue/20260101-000000",
            description="Before merge of feature-x",
        )
        assert snap.branch == "main"
        assert snap.operation == "merge"
        assert snap.tag.startswith("rescue/")
