"""E2E test harness for ZERG orchestration.

Sets up real git repos and simulates the ZERG orchestrator flow
for end-to-end testing without requiring the full subprocess worker
infrastructure.
"""

import json
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from zerg.config import ZergConfig


@dataclass
class E2EResult:
    """Result of an end-to-end test run."""

    success: bool
    tasks_completed: int
    tasks_failed: int
    levels_completed: int
    merge_commits: list[str]
    duration_s: float


class E2EHarness:
    """End-to-end test harness for ZERG orchestration.

    Creates a real git repository with the full ZERG directory structure,
    sets up task graphs, and simulates orchestrator execution using
    mock workers.
    """

    def __init__(
        self,
        tmp_path: Path,
        feature: str = "test-feature",
        mode: str = "mock",
    ) -> None:
        """Initialize the E2E harness.

        Args:
            tmp_path: Temporary directory for the test (typically from pytest).
            feature: Feature name used in spec paths and state tracking.
            mode: Execution mode - "mock" for simulated workers,
                  "real" for actual Claude CLI invocation.
        """
        self.tmp_path = tmp_path
        self.feature = feature
        self.mode = mode
        self.repo_path: Path | None = None

    def setup_repo(self) -> Path:
        """Create a git repository with full ZERG directory structure.

        Initializes a new git repo at tmp_path/repo with all required
        ZERG directories and a default config, then creates an initial commit.

        Returns:
            Path to the initialized repository.
        """
        repo_path = self.tmp_path / "repo"
        repo_path.mkdir(parents=True, exist_ok=True)

        # Create ZERG infrastructure directories
        (repo_path / ".zerg").mkdir(parents=True, exist_ok=True)
        (repo_path / ".zerg" / "state").mkdir(parents=True, exist_ok=True)
        (repo_path / ".zerg" / "logs").mkdir(parents=True, exist_ok=True)
        (repo_path / ".zerg" / "logs" / "workers").mkdir(parents=True, exist_ok=True)
        (repo_path / ".zerg" / "logs" / "tasks").mkdir(parents=True, exist_ok=True)

        # Create GSD spec directories
        (repo_path / ".gsd").mkdir(parents=True, exist_ok=True)
        (repo_path / ".gsd" / "specs" / self.feature).mkdir(parents=True, exist_ok=True)

        # Write default config
        config = ZergConfig()
        config_path = repo_path / ".zerg" / "config.yaml"
        config_data = config.to_dict()
        config_path.write_text(yaml.dump(config_data, default_flow_style=False, sort_keys=False))

        # Initialize git repository
        subprocess.run(
            ["git", "init"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            env=_git_env(),
        )

        self.repo_path = repo_path
        return repo_path

    def setup_task_graph(self, tasks: list[dict] | dict) -> Path:
        """Build and write a v2.0 task-graph.json from a list of task dicts.

        Args:
            tasks: List of task dictionaries, or a dict with a "tasks" key
                   containing the list. Each task should contain at minimum:
                   id, title, description, level, dependencies, files, verification.

        Returns:
            Path to the written task-graph.json file.

        Raises:
            RuntimeError: If setup_repo has not been called first.
        """
        if self.repo_path is None:
            raise RuntimeError("setup_repo() must be called before setup_task_graph()")

        # Accept both dict-with-tasks-key and plain list formats
        if isinstance(tasks, dict) and "tasks" in tasks:
            tasks = tasks["tasks"]

        # Compute levels from tasks
        levels_set: set[int] = set()
        for task in tasks:
            levels_set.add(task.get("level", 1))

        # Build levels metadata
        levels_dict: dict[str, dict] = {}
        for level_num in sorted(levels_set):
            level_task_ids = [t["id"] for t in tasks if t.get("level", 1) == level_num]
            levels_dict[str(level_num)] = {
                "name": f"Level {level_num}",
                "tasks": level_task_ids,
                "parallel": True,
                "estimated_minutes": 10,
                "depends_on_levels": list(range(1, level_num)) if level_num > 1 else [],
            }

        # Build full v2.0 task graph
        task_graph = {
            "schema": "zerg-task-graph",
            "feature": self.feature,
            "version": "2.0",
            "generated": datetime.now(UTC).isoformat(),
            "total_tasks": len(tasks),
            "tasks": tasks,
            "levels": levels_dict,
        }

        graph_path = self.repo_path / ".gsd" / "specs" / self.feature / "task-graph.json"
        graph_path.write_text(json.dumps(task_graph, indent=2))
        return graph_path

    def setup_config(self, overrides: dict | None = None) -> Path:
        """Create a ZergConfig with optional overrides and write it to disk.

        Args:
            overrides: Dictionary of config overrides to merge into defaults.

        Returns:
            Path to the written config.yaml file.

        Raises:
            RuntimeError: If setup_repo has not been called first.
        """
        if self.repo_path is None:
            raise RuntimeError("setup_repo() must be called before setup_config()")

        config = ZergConfig.from_dict(overrides) if overrides else ZergConfig()

        config_path = self.repo_path / ".zerg" / "config.yaml"
        config_data = config.to_dict()
        config_path.write_text(yaml.dump(config_data, default_flow_style=False, sort_keys=False))
        return config_path

    def run(self, workers: int = 5) -> E2EResult:
        """Execute a simplified orchestration run.

        Simulates the orchestrator flow without spawning real subprocess
        workers. Loads the task graph, processes tasks level-by-level,
        and uses MockWorker for task execution in mock mode, or the
        actual Claude CLI in real mode.

        Args:
            workers: Number of simulated workers (used for concurrency tracking).

        Returns:
            E2EResult with execution outcome.

        Raises:
            RuntimeError: If setup_repo has not been called first.
        """
        if self.repo_path is None:
            raise RuntimeError("setup_repo() must be called before run()")

        start_time = time.monotonic()

        # Load task graph
        graph_path = self.repo_path / ".gsd" / "specs" / self.feature / "task-graph.json"
        with open(graph_path) as f:
            task_graph = json.load(f)

        all_tasks = task_graph.get("tasks", [])

        # Group tasks by level
        tasks_by_level: dict[int, list[dict]] = {}
        for task in all_tasks:
            level = task.get("level", 1)
            tasks_by_level.setdefault(level, []).append(task)

        tasks_completed = 0
        tasks_failed = 0
        levels_completed = 0
        merge_commits = []

        import os

        original_cwd = os.getcwd()
        os.chdir(self.repo_path)

        try:
            if self.mode == "real":
                for level_num in sorted(tasks_by_level.keys()):
                    level_tasks = tasks_by_level[level_num]
                    level_success = True

                    for task in level_tasks:
                        prompt = self._build_real_prompt(task)
                        timeout = task.get("verification", {}).get("timeout_seconds", 120)

                        try:
                            subprocess.run(
                                [
                                    "claude",
                                    "--print",
                                    "--dangerously-skip-permissions",
                                    prompt,
                                ],
                                cwd=self.repo_path,
                                capture_output=True,
                                text=True,
                                timeout=timeout,
                                check=False,
                            )
                        except subprocess.TimeoutExpired:
                            tasks_failed += 1
                            level_success = False
                            continue

                        if self._run_verification(task):
                            tasks_completed += 1
                        else:
                            tasks_failed += 1
                            level_success = False

                    if level_success:
                        levels_completed += 1
                        commit_hash = f"e2e-merge-level-{level_num}"
                        merge_commits.append(commit_hash)
            else:
                from tests.e2e.mock_worker import MockWorker

                mock_worker = MockWorker()

                for level_num in sorted(tasks_by_level.keys()):
                    level_tasks = tasks_by_level[level_num]
                    level_success = True

                    for task in level_tasks:
                        result = mock_worker.invoke_claude_code(task)

                        if result.success:
                            tasks_completed += 1
                        else:
                            tasks_failed += 1
                            level_success = False

                    if level_success:
                        levels_completed += 1
                        commit_hash = f"e2e-merge-level-{level_num}"
                        merge_commits.append(commit_hash)
        finally:
            os.chdir(original_cwd)

        elapsed = time.monotonic() - start_time

        success = tasks_failed == 0 and tasks_completed == len(all_tasks)

        return E2EResult(
            success=success,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            levels_completed=levels_completed,
            merge_commits=merge_commits,
            duration_s=round(elapsed, 3),
        )

    @staticmethod
    def _build_real_prompt(task: dict) -> str:
        """Build a prompt for the Claude CLI from a task dict.

        Args:
            task: Task dictionary from the task graph.

        Returns:
            Prompt string for Claude CLI.
        """
        files = task.get("files", {})
        create_list = files.get("create", [])
        modify_list = files.get("modify", [])

        parts = [
            "Create the following files as specified:",
            f"Title: {task.get('title', '')}",
            f"Description: {task.get('description', '')}",
        ]

        if create_list:
            parts.append(f"Files to create: {', '.join(create_list)}")
        if modify_list:
            parts.append(f"Files to modify: {', '.join(modify_list)}")

        return "\n".join(parts)

    def _run_verification(self, task: dict) -> bool:
        """Run a task's verification command.

        Args:
            task: Task dictionary containing a verification.command field.

        Returns:
            True if verification passed, False otherwise.
        """
        verification = task.get("verification", {})
        command = verification.get("command")
        if not command:
            return True

        timeout = verification.get("timeout_seconds", 30)

        try:
            result = subprocess.run(
                command,
                shell=True,  # noqa: S602 — verification commands are test-defined
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False


def _git_env() -> dict[str, str]:
    """Build environment variables for git commands in test repos.

    Returns:
        Environment dict with git author/committer identity set.
    """
    import os

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "ZERG Test"
    env["GIT_AUTHOR_EMAIL"] = "test@zerg.dev"
    env["GIT_COMMITTER_NAME"] = "ZERG Test"
    env["GIT_COMMITTER_EMAIL"] = "test@zerg.dev"
    return env
