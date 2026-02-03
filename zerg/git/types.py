"""Shared data types for ZERG git operations."""

from dataclasses import dataclass, field
from enum import StrEnum


class CommitType(StrEnum):
    """Conventional commit types."""

    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    TEST = "test"
    CHORE = "chore"
    PERF = "perf"
    CI = "ci"
    BUILD = "build"
    REVERT = "revert"


@dataclass(frozen=True)
class CommitInfo:
    """Parsed commit information."""

    sha: str
    message: str
    author: str
    date: str
    files: tuple[str, ...] = ()
    commit_type: CommitType | None = None


@dataclass
class DiffAnalysis:
    """Analysis of a diff between two refs."""

    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    by_extension: dict[str, list[str]] = field(default_factory=dict)
    by_directory: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ReviewFinding:
    """A single finding from code review."""

    domain: str
    severity: str
    file: str
    line: int | None
    message: str
    suggestion: str
    rule_id: str | None = None


@dataclass
class RescueSnapshot:
    """Snapshot for git rescue/undo operations."""

    timestamp: str
    branch: str
    commit: str
    operation: str
    tag: str
    description: str
