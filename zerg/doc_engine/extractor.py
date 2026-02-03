"""Symbol extraction from Python source files using the ast module."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FunctionInfo:
    """Information about a function or method extracted from AST."""

    name: str
    lineno: int
    docstring: str | None
    args: list[str]
    return_type: str | None
    decorators: list[str]
    is_method: bool = False
    is_async: bool = False


@dataclass
class ClassInfo:
    """Information about a class extracted from AST."""

    name: str
    lineno: int
    docstring: str | None
    bases: list[str]
    methods: list[FunctionInfo]
    decorators: list[str]


@dataclass
class ImportInfo:
    """Information about an import statement."""

    module: str
    names: list[str]
    is_from: bool


@dataclass
class SymbolTable:
    """Complete symbol table for a single Python module."""

    path: Path
    module_docstring: str | None
    classes: list[ClassInfo]
    functions: list[FunctionInfo]
    imports: list[ImportInfo]
    constants: list[str]
    type_aliases: list[str]


def _unparse_node(node: ast.expr) -> str:
    """Convert an AST expression node back to source string."""
    try:
        return ast.unparse(node)
    except Exception:
        return "<unknown>"


def _extract_docstring(node: ast.AST) -> str | None:
    """Extract docstring from a module, class, or function node."""
    if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
        return None
    if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
        value = node.body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return None


def _extract_decorators(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract decorator names from a class or function node."""
    decorators: list[str] = []
    for dec in node.decorator_list:
        decorators.append(_unparse_node(dec))
    return decorators


def _extract_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract argument names with type annotations from a function node."""
    args: list[str] = []
    for arg in node.args.args:
        if arg.annotation:
            args.append(f"{arg.arg}: {_unparse_node(arg.annotation)}")
        else:
            args.append(arg.arg)
    for arg in node.args.posonlyargs:
        if arg.annotation:
            args.append(f"{arg.arg}: {_unparse_node(arg.annotation)}")
        else:
            args.append(arg.arg)
    if node.args.vararg:
        arg = node.args.vararg
        name = f"*{arg.arg}"
        if arg.annotation:
            name += f": {_unparse_node(arg.annotation)}"
        args.append(name)
    for arg in node.args.kwonlyargs:
        if arg.annotation:
            args.append(f"{arg.arg}: {_unparse_node(arg.annotation)}")
        else:
            args.append(arg.arg)
    if node.args.kwarg:
        arg = node.args.kwarg
        name = f"**{arg.arg}"
        if arg.annotation:
            name += f": {_unparse_node(arg.annotation)}"
        args.append(name)
    return args


def _extract_return_type(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Extract return type annotation from a function node."""
    if node.returns:
        return _unparse_node(node.returns)
    return None


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    is_method: bool = False,
) -> FunctionInfo:
    """Extract FunctionInfo from a function or async function AST node."""
    return FunctionInfo(
        name=node.name,
        lineno=node.lineno,
        docstring=_extract_docstring(node),
        args=_extract_args(node),
        return_type=_extract_return_type(node),
        decorators=_extract_decorators(node),
        is_method=is_method,
        is_async=isinstance(node, ast.AsyncFunctionDef),
    )


def _is_constant_name(name: str) -> bool:
    """Check if a name follows ALL_CAPS constant naming convention."""
    return name.isupper() and not name.startswith("_")


def _is_type_alias(node: ast.stmt) -> str | None:
    """Check if a statement is a type alias and return its name.

    Handles both simple assignment type aliases (e.g. ``MyType = dict[str, int]``)
    and PEP 613 ``TypeAlias`` annotations.
    """
    # PEP 613: name: TypeAlias = ...
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        annotation_src = _unparse_node(node.annotation)
        if "TypeAlias" in annotation_src:
            return node.target.id
    return None


class SymbolExtractor:
    """Extract symbols from Python source files using the ast module.

    Parses a Python file and produces a :class:`SymbolTable` containing
    classes, functions, imports, constants, and type aliases found at the
    module level.
    """

    def extract(self, path: Path) -> SymbolTable:
        """Parse a Python source file and extract its symbol table.

        Args:
            path: Path to the Python source file.

        Returns:
            A populated SymbolTable for the given file.

        Raises:
            SyntaxError: If the file cannot be parsed.
            OSError: If the file cannot be read.
        """
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        module_docstring = _extract_docstring(tree)
        classes: list[ClassInfo] = []
        functions: list[FunctionInfo] = []
        imports: list[ImportInfo] = []
        constants: list[str] = []
        type_aliases: list[str] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(self._extract_class(node))

            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                functions.append(_extract_function(node, is_method=False))

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        ImportInfo(
                            module=alias.name,
                            names=[alias.asname or alias.name],
                            is_from=False,
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                names = [alias.asname or alias.name for alias in node.names]
                imports.append(
                    ImportInfo(
                        module=module_name,
                        names=names,
                        is_from=True,
                    )
                )

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and _is_constant_name(target.id):
                        constants.append(target.id)

            elif isinstance(node, ast.AnnAssign):
                alias_name = _is_type_alias(node)
                if alias_name:
                    type_aliases.append(alias_name)
                elif isinstance(node.target, ast.Name) and _is_constant_name(node.target.id):
                    constants.append(node.target.id)

        return SymbolTable(
            path=path,
            module_docstring=module_docstring,
            classes=classes,
            functions=functions,
            imports=imports,
            constants=constants,
            type_aliases=type_aliases,
        )

    def _extract_class(self, node: ast.ClassDef) -> ClassInfo:
        """Extract ClassInfo from a class AST node."""
        methods: list[FunctionInfo] = []
        for child in node.body:
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                methods.append(_extract_function(child, is_method=True))

        bases = [_unparse_node(base) for base in node.bases]

        return ClassInfo(
            name=node.name,
            lineno=node.lineno,
            docstring=_extract_docstring(node),
            bases=bases,
            methods=methods,
            decorators=_extract_decorators(node),
        )
