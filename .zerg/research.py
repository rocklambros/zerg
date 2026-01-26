"""ZERG v2 Research Command - External research and context gathering via MCP."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ResearchSource(Enum):
    """Research source types."""

    DOCS = "docs"  # Official documentation (Context7 MCP)
    WEB = "web"  # General web search (Tavily MCP)
    CODE = "code"  # Code examples (GitHub search)
    PAPERS = "papers"  # Academic papers


class ResearchDepth(Enum):
    """Research depth levels."""

    QUICK = "quick"  # Fast overview
    STANDARD = "standard"  # Balanced depth
    DEEP = "deep"  # Comprehensive research


@dataclass
class ResearchConfig:
    """Configuration for research operations."""

    sources: list[str] = field(default_factory=lambda: ["docs", "web"])
    depth: str = "standard"
    max_results: int = 10
    save_path: str = ""


@dataclass
class ResearchItem:
    """A research finding."""

    title: str
    url: str
    source_type: str
    snippet: str
    relevance: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type,
            "snippet": self.snippet,
            "relevance": self.relevance,
        }


@dataclass
class ResearchResult:
    """Result of research operation."""

    query: str
    quick_answer: str
    items: list[ResearchItem] = field(default_factory=list)
    implementation_notes: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    searched_at: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "quick_answer": self.quick_answer,
            "items": [i.to_dict() for i in self.items],
            "implementation_notes": self.implementation_notes,
            "citations": self.citations,
            "searched_at": self.searched_at,
        }

    def to_markdown(self) -> str:
        """Generate markdown research report."""
        lines = [
            f"# Research: {self.query}",
            "",
            "## Quick Answer",
            self.quick_answer,
            "",
            "## Sources",
        ]

        # Group by source type
        by_type: dict[str, list[ResearchItem]] = {}
        for item in self.items:
            if item.source_type not in by_type:
                by_type[item.source_type] = []
            by_type[item.source_type].append(item)

        for source_type, items in by_type.items():
            lines.append(f"\n### {source_type.title()}")
            for i, item in enumerate(items, 1):
                lines.append(f"{i}. [{item.title}]({item.url})")
                if item.snippet:
                    lines.append(f"   - {item.snippet}")

        if self.implementation_notes:
            lines.append("\n## Implementation Notes")
            for note in self.implementation_notes:
                lines.append(f"- {note}")

        if self.citations:
            lines.append("\n## Citations")
            for i, citation in enumerate(self.citations, 1):
                lines.append(f"[{i}] {citation}")

        return "\n".join(lines)


class DocsSearcher:
    """Search official documentation via MCP."""

    def search(self, query: str, max_results: int = 5) -> list[ResearchItem]:
        """Search documentation."""
        # Placeholder - would integrate with Context7 MCP
        return [
            ResearchItem(
                title=f"Documentation: {query}",
                url="https://docs.example.com",
                source_type="docs",
                snippet=f"Official documentation for {query}",
                relevance=0.9,
            )
        ]


class WebSearcher:
    """Search web via MCP."""

    def search(self, query: str, max_results: int = 5) -> list[ResearchItem]:
        """Search web."""
        # Placeholder - would integrate with Tavily MCP
        return [
            ResearchItem(
                title=f"Web result: {query}",
                url="https://example.com",
                source_type="web",
                snippet=f"Web search result for {query}",
                relevance=0.7,
            )
        ]


class CodeSearcher:
    """Search code examples via GitHub."""

    def search(self, query: str, max_results: int = 5) -> list[ResearchItem]:
        """Search code."""
        # Placeholder - would integrate with GitHub API
        return [
            ResearchItem(
                title=f"Code example: {query}",
                url="https://github.com/example",
                source_type="code",
                snippet=f"Code example implementing {query}",
                relevance=0.8,
            )
        ]


class ResearchAggregator:
    """Aggregate research from multiple sources."""

    def __init__(self, config: ResearchConfig | None = None):
        """Initialize aggregator."""
        self.config = config or ResearchConfig()
        self.docs_searcher = DocsSearcher()
        self.web_searcher = WebSearcher()
        self.code_searcher = CodeSearcher()

    def research(self, query: str) -> ResearchResult:
        """Conduct research across sources."""
        items: list[ResearchItem] = []

        for source in self.config.sources:
            if source == "docs":
                items.extend(
                    self.docs_searcher.search(query, self.config.max_results)
                )
            elif source == "web":
                items.extend(
                    self.web_searcher.search(query, self.config.max_results)
                )
            elif source == "code":
                items.extend(
                    self.code_searcher.search(query, self.config.max_results)
                )

        # Sort by relevance
        items.sort(key=lambda x: x.relevance, reverse=True)

        # Generate quick answer
        quick_answer = self._generate_quick_answer(query, items)

        return ResearchResult(
            query=query,
            quick_answer=quick_answer,
            items=items[: self.config.max_results],
            implementation_notes=self._extract_notes(items),
            citations=self._generate_citations(items),
            searched_at=datetime.now().isoformat(),
        )

    def _generate_quick_answer(self, query: str, items: list[ResearchItem]) -> str:
        """Generate quick answer from results."""
        if not items:
            return f"No results found for: {query}"
        return f"Based on {len(items)} sources, {query} refers to..."

    def _extract_notes(self, items: list[ResearchItem]) -> list[str]:
        """Extract implementation notes from results."""
        notes = []
        for item in items[:3]:
            if item.snippet:
                notes.append(item.snippet)
        return notes

    def _generate_citations(self, items: list[ResearchItem]) -> list[str]:
        """Generate citations for results."""
        return [f"{item.title}, {item.url}" for item in items[:5]]


class ResearchCommand:
    """Main research command orchestrator."""

    def __init__(self, config: ResearchConfig | None = None):
        """Initialize research command."""
        self.config = config or ResearchConfig()
        self.aggregator = ResearchAggregator(config=self.config)

    def run(
        self,
        query: str,
        sources: list[str] | None = None,
        depth: str = "standard",
    ) -> ResearchResult:
        """Run research operation."""
        if sources:
            self.config.sources = sources

        if depth == "quick":
            self.config.max_results = 3
        elif depth == "deep":
            self.config.max_results = 20
        else:
            self.config.max_results = 10

        return self.aggregator.research(query)

    def format_result(self, result: ResearchResult, format: str = "text") -> str:
        """Format research result."""
        if format == "json":
            return json.dumps(result.to_dict(), indent=2)

        if format == "markdown":
            return result.to_markdown()

        lines = [
            "Research Result",
            "=" * 40,
            f"Query: {result.query}",
            "",
            "Quick Answer:",
            result.quick_answer,
            "",
            f"Sources Found: {len(result.items)}",
        ]

        for item in result.items[:5]:
            lines.append(f"  - {item.title} ({item.source_type})")

        return "\n".join(lines)


__all__ = [
    "ResearchSource",
    "ResearchDepth",
    "ResearchConfig",
    "ResearchItem",
    "ResearchResult",
    "DocsSearcher",
    "WebSearcher",
    "CodeSearcher",
    "ResearchAggregator",
    "ResearchCommand",
]
