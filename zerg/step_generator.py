"""Step generation for bite-sized task planning.

Generates TDD-style execution steps for tasks based on detail level.
For medium/high detail, produces a 6-step TDD sequence:
1. write_test - Write failing test
2. verify_fail - Verify test fails (exit_code_nonzero)
3. implement - Write implementation
4. verify_pass - Verify test passes (exit_code)
5. format - Run code formatter
6. commit - Commit changes

For high detail, includes code_snippet with realistic patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zerg.formatter_detector import FormatterConfig, FormatterDetector

if TYPE_CHECKING:
    pass


class DetailLevel(StrEnum):
    """Detail level for step generation."""

    STANDARD = "standard"  # No steps (backward compatible)
    MEDIUM = "medium"  # TDD steps without code snippets
    HIGH = "high"  # TDD steps with code snippets


class StepAction(StrEnum):
    """Action types for execution steps."""

    WRITE_TEST = "write_test"
    VERIFY_FAIL = "verify_fail"
    IMPLEMENT = "implement"
    VERIFY_PASS = "verify_pass"
    FORMAT = "format"
    COMMIT = "commit"


class VerifyMode(StrEnum):
    """Verification modes for step execution."""

    EXIT_CODE = "exit_code"  # 0 = success
    EXIT_CODE_NONZERO = "exit_code_nonzero"  # non-0 = success
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
        }
        if self.file:
            result["file"] = self.file
        if self.code_snippet:
            result["code_snippet"] = self.code_snippet
        if self.run:
            result["run"] = self.run
        result["verify"] = self.verify.value
        return result


@dataclass
class TaskDefinition:
    """Task definition from task-graph.json."""

    id: str
    title: str
    description: str = ""
    files: dict[str, list[str]] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskDefinition:
        """Create TaskDefinition from dictionary."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            files=data.get("files", {}),
            verification=data.get("verification", {}),
        )


