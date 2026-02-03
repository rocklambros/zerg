"""Component type detection for ZERG source files."""

from __future__ import annotations

import ast
import logging
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """Classification of a source file's role in the project."""

    MODULE = "module"
    COMMAND = "command"
    CONFIG = "config"
    TYPES = "types"
    API = "api"


# Patterns that indicate an API endpoint file
_API_MARKERS = (
    "@click.command",
    "@click.group",
    "@app.route",
    "@router.",
    "@blueprint.",
    "APIRouter",
)

# Base names (without extension) that signal a config file
_CONFIG_STEMS = {"config", "configuration", "settings"}

# Base names that signal a types/constants file
_TYPES_STEMS = {"types", "constants", "enums"}

# AST node types that dominate a "types" file
_TYPE_DEF_NODES = (ast.ClassDef,)


class ComponentDetector:
    """Detects the logical component type of project files."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, path: Path) -> ComponentType:
        """Classify a single file into a ``ComponentType``.

        Detection priority:
        1. ``.md`` files under a ``data/commands/`` directory → COMMAND
        2. Config-like file names or extensions → CONFIG
        3. Types/constants file names or files dominated by type definitions → TYPES
        4. Files containing API / CLI endpoint markers → API
        5. Everything else → MODULE
        """
        path = Path(path)

        if self._is_command_file(path):
            return ComponentType.COMMAND

        if self._is_config_file(path):
            return ComponentType.CONFIG

        if self._is_types_file(path):
            return ComponentType.TYPES

        if self._is_api_file(path):
            return ComponentType.API

        return ComponentType.MODULE

    def detect_all(self, directory: Path) -> dict[Path, ComponentType]:
        """Recursively scan *directory* and classify every file.

        Returns:
            Mapping from each file's ``Path`` to its detected ``ComponentType``.
        """
        directory = Path(directory)
        results: dict[Path, ComponentType] = {}
        for child in sorted(directory.rglob("*")):
            if child.is_dir():
                continue
            # Skip hidden files and __pycache__
            if any(part.startswith(".") or part == "__pycache__" for part in child.parts):
                continue
            try:
                results[child] = self.detect(child)
            except Exception:
                logger.debug("Failed to detect type for %s", child, exc_info=True)
                results[child] = ComponentType.MODULE
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_command_file(path: Path) -> bool:
        """Markdown files inside a ``data/commands/`` directory."""
        if path.suffix != ".md":
            return False
        try:
            parts = path.resolve().parts
            for i, part in enumerate(parts):
                if part == "data" and i + 1 < len(parts) and parts[i + 1] == "commands":
                    return True
        except (OSError, ValueError):
            pass
        return False

    @staticmethod
    def _is_config_file(path: Path) -> bool:
        """Files whose name or extension strongly suggests configuration."""
        stem_lower = path.stem.lower()
        suffix_lower = path.suffix.lower()

        # YAML/TOML config files
        if suffix_lower in {".yaml", ".yml", ".toml", ".ini", ".cfg"}:
            return True

        # Python files with "config" in the name
        if suffix_lower == ".py" and any(token in stem_lower for token in _CONFIG_STEMS):
            return True

        return False

    def _is_types_file(self, path: Path) -> bool:
        """Files named types/constants or dominated by type-definition nodes."""
        stem_lower = path.stem.lower()

        if stem_lower in _TYPES_STEMS:
            return True

        # For Python files, inspect the AST
        if path.suffix == ".py":
            return self._ast_dominated_by_type_defs(path)

        return False

    @staticmethod
    def _ast_dominated_by_type_defs(path: Path) -> bool:
        """Return True if >50% of top-level statements are class defs (TypedDict, dataclass, Enum)."""
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError):
            return False

        top_level = [node for node in tree.body if not isinstance(node, ast.Import | ast.ImportFrom)]
        if not top_level:
            return False

        type_def_count = sum(1 for node in top_level if isinstance(node, _TYPE_DEF_NODES))
        return type_def_count / len(top_level) > 0.5

    @staticmethod
    def _is_api_file(path: Path) -> bool:
        """Files containing CLI or HTTP endpoint decorators."""
        if path.suffix != ".py":
            return False
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            return False
        return any(marker in source for marker in _API_MARKERS)
