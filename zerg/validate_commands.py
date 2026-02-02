"""ZERG command file validation for context engineering and Task ecosystem integrity.

Codifies the drift detection checklist from CLAUDE.md to ensure all command
files maintain proper Task ecosystem integration and context engineering
compliance (split pairs, thresholds, state JSON references).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from zerg.command_splitter import MIN_LINES_TO_SPLIT, CommandSplitter

# Backbone commands require deeper Task integration
BACKBONE_COMMANDS: set[str] = {"worker", "status", "merge", "stop", "retry"}

# Minimum Task tool references for backbone files (TaskUpdate|TaskList|TaskGet, not TaskCreate)
BACKBONE_MIN_REFS: int = 3

# All Task ecosystem markers
TASK_MARKERS: set[str] = {"TaskCreate", "TaskUpdate", "TaskList", "TaskGet"}

# Backbone-specific markers (deeper integration, excludes TaskCreate)
BACKBONE_MARKERS: set[str] = {"TaskUpdate", "TaskList", "TaskGet"}

# Pattern matching state JSON references in command files
STATE_PATTERNS: re.Pattern[str] = re.compile(r"state.*json|STATE_FILE|\.zerg/state")

# Prefixes to exclude from base command file scanning
EXCLUDED_PREFIXES: tuple[str, ...] = ("_",)

# Default commands directory relative to this package
DEFAULT_COMMANDS_DIR: Path = Path(__file__).parent / "data" / "commands"


def _get_base_command_files(commands_dir: Path) -> list[Path]:
    """Return base command .md files, excluding .core.md, .details.md, and _ prefixed.

    Args:
        commands_dir: Path to the commands directory.

    Returns:
        Sorted list of base command file paths.
    """
    results: list[Path] = []
    for md_file in sorted(commands_dir.glob("*.md")):
        name = md_file.name

        # Skip split fragments
        if ".core.md" in name or ".details.md" in name:
            continue

        # Skip excluded prefixes
        if any(name.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            continue

        results.append(md_file)

    return results


def validate_task_references(commands_dir: Path) -> tuple[bool, list[str]]:
    """Verify every base command file contains at least one Task ecosystem marker.

    Each command file must reference TaskCreate, TaskUpdate, TaskList, or TaskGet
    to maintain Task ecosystem integration.

    Args:
        commands_dir: Path to the commands directory.

    Returns:
        Tuple of (all_valid, list of error messages).
    """
    errors: list[str] = []
    base_files = _get_base_command_files(commands_dir)

    for filepath in base_files:
        content = filepath.read_text()
        found = any(marker in content for marker in TASK_MARKERS)
        if not found:
            errors.append(
                f"{filepath.name}: missing Task ecosystem references "
                f"(needs at least one of {', '.join(sorted(TASK_MARKERS))})"
            )

    return not errors, errors


def validate_backbone_depth(commands_dir: Path) -> tuple[bool, list[str]]:
    """Verify backbone command files have sufficient Task integration depth.

    Backbone files (worker, status, merge, stop, retry) must have at least
    BACKBONE_MIN_REFS occurrences of TaskUpdate, TaskList, or TaskGet to
    ensure deeper coordination capability beyond simple tracking.

    Args:
        commands_dir: Path to the commands directory.

    Returns:
        Tuple of (all_valid, list of error messages).
    """
    errors: list[str] = []

    for cmd_name in sorted(BACKBONE_COMMANDS):
        filepath = commands_dir / f"{cmd_name}.md"
        if not filepath.exists():
            errors.append(f"{cmd_name}.md: backbone file not found")
            continue

        content = filepath.read_text()
        ref_count = sum(content.count(marker) for marker in BACKBONE_MARKERS)

        if ref_count < BACKBONE_MIN_REFS:
            errors.append(
                f"{cmd_name}.md: only {ref_count} Task references "
                f"(minimum {BACKBONE_MIN_REFS})"
            )

    return not errors, errors


def validate_split_pairs(commands_dir: Path) -> tuple[bool, list[str]]:
    """Verify split file pairs are complete and consistent.

    For every .core.md file, a matching .details.md and parent .md must exist.
    For every .details.md file, a matching .core.md and parent .md must exist.

    Args:
        commands_dir: Path to the commands directory.

    Returns:
        Tuple of (all_valid, list of error messages).
    """
    errors: list[str] = []

    core_files = sorted(commands_dir.glob("*.core.md"))
    details_files = sorted(commands_dir.glob("*.details.md"))

    # Check each .core.md has matching .details.md and parent .md
    for core_path in core_files:
        stem = core_path.name.replace(".core.md", "")
        details_path = commands_dir / f"{stem}.details.md"
        parent_path = commands_dir / f"{stem}.md"

        if not details_path.exists():
            errors.append(
                f"{core_path.name}: orphaned core file, "
                f"missing {stem}.details.md"
            )
        if not parent_path.exists():
            errors.append(
                f"{core_path.name}: orphaned core file, "
                f"missing parent {stem}.md"
            )

    # Check each .details.md has matching .core.md and parent .md
    for details_path in details_files:
        stem = details_path.name.replace(".details.md", "")
        core_path = commands_dir / f"{stem}.core.md"
        parent_path = commands_dir / f"{stem}.md"

        if not core_path.exists():
            errors.append(
                f"{details_path.name}: orphaned details file, "
                f"missing {stem}.core.md"
            )
        if not parent_path.exists():
            errors.append(
                f"{details_path.name}: orphaned details file, "
                f"missing parent {stem}.md"
            )

    return not errors, errors


def validate_split_threshold(
    commands_dir: Path, auto_split: bool = False
) -> tuple[bool, list[str]]:
    """Verify large command files have been split for context optimization.

    Base .md files with line count >= MIN_LINES_TO_SPLIT should have a
    corresponding .core.md file. If auto_split is True, missing splits
    are created automatically and reported as informational messages.

    Args:
        commands_dir: Path to the commands directory.
        auto_split: If True, auto-split oversized files instead of erroring.

    Returns:
        Tuple of (all_valid, list of error/info messages).
    """
    errors: list[str] = []
    base_files = _get_base_command_files(commands_dir)

    for filepath in base_files:
        content = filepath.read_text()
        line_count = content.count("\n") + 1

        if line_count < MIN_LINES_TO_SPLIT:
            continue

        core_path = commands_dir / f"{filepath.stem}.core.md"
        if core_path.exists():
            continue

        if auto_split:
            splitter = CommandSplitter(commands_dir)
            core, details = splitter.split_file(filepath)
            errors.append(
                f"{filepath.name}: auto-split into {core.name} and {details.name} "
                f"({line_count} lines)"
            )
        else:
            errors.append(
                f"{filepath.name}: {line_count} lines >= {MIN_LINES_TO_SPLIT} "
                f"threshold but no .core.md split exists"
            )

    # When auto_split is used, messages are informational, not failures
    if auto_split:
        return True, errors

    return not errors, errors


def validate_state_json_without_tasks(commands_dir: Path) -> tuple[bool, list[str]]:
    """Verify files referencing state JSON also reference TaskList or TaskGet.

    State JSON (.zerg/state/) is supplementary to the Task ecosystem. Any
    command file that reads state JSON without also consulting TaskList/TaskGet
    indicates drift from the Task-as-source-of-truth architecture.

    Args:
        commands_dir: Path to the commands directory.

    Returns:
        Tuple of (all_valid, list of error messages).
    """
    errors: list[str] = []

    # Scan ALL .md files including .core.md and .details.md
    for md_file in sorted(commands_dir.glob("*.md")):
        # Skip excluded prefixes
        if any(md_file.name.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            continue

        content = md_file.read_text()

        has_state_ref = bool(STATE_PATTERNS.search(content))
        has_task_query = "TaskList" in content or "TaskGet" in content

        if has_state_ref and not has_task_query:
            errors.append(
                f"{md_file.name}: references state JSON but has no "
                f"TaskList/TaskGet (state JSON must not be sole data source)"
            )

    return not errors, errors


def validate_rules(rules_dir: Path | None = None) -> tuple[bool, list[str]]:
    """Validate engineering rule files in rules directory.

    Args:
        rules_dir: Path to rules directory. Defaults to .zerg/rules/

    Returns:
        Tuple of (all_valid, list of error messages).
    """
    if rules_dir is None:
        rules_dir = Path(".zerg/rules")

    if not rules_dir.exists():
        return True, ["No rules directory found (optional)"]

    errors: list[str] = []

    try:
        from zerg.rules import RuleLoader, RuleValidator

        loader = RuleLoader(rules_dir)
        validator = RuleValidator()
        rulesets = loader.load_all()

        for ruleset in rulesets:
            result = validator.validate_ruleset(ruleset)
            if not result.valid:
                errors.extend(result.errors)
    except ImportError:
        return True, ["Rules module not available"]
    except Exception as e:
        errors.append(f"Rules validation error: {e}")

    return not errors, errors


def validate_all(
    commands_dir: Path | None = None, auto_split: bool = False
) -> tuple[bool, list[str]]:
    """Run all command validation checks and aggregate results.

    Args:
        commands_dir: Path to the commands directory. Defaults to package location.
        auto_split: If True, auto-split oversized files during threshold check.

    Returns:
        Tuple of (all_passed, list of all error messages across checks).
    """
    if commands_dir is None:
        commands_dir = DEFAULT_COMMANDS_DIR

    all_errors: list[str] = []
    all_passed = True

    checks: list[tuple[str, tuple[bool, list[str]]]] = [
        ("Task references", validate_task_references(commands_dir)),
        ("Backbone depth", validate_backbone_depth(commands_dir)),
        ("Split pairs", validate_split_pairs(commands_dir)),
        (
            "Split threshold",
            validate_split_threshold(commands_dir, auto_split=auto_split),
        ),
        ("State JSON", validate_state_json_without_tasks(commands_dir)),
        ("Engineering rules", validate_rules()),
    ]

    base_count = len(_get_base_command_files(commands_dir))
    backbone_count = len(BACKBONE_COMMANDS)
    core_count = len(list(commands_dir.glob("*.core.md")))

    descriptions: dict[str, str] = {
        "Task references": f"all {base_count} command files have Task markers",
        "Backbone depth": (
            f"all {backbone_count} backbone files have >= {BACKBONE_MIN_REFS} refs"
        ),
        "Split pairs": f"all {core_count} pairs consistent",
        "Split threshold": "no oversized unsplit files",
        "State JSON": "no files reference state without TaskList/TaskGet",
        "Engineering rules": "all rule files valid",
    }

    fail_count = 0

    for name, (passed, errors) in checks:
        if passed:
            print(f"[PASS] {name}: {descriptions[name]}")
        else:
            error_count = len(errors)
            print(f"[FAIL] {name}: {error_count} error{'s' if error_count != 1 else ''}")
            for error in errors:
                print(f"  - {error}")
            all_passed = False
            fail_count += 1

        all_errors.extend(errors)

    print()
    if all_passed:
        print("All checks passed.")
    else:
        print(f"{fail_count} check{'s' if fail_count != 1 else ''} failed.")

    return all_passed, all_errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate ZERG command files for Task ecosystem integrity "
        "and context engineering compliance."
    )
    parser.add_argument(
        "--auto-split",
        action="store_true",
        help="Automatically split oversized files instead of reporting errors.",
    )
    parser.add_argument(
        "--commands-dir",
        type=Path,
        default=None,
        help="Path to commands directory. Defaults to zerg/data/commands/.",
    )

    args = parser.parse_args()
    passed, _ = validate_all(
        commands_dir=args.commands_dir, auto_split=args.auto_split
    )
    sys.exit(0 if passed else 1)
