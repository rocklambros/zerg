"""Sidebar and footer generation for GitHub Wiki navigation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SidebarSection:
    """A named group of wiki pages in the sidebar."""

    title: str
    pages: list[str]  # page names (without .md)
    icon: str = ""  # optional section icon/marker


@dataclass
class SidebarConfig:
    """Top-level configuration for sidebar generation."""

    title: str = "ZERG Wiki"
    sections: list[SidebarSection] = field(default_factory=list)


class SidebarGenerator:
    """Generates GitHub Wiki ``_Sidebar.md`` and ``_Footer.md`` content.

    Uses a predefined wiki structure by default.  Callers can override
    sections via :class:`SidebarConfig` or filter to only pages that
    actually exist by passing a *pages* list.
    """

    DEFAULT_SECTIONS: list[SidebarSection] = [
        SidebarSection("Home", ["Home"]),
        SidebarSection(
            "Getting Started",
            [
                "Getting-Started",
                "Installation",
                "Quick-Start",
                "Your-First-Feature",
            ],
        ),
        SidebarSection(
            "Tutorials",
            [
                "Tutorials",
                "Tutorial-Minerals-Store",
                "Tutorial-Container-Mode",
            ],
        ),
        SidebarSection(
            "Command Reference",
            [
                "zerg-Reference",
                "zerg-brainstorm",
                "zerg-init",
                "zerg-plan",
                "zerg-design",
                "zerg-rush",
                "zerg-status",
                "zerg-logs",
                "zerg-stop",
                "zerg-retry",
                "zerg-merge",
                "zerg-cleanup",
                "zerg-build",
                "zerg-test",
                "zerg-analyze",
                "zerg-review",
                "zerg-security",
                "zerg-refactor",
                "zerg-git",
                "zerg-debug",
                "zerg-worker",
                "zerg-plugins",
                "zerg-document",
                "zerg-estimate",
                "zerg-explain",
                "zerg-index",
                "zerg-select-tool",
            ],
        ),
        SidebarSection(
            "Architecture",
            [
                "Architecture-Overview",
                "Architecture-Execution-Flow",
                "Architecture-Module-Reference",
                "Architecture-State-Management",
                "Architecture-Dependency-Graph",
            ],
        ),
        SidebarSection(
            "Configuration",
            [
                "Configuration",
                "Tuning-Guide",
            ],
        ),
        SidebarSection(
            "Plugins",
            [
                "Plugin-System",
                "Plugin-API-Reference",
            ],
        ),
        SidebarSection(
            "Context Engineering",
            [
                "Context-Engineering",
                "Context-Engineering-Internals",
            ],
        ),
        SidebarSection(
            "Troubleshooting",
            [
                "Troubleshooting",
                "Debug-Guide",
            ],
        ),
        SidebarSection(
            "Contributing",
            [
                "Contributing",
                "Testing",
            ],
        ),
        SidebarSection(
            "Reference",
            [
                "Glossary",
                "FAQ",
            ],
        ),
    ]

    REPO_URL: str = "https://github.com/klambros/ZERG"

    def generate(
        self,
        pages: list[str] | None = None,
        config: SidebarConfig | None = None,
    ) -> str:
        """Generate ``_Sidebar.md`` content.

        Args:
            pages: If provided, only include pages whose names appear in
                this list.  Pages not present are skipped.
            config: Optional :class:`SidebarConfig` overriding the default
                title and sections.

        Returns:
            The full markdown string for ``_Sidebar.md``.
        """
        if config is not None:
            title = config.title
            sections = config.sections if config.sections else self.DEFAULT_SECTIONS
        else:
            title = "ZERG Wiki"
            sections = self.DEFAULT_SECTIONS

        existing: set[str] | None = set(pages) if pages is not None else None

        lines: list[str] = [f"## {title}", ""]

        for section in sections:
            visible = self._filter_pages(section.pages, existing)
            if not visible:
                continue

            if section.icon:
                lines.append(f"{section.icon} **{section.title}**")
            else:
                lines.append(f"**{section.title}**")
            lines.append("")
            for page_name, available in visible:
                display = page_name.replace("-", " ")
                if available:
                    lines.append(f"- [[{display}|{page_name}]]")
                else:
                    lines.append(f"- {display} *(coming soon)*")
            lines.append("")

        return "\n".join(lines)

    def generate_footer(self) -> str:
        """Generate ``_Footer.md`` content.

        Returns:
            Markdown string for the wiki footer.
        """
        lines = [
            "---",
            "",
            "Generated by ZERG doc engine",
            "",
            f"[[Home]] | [GitHub]({self.REPO_URL})",
            "",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_pages(
        page_names: list[str],
        existing: set[str] | None,
    ) -> list[tuple[str, bool]]:
        """Return *(name, available)* pairs for each page.

        If *existing* is ``None`` every page is treated as available.
        """
        result: list[tuple[str, bool]] = []
        for name in page_names:
            available = True if existing is None else name in existing
            result.append((name, available))
        return result
