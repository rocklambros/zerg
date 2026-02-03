"""Unit tests for all zerg.doc_engine modules.

Covers: ComponentDetector, SymbolExtractor, DependencyMapper,
MermaidGenerator, DocRenderer, CrossRefBuilder, SidebarGenerator.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zerg.doc_engine.crossref import CrossRefBuilder, GlossaryEntry
from zerg.doc_engine.dependencies import DependencyGraph, DependencyMapper, ModuleNode
from zerg.doc_engine.detector import ComponentDetector, ComponentType
from zerg.doc_engine.extractor import SymbolExtractor, SymbolTable
from zerg.doc_engine.mermaid import MermaidGenerator
from zerg.doc_engine.renderer import DocRenderer
from zerg.doc_engine.sidebar import SidebarConfig, SidebarGenerator, SidebarSection

# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def detector() -> ComponentDetector:
    return ComponentDetector()


@pytest.fixture
def extractor() -> SymbolExtractor:
    return SymbolExtractor()


@pytest.fixture
def mermaid() -> MermaidGenerator:
    return MermaidGenerator()


@pytest.fixture
def crossref() -> CrossRefBuilder:
    return CrossRefBuilder()


@pytest.fixture
def sidebar() -> SidebarGenerator:
    return SidebarGenerator()


@pytest.fixture
def simple_py(tmp_path: Path) -> Path:
    """A minimal Python module with a class, function, constant, and docstring."""
    source = tmp_path / "simple.py"
    source.write_text(
        '''\
"""A simple test module."""

import os
from pathlib import Path

MAX_RETRIES = 5

class Greeter:
    """Greets people."""

    def greet(self, name: str) -> str:
        """Say hello."""
        return f"Hello, {name}"

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

async def fetch(url: str) -> str:
    """Fetch a URL asynchronously."""
    return ""
''',
        encoding="utf-8",
    )
    return source


@pytest.fixture
def types_py(tmp_path: Path) -> Path:
    """A file dominated by class definitions (detected as TYPES)."""
    source = tmp_path / "types.py"
    source.write_text(
        '''\
"""Type definitions."""

from enum import Enum
from dataclasses import dataclass

class Color(Enum):
    RED = "red"
    GREEN = "green"

@dataclass
class Point:
    """A 2D point."""
    x: float
    y: float
''',
        encoding="utf-8",
    )
    return source


@pytest.fixture
def api_py(tmp_path: Path) -> Path:
    """A Python file containing API endpoint markers."""
    source = tmp_path / "api.py"
    source.write_text(
        '''\
"""API endpoints."""

from flask import Flask
app = Flask(__name__)

@app.route("/health")
def health():
    return "ok"
''',
        encoding="utf-8",
    )
    return source


@pytest.fixture
def config_yaml(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("key: value\n", encoding="utf-8")
    return cfg


@pytest.fixture
def command_md(tmp_path: Path) -> Path:
    """A markdown file inside a data/commands directory."""
    cmd_dir = tmp_path / "data" / "commands"
    cmd_dir.mkdir(parents=True)
    md = cmd_dir / "run.md"
    md.write_text(
        """\
# Run Command

Execute the run operation.

## Usage

zerg run [options]

## Options

| Flag | Description |
|------|-------------|
| --fast | Run faster |

## Examples

