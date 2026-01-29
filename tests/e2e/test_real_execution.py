"""E2E tests requiring real Claude CLI execution.

All tests in this module are marked with @pytest.mark.real_e2e and will be
skipped in CI or when Claude CLI / API key is not available.
"""

import os
import shutil

import pytest


def _has_claude_cli() -> bool:
    """Check if Claude CLI is available."""
    return shutil.which("claude") is not None


def _has_api_key() -> bool:
    """Check if ANTHROPIC_API_KEY is set."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _has_claude_auth() -> bool:
    """Check if any Claude authentication is available."""
    return _has_claude_cli() or _has_api_key()


skip_no_auth = pytest.mark.skipif(
    not _has_claude_auth(),
    reason="No Claude CLI or ANTHROPIC_API_KEY available",
)


@pytest.mark.real_e2e
class TestRealExecution:
    """Tests requiring real Claude API access."""

    @skip_no_auth
    def test_real_pipeline_with_simple_task(self, tmp_path):
        """Run a single-task pipeline with real Claude CLI.

        Creates a minimal task graph with one trivial task and runs it
        through E2EHarness in real mode. Skipped if no auth available.
        """
        # This test intentionally does NOT run in CI.
        # When real mode is implemented, it would:
        # 1. Create a single-task graph (create a file with "hello world")
        # 2. Use E2EHarness in "real" mode
        # 3. Verify the file was created by Claude
        #
        # For now, verify the test infrastructure exists and skip gracefully.
        pytest.skip("Real mode not yet implemented in E2EHarness")
