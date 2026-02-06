"""Unit tests for ZERG command validation module.

Tests all validation functions that enforce context engineering compliance
for command files: Task marker presence, backbone depth, split pairs,
split thresholds, and state JSON cross-referencing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zerg.validate_commands import (
    BACKBONE_COMMANDS,
    BACKBONE_MARKERS,
    BACKBONE_MIN_REFS,
    TASK_MARKERS,
    WIRING_EXEMPT_NAMES,
    _get_base_command_files,
    validate_all,
    validate_backbone_depth,
    validate_module_wiring,
    validate_split_pairs,
    validate_split_threshold,
    validate_state_json_without_tasks,
    validate_task_references,
)

REAL_COMMANDS_DIR = Path(__file__).resolve().parents[2] / "zerg" / "data" / "commands"


class TestGetBaseCommandFiles:
    """Tests for _get_base_command_files helper."""

    @pytest.mark.parametrize(
        "excluded_name,base_name",
        [
            ("foo.core.md", "foo.md"),
            ("foo.details.md", "foo.md"),
            ("_template.md", "real.md"),
        ],
        ids=["core", "details", "underscore"],
    )
    def test_excludes_non_base_files(self, tmp_path: Path, excluded_name: str, base_name: str) -> None:
        """Non-base files (.core.md, .details.md, underscore-prefixed) must be excluded."""
        (tmp_path / excluded_name).write_text("# Excluded")
        (tmp_path / base_name).write_text("# Base content")
        result = _get_base_command_files(tmp_path)
        names = [p.name for p in result]
        assert excluded_name not in names
        assert base_name in names


class TestValidateTaskReferences:
    """Tests for validate_task_references which checks Task marker presence."""

    def test_all_real_commands_have_refs(self) -> None:
        """Every base command file in the real commands dir must have at least one Task marker."""
        passed, errors = validate_task_references(REAL_COMMANDS_DIR)
        assert passed, f"Real commands missing Task references: {errors}"

    def test_missing_ref_flagged(self, tmp_path: Path) -> None:
        """A command file without any Task marker must be flagged as an error."""
        (tmp_path / "broken.md").write_text("# Broken Command\n\nThis file has no task markers at all.\n")
        passed, errors = validate_task_references(tmp_path)
        assert not passed
        assert "broken.md" in errors[0].lower()

    def test_empty_directory_passes(self, tmp_path: Path) -> None:
        """An empty directory should pass with no errors."""
        passed, errors = validate_task_references(tmp_path)
        assert passed


class TestValidateBackboneDepth:
    """Tests for validate_backbone_depth which checks backbone files have >= 3 deep refs."""

    def test_real_backbone_passes(self) -> None:
        """All backbone files in the real commands dir must have sufficient Task depth."""
        passed, errors = validate_backbone_depth(REAL_COMMANDS_DIR)
        assert passed, f"Real backbone files insufficient depth: {errors}"

    def test_shallow_backbone_flagged(self, tmp_path: Path) -> None:
        """A backbone file with fewer than 3 backbone marker refs must be flagged."""
        (tmp_path / "worker.md").write_text("# Worker Command\n\nUse TaskUpdate to claim the task.\n")
        passed, errors = validate_backbone_depth(tmp_path)
        assert not passed
        assert "worker.md" in " ".join(e.lower() for e in errors)

    def test_deep_backbone_passes(self, tmp_path: Path) -> None:
        """A backbone file with 3+ backbone marker refs must pass."""
        deep_content = "# Cmd\n\nTaskUpdate claim.\nTaskList check.\nTaskUpdate checkpoint.\nTaskGet verify.\n"
        for cmd_name in BACKBONE_COMMANDS:
            (tmp_path / f"{cmd_name}.md").write_text(deep_content)
        passed, errors = validate_backbone_depth(tmp_path)
        assert passed


class TestValidateSplitPairs:
    """Tests for validate_split_pairs which checks .core.md/.details.md/.md consistency."""

    def test_real_pairs_consistent(self) -> None:
        """All split pairs in the real commands dir must be consistent."""
        passed, errors = validate_split_pairs(REAL_COMMANDS_DIR)
        assert passed, f"Real split pairs inconsistent: {errors}"

    @pytest.mark.parametrize(
        "orphan_name",
        ["foo.core.md", "foo.details.md"],
        ids=["orphan-core", "orphan-details"],
    )
    def test_orphan_split_file_flagged(self, tmp_path: Path, orphan_name: str) -> None:
        """A .core.md or .details.md without matching counterpart must be flagged."""
        (tmp_path / orphan_name).write_text("# Orphan")
        passed, errors = validate_split_pairs(tmp_path)
        assert not passed
        assert "foo" in " ".join(e.lower() for e in errors)

    def test_complete_triplet_passes(self, tmp_path: Path) -> None:
        """A complete set of .md, .core.md, and .details.md should pass."""
        (tmp_path / "bar.md").write_text("# Bar base")
        (tmp_path / "bar.core.md").write_text("# Bar core")
        (tmp_path / "bar.details.md").write_text("# Bar details")
        passed, errors = validate_split_pairs(tmp_path)
        assert passed


class TestValidateSplitThreshold:
    """Tests for validate_split_threshold which flags oversized unsplit files."""

    def _make_oversized(self, tmp_path: Path, name: str) -> str:
        """Create a file with >= 300 lines."""
        lines = ["# Oversized\n", "\n"]
        for i in range(1, 40):
            lines.append(f"## Section {i}\n")
            for j in range(8):
                lines.append(f"Line {j} of section {i} with some content here.\n")
        content = "".join(lines)
        (tmp_path / name).write_text(content)
        return content

    def test_real_commands_pass(self) -> None:
        """All real command files must be either under 300 lines or already split."""
        passed, errors = validate_split_threshold(REAL_COMMANDS_DIR)
        assert passed, f"Real commands have oversized unsplit files: {errors}"

    def test_oversized_unsplit_flagged(self, tmp_path: Path) -> None:
        """A file with >= 300 lines and no .core.md companion must be flagged."""
        self._make_oversized(tmp_path, "bigfile.md")
        passed, errors = validate_split_threshold(tmp_path)
        assert not passed
        assert "bigfile.md" in " ".join(e.lower() for e in errors)

    def test_auto_split_creates_files(self, tmp_path: Path) -> None:
        """With auto_split=True, oversized files should get .core.md and .details.md created."""
        self._make_oversized(tmp_path, "splittable.md")
        validate_split_threshold(tmp_path, auto_split=True)
        assert (tmp_path / "splittable.core.md").exists()
        assert (tmp_path / "splittable.details.md").exists()


class TestValidateStateJsonWithoutTasks:
    """Tests for validate_state_json_without_tasks cross-reference check."""

    def test_state_ref_without_tasks_flagged(self, tmp_path: Path) -> None:
        """A file referencing .zerg/state without TaskList or TaskGet must be flagged."""
        content = (
            "# Bad Command\n\n"
            "Read the state from `.zerg/state/rush-state.json`.\n"
            "Use TaskCreate to track.\nUse TaskUpdate to update progress.\n"
        )
        (tmp_path / "badstate.md").write_text(content)
        passed, errors = validate_state_json_without_tasks(tmp_path)
        assert not passed
        assert "badstate.md" in " ".join(e.lower() for e in errors)

    @pytest.mark.parametrize(
        "task_ref",
        ["TaskList", "TaskGet"],
        ids=["tasklist", "taskget"],
    )
    def test_state_ref_with_task_query_passes(self, tmp_path: Path, task_ref: str) -> None:
        """A file referencing .zerg/state that also references TaskList/TaskGet should pass."""
        content = f"# Cmd\n\nRead `.zerg/state/rush-state.json`.\nUse {task_ref} for auth data.\n"
        (tmp_path / "good.md").write_text(content)
        passed, errors = validate_state_json_without_tasks(tmp_path)
        assert passed


class TestValidateAll:
    """Tests for validate_all which aggregates all validation checks."""

    def test_real_commands_validate_all(self) -> None:
        """validate_all runs against the real commands directory without exceptions."""
        _passed, errors = validate_all(REAL_COMMANDS_DIR)
        known_patterns = ("state json", "orphaned module", "missing required section")
        for error in errors:
            assert any(pat in error.lower() for pat in known_patterns), f"Unexpected validation error: {error}"

    def test_aggregates_multiple_errors(self, tmp_path: Path) -> None:
        """Multiple bad files should produce aggregated errors from all checks."""
        (tmp_path / "notask.md").write_text("# No Task Markers\n\nJust some plain text.\n")
        (tmp_path / "worker.md").write_text("# Worker\n\nOnly one TaskUpdate here.\n")
        (tmp_path / "orphan.core.md").write_text("# Orphan core")
        passed, errors = validate_all(tmp_path)
        assert not passed
        assert len(errors) >= 3


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_core_constants(self) -> None:
        """All module constants must match documented expectations."""
        assert BACKBONE_COMMANDS == {"worker", "status", "merge", "stop", "retry"}
        assert TASK_MARKERS == {"TaskCreate", "TaskUpdate", "TaskList", "TaskGet"}
        assert BACKBONE_MARKERS == {"TaskUpdate", "TaskList", "TaskGet"}
        assert BACKBONE_MIN_REFS == 3
        for name in ("__init__.py", "__main__.py", "conftest.py"):
            assert name in WIRING_EXEMPT_NAMES


class TestValidateModuleWiring:
    """Tests for validate_module_wiring which detects orphaned modules."""

    def _create_package(self, tmp_path: Path, files: dict[str, str]) -> Path:
        """Create a fake package directory with given files and contents."""
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        for filename, content in files.items():
            filepath = pkg_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
        return pkg_dir

    def test_module_with_production_import_passes(self, tmp_path: Path) -> None:
        """A module imported by another production module should not be flagged."""
        pkg = self._create_package(
            tmp_path,
            {
                "core.py": "def do_stuff(): pass\n",
                "main.py": "from mypkg.core import do_stuff\ndo_stuff()\n",
            },
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir)
        flagged_names = [m.split(":")[0] for m in messages]
        assert "core.py" not in flagged_names

    def test_module_with_only_test_imports_warns(self, tmp_path: Path) -> None:
        """A module imported only by test files should be flagged as orphaned."""
        pkg = self._create_package(tmp_path, {"orphan.py": "def helper(): pass\n"})
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_orphan.py").write_text("from mypkg.orphan import helper\n")
        passed, messages = validate_module_wiring(pkg, tests_dir)
        assert "orphan.py" in " ".join(messages)

    @pytest.mark.parametrize(
        "strict,expect_pass",
        [(False, True), (True, False)],
        ids=["warning-mode", "strict-mode"],
    )
    def test_strict_vs_warning_mode(self, tmp_path: Path, strict: bool, expect_pass: bool) -> None:
        """Warning mode always passes, strict mode fails on orphans."""
        pkg = self._create_package(tmp_path, {"orphan.py": "def unused(): pass\n"})
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir, strict=strict)
        assert passed is expect_pass
        assert len(messages) >= 1

    @pytest.mark.parametrize(
        "exempt_file",
        ["__init__.py", "__main__.py"],
        ids=["init", "main"],
    )
    def test_exempt_files_not_flagged(self, tmp_path: Path, exempt_file: str) -> None:
        """Exempt files must not be flagged by wiring check."""
        files = {}
        if exempt_file == "__main__.py":
            files["__main__.py"] = "print('hello')\n"
        pkg = self._create_package(tmp_path, files)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir)
        assert exempt_file not in " ".join(messages)

    def test_entry_point_with_name_guard_exempt(self, tmp_path: Path) -> None:
        """Files containing 'if __name__' must be exempt."""
        pkg = self._create_package(
            tmp_path,
            {
                "cli.py": "def main(): pass\nif __name__ == '__main__':\n    main()\n",
            },
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir)
        assert "cli.py" not in " ".join(messages)
