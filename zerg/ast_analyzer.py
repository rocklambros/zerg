"""AST analysis for code pattern extraction and snippet generation.

Provides AST-based analysis to extract codebase patterns like imports, base classes,
and naming conventions. Used by StepGenerator to create realistic code snippets
matching project style for high-detail task planning.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zerg.ast_cache import ASTCache


@dataclass
class ImportPattern:
    """Represents an import pattern extracted from code."""

    module: str
    names: list[str] = field(default_factory=list)
    is_from_import: bool = False
    alias: str | None = None

    def to_import_line(self) -> str:
        """Generate import statement from pattern."""
        if self.is_from_import:
            names = ", ".join(self.names)
            return f"from {self.module} import {names}"
        elif self.alias:
            return f"import {self.module} as {self.alias}"
        else:
            return f"import {self.module}"


@dataclass
class ClassPattern:
    """Represents a class pattern extracted from code."""

    name: str
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    has_init: bool = False


@dataclass
class FunctionPattern:
    """Represents a function pattern extracted from code."""

    name: str
    decorators: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    return_annotation: str | None = None
    is_async: bool = False


@dataclass
class CodePatterns:
    """Collection of patterns extracted from a codebase."""

    imports: list[ImportPattern] = field(default_factory=list)
    classes: list[ClassPattern] = field(default_factory=list)
    functions: list[FunctionPattern] = field(default_factory=list)
    naming_convention: str = "snake_case"  # snake_case, camelCase, PascalCase
    docstring_style: str = "google"  # google, numpy, sphinx


class ASTAnalyzer:
    """Analyze Python AST to extract code patterns for snippet generation.

    Uses ASTCache for efficient parsing and caching of AST trees.
    """

    def __init__(self, cache: ASTCache) -> None:
        """Initialize analyzer with AST cache.

        Args:
            cache: ASTCache instance for parsing and caching ASTs.
        """
        self.cache = cache

    def extract_patterns(self, file_path: Path) -> CodePatterns:
        """Extract import patterns, base classes, and utilities from a file.

        Args:
            file_path: Path to Python file to analyze.

        Returns:
            CodePatterns containing all extracted patterns.
        """
        try:
            tree = self.cache.parse(file_path)
        except (SyntaxError, FileNotFoundError, OSError):
            return CodePatterns()

        patterns = CodePatterns()
        patterns.imports = self._extract_imports(tree)
        patterns.classes = self._extract_classes(tree)
        patterns.functions = self._extract_functions(tree)
        patterns.naming_convention = self._detect_naming_convention(tree)
        patterns.docstring_style = self._detect_docstring_style(tree)

        return patterns

    def _extract_imports(self, tree: ast.Module) -> list[ImportPattern]:
        """Extract import patterns from AST."""
        imports: list[ImportPattern] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        ImportPattern(
                            module=alias.name,
                            is_from_import=False,
                            alias=alias.asname,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names = [alias.name for alias in node.names]
                    imports.append(
                        ImportPattern(
                            module=node.module,
                            names=names,
                            is_from_import=True,
                        )
                    )

        return imports

    def _extract_classes(self, tree: ast.Module) -> list[ClassPattern]:
        """Extract class patterns from AST."""
        classes: list[ClassPattern] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(f"{self._get_attribute_name(base)}")

                decorators = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name):
                        decorators.append(dec.id)
                    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                        decorators.append(dec.func.id)

                methods = []
                has_init = False
                for item in node.body:
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        methods.append(item.name)
                        if item.name == "__init__":
                            has_init = True

                classes.append(
                    ClassPattern(
                        name=node.name,
                        bases=bases,
                        decorators=decorators,
                        methods=methods,
                        has_init=has_init,
                    )
                )

        return classes

    def _extract_functions(self, tree: ast.Module) -> list[FunctionPattern]:
        """Extract top-level function patterns from AST."""
        functions: list[FunctionPattern] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                decorators = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name):
                        decorators.append(dec.id)
                    elif isinstance(dec, ast.Attribute):
                        # Handle decorators like pytest.fixture
                        decorators.append(dec.attr)
                    elif isinstance(dec, ast.Call):
                        # Handle decorators like @decorator() or @module.decorator()
                        if isinstance(dec.func, ast.Name):
                            decorators.append(dec.func.id)
                        elif isinstance(dec.func, ast.Attribute):
                            decorators.append(dec.func.attr)

                params = []
                for arg in node.args.args:
                    if arg.arg != "self":
                        params.append(arg.arg)

                return_annotation = None
                if node.returns:
                    return_annotation = self._get_annotation_string(node.returns)

                functions.append(
                    FunctionPattern(
                        name=node.name,
                        decorators=decorators,
                        parameters=params,
                        return_annotation=return_annotation,
                        is_async=isinstance(node, ast.AsyncFunctionDef),
                    )
                )

        return functions

    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """Get full dotted name from Attribute node."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _get_annotation_string(self, node: ast.expr) -> str:
        """Get string representation of type annotation."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                return f"{node.value.id}[...]"
        return "Any"

    def _detect_naming_convention(self, tree: ast.Module) -> str:
        """Detect naming convention from function and variable names."""
        snake_count = 0
        camel_count = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                name = node.name
                if not name.startswith("_"):
                    if "_" in name:
                        snake_count += 1
                    elif name[0].islower() and any(c.isupper() for c in name[1:]):
                        camel_count += 1

        if snake_count > camel_count:
            return "snake_case"
        elif camel_count > snake_count:
            return "camelCase"
        return "snake_case"

    def _detect_docstring_style(self, tree: ast.Module) -> str:
        """Detect docstring style from existing docstrings."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                docstring = ast.get_docstring(node)
                if docstring:
                    if "Args:" in docstring or "Returns:" in docstring:
                        return "google"
                    elif "Parameters" in docstring and "----------" in docstring:
                        return "numpy"
                    elif ":param" in docstring or ":return:" in docstring:
                        return "sphinx"
        return "google"

    def generate_test_snippet(
        self,
        target_file: Path,
        function_name: str,
        test_dir: Path | None = None,
    ) -> str:
        """Generate test snippet matching project conventions.

        Args:
            target_file: Path to the file containing the function to test.
            function_name: Name of the function to generate test for.
            test_dir: Optional path to test directory for pattern extraction.

        Returns:
            Generated test function code as string.
        """
        patterns = self.extract_patterns(target_file)

        # Find existing test patterns if test_dir provided
        test_patterns = CodePatterns()
        if test_dir and test_dir.exists():
            test_files = list(test_dir.glob("test_*.py"))
            if test_files:
                test_patterns = self.extract_patterns(test_files[0])

        # Determine test framework from imports
        uses_pytest = any(imp.module == "pytest" or "pytest" in imp.names for imp in test_patterns.imports)

        # Build import section
        module_name = target_file.stem
        imports = [f"from {module_name} import {function_name}"]
        if uses_pytest:
            imports.insert(0, "import pytest")

        # Build test function
        test_name = f"test_{function_name}"
        if patterns.naming_convention == "camelCase":
            # Convert to camelCase for test
            test_name = f"test{function_name[0].upper()}{function_name[1:]}"

        # Build docstring
        docstring = self._generate_docstring(f"Test {function_name} function.", patterns.docstring_style)

        snippet_lines = imports + ["", "", f"def {test_name}():", f'    """{docstring}"""']

        # Add assertion placeholder
        snippet_lines.extend(
            [
                f"    result = {function_name}()",
                "    assert result is not None",
            ]
        )

        return "\n".join(snippet_lines)

    def generate_impl_snippet(
        self,
        target_file: Path,
        based_on: list[Path] | None = None,
    ) -> str:
        """Generate implementation snippet using patterns from similar files.

        Args:
            target_file: Path where implementation will be written.
            based_on: List of paths to analyze for patterns.

        Returns:
            Generated implementation skeleton as string.
        """
        # Collect patterns from reference files
        all_imports: list[ImportPattern] = []
        all_classes: list[ClassPattern] = []
        naming_convention = "snake_case"
        docstring_style = "google"

        if based_on:
            for ref_path in based_on:
                if ref_path.exists():
                    patterns = self.extract_patterns(ref_path)
                    all_imports.extend(patterns.imports)
                    all_classes.extend(patterns.classes)
                    naming_convention = patterns.naming_convention
                    docstring_style = patterns.docstring_style

        # Deduplicate imports
        seen_imports: set[str] = set()
        unique_imports: list[ImportPattern] = []
        for imp in all_imports:
            key = (imp.module, tuple(imp.names), imp.is_from_import)
            if key not in seen_imports:
                seen_imports.add(key)
                unique_imports.append(imp)

        # Find common base classes
        base_class = None
        if all_classes:
            base_counts: dict[str, int] = {}
            for cls in all_classes:
                for base in cls.bases:
                    base_counts[base] = base_counts.get(base, 0) + 1
            if base_counts:
                base_class = max(base_counts.keys(), key=lambda x: base_counts[x])

        # Build import section
        import_lines = [imp.to_import_line() for imp in unique_imports[:5]]  # Limit to 5

        # Build module docstring
        module_name = target_file.stem
        module_doc = self._generate_docstring(f"Implementation for {module_name}.", docstring_style)

        lines = [f'"""{module_doc}"""', "", "from __future__ import annotations", ""]
        lines.extend(import_lines)
        lines.extend(["", ""])

        # Generate class skeleton if pattern found
        if base_class:
            class_name = self._to_pascal_case(module_name)
            lines.extend(
                [
                    f"class {class_name}({base_class}):",
                    f'    """Implementation of {class_name}."""',
                    "",
                    "    def __init__(self) -> None:",
                    '        """Initialize instance."""',
                    "        pass",
                ]
            )
        else:
            # Generate function skeleton
            func_name = module_name if naming_convention == "snake_case" else self._to_camel_case(module_name)
            lines.extend(
                [
                    f"def {func_name}() -> None:",
                    '    """Implementation placeholder."""',
                    "    pass",
                ]
            )

        return "\n".join(lines)

    def _generate_docstring(self, description: str, style: str) -> str:
        """Generate docstring in specified style."""
        if style == "sphinx":
            return description
        elif style == "numpy":
            return description
        # Default to Google style
        return description

    def _to_pascal_case(self, name: str) -> str:
        """Convert snake_case to PascalCase."""
        return "".join(word.capitalize() for word in name.split("_"))

    def _to_camel_case(self, name: str) -> str:
        """Convert snake_case to camelCase."""
        parts = name.split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])


def analyze_directory(
    directory: Path,
    cache: ASTCache,
    file_pattern: str = "*.py",
) -> dict[Path, CodePatterns]:
    """Analyze all Python files in a directory.

    Args:
        directory: Directory to scan.
        cache: ASTCache for parsing.
        file_pattern: Glob pattern for files.

    Returns:
        Dictionary mapping file paths to their extracted patterns.
    """
    analyzer = ASTAnalyzer(cache)
    results: dict[Path, CodePatterns] = {}

    for file_path in directory.rglob(file_pattern):
        if file_path.is_file() and not any(part.startswith(".") or part == "__pycache__" for part in file_path.parts):
            results[file_path] = analyzer.extract_patterns(file_path)

    return results
