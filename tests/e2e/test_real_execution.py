"""Real execution E2E tests with actual Claude CLI.

All tests require either:
- Claude CLI authentication (via ~/.claude for OAuth)
- ANTHROPIC_API_KEY environment variable

Tests are automatically skipped if neither authentication method is available.
"""

import os
import shutil
from pathlib import Path

import pytest

from tests.e2e.harness import E2EHarness


def _detect_auth() -> tuple[bool, str]:
    """Detect available authentication method for Claude CLI.

    Returns:
        Tuple of (auth_available, auth_method).
        auth_available: True if either OAuth or API key is available.
        auth_method: Description of detected auth method.
    """
    # Check for Claude CLI OAuth (Claude Pro/Team)
    claude_cli = shutil.which("claude")
    if claude_cli:
        # Assume OAuth configured if CLI exists and ~/.claude directory exists
        claude_dir = Path.home() / ".claude"
        if claude_dir.exists():
            return True, "oauth"

    # Check for API key env var
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return True, "api_key"

    return False, "none"


# Auto-detect authentication
_auth_available, _auth_method = _detect_auth()

# Skip marker for tests requiring real auth
requires_real_auth = pytest.mark.skipif(
    not _auth_available,
    reason=f"Real Claude CLI auth required (detected: {_auth_method})",
)


@pytest.mark.real_e2e
class TestRealExecution:
    """E2E tests with real Claude CLI execution."""

    @requires_real_auth
    def test_real_pipeline_with_simple_task(self, tmp_path: Path) -> None:
        """Run a 1-worker, 1-task pipeline with real Claude CLI.

        Creates a minimal task graph with a single trivial task that creates
        a file with 'hello world' content. Verifies that the task executes
        successfully and produces the expected file.
        """
        # Setup harness in real mode
        harness = E2EHarness(tmp_path, feature="simple-test", mode="real")
        repo_path = harness.setup_repo()

        # Create minimal task graph: single task that creates a file
        tasks = [
            {
                "id": "SIMPLE-001",
                "title": "Create hello world file",
                "description": "Create a single file containing 'hello world'.",
                "phase": "implementation",
                "level": 1,
                "dependencies": [],
                "files": {
                    "create": ["hello.txt"],
                    "modify": [],
                    "read": [],
                },
                "verification": {
                    "command": "test -f hello.txt && grep -q 'hello world' hello.txt",
                    "timeout_seconds": 30,
                },
            }
        ]

        harness.setup_task_graph(tasks)

        # Configure for single worker
        harness.setup_config(
            {
                "workers": {
                    "max_workers": 1,
                    "spawn_interval_seconds": 0,
                },
            }
        )

        # Execute with real Claude CLI
        # Note: This will invoke actual Claude Code CLI
        result = harness.run(workers=1)

        # Verify results
        assert result.success, "Real execution should succeed"
        assert result.tasks_completed == 1, "Should complete 1 task"
        assert result.tasks_failed == 0, "Should have no failures"
        assert result.levels_completed == 1, "Should complete 1 level"

        # Verify the actual file was created
        hello_file = repo_path / "hello.txt"
        assert hello_file.exists(), "hello.txt should be created"
        content = hello_file.read_text()
        assert "hello world" in content.lower(), "File should contain 'hello world'"
