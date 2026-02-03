"""Dynamic devcontainer generation with multi-language support.

Uses devcontainer "features" to add multiple language runtimes to a base image.
See: https://containers.dev/features
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zerg.logging import get_logger

logger = get_logger(__name__)


# Devcontainer features from ghcr.io/devcontainers/features/
# Maps language name to (feature_url, default_options)
DEVCONTAINER_FEATURES: dict[str, tuple[str, dict[str, Any]]] = {
    "python": ("ghcr.io/devcontainers/features/python:1", {"version": "3.12"}),
    "javascript": ("ghcr.io/devcontainers/features/node:1", {"version": "20"}),
    "typescript": ("ghcr.io/devcontainers/features/node:1", {"version": "20"}),
    "go": ("ghcr.io/devcontainers/features/go:1", {"version": "1.22"}),
    "rust": ("ghcr.io/devcontainers/features/rust:1", {}),
    "java": ("ghcr.io/devcontainers/features/java:1", {"version": "21"}),
    "ruby": ("ghcr.io/devcontainers/features/ruby:1", {}),
    "csharp": ("ghcr.io/devcontainers/features/dotnet:1", {"version": "8.0"}),
    # Common utilities
    "git": ("ghcr.io/devcontainers/features/git:1", {}),
    "github-cli": ("ghcr.io/devcontainers/features/github-cli:1", {}),
    "docker-in-docker": ("ghcr.io/devcontainers/features/docker-in-docker:1", {}),
}

# Languages that require custom installation via postCreateCommand
# Maps language to install command
CUSTOM_INSTALL_COMMANDS: dict[str, str] = {
    "r": "apt-get update && apt-get install -y r-base r-base-dev",
    "julia": "curl -fsSL https://install.julialang.org | sh -s -- -y --default-channel release",
    "cpp": "apt-get update && apt-get install -y build-essential cmake gdb",
    "sql": "",  # SQL doesn't need runtime, database clients depend on specific DB
}

# Default base image for multi-language containers
DEFAULT_BASE_IMAGE = "mcr.microsoft.com/devcontainers/base:ubuntu"

# Single-language optimized images (faster startup)
SINGLE_LANGUAGE_IMAGES: dict[str, str] = {
    "python": "mcr.microsoft.com/devcontainers/python:3.12",
    "javascript": "mcr.microsoft.com/devcontainers/javascript-node:20",
    "typescript": "mcr.microsoft.com/devcontainers/typescript-node:20",
    "go": "mcr.microsoft.com/devcontainers/go:1.22",
    "rust": "mcr.microsoft.com/devcontainers/rust:latest",
    "java": "mcr.microsoft.com/devcontainers/java:21",
    "ruby": "mcr.microsoft.com/devcontainers/ruby:latest",
    "csharp": "mcr.microsoft.com/devcontainers/dotnet:8.0",
}


@dataclass
class DevcontainerSpec:
    """Specification for a devcontainer configuration."""

    name: str = "ZERG Worker"
    base_image: str = DEFAULT_BASE_IMAGE
    features: dict[str, dict[str, Any]] = field(default_factory=dict)
    post_create_commands: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    mounts: list[str] = field(default_factory=list)
    run_args: list[str] = field(default_factory=list)
    workspace_folder: str = "/workspace"


def get_features_for_languages(
    languages: set[str] | list[str],
    version_overrides: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Get devcontainer features for a set of languages.

    Args:
        languages: Set of language names
        version_overrides: Optional version overrides by language

    Returns:
        Dictionary of feature_url -> options for devcontainer.json
    """
    features: dict[str, dict[str, Any]] = {}
    version_overrides = version_overrides or {}

    for lang in languages:
        lang_lower = lang.lower()

        if lang_lower in DEVCONTAINER_FEATURES:
            feature_url, default_options = DEVCONTAINER_FEATURES[lang_lower]

            # Skip if already added (e.g., javascript and typescript share node)
            if feature_url in features:
                continue

            # Apply version override if provided
            options = default_options.copy()
            if lang_lower in version_overrides:
                options["version"] = version_overrides[lang_lower]

            features[feature_url] = options
            logger.debug(f"Added feature for {lang}: {feature_url}")

    return features


