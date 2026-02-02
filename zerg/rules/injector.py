"""Rule injection for ZERG worker task context."""

from __future__ import annotations

from zerg.logging import get_logger
from zerg.rules.loader import Rule, RuleLoader, RulePriority

logger = get_logger("rules.injector")

# Rough approximation: 1 token ~ 4 characters
CHARS_PER_TOKEN = 4

# Priority display labels
_PRIORITY_LABELS: dict[RulePriority, str] = {
    RulePriority.CRITICAL: "CRITICAL",
    RulePriority.IMPORTANT: "IMPORTANT",
    RulePriority.RECOMMENDED: "RECOMMENDED",
}


class RuleInjector:
    """Generates compact markdown rule sections for worker task context."""

    def __init__(self, loader: RuleLoader | None = None) -> None:
        """Initialize the injector.

        Args:
            loader: RuleLoader to use. Creates a default one if None.
        """
        self._loader = loader or RuleLoader()

    def inject_rules(self, task: dict, max_tokens: int = 800) -> str:
        """Generate a markdown rules section filtered by a task's file types.

        Extracts file paths from the task dict (``files.create`` and
        ``files.modify``), filters rules by applicability, and returns
        a compact markdown summary respecting the token budget.

        Args:
            task: Task dictionary with optional ``files`` section.
            max_tokens: Maximum token budget for the output.

        Returns:
            Markdown string with applicable rules, or empty string if
            no rules match.
        """
        file_paths = self._extract_file_paths(task)
        if not file_paths:
            return ""

        try:
            rules = self._loader.get_rules_for_files(file_paths)
        except Exception:
            logger.debug("Failed to load rules for injection", exc_info=True)
            return ""

        if not rules:
            return ""

        # Sort by priority: critical first, then important, then recommended
        priority_order = {
            RulePriority.CRITICAL: 0,
            RulePriority.IMPORTANT: 1,
            RulePriority.RECOMMENDED: 2,
        }
        rules.sort(key=lambda r: priority_order.get(r.priority, 99))

        return self.summarize_rules(rules, max_tokens)

    def format_rule(self, rule: Rule) -> str:
        """Format a single rule as compact markdown.

        Args:
            rule: Rule to format.

        Returns:
            Markdown string for this rule.
        """
        label = _PRIORITY_LABELS.get(rule.priority, rule.priority.value.upper())
        line = f"- **[{label}]** {rule.title}"
        if rule.description:
            line += f": {rule.description}"
        return line

    def summarize_rules(self, rules: list[Rule], max_tokens: int) -> str:
        """Summarize rules within a token budget.

        Rules are added in order until the budget is exhausted. Critical
        rules are always included first.

        Args:
            rules: Pre-sorted list of rules to summarize.
            max_tokens: Maximum token budget.

        Returns:
            Markdown string fitting within the budget.
        """
        if not rules:
            return ""

        max_chars = max_tokens * CHARS_PER_TOKEN
        lines: list[str] = []
        current_chars = 0

        for rule in rules:
            formatted = self.format_rule(rule)
            line_chars = len(formatted) + 1  # +1 for newline

            if current_chars + line_chars > max_chars and lines:
                remaining = len(rules) - len(lines)
                if remaining > 0:
                    truncation_note = f"\n_({remaining} more rules omitted due to token budget)_"
                    lines.append(truncation_note)
                break

            lines.append(formatted)
            current_chars += line_chars

        return "\n".join(lines)

    @staticmethod
    def _extract_file_paths(task: dict) -> list[str]:
        """Extract file paths from a task dictionary."""
        files_section = task.get("files", {})
        result: list[str] = []
        for key in ("create", "modify"):
            entries = files_section.get(key)
            if isinstance(entries, list):
                result.extend(entries)
        return result
