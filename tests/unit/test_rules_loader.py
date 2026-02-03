"""Unit tests for ZERG engineering rules loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from zerg.rules.loader import Rule, RuleLoader, RulePriority, RuleSet


class TestRulePriority:
    """Tests for RulePriority enum."""

    def test_critical_value(self) -> None:
        assert RulePriority.CRITICAL.value == "critical"

    def test_important_value(self) -> None:
        assert RulePriority.IMPORTANT.value == "important"

    def test_recommended_value(self) -> None:
        assert RulePriority.RECOMMENDED.value == "recommended"

    def test_from_string(self) -> None:
        assert RulePriority("critical") is RulePriority.CRITICAL
        assert RulePriority("important") is RulePriority.IMPORTANT
        assert RulePriority("recommended") is RulePriority.RECOMMENDED

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            RulePriority("invalid")


class TestRule:
    """Tests for Rule dataclass."""

    def test_defaults(self) -> None:
        rule = Rule(id="test-001", title="Test rule")
        assert rule.id == "test-001"
        assert rule.title == "Test rule"
        assert rule.description == ""
        assert rule.priority == RulePriority.RECOMMENDED
        assert rule.category == "general"
        assert rule.applies_to == ["*"]
        assert rule.enabled is True

    def test_custom_fields(self) -> None:
        rule = Rule(
            id="sec-001",
            title="Security rule",
            description="A security rule",
            priority=RulePriority.CRITICAL,
            category="security",
            applies_to=["*.py"],
            enabled=False,
        )
        assert rule.priority == RulePriority.CRITICAL
        assert rule.category == "security"
        assert rule.applies_to == ["*.py"]
        assert rule.enabled is False


class TestRuleSet:
    """Tests for RuleSet dataclass."""

    def test_defaults(self) -> None:
        rs = RuleSet(name="test")
        assert rs.name == "test"
        assert rs.description == ""
        assert rs.rules == []
        assert rs.version == "1.0"

    def test_with_rules(self) -> None:
        rules = [Rule(id="r1", title="Rule 1"), Rule(id="r2", title="Rule 2")]
        rs = RuleSet(name="test", rules=rules, version="2.0")
        assert len(rs.rules) == 2
        assert rs.version == "2.0"


class TestRuleLoaderLoadFile:
    """Tests for RuleLoader.load_file."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        yaml_content = """\
name: test-rules
description: Test rule set
version: "1.0"
rules:
  - id: test-001
    title: Test rule one
    description: A test rule
    priority: critical
    category: security
    applies_to: ["*.py"]
    enabled: true
  - id: test-002
    title: Test rule two
    priority: important
    category: quality
    applies_to: ["*.js", "*.ts"]
    enabled: true
"""
        rule_file = tmp_path / "test.yaml"
        rule_file.write_text(yaml_content)

        loader = RuleLoader(tmp_path)
        ruleset = loader.load_file(rule_file)

        assert ruleset.name == "test-rules"
        assert ruleset.description == "Test rule set"
        assert len(ruleset.rules) == 2
        assert ruleset.rules[0].id == "test-001"
        assert ruleset.rules[0].priority == RulePriority.CRITICAL
        assert ruleset.rules[1].applies_to == ["*.js", "*.ts"]

    def test_load_file_not_found(self, tmp_path: Path) -> None:
        loader = RuleLoader(tmp_path)
        with pytest.raises(FileNotFoundError):
            loader.load_file(tmp_path / "nonexistent.yaml")

    def test_load_invalid_yaml_top_level(self, tmp_path: Path) -> None:
        rule_file = tmp_path / "bad.yaml"
        rule_file.write_text("- just a list")

        loader = RuleLoader(tmp_path)
        with pytest.raises(ValueError, match="must contain a YAML mapping"):
            loader.load_file(rule_file)

    def test_load_invalid_rules_field(self, tmp_path: Path) -> None:
        rule_file = tmp_path / "bad.yaml"
        rule_file.write_text("name: bad\nrules: not-a-list\n")

        loader = RuleLoader(tmp_path)
        with pytest.raises(ValueError, match="'rules' must be a list"):
            loader.load_file(rule_file)

    def test_load_missing_rule_id(self, tmp_path: Path) -> None:
        yaml_content = """\
name: incomplete
rules:
  - title: No ID rule
    priority: critical
"""
        rule_file = tmp_path / "incomplete.yaml"
        rule_file.write_text(yaml_content)

        loader = RuleLoader(tmp_path)
        # Should skip invalid rule (logged warning) and return empty rules
        ruleset = loader.load_file(rule_file)
        assert len(ruleset.rules) == 0

    def test_load_defaults_for_optional_fields(self, tmp_path: Path) -> None:
        yaml_content = """\
name: minimal
rules:
  - id: min-001
    title: Minimal rule
