"""ZERG v2 DevContainer - Generation and build automation for worker isolation."""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DevcontainerConfig:
    """Configuration for devcontainer generation."""

    name: str = "zerg-worker"
    image_name: str = "zerg-worker"
    build_context: str = "."
    python_version: str = "3.12"
    node_version: str = "20"
    install_claude: bool = True
    extensions: list[str] = field(default_factory=list)
    post_create_commands: list[str] = field(default_factory=list)


# Language-specific Dockerfile templates
DOCKERFILE_TEMPLATES = {
    "python": '''# ZERG Worker - Python
FROM python:{python_version}-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    curl \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Claude Code
RUN curl -fsSL https://deb.nodesource.com/setup_{node_version}.x | bash - \\
    && apt-get install -y nodejs \\
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
{claude_install}

# Set up workspace
WORKDIR /workspace

# Install Python dependencies if requirements exist
COPY requirements*.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Default command
CMD ["bash"]
''',
    "typescript": '''# ZERG Worker - TypeScript/Node.js
FROM node:{node_version}-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
{claude_install}

# Set up workspace
WORKDIR /workspace

# Install dependencies if package.json exists
COPY package*.json* ./
RUN if [ -f package.json ]; then npm install; fi

# Default command
CMD ["bash"]
''',
    "go": '''# ZERG Worker - Go
FROM golang:{go_version}-alpine

# Install system dependencies
RUN apk add --no-cache git curl bash nodejs npm

# Install Claude Code CLI
{claude_install}

# Set up workspace
WORKDIR /workspace

# Download dependencies if go.mod exists
COPY go.* ./
RUN if [ -f go.mod ]; then go mod download; fi

# Default command
CMD ["bash"]
''',
    "rust": '''# ZERG Worker - Rust
FROM rust:{rust_version}-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    curl \\
    pkg-config \\
    libssl-dev \\
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Claude Code
RUN curl -fsSL https://deb.nodesource.com/setup_{node_version}.x | bash - \\
    && apt-get install -y nodejs \\
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
{claude_install}

# Set up workspace
WORKDIR /workspace

# Default command
CMD ["bash"]
''',
    "default": '''# ZERG Worker - Generic
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    curl \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_{node_version}.x | bash - \\
    && apt-get install -y nodejs \\
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
{claude_install}

# Set up workspace
WORKDIR /workspace

# Default command
CMD ["bash"]
''',
}

CLAUDE_INSTALL_CMD = "RUN npm install -g @anthropic-ai/claude-code"

DEVCONTAINER_JSON_TEMPLATE = {
    "name": "zerg-worker",
    "build": {
        "dockerfile": "Dockerfile",
        "context": "..",
    },
    "workspaceFolder": "/workspace",
    "workspaceMount": "source=${localWorkspaceFolder},target=/workspace,type=bind",
    "remoteUser": "root",
    "features": {},
    "customizations": {
        "vscode": {
            "extensions": [],
        }
    },
    "postCreateCommand": "echo 'ZERG worker ready'",
    "forwardPorts": [],
    "runArgs": ["--network=zerg-internal"],
}

DOCKER_COMPOSE_TEMPLATE = '''# ZERG Worker Compose Configuration
version: '3.8'

services:
  worker:
    build:
      context: ..
      dockerfile: .devcontainer/Dockerfile
    image: {image_name}
    volumes:
      - ..:/workspace:cached
    working_dir: /workspace
    environment:
      - ZERG_WORKER_ID=${{WORKER_ID:-0}}
      - ANTHROPIC_API_KEY=${{ANTHROPIC_API_KEY}}
    networks:
      - zerg-internal
    deploy:
      resources:
        limits:
          cpus: '{cpu_limit}'
          memory: {memory_limit}

networks:
  zerg-internal:
    driver: bridge
    internal: true
'''

POST_CREATE_TEMPLATE = '''#!/bin/bash
# ZERG Worker Post-Create Script

set -e

echo "Setting up ZERG worker environment..."

# Install project dependencies
{install_commands}

# Verify Claude Code is available
if command -v claude &> /dev/null; then
    echo "Claude Code CLI: $(claude --version)"
else
    echo "Warning: Claude Code CLI not found"
fi

echo "ZERG worker setup complete"
'''


