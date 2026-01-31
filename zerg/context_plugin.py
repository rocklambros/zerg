"""Context engineering plugin for ZERG -- minimizes token usage across workers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from zerg.command_splitter import CommandSplitter
from zerg.plugin_config import ContextEngineeringConfig
from zerg.plugins import ContextPlugin
from zerg.security_rules import filter_rules_for_files, summarize_rules
from zerg.spec_loader import SpecLoader

logger = logging.getLogger(__name__)

# Default location for security rules within a project
DEFAULT_RULES_DIR = Path(".claude/rules/security")


class ContextEngineeringPlugin(ContextPlugin):
    """Concrete context plugin that combines security rules, spec context, and command splitting.

    Budget allocation strategy for ``build_task_context``:
        - Security rules summary:  ~30% of task_context_budget_tokens
        - Spec context (relevant sections): ~50%
        - Remaining ~20% is reserved as buffer / overhead
    """

    def __init__(self, config: ContextEngineeringConfig | None = None) -> None:
        self._config = config or ContextEngineeringConfig()
        self._splitter = CommandSplitter()

    # -- ABC properties / methods --------------------------------------------

    @property
    def name(self) -> str:
        """Unique name identifying this context plugin."""
        return "context-engineering"

    def build_task_context(self, task: dict, task_graph: dict, feature: str) -> str:
        """Build a token-budgeted context string for a single task.

        Combines filtered security rules and feature-spec excerpts relevant to
        the task's file list and description.  Respects the configured
        ``task_context_budget_tokens`` limit.

        Args:
            task: Task dict from task-graph.json.
            task_graph: Full task graph dict.
            feature: Feature name.

        Returns:
            Markdown context string to inject into worker prompt.  Empty string
            signals the caller to fall back to global/full context.
        """
        try:
            return self._build_context_inner(task, task_graph, feature)
        except Exception:
            if self._config.fallback_to_full:
                logger.warning(
                    "Context plugin failed for task %s; falling back to full context",
                    task.get("id", "unknown"),
                    exc_info=True,
                )
                return ""
            raise

    def estimate_context_tokens(self, task: dict) -> int:
        """Rough token estimate: file_count * 500 + description_chars / 4."""
        files = task.get("files", {})
        file_count = 0
        for file_list in files.values():
            if isinstance(file_list, list):
                file_count += len(file_list)
        file_count = max(file_count, 1)

        description = task.get("description", "")
        return file_count * 500 + len(description) // 4

    # -- Command splitting helper -------------------------------------------

    def get_split_command_path(self, command_name: str) -> Path | None:
        """Return path to a ``.core.md`` split command file if available.

        Args:
            command_name: Command name (e.g. ``"zerg:init"``).

        Returns:
            Path to the core split file, or ``None`` if splitting is disabled
            or the file does not exist.
        """
        if not self._config.command_splitting:
            return None

        core_path = self._splitter.commands_dir / f"{command_name}.core.md"
        if core_path.exists():
            return core_path
        return None

    # -- Internal -----------------------------------------------------------

    def _collect_task_files(self, task: dict) -> list[str]:
        """Extract the list of files a task will create or modify."""
        files_section = task.get("files", {})
        result: list[str] = []
        for key in ("create", "modify"):
            entries = files_section.get(key)
            if isinstance(entries, list):
                result.extend(entries)
        return result

    def _build_context_inner(
        self, task: dict, task_graph: dict, feature: str
    ) -> str:
        """Core context-building logic (may raise)."""
        budget = self._config.task_context_budget_tokens
        file_paths = self._collect_task_files(task)

        sections: list[str] = []

        # -- Security rules (~30% of budget) --------------------------------
        security_budget = int(budget * 0.30)
        security_section = self._build_security_section(file_paths, security_budget)
        if security_section:
            sections.append(security_section)

        # -- Spec context (~50% of budget) ----------------------------------
        spec_budget = int(budget * 0.50)
        spec_section = self._build_spec_section(task, feature, spec_budget)
        if spec_section:
            sections.append(spec_section)

        return "\n\n".join(sections)

    def _build_security_section(
        self, file_paths: list[str], max_tokens: int
    ) -> str:
        """Filter and summarize security rules relevant to the task files."""
        if not self._config.security_rule_filtering:
            return ""

        if not file_paths:
            return ""

        rules_dir = DEFAULT_RULES_DIR

        try:
            filtered_paths = filter_rules_for_files(file_paths, rules_dir)
        except Exception:
            logger.debug(
                "Security rule filtering failed; skipping section", exc_info=True
            )
            return ""

        if not filtered_paths:
            return ""

        summary = summarize_rules(filtered_paths, max_tokens)
        if not summary:
            return ""

        return f"## Security Rules (task-scoped)\n\n{summary}"

    def _build_spec_section(
        self, task: dict, feature: str, max_tokens: int
    ) -> str:
        """Load feature specs scoped to this task's keywords."""
        try:
            loader = SpecLoader()
            return loader.format_task_context(task, feature, max_tokens=max_tokens)
        except Exception:
            logger.debug(
                "Spec context loading failed; skipping section", exc_info=True
            )
            return ""
