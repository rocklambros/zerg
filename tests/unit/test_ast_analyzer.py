"""Unit tests for AST analyzer module.

Tests for pattern extraction, snippet generation, and graceful error handling.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

from zerg.ast_analyzer import (
    ASTAnalyzer,
    ClassPattern,
    CodePatterns,
    FunctionPattern,
    ImportPattern,
    analyze_directory,
)
from zerg.ast_cache import ASTCache


class TestImportPattern:
    """Tests for ImportPattern dataclass."""

    def test_regular_import(self) -> None:
        """Test regular import line generation."""
        pattern = ImportPattern(module="os", is_from_import=False)
        assert pattern.to_import_line() == "import os"

    def test_import_with_alias(self) -> None:
        """Test import with alias line generation."""
        pattern = ImportPattern(module="numpy", alias="np", is_from_import=False)
        assert pattern.to_import_line() == "import numpy as np"

    def test_from_import(self) -> None:
        """Test from import line generation."""
        pattern = ImportPattern(module="pathlib", names=["Path"], is_from_import=True)
        assert pattern.to_import_line() == "from pathlib import Path"

    def test_from_import_multiple_names(self) -> None:
        """Test from import with multiple names."""
        pattern = ImportPattern(module="typing", names=["List", "Dict", "Optional"], is_from_import=True)
        assert pattern.to_import_line() == "from typing import List, Dict, Optional"


class TestClassPattern:
    """Tests for ClassPattern dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        pattern = ClassPattern(name="TestClass")
        assert pattern.name == "TestClass"
        assert pattern.bases == []
        assert pattern.decorators == []
        assert pattern.methods == []
        assert pattern.has_init is False


class TestFunctionPattern:
    """Tests for FunctionPattern dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        pattern = FunctionPattern(name="test_func")
        assert pattern.name == "test_func"
        assert pattern.decorators == []
        assert pattern.parameters == []
        assert pattern.return_annotation is None
        assert pattern.is_async is False


class TestCodePatterns:
    """Tests for CodePatterns dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        patterns = CodePatterns()
        assert patterns.imports == []
        assert patterns.classes == []
        assert patterns.functions == []
        assert patterns.naming_convention == "snake_case"
        assert patterns.docstring_style == "google"


