"""Integration tests for container execution with live Docker.

These tests require a real Docker daemon and are skipped when Docker
is not available. All containers and images use a '-test' suffix to
avoid interfering with real ZERG containers.
"""

import json
import subprocess
from pathlib import Path

import pytest

# Compute project root dynamically from this file's location
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
TEST_IMAGE = "zerg-worker-test"
DOCKERFILE_PATH = ".devcontainer/Dockerfile"


def docker_available() -> bool:
    """Check if Docker daemon is accessible."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


skip_no_docker = pytest.mark.skipif(
    not docker_available(),
    reason="Docker not available",
)


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess command with defaults for test usage."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    return subprocess.run(cmd, **kwargs)


def _remove_container(name: str) -> None:
    """Force-remove a container by name, ignoring errors."""
    _run(["docker", "rm", "-f", name])


def _remove_image(name: str) -> None:
    """Remove an image by name, ignoring errors."""
    _run(["docker", "rmi", "-f", name])


@skip_no_docker
class TestImageBuilds:
    """Verify the devcontainer Dockerfile builds successfully."""

    def test_image_builds(self):
        try:
            result = _run(
                [
                    "docker",
                    "build",
                    "-t",
                    TEST_IMAGE,
                    "-f",
                    DOCKERFILE_PATH,
                    ".",
                ],
                cwd=PROJECT_ROOT,
                timeout=300,
            )
            assert result.returncode == 0, f"Docker build failed.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        finally:
            _remove_image(TEST_IMAGE)


@skip_no_docker
class TestContainerSpawnsWithResourceLimits:
    """Verify containers can be started with memory and CPU limits."""

    CONTAINER_NAME = "zerg-worker-resource-test"

    def test_container_spawns_with_resource_limits(self):
        try:
            # Build the image first
            build = _run(
                [
                    "docker",
                    "build",
                    "-t",
                    TEST_IMAGE,
                    "-f",
                    DOCKERFILE_PATH,
                    ".",
                ],
                cwd=PROJECT_ROOT,
                timeout=300,
            )
            assert build.returncode == 0, f"Docker build failed.\nstderr: {build.stderr}"

            # Run container with resource limits
            run_result = _run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    self.CONTAINER_NAME,
                    "--memory",
                    "256m",
                    "--cpus",
                    "1.0",
                    TEST_IMAGE,
                    "sleep",
                    "30",
                ],
                timeout=30,
            )
            assert run_result.returncode == 0, f"Container start failed.\nstderr: {run_result.stderr}"

            # Inspect the container for resource limits
            inspect_result = _run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .HostConfig}}",
                    self.CONTAINER_NAME,
                ],
                timeout=10,
            )
            assert inspect_result.returncode == 0

            host_config = json.loads(inspect_result.stdout)

            # 256 MB in bytes
            expected_memory = 256 * 1024 * 1024
            assert host_config["Memory"] == expected_memory, (
                f"Expected Memory={expected_memory}, got {host_config['Memory']}"
            )

            # 1.0 CPU = 1_000_000_000 NanoCpus
            expected_nano_cpus = 1_000_000_000
            assert host_config["NanoCpus"] == expected_nano_cpus, (
                f"Expected NanoCpus={expected_nano_cpus}, got {host_config['NanoCpus']}"
            )
        finally:
            _remove_container(self.CONTAINER_NAME)
            _remove_image(TEST_IMAGE)


@skip_no_docker
class TestOrphanCleanup:
    """Verify orphaned zerg containers can be detected and removed."""

    CONTAINER_NAME = "zerg-worker-test-orphan"

    def test_orphan_cleanup(self):
        try:
            # Create a stopped container to simulate an orphan
            create_result = _run(
                [
                    "docker",
                    "create",
                    "--name",
                    self.CONTAINER_NAME,
                    "ubuntu:latest",
                    "echo",
                    "orphan",
                ],
                timeout=60,
            )
            assert create_result.returncode == 0, f"Failed to create orphan container.\nstderr: {create_result.stderr}"

            # Verify the container exists
            ps_result = _run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"name={self.CONTAINER_NAME}",
                    "--format",
                    "{{.Names}}",
                ],
                timeout=10,
            )
            assert self.CONTAINER_NAME in ps_result.stdout, f"Orphan container not found. Output: {ps_result.stdout}"

            # Run cleanup logic: find containers matching the filter and remove them
            find_result = _run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"name={self.CONTAINER_NAME}",
                    "--format",
                    "{{.Names}}",
                ],
                timeout=10,
            )
            containers = find_result.stdout.strip().splitlines()
            assert len(containers) > 0, "No containers found to clean up"

            for container in containers:
                rm_result = _run(
                    ["docker", "rm", "-f", container.strip()],
                    timeout=10,
                )
                assert rm_result.returncode == 0, f"Failed to remove container {container}.\nstderr: {rm_result.stderr}"

            # Verify the container no longer exists
            verify_result = _run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"name={self.CONTAINER_NAME}",
                    "--format",
                    "{{.Names}}",
                ],
                timeout=10,
            )
            assert self.CONTAINER_NAME not in verify_result.stdout, (
                f"Orphan container still exists after cleanup. Output: {verify_result.stdout}"
            )
        finally:
            _remove_container(self.CONTAINER_NAME)


@skip_no_docker
class TestContainerLogsAccessible:
    """Verify container logs can be retrieved after execution."""

    CONTAINER_NAME = "zerg-worker-logs-test"

    def test_container_logs_accessible(self):
        try:
            # Run a container that echoes a known string
            run_result = _run(
                [
                    "docker",
                    "run",
                    "--name",
                    self.CONTAINER_NAME,
                    "ubuntu:latest",
                    "echo",
                    "hello zerg",
                ],
                timeout=30,
            )
            assert run_result.returncode == 0, f"Container run failed.\nstderr: {run_result.stderr}"

            # Fetch logs
            logs_result = _run(
                ["docker", "logs", self.CONTAINER_NAME],
                timeout=10,
            )
            assert logs_result.returncode == 0, f"Failed to fetch logs.\nstderr: {logs_result.stderr}"
            assert "hello zerg" in logs_result.stdout, f"Expected 'hello zerg' in logs. Got: {logs_result.stdout}"
        finally:
            _remove_container(self.CONTAINER_NAME)


@skip_no_docker
class TestHealthcheckMarker:
    """Verify the healthcheck marker file mechanism works inside containers."""

    CONTAINER_NAME = "zerg-worker-health-test"

    def test_healthcheck_marker(self):
        try:
            # Start a container in detached mode
            run_result = _run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    self.CONTAINER_NAME,
                    "ubuntu:latest",
                    "sleep",
                    "30",
                ],
                timeout=30,
            )
            assert run_result.returncode == 0, f"Container start failed.\nstderr: {run_result.stderr}"

            # Create the healthcheck marker file
            exec_touch = _run(
                [
                    "docker",
                    "exec",
                    self.CONTAINER_NAME,
                    "touch",
                    "/tmp/.zerg-alive",
                ],
                timeout=10,
            )
            assert exec_touch.returncode == 0, f"Failed to create marker file.\nstderr: {exec_touch.stderr}"

            # Verify the marker file exists
            exec_test = _run(
                [
                    "docker",
                    "exec",
                    self.CONTAINER_NAME,
                    "test",
                    "-f",
                    "/tmp/.zerg-alive",
                ],
                timeout=10,
            )
            assert exec_test.returncode == 0, "Healthcheck marker file /tmp/.zerg-alive does not exist in container"
        finally:
            _remove_container(self.CONTAINER_NAME)
