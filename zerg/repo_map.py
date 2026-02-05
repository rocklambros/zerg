"""Repository symbol map for ZERG — injects relevant code context into worker prompts.

Uses Python ast module for .py files and regex-based extraction (repo_map_js)
for .js/.ts/.jsx/.tsx files. Zero new dependencies.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zerg.repo_map_js import JSSymbol, extract_js_file

logger = logging.getLogger(__name__)

# Approx chars per token for budget calculations
CHARS_PER_TOKEN = 4


@dataclass
class Symbol:
    """A code symbol extracted from a source file."""

    name: str
    kind: str  # "function", "class", "method", "variable", "import"
    signature: str  # e.g. "def foo(x: int, y: str) -> bool"
    docstring: str | None  # first line only
    line: int
    module: str  # e.g. "zerg.config"


@dataclass
class SymbolEdge:
    """A relationship between two symbols."""

    source: str  # "zerg.config.ZergConfig"
    target: str  # "zerg.heartbeat.HeartbeatConfig"
    kind: str  # "imports", "calls", "inherits"


@dataclass
class SymbolGraph:
    """Aggregated symbol graph for a repository or subset."""

    modules: dict[str, list[Symbol]] = field(default_factory=dict)
    edges: list[SymbolEdge] = field(default_factory=list)

    def query(self, files: list[str], keywords: list[str], max_tokens: int = 3000) -> str:
        """Return compact representation of relevant symbols.

        Filters symbols by file paths and keyword relevance,
        then formats as a compact markdown string within budget.

        Args:
            files: File paths to include (exact match on module path).
            keywords: Keywords to boost relevance (task description words).
            max_tokens: Approximate token budget.

        Returns:
            Markdown string of relevant symbols.
        """
        max_chars = max_tokens * CHARS_PER_TOKEN
        relevant_modules = self._filter_modules(files, keywords)
        return self._format(relevant_modules, max_chars)

    def _filter_modules(self, files: list[str], keywords: list[str]) -> dict[str, list[Symbol]]:
        """Filter modules by file list and keyword relevance."""
        result: dict[str, list[Symbol]] = {}
        kw_lower = {kw.lower() for kw in keywords if kw}

        for mod_key, symbols in self.modules.items():
            # Direct match on file paths
            if any(self._module_matches_file(mod_key, f) for f in files):
                result[mod_key] = symbols
                continue

            # Keyword match on symbol names/signatures
            if kw_lower:
                matched = [
                    s for s in symbols if any(kw in s.name.lower() or kw in s.signature.lower() for kw in kw_lower)
                ]
                if matched:
                    result[mod_key] = matched

        # Also include edge-connected modules
        connected = set()
        for edge in self.edges:
            src_mod = edge.source.rsplit(".", 1)[0] if "." in edge.source else edge.source
            tgt_mod = edge.target.rsplit(".", 1)[0] if "." in edge.target else edge.target
            if src_mod in result:
                connected.add(tgt_mod)
            if tgt_mod in result:
                connected.add(src_mod)

        for mod_key in connected:
            if mod_key in self.modules and mod_key not in result:
                result[mod_key] = self.modules[mod_key]

        return result

    @staticmethod
    def _module_matches_file(module_key: str, filepath: str) -> bool:
        """Check if a module key corresponds to a filepath."""
        # module_key like "zerg.config" matches "zerg/config.py"
        mod_as_path = module_key.replace(".", "/")
        fp_normalized = filepath.replace("\\", "/")
        # Strip extension for comparison
        fp_stem = fp_normalized.rsplit(".", 1)[0] if "." in fp_normalized else fp_normalized
        return fp_stem == mod_as_path or fp_stem.endswith("/" + mod_as_path)

    def _format(self, modules: dict[str, list[Symbol]], max_chars: int) -> str:
        """Format filtered modules into a compact markdown string."""
        if not modules:
            return ""

        lines: list[str] = ["## Repository Symbol Map\n"]
        char_count = len(lines[0])

        for mod_key in sorted(modules.keys()):
            symbols = modules[mod_key]
            header = f"\n### {mod_key}\n"
            if char_count + len(header) > max_chars:
                break
            lines.append(header)
            char_count += len(header)

            for sym in sorted(symbols, key=lambda s: s.line):
                line = f"- `{sym.signature}`"
                if sym.docstring:
                    line += f" — {sym.docstring}"
                line += "\n"
                if char_count + len(line) > max_chars:
                    break
                lines.append(line)
                char_count += len(line)

        return "".join(lines)


def _path_to_module(filepath: Path, root: Path) -> str:
    """Convert a file path to a Python-style module name."""
    try:
        rel = filepath.relative_to(root)
    except ValueError:
        rel = filepath
    parts = list(rel.with_suffix("").parts)
    return ".".join(parts)


def _extract_python_symbols(filepath: Path, module_name: str) -> tuple[list[Symbol], list[SymbolEdge]]:
    """Extract symbols from a Python file using the ast module."""
    symbols: list[Symbol] = []
    edges: list[SymbolEdge] = []

    try:
        source = filepath.read_text(errors="replace")
        tree = ast.parse(source, str(filepath))
    except (SyntaxError, OSError):
        return symbols, edges

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            sig = _format_func_signature(node)
            doc = ast.get_docstring(node)
            symbols.append(
                Symbol(
                    name=node.name,
                    kind="function",
                    signature=sig,
                    docstring=doc.split("\n")[0] if doc else None,
                    line=node.lineno,
                    module=module_name,
                )
            )

        elif isinstance(node, ast.ClassDef):
            bases = [_format_expr(b) for b in node.bases]
            sig = f"class {node.name}"
            if bases:
                sig += f"({', '.join(bases)})"
            doc = ast.get_docstring(node)
            symbols.append(
                Symbol(
                    name=node.name,
                    kind="class",
                    signature=sig,
                    docstring=doc.split("\n")[0] if doc else None,
                    line=node.lineno,
                    module=module_name,
                )
            )

            # Record inheritance edges
            for base_name in bases:
                if base_name and base_name not in ("object", "ABC"):
                    edges.append(
                        SymbolEdge(
                            source=f"{module_name}.{node.name}",
                            target=base_name,
                            kind="inherits",
                        )
                    )

            # Extract methods
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    msig = _format_func_signature(item)
                    mdoc = ast.get_docstring(item)
                    symbols.append(
                        Symbol(
                            name=f"{node.name}.{item.name}",
                            kind="method",
                            signature=msig,
                            docstring=mdoc.split("\n")[0] if mdoc else None,
                            line=item.lineno,
                            module=module_name,
                        )
                    )

        elif isinstance(node, ast.Import):
            for alias in node.names:
                symbols.append(
                    Symbol(
                        name=alias.asname or alias.name,
                        kind="import",
                        signature=f"import {alias.name}",
                        docstring=None,
                        line=node.lineno,
                        module=module_name,
                    )
                )
                edges.append(
                    SymbolEdge(
                        source=module_name,
                        target=alias.name,
                        kind="imports",
                    )
                )

        elif isinstance(node, ast.ImportFrom):
            from_mod = node.module or ""
            for alias in node.names:
                symbols.append(
                    Symbol(
                        name=alias.asname or alias.name,
                        kind="import",
                        signature=f"from {from_mod} import {alias.name}",
                        docstring=None,
                        line=node.lineno,
                        module=module_name,
                    )
                )
            if from_mod:
                edges.append(
                    SymbolEdge(
                        source=module_name,
                        target=from_mod,
                        kind="imports",
                    )
                )

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    symbols.append(
                        Symbol(
                            name=target.id,
                            kind="variable",
                            signature=f"{target.id} = ...",
                            docstring=None,
                            line=node.lineno,
                            module=module_name,
                        )
                    )

    return symbols, edges


def _format_func_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Format a function/method signature from AST node."""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args_parts: list[str] = []

    for arg in node.args.args:
        name = arg.arg
        if arg.annotation:
            name += f": {_format_expr(arg.annotation)}"
        args_parts.append(name)

    ret = ""
    if node.returns:
        ret = f" -> {_format_expr(node.returns)}"

    return f"{prefix} {node.name}({', '.join(args_parts)}){ret}"