class StepGenerator:
    """Generates TDD execution steps for tasks based on detail level.

    For standard detail: Returns empty list (backward compatible).
    For medium detail: Returns 6-step TDD sequence without snippets.
    For high detail: Returns 6-step TDD sequence with code snippets.

    Uses FormatterDetector to populate format step commands and
    optionally integrates with ASTAnalyzer for realistic snippets.
    """

    # TDD step sequence with descriptions
    TDD_SEQUENCE = [
        (StepAction.WRITE_TEST, "Write failing test for {title}"),
        (StepAction.VERIFY_FAIL, "Verify test fails (TDD red phase)"),
        (StepAction.IMPLEMENT, "Implement {title}"),
        (StepAction.VERIFY_PASS, "Verify test passes (TDD green phase)"),
        (StepAction.FORMAT, "Format code with {formatter}"),
        (StepAction.COMMIT, "Commit changes"),
    ]

    def __init__(
        self,
        project_root: Path | str | None = None,
        ast_analyzer: Any | None = None,
    ) -> None:
        """Initialize step generator.

        Args:
            project_root: Root directory of the project. Defaults to cwd.
            ast_analyzer: Optional ASTAnalyzer for code snippet generation.
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.formatter_detector = FormatterDetector(self.project_root)
        self.ast_analyzer = ast_analyzer
        self._formatter_cache: FormatterConfig | None = None
        self._formatter_cached: bool = False

    @property
    def formatter(self) -> FormatterConfig | None:
        """Get detected formatter, caching the result."""
        if not self._formatter_cached:
            self._formatter_cache = self.formatter_detector.detect()
            self._formatter_cached = True
        return self._formatter_cache

    def generate_steps(
        self,
        task: TaskDefinition | dict[str, Any],
        detail_level: DetailLevel | str = DetailLevel.STANDARD,
    ) -> list[Step]:
        """Generate execution steps for a task.

        Args:
            task: Task definition (TaskDefinition or dict).
            detail_level: Detail level (standard/medium/high).

        Returns:
            List of Step objects. Empty for standard detail.
        """
        # Normalize inputs
        if isinstance(task, dict):
            task = TaskDefinition.from_dict(task)
        if isinstance(detail_level, str):
            detail_level = DetailLevel(detail_level)

        # Standard detail = no steps (backward compatible)
        if detail_level == DetailLevel.STANDARD:
            return []

        # Medium/High detail = TDD sequence
        steps: list[Step] = []
        include_snippets = detail_level == DetailLevel.HIGH

        # Get files from task definition
        create_files = task.files.get("create", [])
        modify_files = task.files.get("modify", [])
        target_files = create_files + modify_files

        # Determine test file and impl file
        test_file, impl_file = self._determine_files(task, target_files)

        # Get verification command from task
        verify_cmd = task.verification.get("command", "pytest -xvs")

        # Generate TDD steps
        for step_num, (action, desc_template) in enumerate(self.TDD_SEQUENCE, start=1):
            step = self._create_step(
                step_num=step_num,
                action=action,
                desc_template=desc_template,
                task=task,
                test_file=test_file,
                impl_file=impl_file,
                verify_cmd=verify_cmd,
                include_snippets=include_snippets,
            )
            steps.append(step)

        return steps

    def _determine_files(
        self,
        task: TaskDefinition,
        target_files: list[str],
    ) -> tuple[str | None, str | None]:
        """Determine test file and implementation file for a task.

        Args:
            task: Task definition.
            target_files: List of files from task.

        Returns:
            Tuple of (test_file, impl_file).
        """
        test_file: str | None = None
        impl_file: str | None = None

        for f in target_files:
            if "test" in f.lower() or f.startswith("tests/"):
                test_file = f
            elif f.endswith(".py"):
                impl_file = f

        # If no explicit test file, infer from impl file
        if not test_file and impl_file:
            # zerg/foo.py -> tests/unit/test_foo.py
            impl_path = Path(impl_file)
            test_file = f"tests/unit/test_{impl_path.stem}.py"

        # If no impl file but test file exists, infer impl
        if not impl_file and test_file:
            # tests/unit/test_foo.py -> zerg/foo.py
            test_path = Path(test_file)
            stem = test_path.stem.replace("test_", "")
            impl_file = f"zerg/{stem}.py"

        return test_file, impl_file

    def _create_step(
        self,
        step_num: int,
        action: StepAction,
        desc_template: str,
        task: TaskDefinition,
        test_file: str | None,
        impl_file: str | None,
        verify_cmd: str,
        include_snippets: bool,
    ) -> Step:
        """Create a single execution step.

        Args:
            step_num: Step number (1-6).
            action: Step action type.
            desc_template: Description template.
            task: Task definition.
            test_file: Test file path.
            impl_file: Implementation file path.
            verify_cmd: Verification command.
            include_snippets: Whether to include code snippets.

        Returns:
            Step object.
        """
        step = Step(
            step=step_num,
            action=action,
        )

        # Set step-specific properties
        if action == StepAction.WRITE_TEST:
            step.file = test_file
            step.verify = VerifyMode.NONE
            if include_snippets:
                step.code_snippet = self._generate_test_snippet(task, test_file)

        elif action == StepAction.VERIFY_FAIL:
            step.run = verify_cmd
            step.verify = VerifyMode.EXIT_CODE_NONZERO  # Test must fail

        elif action == StepAction.IMPLEMENT:
            step.file = impl_file
            step.verify = VerifyMode.NONE
            if include_snippets:
                step.code_snippet = self._generate_impl_snippet(task, impl_file)

        elif action == StepAction.VERIFY_PASS:
            step.run = verify_cmd
            step.verify = VerifyMode.EXIT_CODE  # Test must pass

        elif action == StepAction.FORMAT:
            if self.formatter:
                step.run = self.formatter.fix_cmd
            else:
                step.run = "echo 'No formatter detected, skipping'"
            step.verify = VerifyMode.EXIT_CODE

        elif action == StepAction.COMMIT:
            step.run = 'git add -A && git diff --cached --quiet || echo "Changes staged"'
            step.verify = VerifyMode.NONE  # Commit handled by worker protocol

        return step

    def _generate_test_snippet(
        self,
        task: TaskDefinition,
        test_file: str | None,
    ) -> str:
        """Generate a test code snippet.

        Uses ASTAnalyzer if available, otherwise provides a generic template.

        Args:
            task: Task definition.
            test_file: Test file path.

        Returns:
            Test code snippet.
        """
        # Try ASTAnalyzer if available
        if self.ast_analyzer and test_file:
            try:
                patterns = self.ast_analyzer.extract_patterns(Path(test_file))
                if patterns and patterns.imports:
                    # Build snippet from extracted patterns
                    lines = []
                    for imp in patterns.imports[:5]:
                        lines.append(imp.to_import_line())
                    lines.append("")
                    lines.append(f"def test_{self._snake_case(task.title)}():")
                    lines.append(f'    """Test {task.title}."""')
                    lines.append("    # TODO: Implement test")
                    lines.append("    assert False, 'Not implemented'")
                    return "\n".join(lines)
            except Exception:  # noqa: BLE001 — intentional: best-effort AST pattern extraction; falls back to template
                pass  # Fall through to generic template

        # Generic test template
        module_name = self._extract_module_name(task)
        return f'''"""Tests for {task.title}."""

import pytest
from {module_name} import ...  # TODO: Import target


class Test{self._pascal_case(task.title)}:
    """Tests for {task.title}."""

    def test_basic_functionality(self):
        """Test basic functionality."""
        # TODO: Implement test
        assert False, "Not implemented"
'''

    def _generate_impl_snippet(
        self,
        task: TaskDefinition,
        impl_file: str | None,
    ) -> str:
        """Generate an implementation code snippet.

        Uses ASTAnalyzer if available, otherwise provides a generic template.

        Args:
            task: Task definition.
            impl_file: Implementation file path.

        Returns:
            Implementation code snippet.
        """
        # Try ASTAnalyzer if available
        if self.ast_analyzer and impl_file:
            try:
                patterns = self.ast_analyzer.extract_patterns(Path(impl_file))
                if patterns and patterns.imports:
                    lines = []
                    for imp in patterns.imports[:5]:
                        lines.append(imp.to_import_line())
                    lines.append("")
                    lines.append(f"def {self._snake_case(task.title)}():")
                    lines.append(f'    """Implement {task.title}."""')
                    lines.append("    # TODO: Implement")
                    lines.append("    raise NotImplementedError")
                    return "\n".join(lines)
            except Exception:  # noqa: BLE001 — intentional: best-effort AST pattern extraction; falls back to template
                pass  # Fall through to generic template

        # Generic implementation template
        return f'''"""{task.title}