@dataclass
class BuildResult:
    """Result of devcontainer build."""

    success: bool
    image_name: str
    image_id: str = ""
    build_time_seconds: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "image_name": self.image_name,
            "image_id": self.image_id,
            "build_time_seconds": self.build_time_seconds,
            "error": self.error,
        }


class DevcontainerGenerator:
    """Generate devcontainer configuration for ZERG workers."""

    def __init__(self, project_path: Path, config: DevcontainerConfig | None = None):
        """Initialize generator.

        Args:
            project_path: Path to project root
            config: Devcontainer configuration
        """
        self.project_path = project_path
        self.config = config or DevcontainerConfig()
        self.devcontainer_dir = project_path / ".devcontainer"

    def generate(self, language: str = "python", framework: str | None = None) -> Path:
        """Generate devcontainer files.

        Args:
            language: Project language (python, typescript, go, rust)
            framework: Optional framework name

        Returns:
            Path to generated .devcontainer directory
        """
        # Create directory
        self.devcontainer_dir.mkdir(parents=True, exist_ok=True)

        # Generate files
        self._generate_dockerfile(language)
        self._generate_devcontainer_json(language, framework)
        self._generate_docker_compose()
        self._generate_post_create(language)

        return self.devcontainer_dir

    def _generate_dockerfile(self, language: str) -> None:
        """Generate Dockerfile for the language."""
        template = DOCKERFILE_TEMPLATES.get(language, DOCKERFILE_TEMPLATES["default"])

        # Format template
        if self.config.install_claude:
            claude_install = CLAUDE_INSTALL_CMD
        else:
            claude_install = "# Claude CLI install skipped"

        content = template.format(
            python_version=self.config.python_version,
            node_version=self.config.node_version,
            go_version="1.22",
            rust_version="1.75",
            claude_install=claude_install,
        )

        dockerfile_path = self.devcontainer_dir / "Dockerfile"
        dockerfile_path.write_text(content)

    def _generate_devcontainer_json(self, language: str, framework: str | None) -> None:
        """Generate devcontainer.json."""
        config: dict[str, Any] = DEVCONTAINER_JSON_TEMPLATE.copy()
        config["name"] = self.config.name

        # Add language-specific extensions
        extensions = list(self.config.extensions)
        if language == "python":
            extensions.extend([
                "ms-python.python",
                "ms-python.vscode-pylance",
            ])
        elif language == "typescript":
            extensions.extend([
                "dbaeumer.vscode-eslint",
                "esbenp.prettier-vscode",
            ])
        elif language == "go":
            extensions.append("golang.go")
        elif language == "rust":
            extensions.append("rust-lang.rust-analyzer")

        config["customizations"]["vscode"]["extensions"] = extensions

        # Add framework-specific features
        if framework:
            config["features"][f"framework-{framework}"] = True

        devcontainer_json_path = self.devcontainer_dir / "devcontainer.json"
        devcontainer_json_path.write_text(json.dumps(config, indent=2))

    def _generate_docker_compose(self) -> None:
        """Generate docker-compose.yaml."""
        content = DOCKER_COMPOSE_TEMPLATE.format(
            image_name=self.config.image_name,
            cpu_limit="2.0",
            memory_limit="4G",
        )

        compose_path = self.devcontainer_dir / "docker-compose.yaml"
        compose_path.write_text(content)

    def _generate_post_create(self, language: str) -> None:
        """Generate post-create.sh script."""
        install_commands = []

        if language == "python":
            install_commands.append(
                'if [ -f requirements.txt ]; then pip install -r requirements.txt; fi'
            )
            install_commands.append(
                'if [ -f pyproject.toml ]; then pip install -e .; fi'
            )
        elif language == "typescript":
            install_commands.append('if [ -f package.json ]; then npm install; fi')
        elif language == "go":
            install_commands.append('if [ -f go.mod ]; then go mod download; fi')
        elif language == "rust":
            install_commands.append('if [ -f Cargo.toml ]; then cargo fetch; fi')

        # Add custom commands
        install_commands.extend(self.config.post_create_commands)

        content = POST_CREATE_TEMPLATE.format(
            install_commands="\n".join(install_commands) or "echo 'No dependencies to install'"
        )

        post_create_path = self.devcontainer_dir / "post-create.sh"
        post_create_path.write_text(content)
        post_create_path.chmod(0o755)