def get_post_create_commands(languages: set[str] | list[str]) -> list[str]:
    """Get custom installation commands for languages without features.

    Args:
        languages: Set of language names

    Returns:
        List of shell commands to run in postCreateCommand
    """
    commands: list[str] = []

    for lang in languages:
        lang_lower = lang.lower()

        # Skip if handled by feature
        if lang_lower in DEVCONTAINER_FEATURES:
            continue

        # Check for custom install
        if lang_lower in CUSTOM_INSTALL_COMMANDS:
            cmd = CUSTOM_INSTALL_COMMANDS[lang_lower]
            if cmd:  # Skip empty commands
                commands.append(cmd)
                logger.debug(f"Added custom install for {lang}: {cmd[:50]}...")

    return commands


def should_use_single_image(languages: set[str] | list[str]) -> str | None:
    """Check if a single optimized image should be used.

    Returns optimized image name if:
    - Only one language detected
    - That language has an optimized image

    Args:
        languages: Set of language names

    Returns:
        Image name if single-language optimization applies, None otherwise
    """
    lang_list = list(languages)

    if len(lang_list) == 1:
        lang = lang_list[0].lower()
        if lang in SINGLE_LANGUAGE_IMAGES:
            return SINGLE_LANGUAGE_IMAGES[lang]

    return None


