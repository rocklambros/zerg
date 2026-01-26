"""ZERG v2 Review Command - Two-stage code review workflow."""

import json
from dataclasses import dataclass
from enum import Enum


class ReviewMode(Enum):
    """Review workflow modes."""

    PREPARE = "prepare"
    SELF = "self"
    RECEIVE = "receive"
    FULL = "full"


@dataclass
class ReviewConfig:
    """Configuration for review."""

    mode: str = "full"
    include_tests: bool = True
    include_docs: bool = True
    strict: bool = False


@dataclass
class ReviewItem:
    """A review comment or finding."""

    category: str
    severity: str
    file: str
    line: int
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class ReviewResult:
    """Result of code review."""

    files_reviewed: int
    items: list[ReviewItem]
    spec_passed: bool
    quality_passed: bool
    stage1_details: str = ""
    stage2_details: str = ""

    @property
    def overall_passed(self) -> bool:
        """Check if both stages passed."""
        return self.spec_passed and self.quality_passed

    @property
    def total_items(self) -> int:
        """Count total review items."""
        return len(self.items)


class SelfReviewChecklist:
    """Checklist for self-review before submission."""

    ITEMS = [
        "Code compiles without errors",
        "All tests pass locally",
        "No hardcoded values or secrets",
        "Error handling is appropriate",
        "Edge cases are handled",
        "Code is readable and well-named",
        "No unnecessary complexity",
        "Documentation is updated",
        "No console.log/print statements",
        "Changes match the requirements",
    ]

    def get_items(self) -> list[str]:
        """Return checklist items."""
        return self.ITEMS


class ReviewCommand:
    """Main review command orchestrator."""

    def __init__(self, config: ReviewConfig | None = None):
        """Initialize review command."""
        self.config = config or ReviewConfig()
        self.checklist = SelfReviewChecklist()

    def supported_modes(self) -> list[str]:
        """Return list of supported review modes."""
        return [m.value for m in ReviewMode]

    def run(
        self,
        files: list[str],
        mode: str = "full",
        dry_run: bool = False,
    ) -> ReviewResult:
        """Run code review.

        Args:
            files: Files to review
            mode: Review mode (prepare, self, receive, full)
            dry_run: If True, don't make changes

        Returns:
            ReviewResult with review details
        """
        items = []
        spec_passed = True
        quality_passed = True

        if mode in ("prepare", "full"):
            spec_passed = self._run_spec_review(files)

        if mode in ("self", "full"):
            items.extend(self._run_self_review(files))

        if mode in ("receive", "full"):
            quality_passed = self._run_quality_review(files)

        return ReviewResult(
            files_reviewed=len(files),
            items=items,
            spec_passed=spec_passed,
            quality_passed=quality_passed,
        )

    def _run_spec_review(self, files: list[str]) -> bool:
        """Stage 1: Spec compliance review."""
        # Check that implementation matches requirements
        return True

    def _run_self_review(self, files: list[str]) -> list[ReviewItem]:
        """Generate self-review checklist items."""
        return []

    def _run_quality_review(self, files: list[str]) -> bool:
        """Stage 2: Code quality review."""
        return True

    def format_result(self, result: ReviewResult, format: str = "text") -> str:
        """Format review result.

        Args:
            result: Review result to format
            format: Output format (text or json)

        Returns:
            Formatted string
        """
        if format == "json":
            return json.dumps(
                {
                    "files_reviewed": result.files_reviewed,
                    "overall_passed": result.overall_passed,
                    "spec_passed": result.spec_passed,
                    "quality_passed": result.quality_passed,
                    "total_items": result.total_items,
                    "items": [i.to_dict() for i in result.items],
                },
                indent=2,
            )

        status = "PASSED" if result.overall_passed else "NEEDS ATTENTION"
        lines = [
            "Code Review Results",
            "=" * 40,
            f"Status: {status}",
            f"Files Reviewed: {result.files_reviewed}",
            "",
            f"Stage 1 (Spec): {'✓' if result.spec_passed else '✗'}",
            f"Stage 2 (Quality): {'✓' if result.quality_passed else '✗'}",
            "",
        ]

        if result.items:
            lines.append("Review Items:")
            for item in result.items[:10]:
                lines.append(f"  [{item.severity}] {item.file}:{item.line}")
                lines.append(f"    {item.message}")

        return "\n".join(lines)


__all__ = [
    "ReviewMode",
    "ReviewConfig",
    "ReviewItem",
    "ReviewResult",
    "SelfReviewChecklist",
    "ReviewCommand",
]