```bash
zerg run --fast
```
""",
        encoding="utf-8",
    )
    return md


# ======================================================================
# ComponentDetector
# ======================================================================


class TestComponentDetector:
    def test_instantiation(self, detector: ComponentDetector) -> None:
        assert detector is not None

    def test_detect_module(self, detector: ComponentDetector, simple_py: Path) -> None:
        assert detector.detect(simple_py) == ComponentType.MODULE

    def test_detect_config_yaml(self, detector: ComponentDetector, config_yaml: Path) -> None:
        assert detector.detect(config_yaml) == ComponentType.CONFIG

    def test_detect_config_py(self, detector: ComponentDetector, tmp_path: Path) -> None:
        cfg = tmp_path / "config.py"
        cfg.write_text("DB_URL = 'sqlite:///db.sqlite'\n", encoding="utf-8")
        assert detector.detect(cfg) == ComponentType.CONFIG

    def test_detect_types_by_stem(self, detector: ComponentDetector, types_py: Path) -> None:
        assert detector.detect(types_py) == ComponentType.TYPES

    def test_detect_types_by_ast(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """A file with >50% class defs is detected as TYPES even without a types stem."""
        src = tmp_path / "models.py"
        src.write_text(
            "class A:\n    pass\nclass B:\n    pass\n",
            encoding="utf-8",
        )
        assert detector.detect(src) == ComponentType.TYPES

    def test_detect_api(self, detector: ComponentDetector, api_py: Path) -> None:
        assert detector.detect(api_py) == ComponentType.API

    def test_detect_command(self, detector: ComponentDetector, command_md: Path) -> None:
        assert detector.detect(command_md) == ComponentType.COMMAND

    def test_detect_regular_md_is_not_command(self, detector: ComponentDetector, tmp_path: Path) -> None:
        md = tmp_path / "readme.md"
        md.write_text("# Readme\n", encoding="utf-8")
        assert detector.detect(md) != ComponentType.COMMAND

    def test_detect_all_returns_dict(self, detector: ComponentDetector, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "b.yaml").write_text("key: 1\n", encoding="utf-8")
        results = detector.detect_all(tmp_path)
        assert isinstance(results, dict)
        assert len(results) == 2

    def test_detect_all_skips_hidden_and_pycache(self, detector: ComponentDetector, tmp_path: Path) -> None:
        (tmp_path / ".hidden.py").write_text("x = 1\n", encoding="utf-8")
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "mod.pyc").write_text("", encoding="utf-8")
        (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
        results = detector.detect_all(tmp_path)
        assert len(results) == 1

    def test_detect_empty_py_file(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        assert detector.detect(f) == ComponentType.MODULE

    def test_detect_syntax_error_py(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("def (broken:\n", encoding="utf-8")
        # Should not raise; falls through to MODULE
        assert detector.detect(f) == ComponentType.MODULE


# ======================================================================
# SymbolExtractor
# ======================================================================


class TestSymbolExtractor:
    def test_instantiation(self, extractor: SymbolExtractor) -> None:
        assert extractor is not None

    def test_extract_module_docstring(self, extractor: SymbolExtractor, simple_py: Path) -> None:
        table = extractor.extract(simple_py)
        assert table.module_docstring == "A simple test module."

    def test_extract_classes(self, extractor: SymbolExtractor, simple_py: Path) -> None:
        table = extractor.extract(simple_py)
        assert len(table.classes) == 1
        cls = table.classes[0]
        assert cls.name == "Greeter"
        assert cls.docstring == "Greets people."
        assert len(cls.methods) == 1
        assert cls.methods[0].name == "greet"
        assert cls.methods[0].is_method is True

    def test_extract_functions(self, extractor: SymbolExtractor, simple_py: Path) -> None:
        table = extractor.extract(simple_py)
        func_names = [f.name for f in table.functions]
        assert "add" in func_names
        assert "fetch" in func_names

    def test_extract_async_function(self, extractor: SymbolExtractor, simple_py: Path) -> None:
        table = extractor.extract(simple_py)
        fetch_fn = [f for f in table.functions if f.name == "fetch"][0]
        assert fetch_fn.is_async is True

    def test_extract_return_type(self, extractor: SymbolExtractor, simple_py: Path) -> None:
        table = extractor.extract(simple_py)
        add_fn = [f for f in table.functions if f.name == "add"][0]
        assert add_fn.return_type == "int"

    def test_extract_imports(self, extractor: SymbolExtractor, simple_py: Path) -> None:
        table = extractor.extract(simple_py)
        assert len(table.imports) == 2
        modules = {imp.module for imp in table.imports}
        assert "os" in modules
        assert "pathlib" in modules

    def test_extract_constants(self, extractor: SymbolExtractor, simple_py: Path) -> None:
        table = extractor.extract(simple_py)
        assert "MAX_RETRIES" in table.constants

    def test_extract_type_alias(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "aliases.py"
        src.write_text(
            "from typing import TypeAlias\n\nMyType: TypeAlias = dict[str, int]\n",
            encoding="utf-8",
        )
        table = extractor.extract(src)
        assert "MyType" in table.type_aliases

    def test_extract_empty_file(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        table = extractor.extract(f)
        assert table.module_docstring is None
        assert not table.classes
        assert not table.functions

    def test_extract_syntax_error_raises(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("def (broken:\n", encoding="utf-8")
        with pytest.raises(SyntaxError):
            extractor.extract(f)

    def test_extract_missing_file_raises(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.py"
        with pytest.raises(OSError):
            extractor.extract(f)

    def test_extract_decorators(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "decorated.py"
        src.write_text(
            "from dataclasses import dataclass\n\n@dataclass\nclass Cfg:\n    x: int = 1\n",
            encoding="utf-8",
        )
        table = extractor.extract(src)
        assert "dataclass" in table.classes[0].decorators

    def test_extract_function_args(self, extractor: SymbolExtractor, simple_py: Path) -> None:
        table = extractor.extract(simple_py)
        add_fn = [f for f in table.functions if f.name == "add"][0]
        assert "a: int" in add_fn.args
        assert "b: int" in add_fn.args


# ======================================================================
# DependencyMapper
# ======================================================================


class TestDependencyMapper:
    def test_build_empty_dir(self, tmp_path: Path) -> None:
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert graph.modules == {}

    def test_build_single_module(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "core.py").write_text("import os\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert "mypkg.core" in graph.modules

    def test_build_internal_dependency(self, tmp_path: Path) -> None:
        """Use `import mypkg.b` so the resolver produces `mypkg.b` as the target."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "a.py").write_text("import mypkg.b\n", encoding="utf-8")
        (pkg / "b.py").write_text("x = 1\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert "mypkg.b" in graph.get_imports("mypkg.a")
        assert "mypkg.a" in graph.get_importers("mypkg.b")

    def test_build_from_import_resolves_to_package(self, tmp_path: Path) -> None:
        """Verify that `from mypkg import b` resolves to the package, not submodule."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "a.py").write_text("from mypkg import b\n", encoding="utf-8")
        (pkg / "b.py").write_text("x = 1\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        # `from mypkg import b` resolves to importing the `mypkg` package itself
        assert "mypkg" in graph.get_imports("mypkg.a")

    def test_to_adjacency_list(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "a.py").write_text("import mypkg.b\n", encoding="utf-8")
        (pkg / "b.py").write_text("x = 1\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        adj = DependencyMapper.to_adjacency_list(graph)
        assert isinstance(adj, dict)
        assert "mypkg.b" in adj.get("mypkg.a", [])

    def test_get_dependency_chain(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "a.py").write_text("import mypkg.b\n", encoding="utf-8")
        (pkg / "b.py").write_text("import mypkg.c\n", encoding="utf-8")
        (pkg / "c.py").write_text("x = 1\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        chain = graph.get_dependency_chain("mypkg.a")
        assert "mypkg.b" in chain
        assert "mypkg.c" in chain

    def test_get_imports_missing_module(self) -> None:
        graph = DependencyGraph()
        assert graph.get_imports("nonexistent") == []

    def test_get_importers_missing_module(self) -> None:
        graph = DependencyGraph()
        assert graph.get_importers("nonexistent") == []

    def test_external_imports_excluded(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "core.py").write_text("import os\nimport json\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        node = graph.modules["mypkg.core"]
        assert not node.imports  # os, json are external

    def test_syntax_error_file_skipped(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "bad.py").write_text("def (broken:\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        # The module should still be discovered (empty imports)
        assert "mypkg.bad" in graph.modules


# ======================================================================
# MermaidGenerator
# ======================================================================


class TestMermaidGenerator:
    def test_instantiation(self, mermaid: MermaidGenerator) -> None:
        assert mermaid is not None

    def test_dependency_graph_basic(self, mermaid: MermaidGenerator) -> None:
        modules = {"pkg.a": ["pkg.b"], "pkg.b": []}
        result = mermaid.dependency_graph(modules)
        assert "```mermaid" in result
        assert "graph TD" in result
        assert "-->" in result

    def test_dependency_graph_with_title(self, mermaid: MermaidGenerator) -> None:
        result = mermaid.dependency_graph({"a": []}, title="Test Title")
        assert "%% Test Title" in result

    def test_dependency_graph_empty(self, mermaid: MermaidGenerator) -> None:
        result = mermaid.dependency_graph({})
        assert "```mermaid" in result
        assert "graph TD" in result

    def test_workflow(self, mermaid: MermaidGenerator) -> None:
        steps = [
            {"actor": "User", "action": "clicks button", "target": "Server"},
            {"actor": "Server", "action": "returns data", "target": "User"},
        ]
        result = mermaid.workflow(steps)
        assert "sequenceDiagram" in result
        assert "User->>+Server: clicks button" in result

    def test_workflow_empty(self, mermaid: MermaidGenerator) -> None:
        result = mermaid.workflow([])
        assert "sequenceDiagram" in result

    def test_state_machine(self, mermaid: MermaidGenerator) -> None:
        states = ["Idle", "Running"]
        transitions = [("Idle", "Running", "start")]
        result = mermaid.state_machine(states, transitions)
        assert "stateDiagram-v2" in result
        assert "Idle : Idle" in result
        assert "Idle --> Running: start" in result

    def test_data_flow(self, mermaid: MermaidGenerator) -> None:
        nodes = [
            {"id": "input", "label": "Input", "type": "external"},
            {"id": "proc", "label": "Process", "type": "process"},
            {"id": "db", "label": "Database", "type": "store"},
        ]
        edges = [
            {"from": "input", "to": "proc", "label": "raw data"},
            {"from": "proc", "to": "db"},
        ]
        result = mermaid.data_flow(nodes, edges)
        assert "flowchart LR" in result
        assert "raw data" in result

    def test_class_diagram(self, mermaid: MermaidGenerator) -> None:
        classes = [
            {
                "name": "Animal",
                "methods": ["speak"],
                "attributes": ["name: str"],
                "bases": [],
            },
            {
                "name": "Dog",
                "methods": ["speak", "fetch"],
                "attributes": ["breed: str"],
                "bases": ["Animal"],
            },
        ]
        result = mermaid.class_diagram(classes)
        assert "classDiagram" in result
        assert "class Animal" in result
        assert "Animal <|-- Dog" in result

    def test_class_diagram_empty(self, mermaid: MermaidGenerator) -> None:
        result = mermaid.class_diagram([])
        assert "classDiagram" in result


# ======================================================================
# DocRenderer
# ======================================================================


class TestDocRenderer:
    def test_instantiation(self, tmp_path: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        assert renderer is not None

    def test_render_module(self, tmp_path: Path, simple_py: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(simple_py)
        assert "# " in md  # has a title
        assert "Greeter" in md
        assert "add" in md
        assert "Module Info" in md

    def test_render_config(self, tmp_path: Path, config_yaml: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(config_yaml)
        assert "Configuration:" in md
        assert "key: value" in md

    def test_render_command(self, tmp_path: Path, command_md: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(command_md)
        assert "Run Command" in md
        assert "Usage" in md

    def test_render_types(self, tmp_path: Path, types_py: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(types_py, component_type="TYPES")
        assert "(Types)" in md
        assert "Color" in md

    def test_render_api(self, tmp_path: Path, api_py: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(api_py, component_type="API")
        assert "(API)" in md
        assert "health" in md

    def test_render_with_override_type(self, tmp_path: Path, simple_py: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(simple_py, component_type="MODULE")
        assert "Module Info" in md

    def test_render_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f)
        assert "No module docstring" in md

    def test_render_module_contains_see_also(self, tmp_path: Path, simple_py: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(simple_py)
        assert "See Also" in md

    def test_render_command_missing_sections(self, tmp_path: Path) -> None:
        """A command file with no Options or Examples sections."""
        cmd_dir = tmp_path / "data" / "commands"
        cmd_dir.mkdir(parents=True)
        md_file = cmd_dir / "bare.md"
        md_file.write_text("# Bare\n\nJust a description.\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(md_file)
        assert "Bare" in md


# ======================================================================
# CrossRefBuilder
# ======================================================================


class TestCrossRefBuilder:
    def test_instantiation(self, crossref: CrossRefBuilder) -> None:
        assert crossref is not None

    def test_build_glossary_from_headings(self, crossref: CrossRefBuilder) -> None:
        pages = {
            "page1": "## Term One\n\nDefinition of term one.\n\n## Term Two\n\nAnother definition.",
        }
        glossary = crossref.build_glossary(pages)
        terms = {e.term for e in glossary}
        assert "Term One" in terms
        assert "Term Two" in terms

    def test_build_glossary_from_bold_defs(self, crossref: CrossRefBuilder) -> None:
        pages = {
            "page1": "Some text.\n\n**Widget**: A reusable component.\n",
        }
        glossary = crossref.build_glossary(pages)
        assert any(e.term == "Widget" for e in glossary)

    def test_build_glossary_dedup(self, crossref: CrossRefBuilder) -> None:
        pages = {
            "p1": "## Dup\n\nFirst.\n",
            "p2": "## Dup\n\nSecond.\n",
        }
        glossary = crossref.build_glossary(pages)
        # Only first occurrence should be kept
        dup_entries = [e for e in glossary if e.term == "Dup"]
        assert len(dup_entries) == 1

    def test_build_glossary_empty_pages(self, crossref: CrossRefBuilder) -> None:
        assert crossref.build_glossary({}) == []

    def test_inject_links_basic(self, crossref: CrossRefBuilder) -> None:
        glossary = [
            GlossaryEntry(term="Widget", definition="A component.", page="other"),
        ]
        content = "We use a Widget here."
        result = crossref.inject_links(content, glossary, current_page="mypage")
        assert "[[Widget|Widget]]" in result

    def test_inject_links_no_self_link(self, crossref: CrossRefBuilder) -> None:
        glossary = [
            GlossaryEntry(term="Widget", definition="A component.", page="mypage"),
        ]
        content = "We use a Widget here."
        result = crossref.inject_links(content, glossary, current_page="mypage")
        assert "[[" not in result

    def test_inject_links_skips_code_blocks(self, crossref: CrossRefBuilder) -> None:
        glossary = [
            GlossaryEntry(term="Widget", definition="A component.", page="other"),
        ]
        content = "```\nWidget\n```\n\nWidget outside."
        result = crossref.inject_links(content, glossary, current_page="mypage")
        # The link should appear for the occurrence outside the code block
        assert "[[Widget|Widget]]" in result

    def test_inject_links_skips_headings(self, crossref: CrossRefBuilder) -> None:
        glossary = [
            GlossaryEntry(term="Widget", definition="A component.", page="other"),
        ]
        content = "## Widget\n\nWidget in body."
        result = crossref.inject_links(content, glossary, current_page="mypage")
        # The heading occurrence should not be linked, but the body one should
        assert result.count("[[Widget|Widget]]") == 1

    def test_see_also_basic(self, crossref: CrossRefBuilder) -> None:
        pages = {
            "page1": "## Authentication\n\nHandles auth logic.",
            "page2": "## Authentication\n\nAuth config reference.",
            "page3": "## Unrelated\n\nNothing in common.",
        }
        related = crossref.see_also("page1", pages, max_related=5)
        assert "page2" in related

    def test_see_also_missing_page(self, crossref: CrossRefBuilder) -> None:
        pages = {"page1": "content"}
        assert crossref.see_also("nonexistent", pages) == []

    def test_see_also_respects_max(self, crossref: CrossRefBuilder) -> None:
        pages = {f"page{i}": "## Shared\n\nCommon content." for i in range(10)}
        related = crossref.see_also("page0", pages, max_related=3)
        assert len(related) <= 3

    def test_generate_glossary_page(self, crossref: CrossRefBuilder) -> None:
        glossary = [
            GlossaryEntry(term="Beta", definition="Second.", page="p1"),
            GlossaryEntry(term="Alpha", definition="First.", page="p2"),
        ]
        page = crossref.generate_glossary_page(glossary)
        assert "# Glossary" in page
        # Alpha should appear before Beta
        alpha_pos = page.index("Alpha")
        beta_pos = page.index("Beta")
        assert alpha_pos < beta_pos

    def test_generate_glossary_page_with_aliases(self, crossref: CrossRefBuilder) -> None:
        glossary = [
            GlossaryEntry(
                term="CLI",
                definition="Command line.",
                page="p1",
                aliases=["command-line interface"],
            ),
        ]
        page = crossref.generate_glossary_page(glossary)
        assert "Aliases:" in page
        assert "command-line interface" in page

    def test_generate_glossary_page_empty(self, crossref: CrossRefBuilder) -> None:
        page = crossref.generate_glossary_page([])
        assert "# Glossary" in page


# ======================================================================
# SidebarGenerator
# ======================================================================


class TestSidebarGenerator:
    def test_instantiation(self, sidebar: SidebarGenerator) -> None:
        assert sidebar is not None

    def test_generate_defaults(self, sidebar: SidebarGenerator) -> None:
        result = sidebar.generate()
        assert "## ZERG Wiki" in result
        assert "**Home**" in result
        assert "Getting Started" in result

    def test_generate_with_page_filter(self, sidebar: SidebarGenerator) -> None:
        result = sidebar.generate(pages=["Home", "Glossary"])
        assert "[[Home|Home]]" in result
        # Pages not in the filter should be marked coming soon
        assert "coming soon" in result

    def test_generate_with_config(self, sidebar: SidebarGenerator) -> None:
        config = SidebarConfig(
            title="My Wiki",
            sections=[SidebarSection(title="Docs", pages=["PageA", "PageB"])],
        )
        result = sidebar.generate(config=config)
        assert "## My Wiki" in result
        assert "**Docs**" in result
        assert "PageA" in result

    def test_generate_config_empty_sections_uses_defaults(self, sidebar: SidebarGenerator) -> None:
        config = SidebarConfig(title="Custom Title", sections=[])
        result = sidebar.generate(config=config)
        assert "## Custom Title" in result
        # Falls back to default sections
        assert "Home" in result

    def test_generate_section_with_icon(self, sidebar: SidebarGenerator) -> None:
        config = SidebarConfig(
            title="Wiki",
            sections=[
                SidebarSection(title="Starred", pages=["PageX"], icon="*"),
            ],
        )
        result = sidebar.generate(config=config)
        assert "* **Starred**" in result

    def test_generate_footer(self, sidebar: SidebarGenerator) -> None:
        footer = sidebar.generate_footer()
        assert "---" in footer
        assert "[[Home]]" in footer
        assert "GitHub" in footer

    def test_filter_pages_all_available(self, sidebar: SidebarGenerator) -> None:
        result = sidebar._filter_pages(["A", "B"], existing={"A", "B", "C"})
        assert all(available for _, available in result)

    def test_filter_pages_none_existing(self, sidebar: SidebarGenerator) -> None:
        result = sidebar._filter_pages(["A", "B"], existing=None)
        assert all(available for _, available in result)

    def test_filter_pages_partial(self, sidebar: SidebarGenerator) -> None:
        result = sidebar._filter_pages(["A", "B"], existing={"A"})
        availability = {name: avail for name, avail in result}
        assert availability["A"] is True
        assert availability["B"] is False

    def test_empty_section_shows_coming_soon(self, sidebar: SidebarGenerator) -> None:
        """Sections whose pages are not in the filter still appear with 'coming soon'."""
        config = SidebarConfig(
            title="Wiki",
            sections=[
                SidebarSection(title="Visible", pages=["Home"]),
                SidebarSection(title="Planned", pages=["NonExistent"]),
            ],
        )
        result = sidebar.generate(pages=["Home"], config=config)
        assert "**Visible**" in result
        assert "**Planned**" in result
        assert "coming soon" in result


# ======================================================================
# Data classes standalone
# ======================================================================


class TestDataClasses:
    def test_module_node(self) -> None:
        node = ModuleNode(name="pkg.mod", path=Path("/fake"))
        assert node.name == "pkg.mod"
        assert not node.imports
        assert not node.imported_by

    def test_dependency_graph_empty(self) -> None:
        graph = DependencyGraph()
        assert graph.get_imports("x") == []
        assert graph.get_importers("x") == []
        assert graph.get_dependency_chain("x") == []

    def test_symbol_table_fields(self, simple_py: Path) -> None:
        table = SymbolTable(
            path=simple_py,
            module_docstring=None,
            classes=[],
            functions=[],
            imports=[],
            constants=[],
            type_aliases=[],
        )
        assert table.path == simple_py
        assert not table.classes

    def test_glossary_entry(self) -> None:
        entry = GlossaryEntry(term="Test", definition="A test.", page="p1", aliases=["t"])
        assert entry.term == "Test"
        assert entry.aliases == ["t"]

    def test_sidebar_section(self) -> None:
        sec = SidebarSection(title="Section", pages=["A"])
        assert sec.icon == ""

    def test_sidebar_config(self) -> None:
        cfg = SidebarConfig()
        assert cfg.title == "ZERG Wiki"
        assert not cfg.sections
