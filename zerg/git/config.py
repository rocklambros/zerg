"""Git configuration models for ZERG."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from zerg.git.base import GitRunner


class GitCommitConfig(BaseModel):
    """Configuration for git commit behavior."""

    mode: str = Field(default="confirm", pattern="^(auto|confirm|suggest)$")
    conventional: bool = True
    sign: bool = False


class GitPRConfig(BaseModel):
    """Configuration for pull request generation."""

    context_depth: str = Field(default="full", pattern="^(diffs|issues|full)$")
    auto_label: bool = True
    size_warning_loc: int = Field(default=400, ge=100, le=5000)
    reviewer_suggestion: bool = True


class GitReleaseConfig(BaseModel):
    """Configuration for release management."""

    changelog_file: str = "CHANGELOG.md"
    tag_prefix: str = "v"
    github_release: bool = True


class GitRescueConfig(BaseModel):
    """Configuration for git rescue/undo operations."""

    auto_snapshot: bool = True
    ops_log: str = ".zerg/git-ops.log"
    max_snapshots: int = Field(default=20, ge=1, le=100)


class GitReviewConfig(BaseModel):
    """Configuration for code review analysis."""

    domains: list[str] = Field(default_factory=lambda: ["security", "performance", "quality", "architecture"])
    confidence_threshold: float = Field(default=0.8, ge=0.5, le=1.0)


class GitConfig(BaseModel):
    """Top-level git configuration."""

    commit: GitCommitConfig = Field(default_factory=GitCommitConfig)
    pr: GitPRConfig = Field(default_factory=GitPRConfig)
    release: GitReleaseConfig = Field(default_factory=GitReleaseConfig)
    rescue: GitRescueConfig = Field(default_factory=GitRescueConfig)
    review: GitReviewConfig = Field(default_factory=GitReviewConfig)
    context_mode: str = Field(default="auto", pattern="^(solo|team|swarm|auto)$")


def detect_context(runner: GitRunner) -> str:
    """Detect solo/team/swarm context based on repository state.

    Inspects active worker branches to determine the collaboration mode:
    - solo: No worker branches detected
    - team: 1-3 worker branches active
    - swarm: 4+ worker branches active

    Args:
        runner: GitRunner instance for repository inspection

    Returns:
        One of "solo", "team", or "swarm"
    """
    try:
        result = runner._run("branch", "--list", "zerg/*/worker-*", check=False)
        branches = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        count = len(branches)
    except Exception:
        return "solo"

    if count == 0:
        return "solo"
    elif count <= 3:
        return "team"
    else:
        return "swarm"
