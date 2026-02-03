"""Comprehensive tests for zerg.doc_engine.extractor and zerg.doc_engine.detector.

Targets all functions, branches, and edge cases to achieve >=80% coverage.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.doc_engine.detector import (
    _API_MARKERS,
    _CONFIG_STEMS,
    _TYPES_STEMS,
    ComponentDetector,
    ComponentType,
)
from zerg.doc_engine.extractor import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    SymbolExtractor,
    SymbolTable,
    _extract_args,
    _extract_decorators,
    _extract_docstring,
    _extract_function,
    _extract_return_type,
    _is_constant_name,
    _is_type_alias,
    _unparse_node,
)

# ======================================================================
# extractor.py - _unparse_node
# ======================================================================


class TestUnparseNode:
    def test_simple_name_node(self) -> None:
        node = ast.Name(id="int", ctx=ast.Load())
        assert _unparse_node(node) == "int"

    def test_attribute_node(self) -> None:
        source = "os.path"
        tree = ast.parse(source, mode="eval")
        assert _unparse_node(tree.body) == "os.path"

    def test_exception_returns_unknown(self) -> None:
        """When ast.unparse fails, return '<unknown>'."""
        bad_node = MagicMock(spec=ast.expr)
        with patch("zerg.doc_engine.extractor.ast.unparse", side_effect=Exception("fail")):
            result = _unparse_node(bad_node)
        assert result == "<unknown>"


# ======================================================================
# extractor.py - _extract_docstring
# ======================================================================


class TestExtractDocstring:
    def test_module_docstring(self) -> None:
        tree = ast.parse('"""Module doc."""\nx = 1\n')
        assert _extract_docstring(tree) == "Module doc."

    def test_class_docstring(self) -> None:
        tree = ast.parse('class Foo:\n    """Foo doc."""\n    pass\n')
        cls_node = tree.body[0]
        assert _extract_docstring(cls_node) == "Foo doc."

    def test_function_docstring(self) -> None:
        tree = ast.parse('def bar():\n    """Bar doc."""\n    pass\n')
        func_node = tree.body[0]
        assert _extract_docstring(func_node) == "Bar doc."

    def test_async_function_docstring(self) -> None:
        tree = ast.parse('async def baz():\n    """Baz doc."""\n    pass\n')
        func_node = tree.body[0]
        assert _extract_docstring(func_node) == "Baz doc."

    def test_no_docstring_returns_none(self) -> None:
        tree = ast.parse("x = 1\n")
        assert _extract_docstring(tree) is None

    def test_non_string_first_expr_returns_none(self) -> None:
        tree = ast.parse("42\nx = 1\n")
        # First statement is Expr(value=Constant(42)) -- an int, not a str
        assert _extract_docstring(tree) is None

    def test_empty_body_returns_none(self) -> None:
        # A module with empty body
        tree = ast.parse("")
        assert _extract_docstring(tree) is None

    def test_non_supported_node_returns_none(self) -> None:
        """Nodes like ast.Assign should return None."""
        tree = ast.parse("x = 1\n")
        assign_node = tree.body[0]
        assert _extract_docstring(assign_node) is None

    def test_function_without_docstring(self) -> None:
        tree = ast.parse("def foo():\n    return 1\n")
        func_node = tree.body[0]
        assert _extract_docstring(func_node) is None


# ======================================================================
# extractor.py - _extract_decorators
# ======================================================================


class TestExtractDecorators:
    def test_no_decorators(self) -> None:
        tree = ast.parse("class Foo:\n    pass\n")
        cls = tree.body[0]
        assert _extract_decorators(cls) == []

    def test_single_decorator(self) -> None:
        tree = ast.parse("@dataclass\nclass Foo:\n    pass\n")
        cls = tree.body[0]
        decs = _extract_decorators(cls)
        assert decs == ["dataclass"]

    def test_multiple_decorators(self) -> None:
        source = "@decorator_a\n@decorator_b\ndef foo():\n    pass\n"
        tree = ast.parse(source)
        func = tree.body[0]
        decs = _extract_decorators(func)
        assert len(decs) == 2
        assert "decorator_a" in decs
        assert "decorator_b" in decs

    def test_decorator_with_args(self) -> None:
        source = '@app.route("/health")\ndef health():\n    pass\n'
        tree = ast.parse(source)
        func = tree.body[0]
        decs = _extract_decorators(func)
        assert len(decs) == 1
        assert "app.route" in decs[0]


# ======================================================================
# extractor.py - _extract_args
# ======================================================================


class TestExtractArgs:
    def test_no_args(self) -> None:
        tree = ast.parse("def foo():\n    pass\n")
        func = tree.body[0]
        assert _extract_args(func) == []

    def test_simple_args(self) -> None:
        tree = ast.parse("def foo(a, b):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        assert args == ["a", "b"]

    def test_annotated_args(self) -> None:
        tree = ast.parse("def foo(a: int, b: str):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        assert "a: int" in args
        assert "b: str" in args

    def test_vararg_without_annotation(self) -> None:
        tree = ast.parse("def foo(*args):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        assert "*args" in args

    def test_vararg_with_annotation(self) -> None:
        tree = ast.parse("def foo(*args: int):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        assert "*args: int" in args

    def test_kwarg_without_annotation(self) -> None:
        tree = ast.parse("def foo(**kwargs):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        assert "**kwargs" in args

    def test_kwarg_with_annotation(self) -> None:
        tree = ast.parse("def foo(**kwargs: str):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        assert "**kwargs: str" in args

    def test_kwonly_args(self) -> None:
        tree = ast.parse("def foo(*, key: int):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        assert "key: int" in args

    def test_kwonly_args_without_annotation(self) -> None:
        tree = ast.parse("def foo(*, key):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        assert "key" in args

    def test_posonly_args(self) -> None:
        tree = ast.parse("def foo(a: int, /):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        # posonlyargs come after regular args in the function
        assert any("a: int" in a for a in args)

    def test_posonly_args_without_annotation(self) -> None:
        tree = ast.parse("def foo(a, /):\n    pass\n")
        func = tree.body[0]
        args = _extract_args(func)
        assert "a" in args

    def test_mixed_args(self) -> None:
        source = "def foo(a: int, /, b, *args: str, key: bool = True, **kw):\n    pass\n"
        tree = ast.parse(source)
        func = tree.body[0]
        args = _extract_args(func)
        assert len(args) >= 4  # a, b, *args, key, **kw


# ======================================================================
# extractor.py - _extract_return_type
# ======================================================================


class TestExtractReturnType:
    def test_with_return_type(self) -> None:
        tree = ast.parse("def foo() -> int:\n    pass\n")
        func = tree.body[0]
        assert _extract_return_type(func) == "int"

    def test_without_return_type(self) -> None:
        tree = ast.parse("def foo():\n    pass\n")
        func = tree.body[0]
        assert _extract_return_type(func) is None

    def test_complex_return_type(self) -> None:
        tree = ast.parse("def foo() -> dict[str, list[int]]:\n    pass\n")
        func = tree.body[0]
        result = _extract_return_type(func)
        assert result is not None
        assert "dict" in result


# ======================================================================
# extractor.py - _extract_function
# ======================================================================


class TestExtractFunction:
    def test_sync_function(self) -> None:
        tree = ast.parse('def foo(x: int) -> str:\n    """Doc."""\n    pass\n')
        func_node = tree.body[0]
        info = _extract_function(func_node, is_method=False)
        assert info.name == "foo"
        assert info.is_async is False
        assert info.is_method is False
        assert info.docstring == "Doc."
        assert info.return_type == "str"

    def test_async_function(self) -> None:
        tree = ast.parse("async def bar():\n    pass\n")
        func_node = tree.body[0]
        info = _extract_function(func_node, is_method=False)
        assert info.is_async is True

    def test_method_flag(self) -> None:
        tree = ast.parse("def baz(self):\n    pass\n")
        func_node = tree.body[0]
        info = _extract_function(func_node, is_method=True)
        assert info.is_method is True

    def test_no_docstring(self) -> None:
        tree = ast.parse("def nodoc():\n    return 1\n")
        func_node = tree.body[0]
        info = _extract_function(func_node)
        assert info.docstring is None

    def test_decorated_function(self) -> None:
        tree = ast.parse("@staticmethod\ndef s():\n    pass\n")
        func_node = tree.body[0]
        info = _extract_function(func_node)
        assert "staticmethod" in info.decorators


# ======================================================================
# extractor.py - _is_constant_name
# ======================================================================


class TestIsConstantName:
    def test_all_upper(self) -> None:
        assert _is_constant_name("MAX_RETRIES") is True

    def test_single_upper(self) -> None:
        assert _is_constant_name("X") is True

    def test_lowercase(self) -> None:
        assert _is_constant_name("max_retries") is False

    def test_mixed_case(self) -> None:
        assert _is_constant_name("MaxRetries") is False

    def test_underscore_prefix(self) -> None:
        assert _is_constant_name("_PRIVATE") is False

    def test_dunder(self) -> None:
        assert _is_constant_name("__ALL__") is False

    def test_empty_string(self) -> None:
        assert _is_constant_name("") is False


# ======================================================================
# extractor.py - _is_type_alias
# ======================================================================


class TestIsTypeAlias:
    def test_type_alias_annotation(self) -> None:
        tree = ast.parse("from typing import TypeAlias\nMyType: TypeAlias = dict[str, int]\n")
        stmt = tree.body[1]  # AnnAssign
        assert _is_type_alias(stmt) == "MyType"

    def test_non_type_alias_annotation(self) -> None:
        tree = ast.parse("x: int = 5\n")
        stmt = tree.body[0]
        assert _is_type_alias(stmt) is None

    def test_assign_not_annassign(self) -> None:
        tree = ast.parse("x = 5\n")
        stmt = tree.body[0]
        assert _is_type_alias(stmt) is None

    def test_annassign_non_name_target(self) -> None:
        """AnnAssign where target is not ast.Name (e.g., attribute)."""
        tree = ast.parse("self.x: int = 5\n")
        stmt = tree.body[0]
        # This is an AnnAssign with target=Attribute, not Name
        assert _is_type_alias(stmt) is None


# ======================================================================
# extractor.py - SymbolExtractor
# ======================================================================


class TestSymbolExtractorComprehensive:
    @pytest.fixture
    def extractor(self) -> SymbolExtractor:
        return SymbolExtractor()

    def test_extract_regular_import(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("import os\nimport sys\n", encoding="utf-8")
        table = extractor.extract(src)
        assert len(table.imports) == 2
        for imp in table.imports:
            assert imp.is_from is False

    def test_extract_import_with_asname(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("import numpy as np\n", encoding="utf-8")
        table = extractor.extract(src)
        assert len(table.imports) == 1
        assert table.imports[0].names == ["np"]
        assert table.imports[0].module == "numpy"

    def test_extract_from_import(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("from os.path import join, exists\n", encoding="utf-8")
        table = extractor.extract(src)
        assert len(table.imports) == 1
        assert table.imports[0].is_from is True
        assert table.imports[0].module == "os.path"
        assert "join" in table.imports[0].names
        assert "exists" in table.imports[0].names

    def test_extract_from_import_with_asname(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("from os.path import join as j\n", encoding="utf-8")
        table = extractor.extract(src)
        assert table.imports[0].names == ["j"]

    def test_extract_from_import_no_module(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        """Relative import like 'from . import foo' has module=None in AST."""
        src = tmp_path / "mod.py"
        src.write_text("from . import foo\n", encoding="utf-8")
        table = extractor.extract(src)
        assert table.imports[0].module == ""
        assert table.imports[0].is_from is True

    def test_extract_multiple_constants(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("MAX = 10\nMIN = 0\nlower = 5\n", encoding="utf-8")
        table = extractor.extract(src)
        assert "MAX" in table.constants
        assert "MIN" in table.constants
        assert "lower" not in table.constants

    def test_extract_annotated_constant(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        """AnnAssign with uppercase name that is not a TypeAlias -> constant."""
        src = tmp_path / "mod.py"
        src.write_text("TIMEOUT: int = 30\n", encoding="utf-8")
        table = extractor.extract(src)
        assert "TIMEOUT" in table.constants

    def test_extract_annotated_non_constant(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("timeout: int = 30\n", encoding="utf-8")
        table = extractor.extract(src)
        assert "timeout" not in table.constants

    def test_extract_class_with_bases(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("class Dog(Animal, Pet):\n    pass\n", encoding="utf-8")
        table = extractor.extract(src)
        assert len(table.classes) == 1
        assert "Animal" in table.classes[0].bases
        assert "Pet" in table.classes[0].bases

    def test_extract_class_no_bases(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("class Bare:\n    pass\n", encoding="utf-8")
        table = extractor.extract(src)
        assert table.classes[0].bases == []

    def test_extract_class_no_docstring(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("class NoDocs:\n    x = 1\n", encoding="utf-8")
        table = extractor.extract(src)
        assert table.classes[0].docstring is None

    def test_extract_class_with_async_method(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text(
            "class Svc:\n    async def run(self) -> None:\n        pass\n",
            encoding="utf-8",
        )
        table = extractor.extract(src)
        assert len(table.classes[0].methods) == 1
        method = table.classes[0].methods[0]
        assert method.is_async is True
        assert method.is_method is True

    def test_extract_class_with_multiple_methods(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text(
            "class Svc:\n"
            "    def a(self):\n        pass\n"
            "    def b(self):\n        pass\n"
            "    async def c(self):\n        pass\n",
            encoding="utf-8",
        )
        table = extractor.extract(src)
        method_names = [m.name for m in table.classes[0].methods]
        assert method_names == ["a", "b", "c"]

    def test_extract_class_non_method_body(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        """Class body with non-function statements should not produce methods."""
        src = tmp_path / "mod.py"
        src.write_text(
            "class Cfg:\n    X = 1\n    Y = 2\n",
            encoding="utf-8",
        )
        table = extractor.extract(src)
        assert table.classes[0].methods == []

    def test_extract_async_top_level_function(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("async def main():\n    pass\n", encoding="utf-8")
        table = extractor.extract(src)
        assert len(table.functions) == 1
        assert table.functions[0].is_async is True
        assert table.functions[0].is_method is False

    def test_extract_no_module_docstring(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("x = 1\n", encoding="utf-8")
        table = extractor.extract(src)
        assert table.module_docstring is None

    def test_extract_syntax_error(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "bad.py"
        src.write_text("def (:\n", encoding="utf-8")
        with pytest.raises(SyntaxError):
            extractor.extract(src)

    def test_extract_missing_file(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "nope.py"
        with pytest.raises(OSError):
            extractor.extract(src)

    def test_extract_multiple_type_aliases(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text(
            "from typing import TypeAlias\nA: TypeAlias = int\nB: TypeAlias = str\n",
            encoding="utf-8",
        )
        table = extractor.extract(src)
        assert "A" in table.type_aliases
        assert "B" in table.type_aliases

    def test_extract_class_with_decorators(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text(
            "from dataclasses import dataclass\n\n@dataclass\nclass Pt:\n    x: int\n",
            encoding="utf-8",
        )
        table = extractor.extract(src)
        assert "dataclass" in table.classes[0].decorators

    def test_extract_function_with_no_return_type(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("def noop():\n    pass\n", encoding="utf-8")
        table = extractor.extract(src)
        assert table.functions[0].return_type is None

    def test_symbol_table_path(self, extractor: SymbolExtractor, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text("", encoding="utf-8")
        table = extractor.extract(src)
        assert table.path == src


# ======================================================================
# extractor.py - dataclass constructors
# ======================================================================


class TestDataclasses:
    def test_function_info_defaults(self) -> None:
        info = FunctionInfo(
            name="f",
            lineno=1,
            docstring=None,
            args=[],
            return_type=None,
            decorators=[],
        )
        assert info.is_method is False
        assert info.is_async is False

    def test_class_info(self) -> None:
        info = ClassInfo(
            name="C",
            lineno=1,
            docstring="Doc.",
            bases=["Base"],
            methods=[],
            decorators=["dc"],
        )
        assert info.name == "C"
        assert info.bases == ["Base"]

    def test_import_info(self) -> None:
        info = ImportInfo(module="os", names=["path"], is_from=True)
        assert info.is_from is True

    def test_symbol_table(self, tmp_path: Path) -> None:
        table = SymbolTable(
            path=tmp_path / "x.py",
            module_docstring="doc",
            classes=[],
            functions=[],
            imports=[],
            constants=["A"],
            type_aliases=["B"],
        )
        assert table.module_docstring == "doc"
        assert table.constants == ["A"]
        assert table.type_aliases == ["B"]


# ======================================================================
# detector.py - ComponentType enum
# ======================================================================


class TestComponentType:
    def test_all_values(self) -> None:
        assert ComponentType.MODULE.value == "module"
        assert ComponentType.COMMAND.value == "command"
        assert ComponentType.CONFIG.value == "config"
        assert ComponentType.TYPES.value == "types"
        assert ComponentType.API.value == "api"


# ======================================================================
# detector.py - ComponentDetector
# ======================================================================


class TestComponentDetectorComprehensive:
    @pytest.fixture
    def detector(self) -> ComponentDetector:
        return ComponentDetector()

    # --- _is_command_file ---

    def test_command_md_in_data_commands(self, detector: ComponentDetector, tmp_path: Path) -> None:
        cmd_dir = tmp_path / "data" / "commands"
        cmd_dir.mkdir(parents=True)
        md = cmd_dir / "init.md"
        md.write_text("# Init\n", encoding="utf-8")
        assert detector.detect(md) == ComponentType.COMMAND

    def test_md_not_in_data_commands(self, detector: ComponentDetector, tmp_path: Path) -> None:
        md = tmp_path / "readme.md"
        md.write_text("# Readme\n", encoding="utf-8")
        assert detector.detect(md) != ComponentType.COMMAND

    def test_non_md_in_data_commands(self, detector: ComponentDetector, tmp_path: Path) -> None:
        cmd_dir = tmp_path / "data" / "commands"
        cmd_dir.mkdir(parents=True)
        txt = cmd_dir / "notes.txt"
        txt.write_text("notes\n", encoding="utf-8")
        assert detector.detect(txt) != ComponentType.COMMAND

    def test_md_in_only_data_dir(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """Markdown in data/ but not data/commands/ is not a COMMAND."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        md = data_dir / "readme.md"
        md.write_text("# Hi\n", encoding="utf-8")
        assert detector.detect(md) != ComponentType.COMMAND

    # --- _is_config_file ---

    def test_yaml_is_config(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "app.yaml"
        f.write_text("key: val\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.CONFIG

    def test_yml_is_config(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "app.yml"
        f.write_text("key: val\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.CONFIG

    def test_toml_is_config(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "pyproject.toml"
        f.write_text("[tool]\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.CONFIG

    def test_ini_is_config(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "setup.ini"
        f.write_text("[section]\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.CONFIG

    def test_cfg_is_config(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "setup.cfg"
        f.write_text("[section]\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.CONFIG

    def test_py_with_config_stem(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "configuration.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.CONFIG

    def test_py_with_settings_stem(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "settings.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.CONFIG

    def test_py_without_config_stem(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "utils.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert detector.detect(f) != ComponentType.CONFIG

    # --- _is_types_file ---

    def test_types_stem(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "types.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.TYPES

    def test_constants_stem(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "constants.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.TYPES

    def test_enums_stem(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "enums.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.TYPES

    def test_types_stem_non_py(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """Non-.py file with types stem should still match by stem."""
        f = tmp_path / "types.ts"
        f.write_text("export type X = string;\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.TYPES

    def test_types_by_ast_majority_classes(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """File with >50% class defs detected as TYPES."""
        f = tmp_path / "models.py"
        f.write_text(
            "class A:\n    pass\nclass B:\n    pass\nclass C:\n    pass\n",
            encoding="utf-8",
        )
        assert detector.detect(f) == ComponentType.TYPES

    def test_types_by_ast_not_majority(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """File with <=50% class defs NOT detected as TYPES."""
        f = tmp_path / "mixed.py"
        f.write_text(
            "class A:\n    pass\nx = 1\ny = 2\nz = 3\n",
            encoding="utf-8",
        )
        # 1 class / 4 total = 25%, should not be TYPES
        assert detector.detect(f) != ComponentType.TYPES

    # --- _ast_dominated_by_type_defs ---

    def test_ast_dominated_syntax_error(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """SyntaxError during AST parse returns False."""
        f = tmp_path / "bad.py"
        f.write_text("def (:\n", encoding="utf-8")
        assert ComponentDetector._ast_dominated_by_type_defs(f) is False

    def test_ast_dominated_os_error(self, tmp_path: Path) -> None:
        """Missing file returns False."""
        f = tmp_path / "nope.py"
        assert ComponentDetector._ast_dominated_by_type_defs(f) is False

    def test_ast_dominated_empty_top_level(self, tmp_path: Path) -> None:
        """File with only imports (no top-level after filtering) returns False."""
        f = tmp_path / "imports_only.py"
        f.write_text("import os\nfrom sys import argv\n", encoding="utf-8")
        assert ComponentDetector._ast_dominated_by_type_defs(f) is False

    def test_ast_dominated_exactly_half(self, tmp_path: Path) -> None:
        """Exactly 50% class defs should return False (needs >50%)."""
        f = tmp_path / "half.py"
        f.write_text("class A:\n    pass\nx = 1\n", encoding="utf-8")
        assert ComponentDetector._ast_dominated_by_type_defs(f) is False

    # --- _is_api_file ---

    def test_api_flask_route(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "api.py"
        f.write_text('@app.route("/health")\ndef health():\n    return "ok"\n', encoding="utf-8")
        assert detector.detect(f) == ComponentType.API

    def test_api_click_command(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "cli.py"
        f.write_text("@click.command\ndef run():\n    pass\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.API

    def test_api_click_group(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "cli.py"
        f.write_text("@click.group\ndef main():\n    pass\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.API

    def test_api_router(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "routes.py"
        f.write_text("@router.get\ndef items():\n    pass\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.API

    def test_api_blueprint(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "bp.py"
        f.write_text("@blueprint.route\ndef view():\n    pass\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.API

    def test_api_router_class(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "main.py"
        f.write_text("router = APIRouter(prefix='/v1')\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.API

    def test_api_non_py_not_detected(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "routes.txt"
        f.write_text("@app.route\n", encoding="utf-8")
        assert detector.detect(f) != ComponentType.API

    def test_api_os_error(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """When the file cannot be read, _is_api_file returns False."""
        f = tmp_path / "unreadable.py"
        # Don't create the file so read_text will fail
        assert ComponentDetector._is_api_file(f) is False

    # --- detect (fallthrough to MODULE) ---

    def test_detect_plain_py_is_module(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "utils.py"
        f.write_text("def helper():\n    pass\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.MODULE

    def test_detect_unknown_extension_is_module(self, detector: ComponentDetector, tmp_path: Path) -> None:
        f = tmp_path / "data.dat"
        f.write_text("binary-ish\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.MODULE

    # --- detect_all ---

    def test_detect_all_basic(self, detector: ComponentDetector, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "b.yaml").write_text("k: v\n", encoding="utf-8")
        results = detector.detect_all(tmp_path)
        assert len(results) == 2

    def test_detect_all_skips_hidden(self, detector: ComponentDetector, tmp_path: Path) -> None:
        (tmp_path / ".hidden.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "visible.py").write_text("x = 1\n", encoding="utf-8")
        results = detector.detect_all(tmp_path)
        paths = list(results.keys())
        assert all(".hidden" not in str(p) for p in paths)
        assert len(results) == 1

    def test_detect_all_skips_pycache(self, detector: ComponentDetector, tmp_path: Path) -> None:
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "mod.pyc").write_text("", encoding="utf-8")
        (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
        results = detector.detect_all(tmp_path)
        assert len(results) == 1

    def test_detect_all_skips_directories(self, detector: ComponentDetector, tmp_path: Path) -> None:
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "mod.py").write_text("x = 1\n", encoding="utf-8")
        results = detector.detect_all(tmp_path)
        # subdir itself is skipped (is_dir), but subdir/mod.py is included
        assert any("mod.py" in str(p) for p in results)

    def test_detect_all_exception_fallback_to_module(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """If detect() raises for a file, detect_all falls back to MODULE."""
        f = tmp_path / "weird.py"
        f.write_text("x = 1\n", encoding="utf-8")

        with patch.object(
            ComponentDetector,
            "detect",
            side_effect=RuntimeError("unexpected"),
        ):
            results = detector.detect_all(tmp_path)
        assert len(results) == 1
        assert list(results.values())[0] == ComponentType.MODULE

    def test_detect_all_empty_directory(self, detector: ComponentDetector, tmp_path: Path) -> None:
        results = detector.detect_all(tmp_path)
        assert results == {}

    def test_detect_all_recursive(self, detector: ComponentDetector, tmp_path: Path) -> None:
        sub = tmp_path / "pkg" / "sub"
        sub.mkdir(parents=True)
        (sub / "deep.py").write_text("x = 1\n", encoding="utf-8")
        results = detector.detect_all(tmp_path)
        assert len(results) == 1

    # --- Priority tests: command > config > types > api > module ---

    def test_priority_command_over_config(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """A .md file in data/commands/ with 'config' in name is still COMMAND."""
        cmd_dir = tmp_path / "data" / "commands"
        cmd_dir.mkdir(parents=True)
        md = cmd_dir / "config.md"
        md.write_text("# Config command\n", encoding="utf-8")
        assert detector.detect(md) == ComponentType.COMMAND

    def test_config_takes_priority_over_types(self, detector: ComponentDetector, tmp_path: Path) -> None:
        """A .yaml file named 'types.yaml' is CONFIG (yaml extension wins)."""
        f = tmp_path / "types.yaml"
        f.write_text("key: val\n", encoding="utf-8")
        assert detector.detect(f) == ComponentType.CONFIG


# ======================================================================
# detector.py - module-level constants
# ======================================================================


class TestDetectorConstants:
    def test_api_markers_are_strings(self) -> None:
        assert all(isinstance(m, str) for m in _API_MARKERS)

    def test_config_stems(self) -> None:
        assert "config" in _CONFIG_STEMS
        assert "settings" in _CONFIG_STEMS
        assert "configuration" in _CONFIG_STEMS

    def test_types_stems(self) -> None:
        assert "types" in _TYPES_STEMS
        assert "constants" in _TYPES_STEMS
        assert "enums" in _TYPES_STEMS
