"""ZERG v2 Quality Tools - Auto-detection and configuration of quality tools."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolConfig:
    """Configuration for a detected tool."""

    name: str
    command: str
    version: str = ""
    available: bool = False
    config_file: str = ""


@dataclass
class QualityToolset:
    """Complete set of detected quality tools for a project."""

    language: str
    linter: ToolConfig | None = None
    formatter: ToolConfig | None = None
    type_checker: ToolConfig | None = None
    test_runner: ToolConfig | None = None
    security_scanner: ToolConfig | None = None
    dependency_checker: ToolConfig | None = None

    def to_gates_config(self) -> list[dict]:
        """Convert to quality_gates config format.

        Returns:
            List of gate configurations for config.yaml
        """
        gates = []

        if self.linter and self.linter.available:
            gates.append({
                "name": "lint",
                "command": self.linter.command,
                "required": True,
            })

        if self.formatter and self.formatter.available:
            gates.append({
                "name": "format",
                "command": self.formatter.command,
                "required": False,
            })

        if self.type_checker and self.type_checker.available:
            gates.append({
                "name": "typecheck",
                "command": self.type_checker.command,
                "required": True,
            })

        if self.test_runner and self.test_runner.available:
            gates.append({
                "name": "test",
                "command": self.test_runner.command,
                "required": True,
            })

        if self.security_scanner and self.security_scanner.available:
            gates.append({
                "name": "security",
                "command": self.security_scanner.command,
                "required": False,
            })

        if self.dependency_checker and self.dependency_checker.available:
            gates.append({
                "name": "dependencies",
                "command": self.dependency_checker.command,
                "required": False,
            })

        return gates

    def summary(self) -> dict[str, str]:
        """Get summary of detected tools.

        Returns:
            Dictionary of tool type to command
        """
        result = {}
        for tool_type in ["linter", "formatter", "type_checker",
                          "test_runner", "security_scanner", "dependency_checker"]:
            tool = getattr(self, tool_type)
            if tool and tool.available:
                result[tool_type] = f"{tool.name} ({tool.command})"
            else:
                result[tool_type] = "not detected"
        return result


# Tool detection configurations per language
PYTHON_TOOLS = {
    "linter": [
        ("ruff", "ruff check .", "ruff.toml", "pyproject.toml"),
        ("flake8", "flake8 .", ".flake8", "setup.cfg"),
        ("pylint", "pylint **/*.py", ".pylintrc", "pyproject.toml"),
    ],
    "formatter": [
        ("ruff", "ruff format --check .", "ruff.toml", "pyproject.toml"),
        ("black", "black --check .", "pyproject.toml", None),
        ("autopep8", "autopep8 --diff .", None, None),
    ],
    "type_checker": [
        ("mypy", "mypy .", "mypy.ini", "pyproject.toml"),
        ("pyright", "pyright", "pyrightconfig.json", "pyproject.toml"),
    ],
    "test_runner": [
        ("pytest", "python -m pytest", "pytest.ini", "pyproject.toml"),
        ("unittest", "python -m unittest discover", None, None),
    ],
    "security_scanner": [
        ("bandit", "bandit -r . -ll", ".bandit", None),
        ("semgrep", "semgrep --config auto .", None, None),
        ("safety", "safety check", None, None),
    ],
    "dependency_checker": [
        ("pip-audit", "pip-audit", None, None),
        ("safety", "safety check -r requirements.txt", None, None),
    ],
}

TYPESCRIPT_TOOLS = {
    "linter": [
        ("eslint", "npx eslint .", ".eslintrc.js", ".eslintrc.json"),
        ("biome", "npx biome lint .", "biome.json", None),
    ],
    "formatter": [
        ("prettier", "npx prettier --check .", ".prettierrc", ".prettierrc.json"),
        ("biome", "npx biome format --check .", "biome.json", None),
    ],
    "type_checker": [
        ("tsc", "npx tsc --noEmit", "tsconfig.json", None),
    ],
    "test_runner": [
        ("jest", "npx jest", "jest.config.js", "jest.config.ts"),
        ("vitest", "npx vitest run", "vitest.config.ts", "vite.config.ts"),
        ("mocha", "npx mocha", ".mocharc.js", ".mocharc.json"),
    ],
    "security_scanner": [
        ("semgrep", "semgrep --config auto .", None, None),
        ("snyk", "npx snyk test", None, None),
    ],
    "dependency_checker": [
        ("npm-audit", "npm audit", "package-lock.json", None),
        ("snyk", "npx snyk test", None, None),
    ],
}

GO_TOOLS = {
    "linter": [
        ("golangci-lint", "golangci-lint run", ".golangci.yml", ".golangci.yaml"),
        ("staticcheck", "staticcheck ./...", None, None),
        ("go-vet", "go vet ./...", None, None),
    ],
    "formatter": [
        ("gofmt", "gofmt -l .", None, None),
        ("goimports", "goimports -l .", None, None),
    ],
    "type_checker": [
        # Go is statically typed, compilation is the type check
        ("go-build", "go build ./...", None, None),
    ],
    "test_runner": [
        ("go-test", "go test ./...", None, None),
    ],
    "security_scanner": [
        ("gosec", "gosec ./...", None, None),
        ("semgrep", "semgrep --config auto .", None, None),
    ],
    "dependency_checker": [
        ("govulncheck", "govulncheck ./...", None, None),
    ],
}

RUST_TOOLS = {
    "linter": [
        ("clippy", "cargo clippy -- -D warnings", None, None),
    ],
    "formatter": [
        ("rustfmt", "cargo fmt --check", "rustfmt.toml", ".rustfmt.toml"),
    ],
    "type_checker": [
        ("cargo-check", "cargo check", None, None),
    ],
    "test_runner": [
        ("cargo-test", "cargo test", None, None),
    ],
    "security_scanner": [
        ("cargo-audit", "cargo audit", None, None),
        ("semgrep", "semgrep --config auto .", None, None),
    ],
    "dependency_checker": [
        ("cargo-audit", "cargo audit", None, None),
    ],
}

LANGUAGE_TOOLS = {
    "python": PYTHON_TOOLS,
    "typescript": TYPESCRIPT_TOOLS,
    "javascript": TYPESCRIPT_TOOLS,  # Same tools
    "go": GO_TOOLS,
    "rust": RUST_TOOLS,
}


class ToolDetector:
    """Detect available quality tools for a project."""

    def __init__(self, project_path: Path):
        """Initialize detector.

        Args:
            project_path: Path to project root
        """
        self.project_path = project_path

    def detect(self, language: str) -> QualityToolset:
        """Detect available tools for the given language.

        Args:
            language: Project language (python, typescript, go, rust)

        Returns:
            QualityToolset with detected tools
        """
        tools = LANGUAGE_TOOLS.get(language, {})
        toolset = QualityToolset(language=language)

        for tool_type, candidates in tools.items():
            detected = self._detect_tool(candidates)
            if detected:
                setattr(toolset, tool_type, detected)

        return toolset

    def _detect_tool(self, candidates: list[tuple]) -> ToolConfig | None:
        """Detect first available tool from candidates.

        Args:
            candidates: List of (name, command, config1, config2) tuples

        Returns:
            ToolConfig if found, None otherwise
        """
        for candidate in candidates:
            name, command, config1, config2 = candidate

            # Check if tool is installed
            if not self._is_tool_installed(name):
                continue

            # Check for config files (prefer projects with explicit config)
            config_file = ""
            if config1 and (self.project_path / config1).exists():
                config_file = config1
            elif config2 and (self.project_path / config2).exists():
                config_file = config2

            # Get version
            version = self._get_tool_version(name)

            return ToolConfig(
                name=name,
                command=command,
                version=version,
                available=True,
                config_file=config_file,
            )

        return None

    def _is_tool_installed(self, name: str) -> bool:
        """Check if a tool is installed.

        Args:
            name: Tool name

        Returns:
            True if tool is available
        """
        # Handle special cases
        if name.startswith("go-"):
            return shutil.which("go") is not None
        if name.startswith("cargo-"):
            return shutil.which("cargo") is not None
        if name.startswith("npm-"):
            return shutil.which("npm") is not None

        # Check PATH
        if shutil.which(name):
            return True

        # Check npx availability for Node tools
        if name in ("eslint", "prettier", "jest", "vitest", "mocha", "biome", "tsc"):
            return shutil.which("npx") is not None and (
                (self.project_path / "node_modules" / ".bin" / name).exists()
                or (self.project_path / "package.json").exists()
            )

        return False

    def _get_tool_version(self, name: str) -> str:
        """Get tool version.

        Args:
            name: Tool name

        Returns:
            Version string or empty string
        """
        version_commands = {
            "ruff": ["ruff", "--version"],
            "black": ["black", "--version"],
            "mypy": ["mypy", "--version"],
            "pytest": ["pytest", "--version"],
            "eslint": ["npx", "eslint", "--version"],
            "prettier": ["npx", "prettier", "--version"],
            "go-test": ["go", "version"],
            "cargo-test": ["cargo", "--version"],
            "golangci-lint": ["golangci-lint", "--version"],
        }

        cmd = version_commands.get(name)
        if not cmd:
            return ""

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(self.project_path),
            )
            if result.returncode == 0:
                # Extract first line, strip
                return result.stdout.split("\n")[0].strip()[:50]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # Optional tool not available or timed out

        return ""


class QualityConfigGenerator:
    """Generate quality configuration based on detected tools."""

    def __init__(self, project_path: Path):
        """Initialize generator.

        Args:
            project_path: Path to project root
        """
        self.project_path = project_path
        self.detector = ToolDetector(project_path)

    def generate(self, language: str) -> dict:
        """Generate complete quality configuration.

        Args:
            language: Project language

        Returns:
            Configuration dictionary
        """
        toolset = self.detector.detect(language)

        return {
            "language": language,
            "tools": toolset.summary(),
            "quality_gates": toolset.to_gates_config(),
            "two_stage_gates": {
                "stage_1": ["spec_compliance"],
                "stage_2": [
                    g["name"] for g in toolset.to_gates_config()
                    if g.get("required", False)
                ],
            },
        }

    def generate_config_yaml_section(self, language: str) -> str:
        """Generate YAML section for config.yaml.

        Args:
            language: Project language

        Returns:
            YAML-formatted string
        """
        toolset = self.detector.detect(language)
        gates = toolset.to_gates_config()

        if not gates:
            return """# Quality gates (no tools detected - configure manually)
quality_gates:
  - name: lint
    command: "echo 'No linter configured'"
    required: false
  - name: test
    command: "echo 'No tests configured'"
    required: false
"""

        lines = ["# Quality gates (auto-detected)", "quality_gates:"]
        for gate in gates:
            lines.append(f"  - name: {gate['name']}")
            lines.append(f"    command: \"{gate['command']}\"")
            lines.append(f"    required: {str(gate.get('required', False)).lower()}")

        return "\n".join(lines) + "\n"


def detect_and_configure(project_path: Path, language: str) -> QualityToolset:
    """Convenience function to detect tools and return toolset.

    Args:
        project_path: Path to project root
        language: Project language

    Returns:
        QualityToolset with detected tools
    """
    detector = ToolDetector(project_path)
    return detector.detect(language)


__all__ = [
    "ToolConfig",
    "QualityToolset",
    "ToolDetector",
    "QualityConfigGenerator",
    "detect_and_configure",
    "PYTHON_TOOLS",
    "TYPESCRIPT_TOOLS",
    "GO_TOOLS",
    "RUST_TOOLS",
]
