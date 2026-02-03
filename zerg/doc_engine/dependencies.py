"""Dependency mapper -- builds directed graphs of Python import relationships."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ModuleNode:
    """A single module in the dependency graph.

    Attributes:
        name: Fully-qualified module name (e.g. ``"zerg.orchestrator"``).
        path: Filesystem path to the module source, or ``None`` for external modules.
        imports: Module names that this module imports.
        imported_by: Module names that import this module (reverse edges).
    """

    name: str
    path: Path | None = None
    imports: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)


@dataclass
class DependencyGraph:
    """Directed graph of module-level import relationships.

    Attributes:
        modules: Mapping of fully-qualified module name to its :class:`ModuleNode`.
    """

    modules: dict[str, ModuleNode] = field(default_factory=dict)

    def get_imports(self, module: str) -> list[str]:
        """Return the modules directly imported by *module*.

        Args:
            module: Fully-qualified module name.

        Returns:
            List of module names imported by *module*, or an empty list if
            *module* is not in the graph.
        """
        node = self.modules.get(module)
        return list(node.imports) if node else []

    def get_importers(self, module: str) -> list[str]:
        """Return the modules that directly import *module* (reverse lookup).

        Args:
            module: Fully-qualified module name.

        Returns:
            List of module names that import *module*, or an empty list if
            *module* is not in the graph.
        """
        node = self.modules.get(module)
        return list(node.imported_by) if node else []

    def get_dependency_chain(self, module: str) -> list[str]:
        """Return the transitive closure of imports starting from *module*.

        Performs a depth-first traversal of forward imports and returns all
        reachable modules (excluding *module* itself).

        Args:
            module: Fully-qualified module name.

        Returns:
            List of transitively-imported module names (order is deterministic
            but not guaranteed to be topological).
        """
        visited: set[str] = set()
        result: list[str] = []

        def _walk(current: str) -> None:
            for dep in self.get_imports(current):
                if dep not in visited:
                    visited.add(dep)
                    result.append(dep)
                    _walk(dep)

        _walk(module)
        return result


# ---------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------


class DependencyMapper:
    """Builds a :class:`DependencyGraph` by scanning Python source files.

    Usage::

        graph = DependencyMapper.build(Path("src"), package="zerg")
        adj = DependencyMapper.to_adjacency_list(graph)
    """

    # -- public API ----------------------------------------------------------

    @staticmethod
    def build(root_dir: Path, package: str = "zerg") -> DependencyGraph:
        """Scan *root_dir* for ``.py`` files and build a dependency graph.

        Only modules whose fully-qualified name starts with *package* are
        included as nodes.  Imports that reference external packages are
        silently ignored.

        Args:
            root_dir: Directory to scan recursively.
            package: Top-level package name used to filter and resolve modules.

        Returns:
            A :class:`DependencyGraph` containing all discovered in-package
            import relationships.
        """
        root_dir = root_dir.resolve()
        graph = DependencyGraph()

        # Phase 1 -- discover modules and parse their imports.
        py_files = sorted(root_dir.rglob("*.py"))
        for py_file in py_files:
            module_name = _path_to_module(py_file, root_dir, package)
            if module_name is None:
                continue
            if not module_name.startswith(package):
                continue

            raw_imports = _extract_imports(py_file, module_name, package)
            # Filter to in-package only.
            in_pkg_imports = [m for m in raw_imports if m.startswith(package)]

            node = ModuleNode(
                name=module_name,
                path=py_file,
                imports=in_pkg_imports,
            )
            graph.modules[module_name] = node

        # Phase 2 -- build reverse edges (imported_by).
        for module_name, node in graph.modules.items():
            for imp in node.imports:
                target = graph.modules.get(imp)
                if target is not None and module_name not in target.imported_by:
                    target.imported_by.append(module_name)

        logger.debug(
            "DependencyMapper.build: %d modules, %d edges",
            len(graph.modules),
            sum(len(n.imports) for n in graph.modules.values()),
        )
        return graph

    @staticmethod
    def to_adjacency_list(graph: DependencyGraph) -> dict[str, list[str]]:
        """Convert a :class:`DependencyGraph` to a plain adjacency list.

        Useful for downstream renderers (e.g. Mermaid diagram generation).

        Args:
            graph: The dependency graph to convert.

        Returns:
            A dict mapping each module name to its list of direct imports that
            are present in the graph.
        """
        adj: dict[str, list[str]] = {}
        for module_name, node in graph.modules.items():
            adj[module_name] = [imp for imp in node.imports if imp in graph.modules]
        return adj


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _path_to_module(py_file: Path, root_dir: Path, package: str) -> str | None:
    """Derive a fully-qualified module name from a filesystem path.

    Returns ``None`` if the file does not live under a directory named
    *package* within *root_dir*.
    """
    try:
        relative = py_file.relative_to(root_dir)
    except ValueError:
        return None

    parts = list(relative.with_suffix("").parts)
    if not parts:
        return None

    # If root_dir already *contains* the package directory, the first part
    # of the relative path should be the package name.  Otherwise, the file
    # is outside the package.
    if parts[0] != package:
        return None

    # Convert __init__ to its parent package name.
    if parts[-1] == "__init__":
        parts = parts[:-1]

    if not parts:
        return None

    return ".".join(parts)


def _extract_imports(py_file: Path, module_name: str, package: str) -> list[str]:
    """Parse *py_file* with :mod:`ast` and return a list of imported module names.

    Relative imports are resolved to absolute names using *module_name* as
    the context.
    """
    try:
        source = py_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read %s: %s", py_file, exc)
        return []

    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError as exc:
        logger.warning("Syntax error in %s: %s", py_file, exc)
        return []

    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module is None and node.level == 0:
                continue

            resolved = _resolve_import(module_name, node.module, node.level, package)
            if resolved is not None:
                imports.append(resolved)

    return imports


def _resolve_import(
    current_module: str,
    imported_module: str | None,
    level: int,
    package: str,
) -> str | None:
    """Resolve an import (possibly relative) to an absolute module name.

    Args:
        current_module: The fully-qualified name of the importing module.
        imported_module: The module string from the ``from ... import`` statement.
        level: Number of leading dots (0 = absolute import).
        package: The top-level package name.

    Returns:
        The resolved absolute module name, or ``None`` if resolution fails.
    """
    if level == 0:
        # Absolute import.
        return imported_module

    # Relative import -- walk up *level* packages from current_module.
    parts = current_module.split(".")
    # ``level`` dots means go up ``level`` package components.
    if level > len(parts):
        logger.warning("Relative import level %d exceeds depth of %s", level, current_module)
        return None

    base_parts = parts[: len(parts) - level]
    if not base_parts:
        base_parts = [package]

    if imported_module:
        return ".".join(base_parts) + "." + imported_module
    return ".".join(base_parts)
