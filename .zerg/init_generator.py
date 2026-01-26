"""ZERG v2 Init Generator - Project initialization and configuration."""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from devcontainer import DevcontainerConfig, DevcontainerGenerator


@dataclass
class ProjectInfo:
    """Information about a detected project."""

    language: str = "unknown"
    framework: str | None = None
    package_manager: str | None = None


class ProjectDetector:
    """Detects project type, language, and framework."""

    LANGUAGE_MARKERS = {
        "pyproject.toml": "python",
        "setup.py": "python",
        "requirements.txt": "python",
        "package.json": "typescript",
        "go.mod": "go",
        "Cargo.toml": "rust",
        "pom.xml": "java",
        "build.gradle": "java",
    }

    FRAMEWORK_MARKERS = {
        "python": {
            "fastapi": ["fastapi"],
            "flask": ["flask"],
            "django": ["django"],
        },
        "typescript": {
            "nextjs": ["next"],
            "react": ["react"],
            "vue": ["vue"],
            "angular": ["@angular/core"],
            "express": ["express"],
        },
    }

    PACKAGE_MANAGER_MARKERS = {
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "package-lock.json": "npm",
        "requirements.txt": "pip",
        "Pipfile": "pipenv",
        "poetry.lock": "poetry",
        "Cargo.lock": "cargo",
        "go.sum": "go",
    }

    def __init__(self, project_path: Path):
        """Initialize detector.

        Args:
            project_path: Path to project root
        """
        self.project_path = project_path

    def detect(self) -> ProjectInfo:
        """Detect project information.

        Returns:
            ProjectInfo with detected language, framework, package manager
        """
        language = self._detect_language()
        framework = self._detect_framework(language)
        package_manager = self._detect_package_manager(language)

        return ProjectInfo(
            language=language,
            framework=framework,
            package_manager=package_manager,
        )

    def _detect_language(self) -> str:
        """Detect project language."""
        for marker, language in self.LANGUAGE_MARKERS.items():
            if (self.project_path / marker).exists():
                return language
        return "unknown"

    def _detect_framework(self, language: str) -> str | None:
        """Detect framework based on language."""
        if language not in self.FRAMEWORK_MARKERS:
            return None

        frameworks = self.FRAMEWORK_MARKERS[language]

        if language == "python":
            return self._detect_python_framework(frameworks)
        elif language == "typescript":
            return self._detect_node_framework(frameworks)

        return None

    def _detect_python_framework(self, frameworks: dict) -> str | None:
        """Detect Python framework from requirements."""
        deps = set()

        # Check requirements.txt
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text().lower()
            for line in content.splitlines():
                # Extract package name (before any version specifier)
                pkg = line.split("==")[0].split(">=")[0].split("<")[0].strip()
                deps.add(pkg)

        # Check pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text().lower()
            for framework, markers in frameworks.items():
                for marker in markers:
                    if marker in content:
                        return framework

        # Check against frameworks
        for framework, markers in frameworks.items():
            for marker in markers:
                if marker in deps:
                    return framework

        return None

    def _detect_node_framework(self, frameworks: dict) -> str | None:
        """Detect Node.js framework from package.json."""
        pkg_file = self.project_path / "package.json"
        if not pkg_file.exists():
            return None

        try:
            pkg = json.loads(pkg_file.read_text())
        except json.JSONDecodeError:
            return None

        deps = set()
        deps.update(pkg.get("dependencies", {}).keys())
        deps.update(pkg.get("devDependencies", {}).keys())

        for framework, markers in frameworks.items():
            for marker in markers:
                if marker in deps:
                    return framework

        return None

    def _detect_package_manager(self, language: str) -> str | None:
        """Detect package manager."""
        # Check for lock files first (most specific)
        for marker, pm in self.PACKAGE_MANAGER_MARKERS.items():
            if (self.project_path / marker).exists():
                return pm

        # Fall back to language defaults
        defaults = {
            "python": "pip",
            "typescript": "npm",
            "go": "go",
            "rust": "cargo",
            "java": "maven",
        }
        return defaults.get(language)


@dataclass
class ConfigGenerator:
    """Generates config.json for ZERG v2."""

    project_path: Path
    project_info: ProjectInfo

    def generate(self) -> dict:
        """Generate config dictionary.

        Returns:
            Configuration dictionary
        """
        return {
            "version": "2.0.0",
            "project": {
                "name": self.project_path.name,
                "language": self.project_info.language,
                "framework": self.project_info.framework,
            },
            "orchestrator": {
                "max_workers": 5,
                "heartbeat_interval": 30,
                "context_threshold": 0.70,
            },
            "quality_gates": {
                "stage_1": ["spec_compliance"],
                "stage_2": ["lint", "test", "security"],
            },
        }


class InitGenerator:
    """Generates ZERG v2 directory structure."""

    # Path to source templates/schemas (relative to this file)
    SOURCE_DIR = Path(__file__).parent

    def __init__(self, project_path: Path):
        """Initialize generator.

        Args:
            project_path: Path to project root
        """
        self.project_path = project_path
        self.zerg_dir = project_path / ".zerg"

    def generate(self, generate_devcontainer: bool = True) -> None:
        """Generate ZERG v2 structure.

        Args:
            generate_devcontainer: Whether to generate devcontainer files
        """
        # Create directories
        self._create_directories()

        # Detect project info
        detector = ProjectDetector(self.project_path)
        info = detector.detect()

        # Generate config.json
        self._generate_config(info)

        # Copy schemas
        self._copy_schemas()

        # Copy templates
        self._copy_templates()

        # Generate devcontainer
        if generate_devcontainer:
            self._generate_devcontainer(info)

    def _create_directories(self) -> None:
        """Create ZERG directory structure."""
        dirs = [
            self.zerg_dir,
            self.zerg_dir / "schemas",
            self.zerg_dir / "templates",
            self.zerg_dir / "logs",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _generate_config(self, info: ProjectInfo) -> None:
        """Generate config.json file."""
        generator = ConfigGenerator(self.project_path, info)
        config = generator.generate()

        config_path = self.zerg_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2))

    def _copy_schemas(self) -> None:
        """Copy schema files."""
        source_schemas = self.SOURCE_DIR / "schemas"
        target_schemas = self.zerg_dir / "schemas"

        if source_schemas.exists():
            for schema_file in source_schemas.glob("*.json"):
                shutil.copy(schema_file, target_schemas / schema_file.name)

    def _copy_templates(self) -> None:
        """Copy template files."""
        source_templates = self.SOURCE_DIR / "templates"
        target_templates = self.zerg_dir / "templates"

        if source_templates.exists():
            for template_file in source_templates.glob("*.md"):
                shutil.copy(template_file, target_templates / template_file.name)

    def _generate_devcontainer(self, info: ProjectInfo) -> None:
        """Generate devcontainer configuration.

        Args:
            info: Detected project information
        """
        config = DevcontainerConfig(
            name=f"zerg-worker-{self.project_path.name}",
            image_name=f"zerg-worker-{info.language}",
        )
        generator = DevcontainerGenerator(self.project_path, config)
        generator.generate(
            language=info.language,
            framework=info.framework,
        )