{task.description}
"""

from __future__ import annotations


def {self._snake_case(task.title)}():
    """{task.title}.

    TODO: Implement according to task description.
    """
    raise NotImplementedError("TODO: Implement {task.title}")
'''

    def _extract_module_name(self, task: TaskDefinition) -> str:
        """Extract module name from task files."""
        create_files = task.files.get("create", [])
        modify_files = task.files.get("modify", [])

        for f in create_files + modify_files:
            if f.endswith(".py") and not f.startswith("tests/"):
                # zerg/foo.py -> zerg.foo
                return f.replace("/", ".").replace(".py", "")

        return "module"

    @staticmethod
    def _snake_case(text: str) -> str:
        """Convert text to snake_case identifier."""
        # Remove non-alphanumeric, convert to lowercase
        result = ""
        prev_lower = False
        for c in text:
            if c.isalnum():
                if c.isupper() and prev_lower:
                    result += "_"
                result += c.lower()
                prev_lower = c.islower()
            else:
                if result and not result.endswith("_"):
                    result += "_"
                prev_lower = False
        return result.strip("_")[:50]  # Limit length

    @staticmethod
    def _pascal_case(text: str) -> str:
        """Convert text to PascalCase identifier."""
        words = text.replace("-", " ").replace("_", " ").split()
        return "".join(word.capitalize() for word in words)[:50]


def generate_steps_for_task(
    task: dict[str, Any] | TaskDefinition,
    detail_level: str = "standard",
    project_root: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Convenience function to generate steps for a task.

    Args:
        task: Task definition (dict or TaskDefinition).
        detail_level: Detail level (standard/medium/high).
        project_root: Project root for formatter detection.

    Returns:
        List of step dictionaries for JSON serialization.
    """
    generator = StepGenerator(project_root=project_root)
    steps = generator.generate_steps(task, detail_level)
    return [step.to_dict() for step in steps]
