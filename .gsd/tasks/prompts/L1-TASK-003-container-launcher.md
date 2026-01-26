# L1-TASK-003: Container Launcher

## Objective

Implement Docker container management for worker isolation.

## Context

**Depends on**: L0-TASK-001 (Orchestrator Core), L1-TASK-002 (Port Allocator)

Workers run in Docker containers based on the devcontainer spec. This provides consistent environments, resource limits, and network isolation.

## Files to Modify/Create

```
.zerg/
└── container.py              # CREATE: ContainerLauncher class

.devcontainer/
└── docker-compose.yaml       # MODIFY: Add worker service template
```

## Implementation Requirements

### ContainerLauncher Class

```python
import docker
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

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

class ContainerLauncher:
    """Manages Docker containers for worker isolation."""
    
    def __init__(self):
        self.client = docker.from_env()
        self.containers: dict[str, RunningContainer] = {}
        self._ensure_network()
    
    def launch(self, worker_id: str, config: ContainerConfig) -> RunningContainer:
        """Launch worker container."""
        
        # Build environment
        env = {
            'ZERG_WORKER_ID': worker_id,
            **config.env_vars
        }
        
        # Port bindings
        port_bindings = {f"{p}/tcp": p for p in config.ports}
        
        # Volume mounts
        volumes = {
            str(config.worktree_path.absolute()): {
                'bind': '/workspace',
                'mode': 'rw'
            }
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
            working_dir='/workspace',
            remove=False,  # Keep for logs on failure
        )
        
        running = RunningContainer(
            container_id=container.id,
            worker_id=worker_id,
            worktree_path=config.worktree_path,
            ports=config.ports,
            started_at=datetime.now()
        )
        
        self.containers[worker_id] = running
        return running
    
    def stop(self, worker_id: str, timeout: int = 30) -> None:
        """Stop worker container gracefully."""
        if worker_id not in self.containers:
            return
        
        running = self.containers[worker_id]
        try:
            container = self.client.containers.get(running.container_id)
            container.stop(timeout=timeout)
            container.remove()
        except docker.errors.NotFound:
            pass
        
        del self.containers[worker_id]
    
    def get_logs(self, worker_id: str, tail: int = 100) -> str:
        """Get container logs."""
        if worker_id not in self.containers:
            return ""
        
        running = self.containers[worker_id]
        try:
            container = self.client.containers.get(running.container_id)
            return container.logs(tail=tail).decode('utf-8')
        except docker.errors.NotFound:
            return ""
    
    def is_running(self, worker_id: str) -> bool:
        """Check if container is still running."""
        if worker_id not in self.containers:
            return False
        
        running = self.containers[worker_id]
        try:
            container = self.client.containers.get(running.container_id)
            return container.status == 'running'
        except docker.errors.NotFound:
            return False
    
    def _ensure_network(self) -> None:
        """Ensure internal network exists."""
        try:
            self.client.networks.get('zerg-internal')
        except docker.errors.NotFound:
            self.client.networks.create(
                'zerg-internal',
                driver='bridge',
                internal=True  # No external access
            )
```

### Docker Compose Worker Template

Update `.devcontainer/docker-compose.yaml`:

```yaml
version: '3.8'

services:
  # Base worker service (used as template)
  zerg-worker:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - ${ZERG_WORKTREE_PATH:-./workspace}:/workspace
      - ${HOME}/.claude:/home/claude/.claude:ro
    environment:
      - ZERG_WORKER_ID=${ZERG_WORKER_ID:-default}
      - ZERG_TASK_ID=${ZERG_TASK_ID:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    working_dir: /workspace
    networks:
      - zerg-internal
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'

networks:
  zerg-internal:
    driver: bridge
    internal: true
```

### Resource Limits

```python
@dataclass
class ResourceLimits:
    """Container resource limits."""
    memory: str = "4g"
    cpus: float = 2.0
    
    @classmethod
    def from_config(cls, config: dict) -> "ResourceLimits":
        return cls(
            memory=config.get('memory_limit', '4g'),
            cpus=config.get('cpu_limit', 2.0)
        )
```

## Acceptance Criteria

- [ ] Launch worker containers from devcontainer spec
- [ ] Mount worktree as workspace volume
- [ ] Inject environment variables (ZERG_WORKER_ID, ZERG_TASK_ID)
- [ ] Network isolation on internal bridge
- [ ] Resource limits (memory, CPU)
- [ ] Graceful shutdown with timeout
- [ ] Log retrieval for debugging

## Verification

```bash
cd .zerg && python -c "
from container import ContainerLauncher, ContainerConfig
from pathlib import Path
import tempfile

# Skip if Docker not available
try:
    import docker
    docker.from_env().ping()
except:
    print('SKIP: Docker not available')
    exit(0)

cl = ContainerLauncher()

# Create temp worktree path
with tempfile.TemporaryDirectory() as tmpdir:
    config = ContainerConfig(
        image='python:3.11-slim',
        worktree_path=Path(tmpdir),
        env_vars={'TEST_VAR': 'hello'},
        ports=[8080]
    )
    
    # Launch container
    running = cl.launch('test-001', config)
    assert cl.is_running('test-001')
    
    # Stop container
    cl.stop('test-001')
    assert not cl.is_running('test-001')

print('OK: Container launcher works')
"
```

## Test Cases

```python
# .zerg/tests/test_container.py
import pytest
from container import ContainerLauncher, ContainerConfig
from pathlib import Path

@pytest.fixture
def launcher():
    return ContainerLauncher()

@pytest.fixture
def config(tmp_path):
    return ContainerConfig(
        image='python:3.11-slim',
        worktree_path=tmp_path,
        env_vars={'TEST': '1'},
        ports=[8080]
    )

def test_launch_container(launcher, config):
    running = launcher.launch('w1', config)
    assert running.worker_id == 'w1'
    assert launcher.is_running('w1')
    launcher.stop('w1')

def test_stop_container(launcher, config):
    launcher.launch('w1', config)
    launcher.stop('w1')
    assert not launcher.is_running('w1')

def test_get_logs(launcher, config):
    launcher.launch('w1', config)
    logs = launcher.get_logs('w1')
    assert isinstance(logs, str)
    launcher.stop('w1')

def test_resource_limits(launcher, config):
    config.memory_limit = '2g'
    config.cpu_limit = 1.0
    running = launcher.launch('w1', config)
    # Verify limits applied via docker inspect
    launcher.stop('w1')
```

## Notes

- Requires `docker` Python package: `pip install docker`
- Docker daemon must be running
- Worker image should be pre-built or use standard base
- Internal network prevents workers from external access (security)

## Definition of Done

1. All acceptance criteria checked
2. Verification command passes
3. Unit tests pass: `pytest .zerg/tests/test_container.py`
4. docker-compose.yaml updated with worker template
