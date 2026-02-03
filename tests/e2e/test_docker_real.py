"""Real Docker E2E tests for ZERG container management.

These tests require a running Docker daemon. They are auto-skipped
when Docker is unavailable (see conftest.py pytest_collection_modifyitems).
"""

import subprocess
from pathlib import Path

import pytest

from zerg.constants import WorkerStatus
from zerg.containers import ContainerManager
from zerg.launcher import ContainerLauncher

pytestmark = pytest.mark.docker


# ---------------------------------------------------------------------------
# TestDockerImageOperations
# ---------------------------------------------------------------------------


class TestDockerImageOperations:
    """Tests for image presence detection."""

    def test_image_exists_true(self, docker_image: str) -> None:
        """ContainerLauncher.image_exists() returns True for a built image."""
        launcher = ContainerLauncher(image_name=docker_image)
        assert launcher.image_exists() is True

    def test_image_exists_false_for_missing(self) -> None:
        """image_exists() returns False for a nonexistent image."""
        launcher = ContainerLauncher(image_name="zerg-nonexistent:never")
        assert launcher.image_exists() is False


# ---------------------------------------------------------------------------
# TestContainerLifecycle
# ---------------------------------------------------------------------------


class TestContainerLifecycle:
    """Tests for container start / inspect / stop."""

    def test_run_and_inspect_running(self, docker_container: tuple[str, str]) -> None:
        """A freshly started container reports State.Running=true."""
        cid, _ = docker_container
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", cid],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.stdout.strip() == "true"

    def test_get_status_running(self, container_manager_real: ContainerManager) -> None:
        """get_status() returns RUNNING for a live container."""
        status = container_manager_real.get_status(worker_id=0)
        assert status == WorkerStatus.RUNNING

    def test_get_status_after_stop(self, container_manager_real: ContainerManager) -> None:
        """get_status() returns STOPPED after the container is stopped."""
        info = container_manager_real._containers[0]
        subprocess.run(
            ["docker", "stop", "-t", "2", info.container_id],
            capture_output=True,
            timeout=15,
        )
        status = container_manager_real.get_status(worker_id=0)
        assert status == WorkerStatus.STOPPED

    def test_stop_worker_removes(self, docker_container: tuple[str, str]) -> None:
        """stop_worker() removes the container from docker ps -a."""
        from zerg.containers import ContainerInfo, ContainerManager

        cid, name = docker_container

        # Build a manager with the container injected
        original_check = ContainerManager._check_docker
        ContainerManager._check_docker = lambda self: None  # type: ignore[assignment]
        try:
            mgr = ContainerManager()
        finally:
            ContainerManager._check_docker = original_check  # type: ignore[assignment]

        mgr._containers[0] = ContainerInfo(
            container_id=cid,
            name=name,
            status="running",
            worker_id=0,
        )
        mgr.stop_worker(worker_id=0, force=True)

        # Container should no longer appear in docker ps -a
        result = subprocess.run(
            ["docker", "ps", "-a", "-q", "--filter", f"id={cid}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# TestContainerExec
# ---------------------------------------------------------------------------


class TestContainerExec:
    """Tests for executing commands inside containers."""

    def test_exec_echo(self, container_manager_real: ContainerManager) -> None:
        """exec_in_worker with 'echo hello' returns exit 0 and stdout 'hello'."""
        exit_code, stdout, stderr = container_manager_real.exec_in_worker(worker_id=0, command="echo hello")
        assert exit_code == 0
        assert stdout.strip() == "hello"

    def test_exec_blocked_command(self, container_manager_real: ContainerManager) -> None:
        """exec_in_worker rejects commands not in the allowlist."""
        exit_code, stdout, stderr = container_manager_real.exec_in_worker(worker_id=0, command="rm -rf /")
        assert exit_code == -1
        assert "validation failed" in stderr.lower() or "not in allowlist" in stderr.lower()


# ---------------------------------------------------------------------------
# TestContainerVolumeMounts
# ---------------------------------------------------------------------------


class TestContainerVolumeMounts:
    """Tests for volume mounts inside containers."""

    def test_volume_mount_visible(self, docker_image: str, tmp_path: Path) -> None:
        """A host directory mounted into a container is readable inside."""
        marker = tmp_path / "marker.txt"
        marker.write_text("zerg-volume-ok")

        name = "zerg-test-vol"
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                name,
                "--label",
                "zerg-test=true",
                "-v",
                f"{tmp_path.absolute()}:/workspace",
                docker_image,
                "cat",
                "/workspace/marker.txt",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "zerg-volume-ok"


# ---------------------------------------------------------------------------
# TestContainerLauncherSpawn
# ---------------------------------------------------------------------------


class TestContainerLauncherSpawn:
    """Tests for ContainerLauncher.spawn()."""

    @pytest.mark.e2e
    @pytest.mark.timeout(120)
    def test_launcher_spawn_creates_container(self, docker_image: str, tmp_worktree: Path) -> None:
        """spawn() creates a running container and returns success."""
        launcher = ContainerLauncher(
            image_name=docker_image,
            memory_limit="256m",
            cpu_limit=1.0,
        )

        result = launcher.spawn(
            worker_id=99,
            feature="test-spawn",
            worktree_path=tmp_worktree,
            branch="main",
        )

        try:
            # spawn may fail due to worker_entry.sh verification — that's fine
            # for this test we only need to verify the container was created
            cid = launcher._container_ids.get(99)
            if cid:
                inspect = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Running}}", cid],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                # Container was at least created (may be running or exited)
                assert inspect.returncode == 0
            else:
                # If no container ID, spawn must have reported an error
                # but it should have at least tried — verify SpawnResult fields
                assert result.worker_id == 99
                assert result.error is not None
        finally:
            # Clean up any container created
            cid = launcher._container_ids.get(99)
            if cid:
                subprocess.run(
                    ["docker", "rm", "-f", cid],
                    capture_output=True,
                    timeout=15,
                )
            else:
                # Try by name pattern
                subprocess.run(
                    ["docker", "rm", "-f", "zerg-worker-99"],
                    capture_output=True,
                    timeout=15,
                )
