"""JS/TS symbol extraction via regex for ZERG repo map.

Covers named exports, class/function declarations, import statements,
and variable exports. Does not use tree-sitter; regex covers ~90% of cases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class JSSymbol:
    """A symbol extracted from a JS/TS file."""

    name: str
    kind: str  # "function", "class", "variable", "import", "method"
    signature: str
    line: int
    docstring: str | None = None


# Patterns for symbol extraction
_FUNCTION_DECL = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*(\([^)]*\))",
    re.MULTILINE,
)

_ARROW_EXPORT = re.compile(
    r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>",
    re.MULTILINE,
)

_CLASS_DECL = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+[\w,\s]+)?",
    re.MULTILINE,
)

_METHOD_DECL = re.compile(
    r"^\s+(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?(\w+)\s*(\([^)]*\))",
    re.MULTILINE,
)

_IMPORT_STMT = re.compile(
    r"^import\s+(?:type\s+)?(?:\{([^}]+)\}|(\w+))\s+from\s+['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)

_VARIABLE_EXPORT = re.compile(
    r"^export\s+(?:const|let|var)\s+(\w+)\s*(?::\s*([^=]+))?\s*=",
    re.MULTILINE,
)

_INTERFACE_DECL = re.compile(
    r"^(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+[\w,\s]+)?",
    re.MULTILINE,
)

_TYPE_ALIAS = re.compile(
    r"^(?:export\s+)?type\s+(\w+)\s*(?:<[^>]+>)?\s*=",
    re.MULTILINE,
)


def extract_js_symbols(source: str, filepath: str = "") -> list[JSSymbol]:
    """Extract symbols from JavaScript/TypeScript source code.

    Args:
        source: File contents.
        filepath: Path for reference (not required).

    Returns:
        List of extracted symbols.
    """
    symbols: list[JSSymbol] = []
    lines = source.split("\n")

    def _line_number(match: re.Match) -> int:
        return source[: match.start()].count("\n") + 1

    # Functions
    for m in _FUNCTION_DECL.finditer(source):
        name = m.group(1)
        params = m.group(2)
        symbols.append(
            JSSymbol(
                name=name,
                kind="function",
                signature=f"function {name}{params}",
                line=_line_number(m),
                docstring=_get_preceding_comment(lines, _line_number(m) - 1),
            )
        )

    # Arrow function exports
    for m in _ARROW_EXPORT.finditer(source):
        name = m.group(1)
        # Skip if already captured as a function
        if any(s.name == name and s.kind == "function" for s in symbols):
            continue
        symbols.append(
            JSSymbol(
                name=name,
                kind="function",
                signature=f"const {name} = (...) => ...",
                line=_line_number(m),
            )
        )

    # Classes
    for m in _CLASS_DECL.finditer(source):
        name = m.group(1)
        extends = m.group(2)
        sig = f"class {name}"
        if extends:
            sig += f" extends {extends}"
        symbols.append(
            JSSymbol(
                name=name,
                kind="class",
                signature=sig,
                line=_line_number(m),
                docstring=_get_preceding_comment(lines, _line_number(m) - 1),
            )
        )

    # Interfaces (TS)
    for m in _INTERFACE_DECL.finditer(source):
        name = m.group(1)
        symbols.append(
            JSSymbol(
                name=name,
                kind="class",
                signature=f"interface {name}",
                line=_line_number(m),
            )
        )

    # Type aliases (TS)
    for m in _TYPE_ALIAS.finditer(source):
        name = m.group(1)
        symbols.append(
            JSSymbol(
                name=name,
                kind="variable",
                signature=f"type {name} = ...",
                line=_line_number(m),
            )
        )

    # Imports
    for m in _IMPORT_STMT.finditer(source):
        named = m.group(1)
        default = m.group(2)
        module = m.group(3)
        if named:
            for item in named.split(","):
                item = item.strip().split(" as ")[0].strip()
                if item and item != "type":
                    symbols.append(
                        JSSymbol(
                            name=item,
                            kind="import",
                            signature=f"import {{ {item} }} from '{module}'",
                            line=_line_number(m),
                        )
                    )
        elif default:
            symbols.append(
                JSSymbol(
                    name=default,
                    kind="import",
                    signature=f"import {default} from '{module}'",
                    line=_line_number(m),
                )
            )

    # Variable exports (not already captured)
    for m in _VARIABLE_EXPORT.finditer(source):
        name = m.group(1)
        type_ann = m.group(2)
        if any(s.name == name for s in symbols):
            continue
        sig = f"export const {name}"
        if type_ann:
            sig += f": {type_ann.strip()}"
        symbols.append(
            JSSymbol(
                name=name,
                kind="variable",
                signature=sig,
                line=_line_number(m),
            )
        )

    return symbols


def extract_js_file(filepath: str | Path) -> list[JSSymbol]:
    """Extract symbols from a JS/TS file on disk."""
    path = Path(filepath)
    if not path.exists():
        return []
    try:
        source = path.read_text(errors="replace")
        return extract_js_symbols(source, str(filepath))
    except OSError:
        return []


def _get_preceding_comment(lines: list[str], line_idx: int) -> str | None:
    """Get JSDoc or single-line comment preceding a declaration."""
    if line_idx <= 0 or line_idx > len(lines):
        return None
    prev = lines[line_idx - 1].strip() if line_idx > 0 else ""
    # Single-line JSDoc: /** ... */
    if prev.startswith("/**") and prev.endswith("*/"):
        return prev[3:-2].strip()
    # Check for end of multi-line JSDoc
    if prev == "*/":
        for i in range(line_idx - 2, max(line_idx - 10, -1), -1):
            stripped = lines[i].strip()
            if stripped.startswith("/**"):
                # Extract first description line
                desc_line = stripped[3:].strip()
                if desc_line and desc_line != "*":
                    return desc_line
                if i + 1 < line_idx:
                    next_line = lines[i + 1].strip().lstrip("* ").strip()
                    if next_line and not next_line.startswith("@"):
                        return next_line
                return None
    return None
