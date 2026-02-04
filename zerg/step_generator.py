"""Step generator for bite-sized task planning.

Generates TDD-style execution steps for tasks based on detail level.
Supports three detail levels:
- standard: No steps (backward compatible, classic mode)
- medium: TDD sequence without code snippets
- high: TDD sequence with code snippets from AST analysis

Steps follow the TDD red-green-refactor cycle:
1. write_test - Create test file with failing test
2. verify_fail - Verify test fails (expected to fail)
3. implement - Write implementation code
4. verify_pass - Verify test passes
5. format - Run formatter on changed files
6. commit - Commit changes
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zerg.ast_cache import ASTCache


class DetailLevel(Enum):
    """Task detail level for step generation."""

    STANDARD = "standard"  # No steps (classic mode)
    MEDIUM = "medium"  # TDD steps without code snippets
    HIGH = "high"  # TDD steps with code snippets


class StepAction(Enum):
    """Step action types matching task_graph.json schema."""

    WRITE_TEST = "write_test"
    VERIFY_FAIL = "verify_fail"
    IMPLEMENT = "implement"
    VERIFY_PASS = "verify_pass"
    FORMAT = "format"
    COMMIT = "commit"


class VerifyMode(Enum):
    """Verification mode for step commands."""

    EXIT_CODE = "exit_code"  # 0 = success
    EXIT_CODE_NONZERO = "exit_code_nonzero"  # non-0 = success (for verify_fail)
    NONE = "none"  # No verification


@dataclass
class Step:
    """A single execution step in a task."""

    step: int
    action: StepAction
    file: str | None = None
    code_snippet: str | None = None
    run: str | None = None
    verify: VerifyMode = VerifyMode.EXIT_CODE

    def to_dict(self) -> dict[str, Any]:
        """Convert step to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "step": self.step,
            "action": self.action.value,
            "verify": self.verify.value,
        }
        if self.file:
            result["file"] = self.file
        if self.code_snippet:
            result["code_snippet"] = self.code_snippet
        if self.run:
            result["run"] = self.run
        return result


@dataclass
class FormatterConfig:
    """Formatter configuration for a project."""

    format_cmd: str
    fix_cmd: str
    file_patterns: list[str]


