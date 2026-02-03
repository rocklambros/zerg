"""ZERG context usage tracking.

Provides heuristic-based token counting and context threshold monitoring
for worker checkpoint decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Token estimation constants (conservative estimates)
TOKENS_PER_CHAR = 0.25  # ~4 chars per token on average
TOKENS_PER_LINE = 15  # Average line length ~60 chars
TOKENS_PER_FILE_READ = 100  # Overhead for file operations
TOKENS_PER_TASK = 500  # Estimated tokens per task context
TOKENS_PER_TOOL_CALL = 50  # Overhead per tool invocation
MAX_CONTEXT_TOKENS = 200_000  # Claude's context window


@dataclass
class ContextUsage:
    """Snapshot of context usage."""

    estimated_tokens: int
    threshold_percent: float
    files_read: int
    tasks_executed: int
    tool_calls: int
    context_budget_tokens: int = 0
    context_budget_used: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def budget_usage_percent(self) -> float:
        """Get budget usage as percentage."""
        if self.context_budget_tokens == 0:
            return 0.0
        return (self.context_budget_used / self.context_budget_tokens) * 100

    @property
    def usage_percent(self) -> float:
        """Get usage as percentage of max context."""
        return (self.estimated_tokens / MAX_CONTEXT_TOKENS) * 100

    @property
    def is_over_threshold(self) -> bool:
        """Check if usage exceeds threshold."""
        return self.usage_percent >= self.threshold_percent

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimated_tokens": self.estimated_tokens,
            "usage_percent": round(self.usage_percent, 1),
            "threshold_percent": self.threshold_percent,
            "is_over_threshold": self.is_over_threshold,
            "files_read": self.files_read,
            "tasks_executed": self.tasks_executed,
            "tool_calls": self.tool_calls,
            "context_budget_tokens": self.context_budget_tokens,
            "context_budget_used": self.context_budget_used,
            "budget_usage_percent": round(self.budget_usage_percent, 1),
            "timestamp": self.timestamp.isoformat(),
        }


class ContextTracker:
    """Track and estimate context usage for checkpoint decisions.

    Uses heuristics based on:
    - Files read (content length)
    - Tasks executed
    - Tool calls made
    - Time elapsed (as proxy for conversation length)
    """

    def __init__(
        self,
        threshold_percent: float = 70.0,
        max_tokens: int = MAX_CONTEXT_TOKENS,
    ) -> None:
        """Initialize context tracker.

        Args:
            threshold_percent: Checkpoint trigger threshold (0-100)
            max_tokens: Maximum context tokens
        """
        self.threshold_percent = threshold_percent
        self.max_tokens = max_tokens

        # Tracking state
        self._files_read: list[tuple[str, int]] = []  # (path, size)
        self._tasks_executed: list[str] = []
        self._tool_calls: int = 0
        self._started_at: datetime = datetime.now()

    def track_file_read(self, path: str | Path, size: int | None = None) -> None:
        """Track a file read operation.

        Args:
            path: File path
            size: File size in bytes (auto-detected if not provided)
        """
        path_str = str(path)

        if size is None:
            try:
                size = Path(path).stat().st_size
            except (OSError, FileNotFoundError):
                size = 0

        self._files_read.append((path_str, size))

    def track_task_execution(self, task_id: str) -> None:
        """Track a task execution.

        Args:
            task_id: Task identifier
        """
        self._tasks_executed.append(task_id)

    def track_tool_call(self) -> None:
        """Track a tool invocation."""
        self._tool_calls += 1

    def estimate_tokens(self) -> int:
        """Estimate current token usage.

        Returns:
            Estimated token count
        """
        tokens = 0

        # File content tokens
        for _path, size in self._files_read:
            tokens += int(size * TOKENS_PER_CHAR)
            tokens += TOKENS_PER_FILE_READ

        # Task context tokens
        tokens += len(self._tasks_executed) * TOKENS_PER_TASK

        # Tool call tokens
        tokens += self._tool_calls * TOKENS_PER_TOOL_CALL

        # Time-based conversation growth estimate
        elapsed_minutes = (datetime.now() - self._started_at).total_seconds() / 60
        tokens += int(elapsed_minutes * 100)  # ~100 tokens per minute of conversation

        return tokens

    def get_usage(self) -> ContextUsage:
        """Get current context usage snapshot.

        Returns:
            ContextUsage instance
        """
        return ContextUsage(
            estimated_tokens=self.estimate_tokens(),
            threshold_percent=self.threshold_percent,
            files_read=len(self._files_read),
            tasks_executed=len(self._tasks_executed),
            tool_calls=self._tool_calls,
        )

    def should_checkpoint(self) -> bool:
        """Check if context usage warrants checkpointing.

        Returns:
            True if should checkpoint and exit
        """
        usage = self.get_usage()
        return usage.is_over_threshold

    def budget_for_task(self, total_budget_tokens: int, task_files: list[str]) -> int:
        """Calculate token budget for a single task based on file count.

        Returns token budget clamped to [500, total_budget_tokens].

        Args:
            total_budget_tokens: Total available budget
            task_files: List of file paths the task operates on

        Returns:
            Token budget for this task
        """
        file_count = max(len(task_files), 1)
        base = total_budget_tokens // file_count
        return max(500, min(base, total_budget_tokens))

    def remaining_budget(self, used_tokens: int, total_budget: int) -> int:
        """Calculate remaining token budget.

        Args:
            used_tokens: Tokens already consumed
            total_budget: Total token budget

        Returns:
            Remaining tokens (minimum 0)
        """
        return max(0, total_budget - used_tokens)

    def context_budget_summary(self, tasks: list[dict], total_budget: int) -> dict:
        """Generate budget summary for all tasks.

        Args:
            tasks: List of task dicts with id and files keys
            total_budget: Total token budget

        Returns:
            Dict with total_budget, allocated, per_task dict, avg_per_task
        """
        per_task: dict[str, int] = {}
        allocated = 0
        for task in tasks:
            task_id = task.get("id", "unknown")
            files = task.get("files", {})
            task_files = (files.get("create") or []) + (files.get("modify") or [])
            budget = self.budget_for_task(total_budget, task_files)
            per_task[task_id] = budget
            allocated += budget

        avg = allocated / max(len(tasks), 1)
        return {
            "total_budget": total_budget,
            "allocated": allocated,
            "per_task": per_task,
            "avg_per_task": round(avg, 1),
        }

    def get_zone(self) -> str:
        """Get current efficiency zone based on context usage.

        Returns:
            Zone name: 'green', 'yellow', or 'red'.
        """
        from zerg.efficiency import ZoneDetector

        detector = ZoneDetector()
        usage = self.get_usage()
        zone = detector.detect(usage.usage_percent)
        return zone.value

    def reset(self) -> None:
        """Reset tracking state for new session."""
        self._files_read.clear()
        self._tasks_executed.clear()
        self._tool_calls = 0
        self._started_at = datetime.now()

    def get_summary(self) -> dict[str, Any]:
        """Get tracking summary.

        Returns:
            Summary dictionary
        """
        usage = self.get_usage()
        return {
            "usage": usage.to_dict(),
            "threshold_percent": self.threshold_percent,
            "max_tokens": self.max_tokens,
            "should_checkpoint": self.should_checkpoint(),
            "session_duration_minutes": round((datetime.now() - self._started_at).total_seconds() / 60, 1),
        }


def estimate_file_tokens(path: str | Path) -> int:
    """Estimate tokens for a file.

    Args:
        path: File path

    Returns:
        Estimated token count
    """
    try:
        size = Path(path).stat().st_size
        return int(size * TOKENS_PER_CHAR) + TOKENS_PER_FILE_READ
    except (OSError, FileNotFoundError):
        return TOKENS_PER_FILE_READ


def estimate_task_tokens(task: dict[str, Any]) -> int:
    """Estimate tokens for a task.

    Args:
        task: Task dictionary

    Returns:
        Estimated token count
    """
    tokens = TOKENS_PER_TASK

    # Add tokens for files the task will read/modify
    files = task.get("files", {})
    for file_list in files.values():
        if isinstance(file_list, list):
            tokens += len(file_list) * TOKENS_PER_FILE_READ

    # Add tokens for description length
    description = task.get("description", "")
    tokens += int(len(description) * TOKENS_PER_CHAR)

    return tokens
