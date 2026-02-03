"""ZERG command file splitter for context engineering."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Files under this threshold are not worth splitting
MIN_LINES_TO_SPLIT = 300

# Approximate characters per token
CHARS_PER_TOKEN = 4


class CommandSplitter:
    """Splits large command .md files into core + details for context optimization."""

    def __init__(self, commands_dir: str | Path | None = None) -> None:
        if commands_dir is None:
            # Default: find from package location
            self.commands_dir = Path(__file__).parent / "data" / "commands"
        else:
            self.commands_dir = Path(commands_dir)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(text) // CHARS_PER_TOKEN

    def get_splittable_files(self) -> list[dict]:
        """Return list of command files over MIN_LINES_TO_SPLIT.

        Returns list of dicts: {path: Path, lines: int, tokens: int}
        """
        results = []
        for md_file in sorted(self.commands_dir.glob("*.md")):
            # Skip already-split files
            if ".core.md" in md_file.name or ".details.md" in md_file.name:
                continue
            content = md_file.read_text()
            line_count = content.count("\n") + 1
            if line_count >= MIN_LINES_TO_SPLIT:
                results.append(
                    {
                        "path": md_file,
                        "lines": line_count,
                        "tokens": self.estimate_tokens(content),
                    }
                )
        return results

    def analyze_file(self, filepath: Path) -> dict:
        """Analyze a command file's structure.

        Returns dict with: total_lines, sections (list of {header, start_line,
        end_line, lines}), suggested_split_line, has_task_tracking
        """
        content = filepath.read_text()
        lines = content.split("\n")
        total_lines = len(lines)

        # Parse ## sections
        sections: list[dict] = []
        current_header: str | None = None
        current_start = 0

        for i, line in enumerate(lines):
            if line.startswith("## ") or line.startswith("# "):
                if current_header is not None:
                    sections.append(
                        {
                            "header": current_header,
                            "start_line": current_start,
                            "end_line": i - 1,
                            "lines": i - current_start,
                        }
                    )
                current_header = line.strip("# ").strip()
                current_start = i

        # Last section
        if current_header is not None:
            sections.append(
                {
                    "header": current_header,
                    "start_line": current_start,
                    "end_line": total_lines - 1,
                    "lines": total_lines - current_start,
                }
            )

        # Find ~30% split point on section boundary
        target_line = int(total_lines * 0.30)
        suggested_split = 0
        cumulative = 0
        for sec in sections:
            cumulative += sec["lines"]
            if cumulative >= target_line:
                suggested_split = sec["end_line"] + 1
                break

        # Check for Task tracking markers
        has_task_tracking = any(marker in content for marker in ["TaskCreate", "TaskUpdate", "TaskList", "TaskGet"])

        return {
            "total_lines": total_lines,
            "sections": sections,
            "suggested_split_line": suggested_split,
            "has_task_tracking": has_task_tracking,
        }

    def split_file(self, filepath: Path, split_line: int | None = None) -> tuple[Path, Path]:
        """Split a command file into .core.md and .details.md.

        Args:
            filepath: Path to the command .md file
            split_line: Line number to split at. If None, auto-detect at ~30%.

        Returns:
            Tuple of (core_path, details_path)

        The original file is updated to contain the core content
        (so symlinks from .claude/commands/ still work) plus a reference
        comment pointing to the details file.
        """
        content = filepath.read_text()
        lines = content.split("\n")
        total_lines = len(lines)

        if total_lines < MIN_LINES_TO_SPLIT:
            logger.info(f"File {filepath.name} has {total_lines} lines, below threshold. Skipping.")
            return filepath, filepath

        if split_line is None:
            analysis = self.analyze_file(filepath)
            split_line = analysis["suggested_split_line"]

        # Ensure split_line is valid
        split_line = max(10, min(split_line, total_lines - 10))

        core_lines = lines[:split_line]
        details_lines = lines[split_line:]

        # Build file names
        stem = filepath.stem  # e.g., "zerg:init"
        suffix = filepath.suffix  # ".md"
        core_path = filepath.parent / f"{stem}.core{suffix}"
        details_path = filepath.parent / f"{stem}.details{suffix}"

        # Write core file
        core_content = "\n".join(core_lines)
        core_path.write_text(core_content + "\n")

        # Write details file with header
        details_header = f"<!-- SPLIT: details, parent: {filepath.name} -->\n"
        details_header += f"# {stem} — Detailed Reference\n\n"
        details_header += "This file contains extended examples, templates, and edge cases.\n"
        details_header += f"Core instructions are in `{core_path.name}`.\n\n"
        details_content = details_header + "\n".join(details_lines)
        details_path.write_text(details_content + "\n")

        # Update original file: keep core content + reference to details
        reference = f"\n\n<!-- SPLIT: core={core_path.name} details={details_path.name} -->\n"
        reference += f"<!-- For detailed examples and templates, see {details_path.name} -->\n"
        original_content = "\n".join(core_lines) + reference
        filepath.write_text(original_content + "\n")

        logger.info(f"Split {filepath.name}: core={len(core_lines)} lines, details={len(details_lines)} lines")

        return core_path, details_path

    def load_command(self, name: str, include_details: bool = False) -> str:
        """Load a command file, using .core.md if available.

        Args:
            name: Command name (e.g., "zerg:init")
            include_details: If True, append details content after core

        Returns:
            Command file content string
        """
        core_path = self.commands_dir / f"{name}.core.md"
        full_path = self.commands_dir / f"{name}.md"

        # Prefer core file if it exists
        if core_path.exists():
            content = core_path.read_text()
            if include_details:
                details_path = self.commands_dir / f"{name}.details.md"
                if details_path.exists():
                    content += "\n\n" + details_path.read_text()
            return content

        # Fallback to full file
        if full_path.exists():
            return full_path.read_text()

        raise FileNotFoundError(f"Command file not found: {name}")
