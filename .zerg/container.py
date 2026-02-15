"""ZERG v2 Container Launcher - Docker container management for worker isolation."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import docker
from devcontainer import DevcontainerBuilder, DevcontainerManager

__all__ = [
    "ContainerConfig",
    "RunningContainer",
    "ResourceLimits",
    "ContainerLauncher",
]


@dataclass
class ContainerConfig:
    """Configuration for worker container."""

    image: str
    worktree_path: Path
    env_vars: dict[str, str]
    ports: list[int]
    memory_limit: str = "4g"
    cpu_limit: float = 2.0
    network: str = "zerg-internal"


@dataclass
class RunningContainer:
    """Represents a running worker container."""

    container_id: str
    worker_id: str
    worktree_path: Path
    ports: list[int]
    started_at: datetime


@dataclass
class ResourceLimits:
    """Container resource limits."""

    memory: str = "4g"
    cpus: float = 2.0

    @classmethod
    def from_config(cls, config: dict) -> "ResourceLimits":
        """Create ResourceLimits from config dict.

        Args:
            config: Dictionary with memory_limit and cpu_limit keys

        Returns:
            ResourceLimits instance
        """
        return cls(
            memory=config.get("memory_limit", "4g"),
            cpus=config.get("cpu_limit", 2.0),
        )


class ContainerLauncher:
    """Manages Docker containers for worker isolation."""

    def __init__(self, project_path: Path | None = None):
        """Initialize container launcher.

        Args:
            project_path: Path to project root (for devcontainer operations)
        """
        self.client = docker.from_env()
        self.containers: dict[str, RunningContainer] = {}
        self.project_path = project_path or Path(".")
        self.devcontainer_manager = DevcontainerManager(self.project_path)
        self._ensure_network()

    def ensure_image(
        self,
        language: str = "python",
        force_build: bool = False,
    ) -> tuple[bool, str]:
        """Ensure worker image is available, building if necessary.

        Args:
            language: Project language for image selection
            force_build: Force rebuild even if image exists

        Returns:
            Tuple of (success, image_name or error)
        """
        image_name = f"zerg-worker-{language}"
        builder = DevcontainerBuilder(self.project_path)

        # Check if image exists
        if not force_build and builder.image_exists(image_name):
            return True, image_name

        # Need to build - ensure devcontainer is generated
        result = self.devcontainer_manager.ensure_ready(language)
        if not result.success:
            return False, result.error

        return True, image_name

    def launch(self, worker_id: str, config: ContainerConfig) -> RunningContainer:
        """Launch worker container.

        Args:
            worker_id: Unique worker identifier
            config: Container configuration

        Returns:
            RunningContainer instance
        """
        # Build environment
        env = {"ZERG_WORKER_ID": worker_id, **config.env_vars}

        # Port bindings
        port_bindings = {f"{p}/tcp": p for p in config.ports} if config.ports else None

        # Volume mounts
        volumes = {
            str(config.worktree_path.absolute()): {"bind": "/workspace", "mode": "rw"}
        }

        # Launch container
        container = self.client.containers.run(
            config.image,
            detach=True,
            name=f"zerg-worker-{worker_id}",
            environment=env,
            ports=port_bindings,
            volumes=volumes,
            network=config.network,
            mem_limit=config.memory_limit,
            nano_cpus=int(config.cpu_limit * 1e9),
            working_dir="/workspace",
            remove=False,  # Keep for logs on failure
        )

        running = RunningContainer(
            container_id=container.id,
            worker_id=worker_id,
            worktree_path=config.worktree_path,
            ports=config.ports,
            started_at=datetime.now(),
        )

        self.containers[worker_id] = running
        return running

    def stop(self, worker_id: str, timeout: int = 30) -> None:
        """Stop worker container gracefully.

        Args:
            worker_id: Worker identifier
            timeout: Seconds to wait before killing
        """
        if worker_id not in self.containers:
            return

        running = self.containers[worker_id]
        try:
            container = self.client.containers.get(running.container_id)
            container.stop(timeout=timeout)
            container.remove()
        except docker.errors.NotFound:
            pass  # Container already removed; proceed with cleanup

        del self.containers[worker_id]

    def get_logs(self, worker_id: str, tail: int = 100) -> str:
        """Get container logs.

        Args:
            worker_id: Worker identifier
            tail: Number of lines to return

        Returns:
            Log content as string
        """
        if worker_id not in self.containers:
            return ""

        running = self.containers[worker_id]
        try:
            container = self.client.containers.get(running.container_id)
            return container.logs(tail=tail).decode("utf-8")
        except docker.errors.NotFound:
            return ""

    def is_running(self, worker_id: str) -> bool:
        """Check if container is still running.

        Args:
            worker_id: Worker identifier

        Returns:
            True if container is running
        """
        if worker_id not in self.containers:
            return False

        running = self.containers[worker_id]
        try:
            container = self.client.containers.get(running.container_id)
            return container.status == "running"
        except docker.errors.NotFound:
            return False

    def _ensure_network(self) -> None:
        """Ensure internal network exists."""
        try:
            self.client.networks.get("zerg-internal")
        except docker.errors.NotFound:
            self.client.networks.create(
                "zerg-internal",
                driver="bridge",
                internal=True,  # No external access
            )