class DevcontainerBuilder:
    """Build devcontainer images for ZERG workers."""

    def __init__(self, project_path: Path):
        """Initialize builder.

        Args:
            project_path: Path to project root
        """
        self.project_path = project_path
        self.devcontainer_dir = project_path / ".devcontainer"

    def image_exists(self, image_name: str) -> bool:
        """Check if image already exists.

        Args:
            image_name: Name of the image to check

        Returns:
            True if image exists
        """
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", image_name],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def build(
        self,
        image_name: str = "zerg-worker",
        no_cache: bool = False,
        pull: bool = True,
    ) -> BuildResult:
        """Build the devcontainer image.

        Args:
            image_name: Name for the built image
            no_cache: Force rebuild without cache
            pull: Pull base image before build

        Returns:
            BuildResult with build status
        """
        import time

        dockerfile_path = self.devcontainer_dir / "Dockerfile"
        if not dockerfile_path.exists():
            return BuildResult(
                success=False,
                image_name=image_name,
                error="Dockerfile not found. Run devcontainer generation first.",
            )

        # Build command
        cmd = [
            "docker", "build",
            "-t", image_name,
            "-f", str(dockerfile_path),
        ]

        if no_cache:
            cmd.append("--no-cache")
        if pull:
            cmd.append("--pull")

        cmd.append(str(self.project_path))

        # Execute build
        start_time = time.time()
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(self.project_path),
            )
            build_time = time.time() - start_time

            # Get image ID
            inspect_result = subprocess.run(
                ["docker", "image", "inspect", image_name, "--format", "{{.Id}}"],
                capture_output=True,
                text=True,
                check=True,
            )
            image_id = inspect_result.stdout.strip()

            return BuildResult(
                success=True,
                image_name=image_name,
                image_id=image_id,
                build_time_seconds=build_time,
            )
        except subprocess.CalledProcessError as e:
            return BuildResult(
                success=False,
                image_name=image_name,
                error=e.stderr or str(e),
            )
        except FileNotFoundError:
            return BuildResult(
                success=False,
                image_name=image_name,
                error="Docker not found. Please install Docker.",
            )

    def build_if_needed(
        self,
        image_name: str = "zerg-worker",
        force: bool = False,
    ) -> BuildResult:
        """Build image only if it doesn't exist or force is True.

        Args:
            image_name: Name for the image
            force: Force rebuild even if exists

        Returns:
            BuildResult with build status
        """
        if not force and self.image_exists(image_name):
            return BuildResult(
                success=True,
                image_name=image_name,
                image_id="cached",
            )

        return self.build(image_name=image_name)


class DevcontainerManager:
    """High-level manager for devcontainer operations."""

    def __init__(self, project_path: Path):
        """Initialize manager.

        Args:
            project_path: Path to project root
        """
        self.project_path = project_path
        self.generator = DevcontainerGenerator(project_path)
        self.builder = DevcontainerBuilder(project_path)

    def setup(
        self,
        language: str = "python",
        framework: str | None = None,
        build: bool = True,
        force_build: bool = False,
    ) -> tuple[Path, BuildResult | None]:
        """Complete devcontainer setup: generate and optionally build.

        Args:
            language: Project language
            framework: Optional framework
            build: Whether to build the image
            force_build: Force rebuild even if image exists

        Returns:
            Tuple of (devcontainer_path, build_result)
        """
        # Generate configuration
        devcontainer_path = self.generator.generate(language, framework)

        # Build if requested
        build_result = None
        if build:
            image_name = f"zerg-worker-{language}"
            build_result = self.builder.build_if_needed(
                image_name=image_name,
                force=force_build,
            )

        return devcontainer_path, build_result

    def ensure_ready(self, language: str = "python") -> BuildResult:
        """Ensure devcontainer is ready for use.

        Generates if missing, builds if needed.

        Args:
            language: Project language

        Returns:
            BuildResult indicating readiness
        """
        devcontainer_dir = self.project_path / ".devcontainer"
        dockerfile = devcontainer_dir / "Dockerfile"

        # Generate if missing
        if not dockerfile.exists():
            self.generator.generate(language)

        # Build if needed
        image_name = f"zerg-worker-{language}"
        return self.builder.build_if_needed(image_name=image_name)


__all__ = [
    "DevcontainerConfig",
    "BuildResult",
    "DevcontainerGenerator",
    "DevcontainerBuilder",
    "DevcontainerManager",
    "DOCKERFILE_TEMPLATES",
]
