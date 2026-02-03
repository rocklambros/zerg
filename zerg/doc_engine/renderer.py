"""Render documentation markdown from detected component types and extracted symbols."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from zerg.doc_engine.detector import ComponentDetector, ComponentType
from zerg.doc_engine.extractor import ClassInfo, FunctionInfo, SymbolExtractor, SymbolTable
from zerg.doc_engine.templates import TEMPLATES

logger = logging.getLogger(__name__)


class DocRenderer:
    """Orchestrates component detection, symbol extraction, and template rendering.

    Usage::

        renderer = DocRenderer(project_root=Path("."))
        markdown = renderer.render(Path("zerg/launcher.py"))
    """

    def __init__(self, project_root: Path) -> None:
        self._root = Path(project_root)
        self._detector = ComponentDetector()
        self._extractor = SymbolExtractor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        target: Path,
        component_type: str | None = None,
        depth: str = "standard",
    ) -> str:
        """Render documentation for *target*.

        Args:
            target: Path to the file to document.
            component_type: Override auto-detection with a ComponentType name
                (e.g. ``"MODULE"``).  ``None`` means auto-detect.
            depth: Rendering depth -- ``"standard"`` (default) or ``"deep"``.
                Reserved for future use.

        Returns:
            Rendered markdown string.
        """
        target = Path(target)

        if component_type is not None:
            ctype = ComponentType[component_type.upper()]
        else:
            ctype = self._detector.detect(target)

        if ctype == ComponentType.MODULE:
            symbols = self._extractor.extract(target)
            return self.render_module(symbols)
        if ctype == ComponentType.COMMAND:
            return self.render_command(target)
        if ctype == ComponentType.CONFIG:
            return self.render_config(target)
        if ctype == ComponentType.TYPES:
            symbols = self._extractor.extract(target)
            return self.render_types(symbols)
        if ctype == ComponentType.API:
            symbols = self._extractor.extract(target)
            return self.render_api(symbols)

        # Fallback -- treat as module
        symbols = self._extractor.extract(target)
        return self.render_module(symbols)

    # ------------------------------------------------------------------
    # Component renderers
    # ------------------------------------------------------------------

    def render_module(self, symbols: SymbolTable) -> str:
        """Render a MODULE template from an extracted SymbolTable."""
        title = _module_title(symbols.path, self._root)
        summary = symbols.module_docstring or "No module docstring."
        lines = _count_lines(symbols.path)

        classes_table = _build_classes_table(symbols.classes)
        functions_table = _build_functions_table(symbols.functions)
        imports_list = _build_imports_list(symbols.imports)
        dependency_diagram = _build_dependency_diagram(title, symbols.imports)

        return TEMPLATES["MODULE"].format(
            title=title,
            summary=summary,
            path=_relative(symbols.path, self._root),
            lines=lines,
            class_count=len(symbols.classes),
            function_count=len(symbols.functions),
            classes_table=classes_table,
            functions_table=functions_table,
            imports_list=imports_list,
            dependency_diagram=dependency_diagram,
            see_also="_No cross-references generated._",
        )

    def render_command(self, path: Path) -> str:
        """Render a COMMAND template from a markdown command file."""
        text = path.read_text(encoding="utf-8")
        title = _extract_md_title(text) or path.stem
        summary = _extract_md_summary(text)
        usage = _extract_md_section(text, "Usage") or title
        options_table = _extract_md_section(text, "Options") or "_No options documented._"
        examples = _extract_md_section(text, "Examples") or "_No examples documented._"

        return TEMPLATES["COMMAND"].format(
            title=title,
            summary=summary,
            usage=usage,
            options_table=options_table,
            examples=examples,
            workflow_diagram=f'    A["{title}"] --> B["Execute"]',
            see_also="_No cross-references generated._",
        )

    def render_config(self, path: Path) -> str:
        """Render a CONFIG template from a configuration file."""
        text = path.read_text(encoding="utf-8")
        title = f"Configuration: {path.name}"
        summary = f"Configuration file at `{_relative(path, self._root)}`."

        return TEMPLATES["CONFIG"].format(
            title=title,
            summary=summary,
            options_rows="| _see file_ | - | - | _see file_ |",
            example_config=text[:2000] if text else "# empty",
            env_vars="_No environment variables documented._",
            see_also="_No cross-references generated._",
        )

    def render_types(self, symbols: SymbolTable) -> str:
        """Render a TYPES template from an extracted SymbolTable."""
        title = _module_title(symbols.path, self._root) + " (Types)"
        summary = symbols.module_docstring or "Type definitions module."

        type_defs_table = _build_type_defs_table(symbols)
        enums_table = _build_enums_table(symbols.classes)
        dataclass_details = _build_dataclass_details(symbols.classes)
        class_diagram = _build_class_diagram(symbols.classes)

        return TEMPLATES["TYPES"].format(
            title=title,
            summary=summary,
            type_defs_table=type_defs_table,
            enums_table=enums_table,
            dataclass_details=dataclass_details,
            class_diagram=class_diagram,
            see_also="_No cross-references generated._",
        )

    def render_api(self, symbols: SymbolTable) -> str:
        """Render an API template from an extracted SymbolTable."""
        title = _module_title(symbols.path, self._root) + " (API)"
        summary = symbols.module_docstring or "API endpoint definitions."

        endpoints_table = _build_endpoints_table(symbols.functions)
        schemas = "_Schema extraction not yet implemented._"
        authentication = "_Authentication details not yet extracted._"

        return TEMPLATES["API"].format(
            title=title,
            summary=summary,
            endpoints_table=endpoints_table,
            schemas=schemas,
            authentication=authentication,
            see_also="_No cross-references generated._",
        )


# ======================================================================
# Private helpers
# ======================================================================


def _relative(path: Path, root: Path) -> str:
    """Return path relative to root, or the absolute path as fallback."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _module_title(path: Path, root: Path) -> str:
    """Derive a human-readable module title from a file path."""
    rel = _relative(path, root)
    return rel.replace("/", ".").removesuffix(".py")


