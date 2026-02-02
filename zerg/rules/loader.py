"""Rule loading and filtering for the ZERG engineering rules framework."""

from __future__ import annotations

import enum
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from zerg.logging import get_logger

logger = get_logger("rules.loader")


class RulePriority(enum.Enum):
    """Priority levels for engineering rules."""

    CRITICAL = "critical"
    IMPORTANT = "important"
    RECOMMENDED = "recommended"


@dataclass
class Rule:
    """A single engineering rule."""

    id: str
    title: str
    description: str = ""
    priority: RulePriority = RulePriority.RECOMMENDED
    category: str = "general"
    applies_to: list[str] = field(default_factory=lambda: ["*"])
    enabled: bool = True


@dataclass
class RuleSet:
    """A named collection of engineering rules."""

    name: str
    description: str = ""
    rules: list[Rule] = field(default_factory=list)
    version: str = "1.0"


def _parse_priority(value: str) -> RulePriority:
    """Parse a priority string into a RulePriority enum.

    Args:
        value: Priority string (case-insensitive).

    Returns:
        Corresponding RulePriority enum member.

    Raises:
        ValueError: If the value is not a valid priority.
    """
    try:
        return RulePriority(value.lower())
    except ValueError:
        valid = ", ".join(p.value for p in RulePriority)
        raise ValueError(f"Invalid priority '{value}'. Valid values: {valid}") from None


def _parse_rule(data: dict[str, Any]) -> Rule:
    """Parse a dictionary into a Rule instance.

    Args:
        data: Dictionary with rule fields.

    Returns:
        Rule instance.

    Raises:
        ValueError: If required fields are missing.
    """
    if "id" not in data:
        raise ValueError("Rule is missing required 'id' field")
    if "title" not in data:
        raise ValueError(f"Rule '{data['id']}' is missing required 'title' field")

    priority_str = data.get("priority", "recommended")
    priority = _parse_priority(priority_str)

    applies_to = data.get("applies_to", ["*"])
    if isinstance(applies_to, str):
        applies_to = [applies_to]

    return Rule(
        id=data["id"],
        title=data["title"],
        description=data.get("description", ""),
        priority=priority,
        category=data.get("category", "general"),
        applies_to=applies_to,
        enabled=data.get("enabled", True),
    )


class RuleLoader:
    """Loads engineering rule sets from YAML files."""

    def __init__(self, rules_dir: Path | None = None) -> None:
        """Initialize the rule loader.

        Args:
            rules_dir: Directory containing YAML rule files.
                       Defaults to ``.zerg/rules/``.
        """
        self._rules_dir = rules_dir or Path(".zerg/rules")

    @property
    def rules_dir(self) -> Path:
        """Return the configured rules directory."""
        return self._rules_dir

    def load_all(self) -> list[RuleSet]:
        """Load all YAML rule files from the rules directory.

        Returns:
            List of RuleSet instances. Empty list if directory doesn't exist
            or contains no valid YAML files.
        """
        if not self._rules_dir.exists():
            logger.debug("Rules directory %s does not exist", self._rules_dir)
            return []

        rulesets: list[RuleSet] = []
        for yaml_path in sorted(self._rules_dir.glob("*.yaml")):
            try:
                rulesets.append(self.load_file(yaml_path))
            except Exception:
                logger.warning("Failed to load rule file %s", yaml_path, exc_info=True)
        for yml_path in sorted(self._rules_dir.glob("*.yml")):
            try:
                rulesets.append(self.load_file(yml_path))
            except Exception:
                logger.warning("Failed to load rule file %s", yml_path, exc_info=True)

        return rulesets

    def load_file(self, path: Path) -> RuleSet:
        """Load a single YAML rule file into a RuleSet.

        Args:
            path: Path to the YAML file.

        Returns:
            RuleSet parsed from the file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file content is invalid.
        """
        if not path.exists():
            raise FileNotFoundError(f"Rule file not found: {path}")

        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)

        if not isinstance(data, dict):
            raise ValueError(f"Rule file {path} must contain a YAML mapping at top level")

        rules_data = data.get("rules", [])
        if not isinstance(rules_data, list):
            raise ValueError(f"Rule file {path}: 'rules' must be a list")

        rules: list[Rule] = []
        for rule_data in rules_data:
            if not isinstance(rule_data, dict):
                logger.warning("Skipping non-dict rule entry in %s", path)
                continue
            try:
                rules.append(_parse_rule(rule_data))
            except ValueError as exc:
                logger.warning("Skipping invalid rule in %s: %s", path, exc)

        return RuleSet(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            rules=rules,
            version=str(data.get("version", "1.0")),
        )

    def get_rules_for_files(
        self,
        file_paths: list[str],
        rulesets: list[RuleSet] | None = None,
    ) -> list[Rule]:
        """Filter rules to those applicable to the given file paths.

        A rule applies if any of its ``applies_to`` glob patterns match
        any of the provided file paths (matched against the basename).

        Args:
            file_paths: List of file paths to match against.
            rulesets: Rule sets to filter. Loads all if None.

        Returns:
            Deduplicated list of matching enabled rules.
        """
        if rulesets is None:
            rulesets = self.load_all()

        if not file_paths:
            return []

        basenames = [Path(fp).name for fp in file_paths]
        matched: dict[str, Rule] = {}

        for ruleset in rulesets:
            for rule in ruleset.rules:
                if not rule.enabled:
                    continue
                if rule.id in matched:
                    continue
                if self._rule_matches_files(rule, basenames):
                    matched[rule.id] = rule

        return list(matched.values())

    def get_rules_by_priority(
        self,
        priority: RulePriority,
        rulesets: list[RuleSet] | None = None,
    ) -> list[Rule]:
        """Return all enabled rules matching the given priority.

        Args:
            priority: Priority level to filter by.
            rulesets: Rule sets to search. Loads all if None.

        Returns:
            List of matching enabled rules.
        """
        if rulesets is None:
            rulesets = self.load_all()

        results: list[Rule] = []
        for ruleset in rulesets:
            for rule in ruleset.rules:
                if rule.enabled and rule.priority == priority:
                    results.append(rule)
        return results

    @staticmethod
    def _rule_matches_files(rule: Rule, basenames: list[str]) -> bool:
        """Check whether a rule's applies_to patterns match any basenames."""
        for pattern in rule.applies_to:
            for basename in basenames:
                if fnmatch.fnmatch(basename, pattern):
                    return True
        return False
