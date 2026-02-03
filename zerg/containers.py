"""Container management for ZERG workers."""

import asyncio
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from zerg.config import ZergConfig
from zerg.constants import WorkerStatus
from zerg.exceptions import ContainerError
from zerg.logging import get_logger

logger = get_logger("containers")


@dataclass
class ContainerInfo:
    """Information about a running container."""

    container_id: str
    name: str
    status: str
    worker_id: int
    port: int | None = None
    image: str | None = None


class ContainerManager:
    """Manage Docker containers for ZERG workers."""

    def __init__(
        self,
        config: ZergConfig | None = None,
        compose_file: str | Path | None = None,
    ) -> None:
        """Initialize container manager.

        Args:
            config: ZERG configuration
            compose_file: Path to docker-compose.yaml
        """
        self.config = config or ZergConfig.load()
        self.compose_file = Path(compose_file or ".devcontainer/docker-compose.yaml")
        self._containers: dict[int, ContainerInfo] = {}
        self._check_docker()

    def _check_docker(self) -> None:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning("Docker not available or not running")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Docker not found")

    def _run_docker(
        self,
        *args: str,
        check: bool = True,
        timeout: int = 60,
    ) -> subprocess.CompletedProcess[str]:
        """Run a docker command.

        Args:
            *args: Docker command arguments
            check: Raise on non-zero exit
            timeout: Command timeout

        Returns:
            Completed process result
        """
        cmd = ["docker", *args]
        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise ContainerError(
                f"Docker command failed: {e.stderr.strip()}",
                details={"command": " ".join(cmd), "exit_code": e.returncode},
            ) from e
        except subprocess.TimeoutExpired:
            raise ContainerError(
                f"Docker command timed out after {timeout}s",
                details={"command": " ".join(cmd)},
            ) from None

    def _run_compose(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        check: bool = True,
        timeout: int = 120,
    ) -> subprocess.CompletedProcess[str]:
        """Run a docker-compose command.

        Args:
            *args: Compose command arguments
            env: Environment variables
            check: Raise on non-zero exit
            timeout: Command timeout

        Returns:
            Completed process result
        """
        cmd = ["docker", "compose", "-f", str(self.compose_file), *args]
        logger.debug(f"Running: {' '.join(cmd)}")

        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=full_env,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            raise ContainerError(
                f"Compose command failed: {e.stderr.strip()}",
                details={"command": " ".join(cmd), "exit_code": e.returncode},
            ) from e
        except subprocess.TimeoutExpired:
            raise ContainerError(
                f"Compose command timed out after {timeout}s",
                details={"command": " ".join(cmd)},
            ) from None

    def build(self, no_cache: bool = False) -> None:
        """Build the worker image.

        Args:
            no_cache: Build without cache
        """
        args = ["build"]
        if no_cache:
            args.append("--no-cache")

        logger.info("Building worker image...")
        self._run_compose(*args, timeout=300)
        logger.info("Worker image built")

    def start_worker(
        self,
        worker_id: int,
        feature: str,
        port: int,
        worktree_path: str | Path,
        branch: str,
    ) -> ContainerInfo:
        """Start a worker container.

        Args:
            worker_id: Worker identifier
            feature: Feature name
            port: Port for the container
            worktree_path: Path to worker's worktree
            branch: Git branch for the worker

        Returns:
            ContainerInfo for the started container
        """
        container_name = f"zerg-worker-{worker_id}"

        # Environment for docker-compose
        env = {
            "ZERG_WORKER_ID": str(worker_id),
            "ZERG_FEATURE": feature,
            "ZERG_BRANCH": branch,
            "ZERG_WORKTREE": str(worktree_path),
        }

        # Stop existing container if any
        self._run_docker("rm", "-f", container_name, check=False)

        # Start with compose
        logger.info(f"Starting worker {worker_id} on port {port}")
        self._run_compose("up", "-d", "worker", env=env)

        # Wait for container to be ready
        time.sleep(2)

        # Get container ID
        result = self._run_docker(
            "ps",
            "-q",
            "-f",
            f"name={container_name}",
            check=False,
        )
        container_id = result.stdout.strip()

        if not container_id:
            # Try alternate naming
            result = self._run_docker("ps", "-q", "--latest", check=False)
            container_id = result.stdout.strip() or f"unknown-{worker_id}"

        info = ContainerInfo(
            container_id=container_id,
            name=container_name,
            status="running",
            worker_id=worker_id,
            port=port,
        )

        self._containers[worker_id] = info
        logger.info(f"Worker {worker_id} started: {container_id[:12]}")

        return info

    def stop_worker(
        self,
        worker_id: int,
        timeout: int = 30,
        force: bool = False,
    ) -> None:
        """Stop a worker container.

        Args:
            worker_id: Worker identifier
            timeout: Graceful stop timeout
            force: Force kill
        """
        info = self._containers.get(worker_id)
        if not info:
            logger.warning(f"Worker {worker_id} not found")
            return

        container_name = info.name

        if force:
            self._run_docker("kill", container_name, check=False)
        else:
            self._run_docker("stop", "-t", str(timeout), container_name, check=False)

        self._run_docker("rm", "-f", container_name, check=False)
        del self._containers[worker_id]

        logger.info(f"Worker {worker_id} stopped")

    def stop_all(self, force: bool = False) -> int:
        """Stop all worker containers.

        Args:
            force: Force kill

        Returns:
            Number of containers stopped
        """
        count = 0
        for worker_id in list(self._containers.keys()):
            self.stop_worker(worker_id, force=force)
            count += 1

        # Also stop any orphaned zerg containers
        result = self._run_docker(
            "ps",
            "-q",
            "-f",
            "name=zerg-worker-",
            check=False,
        )
        for container_id in result.stdout.strip().split("\n"):
            if container_id:
                self._run_docker("rm", "-f", container_id, check=False)
                count += 1

        logger.info(f"Stopped {count} containers")
        return count

    def get_status(self, worker_id: int) -> WorkerStatus:
        """Get the status of a worker container.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerStatus
        """
        info = self._containers.get(worker_id)
        if not info:
            return WorkerStatus.STOPPED

        result = self._run_docker(
            "inspect",
            "-f",
            "{{.State.Status}}",
            info.container_id,
            check=False,
        )
        status = result.stdout.strip()

        status_map = {
            "running": WorkerStatus.RUNNING,
            "paused": WorkerStatus.CHECKPOINTING,
            "exited": WorkerStatus.STOPPED,
            "dead": WorkerStatus.CRASHED,
        }

        return status_map.get(status, WorkerStatus.STOPPED)

    def get_logs(
        self,
        worker_id: int,
        tail: int = 100,
        follow: bool = False,
    ) -> str:
        """Get logs from a worker container.

        Args:
            worker_id: Worker identifier
            tail: Number of lines
            follow: Stream logs (blocking)

        Returns:
            Log content
        """
        info = self._containers.get(worker_id)
        if not info:
            return ""

        args = ["logs", "--tail", str(tail)]
        if follow:
            args.append("-f")
        args.append(info.container_id)

        result = self._run_docker(*args, check=False, timeout=5 if not follow else 3600)
        return result.stdout + result.stderr

    def health_check(self, worker_id: int) -> bool:
        """Check if a worker container is healthy.

        Args:
            worker_id: Worker identifier

        Returns:
            True if healthy
        """
        info = self._containers.get(worker_id)
        if not info:
            return False

        status = self.get_status(worker_id)
        return status == WorkerStatus.RUNNING

    # Allowlist of commands that can be executed in containers
    ALLOWED_EXEC_COMMANDS = {
        # Test commands
        "pytest",
        "python -m pytest",
        "npm test",
        "cargo test",
        "go test",
        # Lint commands
        "ruff",
        "ruff check",
        "flake8",
        "mypy",
        "eslint",
        "prettier",
        # Build commands
        "make",
        "npm run build",
        "cargo build",
        "go build",
        # Git commands (read-only)
        "git status",
        "git diff",
        "git log",
        # Info commands
        "pwd",
        "ls",
        "cat",
        "echo",
        "which",
    }

    def _validate_exec_command(self, command: str) -> tuple[bool, str | None]:
        """Validate a command for container execution.

        Args:
            command: Command to validate

        Returns:
            Tuple of (is_valid, error_message or None)
        """
        if not command:
            return False, "Empty command"

        # Check for shell metacharacters that could enable injection
        dangerous_chars = set(";|&`$(){}[]<>\\")
        found_dangerous = set(command) & dangerous_chars
        if found_dangerous:
            return False, f"Command contains shell metacharacters: {found_dangerous}"

        # Check if command starts with an allowed prefix
        command_lower = command.lower().strip()
        for allowed in self.ALLOWED_EXEC_COMMANDS:
            if command_lower.startswith(allowed.lower()):
                return True, None

        cmd_name = command.split()[0] if command.split() else command
        return False, f"Command not in allowlist: {cmd_name}"

    def exec_in_worker(
        self,
        worker_id: int,
        command: str,
        timeout: int = 60,
        validate: bool = True,
    ) -> tuple[int, str, str]:
        """Execute a command in a worker container.

        Args:
            worker_id: Worker identifier
            command: Command to execute
            timeout: Command timeout
            validate: Whether to validate command against allowlist

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        info = self._containers.get(worker_id)
        if not info:
            return -1, "", "Worker not found"

        # Validate command if requested
        if validate:
            is_valid, error = self._validate_exec_command(command)
            if not is_valid:
                logger.warning(f"Blocked container exec command: {error}")
                return -1, "", f"Command validation failed: {error}"

        result = self._run_docker(
            "exec",
            info.container_id,
            "sh",
            "-c",
            command,
            check=False,
            timeout=timeout,
        )

        return result.returncode, result.stdout, result.stderr

    def get_all_containers(self) -> dict[int, ContainerInfo]:
        """Get all tracked containers.

        Returns:
            Dictionary of worker_id to ContainerInfo
        """
        return self._containers.copy()

    # --- Async methods ---

    async def _run_docker_async(
        self,
        *args: str,
        timeout: int = 60,
    ) -> tuple[int, str, str]:
        """Run a docker command asynchronously.

        Args:
            *args: Docker command arguments
            timeout: Command timeout

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        cmd = ["docker", *args]
        logger.debug(f"Running async: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return (
                proc.returncode or 0,
                stdout_bytes.decode(),
                stderr_bytes.decode(),
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return 1, "", f"timeout after {timeout}s"

    async def _run_compose_async(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        timeout: int = 120,
    ) -> tuple[int, str, str]:
        """Run a docker-compose command asynchronously.

        Args:
            *args: Compose command arguments
            env: Environment variables
            timeout: Command timeout

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        cmd = ["docker", "compose", "-f", str(self.compose_file), *args]
        logger.debug(f"Running async: {' '.join(cmd)}")

        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return (
                proc.returncode or 0,
                stdout_bytes.decode(),
                stderr_bytes.decode(),
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return 1, "", f"timeout after {timeout}s"

    async def build_async(self, no_cache: bool = False) -> None:
        """Build the worker image asynchronously.

        Args:
            no_cache: Build without cache
        """
        args = ["build"]
        if no_cache:
            args.append("--no-cache")

        logger.info("Building worker image (async)...")
        returncode, _, stderr = await self._run_compose_async(*args, timeout=300)
        if returncode != 0:
            raise ContainerError(
                f"Compose build failed: {stderr.strip()}",
                details={"exit_code": returncode},
            )
        logger.info("Worker image built")

    async def stop_worker_async(
        self,
        worker_id: int,
        timeout: int = 30,
        force: bool = False,
    ) -> None:
        """Stop a worker container asynchronously.

        Args:
            worker_id: Worker identifier
            timeout: Graceful stop timeout
            force: Force kill
        """
        info = self._containers.get(worker_id)
        if not info:
            logger.warning(f"Worker {worker_id} not found")
            return

        container_name = info.name

        if force:
            await self._run_docker_async("kill", container_name)
        else:
            await self._run_docker_async("stop", "-t", str(timeout), container_name)

        await self._run_docker_async("rm", "-f", container_name)
        del self._containers[worker_id]

        logger.info(f"Worker {worker_id} stopped (async)")

    async def stop_all_async(self, force: bool = False) -> int:
        """Stop all worker containers asynchronously.

        Args:
            force: Force kill

        Returns:
            Number of containers stopped
        """
        tasks = [self.stop_worker_async(worker_id, force=force) for worker_id in list(self._containers.keys())]
        await asyncio.gather(*tasks, return_exceptions=True)
        count = len(tasks)

        # Also stop any orphaned zerg containers
        returncode, stdout, _ = await self._run_docker_async(
            "ps",
            "-q",
            "-f",
            "name=zerg-worker-",
        )
        for container_id in stdout.strip().split("\n"):
            if container_id:
                await self._run_docker_async("rm", "-f", container_id)
                count += 1

        logger.info(f"Stopped {count} containers (async)")
        return count

    async def get_status_async(self, worker_id: int) -> WorkerStatus:
        """Get the status of a worker container asynchronously.

        Args:
            worker_id: Worker identifier

        Returns:
            WorkerStatus
        """
        info = self._containers.get(worker_id)
        if not info:
            return WorkerStatus.STOPPED

        returncode, stdout, _ = await self._run_docker_async(
            "inspect",
            "-f",
            "{{.State.Status}}",
            info.container_id,
        )
        status = stdout.strip()

        status_map = {
            "running": WorkerStatus.RUNNING,
            "paused": WorkerStatus.CHECKPOINTING,
            "exited": WorkerStatus.STOPPED,
            "dead": WorkerStatus.CRASHED,
        }

        return status_map.get(status, WorkerStatus.STOPPED)

    async def exec_in_worker_async(
        self,
        worker_id: int,
        command: str,
        timeout: int = 60,
        validate: bool = True,
    ) -> tuple[int, str, str]:
        """Execute a validated command in a worker container asynchronously.

        Uses create_subprocess_exec with explicit argument list to avoid
        shell injection. The command string is validated against the allowlist
        before execution.

        Args:
            worker_id: Worker identifier
            command: Command to execute (validated against ALLOWED_EXEC_COMMANDS)
            timeout: Command timeout
            validate: Whether to validate command against allowlist

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        info = self._containers.get(worker_id)
        if not info:
            return -1, "", "Worker not found"

        if validate:
            is_valid, error = self._validate_exec_command(command)
            if not is_valid:
                logger.warning(f"Blocked container exec command: {error}")
                return -1, "", f"Command validation failed: {error}"

        return await self._run_docker_async(
            "exec",
            info.container_id,
            "sh",
            "-c",
            command,
            timeout=timeout,
        )

    def cleanup_volumes(self, feature: str) -> None:
        """Clean up Docker volumes for a feature.

        Args:
            feature: Feature name
        """
        volume_name = f"zerg-tasks-{feature}"
        self._run_docker("volume", "rm", "-f", volume_name, check=False)
        logger.info(f"Cleaned up volume {volume_name}")
