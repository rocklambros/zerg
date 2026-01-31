"""Spec loader utility for ZERG GSD integration.

Loads feature specifications (requirements.md, design.md) and formats them
for injection into worker prompts.
"""

from pathlib import Path
from typing import NamedTuple

from zerg.constants import GSD_DIR
from zerg.logging import get_logger

logger = get_logger("spec_loader")

# Maximum tokens for spec content before truncation
MAX_SPEC_TOKENS = 2000
# Approximate chars per token for truncation
CHARS_PER_TOKEN = 4


class SpecContent(NamedTuple):
    """Container for loaded spec content."""

    requirements: str
    design: str
    feature: str


class SpecLoader:
    """Load and format feature specifications for worker prompts.

    Reads requirements.md and design.md (or architecture.md) from the GSD
    specs directory and formats them for injection into worker prompts.
    """

    def __init__(self, gsd_dir: str | Path | None = None) -> None:
        """Initialize spec loader.

        Args:
            gsd_dir: Path to GSD directory (defaults to .gsd)
        """
        self.gsd_dir = Path(gsd_dir or GSD_DIR)

    def get_spec_dir(self, feature: str) -> Path:
        """Get the spec directory for a feature.

        Args:
            feature: Feature name

        Returns:
            Path to feature spec directory
        """
        return self.gsd_dir / "specs" / feature

    def load_feature_specs(self, feature: str) -> SpecContent:
        """Load requirements and design specs for a feature.

        Args:
            feature: Feature name to load specs for

        Returns:
            SpecContent with requirements and design content
        """
        spec_dir = self.get_spec_dir(feature)

        requirements = self._load_file(spec_dir / "requirements.md")
        if not requirements:
            requirements = self._load_file(spec_dir / "REQUIREMENTS.md")

        design = self._load_file(spec_dir / "design.md")
        if not design:
            design = self._load_file(spec_dir / "DESIGN.md")
        if not design:
            design = self._load_file(spec_dir / "architecture.md")
        if not design:
            design = self._load_file(spec_dir / "ARCHITECTURE.md")

        logger.debug(
            f"Loaded specs for {feature}: "
            f"requirements={len(requirements)} chars, design={len(design)} chars"
        )

        return SpecContent(
            requirements=requirements,
            design=design,
            feature=feature,
        )

    def _load_file(self, path: Path) -> str:
        """Load file content if it exists.

        Args:
            path: File path to load

        Returns:
            File content or empty string if not found
        """
        if not path.exists():
            return ""

        try:
            content = path.read_text(encoding="utf-8")
            return content.strip()
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
            return ""

    def format_context_prompt(
        self,
        requirements: str,
        design: str,
        feature: str | None = None,
        max_tokens: int = MAX_SPEC_TOKENS,
    ) -> str:
        """Format specs as a prompt prefix for workers.

        Args:
            requirements: Requirements content
            design: Design/architecture content
            feature: Optional feature name for header
            max_tokens: Maximum tokens for combined content

        Returns:
            Formatted prompt prefix string
        """
        if not requirements and not design:
            return ""

        parts = []

        # Feature header
        if feature:
            parts.append(f"# Feature Context: {feature}")
            parts.append("")

        # Requirements summary
        if requirements:
            parts.append("## Requirements Summary")
            truncated_req = self._truncate_to_tokens(
                requirements, max_tokens // 2
            )
            parts.append(truncated_req)
            parts.append("")

        # Design decisions
        if design:
            parts.append("## Design Decisions")
            # Give remaining token budget to design
            remaining_tokens = max_tokens - self._estimate_tokens("\n".join(parts))
            truncated_design = self._truncate_to_tokens(
                design, max(remaining_tokens, max_tokens // 2)
            )
            parts.append(truncated_design)
            parts.append("")

        # Separator
        parts.append("---")
        parts.append("")

        return "\n".join(parts)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return len(text) // CHARS_PER_TOKEN

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to approximate token limit.

        Truncates at paragraph boundaries when possible.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens

        Returns:
            Truncated text
        """
        max_chars = max_tokens * CHARS_PER_TOKEN

        if len(text) <= max_chars:
            return text

        # Try to truncate at paragraph boundary
        truncated = text[:max_chars]
        last_para = truncated.rfind("\n\n")

        if last_para > max_chars // 2:
            truncated = truncated[:last_para]
        else:
            # Fall back to sentence boundary
            last_sentence = max(
                truncated.rfind(". "),
                truncated.rfind(".\n"),
            )
            if last_sentence > max_chars // 2:
                truncated = truncated[:last_sentence + 1]

        return truncated + "\n\n[... truncated for context limits ...]"

    def format_task_context(
        self,
        task: dict,
        feature: str,
        max_tokens: int = 1000,
    ) -> str:
        """Format feature specs scoped to a specific task's files and keywords.

        Unlike format_context_prompt (full spec summary), this extracts only
        sections relevant to the task.

        Args:
            task: Task dictionary with title, description, and files
            feature: Feature name to load specs for
            max_tokens: Maximum tokens for combined content

        Returns:
            Formatted context string with relevant sections only
        """
        try:
            specs = self.load_feature_specs(feature)
        except Exception:
            return ""

        if not specs.requirements and not specs.design:
            return ""

        keywords = self._extract_task_keywords(task)
        if not keywords:
            return ""

        parts: list[str] = []

        if specs.requirements:
            relevant = self._extract_relevant_sections(specs.requirements, keywords)
            if relevant:
                parts.append("## Relevant Requirements")
                parts.append(self._truncate_to_tokens(relevant, max_tokens // 2))

        if specs.design:
            relevant = self._extract_relevant_sections(specs.design, keywords)
            if relevant:
                parts.append("## Relevant Design")
                remaining = max_tokens - self._estimate_tokens("\n".join(parts))
                parts.append(
                    self._truncate_to_tokens(
                        relevant, max(remaining, max_tokens // 4)
                    )
                )

        return "\n\n".join(parts) if parts else ""

    def _extract_task_keywords(self, task: dict) -> set[str]:
        """Extract keywords from task title, description, and file paths.

        Args:
            task: Task dictionary with title, description, and files

        Returns:
            Set of lowercase keywords (length > 3 for text, > 2 for file stems)
        """
        words: set[str] = set()
        for field in ("title", "description"):
            if text := task.get(field, ""):
                words.update(w.lower() for w in text.split() if len(w) > 3)
        for file_list in task.get("files", {}).values():
            if isinstance(file_list, list):
                for fp in file_list:
                    from pathlib import Path as _Path

                    stem = _Path(fp).stem
                    words.update(
                        part.lower()
                        for part in stem.replace("-", "_").split("_")
                        if len(part) > 2
                    )
        return words

    def _extract_relevant_sections(self, text: str, keywords: set[str]) -> str:
        """Extract paragraphs containing keyword matches, ranked by relevance.

        Args:
            text: Full spec text to search
            keywords: Set of lowercase keywords to match

        Returns:
            Top 5 matching paragraphs joined by double newlines
        """
        paragraphs = text.split("\n\n")
        scored: list[tuple[int, str]] = []
        for para in paragraphs:
            if not para.strip():
                continue
            score = sum(1 for kw in keywords if kw in para.lower())
            if score > 0:
                scored.append((score, para))
        scored.sort(key=lambda x: x[0], reverse=True)
        return "\n\n".join(para for _, para in scored[:5])

    def load_and_format(self, feature: str, max_tokens: int = MAX_SPEC_TOKENS) -> str:
        """Load specs and format as prompt prefix in one call.

        Args:
            feature: Feature name
            max_tokens: Maximum tokens for content

        Returns:
            Formatted prompt prefix
        """
        specs = self.load_feature_specs(feature)
        return self.format_context_prompt(
            requirements=specs.requirements,
            design=specs.design,
            feature=feature,
            max_tokens=max_tokens,
        )

    def specs_exist(self, feature: str) -> bool:
        """Check if specs exist for a feature.

        Args:
            feature: Feature name

        Returns:
            True if at least one spec file exists
        """
        spec_dir = self.get_spec_dir(feature)

        if not spec_dir.exists():
            return False

        # Check for any spec files
        spec_files = [
            "requirements.md", "REQUIREMENTS.md",
            "design.md", "DESIGN.md",
            "architecture.md", "ARCHITECTURE.md",
        ]

        return any((spec_dir / f).exists() for f in spec_files)