class TestASTAnalyzer:
    """Tests for ASTAnalyzer class."""

    @pytest.fixture
    def cache(self) -> ASTCache:
        """Create fresh AST cache for each test."""
        return ASTCache()

    @pytest.fixture
    def analyzer(self, cache: ASTCache) -> ASTAnalyzer:
        """Create analyzer with fresh cache."""
        return ASTAnalyzer(cache)

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    def test_extract_imports_simple(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test extracting simple imports."""
        code = dedent("""
            import os
            import sys
            from pathlib import Path
            from typing import List, Optional
        """).strip()

        test_file = temp_dir / "test_imports.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)

        assert len(patterns.imports) == 4

        # Check regular imports
        os_import = next(i for i in patterns.imports if i.module == "os")
        assert not os_import.is_from_import

        # Check from import
        path_import = next(i for i in patterns.imports if i.module == "pathlib")
        assert path_import.is_from_import
        assert "Path" in path_import.names

        # Check from import with multiple names
        typing_import = next(i for i in patterns.imports if i.module == "typing")
        assert "List" in typing_import.names
        assert "Optional" in typing_import.names

    def test_extract_imports_with_alias(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test extracting imports with aliases."""
        code = dedent("""
            import numpy as np
            import pandas as pd
        """).strip()

        test_file = temp_dir / "test_alias.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)

        np_import = next(i for i in patterns.imports if i.module == "numpy")
        assert np_import.alias == "np"

    def test_extract_classes(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test extracting class patterns."""
        code = dedent("""
            from abc import ABC

            class BaseClass:
                def method_a(self):
                    pass

            class ChildClass(BaseClass, ABC):
                def __init__(self):
                    pass

                def method_b(self):
                    pass
        """).strip()

        test_file = temp_dir / "test_classes.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)

        assert len(patterns.classes) == 2

        base_class = next(c for c in patterns.classes if c.name == "BaseClass")
        assert base_class.bases == []
        assert "method_a" in base_class.methods
        assert not base_class.has_init

        child_class = next(c for c in patterns.classes if c.name == "ChildClass")
        assert "BaseClass" in child_class.bases
        assert "ABC" in child_class.bases
        assert child_class.has_init
        assert "__init__" in child_class.methods
        assert "method_b" in child_class.methods

    def test_extract_classes_with_decorators(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test extracting class decorators."""
        code = dedent("""
            from dataclasses import dataclass

            @dataclass
            class DataClass:
                name: str
                value: int
        """).strip()

        test_file = temp_dir / "test_decorators.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)

        data_class = patterns.classes[0]
        assert "dataclass" in data_class.decorators

    def test_extract_functions(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test extracting function patterns."""
        code = dedent("""
            def simple_func():
                pass

            def func_with_params(a, b, c):
                pass

            def func_with_return() -> str:
                return "test"

            async def async_func():
                pass
        """).strip()

        test_file = temp_dir / "test_functions.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)

        assert len(patterns.functions) == 4

        simple = next(f for f in patterns.functions if f.name == "simple_func")
        assert simple.parameters == []
        assert simple.return_annotation is None
        assert not simple.is_async

        with_params = next(f for f in patterns.functions if f.name == "func_with_params")
        assert with_params.parameters == ["a", "b", "c"]

        with_return = next(f for f in patterns.functions if f.name == "func_with_return")
        assert with_return.return_annotation == "str"

        async_fn = next(f for f in patterns.functions if f.name == "async_func")
        assert async_fn.is_async

    def test_extract_functions_with_decorators(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test extracting function decorators."""
        code = dedent("""
            import pytest

            @pytest.fixture
            def my_fixture():
                return "fixture"

            @staticmethod
            def static_method():
                pass
        """).strip()

        test_file = temp_dir / "test_func_decorators.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)

        fixture = next(f for f in patterns.functions if f.name == "my_fixture")
        assert "fixture" in fixture.decorators

        static = next(f for f in patterns.functions if f.name == "static_method")
        assert "staticmethod" in static.decorators

    def test_detect_snake_case_naming(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test detecting snake_case naming convention."""
        code = dedent("""
            def process_data():
                pass

            def validate_input():
                pass

            def transform_output():
                pass
        """).strip()

        test_file = temp_dir / "test_snake.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)
        assert patterns.naming_convention == "snake_case"

    def test_detect_camel_case_naming(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test detecting camelCase naming convention."""
        code = dedent("""
            def processData():
                pass

            def validateInput():
                pass

            def transformOutput():
                pass
        """).strip()

        test_file = temp_dir / "test_camel.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)
        assert patterns.naming_convention == "camelCase"

    def test_detect_google_docstring_style(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test detecting Google docstring style."""
        code = dedent('''
            def example_func(param):
                """Example function.

                Args:
                    param: The parameter.

                Returns:
                    The result.
                """
                return param
        ''').strip()

        test_file = temp_dir / "test_google.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)
        assert patterns.docstring_style == "google"

    def test_detect_numpy_docstring_style(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test detecting NumPy docstring style."""
        code = dedent('''
            def example_func(param):
                """Example function.

                Parameters
                ----------
                param : str
                    The parameter.

                Returns
                -------
                str
                    The result.
                """
                return param
        ''').strip()

        test_file = temp_dir / "test_numpy.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)
        assert patterns.docstring_style == "numpy"

    def test_detect_sphinx_docstring_style(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test detecting Sphinx docstring style."""
        code = dedent('''
            def example_func(param):
                """Example function.

                :param param: The parameter.
                :return: The result.
                """
                return param
        ''').strip()

        test_file = temp_dir / "test_sphinx.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)
        assert patterns.docstring_style == "sphinx"

    def test_extract_patterns_handles_syntax_error(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test graceful handling of syntax errors."""
        code = "def broken("  # Invalid syntax

        test_file = temp_dir / "broken.py"
        test_file.write_text(code)

        patterns = analyzer.extract_patterns(test_file)
        assert patterns == CodePatterns()

    def test_extract_patterns_handles_file_not_found(self, analyzer: ASTAnalyzer) -> None:
        """Test graceful handling of missing files."""
        patterns = analyzer.extract_patterns(Path("/nonexistent/file.py"))
        assert patterns == CodePatterns()

    def test_generate_test_snippet(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test generating test snippets."""
        code = dedent("""
            def process_data(input_data):
                return input_data.upper()
        """).strip()

        target_file = temp_dir / "processor.py"
        target_file.write_text(code)

        snippet = analyzer.generate_test_snippet(target_file, "process_data")

        assert "def test_process_data" in snippet
        assert "from processor import process_data" in snippet
        assert "assert" in snippet

    def test_generate_test_snippet_with_pytest_patterns(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test generating test snippets using existing pytest patterns."""
        # Create target file
        target_code = "def my_function(): pass"
        target_file = temp_dir / "target.py"
        target_file.write_text(target_code)

        # Create test directory with pytest patterns
        test_dir = temp_dir / "tests"
        test_dir.mkdir()
        test_code = dedent("""
            import pytest

            def test_existing():
                assert True
        """).strip()
        (test_dir / "test_existing.py").write_text(test_code)

        snippet = analyzer.generate_test_snippet(target_file, "my_function", test_dir)

        assert "import pytest" in snippet
        assert "def test_my_function" in snippet

    def test_generate_impl_snippet_basic(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test generating basic implementation snippet."""
        target_file = temp_dir / "new_module.py"

        snippet = analyzer.generate_impl_snippet(target_file)

        assert '"""' in snippet
        assert "from __future__ import annotations" in snippet
        assert "def" in snippet or "class" in snippet

    def test_generate_impl_snippet_with_reference(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test generating implementation snippet based on reference files."""
        # Create reference file
        ref_code = dedent("""
            from dataclasses import dataclass
            from pathlib import Path

            class BaseProcessor:
                def process(self):
                    pass
        """).strip()
        ref_file = temp_dir / "reference.py"
        ref_file.write_text(ref_code)

        target_file = temp_dir / "new_processor.py"

        snippet = analyzer.generate_impl_snippet(target_file, based_on=[ref_file])

        assert "from __future__ import annotations" in snippet
        assert "class NewProcessor" in snippet or "def" in snippet

    def test_generate_impl_snippet_inherits_patterns(self, analyzer: ASTAnalyzer, temp_dir: Path) -> None:
        """Test that impl snippet uses patterns from reference."""
        # Create multiple reference files with common base class
        ref1 = temp_dir / "handler_a.py"
        ref1.write_text("class HandlerA(BaseHandler): pass")

        ref2 = temp_dir / "handler_b.py"
        ref2.write_text("class HandlerB(BaseHandler): pass")

        target_file = temp_dir / "handler_c.py"

        snippet = analyzer.generate_impl_snippet(target_file, based_on=[ref1, ref2])

        # Should detect BaseHandler as common base
        assert "BaseHandler" in snippet

    def test_to_pascal_case(self, analyzer: ASTAnalyzer) -> None:
        """Test snake_case to PascalCase conversion."""
        assert analyzer._to_pascal_case("hello_world") == "HelloWorld"
        assert analyzer._to_pascal_case("ast_analyzer") == "AstAnalyzer"
        assert analyzer._to_pascal_case("simple") == "Simple"

    def test_to_camel_case(self, analyzer: ASTAnalyzer) -> None:
        """Test snake_case to camelCase conversion."""
        assert analyzer._to_camel_case("hello_world") == "helloWorld"
        assert analyzer._to_camel_case("ast_analyzer") == "astAnalyzer"
        assert analyzer._to_camel_case("simple") == "simple"


class TestAnalyzeDirectory:
    """Tests for analyze_directory utility function."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create temporary directory with test files."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)

            # Create some Python files
            (base / "module_a.py").write_text("def func_a(): pass")
            (base / "module_b.py").write_text("class ClassB: pass")

            # Create subdirectory with files
            subdir = base / "subpackage"
            subdir.mkdir()
            (subdir / "module_c.py").write_text("import os")

            # Create __pycache__ that should be ignored
            pycache = base / "__pycache__"
            pycache.mkdir()
            (pycache / "module.cpython-311.pyc").write_text("binary")

            yield base

    def test_analyzes_all_files(self, temp_dir: Path) -> None:
        """Test that all Python files are analyzed."""
        cache = ASTCache()
        results = analyze_directory(temp_dir, cache)

        # Should find 3 Python files (excluding __pycache__)
        py_files = [p for p in results.keys() if p.suffix == ".py"]
        assert len(py_files) == 3

    def test_excludes_pycache(self, temp_dir: Path) -> None:
        """Test that __pycache__ is excluded."""
        cache = ASTCache()
        results = analyze_directory(temp_dir, cache)

        pycache_files = [p for p in results.keys() if "__pycache__" in str(p)]
        assert len(pycache_files) == 0

    def test_extracts_patterns(self, temp_dir: Path) -> None:
        """Test that patterns are extracted correctly."""
        cache = ASTCache()
        results = analyze_directory(temp_dir, cache)

        # Find module_a.py result
        module_a = next(p for p in results.keys() if p.name == "module_a.py")
        patterns = results[module_a]

        assert any(f.name == "func_a" for f in patterns.functions)

    def test_custom_file_pattern(self, temp_dir: Path) -> None:
        """Test custom file pattern matching."""
        # Create a .pyi file
        (temp_dir / "stubs.pyi").write_text("def typed_func() -> int: ...")

        cache = ASTCache()

        # Default pattern should not include .pyi
        py_results = analyze_directory(temp_dir, cache, "*.py")
        pyi_in_py = any(p.suffix == ".pyi" for p in py_results.keys())
        assert not pyi_in_py

        # Custom pattern should include .pyi
        pyi_results = analyze_directory(temp_dir, cache, "*.pyi")
        assert any(p.suffix == ".pyi" for p in pyi_results.keys())
