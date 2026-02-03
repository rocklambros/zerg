"""Unit tests for ZERG engineering rules injector."""

from __future__ import annotations

from pathlib import Path

from zerg.rules.injector import CHARS_PER_TOKEN, RuleInjector
from zerg.rules.loader import Rule, RuleLoader, RulePriority


def _make_loader_with_rules(tmp_path: Path, rules: list[Rule]) -> RuleLoader:
    """Create a RuleLoader backed by a temp directory with given rules."""
    import yaml

    ruleset_data = {
        "name": "test",
        "version": "1.0",
        "rules": [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "priority": r.priority.value,
                "category": r.category,
                "applies_to": r.applies_to,
                "enabled": r.enabled,
            }
            for r in rules
        ],
    }
    (tmp_path / "test.yaml").write_text(yaml.dump(ruleset_data))
    return RuleLoader(tmp_path)


class TestRuleInjectorInjectRules:
    """Tests for RuleInjector.inject_rules."""

    def test_inject_for_python_files(self, tmp_path: Path) -> None:
        rules = [
            Rule(
                id="py-001",
                title="Python safety",
                description="Be safe in Python",
                priority=RulePriority.CRITICAL,
                applies_to=["*.py"],
            ),
            Rule(
                id="js-001",
                title="JS safety",
                description="Be safe in JS",
                priority=RulePriority.CRITICAL,
                applies_to=["*.js"],
            ),
        ]
        loader = _make_loader_with_rules(tmp_path, rules)
        injector = RuleInjector(loader=loader)

        task = {"files": {"create": ["src/main.py"], "modify": []}}
        result = injector.inject_rules(task, max_tokens=800)

        assert "Python safety" in result
        assert "JS safety" not in result

    def test_inject_for_js_files(self, tmp_path: Path) -> None:
        rules = [
            Rule(
                id="py-001",
                title="Python safety",
                applies_to=["*.py"],
            ),
            Rule(
                id="js-001",
                title="JS safety",
                applies_to=["*.js"],
            ),
        ]
        loader = _make_loader_with_rules(tmp_path, rules)
        injector = RuleInjector(loader=loader)

        task = {"files": {"create": ["app.js"], "modify": []}}
        result = injector.inject_rules(task, max_tokens=800)

        assert "JS safety" in result
        assert "Python safety" not in result

    def test_empty_file_list(self, tmp_path: Path) -> None:
        loader = _make_loader_with_rules(
            tmp_path,
            [Rule(id="r1", title="Rule", applies_to=["*.py"])],
        )
        injector = RuleInjector(loader=loader)

        task = {"files": {"create": [], "modify": []}}
        result = injector.inject_rules(task, max_tokens=800)
        assert result == ""

    def test_no_files_key(self, tmp_path: Path) -> None:
        loader = _make_loader_with_rules(
            tmp_path,
            [Rule(id="r1", title="Rule", applies_to=["*.py"])],
        )
        injector = RuleInjector(loader=loader)
        result = injector.inject_rules({}, max_tokens=800)
        assert result == ""

    def test_critical_rules_sorted_first(self, tmp_path: Path) -> None:
        rules = [
            Rule(
                id="rec-001",
                title="Recommended rule",
                priority=RulePriority.RECOMMENDED,
                applies_to=["*"],
            ),
            Rule(
                id="crit-001",
                title="Critical rule",
                priority=RulePriority.CRITICAL,
                applies_to=["*"],
            ),
        ]
        loader = _make_loader_with_rules(tmp_path, rules)
        injector = RuleInjector(loader=loader)

        task = {"files": {"create": ["file.py"], "modify": []}}
        result = injector.inject_rules(task, max_tokens=800)

        crit_pos = result.index("Critical rule")
        rec_pos = result.index("Recommended rule")
        assert crit_pos < rec_pos


class TestRuleInjectorFormatRule:
    """Tests for RuleInjector.format_rule."""

    def test_format_with_description(self) -> None:
        rule = Rule(
            id="t-001",
            title="Test rule",
            description="Do the right thing",
            priority=RulePriority.CRITICAL,
        )
        injector = RuleInjector()
        formatted = injector.format_rule(rule)

        assert formatted.startswith("- **[CRITICAL]**")
        assert "Test rule" in formatted
        assert "Do the right thing" in formatted

    def test_format_without_description(self) -> None:
        rule = Rule(
            id="t-002",
            title="Minimal rule",
            priority=RulePriority.IMPORTANT,
        )
        injector = RuleInjector()
        formatted = injector.format_rule(rule)

        assert "**[IMPORTANT]**" in formatted
        assert "Minimal rule" in formatted
        assert ": " not in formatted.split("Minimal rule")[1] if "Minimal rule" in formatted else True

    def test_format_produces_valid_markdown(self) -> None:
        rule = Rule(
            id="md-001",
            title="Markdown rule",
            description="Has **bold**",
            priority=RulePriority.RECOMMENDED,
        )
        injector = RuleInjector()
        formatted = injector.format_rule(rule)

        assert formatted.startswith("- ")
        assert "**[RECOMMENDED]**" in formatted


class TestRuleInjectorSummarizeRules:
    """Tests for RuleInjector.summarize_rules."""

    def test_empty_rules(self) -> None:
        injector = RuleInjector()
        result = injector.summarize_rules([], max_tokens=100)
        assert result == ""

    def test_token_budget_respected(self) -> None:
        rules = [
            Rule(
                id=f"r-{i:03d}",
                title=f"Rule number {i} with a moderately long description text",
                description="This description adds length to test the token budget",
                priority=RulePriority.IMPORTANT,
            )
            for i in range(50)
        ]

        injector = RuleInjector()
        result = injector.summarize_rules(rules, max_tokens=50)

        # 50 tokens * 4 chars/token = 200 chars max
        # The result should be within reasonable bounds (with truncation note)
        assert len(result) <= 50 * CHARS_PER_TOKEN + 100  # some slack for truncation note

    def test_truncation_note_added(self) -> None:
        rules = [
            Rule(
                id=f"r-{i:03d}",
                title=f"Rule {i} with enough text to fill the budget",
                description="Extra description to make each rule take more space",
                priority=RulePriority.IMPORTANT,
            )
            for i in range(20)
        ]

        injector = RuleInjector()
        result = injector.summarize_rules(rules, max_tokens=30)

        assert "omitted due to token budget" in result

    def test_all_rules_fit(self) -> None:
        rules = [
            Rule(id="r1", title="Short", priority=RulePriority.CRITICAL),
            Rule(id="r2", title="Also short", priority=RulePriority.IMPORTANT),
        ]

        injector = RuleInjector()
        result = injector.summarize_rules(rules, max_tokens=500)

        assert "omitted" not in result
        assert "Short" in result
        assert "Also short" in result
