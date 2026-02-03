"""Stack detection for project technology analysis."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from zerg.performance.types import DetectedStack

# Extension-to-language mapping
_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c/cpp",
    ".cpp": "c/cpp",
    ".h": "c/cpp",
}

# Directories to skip during scanning
_SKIP_DIRS: set[str] = {
    "node_modules",
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".tox",
    ".venv",
    "venv",
}

# Maximum files to scan for language detection
_MAX_SCAN_FILES = 1000

# Framework detection patterns for package.json dependencies
_JS_FRAMEWORKS: dict[str, str] = {
    "react": "react",
    "vue": "vue",
    "angular": "angular",
    "@angular/core": "angular",
    "next": "next",
    "express": "express",
    "fastify": "fastify",
}

# Framework detection patterns for Python dependency files
_PYTHON_FRAMEWORKS: dict[str, str] = {
    "django": "django",
    "flask": "flask",
    "fastapi": "fastapi",
    "sqlalchemy": "sqlalchemy",
}


def _should_skip(path: Path) -> bool:
    """Check if a path component indicates the directory should be skipped."""
    return any(part.startswith(".") or part in _SKIP_DIRS for part in path.parts)


def _detect_languages(project_path: Path) -> list[str]:
    """Detect programming languages by scanning file extensions."""
    languages: set[str] = set()
    count = 0

    for file_path in project_path.rglob("*"):
        if count >= _MAX_SCAN_FILES:
            break
        if not file_path.is_file():
            continue
        if _should_skip(file_path.relative_to(project_path)):
            continue

        lang = _EXTENSION_MAP.get(file_path.suffix.lower())
        if lang:
            languages.add(lang)
        count += 1

    return sorted(languages)


def _detect_frameworks(project_path: Path) -> list[str]:
    """Detect frameworks by checking config files and their contents."""
    frameworks: set[str] = set()

    # Check package.json for JS/TS frameworks
    package_json = project_path / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            all_deps: dict[str, str] = {}
            all_deps.update(data.get("dependencies", {}))
            all_deps.update(data.get("devDependencies", {}))
            for dep_name, framework_name in _JS_FRAMEWORKS.items():
                if dep_name in all_deps:
                    frameworks.add(framework_name)
        except (json.JSONDecodeError, OSError):
            pass

    # Check Python dependency files
    _detect_python_frameworks(project_path, frameworks)

    # Check Go modules
    if (project_path / "go.mod").is_file():
        frameworks.add("go-module")

    # Check Rust Cargo
    if (project_path / "Cargo.toml").is_file():
        frameworks.add("rust-cargo")

    # Check Java build systems
    if (project_path / "pom.xml").is_file():
        frameworks.add("java-maven")
    if (project_path / "build.gradle").is_file():
        frameworks.add("java-gradle")

    return sorted(frameworks)


def _detect_python_frameworks(project_path: Path, frameworks: set[str]) -> None:
    """Detect Python frameworks from requirements.txt, pyproject.toml, and setup.py."""
    contents: list[str] = []

    for filename in ("requirements.txt", "pyproject.toml", "setup.py"):
        filepath = project_path / filename
        if filepath.is_file():
            with contextlib.suppress(OSError):
                contents.append(filepath.read_text(encoding="utf-8").lower())

    combined = "\n".join(contents)
    for keyword, framework_name in _PYTHON_FRAMEWORKS.items():
        if keyword in combined:
            frameworks.add(framework_name)


def _detect_docker(project_path: Path) -> bool:
    """Check for Docker configuration files."""
    docker_files = ("Dockerfile", "docker-compose.yml", "docker-compose.yaml")
    # Check project root
    if any((project_path / f).is_file() for f in docker_files):
        return True
    # Check .devcontainer/ (common for VS Code / Claude Code projects)
    devcontainer = project_path / ".devcontainer"
    if devcontainer.is_dir() and any((devcontainer / f).is_file() for f in docker_files):
        return True
    return False


def _detect_kubernetes(project_path: Path) -> bool:
    """Check for Kubernetes configuration files."""
    # Check for Helm files
    if (project_path / "helmfile.yaml").is_file():
        return True
    if (project_path / "Chart.yaml").is_file():
        return True

    # Scan YAML files for Kubernetes resource definitions
    k8s_markers = ("kind: Deployment", "kind: Service")
    try:
        for yaml_file in project_path.rglob("*.yaml"):
            if _should_skip(yaml_file.relative_to(project_path)):
                continue
            try:
                content = yaml_file.read_text(encoding="utf-8")
                if any(marker in content for marker in k8s_markers):
                    return True
            except OSError:
                continue

        for yml_file in project_path.rglob("*.yml"):
            if _should_skip(yml_file.relative_to(project_path)):
                continue
            try:
                content = yml_file.read_text(encoding="utf-8")
                if any(marker in content for marker in k8s_markers):
                    return True
            except OSError:
                continue
    except OSError:
        pass

    return False


def detect_stack(project_path: str) -> DetectedStack:
    """Detect the technology stack of a project.

    Scans the given project directory for programming languages, frameworks,
    and infrastructure configuration.

    Args:
        project_path: Path to the project root directory.

    Returns:
        DetectedStack with detected languages, frameworks, and infrastructure flags.
    """
    path = Path(project_path).resolve()

    if not path.is_dir():
        return DetectedStack(languages=[], frameworks=[])

    return DetectedStack(
        languages=_detect_languages(path),
        frameworks=_detect_frameworks(path),
        has_docker=_detect_docker(path),
        has_kubernetes=_detect_kubernetes(path),
    )
