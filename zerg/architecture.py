"""Architecture compliance checking for ZERG.

Validates Python imports against layer definitions and import rules.
Runs as a quality gate at ship/merge time to catch architectural violations.
"""

from __future__ import annotations

import ast
import fnmatch
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zerg.ast_cache import ASTCache

# Standard library modules (Python 3.10+)
# Fallback list for older Python versions
_STDLIB_MODULES: frozenset[str] = frozenset(
    getattr(sys, "stdlib_module_names", set())
    | {
        # Common stdlib modules for fallback
        "abc",
        "ast",
        "asyncio",
        "collections",
        "contextlib",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "hashlib",
        "importlib",
        "io",
        "itertools",
        "json",
        "logging",
        "os",
        "pathlib",
        "re",
        "shutil",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
        "time",
        "typing",
        "unittest",
        "uuid",
        "warnings",
    }
)


@dataclass
class LayerConfig:
    """Configuration for an architectural layer."""

    name: str
    paths: list[str] = field(default_factory=list)  # Glob patterns
    allowed_imports: list[str] = field(default_factory=list)  # Layer names or "stdlib"


@dataclass
class ImportRule:
    """Import allow/deny rule for a directory."""

    directory: str
    allow: list[str] | None = None
    deny: list[str] | None = None


@dataclass
class NamingConvention:
    """Naming convention rules for a directory."""

    directory: str
    files: str | None = None  # snake_case, test_*.py, etc.
    classes: str | None = None  # PascalCase
    functions: str | None = None  # snake_case


@dataclass
class ArchitectureException:
    """Exception from architecture rules."""

    file: str | None = None
    import_module: str | None = None
    in_file: str | None = None
    pattern: str | None = None
    reason: str = ""


@dataclass
class ArchitectureConfig:
    """Complete architecture configuration."""

    enabled: bool = True
    layers: list[LayerConfig] = field(default_factory=list)
    import_rules: list[ImportRule] = field(default_factory=list)
    naming_conventions: list[NamingConvention] = field(default_factory=list)
    exceptions: list[ArchitectureException] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ArchitectureConfig:
        """Create config from dictionary (e.g., from YAML)."""
        if not data:
            return cls(enabled=False)

        layers = [
            LayerConfig(
                name=layer.get("name", ""),
                paths=layer.get("paths", []),
                allowed_imports=layer.get("allowed_imports", []),
            )
            for layer in data.get("layers", [])
        ]

        import_rules = [
            ImportRule(
                directory=rule.get("directory", ""),
                allow=rule.get("allow"),
                deny=rule.get("deny"),
            )
            for rule in data.get("import_rules", [])
        ]

        naming_conventions = [
            NamingConvention(
                directory=conv.get("directory", ""),
                files=conv.get("files"),
                classes=conv.get("classes"),
                functions=conv.get("functions"),
            )
            for conv in data.get("naming_conventions", [])
        ]

        exceptions = [
            ArchitectureException(
                file=exc.get("file"),
                import_module=exc.get("import"),
                in_file=exc.get("in_file"),
                pattern=exc.get("pattern"),
                reason=exc.get("reason", ""),
            )
            for exc in data.get("exceptions", [])
        ]

        return cls(
            enabled=data.get("enabled", True),
            layers=layers,
            import_rules=import_rules,
            naming_conventions=naming_conventions,
            exceptions=exceptions,
        )


@dataclass
class Violation:
    """An architecture rule violation."""

    file: str
    line: int | None
    rule_type: str  # "layer", "import", "naming"
    message: str
    severity: str = "error"  # "error", "warning"

    def __str__(self) -> str:
        """Format violation for display."""
        location = f"{self.file}:{self.line}" if self.line else self.file
        return f"{self.rule_type.upper()}: {location}\n  {self.message}"


