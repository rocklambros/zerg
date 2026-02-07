"""ContainerLauncher — Docker-based worker launcher.

Extracted from zerg/launcher.py. Launches workers in Docker containers
using devcontainer configuration. Each worker runs in its own container
with mounted workspace.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.constants import WorkerStatus
from zerg.env_validator import (
    CONTAINER_HEALTH_FILE,
    CONTAINER_HOME_DIR,
    validate_env_vars,
)
from zerg.launcher_types import LauncherConfig, SpawnResult, WorkerHandle
from zerg.launchers.base import WorkerLauncher
from zerg.logging import get_logger

logger = get_logger("launcher")


class ContainerLauncher(WorkerLauncher):
    """Launch workers in Docker containers.

    Uses devcontainer configuration to spawn isolated worker environments.
    Each worker runs in its own container with mounted workspace.
    """

    # Container configuration
    # Use default bridge network for internet access (required for API calls)
    DEFAULT_NETWORK = "bridge"
    CONTAINER_PREFIX = "zerg-worker"
    WORKER_ENTRY_SCRIPT = ".zerg/worker_entry.sh"
    # Performance: Skip docker calls if status was checked recently (FR-1)
    MONITOR_COOLDOWN_SECONDS = 10

    def __init__(
        self,
        config: LauncherConfig | None = None,
        image_name: str = "zerg-worker",
        network: str | None = None,
        memory_limit: str = "4g",
        cpu_limit: float = 2.0,
    ) -> None:
        """Initialize container launcher.

        Args:
            config: Launcher configuration
            image_name: Docker image name for workers
            network: Docker network name (default: zerg-internal)
            memory_limit: Docker --memory limit (e.g., '4g', '512m')
            cpu_limit: Docker --cpus limit (e.g., 2.0)
        """
        super().__init__(config)
        self.image_name = image_name
        self.network = network or self.DEFAULT_NETWORK
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self._container_ids: dict[int, str] = {}

    def spawn(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        """Spawn a new worker container.

        Args:
            worker_id: Unique worker identifier
            feature: Feature name being worked on
            worktree_path: Path to worker's git worktree
            branch: Git branch for worker
            env: Additional environment variables

        Returns:
            SpawnResult with handle or error
        """
        try:
            # Validate worker_id
            if not isinstance(worker_id, int) or worker_id < 0:
                raise ValueError(f"Invalid worker_id: {worker_id}")

            container_name = f"{self.CONTAINER_PREFIX}-{int(worker_id)}"

            # Remove any existing container with the same name
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
            )

            # Build environment
            container_env = {
                "ZERG_WORKER_ID": str(worker_id),
                "ZERG_FEATURE": feature,
                "ZERG_WORKTREE": "/workspace",
                "ZERG_BRANCH": branch,
                "ZERG_SPEC_DIR": f"/workspace/.gsd/specs/{feature}",
                **(
                    {"CLAUDE_CODE_TASK_LIST_ID": os.environ["CLAUDE_CODE_TASK_LIST_ID"]}
                    if "CLAUDE_CODE_TASK_LIST_ID" in os.environ
                    else {}
                ),
            }

            # Add API key from environment or .env file
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                env_file = Path(".env")
                if env_file.exists():
                    for line in env_file.read_text().splitlines():
                        line = line.strip()
                        if line.startswith("ANTHROPIC_API_KEY"):
                            _, _, val = line.partition("=")
                            api_key = val.strip().strip("'\"")
                            break
            if api_key:
                container_env["ANTHROPIC_API_KEY"] = api_key

            # Validate and add additional env vars
            if self.config.env_vars:
                validated = validate_env_vars(self.config.env_vars)
                container_env.update(validated)
            if env:
                validated = validate_env_vars(env)
                container_env.update(validated)

            # Start container
            container_id = self._start_container(
                container_name=container_name,
                worktree_path=worktree_path,
                env=container_env,
            )

            if not container_id:
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Failed to start container",
                )

            # Create handle
            handle = WorkerHandle(
                worker_id=worker_id,
                container_id=container_id,
                status=WorkerStatus.INITIALIZING,
            )

            # Store references
            self._workers[worker_id] = handle
            self._container_ids[worker_id] = container_id

            # Wait for container ready
            if not self._wait_ready(container_id, timeout=30):
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Container failed to become ready",
                )

            # Entry script runs as container CMD (no separate docker invocation needed).
            # Wait longer for worker to start since it includes dependency install.
            if not self._verify_worker_process(container_id, timeout=120.0):
                logger.error(f"Worker process failed to start for worker {worker_id}")
                self._cleanup_failed_container(container_id, worker_id)
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Worker process failed to start",
                )

            handle.status = WorkerStatus.RUNNING
            logger.info(f"Spawned container {container_name} ({container_id[:12]})")

            return SpawnResult(success=True, worker_id=worker_id, handle=handle)

        except Exception as e:  # noqa: BLE001 — intentional: spawn must report all failures gracefully
            logger.exception(f"Failed to spawn container for worker {worker_id}")
            return SpawnResult(success=False, worker_id=worker_id, error=str(e))

    def _build_container_cmd(
        self,
        container_name: str,
        worktree_path: Path,
        env: dict[str, str],
    ) -> list[str]:
        """Build docker run command array. Single source of truth for container command construction.

        Both _start_container_impl (async) and its sync wrapper use this method
        to build identical docker run commands.

        Args:
            container_name: Name for the container
            worktree_path: Host path to mount as workspace
            env: Environment variables for container (may be mutated to add git env vars)

        Returns:
            Complete docker run command as list of strings
        """
        # Mount worktree as workspace and share state directory from main repo
        main_repo = worktree_path.parent.parent.parent  # .zerg-worktrees/feature/worker-N -> repo
        state_dir = main_repo / ".zerg" / "state"

        # Git worktrees need access to:
        # 1. The worktree metadata in main repo's .git/worktrees/<name>
        # 2. The main repo's .git directory for objects/refs
        worktree_name = worktree_path.name  # e.g., "worker-0"
        main_git_dir = main_repo / ".git"
        git_worktree_dir = main_git_dir / "worktrees" / worktree_name

        # Mount ~/.claude for OAuth credentials if it exists
        claude_config_dir = Path.home() / ".claude"

        # Get current user's UID/GID to run container as non-root
        # This is required because --dangerously-skip-permissions doesn't work as root
        uid = os.getuid()
        gid = os.getgid()
        home_dir = CONTAINER_HOME_DIR

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--user",
            f"{uid}:{gid}",
            "-v",
            f"{worktree_path.absolute()}:/workspace",
            "-v",
            f"{state_dir.absolute()}:/workspace/.zerg/state",  # Share state with orchestrator
        ]

        # Mount main repo's .git and worktree metadata for git operations inside container
        if main_git_dir.exists() and git_worktree_dir.exists():
            # Mount the main .git to /repo/.git so git can find objects/refs
            # Note: Not read-only because git needs write access for commits
            cmd.extend(["-v", f"{main_git_dir.absolute()}:/repo/.git"])
            # Mount the worktree metadata
            cmd.extend(["-v", f"{git_worktree_dir.absolute()}:/workspace/.git-worktree"])
            # Pass env vars so entry script can fix the git paths
            env["ZERG_GIT_WORKTREE_DIR"] = "/workspace/.git-worktree"
            env["ZERG_GIT_MAIN_DIR"] = "/repo/.git"

        # Add Claude config mount for OAuth authentication (needs write for debug logs)
        if claude_config_dir.exists():
            cmd.extend(["-v", f"{claude_config_dir.absolute()}:{home_dir}/.claude"])
            cmd.extend(["-e", f"HOME={home_dir}"])

        # Mount ~/.claude.json for OAuth token (separate file from ~/.claude/ directory)
        claude_config_file = Path.home() / ".claude.json"
        if claude_config_file.exists():
            cmd.extend(["-v", f"{claude_config_file.absolute()}:{home_dir}/.claude.json"])

        # Resource limits
        cmd.extend(["--memory", self.memory_limit])
        cmd.extend(["--cpus", str(self.cpu_limit)])

        cmd.extend(
            [
                "-w",
                "/workspace",
                "--network",
                self.network,
            ]
        )

        # Add environment variables
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Run entry script directly as container CMD.
        # The entry script uses a process replacement to become worker_main (PID 1).
        # If it fails, the fallback keeps the container alive for debugging.
        cmd.extend(
            [
                self.image_name,
                "bash",
                "-c",
                f"bash /workspace/{self.WORKER_ENTRY_SCRIPT} 2>&1; "
                f"echo 'Worker entry exited with code '$?; sleep infinity",
            ]
        )

        return cmd

    async def _start_container_impl(
        self,
        container_name: str,
        worktree_path: Path,
        env: dict[str, str],
        run_fn: Any,
    ) -> str | None:
        """Core container start logic. Single source of truth.

        Both _start_container() and _start_container_async() delegate here,
        passing appropriate run callables for sync vs async contexts.

        Args:
            container_name: Name for the container
            worktree_path: Host path to mount as workspace
            env: Environment variables for container
            run_fn: Awaitable callable that runs the docker command and returns
                     (returncode, stdout, stderr) tuple

        Returns:
            Container ID or None on failure
        """
        cmd = self._build_container_cmd(container_name, worktree_path, env)

        try:
            returncode, stdout, stderr = await run_fn(cmd)

            if returncode == 0:
                container_id = stdout.strip()
                return container_id
            else:
                logger.error(f"Docker run failed: {stderr}")
                return None

        except (subprocess.TimeoutExpired, TimeoutError):
            logger.error("Docker run timed out")
            return None
        except Exception as e:  # noqa: BLE001 — intentional: container start must not crash caller
            logger.exception(f"Docker run error: {e}")
            return None

    def _start_container(
        self,
        container_name: str,
        worktree_path: Path,
        env: dict[str, str],
    ) -> str | None:
        """Start a Docker container (sync wrapper).

        Delegates to _start_container_impl() with a sync-compatible callable.

        Args:
            container_name: Name for the container
            worktree_path: Host path to mount as workspace
            env: Environment variables for container

        Returns:
            Container ID or None on failure
        """

        async def _sync_run(cmd: list[str]) -> tuple[int, str, str]:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode, result.stdout, result.stderr

        return asyncio.run(
            self._start_container_impl(
                container_name=container_name,
                worktree_path=worktree_path,
                env=env,
                run_fn=_sync_run,
            )
        )

    def _wait_ready(self, container_id: str, timeout: float = 30) -> bool:
        """Wait for container to be ready.

        Args:
            container_id: Container ID
            timeout: Maximum wait time in seconds

        Returns:
            True if container is running
        """

        start = time.time()
        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Running}}", container_id],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip() == "true":
                    return True
            except (subprocess.SubprocessError, OSError) as e:  # noqa: BLE001 — intentional: polling loop retries on transient failures
                logger.debug(f"Container readiness check failed (retrying): {e}")
            time.sleep(0.5)

        return False

    def _run_worker_entry(self, container_id: str) -> bool:
        """Run the worker entry script in container.

        Args:
            container_id: Container ID

        Returns:
            True if started successfully
        """
        cmd = [
            "docker",
            "exec",  # noqa: S607 — docker subcommand, not shell exec
            "-d",
            "-w",
            "/workspace",
            container_id,
            "/bin/bash",
            f"/workspace/{self.WORKER_ENTRY_SCRIPT}",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to run worker entry: {e}")
            return False

    def _verify_worker_process(self, container_id: str, timeout: float = 5.0) -> bool:
        """Verify the worker process is running in container.

        BF-008: Added process verification after start.

        Args:
            container_id: Container ID
            timeout: Maximum time to wait for process

        Returns:
            True if worker process is running
        """
        import time as _time

        start = _time.time()
        while _time.time() - start < timeout:
            try:
                result = subprocess.run(
                    ["docker", "exec", container_id, "pgrep", "-f", "worker_main"],  # noqa: S607
                    capture_output=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    logger.debug(f"Worker process verified running in {container_id[:12]}")
                    return True
            except (subprocess.SubprocessError, OSError) as e:  # noqa: BLE001 — intentional: polling loop retries on transient failures
                logger.debug(f"Process check failed (retrying): {e}")
            _time.sleep(0.5)

        logger.warning(f"Worker process not found in container {container_id[:12]} after {timeout}s")
        return False

    def _cleanup_failed_container(self, container_id: str, worker_id: int) -> None:
        """Clean up container after spawn failure.

        Args:
            container_id: Container to clean up
            worker_id: Worker ID
        """
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                timeout=10,
            )
            logger.debug(f"Cleaned up failed container {container_id[:12]}")
        except Exception as e:  # noqa: BLE001 — intentional: cleanup must not fail, any error is swallowed
            logger.warning(f"Failed to clean up container: {e}")

        # Remove from tracking
        if worker_id in self._container_ids:
            del self._container_ids[worker_id]
        if worker_id in self._workers:
            del self._workers[worker_id]

    def monitor(self, worker_id: int) -> WorkerStatus:
        """Check worker container status.

        Args:
            worker_id: Worker to check

        Returns:
            Current worker status
        """
        handle = self._workers.get(worker_id)
        container_id = self._container_ids.get(worker_id)

        if not handle or not container_id:
            return WorkerStatus.STOPPED

        # FR-1: Check cooldown - skip docker calls if checked recently
        # This reduces docker subprocess overhead from 120+/min to ~20-30/min
        if handle.health_check_at:
            age = (datetime.now() - handle.health_check_at).total_seconds()
            if age < self.MONITOR_COOLDOWN_SECONDS:
                return handle.status

        try:
            # Check container state
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}},{{.State.ExitCode}}", container_id],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                handle.status = WorkerStatus.STOPPED
                return WorkerStatus.STOPPED

            running, exit_code_str = result.stdout.strip().split(",")

            if running == "true":
                # Container is running, but the CMD sleep keeps it alive after
                # the worker process exits. Check /tmp/.zerg-alive marker file
                # which the entry script removes on exit.
                # Only check after a grace period (marker created during init).
                if handle.started_at:
                    from datetime import timedelta

                    age = datetime.now() - handle.started_at
                    if age > timedelta(seconds=60):
                        alive_check = subprocess.run(
                            ["docker", "exec", container_id, "test", "-f", CONTAINER_HEALTH_FILE],  # noqa: S607
                            capture_output=True,
                            timeout=5,
                        )
                        if alive_check.returncode != 0:
                            logger.info(f"Worker {worker_id} process exited (marker file absent)")
                            handle.status = WorkerStatus.STOPPED
                            return WorkerStatus.STOPPED
                if handle.status == WorkerStatus.INITIALIZING:
                    handle.status = WorkerStatus.RUNNING
                return handle.status
            else:
                # Container has exited
                handle.exit_code = int(exit_code_str)

                if exit_code_str == "0":
                    handle.status = WorkerStatus.STOPPED
                elif exit_code_str == "2":
                    handle.status = WorkerStatus.CHECKPOINTING
                elif exit_code_str == "3":
                    handle.status = WorkerStatus.BLOCKED
                else:
                    handle.status = WorkerStatus.CRASHED

                return handle.status

        except (subprocess.SubprocessError, OSError, ValueError) as e:
            logger.error(f"Failed to monitor container: {e}")
            return handle.status if handle else WorkerStatus.STOPPED
        finally:
            # FR-1: Update timestamp after actual docker check
            if handle:
                handle.health_check_at = datetime.now()

    async def _terminate_impl(
        self,
        worker_id: int,
        force: bool,
        run_fn: Any,
    ) -> bool:
        """Core terminate logic. Single source of truth.

        Both terminate() and terminate_async() delegate here,
        passing appropriate run callables for sync vs async contexts.

        Args:
            worker_id: Worker to terminate
            force: Force termination (docker kill vs docker stop)
            run_fn: Awaitable callable that runs a docker command and returns
                     (returncode, stdout, stderr) tuple

        Returns:
            True if termination succeeded
        """
        container_id = self._container_ids.get(worker_id)
        handle = self._workers.get(worker_id)

        if not container_id or not handle:
            return False

        try:
            # Stop or kill container
            action = "kill" if force else "stop"
            cmd = ["docker", action, container_id]
            returncode, _stdout, stderr = await run_fn(cmd, 10 if force else 30)

            if returncode == 0:
                handle.status = WorkerStatus.STOPPED
                logger.info(f"Terminated container for worker {worker_id}")

                # Remove container
                await run_fn(["docker", "rm", "-f", container_id], 10)

                return True
            else:
                logger.error(f"Failed to stop container: {stderr}")
                return False

        except (subprocess.TimeoutExpired, TimeoutError):
            # Force kill on timeout -- best effort, ignore secondary failures
            try:
                await run_fn(["docker", "kill", container_id], 5)
            except (subprocess.SubprocessError, OSError, TimeoutError) as e:  # noqa: BLE001 — intentional: force-kill is last-resort best-effort
                logger.debug(f"Force kill also failed for worker {worker_id}, proceeding with cleanup: {e}")
            handle.status = WorkerStatus.STOPPED
            return True

        except Exception:  # noqa: BLE001 — intentional: terminate must not crash orchestrator
            logger.exception(f"Failed to terminate container for worker {worker_id}")
            return False

        finally:
            # Clean up references
            if worker_id in self._container_ids:
                del self._container_ids[worker_id]
            # Also remove from worker handles to prevent stale state
            if worker_id in self._workers:
                del self._workers[worker_id]

    def terminate(self, worker_id: int, force: bool = False) -> bool:
        """Terminate a worker container.

        Sync wrapper that delegates to _terminate_impl() with a
        sync-compatible callable.

        Args:
            worker_id: Worker to terminate
            force: Force termination (docker kill vs docker stop)

        Returns:
            True if termination succeeded
        """

        async def _sync_run(cmd: list[str], timeout: int) -> tuple[int, str, str]:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr

        return asyncio.run(
            self._terminate_impl(
                worker_id=worker_id,
                force=force,
                run_fn=_sync_run,
            )
        )

    def get_output(self, worker_id: int, tail: int = 100) -> str:
        """Get worker container logs.

        Args:
            worker_id: Worker to get output from
            tail: Number of lines from end

        Returns:
            Output string
        """
        container_id = self._container_ids.get(worker_id)

        if not container_id:
            return ""

        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout + result.stderr
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to get container logs: {e}")
            return ""

    def ensure_network(self) -> bool:
        """Ensure the Docker network exists.

        Returns:
            True if network exists or was created
        """
        try:
            # Check if network exists
            result = subprocess.run(
                ["docker", "network", "inspect", self.network],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return True

            # Create network
            result = subprocess.run(
                ["docker", "network", "create", self.network],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info(f"Created Docker network: {self.network}")
                return True
            else:
                logger.error(f"Failed to create network: {result.stderr}")
                return False

        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Network setup error: {e}")
            return False

    def image_exists(self) -> bool:
        """Check if the worker image exists.

        Returns:
            True if image exists locally
        """
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", self.image_name],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug(f"Image existence check failed: {e}")
            return False

    async def spawn_async(
        self,
        worker_id: int,
        feature: str,
        worktree_path: Path,
        branch: str,
        env: dict[str, str] | None = None,
    ) -> SpawnResult:
        """Spawn a new worker container asynchronously.

        Uses asyncio.create_subprocess_exec() for docker commands
        instead of blocking subprocess.run().

        Args:
            worker_id: Unique worker identifier
            feature: Feature name being worked on
            worktree_path: Path to worker's git worktree
            branch: Git branch for worker
            env: Additional environment variables

        Returns:
            SpawnResult with handle or error
        """
        try:
            # Validate worker_id
            if not isinstance(worker_id, int) or worker_id < 0:
                raise ValueError(f"Invalid worker_id: {worker_id}")

            container_name = f"{self.CONTAINER_PREFIX}-{int(worker_id)}"

            # Remove any existing container with the same name
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            # Build environment
            container_env: dict[str, str] = {
                "ZERG_WORKER_ID": str(worker_id),
                "ZERG_FEATURE": feature,
                "ZERG_WORKTREE": "/workspace",
                "ZERG_BRANCH": branch,
                "ZERG_SPEC_DIR": f"/workspace/.gsd/specs/{feature}",
                **(
                    {"CLAUDE_CODE_TASK_LIST_ID": os.environ["CLAUDE_CODE_TASK_LIST_ID"]}
                    if "CLAUDE_CODE_TASK_LIST_ID" in os.environ
                    else {}
                ),
            }

            # Add API key from environment or .env file
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                env_file = Path(".env")
                if env_file.exists():
                    for line in env_file.read_text().splitlines():
                        line = line.strip()
                        if line.startswith("ANTHROPIC_API_KEY"):
                            _, _, val = line.partition("=")
                            api_key = val.strip().strip("'\"")
                            break
            if api_key:
                container_env["ANTHROPIC_API_KEY"] = api_key

            # Validate and add additional env vars
            if self.config.env_vars:
                validated = validate_env_vars(self.config.env_vars)
                container_env.update(validated)
            if env:
                validated = validate_env_vars(env)
                container_env.update(validated)

            # Start container asynchronously
            container_id = await self._start_container_async(
                container_name=container_name,
                worktree_path=worktree_path,
                env=container_env,
            )

            if not container_id:
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Failed to start container",
                )

            # Create handle
            handle = WorkerHandle(
                worker_id=worker_id,
                container_id=container_id,
                status=WorkerStatus.INITIALIZING,
            )

            # Store references
            self._workers[worker_id] = handle
            self._container_ids[worker_id] = container_id

            # Wait for container ready (fall back to sync for complex checks)
            ready = await asyncio.to_thread(self._wait_ready, container_id, 30)
            if not ready:
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Container failed to become ready",
                )

            # Verify worker process
            verified = await asyncio.to_thread(self._verify_worker_process, container_id, 120.0)
            if not verified:
                logger.error(f"Worker process failed to start for worker {worker_id}")
                await asyncio.to_thread(self._cleanup_failed_container, container_id, worker_id)
                return SpawnResult(
                    success=False,
                    worker_id=worker_id,
                    error="Worker process failed to start",
                )

            handle.status = WorkerStatus.RUNNING
            logger.info(f"Spawned async container {container_name} ({container_id[:12]})")

            return SpawnResult(success=True, worker_id=worker_id, handle=handle)

        except Exception as e:  # noqa: BLE001 — intentional: async spawn must report all failures gracefully
            logger.exception(f"Failed to spawn async container for worker {worker_id}")
            return SpawnResult(success=False, worker_id=worker_id, error=str(e))

    async def _start_container_async(
        self,
        container_name: str,
        worktree_path: Path,
        env: dict[str, str],
    ) -> str | None:
        """Start a Docker container asynchronously.

        Async wrapper that delegates to _start_container_impl() with
        native async callable (asyncio.create_subprocess_exec).

        Args:
            container_name: Name for the container
            worktree_path: Host path to mount as workspace
            env: Environment variables for container

        Returns:
            Container ID or None on failure
        """

        async def _async_run(cmd: list[str]) -> tuple[int, str, str]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            return proc.returncode or 0, stdout.decode(), stderr.decode()

        return await self._start_container_impl(
            container_name=container_name,
            worktree_path=worktree_path,
            env=env,
            run_fn=_async_run,
        )

    async def terminate_async(self, worker_id: int, force: bool = False) -> bool:
        """Terminate a worker container asynchronously.

        Async wrapper that delegates to _terminate_impl() with
        native async callable (asyncio.create_subprocess_exec).

        Args:
            worker_id: Worker to terminate
            force: Force termination (docker kill vs docker stop)

        Returns:
            True if termination succeeded
        """

        async def _async_run(cmd: list[str], timeout: int) -> tuple[int, str, str]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode or 0, stdout.decode(), stderr.decode()

        return await self._terminate_impl(
            worker_id=worker_id,
            force=force,
            run_fn=_async_run,
        )
