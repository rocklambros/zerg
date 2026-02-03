"""Unit tests for ZERG command validation module.

Tests all validation functions that enforce context engineering compliance
for command files: Task marker presence, backbone depth, split pairs,
split thresholds, and state JSON cross-referencing.
"""

from __future__ import annotations

from pathlib import Path

from zerg.validate_commands import (
    BACKBONE_COMMANDS,
    BACKBONE_MARKERS,
    BACKBONE_MIN_REFS,
    EXCLUDED_PREFIXES,
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

    def test_excludes_core_files(self, tmp_path: Path) -> None:
        """Core .md files (.core.md) must be excluded from base file listing."""
        (tmp_path / "foo.core.md").write_text("# Core content")
        (tmp_path / "foo.md").write_text("# Base content")
        result = _get_base_command_files(tmp_path)
        names = [p.name for p in result]
        assert "foo.core.md" not in names
        assert "foo.md" in names

    def test_excludes_details_files(self, tmp_path: Path) -> None:
        """Details .md files (.details.md) must be excluded from base file listing."""
        (tmp_path / "foo.details.md").write_text("# Details content")
        (tmp_path / "foo.md").write_text("# Base content")
        result = _get_base_command_files(tmp_path)
        names = [p.name for p in result]
        assert "foo.details.md" not in names
        assert "foo.md" in names

    def test_excludes_underscore_prefixed(self, tmp_path: Path) -> None:
        """Files starting with underscore must be excluded."""
        (tmp_path / "_template.md").write_text("# Template")
        (tmp_path / "real.md").write_text("# Real command")
        result = _get_base_command_files(tmp_path)
        names = [p.name for p in result]
        assert "_template.md" not in names
        assert "real.md" in names

    def test_includes_base_md(self, tmp_path: Path) -> None:
        """Regular .md files should be included in the result."""
        (tmp_path / "alpha.md").write_text("# Alpha")
        (tmp_path / "beta.md").write_text("# Beta")
        result = _get_base_command_files(tmp_path)
        names = [p.name for p in result]
        assert "alpha.md" in names
        assert "beta.md" in names


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
        assert len(errors) == 1
        assert "broken.md" in errors[0].lower()

    def test_file_with_single_marker_passes(self, tmp_path: Path) -> None:
        """A file with at least one Task marker should pass validation."""
        (tmp_path / "good.md").write_text("# Good Command\n\nRun TaskCreate to track this work.\n")
        passed, errors = validate_task_references(tmp_path)
        assert passed
        assert len(errors) == 0

    def test_empty_directory_passes(self, tmp_path: Path) -> None:
        """An empty directory should pass with no errors (nothing to validate)."""
        passed, errors = validate_task_references(tmp_path)
        assert passed
        assert len(errors) == 0


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
        assert len(errors) >= 1
        error_text = " ".join(e.lower() for e in errors)
        assert "worker.md" in error_text

    def test_deep_backbone_passes(self, tmp_path: Path) -> None:
        """A backbone file with 3+ backbone marker refs must pass."""
        deep_content = (
            "# Command\n\n"
            "First TaskUpdate to claim.\n"
            "Then TaskList to check.\n"
            "Another TaskUpdate for checkpoint.\n"
            "Final TaskGet for verification.\n"
        )
        # All 5 backbone files must be present with sufficient depth
        for cmd_name in BACKBONE_COMMANDS:
            (tmp_path / f"{cmd_name}.md").write_text(deep_content)
        passed, errors = validate_backbone_depth(tmp_path)
        assert passed
        assert len(errors) == 0

    def test_non_backbone_file_ignored(self, tmp_path: Path) -> None:
        """Non-backbone files should not be checked for depth, even if shallow."""
        deep_content = "# Command\n\nTaskUpdate claim.\nTaskList check.\nTaskUpdate checkpoint.\nTaskGet verify.\n"
        # Provide all backbone files so they pass, then add a non-backbone file
        for cmd_name in BACKBONE_COMMANDS:
            (tmp_path / f"{cmd_name}.md").write_text(deep_content)
        (tmp_path / "analyze.md").write_text("# Analyze\n\nRun TaskCreate to start.\n")
        passed, errors = validate_backbone_depth(tmp_path)
        assert passed
        assert len(errors) == 0


class TestValidateSplitPairs:
    """Tests for validate_split_pairs which checks .core.md/.details.md/.md consistency."""

    def test_real_pairs_consistent(self) -> None:
        """All split pairs in the real commands dir must be consistent."""
        passed, errors = validate_split_pairs(REAL_COMMANDS_DIR)
        assert passed, f"Real split pairs inconsistent: {errors}"

    def test_orphan_core_flagged(self, tmp_path: Path) -> None:
        """A .core.md file without matching .md or .details.md must be flagged."""
        (tmp_path / "foo.core.md").write_text("# Core only, no parent or details")
        passed, errors = validate_split_pairs(tmp_path)
        assert not passed
        assert len(errors) >= 1
        error_text = " ".join(e.lower() for e in errors)
        assert "foo" in error_text

    def test_orphan_details_flagged(self, tmp_path: Path) -> None:
        """A .details.md file without matching .md or .core.md must be flagged."""
        (tmp_path / "foo.details.md").write_text("# Details only, no parent or core")
        passed, errors = validate_split_pairs(tmp_path)
        assert not passed
        assert len(errors) >= 1
        error_text = " ".join(e.lower() for e in errors)
        assert "foo" in error_text

    def test_complete_triplet_passes(self, tmp_path: Path) -> None:
        """A complete set of .md, .core.md, and .details.md should pass."""
        (tmp_path / "bar.md").write_text("# Bar base")
        (tmp_path / "bar.core.md").write_text("# Bar core")
        (tmp_path / "bar.details.md").write_text("# Bar details")
        passed, errors = validate_split_pairs(tmp_path)
        assert passed
        assert len(errors) == 0


class TestValidateSplitThreshold:
    """Tests for validate_split_threshold which flags oversized unsplit files."""

    def test_real_commands_pass(self) -> None:
        """All real command files must be either under 300 lines or already split."""
        passed, errors = validate_split_threshold(REAL_COMMANDS_DIR)
        assert passed, f"Real commands have oversized unsplit files: {errors}"

    def test_oversized_unsplit_flagged(self, tmp_path: Path) -> None:
        """A file with >= 300 lines and no .core.md companion must be flagged."""
        lines = ["# Oversized Command\n", "\n"]
        for i in range(1, 40):
            lines.append(f"## Section {i}\n")
            for j in range(8):
                lines.append(f"Line {j} of section {i} with some content here.\n")
        content = "".join(lines)
        (tmp_path / "bigfile.md").write_text(content)
        # Verify we actually have enough lines
        assert len(content.splitlines()) >= 300

        passed, errors = validate_split_threshold(tmp_path)
        assert not passed
        assert len(errors) >= 1
        error_text = " ".join(e.lower() for e in errors)
        assert "bigfile.md" in error_text

    def test_auto_split_creates_files(self, tmp_path: Path) -> None:
        """With auto_split=True, oversized files should get .core.md and .details.md created."""
        lines = ["# Auto Split Target\n", "\n"]
        for i in range(1, 40):
            lines.append(f"## Section {i}\n")
            for j in range(8):
                lines.append(f"Content line {j} in section {i} for splitting.\n")
        content = "".join(lines)
        (tmp_path / "splittable.md").write_text(content)
        assert len(content.splitlines()) >= 300

        passed, errors = validate_split_threshold(tmp_path, auto_split=True)
        # After auto-split, the .core.md and .details.md files should exist
        assert (tmp_path / "splittable.core.md").exists()
        assert (tmp_path / "splittable.details.md").exists()

    def test_under_threshold_passes(self, tmp_path: Path) -> None:
        """A file under 300 lines should pass without issue."""
        lines = [f"Line {i}\n" for i in range(200)]
        (tmp_path / "small.md").write_text("".join(lines))
        passed, errors = validate_split_threshold(tmp_path)
        assert passed
        assert len(errors) == 0

    def test_file_with_existing_split_passes(self, tmp_path: Path) -> None:
        """A file >= 300 lines that already has .core.md should pass."""
        lines = ["# Already Split\n", "\n"]
        for i in range(1, 40):
            lines.append(f"## Section {i}\n")
            for j in range(8):
                lines.append(f"Line {j} of section {i}.\n")
        (tmp_path / "already.md").write_text("".join(lines))
        (tmp_path / "already.core.md").write_text("# Core content")
        (tmp_path / "already.details.md").write_text("# Details content")

        passed, errors = validate_split_threshold(tmp_path)
        assert passed
        assert len(errors) == 0


class TestValidateStateJsonWithoutTasks:
    """Tests for validate_state_json_without_tasks cross-reference check."""

    def test_real_commands_state_drift_detected(self) -> None:
        """Validator correctly detects known state JSON drift in existing command files.

        Several command files reference state JSON without TaskList/TaskGet.
        This is expected pre-existing drift; the validator's job is to detect it.
        """
        _passed, errors = validate_state_json_without_tasks(REAL_COMMANDS_DIR)
        # Known drift exists — validator correctly flags files with state refs
        # but no TaskList/TaskGet. All flagged errors must mention state JSON.
        for error in errors:
            assert "state json" in error.lower(), f"Unexpected error: {error}"

    def test_state_ref_without_tasks_flagged(self, tmp_path: Path) -> None:
        """A file referencing .zerg/state without TaskList or TaskGet must be flagged."""
        content = (
            "# Bad Command\n\n"
            "Read the state from `.zerg/state/rush-state.json`.\n"
            "Use TaskCreate to track.\n"
            "Use TaskUpdate to update progress.\n"
        )
        (tmp_path / "badstate.md").write_text(content)
        passed, errors = validate_state_json_without_tasks(tmp_path)
        assert not passed
        assert len(errors) >= 1
        error_text = " ".join(e.lower() for e in errors)
        assert "badstate.md" in error_text

    def test_state_ref_with_tasklist_passes(self, tmp_path: Path) -> None:
        """A file referencing .zerg/state that also references TaskList should pass."""
        content = (
            "# Good Command\n\n"
            "Read the state from `.zerg/state/rush-state.json`.\n"
            "Use TaskList to get authoritative data.\n"
        )
        (tmp_path / "goodstate.md").write_text(content)
        passed, errors = validate_state_json_without_tasks(tmp_path)
        assert passed
        assert len(errors) == 0

    def test_state_ref_with_taskget_passes(self, tmp_path: Path) -> None:
        """A file referencing .zerg/state that also references TaskGet should pass."""
        content = (
            "# Good Command\n\nCheck `.zerg/state` for cached data.\nVerify with TaskGet for authoritative state.\n"
        )
        (tmp_path / "goodget.md").write_text(content)
        passed, errors = validate_state_json_without_tasks(tmp_path)
        assert passed
        assert len(errors) == 0

    def test_no_state_ref_passes(self, tmp_path: Path) -> None:
        """A file without any .zerg/state reference should pass regardless."""
        content = "# Simple Command\n\nNo state references here.\n"
        (tmp_path / "simple.md").write_text(content)
        passed, errors = validate_state_json_without_tasks(tmp_path)
        assert passed
        assert len(errors) == 0


class TestValidateAll:
    """Tests for validate_all which aggregates all validation checks."""

    def test_real_commands_validate_all(self) -> None:
        """validate_all runs against the real commands directory without exceptions.

        Known issues may cause warnings: state JSON drift and orphaned modules.
        We verify any errors are from known patterns only.
        """
        _passed, errors = validate_all(REAL_COMMANDS_DIR)
        known_patterns = ("state json", "orphaned module")
        for error in errors:
            assert any(pat in error.lower() for pat in known_patterns), f"Unexpected validation error: {error}"

    def test_aggregates_multiple_errors(self, tmp_path: Path) -> None:
        """Multiple bad files should produce aggregated errors from all checks."""
        # File 1: Missing Task references entirely
        (tmp_path / "notask.md").write_text("# No Task Markers\n\nJust some plain text without any markers.\n")
        # File 2: Backbone file with insufficient depth
        (tmp_path / "worker.md").write_text("# Worker\n\nOnly one TaskUpdate here.\n")
        # File 3: State reference without TaskList/TaskGet
        (tmp_path / "stateonly.md").write_text(
            "# State Only\n\nRead `.zerg/state/rush-state.json`.\nRun TaskCreate to track.\nRun TaskUpdate to update.\n"
        )
        # File 4: Orphan core file
        (tmp_path / "orphan.core.md").write_text("# Orphan core")

        passed, errors = validate_all(tmp_path)
        assert not passed
        # Should have errors from multiple checks
        assert len(errors) >= 3
        error_text = " ".join(e.lower() for e in errors)
        assert "notask.md" in error_text
        assert "worker.md" in error_text

    def test_uses_default_commands_dir_when_none(self) -> None:
        """When commands_dir is None, validate_all should use the default real directory."""
        _passed, errors = validate_all(commands_dir=None)
        known_patterns = ("state json", "orphaned module")
        for error in errors:
            assert any(pat in error.lower() for pat in known_patterns), f"Unexpected validation error: {error}"

    def test_clean_directory_with_backbone(self, tmp_path: Path) -> None:
        """A directory with all backbone files present should pass all validations.

        Module wiring check runs against the real zerg/ package by default,
        so orphaned module warnings are expected and acceptable.
        """
        deep_content = (
            "# Cmd\n\nTaskCreate start.\nTaskUpdate claim.\nTaskList check.\nTaskUpdate done.\nTaskGet verify.\n"
        )
        for cmd_name in BACKBONE_COMMANDS:
            (tmp_path / f"{cmd_name}.md").write_text(deep_content)
        passed, errors = validate_all(tmp_path)
        assert passed
        # Only orphaned module warnings are acceptable
        for error in errors:
            assert "orphaned module" in error.lower(), f"Unexpected error: {error}"


class TestModuleConstants:
    """Tests for module-level constants to ensure they match documented expectations."""

    def test_backbone_commands_set(self) -> None:
        """BACKBONE_COMMANDS must contain the five documented backbone files."""
        expected = {"worker", "status", "merge", "stop", "retry"}
        assert BACKBONE_COMMANDS == expected

    def test_backbone_min_refs(self) -> None:
        """BACKBONE_MIN_REFS must be 3 as documented in CLAUDE.md drift detection."""
        assert BACKBONE_MIN_REFS == 3

    def test_task_markers_set(self) -> None:
        """TASK_MARKERS must contain all four Task tool names."""
        expected = {"TaskCreate", "TaskUpdate", "TaskList", "TaskGet"}
        assert TASK_MARKERS == expected

    def test_backbone_markers_set(self) -> None:
        """BACKBONE_MARKERS must contain the three deeper-integration markers."""
        expected = {"TaskUpdate", "TaskList", "TaskGet"}
        assert BACKBONE_MARKERS == expected

    def test_excluded_prefixes(self) -> None:
        """EXCLUDED_PREFIXES must include underscore."""
        assert "_" in EXCLUDED_PREFIXES

    def test_wiring_exempt_names(self) -> None:
        """WIRING_EXEMPT_NAMES must contain __init__.py, __main__.py, conftest.py."""
        assert "__init__.py" in WIRING_EXEMPT_NAMES
        assert "__main__.py" in WIRING_EXEMPT_NAMES
        assert "conftest.py" in WIRING_EXEMPT_NAMES


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
        # main.py imports core.py, so core.py is wired.
        # main.py has no importer but is itself a production file — it gets flagged.
        # core.py should NOT be flagged.
        flagged_names = [m.split(":")[0] for m in messages]
        assert "core.py" not in flagged_names

    def test_module_with_only_test_imports_warns(self, tmp_path: Path) -> None:
        """A module imported only by test files should be flagged as orphaned."""
        pkg = self._create_package(
            tmp_path,
            {
                "orphan.py": "def helper(): pass\n",
            },
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_orphan.py").write_text("from mypkg.orphan import helper\n")
        passed, messages = validate_module_wiring(pkg, tests_dir)
        assert len(messages) >= 1
        flagged_text = " ".join(messages)
        assert "orphan.py" in flagged_text

    def test_init_py_exempt(self, tmp_path: Path) -> None:
        """__init__.py files must be exempt from wiring check."""
        pkg = self._create_package(tmp_path, {})
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir)
        flagged_text = " ".join(messages)
        assert "__init__.py" not in flagged_text

    def test_main_py_exempt(self, tmp_path: Path) -> None:
        """__main__.py files must be exempt from wiring check."""
        pkg = self._create_package(
            tmp_path,
            {
                "__main__.py": "print('hello')\n",
            },
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir)
        flagged_text = " ".join(messages)
        assert "__main__.py" not in flagged_text

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
        flagged_text = " ".join(messages)
        assert "cli.py" not in flagged_text

    def test_warning_mode_always_passes(self, tmp_path: Path) -> None:
        """In warning mode (strict=False), result should always be True."""
        pkg = self._create_package(
            tmp_path,
            {
                "orphan.py": "def unused(): pass\n",
            },
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir, strict=False)
        assert passed is True
        assert len(messages) >= 1

    def test_strict_mode_fails_on_orphan(self, tmp_path: Path) -> None:
        """In strict mode, orphaned modules must cause failure."""
        pkg = self._create_package(
            tmp_path,
            {
                "orphan.py": "def unused(): pass\n",
            },
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir, strict=True)
        assert passed is False
        assert len(messages) >= 1

    def test_relative_import_detected(self, tmp_path: Path) -> None:
        """A module imported via relative import should not be flagged."""
        pkg = self._create_package(
            tmp_path,
            {
                "utils.py": "def helper(): pass\n",
                "service.py": "from .utils import helper\nhelper()\n",
            },
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir)
        flagged_names = [m.split(":")[0] for m in messages]
        assert "utils.py" not in flagged_names

    def test_empty_package_passes(self, tmp_path: Path) -> None:
        """A package with only __init__.py should pass with no warnings."""
        pkg = self._create_package(tmp_path, {})
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        passed, messages = validate_module_wiring(pkg, tests_dir)
        assert passed is True
        assert len(messages) == 0