class ArchitectureChecker:
    """Check Python files for architecture compliance."""

    def __init__(self, config: ArchitectureConfig, cache: ASTCache | None = None) -> None:
        """Initialize checker with configuration.

        Args:
            config: Architecture configuration
            cache: Optional AST cache for performance
        """
        self.config = config
        self._cache = cache
        # Build layer index for fast lookup
        self._layer_index: dict[str, LayerConfig] = {layer.name: layer for layer in config.layers}

    def check_file(self, file_path: Path, root: Path | None = None) -> list[Violation]:
        """Check a single file for architecture violations.

        Args:
            file_path: Path to Python file
            root: Project root for relative path calculation

        Returns:
            List of violations found
        """
        if not self.config.enabled:
            return []

        if not file_path.suffix == ".py":
            return []

        root = root or file_path.parent
        relative_path = str(file_path.relative_to(root)) if file_path.is_relative_to(root) else str(file_path)

        # Check if file is exempt
        if self._is_file_exempt(relative_path):
            return []

        violations: list[Violation] = []

        # Check layer violations
        violations.extend(self._check_layer_violations(file_path, relative_path))

        # Check import rules
        violations.extend(self._check_import_rules(file_path, relative_path))

        # Check naming conventions
        violations.extend(self._check_naming_conventions(file_path, relative_path))

        return violations

    def check_directory(self, directory: Path, pattern: str = "**/*.py") -> list[Violation]:
        """Check all Python files in a directory.

        Args:
            directory: Directory to scan
            pattern: Glob pattern for files

        Returns:
            List of all violations found
        """
        if not self.config.enabled:
            return []

        violations: list[Violation] = []

        for file_path in directory.glob(pattern):
            if file_path.is_file() and not self._should_skip_path(file_path):
                violations.extend(self.check_file(file_path, root=directory))

        return violations

    def get_file_layer(self, relative_path: str) -> LayerConfig | None:
        """Determine which layer a file belongs to.

        Args:
            relative_path: File path relative to project root

        Returns:
            LayerConfig if file matches a layer, None otherwise
        """
        for layer in self.config.layers:
            for path_pattern in layer.paths:
                if fnmatch.fnmatch(relative_path, path_pattern):
                    return layer
        return None

    def get_module_layer(self, module_name: str, root: Path) -> LayerConfig | None:
        """Determine which layer a module belongs to.

        Args:
            module_name: Python module name (e.g., "zerg.gates")
            root: Project root directory

        Returns:
            LayerConfig if module matches a layer, None otherwise
        """
        # Convert module name to file path
        module_path = module_name.replace(".", "/")
        candidates = [f"{module_path}.py", f"{module_path}/__init__.py"]

        for candidate in candidates:
            for layer in self.config.layers:
                for path_pattern in layer.paths:
                    if fnmatch.fnmatch(candidate, path_pattern):
                        return layer

        return None

    def _check_layer_violations(self, file_path: Path, relative_path: str) -> list[Violation]:
        """Check for layer boundary violations."""
        violations: list[Violation] = []

        source_layer = self.get_file_layer(relative_path)
        if not source_layer:
            # File not in any layer, skip layer checking
            return violations

        # Parse file and extract imports
        imports = self._get_imports(file_path)

        for module_name, line_no in imports:
            # Check if import is exempt
            if self._is_import_exempt(module_name, relative_path):
                continue

            # Check if it's stdlib
            if self._is_stdlib(module_name):
                if "stdlib" not in source_layer.allowed_imports:
                    violations.append(
                        Violation(
                            file=relative_path,
                            line=line_no,
                            rule_type="layer",
                            message=(
                                f"Import '{module_name}' is stdlib, but layer '{source_layer.name}' "
                                f"does not allow stdlib imports. Allowed: {source_layer.allowed_imports}"
                            ),
                        )
                    )
                continue

            # Find target layer
            target_layer = self._get_layer_for_module(module_name)
            if not target_layer:
                # External package, not tracked
                continue

            # Check if target layer is allowed
            if target_layer.name not in source_layer.allowed_imports:
                violations.append(
                    Violation(
                        file=relative_path,
                        line=line_no,
                        rule_type="layer",
                        message=(
                            f"Import '{module_name}' violates layer boundary. "
                            f"File is in layer '{source_layer.name}', but imports from layer '{target_layer.name}'. "
                            f"Allowed imports for '{source_layer.name}': {source_layer.allowed_imports}"
                        ),
                    )
                )

        return violations

    def _check_import_rules(self, file_path: Path, relative_path: str) -> list[Violation]:
        """Check for import rule violations (allow/deny patterns)."""
        violations: list[Violation] = []

        # Find applicable rules
        applicable_rules = [
            rule for rule in self.config.import_rules if fnmatch.fnmatch(relative_path, f"{rule.directory}*")
        ]

        if not applicable_rules:
            return violations

        imports = self._get_imports(file_path)

        for module_name, line_no in imports:
            if self._is_import_exempt(module_name, relative_path):
                continue

            for rule in applicable_rules:
                # Check deny list
                if rule.deny:
                    for denied in rule.deny:
                        if module_name == denied or module_name.startswith(f"{denied}."):
                            violations.append(
                                Violation(
                                    file=relative_path,
                                    line=line_no,
                                    rule_type="import",
                                    message=(
                                        f"Import '{module_name}' is denied in {rule.directory}. "
                                        f"Denied imports: {rule.deny}"
                                    ),
                                )
                            )

                # Check allow list (if specified, only these are allowed)
                if rule.allow and "*" not in rule.allow:
                    allowed = any(
                        module_name == allowed_mod or module_name.startswith(f"{allowed_mod}.")
                        for allowed_mod in rule.allow
                    )
                    if not allowed and not self._is_stdlib(module_name):
                        violations.append(
                            Violation(
                                file=relative_path,
                                line=line_no,
                                rule_type="import",
                                message=(
                                    f"Import '{module_name}' is not in allow list for {rule.directory}. "
                                    f"Allowed imports: {rule.allow}"
                                ),
                                severity="warning",
                            )
                        )

        return violations

    def _check_naming_conventions(self, file_path: Path, relative_path: str) -> list[Violation]:
        """Check naming convention violations."""
        violations: list[Violation] = []

        # Find applicable conventions
        for conv in self.config.naming_conventions:
            if not fnmatch.fnmatch(relative_path, f"{conv.directory}*"):
                continue

            # Check file naming
            if conv.files:
                # Strip .py extension for snake_case/PascalCase/camelCase checks
                name_to_check = (
                    file_path.stem if conv.files in ("snake_case", "PascalCase", "camelCase") else file_path.name
                )
                if not self._check_name_pattern(name_to_check, conv.files):
                    violations.append(
                        Violation(
                            file=relative_path,
                            line=None,
                            rule_type="naming",
                            message=(
                                f"File name '{file_path.name}' does not match convention '{conv.files}'. "
                                f"Expected pattern: {self._pattern_description(conv.files)}"
                            ),
                            severity="warning",
                        )
                    )

            # Check class and function naming requires parsing
            if conv.classes or conv.functions:
                tree = self._parse_file(file_path)
                if tree:
                    violations.extend(self._check_ast_naming(tree, relative_path, conv))

        return violations

    def _check_ast_naming(self, tree: ast.Module, relative_path: str, conv: NamingConvention) -> list[Violation]:
        """Check class and function naming in AST."""
        violations: list[Violation] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and conv.classes:
                if not self._check_name_pattern(node.name, conv.classes):
                    violations.append(
                        Violation(
                            file=relative_path,
                            line=node.lineno,
                            rule_type="naming",
                            message=(
                                f"Class '{node.name}' does not match convention '{conv.classes}'. "
                                f"Expected: {self._pattern_description(conv.classes)}"
                            ),
                            severity="warning",
                        )
                    )

            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and conv.functions:
                # Skip dunder methods
                if node.name.startswith("__") and node.name.endswith("__"):
                    continue
                if not self._check_name_pattern(node.name, conv.functions):
                    violations.append(
                        Violation(
                            file=relative_path,
                            line=node.lineno,
                            rule_type="naming",
                            message=(
                                f"Function '{node.name}' does not match convention '{conv.functions}'. "
                                f"Expected: {self._pattern_description(conv.functions)}"
                            ),
                            severity="warning",
                        )
                    )

        return violations

    def _check_name_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches naming pattern."""
        if pattern == "snake_case":
            return bool(re.match(r"^[a-z][a-z0-9_]*$", name))
        elif pattern == "PascalCase":
            return bool(re.match(r"^[A-Z][a-zA-Z0-9]*$", name))
        elif pattern == "camelCase":
            return bool(re.match(r"^[a-z][a-zA-Z0-9]*$", name))
        else:
            # Treat as glob pattern
            return fnmatch.fnmatch(name, pattern)

    def _pattern_description(self, pattern: str) -> str:
        """Get human-readable description of naming pattern."""
        descriptions = {
            "snake_case": "lowercase with underscores (e.g., my_function)",
            "PascalCase": "capitalized words (e.g., MyClass)",
            "camelCase": "first word lowercase (e.g., myFunction)",
        }
        return descriptions.get(pattern, f"matching '{pattern}'")

    def _get_imports(self, file_path: Path) -> list[tuple[str, int]]:
        """Extract imports with line numbers from file."""
        tree = self._parse_file(file_path)
        if not tree:
            return []

        imports: list[tuple[str, int]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append((node.module, node.lineno))

        return imports

    def _parse_file(self, file_path: Path) -> ast.Module | None:
        """Parse Python file, using cache if available."""
        try:
            if self._cache:
                return self._cache.parse(file_path)
            source = file_path.read_text(encoding="utf-8")
            return ast.parse(source, filename=str(file_path))
        except (SyntaxError, OSError):
            return None

    def _is_stdlib(self, module_name: str) -> bool:
        """Check if module is from standard library."""
        top_level = module_name.split(".")[0]
        return top_level in _STDLIB_MODULES

    def _get_layer_for_module(self, module_name: str) -> LayerConfig | None:
        """Find layer for a module by checking path patterns."""
        module_path = module_name.replace(".", "/")
        candidates = [f"{module_path}.py", f"{module_path}/__init__.py"]

        for candidate in candidates:
            for layer in self.config.layers:
                for path_pattern in layer.paths:
                    if fnmatch.fnmatch(candidate, path_pattern):
                        return layer

        return None

    def _is_file_exempt(self, relative_path: str) -> bool:
        """Check if file is exempt from architecture rules."""
        for exc in self.config.exceptions:
            if exc.file and fnmatch.fnmatch(relative_path, exc.file):
                return True
            if exc.pattern and fnmatch.fnmatch(relative_path, exc.pattern):
                return True
        return False

    def _is_import_exempt(self, module_name: str, file_path: str) -> bool:
        """Check if import is exempt from architecture rules."""
        for exc in self.config.exceptions:
            if exc.import_module == module_name:
                if exc.in_file is None or fnmatch.fnmatch(file_path, exc.in_file):
                    return True
        return False

    def _should_skip_path(self, path: Path) -> bool:
        """Check if path should be skipped (e.g., __pycache__, .git)."""
        parts = path.parts
        return any(part.startswith(".") or part == "__pycache__" for part in parts)


def load_architecture_config(config_path: Path | None = None) -> ArchitectureConfig:
    """Load architecture configuration from YAML file.

    Args:
        config_path: Path to config file (defaults to .zerg/config.yaml)

    Returns:
        ArchitectureConfig instance
    """
    import yaml

    if config_path is None:
        config_path = Path(".zerg/config.yaml")

    if not config_path.exists():
        return ArchitectureConfig(enabled=False)

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        arch_data = data.get("architecture", {})
        return ArchitectureConfig.from_dict(arch_data)
    except (OSError, yaml.YAMLError):
        return ArchitectureConfig(enabled=False)


def format_violations(violations: list[Violation]) -> str:
    """Format violations for display.

    Args:
        violations: List of violations

    Returns:
        Formatted string for output
    """
    if not violations:
        return "No architecture violations found."

    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]

    lines = [f"Architecture Violations Found ({len(errors)} errors, {len(warnings)} warnings):"]
    lines.append("")

    for violation in violations:
        lines.append(str(violation))
        lines.append("")

    lines.append("To add an exception, update .zerg/config.yaml:")
    lines.append("  architecture:")
    lines.append("    exceptions:")
    lines.append('      - file: "path/to/file.py"')
    lines.append('        reason: "Explanation for exemption"')

    return "\n".join(lines)
