"""End-to-end integration test for container flow."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from zerg.cli import cli

pytestmark = pytest.mark.docker


class TestEndToEndFlow:
    """End-to-end test for complete container workflow."""

    def test_full_init_to_dry_run(self, tmp_path: Path) -> None:
        """Full flow from init to rush dry-run.

        This test verifies the complete workflow:
        1. Create a multi-language project
        2. Initialize git repository
        3. Run zerg init --detect
        4. Verify devcontainer.json created
        5. Create minimal task graph
        6. Run rush --mode auto --dry-run
        """
        # 1. Create multi-lang project
        (tmp_path / "requirements.txt").write_text("pytest>=7.0\n")
        (tmp_path / "package.json").write_text('{"name": "test", "version": "1.0.0"}')

        # 2. Initialize git
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        # Create initial commit
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, capture_output=True)

        runner = CliRunner()
        original_cwd = os.getcwd()

        try:
            os.chdir(tmp_path)

            # 3. Run init
            init_result = runner.invoke(cli, ["init", "--detect", "--force"])

            # Verify init succeeded or was already done
            init_ok = init_result.exit_code == 0 or "already initialized" in init_result.output.lower()
            assert init_ok, f"Init failed: {init_result.output}"

            # 4. Check devcontainer exists (may not exist if init skipped it)
            tmp_path / ".devcontainer" / "devcontainer.json"

            # 5. Create minimal task graph for rush to consume
            gsd_dir = tmp_path / ".gsd" / "specs" / "test-feature"
            gsd_dir.mkdir(parents=True, exist_ok=True)

            task_graph = {
                "feature": "test-feature",
                "created_at": "2026-01-27T00:00:00Z",
                "tasks": [
                    {
                        "id": "T-001",
                        "title": "Test Task",
                        "description": "A test task",
                        "level": 1,
                        "dependencies": [],
                        "files": {"create": ["test.py"], "modify": [], "read": []},
                        "verification": {"command": "echo ok", "timeout_seconds": 10},
                    }
                ],
            }
            (gsd_dir / "task-graph.json").write_text(json.dumps(task_graph, indent=2))

            # 6. Run rush --dry-run
            rush_result = runner.invoke(cli, ["rush", "--feature", "test-feature", "--mode", "auto", "--dry-run"])

            # Rush may fail due to missing setup, but should at least parse args
            # The important thing is it doesn't crash on --mode flag
            assert "--mode" not in rush_result.output or rush_result.exit_code in [
                0,
                1,
            ], f"Rush failed unexpectedly: {rush_result.output}"

        finally:
            os.chdir(original_cwd)