class DynamicDevcontainerGenerator:
    """Generates devcontainer configuration based on detected languages.

    Supports:
    - Multi-language projects via devcontainer features
    - Single-language optimization with pre-built images
    - Custom language installation for unsupported runtimes
    """

    def __init__(
        self,
        name: str = "ZERG Worker",
        install_claude: bool = True,
        network_name: str = "zerg-internal",
    ) -> None:
        """Initialize generator.

        Args:
            name: Container name
            install_claude: Whether to install Claude CLI
            network_name: Docker network name for worker isolation
        """
        self.name = name
        self.install_claude = install_claude
        self.network_name = network_name

    def generate_spec(
        self,
        languages: set[str] | list[str],
        security_level: str = "standard",
        version_overrides: dict[str, str] | None = None,
    ) -> DevcontainerSpec:
        """Generate devcontainer specification for detected languages.

        Args:
            languages: Detected languages
            security_level: minimal, standard, or strict
            version_overrides: Optional version overrides

        Returns:
            DevcontainerSpec ready for serialization
        """
        languages_set = set(languages) if isinstance(languages, list) else languages

        # Determine base image
        single_image = should_use_single_image(languages_set)
        if single_image:
            base_image = single_image
            features = {}
            logger.info(f"Using optimized single-language image: {single_image}")
        else:
            base_image = DEFAULT_BASE_IMAGE
            features = get_features_for_languages(languages_set, version_overrides)
            logger.info(f"Using base image with {len(features)} features")

        # Always add common utilities
        features["ghcr.io/devcontainers/features/git:1"] = {}
        features["ghcr.io/devcontainers/features/github-cli:1"] = {}

        # Get custom install commands
        post_create_commands = get_post_create_commands(languages_set)

        # Add Claude CLI installation if requested
        if self.install_claude:
            post_create_commands.append("npm install -g @anthropic-ai/claude-code || true")

        # Add ZERG ready signal
        post_create_commands.append("echo 'ZERG worker ready'")

        # Build extensions list
        extensions = [
            "anthropic.claude-code",
        ]

        # Add language-specific extensions
        if "python" in languages_set:
            extensions.extend(["ms-python.python", "ms-python.vscode-pylance"])
        if "typescript" in languages_set or "javascript" in languages_set:
            extensions.extend(["dbaeumer.vscode-eslint", "esbenp.prettier-vscode"])
        if "go" in languages_set:
            extensions.append("golang.go")
        if "rust" in languages_set:
            extensions.append("rust-lang.rust-analyzer")

        # Security run args
        run_args: list[str] = []
        if security_level == "strict":
            run_args = [
                "--read-only",
                "--security-opt=no-new-privileges:true",
            ]

        # Standard mounts
        mounts = [
            "source=${localWorkspaceFolder},target=/workspace,type=bind",
        ]

        return DevcontainerSpec(
            name=self.name,
            base_image=base_image,
            features=features,
            post_create_commands=post_create_commands,
            extensions=extensions,
            run_args=run_args,
            mounts=mounts,
            workspace_folder="/workspace",
        )

    def generate_devcontainer_json(
        self,
        spec: DevcontainerSpec,
    ) -> dict[str, Any]:
        """Generate devcontainer.json content from spec.

        Args:
            spec: Devcontainer specification

        Returns:
            Dictionary ready for JSON serialization
        """
        config: dict[str, Any] = {
            "name": spec.name,
            "image": spec.base_image,
        }

        # Add features if any
        if spec.features:
            config["features"] = spec.features

        # Add customizations
        config["customizations"] = {
            "vscode": {
                "extensions": spec.extensions,
            },
        }

        # Add mounts
        if spec.mounts:
            config["mounts"] = spec.mounts

        # Add workspace folder
        config["workspaceFolder"] = spec.workspace_folder

        # Add post-create command
        if spec.post_create_commands:
            if len(spec.post_create_commands) == 1:
                config["postCreateCommand"] = spec.post_create_commands[0]
            else:
                # Chain commands
                config["postCreateCommand"] = " && ".join(spec.post_create_commands)

        # Add run args for security
        if spec.run_args:
            config["runArgs"] = spec.run_args

        # Add environment variables
        if spec.env_vars:
            config["containerEnv"] = spec.env_vars

        return config

    def write_devcontainer(
        self,
        languages: set[str] | list[str],
        output_dir: Path | None = None,
        security_level: str = "standard",
        version_overrides: dict[str, str] | None = None,
    ) -> Path:
        """Generate and write devcontainer.json.

        Args:
            languages: Detected languages
            output_dir: Output directory (default: .devcontainer)
            security_level: minimal, standard, or strict
            version_overrides: Optional version overrides

        Returns:
            Path to created devcontainer.json
        """
        output_dir = output_dir or Path(".devcontainer")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate spec and config
        spec = self.generate_spec(languages, security_level, version_overrides)
        config = self.generate_devcontainer_json(spec)

        # Write file
        devcontainer_path = output_dir / "devcontainer.json"
        with open(devcontainer_path, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Created {devcontainer_path}")
        return devcontainer_path

    def generate_worker_entry_script(
        self,
        output_dir: Path | None = None,
    ) -> Path:
        """Generate worker entry script for container execution.

        Args:
            output_dir: Output directory (default: .zerg)

        Returns:
            Path to created script
        """
        output_dir = output_dir or Path(".zerg")
        output_dir.mkdir(parents=True, exist_ok=True)

        script_content = """#!/bin/bash
# ZERG Worker Entry - Invokes Claude with native task list
set -e

WORKER_ID=${ZERG_WORKER_ID:-0}
TASK_LIST_ID=${ZERG_TASK_LIST_ID}
WORKTREE=${ZERG_WORKTREE:-/workspace}

echo "========================================"
echo "ZERG Worker $WORKER_ID starting..."
echo "Task List: $TASK_LIST_ID"
echo "Worktree: $WORKTREE"
echo "========================================"

cd "$WORKTREE"

# Check if Claude CLI is available
if ! command -v claude &> /dev/null; then
    echo "ERROR: Claude CLI not found. Installing..."
    npm install -g @anthropic-ai/claude-code
fi

# Launch Claude Code with task list (native feature)
exec claude --task-list "$TASK_LIST_ID" \\
     --dangerously-skip-permissions \\
     --env ZERG_WORKER_ID="$WORKER_ID"
"""

        script_path = output_dir / "worker_entry.sh"
        with open(script_path, "w") as f:
            f.write(script_content)

        # Make executable
        script_path.chmod(0o755)

        logger.info(f"Created {script_path}")
        return script_path
