"""Validation for ZERG engineering rule sets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from zerg.logging import get_logger
from zerg.rules.loader import Rule, RuleLoader, RulePriority, RuleSet

logger = get_logger("rules.validator")


@dataclass
class ValidationResult:
    """Outcome of a rule-set validation pass."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rules_checked: int = 0


class RuleValidator:
    """Validates engineering rule sets for consistency and correctness."""

    def validate_ruleset(self, ruleset: RuleSet) -> ValidationResult:
        """Validate a single rule set.

        Checks performed:
        - Rule IDs are unique within the set.
        - All priorities are valid enum members.
        - Required fields (id, title) are present and non-empty.

        Args:
            ruleset: The RuleSet to validate.

        Returns:
            ValidationResult with any detected issues.
        """
        result = ValidationResult()
        seen_ids: dict[str, int] = {}

        for idx, rule in enumerate(ruleset.rules):
            result.rules_checked += 1

            # Check for duplicate IDs
            if rule.id in seen_ids:
                result.valid = False
                result.errors.append(
                    f"Duplicate rule ID '{rule.id}' in ruleset '{ruleset.name}' "
                    f"(first at index {seen_ids[rule.id]}, duplicate at {idx})"
                )
            else:
                seen_ids[rule.id] = idx

            # Check required fields are non-empty
            if not rule.id.strip():
                result.valid = False
                result.errors.append(f"Rule at index {idx} in '{ruleset.name}' has empty ID")

            if not rule.title.strip():
                result.valid = False
                result.errors.append(f"Rule '{rule.id}' in '{ruleset.name}' has empty title")

            # Check priority is a valid enum member
            if not isinstance(rule.priority, RulePriority):
                result.valid = False
                result.errors.append(f"Rule '{rule.id}' in '{ruleset.name}' has invalid priority: {rule.priority}")

            # Warn on empty applies_to
            if not rule.applies_to:
                result.warnings.append(
                    f"Rule '{rule.id}' in '{ruleset.name}' has empty applies_to; it will match no files"
                )

            # Warn on empty description
            if not rule.description:
                result.warnings.append(f"Rule '{rule.id}' in '{ruleset.name}' has no description")

        return result

    def validate_rules_dir(self, rules_dir: Path) -> ValidationResult:
        """Validate all rule files in a directory.

        Args:
            rules_dir: Path to the rules directory.

        Returns:
            Aggregated ValidationResult across all files.
        """
        aggregate = ValidationResult()

        if not rules_dir.exists():
            aggregate.warnings.append(f"Rules directory does not exist: {rules_dir}")
            return aggregate

        loader = RuleLoader(rules_dir)

        try:
            rulesets = loader.load_all()
        except Exception as exc:
            aggregate.valid = False
            aggregate.errors.append(f"Failed to load rules from {rules_dir}: {exc}")
            return aggregate

        if not rulesets:
            aggregate.warnings.append(f"No rule files found in {rules_dir}")
            return aggregate

        for ruleset in rulesets:
            sub = self.validate_ruleset(ruleset)
            aggregate.rules_checked += sub.rules_checked
            aggregate.errors.extend(sub.errors)
            aggregate.warnings.extend(sub.warnings)
            if not sub.valid:
                aggregate.valid = False

        # Cross-ruleset duplicate ID check
        self._check_cross_ruleset_duplicates(rulesets, aggregate)

        return aggregate

    def check_rule_conflicts(self, rules: list[Rule]) -> list[str]:
        """Detect potentially conflicting rules.

        Conflicts are detected when two rules with different priorities
        share the same category and overlapping applies_to patterns.

        Args:
            rules: List of rules to check for conflicts.

        Returns:
            List of conflict description strings.
        """
        conflicts: list[str] = []

        for i, rule_a in enumerate(rules):
            for rule_b in rules[i + 1 :]:
                if rule_a.category != rule_b.category:
                    continue
                if rule_a.priority == rule_b.priority:
                    continue
                if self._patterns_overlap(rule_a.applies_to, rule_b.applies_to):
                    conflicts.append(
                        f"Potential conflict: '{rule_a.id}' ({rule_a.priority.value}) "
                        f"and '{rule_b.id}' ({rule_b.priority.value}) share category "
                        f"'{rule_a.category}' with overlapping file patterns"
                    )

        return conflicts

    @staticmethod
    def _patterns_overlap(patterns_a: list[str], patterns_b: list[str]) -> bool:
        """Check if two sets of glob patterns could match the same files."""
        for pa in patterns_a:
            for pb in patterns_b:
                # "*" matches everything
                if pa == "*" or pb == "*":
                    return True
                # Same pattern
                if pa == pb:
                    return True
        return False

    @staticmethod
    def _check_cross_ruleset_duplicates(rulesets: list[RuleSet], result: ValidationResult) -> None:
        """Check for duplicate rule IDs across different rule sets."""
        seen: dict[str, str] = {}  # rule_id -> ruleset name
        for ruleset in rulesets:
            for rule in ruleset.rules:
                if rule.id in seen and seen[rule.id] != ruleset.name:
                    result.valid = False
                    result.errors.append(
                        f"Rule ID '{rule.id}' duplicated across rulesets: '{seen[rule.id]}' and '{ruleset.name}'"
                    )
                else:
                    seen[rule.id] = ruleset.name
