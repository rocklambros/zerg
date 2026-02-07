"""Single-pass filesystem traversal utilities for ZERG.

Provides a shared ``collect_files()`` function that walks a directory tree
exactly once via ``rglob('*')`` and returns files grouped by extension.
This replaces scattered per-module rglob calls (repo_map, stack_detector,
etc.) with a single efficient traversal.
"""

from __future__ import annotations

from pathlib import Path

_DEFAULT_EXCLUDES: set[str] = {
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    "dist",
    "build",
    ".git",
    ".zerg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "egg-info",
}


def collect_files(
    root: Path,
    extensions: set[str] | None = None,
    exclude_dirs: set[str] = _DEFAULT_EXCLUDES,
    names: set[str] | None = None,
) -> dict[str, list[Path]]:
    """Single rglob('*') traversal, returns files grouped by extension.

    Walks *root* exactly once and buckets every regular file by its
    lowercased suffix.  Directories whose name appears in *exclude_dirs*
    (or starts with ``"."``) are skipped entirely.

    Args:
        root: Root directory to traverse.
        extensions: If provided, only collect files with these extensions
            (e.g. ``{".py", ".js"}``).  Extensions must include the
            leading dot and are compared case-insensitively.
        exclude_dirs: Directory names to skip during traversal.
        names: If provided, files whose name contains any of these
            strings are collected into a ``"_by_name"`` bucket regardless
            of extension (e.g. ``{"Dockerfile"}``).

    Returns:
        Dict mapping extension (e.g. ``".py"``) to a **sorted** list of
        :class:`~pathlib.Path` objects.  When *names* is provided, matched
        files also appear under the ``"_by_name"`` key.
    """
    # Normalise the requested extensions to lowercase for comparison
    if extensions is not None:
        extensions = {ext.lower() for ext in extensions}

    grouped: dict[str, list[Path]] = {}

    for entry in root.rglob("*"):
        # Only include regular files
        if not entry.is_file():
            continue

        # Skip paths that traverse an excluded (or hidden) directory
        try:
            rel_parts = entry.relative_to(root).parts
        except ValueError:
            continue

        if any(
            part in exclude_dirs or part.startswith(".")
            for part in rel_parts[:-1]  # check directory components only
        ):
            continue

        # Name-based matching: collect into '_by_name' bucket
        if names is not None and any(n in entry.name for n in names):
            grouped.setdefault("_by_name", []).append(entry)

        suffix = entry.suffix.lower()
        if not suffix:
            continue

        if extensions is not None and suffix not in extensions:
            continue

        grouped.setdefault(suffix, []).append(entry)

    # Sort each bucket for deterministic output
    for ext in grouped:
        grouped[ext].sort()

    return grouped