class StepGenerator:
    """Generates execution steps for tasks based on detail level.

    For medium and high detail levels, generates a TDD-style sequence:
    1. Write test (red)
    2. Verify test fails
    3. Implement code (green)
    4. Verify test passes
    5. Format code
    6. Commit changes

    For high detail, code snippets are included using AST analysis.
    """

    def __init__(
        self,
        project_root: Path | None = None,
        ast_cache: ASTCache | None = None,
    ) -> None:
        """Initialize step generator.

        Args:
            project_root: Root directory of the project for formatter detection.
            ast_cache: Optional AST cache for code snippet generation.
        """
        self.project_root = project_root or Path.cwd()
        self.ast_cache = ast_cache
        self._formatter: FormatterConfig | None = None
        self._formatter_detected = False

    def _detect_formatter(self) -> FormatterConfig | None:
        """Detect project formatter from config files.

        Attempts to import FormatterDetector if available, otherwise
        uses simple heuristics based on config file presence.

        Returns:
            FormatterConfig if detected, None otherwise.
        """
        if self._formatter_detected:
            return self._formatter

        self._formatter_detected = True

        # Try to use FormatterDetector if available
        try:
            from zerg.formatter_detector import FormatterDetector

            detector = FormatterDetector(self.project_root)
            self._formatter = detector.detect()
            return self._formatter
        except ImportError:
            pass

        # Fallback: Simple detection based on config files
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "[tool.ruff]" in content:
                self._formatter = FormatterConfig(
                    format_cmd="ruff format",
                    fix_cmd="ruff check --fix",
                    file_patterns=["*.py"],
                )
            elif "[tool.black]" in content:
                self._formatter = FormatterConfig(
                    format_cmd="black",
                    fix_cmd="black",
                    file_patterns=["*.py"],
                )

        if self._formatter is None:
            # Check for prettier
            if (self.project_root / ".prettierrc").exists() or (self.project_root / ".prettierrc.json").exists():
                self._formatter = FormatterConfig(
                    format_cmd="prettier --write",
                    fix_cmd="prettier --write",
                    file_patterns=["*.js", "*.ts", "*.jsx", "*.tsx"],
                )

        return self._formatter

    def _get_test_file(self, impl_file: str) -> str:
        """Generate test file path from implementation file.

        Args:
            impl_file: Implementation file path (e.g., 'zerg/foo.py')

        Returns:
            Test file path (e.g., 'tests/unit/test_foo.py')
        """
        path = Path(impl_file)

        # Handle different conventions
        if path.suffix == ".py":
            # Python: zerg/foo.py -> tests/unit/test_foo.py
            return f"tests/unit/test_{path.stem}.py"
        elif path.suffix in (".ts", ".tsx", ".js", ".jsx"):
            # JavaScript/TypeScript: src/foo.ts -> src/__tests__/foo.test.ts
            parent = path.parent
            return str(parent / "__tests__" / f"{path.stem}.test{path.suffix}")

        # Fallback
        return f"tests/test_{path.stem}{path.suffix}"

    def _get_verification_cmd(self, task: dict[str, Any]) -> str:
        """Get verification command from task or generate default.

        Args:
            task: Task definition dictionary.

        Returns:
            Verification command string.
        """
        verification = task.get("verification", {})
        if isinstance(verification, dict) and verification.get("command"):
            return verification["command"]

        # Generate default based on file patterns
        files = task.get("files", {})
        create_files = files.get("create", [])
        modify_files = files.get("modify", [])

        all_files = create_files + modify_files
        if all_files:
            first_file = all_files[0]
            if first_file.endswith(".py"):
                test_file = self._get_test_file(first_file)
                return f"pytest {test_file} -v --tb=short"

        return "pytest -v --tb=short"

    def _generate_code_snippet(
        self,
        task: dict[str, Any],
        action: StepAction,
    ) -> str | None:
        """Generate code snippet for high detail level.

        Uses AST analysis to extract patterns from existing code.

        Args:
            task: Task definition dictionary.
            action: The step action type.

        Returns:
            Code snippet string or None if not applicable.
        """
        if action == StepAction.WRITE_TEST:
            return self._generate_test_snippet(task)
        elif action == StepAction.IMPLEMENT:
            return self._generate_impl_snippet(task)
        return None

    def _generate_test_snippet(self, task: dict[str, Any]) -> str:
        """Generate a test snippet based on task description.

        Args:
            task: Task definition dictionary.

        Returns:
            Test code snippet.
        """
        title = task.get("title", "feature")
        # Convert title to function name
        func_name = title.lower().replace(" ", "_").replace("-", "_")
        # Sanitize
        func_name = "".join(c for c in func_name if c.isalnum() or c == "_")

        files = task.get("files", {})
        create_files = files.get("create", [])

        if create_files:
            # Extract module name from first created file
            first_file = create_files[0]
            module_path = Path(first_file)
            module_name = module_path.stem
            package_path = str(module_path.parent).replace("/", ".")

            return f'''"""Tests for {module_name}."""

import pytest
from {package_path}.{module_name} import {func_name.title().replace("_", "")}


class Test{func_name.title().replace("_", "")}:
    """Test cases for {title}."""

    def test_{func_name}_basic(self) -> None:
        """Test basic functionality."""
        # Arrange
        # TODO: Set up test data

        # Act
        # TODO: Call the function/method

        # Assert
        # TODO: Verify expected behavior
        assert False, "Test not implemented"
'''

        return f'''"""Tests for {title}."""

import pytest


def test_{func_name}() -> None:
    """Test {title}."""
    # TODO: Implement test
    assert False, "Test not implemented"
'''

    def _generate_impl_snippet(self, task: dict[str, Any]) -> str:
        """Generate an implementation snippet based on task description.

        Args:
            task: Task definition dictionary.

        Returns:
            Implementation code snippet.
        """
        title = task.get("title", "Module")
        description = task.get("description", "")

        files = task.get("files", {})
        create_files = files.get("create", [])

        if create_files:
            first_file = create_files[0]
            module_path = Path(first_file)
            module_name = module_path.stem

            # Generate class name from module name
            class_name = "".join(word.title() for word in module_name.split("_"))

            return f'''"""{title}.

{description}
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class {class_name}:
    """{title} implementation.

    TODO: Add fields and methods.
    """

    def __init__(self) -> None:
        """Initialize {class_name}."""
        pass
'''

        return f'''"""{title}.

{description}
"""

from __future__ import annotations


# TODO: Implement {title}
'''

    def generate(
        self,
        task: dict[str, Any],
        detail_level: DetailLevel | str = DetailLevel.STANDARD,
    ) -> list[Step]:
        """Generate execution steps for a task.

        Args:
            task: Task definition dictionary with id, title, description, files, etc.
            detail_level: Detail level (standard/medium/high).

        Returns:
            List of Step objects. Empty list for standard detail level.
        """
        # Normalize detail level
        if isinstance(detail_level, str):
            detail_level = DetailLevel(detail_level.lower())

        # Standard detail: no steps (backward compatible)
        if detail_level == DetailLevel.STANDARD:
            return []

        steps: list[Step] = []
        step_num = 0

        # Get file information
        files = task.get("files", {})
        create_files = files.get("create", [])
        modify_files = files.get("modify", [])

        # Determine primary implementation file
        impl_files = create_files or modify_files
        impl_file = impl_files[0] if impl_files else None

        # Determine test file
        test_file = self._get_test_file(impl_file) if impl_file else None

        # Get verification command
        verify_cmd = self._get_verification_cmd(task)

        # Include code snippets only for high detail
        include_snippets = detail_level == DetailLevel.HIGH

        # Step 1: Write test (red)
        step_num += 1
        steps.append(
            Step(
                step=step_num,
                action=StepAction.WRITE_TEST,
                file=test_file,
                code_snippet=(self._generate_code_snippet(task, StepAction.WRITE_TEST) if include_snippets else None),
                run=None,
                verify=VerifyMode.NONE,
            )
        )

        # Step 2: Verify test fails
        step_num += 1
        steps.append(
            Step(
                step=step_num,
                action=StepAction.VERIFY_FAIL,
                file=None,
                code_snippet=None,
                run=verify_cmd,
                verify=VerifyMode.EXIT_CODE_NONZERO,  # Expects failure
            )
        )

        # Step 3: Implement
        step_num += 1
        steps.append(
            Step(
                step=step_num,
                action=StepAction.IMPLEMENT,
                file=impl_file,
                code_snippet=(self._generate_code_snippet(task, StepAction.IMPLEMENT) if include_snippets else None),
                run=None,
                verify=VerifyMode.NONE,
            )
        )

        # Step 4: Verify test passes
        step_num += 1
        steps.append(
            Step(
                step=step_num,
                action=StepAction.VERIFY_PASS,
                file=None,
                code_snippet=None,
                run=verify_cmd,
                verify=VerifyMode.EXIT_CODE,  # Expects success
            )
        )

        # Step 5: Format
        step_num += 1
        formatter = self._detect_formatter()
        format_cmd = formatter.format_cmd if formatter else "ruff format"

        # Build file list for format command
        all_files = [f for f in [test_file, impl_file] if f]
        if all_files:
            files_arg = " ".join(all_files)
            format_run = f"{format_cmd} {files_arg}"
        else:
            format_run = format_cmd

        steps.append(
            Step(
                step=step_num,
                action=StepAction.FORMAT,
                file=None,
                code_snippet=None,
                run=format_run,
                verify=VerifyMode.EXIT_CODE,
            )
        )

        # Step 6: Commit
        step_num += 1
        task_id = task.get("id", "TASK")
        task_title = task.get("title", "Implement task")
        commit_msg = f"feat({task_id}): {task_title}"

        steps.append(
            Step(
                step=step_num,
                action=StepAction.COMMIT,
                file=None,
                code_snippet=None,
                run=f'git add -A && git commit -m "{commit_msg}"',
                verify=VerifyMode.EXIT_CODE,
            )
        )

        return steps

    def generate_steps_dict(
        self,
        task: dict[str, Any],
        detail_level: DetailLevel | str = DetailLevel.STANDARD,
    ) -> list[dict[str, Any]]:
        """Generate steps as dictionaries for JSON serialization.

        Args:
            task: Task definition dictionary.
            detail_level: Detail level (standard/medium/high).

        Returns:
            List of step dictionaries ready for task-graph.json.
        """
        steps = self.generate(task, detail_level)
        return [step.to_dict() for step in steps]


def generate_steps_for_task(
    task: dict[str, Any],
    detail_level: str = "standard",
    project_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Convenience function to generate steps for a single task.

    Args:
        task: Task definition dictionary.
        detail_level: Detail level string (standard/medium/high).
        project_root: Project root directory for formatter detection.

    Returns:
        List of step dictionaries.
    """
    generator = StepGenerator(project_root=project_root)
    return generator.generate_steps_dict(task, detail_level)
