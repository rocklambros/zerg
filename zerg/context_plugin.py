"""Context engineering plugin for ZERG -- minimizes token usage across workers."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from zerg.command_splitter import CommandSplitter
from zerg.efficiency import CompactFormatter
from zerg.plugin_config import ContextEngineeringConfig
from zerg.plugins import ContextPlugin
from zerg.security_rules import filter_rules_for_files, summarize_rules
from zerg.spec_loader import SpecLoader

logger = logging.getLogger(__name__)

# Default location for security rules within a project
DEFAULT_RULES_DIR = Path(".claude/rules/security")


class ContextEngineeringPlugin(ContextPlugin):
    """Concrete context plugin that combines engineering rules, security rules, spec context, and command splitting.

    Budget allocation strategy for ``build_task_context``:
        - Engineering rules: ~10% of task_context_budget_tokens
        - Security rules summary: ~10%
        - Spec context (relevant sections): ~20%
        - MCP routing hints: ~10%
        - Analysis depth guidance: ~10%
        - Behavioral mode: ~10%
        - TDD enforcement: ~10%
        - Token efficiency hints: ~5%
        - Repo map context: ~10%
        - Remaining ~5% is reserved as buffer / overhead
    """

    def __init__(self, config: ContextEngineeringConfig | None = None) -> None:
        self._config = config or ContextEngineeringConfig()
        self._splitter = CommandSplitter()
        self._formatter: CompactFormatter | None = self._init_formatter()

    @staticmethod
    def _init_formatter() -> CompactFormatter | None:
        """Create a CompactFormatter when ZERG_COMPACT_MODE is active."""
        compact = os.environ.get("ZERG_COMPACT_MODE", "")
        if compact in ("1", "true"):
            return CompactFormatter(use_symbols=True, use_abbreviations=True)
        return None

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

    def _build_context_inner(self, task: dict, task_graph: dict, feature: str) -> str:
        """Core context-building logic (may raise)."""
        budget = self._config.task_context_budget_tokens
        file_paths = self._collect_task_files(task)

        # Track named components for token metrics
        context_components: dict[str, str] = {}
        sections: list[str] = []

        # -- Engineering rules (~10% of budget) -----------------------------
        rules_budget = int(budget * 0.10)
        rules_section = self._build_rules_section(file_paths, rules_budget)
        if rules_section:
            sections.append(rules_section)
            context_components["engineering_rules"] = rules_section

        # -- Security rules (~10% of budget) --------------------------------
        security_budget = int(budget * 0.10)
        security_section = self._build_security_section(file_paths, security_budget)
        if security_section:
            sections.append(security_section)
            context_components["security_rules"] = security_section

        # -- Spec context (~20% of budget) ----------------------------------
        spec_budget = int(budget * 0.20)
        spec_section = self._build_spec_section(task, feature, spec_budget)
        if spec_section:
            sections.append(spec_section)
            context_components["spec_excerpt"] = spec_section

        # -- MCP routing hints (~10% of budget) -----------------------------
        mcp_budget = int(budget * 0.10)
        mcp_section = self._build_mcp_section(task, mcp_budget)
        if mcp_section:
            sections.append(mcp_section)
            context_components["mcp_hints"] = mcp_section

        # -- Depth tier guidance (~10% of budget) ---------------------------
        depth_budget = int(budget * 0.10)
        depth_section = self._build_depth_section(depth_budget)
        if depth_section:
            sections.append(depth_section)
            context_components["depth_guidance"] = depth_section

        # -- Behavioral mode (~10% of budget) -------------------------------
        mode_budget = int(budget * 0.10)
        mode_section = self._build_mode_section(mode_budget)
        if mode_section:
            sections.append(mode_section)
            context_components["behavioral_mode"] = mode_section

        # -- TDD enforcement (~10% of budget) -------------------------------
        tdd_budget = int(budget * 0.10)
        tdd_section = self._build_tdd_section(tdd_budget)
        if tdd_section:
            sections.append(tdd_section)
            context_components["tdd_enforcement"] = tdd_section

        # -- Efficiency hints (~5% of budget) -------------------------------
        efficiency_section = self._build_efficiency_section()
        if efficiency_section:
            sections.append(efficiency_section)
            context_components["efficiency_hints"] = efficiency_section

        # -- Repo map context (~10% of budget) ----------------------------
        repo_map_budget = int(budget * 0.10)
        repo_map_section = self._build_repo_map_section(task, repo_map_budget)
        if repo_map_section:
            sections.append(repo_map_section)
            context_components["repo_map"] = repo_map_section

        assembled = "\n\n".join(sections)

        # Apply compact formatting when ZERG_COMPACT_MODE is active
        if self._formatter is not None:
            try:
                assembled = self._formatter.abbreviate(assembled)
            except Exception:
                logger.debug(
                    "CompactFormatter.abbreviate failed; returning uncompressed context",
                    exc_info=True,
                )

        # Record token metrics per component (informational only, never fails)
        self._record_token_metrics(task, context_components)

        return assembled

    def _record_token_metrics(self, task: dict, context_components: dict[str, str]) -> None:
        """Record per-component token counts for monitoring.

        This is purely informational. Failures are silently ignored
        to avoid disrupting context generation.
        """
        try:
            from zerg.token_counter import TokenCounter
            from zerg.token_tracker import TokenTracker

            counter = TokenCounter()
            tracker = TokenTracker()

            worker_id = os.environ.get("ZERG_WORKER_ID", "unknown")
            task_id = task.get("id", "unknown")

            breakdown: dict[str, int] = {}
            mode = "estimated"
            for component_name, component_text in context_components.items():
                result = counter.count(component_text)
                breakdown[component_name] = result.count
                mode = result.mode

            tracker.record_task(worker_id, task_id, breakdown, mode=mode)
        except Exception:
            pass  # Token tracking is informational, never fail

    def _build_depth_section(self, max_tokens: int) -> str:
        """Inject analysis depth guidance from ZERG_ANALYSIS_DEPTH env var."""
        depth = os.environ.get("ZERG_ANALYSIS_DEPTH", "")
        if not depth or depth == "standard":
            return ""

        token_budgets = {
            "quick": 1000,
            "think": 4000,
            "think_hard": 10000,
            "ultrathink": 32000,
        }
        budget = token_budgets.get(depth, 2000)

        guidance = {
            "quick": "Surface-level analysis. Focus on obvious issues only. Be concise.",
            "think": "Structured analysis. Consider component interactions. ~4K token budget.",
            "think_hard": "Deep architectural analysis. Trace dependencies across modules. ~10K token budget.",
            "ultrathink": "Maximum depth analysis. Full system-wide impact assessment. ~32K token budget.",
        }
        hint = guidance.get(depth, "Standard analysis depth.")

        return f"## Analysis Depth: {depth}\n\nToken budget: {budget}\n{hint}"

    def _build_mode_section(self, max_tokens: int) -> str:
        """Inject behavioral mode instructions from ZERG_BEHAVIORAL_MODE env var."""
        mode = os.environ.get("ZERG_BEHAVIORAL_MODE", "")
        if not mode or mode == "precision":
            return ""

        mode_instructions = {
            "speed": "Prioritize fast delivery. Minimal validation. Skip non-essential checks.",
            "exploration": "Explore alternatives. Consider multiple approaches before implementing.",
            "refactor": "Focus on code quality. Improve structure, naming, and patterns.",
            "debug": "Systematic debugging. Trace root causes. Add diagnostic logging.",
        }
        instruction = mode_instructions.get(mode, "")
        if not instruction:
            return ""

        return f"## Behavioral Mode: {mode}\n\n{instruction}"

    def _build_tdd_section(self, max_tokens: int) -> str:
        """Inject TDD enforcement workflow from ZERG_TDD_MODE env var."""
        tdd = os.environ.get("ZERG_TDD_MODE", "")
        if tdd != "1":
            return ""

        return (
            "## TDD Enforcement\n\n"
            "Follow RED \u2192 GREEN \u2192 REFACTOR workflow strictly:\n"
            "1. **RED**: Write a failing test first that captures the requirement\n"
            "2. **GREEN**: Write minimal code to make the test pass\n"
            "3. **REFACTOR**: Clean up while keeping tests green\n\n"
            "Do NOT write implementation code before tests exist."
        )

    def _build_efficiency_section(self) -> str:
        """Inject token efficiency hints from ZERG_COMPACT_MODE env var."""
        compact = os.environ.get("ZERG_COMPACT_MODE", "")
        if compact != "1":
            return ""

        return (
            "## Token Efficiency\n\n"
            "Compact mode is active. Minimize token usage:\n"
            "- Use concise variable names in explanations\n"
            "- Skip verbose comments on obvious code\n"
            "- Prefer bullet points over paragraphs\n"
            "- Omit redundant type annotations in documentation"
        )

    def _build_rules_section(self, file_paths: list[str], max_tokens: int) -> str:
        """Inject engineering rules relevant to the task files.

        Args:
            file_paths: List of file paths the task will touch.
            max_tokens: Token budget for the rules section.

        Returns:
            Markdown section string, or empty string on failure.
        """
        try:
            from zerg.rules import RuleInjector

            injector = RuleInjector()
            task: dict = {"files": {"create": file_paths, "modify": []}}
            section = injector.inject_rules(task, max_tokens=max_tokens)
            if section:
                return f"## Engineering Rules (task-scoped)\n\n{section}"
        except Exception:
            logger.debug("Engineering rules injection failed; skipping section", exc_info=True)
        return ""

    def _build_security_section(self, file_paths: list[str], max_tokens: int) -> str:
        """Filter and summarize security rules relevant to the task files."""
        if not self._config.security_rule_filtering:
            return ""

        if not file_paths:
            return ""

        rules_dir = DEFAULT_RULES_DIR

        try:
            filtered_paths = filter_rules_for_files(file_paths, rules_dir)
        except Exception:
            logger.debug("Security rule filtering failed; skipping section", exc_info=True)
            return ""

        if not filtered_paths:
            return ""

        summary = summarize_rules(filtered_paths, max_tokens)
        if not summary:
            return ""

        return f"## Security Rules (task-scoped)\n\n{summary}"

    def _build_spec_section(self, task: dict, feature: str, max_tokens: int) -> str:
        """Load feature specs scoped to this task's keywords."""
        try:
            loader = SpecLoader()
            return loader.format_task_context(task, feature, max_tokens=max_tokens)
        except Exception:
            logger.debug("Spec context loading failed; skipping section", exc_info=True)
            return ""

    def _build_repo_map_section(self, task: dict, max_tokens: int) -> str:
        """Inject repo symbol map context relevant to the task.

        Args:
            task: Task dict from task-graph.json.
            max_tokens: Token budget for the repo map section.

        Returns:
            Markdown section string, or empty string if not available.
        """
        try:
            from zerg.repo_map import build_map

            file_paths = self._collect_task_files(task)
            if not file_paths:
                return ""

            description = task.get("description", "")
            keywords = [w for w in description.split() if len(w) > 3][:10]

            graph = build_map(".", languages=["python", "javascript", "typescript"])
            context = graph.query(file_paths, keywords, max_tokens=max_tokens)
            return context
        except Exception:
            logger.debug("Repo map context failed; skipping section", exc_info=True)
            return ""

    def _build_mcp_section(self, task: dict, max_tokens: int) -> str:
        """Inject MCP routing hints for the task.

        Args:
            task: Task dict from task-graph.json.
            max_tokens: Token budget for the MCP section.

        Returns:
            Markdown section string, or empty string if routing not applicable.
        """
        try:
            from zerg.mcp_router import MCPRouter

            router = MCPRouter()
            file_paths = self._collect_task_files(task)
            extensions = list({Path(f).suffix for f in file_paths if Path(f).suffix})

            # Use resolved depth tier if available
            depth_tier = os.environ.get("ZERG_ANALYSIS_DEPTH")

            decision = router.route(
                task_description=task.get("description", ""),
                file_extensions=extensions,
                depth_tier=depth_tier,
            )

            if decision.recommended_servers:
                servers = ", ".join(decision.server_names)
                return f"## MCP Servers (task-scoped)\n\nRecommended: {servers}"
        except Exception:
            logger.debug("MCP routing failed; skipping section", exc_info=True)
        return ""