def _format_expr(node: ast.expr) -> str:
    """Format an AST expression to a readable string."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_format_expr(node.value)}.{node.attr}"
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Subscript):
        return f"{_format_expr(node.value)}[{_format_expr(node.slice)}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return f"{_format_expr(node.left)} | {_format_expr(node.right)}"
    if isinstance(node, ast.Tuple):
        return ", ".join(_format_expr(e) for e in node.elts)
    return "..."


def _convert_js_symbol(js_sym: JSSymbol, module_name: str) -> Symbol:
    """Convert a JSSymbol to our unified Symbol type."""
    return Symbol(
        name=js_sym.name,
        kind=js_sym.kind,
        signature=js_sym.signature,
        docstring=js_sym.docstring,
        line=js_sym.line,
        module=module_name,
    )


# ---------------------------------------------------------------------------
# TTL-based caching for build_map() — module-level cache
# ---------------------------------------------------------------------------
_cached_graph: SymbolGraph | None = None
_cache_time: float | None = None
_cache_root: Path | None = None
_cache_languages: list[str] | None = None
_cache_lock = threading.Lock()
_CACHE_TTL_SECONDS = 30


def build_map(
    root: str | Path,
    languages: list[str] | None = None,
) -> SymbolGraph:
    """Build a symbol graph with TTL-based caching.

    Cached result is returned if:
    - Same root and languages
    - Within TTL (30 seconds)

    Args:
        root: Repository root path.
        languages: Languages to include. Default: ["python", "javascript", "typescript"].

    Returns:
        SymbolGraph with extracted symbols and edges (cached if valid).
    """
    global _cached_graph, _cache_time, _cache_root, _cache_languages

    root = Path(root).resolve()
    languages = languages or ["python", "javascript", "typescript"]

    with _cache_lock:
        # Check cache validity
        if (
            _cached_graph is not None
            and _cache_root == root
            and _cache_languages == languages
            and _cache_time is not None
            and (time.time() - _cache_time) < _CACHE_TTL_SECONDS
        ):
            logger.debug(
                "Cache hit for RepoMap (TTL: %.1fs remaining)",
                _CACHE_TTL_SECONDS - (time.time() - _cache_time),
            )
            return _cached_graph

        # Cache miss - build fresh
        logger.debug("Cache miss for RepoMap, building from %s", root)
        graph = _build_map_impl(root, languages)

        # Update cache
        _cached_graph = graph
        _cache_time = time.time()
        _cache_root = root
        _cache_languages = languages

        return graph


def invalidate_cache() -> None:
    """Invalidate the cached SymbolGraph."""
    global _cached_graph, _cache_time, _cache_root, _cache_languages

    with _cache_lock:
        _cached_graph = None
        _cache_time = None
        _cache_root = None
        _cache_languages = None
        logger.debug("Invalidating cache for RepoMap")


def _build_map_impl(root: Path, languages: list[str]) -> SymbolGraph:
    """Internal implementation of build_map (without caching).

    Args:
        root: Repository root path (already resolved).
        languages: Languages to include.

    Returns:
        SymbolGraph with extracted symbols and edges.
    """
    graph = SymbolGraph()

    # Collect files by extension
    extensions: dict[str, list[str]] = {}
    if "python" in languages:
        extensions[".py"] = ["python"]
    if "javascript" in languages:
        extensions[".js"] = ["javascript"]
        extensions[".jsx"] = ["javascript"]
    if "typescript" in languages:
        extensions[".ts"] = ["typescript"]
        extensions[".tsx"] = ["typescript"]

    for ext, langs in extensions.items():
        for filepath in root.rglob(f"*{ext}"):
            # Skip common non-source directories
            parts = filepath.relative_to(root).parts
            if any(
                p.startswith(".") or p in ("node_modules", "__pycache__", "venv", ".venv", "dist", "build")
                for p in parts
            ):
                continue

            module_name = _path_to_module(filepath, root)

            if ext == ".py":
                syms, edgs = _extract_python_symbols(filepath, module_name)
                if syms:
                    graph.modules[module_name] = syms
                graph.edges.extend(edgs)
            else:
                js_syms = extract_js_file(filepath)
                if js_syms:
                    graph.modules[module_name] = [_convert_js_symbol(s, module_name) for s in js_syms]

    return graph


# ---------------------------------------------------------------------------
# Incremental indexing — MD5-based staleness detection
# ---------------------------------------------------------------------------

# Language extension mapping (mirrors build_map logic)
_LANG_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py"],
    "javascript": [".js", ".jsx"],
    "typescript": [".ts", ".tsx"],
}

# Directories to always skip during file collection
_SKIP_DIRS = frozenset(
    {
        "node_modules",
        "__pycache__",
        "venv",
        ".venv",
        "dist",
        "build",
    }
)


def _md5_file(filepath: Path) -> str:
    """Return hex MD5 digest of a file's contents."""
    h = hashlib.md5()  # noqa: S324 — used for staleness check, not security
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_files(root: Path, languages: list[str]) -> list[Path]:
    """Collect source files matching *languages* under *root*.

    Uses single-pass directory traversal for performance.
    """
    exts: set[str] = set()
    for lang in languages:
        exts.update(_LANG_EXTENSIONS.get(lang, []))

    # Single traversal, filter in memory
    result: list[Path] = []
    for fp in root.rglob("*"):
        if not fp.is_file():
            continue

        # Check extension
        if fp.suffix not in exts:
            continue

        # Check skip directories
        parts = fp.relative_to(root).parts
        if any(p.startswith(".") or p in _SKIP_DIRS for p in parts):
            continue

        result.append(fp)
    return result


