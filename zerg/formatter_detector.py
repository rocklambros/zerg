"""Formatter auto-detection from project configuration files.

This module detects code formatters by examining project configuration files
and returns appropriate commands for formatting code.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FormatterConfig:
    """Configuration for a detected code formatter.

    Attributes:
        name: Name of the formatter (e.g., 'ruff', 'black', 'prettier')
        format_cmd: Command to check formatting (exits non-zero if changes needed)
        fix_cmd: Command to auto-fix/format files
        file_patterns: List of file patterns this formatter handles
    """

    name: str
    format_cmd: str
    fix_cmd: str
    file_patterns: list[str] = field(default_factory=list)


class FormatterDetector:
    """Detects code formatters from project configuration files.

    Searches for formatter configuration in common config files and returns
    the appropriate FormatterConfig for the detected formatter.

    Supported formatters:
        - ruff: Python (from pyproject.toml [tool.ruff])
        - black: Python (from pyproject.toml [tool.black])
        - prettier: JavaScript/TypeScript/CSS/etc (from .prettierrc or package.json)
        - rustfmt: Rust (from rustfmt.toml)
        - clang-format: C/C++ (from .clang-format)
        - gofmt: Go (from go.mod presence)
    """

    def __init__(self, project_root: Path | str | None = None):
        """Initialize the formatter detector.

        Args:
            project_root: Root directory of the project. Defaults to current directory.
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def detect(self) -> FormatterConfig | None:
        """Detect the primary formatter for the project.

        Returns:
            FormatterConfig for the detected formatter, or None if no formatter found.

        Note:
            Detection order (first match wins):
            1. ruff (preferred for Python)
            2. black
            3. prettier
            4. rustfmt
            5. clang-format
            6. gofmt
        """
        # Try each detector in priority order
        detectors = [
            self._detect_ruff,
            self._detect_black,
            self._detect_prettier,
            self._detect_rustfmt,
            self._detect_clang_format,
            self._detect_gofmt,
        ]

        for detector in detectors:
            config = detector()
            if config is not None:
                return config

        return None

    def detect_all(self) -> list[FormatterConfig]:
        """Detect all formatters configured for the project.

        Returns:
            List of FormatterConfig for all detected formatters.
        """
        configs = []
        detectors = [
            self._detect_ruff,
            self._detect_black,
            self._detect_prettier,
            self._detect_rustfmt,
            self._detect_clang_format,
            self._detect_gofmt,
        ]

        for detector in detectors:
            config = detector()
            if config is not None:
                configs.append(config)

        return configs

    def _detect_ruff(self) -> FormatterConfig | None:
        """Detect ruff from pyproject.toml [tool.ruff]."""
        pyproject_path = self.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)

            if "tool" in data and "ruff" in data["tool"]:
                return FormatterConfig(
                    name="ruff",
                    format_cmd="ruff format --check .",
                    fix_cmd="ruff format .",
                    file_patterns=["*.py"],
                )
        except (OSError, tomllib.TOMLDecodeError, KeyError):
            pass

        return None

    def _detect_black(self) -> FormatterConfig | None:
        """Detect black from pyproject.toml [tool.black]."""
        pyproject_path = self.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)

            if "tool" in data and "black" in data["tool"]:
                return FormatterConfig(
                    name="black",
                    format_cmd="black --check .",
                    fix_cmd="black .",
                    file_patterns=["*.py"],
                )
        except (OSError, tomllib.TOMLDecodeError, KeyError):
            pass

        return None

    def _detect_prettier(self) -> FormatterConfig | None:
        """Detect prettier from .prettierrc or package.json."""
        # Check for .prettierrc variants
        prettierrc_names = [
            ".prettierrc",
            ".prettierrc.json",
            ".prettierrc.yml",
            ".prettierrc.yaml",
            ".prettierrc.js",
            ".prettierrc.cjs",
            ".prettierrc.mjs",
            "prettier.config.js",
            "prettier.config.cjs",
            "prettier.config.mjs",
        ]

        for name in prettierrc_names:
            if (self.project_root / name).exists():
                return self._create_prettier_config()

        # Check package.json for prettier field
        package_json_path = self.project_root / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path) as f:
                    data = json.load(f)
                if "prettier" in data:
                    return self._create_prettier_config()
            except (OSError, json.JSONDecodeError, KeyError):
                pass

        return None

    def _create_prettier_config(self) -> FormatterConfig:
        """Create a FormatterConfig for prettier."""
        return FormatterConfig(
            name="prettier",
            format_cmd="npx prettier --check .",
            fix_cmd="npx prettier --write .",
            file_patterns=[
                "*.js",
                "*.jsx",
                "*.ts",
                "*.tsx",
                "*.css",
                "*.scss",
                "*.json",
                "*.md",
                "*.yaml",
                "*.yml",
            ],
        )

    def _detect_rustfmt(self) -> FormatterConfig | None:
        """Detect rustfmt from rustfmt.toml."""
        rustfmt_path = self.project_root / "rustfmt.toml"
        if rustfmt_path.exists():
            return FormatterConfig(
                name="rustfmt",
                format_cmd="cargo fmt -- --check",
                fix_cmd="cargo fmt",
                file_patterns=["*.rs"],
            )

        # Also check for .rustfmt.toml
        rustfmt_dot_path = self.project_root / ".rustfmt.toml"
        if rustfmt_dot_path.exists():
            return FormatterConfig(
                name="rustfmt",
                format_cmd="cargo fmt -- --check",
                fix_cmd="cargo fmt",
                file_patterns=["*.rs"],
            )

        return None

    def _detect_clang_format(self) -> FormatterConfig | None:
        """Detect clang-format from .clang-format file."""
        clang_format_path = self.project_root / ".clang-format"
        if clang_format_path.exists():
            return FormatterConfig(
                name="clang-format",
                format_cmd="clang-format --dry-run -Werror **/*.c **/*.cpp **/*.h **/*.hpp",
                fix_cmd="clang-format -i **/*.c **/*.cpp **/*.h **/*.hpp",
                file_patterns=["*.c", "*.cpp", "*.h", "*.hpp", "*.cc", "*.cxx"],
            )

        # Also check for _clang-format (alternative name)
        clang_format_alt_path = self.project_root / "_clang-format"
        if clang_format_alt_path.exists():
            return FormatterConfig(
                name="clang-format",
                format_cmd="clang-format --dry-run -Werror **/*.c **/*.cpp **/*.h **/*.hpp",
                fix_cmd="clang-format -i **/*.c **/*.cpp **/*.h **/*.hpp",
                file_patterns=["*.c", "*.cpp", "*.h", "*.hpp", "*.cc", "*.cxx"],
            )

        return None

    def _detect_gofmt(self) -> FormatterConfig | None:
        """Detect gofmt from go.mod presence."""
        go_mod_path = self.project_root / "go.mod"
        if go_mod_path.exists():
            return FormatterConfig(
                name="gofmt",
                format_cmd="gofmt -l .",
                fix_cmd="gofmt -w .",
                file_patterns=["*.go"],
            )
        return None


def detect_formatter(project_root: Path | str | None = None) -> FormatterConfig | None:
    """Convenience function to detect the primary formatter for a project.

    Args:
        project_root: Root directory of the project. Defaults to current directory.

    Returns:
        FormatterConfig for the detected formatter, or None if no formatter found.
    """
    detector = FormatterDetector(project_root)
    return detector.detect()
