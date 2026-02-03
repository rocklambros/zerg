"""Unit tests for ZERG engineering rules validator."""

from __future__ import annotations

from pathlib import Path

from zerg.rules.loader import Rule, RulePriority, RuleSet
from zerg.rules.validator import RuleValidator, ValidationResult


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_defaults(self) -> None:
        result = ValidationResult()
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.rules_checked == 0


class TestRuleValidatorValidateRuleset:
    """Tests for RuleValidator.validate_ruleset."""

    def test_valid_ruleset(self) -> None:
        ruleset = RuleSet(
            name="test",
            rules=[
                Rule(
                    id="t-001",
                    title="Rule one",
                    description="Desc",
                    priority=RulePriority.CRITICAL,
                ),
                Rule(
                    id="t-002",
                    title="Rule two",
                    description="Desc",
                    priority=RulePriority.IMPORTANT,
                ),
            ],
        )
        validator = RuleValidator()
        result = validator.validate_ruleset(ruleset)

        assert result.valid is True
        assert result.errors == []
        assert result.rules_checked == 2

    def test_duplicate_rule_ids(self) -> None:
        ruleset = RuleSet(
            name="dupes",
            rules=[
                Rule(id="dup-001", title="First", description="d"),
                Rule(id="dup-001", title="Second", description="d"),
            ],
        )
        validator = RuleValidator()
        result = validator.validate_ruleset(ruleset)

        assert result.valid is False
        assert len(result.errors) == 1
        assert "Duplicate rule ID" in result.errors[0]

    def test_empty_rule_id(self) -> None:
        ruleset = RuleSet(
            name="empty-id",
            rules=[Rule(id="  ", title="Has empty ID", description="d")],
        )
        validator = RuleValidator()
        result = validator.validate_ruleset(ruleset)

        assert result.valid is False
        assert any("empty ID" in e for e in result.errors)

    def test_empty_title(self) -> None:
        ruleset = RuleSet(
            name="empty-title",
            rules=[Rule(id="et-001", title="  ", description="d")],
        )
        validator = RuleValidator()
        result = validator.validate_ruleset(ruleset)

        assert result.valid is False
        assert any("empty title" in e for e in result.errors)

    def test_warns_on_empty_applies_to(self) -> None:
        ruleset = RuleSet(
            name="no-patterns",
            rules=[Rule(id="np-001", title="No patterns", description="d", applies_to=[])],
        )
        validator = RuleValidator()
        result = validator.validate_ruleset(ruleset)

        assert result.valid is True
        assert len(result.warnings) >= 1
        assert any("empty applies_to" in w for w in result.warnings)

    def test_warns_on_empty_description(self) -> None:
        ruleset = RuleSet(
            name="no-desc",
            rules=[Rule(id="nd-001", title="No description")],
        )
        validator = RuleValidator()
        result = validator.validate_ruleset(ruleset)

        assert result.valid is True
        assert any("no description" in w for w in result.warnings)

    def test_empty_ruleset(self) -> None:
        ruleset = RuleSet(name="empty", rules=[])
        validator = RuleValidator()
        result = validator.validate_ruleset(ruleset)

        assert result.valid is True
        assert result.rules_checked == 0


class TestRuleValidatorValidateRulesDir:
    """Tests for RuleValidator.validate_rules_dir."""

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        validator = RuleValidator()
        result = validator.validate_rules_dir(tmp_path / "nonexistent")

        assert result.valid is True
        assert any("does not exist" in w for w in result.warnings)

    def test_empty_directory(self, tmp_path: Path) -> None:
        validator = RuleValidator()
        result = validator.validate_rules_dir(tmp_path)

        assert result.valid is True
        assert any("No rule files" in w for w in result.warnings)

    def test_valid_directory(self, tmp_path: Path) -> None:
        (tmp_path / "rules.yaml").write_text(
            "name: test\nrules:\n  - id: t-001\n    title: Rule\n    description: Desc\n"
        )
        validator = RuleValidator()
        result = validator.validate_rules_dir(tmp_path)

        assert result.valid is True
        assert result.rules_checked == 1

    def test_cross_ruleset_duplicate_ids(self, tmp_path: Path) -> None:
        (tmp_path / "set1.yaml").write_text(
            "name: set1\nrules:\n  - id: shared-001\n    title: Rule A\n    description: d\n"
        )
        (tmp_path / "set2.yaml").write_text(
            "name: set2\nrules:\n  - id: shared-001\n    title: Rule B\n    description: d\n"
        )
        validator = RuleValidator()
        result = validator.validate_rules_dir(tmp_path)

        assert result.valid is False
        assert any("duplicated across rulesets" in e for e in result.errors)


class TestRuleValidatorConflictDetection:
    """Tests for RuleValidator.check_rule_conflicts."""

    def test_no_conflicts_different_categories(self) -> None:
        rules = [
            Rule(
                id="a",
                title="A",
                priority=RulePriority.CRITICAL,
                category="security",
                applies_to=["*.py"],
            ),
            Rule(
                id="b",
                title="B",
                priority=RulePriority.RECOMMENDED,
                category="quality",
                applies_to=["*.py"],
            ),
        ]
        validator = RuleValidator()
        conflicts = validator.check_rule_conflicts(rules)
        assert conflicts == []

    def test_no_conflicts_same_priority(self) -> None:
        rules = [
            Rule(
                id="a",
                title="A",
                priority=RulePriority.CRITICAL,
                category="security",
                applies_to=["*.py"],
            ),
            Rule(
                id="b",
                title="B",
                priority=RulePriority.CRITICAL,
                category="security",
                applies_to=["*.py"],
            ),
        ]
        validator = RuleValidator()
        conflicts = validator.check_rule_conflicts(rules)
        assert conflicts == []

    def test_detects_conflict(self) -> None:
        rules = [
            Rule(
                id="a",
                title="A",
                priority=RulePriority.CRITICAL,
                category="security",
                applies_to=["*.py"],
            ),
            Rule(
                id="b",
                title="B",
                priority=RulePriority.RECOMMENDED,
                category="security",
                applies_to=["*.py"],
            ),
        ]
        validator = RuleValidator()
        conflicts = validator.check_rule_conflicts(rules)
        assert len(conflicts) == 1
        assert "Potential conflict" in conflicts[0]

    def test_detects_wildcard_overlap(self) -> None:
        rules = [
            Rule(
                id="a",
                title="A",
                priority=RulePriority.CRITICAL,
                category="workflow",
                applies_to=["*"],
            ),
            Rule(
                id="b",
                title="B",
                priority=RulePriority.IMPORTANT,
                category="workflow",
                applies_to=["*.py"],
            ),
        ]
        validator = RuleValidator()
        conflicts = validator.check_rule_conflicts(rules)
        assert len(conflicts) == 1

    def test_no_conflict_non_overlapping_patterns(self) -> None:
        rules = [
            Rule(
                id="a",
                title="A",
                priority=RulePriority.CRITICAL,
                category="security",
                applies_to=["*.py"],
            ),
            Rule(
                id="b",
                title="B",
                priority=RulePriority.RECOMMENDED,
                category="security",
                applies_to=["*.js"],
            ),
        ]
        validator = RuleValidator()
        conflicts = validator.check_rule_conflicts(rules)
        assert conflicts == []