def _extract_symbol_names(filepath: Path, root: Path) -> list[str]:
    """Extract symbol names from a single source file.

    Returns a flat list of symbol name strings (used for the index cache).
    """
    module_name = _path_to_module(filepath, root)
    ext = filepath.suffix

    if ext == ".py":
        syms, _edges = _extract_python_symbols(filepath, module_name)
        return [s.name for s in syms]

    # JS/TS
    js_syms = extract_js_file(filepath)
    return [s.name for s in js_syms]


class IncrementalIndex:
    """File-level incremental index with MD5 staleness detection.

    Stores ``{file_path: {hash: md5hex, symbols: [...]}}`` in
    ``.zerg/state/repo-index.json`` and only re-extracts symbols for files
    whose content hash has changed.
    """

    def __init__(self, state_dir: str | Path | None = None) -> None:
        from zerg.constants import STATE_DIR  # avoid circular at module level

        self._state_dir = Path(state_dir) if state_dir else Path(STATE_DIR)
        self._index_path = self._state_dir / "repo-index.json"
        self._data: dict[str, dict[str, Any]] = {}
        self._last_updated: str | None = None
        self._stale_count: int = 0

    # -- persistence ---------------------------------------------------------

    def _load(self) -> dict[str, dict[str, Any]]:
        """Load the on-disk index (returns empty dict on missing/corrupt)."""
        if not self._index_path.exists():
            return {}
        try:
            raw = self._index_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
            self._last_updated = payload.get("_meta", {}).get("last_updated")
            return payload.get("files", {})
        except (json.JSONDecodeError, OSError, KeyError):
            logger.warning("Corrupt repo index at %s — rebuilding", self._index_path)
            return {}

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        """Atomically persist the index via tempfile + os.replace."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC).isoformat()
        payload = {
            "_meta": {"last_updated": now},
            "files": data,
        }
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._state_dir),
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=1)
            os.replace(tmp_path, str(self._index_path))
        except OSError:
            logger.warning("Failed to write repo index to %s", self._index_path)
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        self._last_updated = now

    # -- public API ----------------------------------------------------------

    def update_incremental(
        self,
        root: str | Path,
        languages: list[str] | None = None,
    ) -> SymbolGraph:
        """Re-index only changed files and return a full SymbolGraph.

        Args:
            root: Repository root path.
            languages: Languages to include (default: python, javascript, typescript).

        Returns:
            SymbolGraph reflecting the current state of all tracked files.
        """
        root = Path(root).resolve()
        languages = languages or ["python", "javascript", "typescript"]

        existing = self._load()
        files = _collect_files(root, languages)
        {str(fp) for fp in files}

        updated: dict[str, dict[str, Any]] = {}
        self._stale_count = 0

        for fp in files:
            key = str(fp)
            file_hash = _md5_file(fp)

            prev = existing.get(key)
            if prev and prev.get("hash") == file_hash:
                # Unchanged — carry forward
                updated[key] = prev
            else:
                # New or changed — re-extract
                self._stale_count += 1
                symbol_names = _extract_symbol_names(fp, root)
                updated[key] = {"hash": file_hash, "symbols": symbol_names}

        # Drop entries for files that no longer exist
        self._data = updated
        self._save(updated)

        # Invalidate build_map cache before rebuilding — incremental update
        # explicitly requests fresh data, so bypass TTL cache
        invalidate_cache()

        # Build a full SymbolGraph from the current file set
        return build_map(root, languages)

    def get_stats(self) -> dict[str, Any]:
        """Return index statistics.

        Returns:
            Dict with total_files, indexed_files, stale_files, last_updated.
        """
        return {
            "total_files": len(self._data),
            "indexed_files": len(self._data),
            "stale_files": self._stale_count,
            "last_updated": self._last_updated,
        }
