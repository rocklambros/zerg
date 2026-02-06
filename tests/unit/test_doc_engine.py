"""Unit tests for zerg.doc_engine modules (thinned).

Covers: ComponentDetector, SymbolExtractor, DependencyMapper,
MermaidGenerator, DocRenderer, CrossRefBuilder, SidebarGenerator.

Detailed edge-case tests were removed in test-suite-reduction-phase2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zerg.doc_engine.crossref import CrossRefBuilder, GlossaryEntry
from zerg.doc_engine.dependencies import DependencyMapper, ModuleNode
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

    def test_detect_types_by_stem(self, detector: ComponentDetector, types_py: Path) -> None:
        assert detector.detect(types_py) == ComponentType.TYPES

    def test_detect_api(self, detector: ComponentDetector, api_py: Path) -> None:
        assert detector.detect(api_py) == ComponentType.API

    def test_detect_all_returns_dict(self, detector: ComponentDetector, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "b.yaml").write_text("key: 1\n", encoding="utf-8")
        results = detector.detect_all(tmp_path)
        assert isinstance(results, dict)
        assert len(results) == 2


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

    def test_extract_functions(self, extractor: SymbolExtractor, simple_py: Path) -> None:
        table = extractor.extract(simple_py)
        func_names = [f.name for f in table.functions]
        assert "add" in func_names
        assert "fetch" in func_names

    def test_extract_missing_file_raises(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.py"
        with pytest.raises(OSError):
            extractor.extract(f)


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

    def test_workflow(self, mermaid: MermaidGenerator) -> None:
        steps = [
            {"actor": "User", "action": "clicks button", "target": "Server"},
            {"actor": "Server", "action": "returns data", "target": "User"},
        ]
        result = mermaid.workflow(steps)
        assert "sequenceDiagram" in result
        assert "User->>+Server: clicks button" in result


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

    def test_render_types(self, tmp_path: Path, types_py: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(types_py, component_type="TYPES")
        assert "(Types)" in md
        assert "Color" in md

    def test_render_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f)
        assert "No module docstring" in md


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

    def test_inject_links_basic(self, crossref: CrossRefBuilder) -> None:
        glossary = [
            GlossaryEntry(term="Widget", definition="A component.", page="other"),
        ]
        content = "We use a Widget here."
        result = crossref.inject_links(content, glossary, current_page="mypage")
        assert "[[Widget|Widget]]" in result

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

    def test_generate_with_config(self, sidebar: SidebarGenerator) -> None:
        config = SidebarConfig(
            title="My Wiki",
            sections=[SidebarSection(title="Docs", pages=["PageA", "PageB"])],
        )
        result = sidebar.generate(config=config)
        assert "## My Wiki" in result
        assert "**Docs**" in result
        assert "PageA" in result

    def test_generate_footer(self, sidebar: SidebarGenerator) -> None:
        footer = sidebar.generate_footer()
        assert "---" in footer
        assert "[[Home]]" in footer
        assert "GitHub" in footer


# ======================================================================
# Data classes standalone
# ======================================================================


class TestDataClasses:
    def test_module_node(self) -> None:
        node = ModuleNode(name="pkg.mod", path=Path("/fake"))
        assert node.name == "pkg.mod"
        assert not node.imports
        assert not node.imported_by

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
