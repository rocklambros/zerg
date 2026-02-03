"""Shared types and data models for the ZERG performance analysis system."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = [
    "CategoryScore",
    "DetectedStack",
    "PerformanceFactor",
    "PerformanceFinding",
    "PerformanceReport",
    "Severity",
    "ToolStatus",
]


class Severity(Enum):
    """Severity levels for performance findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @classmethod
    def weight(cls, severity: Severity) -> int:
        """Return the numeric weight for a severity level."""
        weights = {
            cls.CRITICAL: 25,
            cls.HIGH: 10,
            cls.MEDIUM: 5,
            cls.LOW: 2,
            cls.INFO: 0,
        }
        return weights[severity]


@dataclass
class PerformanceFactor:
    """A performance factor from the catalog."""

    id: int
    category: str
    factor: str
    description: str
    cli_tools: list[str]
    security_note: str | None = None


@dataclass
class PerformanceFinding:
    """A single performance finding from a tool adapter."""

    factor_id: int
    factor_name: str
    category: str
    severity: Severity
    message: str
    file: str = ""
    line: int = 0
    tool: str = ""
    rule_id: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "factor_id": self.factor_id,
            "factor_name": self.factor_name,
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "tool": self.tool,
            "rule_id": self.rule_id,
            "suggestion": self.suggestion,
        }


@dataclass
class ToolStatus:
    """Status of an external CLI tool."""

    name: str
    available: bool
    version: str = ""
    factors_covered: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "available": self.available,
            "version": self.version,
            "factors_covered": self.factors_covered,
        }


@dataclass
class CategoryScore:
    """Score for a single performance category."""

    category: str
    score: float | None
    findings: list[PerformanceFinding]
    factors_checked: int
    factors_total: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "score": self.score,
            "findings": [f.to_dict() for f in self.findings],
            "factors_checked": self.factors_checked,
            "factors_total": self.factors_total,
        }


@dataclass
class DetectedStack:
    """Detected project technology stack."""

    languages: list[str]
    frameworks: list[str]
    has_docker: bool = False
    has_kubernetes: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "languages": self.languages,
            "frameworks": self.frameworks,
            "has_docker": self.has_docker,
            "has_kubernetes": self.has_kubernetes,
        }


@dataclass
class PerformanceReport:
    """Complete performance analysis report."""

    overall_score: float | None
    categories: list[CategoryScore]
    tool_statuses: list[ToolStatus]
    findings: list[PerformanceFinding]
    factors_checked: int
    factors_total: int
    detected_stack: DetectedStack

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire report to a dictionary."""
        return {
            "overall_score": self.overall_score,
            "categories": [c.to_dict() for c in self.categories],
            "tool_statuses": [t.to_dict() for t in self.tool_statuses],
            "findings": [f.to_dict() for f in self.findings],
            "factors_checked": self.factors_checked,
            "factors_total": self.factors_total,
            "detected_stack": self.detected_stack.to_dict(),
        }

    def top_issues(self, limit: int = 20) -> list[str]:
        """Return top issues sorted by severity weight (highest first)."""
        sorted_findings = sorted(
            self.findings,
            key=lambda f: Severity.weight(f.severity),
            reverse=True,
        )
        return [f"[{f.severity.value.upper()}] {f.factor_name}: {f.message}" for f in sorted_findings[:limit]]
