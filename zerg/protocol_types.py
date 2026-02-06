"""Pure data types and constants for the worker protocol."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.constants import DEFAULT_CONTEXT_THRESHOLD

# Default Claude Code invocation settings
CLAUDE_CLI_DEFAULT_TIMEOUT = 1800  # 30 minutes
CLAUDE_CLI_COMMAND = "claude"

# Sentinel for distinguishing "not provided" from None
_SENTINEL = object()


@dataclass
class ClaudeInvocationResult:
    """Result of Claude Code CLI invocation."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    task_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:1000] if len(self.stdout) > 1000 else self.stdout,
            "stderr": self.stderr[:1000] if len(self.stderr) > 1000 else self.stderr,
            "duration_ms": self.duration_ms,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class WorkerContext:
    """Context for a worker instance."""

    worker_id: int
    feature: str
    worktree_path: Path
    branch: str
    context_threshold: float = DEFAULT_CONTEXT_THRESHOLD

    # Cross-cutting capability fields (populated from ZERG_* env vars)
    depth: str = "standard"
    compact: bool = True
    mode: str = "precision"
    tdd: bool = False
    mcp_hint: str = ""
