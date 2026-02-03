"""Tests for ZERG repo map Python extractor."""

import textwrap
from pathlib import Path

from zerg.repo_map import (
    Symbol,
    SymbolGraph,
    _extract_python_symbols,
    _path_to_module,
    build_map,
)


class TestSymbol:
    """Tests for Symbol dataclass."""

    def test_creation(self) -> None:
        sym = Symbol(
            name="foo",
            kind="function",
            signature="def foo(x: int) -> bool",
            docstring="Check something.",
            line=10,
            module="zerg.utils",
        )
        assert sym.name == "foo"
        assert sym.kind == "function"
        assert sym.module == "zerg.utils"


class TestSymbolGraph:
    """Tests for SymbolGraph."""

    def test_query_empty(self) -> None:
        graph = SymbolGraph()
        result = graph.query([], [])
        assert result == ""

    def test_query_with_file_match(self) -> None:
        graph = SymbolGraph(
            modules={
                "zerg.config": [
                    Symbol("ZergConfig", "class", "class ZergConfig(BaseModel)", "Config", 1, "zerg.config"),
                ],
            },
        )
        result = graph.query(["zerg/config.py"], [])
        assert "ZergConfig" in result
        assert "class ZergConfig" in result

    def test_query_with_keyword_match(self) -> None:
        graph = SymbolGraph(
            modules={
                "zerg.heartbeat": [
                    Symbol("HeartbeatWriter", "class", "class HeartbeatWriter", "Writer", 1, "zerg.heartbeat"),
                    Symbol("unrelated", "function", "def unrelated()", None, 2, "zerg.heartbeat"),
                ],
            },
        )
        result = graph.query([], ["heartbeat"])
        assert "HeartbeatWriter" in result

    def test_query_respects_budget(self) -> None:
        symbols = [Symbol(f"sym_{i}", "function", f"def sym_{i}()", None, i, "big_module") for i in range(100)]
        graph = SymbolGraph(modules={"big_module": symbols})
        result = graph.query(["big_module.py"], [], max_tokens=50)
        # Should be truncated
        assert len(result) < 50 * 4 + 200  # some overhead

    def test_module_matches_file(self) -> None:
        assert SymbolGraph._module_matches_file("zerg.config", "zerg/config.py")
        assert SymbolGraph._module_matches_file("zerg.config", "src/zerg/config.py")
        assert not SymbolGraph._module_matches_file("zerg.config", "other/module.py")


class TestExtractPythonSymbols:
    """Tests for _extract_python_symbols."""

    def test_extract_function(self, tmp_path: Path) -> None:
        source = textwrap.dedent('''
            def hello(name: str) -> str:
                """Greet someone."""
                return f"Hello {name}"
        ''')
        filepath = tmp_path / "test_mod.py"
        filepath.write_text(source)

        symbols, edges = _extract_python_symbols(filepath, "test_mod")
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "hello"
        assert "str" in funcs[0].signature
        assert funcs[0].docstring == "Greet someone."

    def test_extract_class(self, tmp_path: Path) -> None:
        source = textwrap.dedent('''
            class MyClass(BaseModel):
                """A model."""
                x: int = 0

                def method(self) -> None:
                    pass
        ''')
        filepath = tmp_path / "test_mod.py"
        filepath.write_text(source)

        symbols, edges = _extract_python_symbols(filepath, "test_mod")
        classes = [s for s in symbols if s.kind == "class"]
        methods = [s for s in symbols if s.kind == "method"]
        assert len(classes) == 1
        assert classes[0].name == "MyClass"
        assert len(methods) == 1
        assert methods[0].name == "MyClass.method"

        # Should have inheritance edge
        inherit_edges = [e for e in edges if e.kind == "inherits"]
        assert len(inherit_edges) == 1
        assert inherit_edges[0].target == "BaseModel"

    def test_extract_imports(self, tmp_path: Path) -> None:
        source = textwrap.dedent("""
            import os
            from pathlib import Path
        """)
        filepath = tmp_path / "test_mod.py"
        filepath.write_text(source)

        symbols, edges = _extract_python_symbols(filepath, "test_mod")
        imports = [s for s in symbols if s.kind == "import"]
        assert len(imports) == 2

    def test_extract_constants(self, tmp_path: Path) -> None:
        source = "MAX_SIZE = 100\nDEFAULT_NAME = 'test'\n"
        filepath = tmp_path / "test_mod.py"
        filepath.write_text(source)

        symbols, edges = _extract_python_symbols(filepath, "test_mod")
        vars_ = [s for s in symbols if s.kind == "variable"]
        assert len(vars_) == 2

    def test_syntax_error_file(self, tmp_path: Path) -> None:
        filepath = tmp_path / "bad.py"
        filepath.write_text("def incomplete(")

        symbols, edges = _extract_python_symbols(filepath, "bad")
        assert symbols == []


class TestPathToModule:
    """Tests for _path_to_module."""

    def test_simple(self, tmp_path: Path) -> None:
        result = _path_to_module(tmp_path / "zerg" / "config.py", tmp_path)
        assert result == "zerg.config"


class TestBuildMap:
    """Tests for build_map."""

    def test_build_map_python(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text("def foo(): pass\n")
        graph = build_map(tmp_path, languages=["python"])
        assert len(graph.modules) >= 1

    def test_build_map_skips_hidden(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.py").write_text("SECRET = 'x'\n")
        (tmp_path / "visible.py").write_text("def bar(): pass\n")

        graph = build_map(tmp_path, languages=["python"])
        module_names = list(graph.modules.keys())
        assert all(".hidden" not in m for m in module_names)
