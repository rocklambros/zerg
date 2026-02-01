"""ZERG git package -- structured git operations.

Re-exports core classes for convenient access:
    from zerg.git import GitOps, GitRunner, BranchInfo
"""

from zerg.git.base import GitRunner
from zerg.git.config import GitConfig, detect_context
from zerg.git.ops import BranchInfo, GitOps
from zerg.git.types import (
    CommitInfo,
    CommitType,
    DiffAnalysis,
    RescueSnapshot,
    ReviewFinding,
)

__all__ = [
    "GitRunner",
    "GitOps",
    "BranchInfo",
    "GitConfig",
    "detect_context",
    "CommitType",
    "CommitInfo",
    "DiffAnalysis",
    "ReviewFinding",
    "RescueSnapshot",
]
