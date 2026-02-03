"""AST caching and analysis utilities for cross-file and import-chain checks.

Provides cached AST parsing to avoid double-parsing when multiple checkers
analyze the same files. Used by CrossFileChecker and ImportChainChecker.
"""

from __future__ import annotations

import ast
from pathlib import Path


class ASTCache:
    """Cache parsed ASTs keyed on (path, mtime) to avoid repeated parsing."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, float], ast.Module] = {}

    def parse(self, path: Path) -> ast.Module:
        """Parse a Python file, returning cached result if file hasn't changed."""
        resolved = str(path.resolve())
        mtime = path.stat().st_mtime
        key = (resolved, mtime)

        if key not in self._cache:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=resolved)
            self._cache[key] = tree

        return self._cache[key]

    def clear(self) -> None:
        """Clear the AST cache."""
        self._cache.clear()


def collect_exports(tree: ast.Module) -> list[str]:
    """Collect public module-level function and class names from an AST.

    Only includes top-level definitions that don't start with underscore.

    Args:
        tree: Parsed AST module.

    Returns:
        List of exported symbol names.
    """
    exports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and not node.name.startswith("_"):
            exports.append(node.name)
    return exports


def collect_imports(tree: ast.Module) -> list[tuple[str, str | None]]:
    """Collect import statements from an AST.

    Args:
        tree: Parsed AST module.

    Returns:
        List of (module_path, imported_name) tuples.
        For 'from foo.bar import baz' -> ('foo.bar', 'baz').
        For 'import foo.bar' -> ('foo.bar', None).
    """
    imports: list[tuple[str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, None))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append((module, alias.name))
    return imports