"""
        rule_file = tmp_path / "minimal.yaml"
        rule_file.write_text(yaml_content)

        loader = RuleLoader(tmp_path)
        ruleset = loader.load_file(rule_file)

        assert len(ruleset.rules) == 1
        rule = ruleset.rules[0]
        assert rule.priority == RulePriority.RECOMMENDED
        assert rule.category == "general"
        assert rule.applies_to == ["*"]
        assert rule.enabled is True


class TestRuleLoaderLoadAll:
    """Tests for RuleLoader.load_all."""

    def test_load_empty_directory(self, tmp_path: Path) -> None:
        loader = RuleLoader(tmp_path)
        result = loader.load_all()
        assert result == []

    def test_load_nonexistent_directory(self, tmp_path: Path) -> None:
        loader = RuleLoader(tmp_path / "nonexistent")
        result = loader.load_all()
        assert result == []

    def test_load_multiple_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text("name: alpha\nrules:\n  - id: a1\n    title: Alpha rule\n")
        (tmp_path / "b.yaml").write_text("name: beta\nrules:\n  - id: b1\n    title: Beta rule\n")

        loader = RuleLoader(tmp_path)
        rulesets = loader.load_all()

        assert len(rulesets) == 2
        names = {rs.name for rs in rulesets}
        assert names == {"alpha", "beta"}

    def test_load_skips_invalid_files(self, tmp_path: Path) -> None:
        (tmp_path / "good.yaml").write_text("name: good\nrules:\n  - id: g1\n    title: Good\n")
        (tmp_path / "bad.yaml").write_text("- just a list\n")

        loader = RuleLoader(tmp_path)
        rulesets = loader.load_all()

        assert len(rulesets) == 1
        assert rulesets[0].name == "good"

    def test_load_yml_extension(self, tmp_path: Path) -> None:
        (tmp_path / "rules.yml").write_text("name: yml-set\nrules:\n  - id: y1\n    title: YML rule\n")

        loader = RuleLoader(tmp_path)
        rulesets = loader.load_all()

        assert len(rulesets) == 1
        assert rulesets[0].name == "yml-set"


class TestRuleLoaderFilterByFiles:
    """Tests for RuleLoader.get_rules_for_files."""

    def _make_rulesets(self) -> list[RuleSet]:
        return [
            RuleSet(
                name="test",
                rules=[
                    Rule(id="py-rule", title="Python rule", applies_to=["*.py"]),
                    Rule(id="js-rule", title="JS rule", applies_to=["*.js"]),
                    Rule(id="all-rule", title="All rule", applies_to=["*"]),
                    Rule(
                        id="disabled-rule",
                        title="Disabled",
                        applies_to=["*.py"],
                        enabled=False,
                    ),
                ],
            )
        ]

    def test_filter_python_files(self) -> None:
        loader = RuleLoader()
        rules = loader.get_rules_for_files(["src/main.py"], rulesets=self._make_rulesets())
        rule_ids = {r.id for r in rules}
        assert "py-rule" in rule_ids
        assert "all-rule" in rule_ids
        assert "js-rule" not in rule_ids

    def test_filter_js_files(self) -> None:
        loader = RuleLoader()
        rules = loader.get_rules_for_files(["app.js"], rulesets=self._make_rulesets())
        rule_ids = {r.id for r in rules}
        assert "js-rule" in rule_ids
        assert "all-rule" in rule_ids
        assert "py-rule" not in rule_ids

    def test_filter_excludes_disabled(self) -> None:
        loader = RuleLoader()
        rules = loader.get_rules_for_files(["test.py"], rulesets=self._make_rulesets())
        rule_ids = {r.id for r in rules}
        assert "disabled-rule" not in rule_ids

    def test_empty_file_list(self) -> None:
        loader = RuleLoader()
        rules = loader.get_rules_for_files([], rulesets=self._make_rulesets())
        assert rules == []

    def test_no_matching_files(self) -> None:
        rulesets = [
            RuleSet(
                name="test",
                rules=[Rule(id="py-only", title="Py", applies_to=["*.py"])],
            )
        ]
        loader = RuleLoader()
        rules = loader.get_rules_for_files(["style.css"], rulesets=rulesets)
        assert rules == []

    def test_deduplicates_rules(self) -> None:
        rulesets = [
            RuleSet(
                name="set1",
                rules=[Rule(id="shared", title="Shared", applies_to=["*.py"])],
            ),
            RuleSet(
                name="set2",
                rules=[Rule(id="shared", title="Shared", applies_to=["*.py"])],
            ),
        ]
        loader = RuleLoader()
        rules = loader.get_rules_for_files(["main.py"], rulesets=rulesets)
        assert len([r for r in rules if r.id == "shared"]) == 1


class TestRuleLoaderFilterByPriority:
    """Tests for RuleLoader.get_rules_by_priority."""

    def test_filter_critical(self) -> None:
        rulesets = [
            RuleSet(
                name="test",
                rules=[
                    Rule(id="c1", title="Crit", priority=RulePriority.CRITICAL),
                    Rule(id="i1", title="Imp", priority=RulePriority.IMPORTANT),
                    Rule(id="r1", title="Rec", priority=RulePriority.RECOMMENDED),
                ],
            )
        ]
        loader = RuleLoader()
        rules = loader.get_rules_by_priority(RulePriority.CRITICAL, rulesets=rulesets)
        assert len(rules) == 1
        assert rules[0].id == "c1"

    def test_filter_excludes_disabled(self) -> None:
        rulesets = [
            RuleSet(
                name="test",
                rules=[
                    Rule(
                        id="c1",
                        title="Disabled crit",
                        priority=RulePriority.CRITICAL,
                        enabled=False,
                    ),
                ],
            )
        ]
        loader = RuleLoader()
        rules = loader.get_rules_by_priority(RulePriority.CRITICAL, rulesets=rulesets)
        assert rules == []