def _count_lines(path: Path) -> int:
    """Count the number of lines in a file."""
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0


# -- Table builders ----------------------------------------------------


def _build_classes_table(classes: list[ClassInfo]) -> str:
    if not classes:
        return "_No classes defined._"
    header = "| Class | Bases | Methods | Description |\n|-------|-------|---------|-------------|\n"
    rows = []
    for cls in classes:
        bases = ", ".join(cls.bases) if cls.bases else "-"
        desc = (cls.docstring or "").split("\n")[0][:80] or "-"
        rows.append(f"| `{cls.name}` | {bases} | {len(cls.methods)} | {desc} |")
    return header + "\n".join(rows)


def _build_functions_table(functions: list[FunctionInfo]) -> str:
    if not functions:
        return "_No module-level functions defined._"
    header = "| Function | Arguments | Returns | Description |\n|----------|-----------|---------|-------------|\n"
    rows = []
    for fn in functions:
        args = ", ".join(fn.args) if fn.args else "-"
        ret = fn.return_type or "-"
        desc = (fn.docstring or "").split("\n")[0][:80] or "-"
        rows.append(f"| `{fn.name}` | `{args}` | `{ret}` | {desc} |")
    return header + "\n".join(rows)


def _build_imports_list(imports: list) -> str:
    if not imports:
        return "_No imports._"
    lines = []
    for imp in imports:
        if imp.is_from:
            names = ", ".join(imp.names)
            lines.append(f"- `from {imp.module} import {names}`")
        else:
            lines.append(f"- `import {imp.module}`")
    return "\n".join(lines)


def _build_dependency_diagram(title: str, imports: list) -> str:
    if not imports:
        return f'    {_mermaid_id(title)}["{title}"]'
    lines = []
    src = _mermaid_id(title)
    for imp in imports:
        mod = imp.module or "unknown"
        tgt = _mermaid_id(mod)
        lines.append(f'    {src} --> {tgt}["{mod}"]')
    return "\n".join(lines)


def _mermaid_id(name: str) -> str:
    """Sanitize a name for use as a Mermaid node identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


# -- Types helpers -----------------------------------------------------


def _build_type_defs_table(symbols: SymbolTable) -> str:
    items = symbols.type_aliases + symbols.constants
    if not items:
        return "_No type aliases or constants defined._"
    header = "| Name | Kind |\n|------|------|\n"
    rows = []
    for alias in symbols.type_aliases:
        rows.append(f"| `{alias}` | TypeAlias |")
    for const in symbols.constants:
        rows.append(f"| `{const}` | Constant |")
    return header + "\n".join(rows)


def _build_enums_table(classes: list[ClassInfo]) -> str:
    enums = [c for c in classes if "Enum" in " ".join(c.bases)]
    if not enums:
        return "_No enums defined._"
    header = "| Enum | Bases | Members |\n|------|-------|---------|\n"
    rows = []
    for cls in enums:
        bases = ", ".join(cls.bases)
        rows.append(f"| `{cls.name}` | {bases} | {len(cls.methods)} methods |")
    return header + "\n".join(rows)


def _build_dataclass_details(classes: list[ClassInfo]) -> str:
    dcs = [c for c in classes if any("dataclass" in d for d in c.decorators)]
    if not dcs:
        return "_No dataclasses or TypedDicts defined._"
    sections = []
    for cls in dcs:
        fields = "\n".join(f"  - `{m.name}({', '.join(m.args)})`" for m in cls.methods)
        sections.append(f"### {cls.name}\n\n{cls.docstring or '-'}\n\n{fields}")
    return "\n\n".join(sections)


def _build_class_diagram(classes: list[ClassInfo]) -> str:
    if not classes:
        return "    class Empty"
    lines = []
    for cls in classes:
        lines.append(f"    class {cls.name}")
        for base in cls.bases:
            safe_base = re.sub(r"[^a-zA-Z0-9_]", "_", base)
            lines.append(f"    {safe_base} <|-- {cls.name}")
    return "\n".join(lines)


# -- Endpoint helpers --------------------------------------------------


def _build_endpoints_table(functions: list[FunctionInfo]) -> str:
    if not functions:
        return "_No endpoints defined._"
    header = "| Function | Decorators | Arguments | Returns |\n|----------|------------|-----------|----------|\n"
    rows = []
    for fn in functions:
        decs = ", ".join(fn.decorators) if fn.decorators else "-"
        args = ", ".join(fn.args) if fn.args else "-"
        ret = fn.return_type or "-"
        rows.append(f"| `{fn.name}` | `{decs}` | `{args}` | `{ret}` |")
    return header + "\n".join(rows)


# -- Markdown extraction helpers ---------------------------------------


def _extract_md_title(text: str) -> str | None:
    """Extract the first H1 heading from markdown text."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped.lstrip("# ").strip()
    return None


def _extract_md_summary(text: str) -> str:
    """Extract the first paragraph after the H1 heading."""
    lines = text.splitlines()
    past_title = False
    summary_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not past_title:
            if stripped.startswith("# ") and not stripped.startswith("## "):
                past_title = True
            continue
        if stripped == "":
            if summary_lines:
                break
            continue
        if stripped.startswith("#"):
            break
        summary_lines.append(stripped)
    return " ".join(summary_lines) if summary_lines else "No summary available."


def _extract_md_section(text: str, heading: str) -> str | None:
    """Extract the body of a markdown section by heading name."""
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    start = match.end()
    # Find next heading of same or higher level
    next_heading = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()
