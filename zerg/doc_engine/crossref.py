"""Cross-referencing and glossary generation for wiki pages."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class GlossaryEntry:
    """A single glossary term extracted from wiki content."""

    term: str
    definition: str
    page: str  # wiki page where defined
    aliases: list[str] = field(default_factory=list)


@dataclass
class CrossReference:
    """A directional link between two wiki pages."""

    source_page: str
    target_page: str
    context: str  # why they're related


# Regex patterns for content extraction
_HEADING_PATTERN = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
_BOLD_DEF_PATTERN = re.compile(r"\*\*([^*]+)\*\*\s*[:—–-]\s*(.+?)(?:\n|$)")
_CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```|`[^`]+`")
_HEADING_LINE_PATTERN = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)
_WIKI_LINK_PATTERN = re.compile(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]")

# Words too common to be meaningful keywords
_STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
        "and",
        "but",
        "or",
        "nor",
        "not",
        "so",
        "if",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "each",
        "all",
        "any",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "only",
        "own",
        "same",
        "than",
        "too",
        "very",
        "just",
        "about",
        "also",
        "how",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "why",
    }
)


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text, lowercased and filtered."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


def _mask_code_blocks(content: str) -> str:
    """Replace code blocks with whitespace of equal length to preserve offsets."""

    def _replace(match: re.Match[str]) -> str:
        return " " * len(match.group(0))

    return _CODE_BLOCK_PATTERN.sub(_replace, content)


def _is_inside_heading(content: str, start: int) -> bool:
    """Check whether position *start* falls within a heading line."""
    line_start = content.rfind("\n", 0, start) + 1
    line = content[line_start : content.find("\n", start)]
    return bool(_HEADING_LINE_PATTERN.match(line))


class CrossRefBuilder:
    """Build cross-references and glossaries across a set of wiki pages.

    Provides utilities for extracting glossary terms, injecting wiki-style
    links, discovering related pages, and generating a full glossary page.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_glossary(self, pages: dict[str, str]) -> list[GlossaryEntry]:
        """Extract glossary entries from a collection of wiki pages.

        Terms are harvested from ``##`` / ``###`` headings and from bold
        definitions of the form ``**Term**: definition text``.

        Args:
            pages: Mapping of ``{page_name: markdown_content}``.

        Returns:
            A list of :class:`GlossaryEntry` objects, one per discovered term.
        """
        entries: list[GlossaryEntry] = []
        seen_terms: set[str] = set()

        for page_name, content in pages.items():
            # Extract terms from ## and ### headings
            for match in _HEADING_PATTERN.finditer(content):
                term = match.group(2).strip()
                term_lower = term.lower()
                if term_lower in seen_terms:
                    continue
                seen_terms.add(term_lower)

                # Try to grab the first non-empty line after the heading as definition
                after = content[match.end() :].lstrip("\n")
                definition = ""
                for line in after.split("\n"):
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        definition = stripped
                        break

                entries.append(
                    GlossaryEntry(
                        term=term,
                        definition=definition,
                        page=page_name,
                    )
                )

            # Extract bold definitions: **Term**: definition
            for match in _BOLD_DEF_PATTERN.finditer(content):
                term = match.group(1).strip()
                term_lower = term.lower()
                if term_lower in seen_terms:
                    continue
                seen_terms.add(term_lower)

                definition = match.group(2).strip()
                entries.append(
                    GlossaryEntry(
                        term=term,
                        definition=definition,
                        page=page_name,
                    )
                )

        return entries

    def inject_links(
        self,
        content: str,
        glossary: list[GlossaryEntry],
        current_page: str,
    ) -> str:
        """Replace the first occurrence of each glossary term with a wiki link.

        Links use the ``[[term|display text]]`` format.  Terms that belong to
        *current_page* are skipped (no self-links).  Occurrences inside code
        blocks or headings are not replaced.

        Args:
            content: The markdown content to process.
            glossary: Glossary entries to link against.
            current_page: Name of the page being processed (excluded from linking).

        Returns:
            The content string with wiki links injected.
        """
        # Sort terms longest-first so longer matches take priority
        terms = sorted(
            [e for e in glossary if e.page != current_page],
            key=lambda e: len(e.term),
            reverse=True,
        )

        masked = _mask_code_blocks(content)
        linked_terms: set[str] = set()

        for entry in terms:
            term_lower = entry.term.lower()
            if term_lower in linked_terms:
                continue

            # Build pattern matching the term (or aliases) as a whole word
            needles = [re.escape(entry.term)] + [re.escape(a) for a in entry.aliases]
            pattern = re.compile(r"\b(" + "|".join(needles) + r")\b", re.IGNORECASE)

            for match in pattern.finditer(masked):
                start = match.start()
                # Skip if inside a heading line
                if _is_inside_heading(content, start):
                    continue

                # The masked string guarantees we are not inside a code block
                # (code regions are replaced with spaces, so the regex won't
                # match there).
                original_text = content[match.start() : match.end()]
                link = f"[[{entry.term}|{original_text}]]"
                # Perform the replacement in the real content
                content = content[: match.start()] + link + content[match.end() :]
                # Update the mask to keep offsets consistent
                mask_replacement = " " * len(link)
                masked = masked[: match.start()] + mask_replacement + masked[match.end() :]
                linked_terms.add(term_lower)
                break  # first occurrence only

        return content

    def see_also(
        self,
        page_name: str,
        all_pages: dict[str, str],
        max_related: int = 5,
    ) -> list[str]:
        """Find related pages based on keyword overlap and cross-references.

        Relatedness is scored by:
        - Shared keywords between pages (extracted from headings and body text)
        - Explicit wiki-style cross-references ``[[PageName]]``
        - Common terms in section headings

        Args:
            page_name: The page to find related content for.
            all_pages: Full mapping of ``{page_name: markdown_content}``.
            max_related: Maximum number of related pages to return.

        Returns:
            A list of related page names, most relevant first.
        """
        if page_name not in all_pages:
            return []

        source_content = all_pages[page_name]
        source_keywords = Counter(_extract_keywords(source_content))

        scores: dict[str, float] = {}

        for other_name, other_content in all_pages.items():
            if other_name == page_name:
                continue

            score = 0.0

            # 1. Shared keywords
            other_keywords = Counter(_extract_keywords(other_content))
            shared = set(source_keywords.keys()) & set(other_keywords.keys())
            for kw in shared:
                score += min(source_keywords[kw], other_keywords[kw])

            # 2. Explicit cross-references (wiki links mentioning the other page)
            for link_match in _WIKI_LINK_PATTERN.finditer(source_content):
                linked_page = link_match.group(1).strip()
                if linked_page.lower() == other_name.lower():
                    score += 10.0

            # Reverse direction: other page links to this page
            for link_match in _WIKI_LINK_PATTERN.finditer(other_content):
                linked_page = link_match.group(1).strip()
                if linked_page.lower() == page_name.lower():
                    score += 10.0

            # 3. Shared heading terms (higher weight than body keywords)
            source_headings = {m.group(2).strip().lower() for m in _HEADING_PATTERN.finditer(source_content)}
            other_headings = {m.group(2).strip().lower() for m in _HEADING_PATTERN.finditer(other_content)}
            score += len(source_headings & other_headings) * 5.0

            if score > 0:
                scores[other_name] = score

        ranked = sorted(scores, key=lambda n: scores[n], reverse=True)
        return ranked[:max_related]

    def generate_glossary_page(self, glossary: list[GlossaryEntry]) -> str:
        """Generate a full ``Glossary.md`` page from glossary entries.

        Entries are sorted alphabetically and each term receives an HTML
        anchor for deep-linking.

        Args:
            glossary: The glossary entries to render.

        Returns:
            A complete markdown document string.
        """
        sorted_entries = sorted(glossary, key=lambda e: e.term.lower())

        lines: list[str] = ["# Glossary", ""]

        current_letter = ""
        for entry in sorted_entries:
            first_letter = entry.term[0].upper() if entry.term else ""
            if first_letter != current_letter:
                current_letter = first_letter
                lines.append(f"## {current_letter}")
                lines.append("")

            anchor = re.sub(r"[^a-z0-9-]", "-", entry.term.lower()).strip("-")
            lines.append(f'### <a id="{anchor}"></a>{entry.term}')
            lines.append("")
            if entry.definition:
                lines.append(entry.definition)
                lines.append("")
            if entry.aliases:
                aliases_str = ", ".join(entry.aliases)
                lines.append(f"*Aliases: {aliases_str}*")
                lines.append("")
            lines.append(f"*Defined in: [[{entry.page}]]*")
            lines.append("")

        return "\n".join(lines)
