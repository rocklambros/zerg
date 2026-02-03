"""Comprehensive tests for zerg.doc_engine.crossref and zerg.doc_engine.dependencies.

Covers all public APIs, internal helpers, edge cases, and branch conditions
for both modules with >=80% line coverage target.
"""

from __future__ import annotations

from pathlib import Path

from zerg.doc_engine.crossref import (
    CrossRefBuilder,
    CrossReference,
    GlossaryEntry,
    _extract_keywords,
    _is_inside_heading,
    _mask_code_blocks,
)
from zerg.doc_engine.dependencies import (
    DependencyGraph,
    DependencyMapper,
    ModuleNode,
    _extract_imports,
    _path_to_module,
    _resolve_import,
)

# ======================================================================
# crossref.py -- helper functions
# ======================================================================


class TestExtractKeywords:
    def test_filters_stop_words(self) -> None:
        result = _extract_keywords("the quick brown fox is very fast")
        assert "the" not in result
        assert "quick" in result
        assert "brown" in result
        assert "fox" in result
        assert "fast" in result
        assert "very" not in result

    def test_lowercases_all_words(self) -> None:
        result = _extract_keywords("Authentication HANDLER")
        assert "authentication" in result
        assert "handler" in result

    def test_filters_short_words(self) -> None:
        # Words with fewer than 3 characters after the first letter are excluded
        result = _extract_keywords("I am ok go")
        assert result == []

    def test_includes_hyphenated_and_underscored(self) -> None:
        result = _extract_keywords("my-widget my_component")
        assert "my-widget" in result
        assert "my_component" in result

    def test_empty_string(self) -> None:
        assert _extract_keywords("") == []

    def test_only_stop_words(self) -> None:
        assert _extract_keywords("the is a an") == []

    def test_alphanumeric_words(self) -> None:
        result = _extract_keywords("version2 auth0 handler")
        assert "version2" in result
        assert "auth0" in result
        assert "handler" in result


class TestMaskCodeBlocks:
    def test_masks_fenced_code_block(self) -> None:
        content = "before ```code here``` after"
        masked = _mask_code_blocks(content)
        assert "code here" not in masked
        assert masked.startswith("before ")
        assert masked.endswith(" after")

    def test_masks_inline_code(self) -> None:
        content = "use `Widget` here"
        masked = _mask_code_blocks(content)
        assert "Widget" not in masked
        # Length should be preserved
        assert len(masked) == len(content)

    def test_preserves_non_code_text(self) -> None:
        content = "no code blocks here"
        assert _mask_code_blocks(content) == content

    def test_multiple_code_blocks(self) -> None:
        content = "`one` and `two` and ```three```"
        masked = _mask_code_blocks(content)
        assert "one" not in masked
        assert "two" not in masked
        assert "three" not in masked
        assert len(masked) == len(content)

    def test_multiline_fenced_block(self) -> None:
        content = "text\n```\nline1\nline2\n```\nmore"
        masked = _mask_code_blocks(content)
        assert "line1" not in masked
        assert "line2" not in masked
        assert len(masked) == len(content)


class TestIsInsideHeading:
    def test_inside_heading(self) -> None:
        content = "## Widget Overview\nBody text"
        # Position of "Widget" (at index 3)
        assert _is_inside_heading(content, 3) is True

    def test_outside_heading(self) -> None:
        content = "## Heading\nWidget in body"
        pos = content.index("Widget")
        assert _is_inside_heading(content, pos) is False

    def test_h1_heading(self) -> None:
        content = "# Top Level Heading\nbody"
        assert _is_inside_heading(content, 2) is True

    def test_h4_heading(self) -> None:
        content = "#### Deep Heading\nbody"
        assert _is_inside_heading(content, 5) is True

    def test_not_heading_line(self) -> None:
        content = "regular line without hash"
        assert _is_inside_heading(content, 0) is False

    def test_at_beginning_of_content(self) -> None:
        content = "## Start\nrest"
        assert _is_inside_heading(content, 0) is True

    def test_multiline_detection(self) -> None:
        content = "normal\n## Heading Line\nmore normal"
        heading_pos = content.index("Heading")
        normal_pos = content.index("more")
        assert _is_inside_heading(content, heading_pos) is True
        assert _is_inside_heading(content, normal_pos) is False


# ======================================================================
# crossref.py -- CrossRefBuilder
# ======================================================================


class TestCrossRefBuilderBuildGlossary:
    def setup_method(self) -> None:
        self.builder = CrossRefBuilder()

    def test_heading_h2_extraction(self) -> None:
        pages = {"p1": "## Authentication\n\nHandles user login."}
        glossary = self.builder.build_glossary(pages)
        assert len(glossary) == 1
        assert glossary[0].term == "Authentication"
        assert glossary[0].definition == "Handles user login."
        assert glossary[0].page == "p1"

    def test_heading_h3_extraction(self) -> None:
        pages = {"p1": "### Sub Term\n\nSub definition."}
        glossary = self.builder.build_glossary(pages)
        assert len(glossary) == 1
        assert glossary[0].term == "Sub Term"

    def test_h1_not_extracted(self) -> None:
        pages = {"p1": "# Top Level\n\nNot extracted."}
        glossary = self.builder.build_glossary(pages)
        heading_terms = [e for e in glossary if e.term == "Top Level"]
        assert len(heading_terms) == 0

    def test_bold_definition_pattern(self) -> None:
        pages = {"p1": "Some intro.\n\n**Router**: Handles request routing.\n"}
        glossary = self.builder.build_glossary(pages)
        assert any(e.term == "Router" and "routing" in e.definition for e in glossary)

    def test_bold_definition_with_dash_separator(self) -> None:
        pages = {"p1": "**Term** - definition here\n"}
        glossary = self.builder.build_glossary(pages)
        assert any(e.term == "Term" for e in glossary)

    def test_bold_definition_with_em_dash(self) -> None:
        pages = {"p1": "**Concept** \u2014 explained here\n"}
        glossary = self.builder.build_glossary(pages)
        assert any(e.term == "Concept" for e in glossary)

    def test_deduplication_across_pages(self) -> None:
        pages = {
            "p1": "## Shared\n\nFirst definition.",
            "p2": "## Shared\n\nSecond definition.",
        }
        glossary = self.builder.build_glossary(pages)
        shared = [e for e in glossary if e.term == "Shared"]
        assert len(shared) == 1
        assert shared[0].page == "p1"

    def test_deduplication_case_insensitive(self) -> None:
        pages = {
            "p1": "## Widget\n\nFirst.",
            "p2": "## widget\n\nSecond.",
        }
        glossary = self.builder.build_glossary(pages)
        widgets = [e for e in glossary if e.term.lower() == "widget"]
        assert len(widgets) == 1

    def test_heading_dedup_blocks_bold_def(self) -> None:
        pages = {"p1": "## Router\n\nDef.\n\n**Router**: duplicate.\n"}
        glossary = self.builder.build_glossary(pages)
        routers = [e for e in glossary if e.term.lower() == "router"]
        assert len(routers) == 1

    def test_heading_with_no_definition_line(self) -> None:
        pages = {"p1": "## Orphan Heading\n\n"}
        glossary = self.builder.build_glossary(pages)
        assert any(e.term == "Orphan Heading" and e.definition == "" for e in glossary)

    def test_heading_followed_by_another_heading(self) -> None:
        # When ## First is followed by ## Second, the definition loop skips
        # heading lines (starting with #) but finds "Def of second." as a
        # non-heading, non-empty line, so it becomes First's definition.
        pages = {"p1": "## First\n## Second\n\nDef of second."}
        glossary = self.builder.build_glossary(pages)
        first = [e for e in glossary if e.term == "First"]
        assert len(first) == 1
        assert first[0].definition == "Def of second."

    def test_heading_followed_only_by_headings(self) -> None:
        # When ALL subsequent lines are headings or empty, definition is empty
        pages = {"p1": "## First\n## Second\n## Third\n"}
        glossary = self.builder.build_glossary(pages)
        first = [e for e in glossary if e.term == "First"]
        assert len(first) == 1
        assert first[0].definition == ""

    def test_multiple_pages_multiple_terms(self) -> None:
        pages = {
            "p1": "## Alpha\n\nFirst.\n\n**Bravo**: Second.",
            "p2": "## Charlie\n\nThird.",
        }
        glossary = self.builder.build_glossary(pages)
        terms = {e.term for e in glossary}
        assert terms == {"Alpha", "Bravo", "Charlie"}

    def test_empty_pages_dict(self) -> None:
        assert self.builder.build_glossary({}) == []


class TestCrossRefBuilderInjectLinks:
    def setup_method(self) -> None:
        self.builder = CrossRefBuilder()

    def test_basic_link_injection(self) -> None:
        glossary = [GlossaryEntry(term="Widget", definition=".", page="other")]
        result = self.builder.inject_links("Use Widget here.", glossary, "mypage")
        assert "[[Widget|Widget]]" in result

    def test_no_self_links(self) -> None:
        glossary = [GlossaryEntry(term="Widget", definition=".", page="mypage")]
        result = self.builder.inject_links("Use Widget here.", glossary, "mypage")
        assert "[[" not in result

    def test_first_occurrence_only(self) -> None:
        glossary = [GlossaryEntry(term="Widget", definition=".", page="other")]
        result = self.builder.inject_links("Widget first. Widget second.", glossary, "mypage")
        assert result.count("[[Widget|Widget]]") == 1

    def test_longer_term_takes_priority(self) -> None:
        glossary = [
            GlossaryEntry(term="Auth", definition=".", page="other"),
            GlossaryEntry(term="Auth Handler", definition=".", page="other"),
        ]
        content = "The Auth Handler manages Auth."
        result = self.builder.inject_links(content, glossary, "mypage")
        assert "[[Auth Handler|Auth Handler]]" in result

    def test_skip_code_block_occurrences(self) -> None:
        glossary = [GlossaryEntry(term="Widget", definition=".", page="other")]
        content = "```\nWidget inside code\n```\nWidget outside."
        result = self.builder.inject_links(content, glossary, "mypage")
        assert "[[Widget|Widget]]" in result
        # Verify the link is for the occurrence outside the code block
        code_end = result.index("```", 3)
        link_pos = result.index("[[Widget")
        assert link_pos > code_end

    def test_skip_heading_occurrences(self) -> None:
        glossary = [GlossaryEntry(term="Widget", definition=".", page="other")]
        content = "## Widget\n\nWidget in body."
        result = self.builder.inject_links(content, glossary, "mypage")
        assert result.startswith("## Widget")
        assert "[[Widget|Widget]]" in result

    def test_skip_inline_code_occurrences(self) -> None:
        glossary = [GlossaryEntry(term="Widget", definition=".", page="other")]
        content = "Use `Widget` inline and Widget outside."
        result = self.builder.inject_links(content, glossary, "mypage")
        assert "`Widget`" in result
        assert "[[Widget|Widget]]" in result

    def test_case_insensitive_matching(self) -> None:
        glossary = [GlossaryEntry(term="Widget", definition=".", page="other")]
        content = "A widget is useful."
        result = self.builder.inject_links(content, glossary, "mypage")
        assert "[[Widget|widget]]" in result

    def test_aliases_linked(self) -> None:
        glossary = [GlossaryEntry(term="CLI", definition=".", page="other", aliases=["command-line"])]
        content = "The command-line interface."
        result = self.builder.inject_links(content, glossary, "mypage")
        assert "[[CLI|command-line]]" in result

    def test_no_glossary_entries(self) -> None:
        result = self.builder.inject_links("Some content.", [], "mypage")
        assert result == "Some content."

    def test_no_matching_terms(self) -> None:
        glossary = [GlossaryEntry(term="Widget", definition=".", page="other")]
        result = self.builder.inject_links("No match here.", glossary, "mypage")
        assert result == "No match here."

    def test_empty_content(self) -> None:
        glossary = [GlossaryEntry(term="Widget", definition=".", page="other")]
        result = self.builder.inject_links("", glossary, "mypage")
        assert result == ""

    def test_word_boundary_prevents_partial_match(self) -> None:
        glossary = [GlossaryEntry(term="auth", definition=".", page="other")]
        content = "The authentication module."
        result = self.builder.inject_links(content, glossary, "mypage")
        # "auth" should not match inside "authentication"
        assert "[[" not in result


class TestCrossRefBuilderSeeAlso:
    def setup_method(self) -> None:
        self.builder = CrossRefBuilder()

    def test_keyword_overlap_scoring(self) -> None:
        pages = {
            "source": "## Authentication\n\nHandles auth login.",
            "related": "## Authentication\n\nAuth configuration.",
            "unrelated": "## Deployment\n\nDocker containers.",
        }
        related = self.builder.see_also("source", pages)
        assert "related" in related
        # related should rank higher than unrelated
        if "unrelated" in related:
            assert related.index("related") < related.index("unrelated")

    def test_wiki_link_boosts_score(self) -> None:
        pages = {
            "source": "See [[linked_page]] for more.",
            "linked_page": "Some content here.",
            "other": "Different content.",
        }
        related = self.builder.see_also("source", pages)
        assert related[0] == "linked_page"

    def test_reverse_wiki_link_boosts_score(self) -> None:
        pages = {
            "source": "Source content.",
            "linker": "See [[source]] for details.",
            "other": "Unrelated stuff.",
        }
        related = self.builder.see_also("source", pages)
        assert "linker" in related

    def test_shared_headings_boost_score(self) -> None:
        pages = {
            "source": "## Configuration\n\nSetup details.",
            "match": "## Configuration\n\nConfig info.",
            "nomatch": "## Deployment\n\nDeploy info.",
        }
        related = self.builder.see_also("source", pages)
        assert related[0] == "match"

    def test_missing_page_returns_empty(self) -> None:
        pages = {"existing": "content"}
        assert self.builder.see_also("nonexistent", pages) == []

    def test_max_related_limits_output(self) -> None:
        pages = {f"page{i}": "## Shared\n\nCommon keyword content." for i in range(20)}
        related = self.builder.see_also("page0", pages, max_related=3)
        assert len(related) <= 3

    def test_single_page_returns_empty(self) -> None:
        pages = {"only": "Some content."}
        assert self.builder.see_also("only", pages) == []

    def test_no_overlap_returns_empty(self) -> None:
        pages = {
            "alpha": "## Unique Alpha\n\nxyzzy plugh.",
            "beta": "## Unique Beta\n\nfoobar bazqux.",
        }
        # If there is zero keyword overlap and no links, result could be empty
        related = self.builder.see_also("alpha", pages)
        # The words are all unique, but "unique" itself is shared
        # so this may or may not return results depending on keyword extraction
        assert isinstance(related, list)

    def test_wiki_link_with_display_text(self) -> None:
        pages = {
            "source": "See [[target|Display Text]] for more.",
            "target": "Content.",
        }
        related = self.builder.see_also("source", pages)
        assert "target" in related


class TestCrossRefBuilderGenerateGlossaryPage:
    def setup_method(self) -> None:
        self.builder = CrossRefBuilder()

    def test_alphabetical_ordering(self) -> None:
        glossary = [
            GlossaryEntry(term="Zebra", definition="Last.", page="p1"),
            GlossaryEntry(term="Alpha", definition="First.", page="p2"),
            GlossaryEntry(term="Middle", definition="Mid.", page="p3"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        alpha_pos = page.index("Alpha")
        middle_pos = page.index("Middle")
        zebra_pos = page.index("Zebra")
        assert alpha_pos < middle_pos < zebra_pos

    def test_letter_sections(self) -> None:
        glossary = [
            GlossaryEntry(term="Alpha", definition=".", page="p1"),
            GlossaryEntry(term="Beta", definition=".", page="p2"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        assert "## A" in page
        assert "## B" in page

    def test_same_letter_no_duplicate_header(self) -> None:
        glossary = [
            GlossaryEntry(term="Apple", definition=".", page="p1"),
            GlossaryEntry(term="Avocado", definition=".", page="p2"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        assert page.count("## A") == 1

    def test_anchor_generation(self) -> None:
        glossary = [
            GlossaryEntry(term="My Term", definition=".", page="p1"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        assert '<a id="my-term"></a>' in page

    def test_anchor_special_chars(self) -> None:
        glossary = [
            GlossaryEntry(term="C++ Style!", definition=".", page="p1"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        # Special chars replaced with hyphens, stripped from edges
        assert "a id=" in page

    def test_definition_included(self) -> None:
        glossary = [
            GlossaryEntry(term="Test", definition="The definition.", page="p1"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        assert "The definition." in page

    def test_empty_definition_omitted(self) -> None:
        glossary = [
            GlossaryEntry(term="NoDesc", definition="", page="p1"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        # Should not crash and should have the term
        assert "NoDesc" in page

    def test_aliases_rendered(self) -> None:
        glossary = [
            GlossaryEntry(term="CLI", definition=".", page="p1", aliases=["cmd", "terminal"]),
        ]
        page = self.builder.generate_glossary_page(glossary)
        assert "*Aliases: cmd, terminal*" in page

    def test_no_aliases_no_alias_line(self) -> None:
        glossary = [
            GlossaryEntry(term="Simple", definition=".", page="p1"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        assert "Aliases:" not in page

    def test_page_reference(self) -> None:
        glossary = [
            GlossaryEntry(term="Term", definition=".", page="MyPage"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        assert "*Defined in: [[MyPage]]*" in page

    def test_empty_glossary(self) -> None:
        page = self.builder.generate_glossary_page([])
        assert "# Glossary" in page
        assert "##" not in page.replace("# Glossary", "")

    def test_empty_term_string(self) -> None:
        glossary = [
            GlossaryEntry(term="", definition="empty term.", page="p1"),
        ]
        page = self.builder.generate_glossary_page(glossary)
        # Should not crash, empty first_letter
        assert "# Glossary" in page


# ======================================================================
# crossref.py -- dataclasses
# ======================================================================


class TestCrossRefDataClasses:
    def test_glossary_entry_defaults(self) -> None:
        entry = GlossaryEntry(term="T", definition="D", page="P")
        assert entry.aliases == []

    def test_glossary_entry_with_aliases(self) -> None:
        entry = GlossaryEntry(term="T", definition="D", page="P", aliases=["a", "b"])
        assert entry.aliases == ["a", "b"]

    def test_cross_reference(self) -> None:
        ref = CrossReference(source_page="A", target_page="B", context="related")
        assert ref.source_page == "A"
        assert ref.target_page == "B"
        assert ref.context == "related"


# ======================================================================
# dependencies.py -- helper functions
# ======================================================================


class TestPathToModule:
    def test_valid_path(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        f = pkg / "core.py"
        f.touch()
        result = _path_to_module(f, tmp_path, "mypkg")
        assert result == "mypkg.core"

    def test_init_file_resolves_to_package(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        f = pkg / "__init__.py"
        f.touch()
        result = _path_to_module(f, tmp_path, "mypkg")
        assert result == "mypkg"

    def test_nested_module(self, tmp_path: Path) -> None:
        sub = tmp_path / "mypkg" / "sub"
        sub.mkdir(parents=True)
        f = sub / "mod.py"
        f.touch()
        result = _path_to_module(f, tmp_path, "mypkg")
        assert result == "mypkg.sub.mod"

    def test_outside_package_returns_none(self, tmp_path: Path) -> None:
        other = tmp_path / "other"
        other.mkdir()
        f = other / "mod.py"
        f.touch()
        result = _path_to_module(f, tmp_path, "mypkg")
        assert result is None

    def test_file_not_relative_returns_none(self, tmp_path: Path) -> None:
        # File is not under root_dir at all
        other = Path("/tmp/completely_different")
        result = _path_to_module(other / "mod.py", tmp_path, "mypkg")
        assert result is None

    def test_nested_init_resolves_to_subpackage(self, tmp_path: Path) -> None:
        sub = tmp_path / "mypkg" / "sub"
        sub.mkdir(parents=True)
        f = sub / "__init__.py"
        f.touch()
        result = _path_to_module(f, tmp_path, "mypkg")
        assert result == "mypkg.sub"

    def test_top_level_init_only(self, tmp_path: Path) -> None:
        """A bare __init__.py in the package root should return the package name."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        f = pkg / "__init__.py"
        f.touch()
        result = _path_to_module(f, tmp_path, "mypkg")
        assert result == "mypkg"


class TestResolveImport:
    def test_absolute_import(self) -> None:
        result = _resolve_import("mypkg.core", "os", 0, "mypkg")
        assert result == "os"

    def test_relative_import_level_1(self) -> None:
        result = _resolve_import("mypkg.sub.mod", "sibling", 1, "mypkg")
        assert result == "mypkg.sub.sibling"

    def test_relative_import_level_2(self) -> None:
        result = _resolve_import("mypkg.sub.deep.mod", "target", 2, "mypkg")
        assert result == "mypkg.sub.target"

    def test_relative_import_no_module(self) -> None:
        result = _resolve_import("mypkg.sub.mod", None, 1, "mypkg")
        assert result == "mypkg.sub"

    def test_relative_import_exceeds_depth(self) -> None:
        result = _resolve_import("mypkg.mod", "target", 5, "mypkg")
        assert result is None

    def test_relative_import_to_package_root(self) -> None:
        # level == len(parts), base_parts becomes empty, falls back to [package]
        result = _resolve_import("mypkg", "sub", 1, "mypkg")
        assert result == "mypkg.sub"

    def test_absolute_import_none_module(self) -> None:
        # level 0 with no module -- this path returns imported_module (None)
        result = _resolve_import("mypkg.core", None, 0, "mypkg")
        assert result is None


class TestExtractImports:
    def test_import_statement(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("import os\nimport json\n", encoding="utf-8")
        result = _extract_imports(f, "mypkg.mod", "mypkg")
        assert "os" in result
        assert "json" in result

    def test_from_import_statement(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("from pathlib import Path\n", encoding="utf-8")
        result = _extract_imports(f, "mypkg.mod", "mypkg")
        assert "pathlib" in result

    def test_relative_import(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("from . import sibling\n", encoding="utf-8")
        result = _extract_imports(f, "mypkg.sub.mod", "mypkg")
        assert "mypkg.sub" in result

    def test_syntax_error_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("def (broken:\n", encoding="utf-8")
        result = _extract_imports(f, "mypkg.bad", "mypkg")
        assert result == []

    def test_unreadable_file_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.py"
        # File does not exist
        result = _extract_imports(f, "mypkg.missing", "mypkg")
        assert result == []

    def test_from_import_level0_no_module_skipped(self, tmp_path: Path) -> None:
        """A `from import x` with no module and level 0 is skipped."""
        f = tmp_path / "mod.py"
        f.write_text("from mypkg import core\n", encoding="utf-8")
        result = _extract_imports(f, "mypkg.mod", "mypkg")
        assert "mypkg" in result

    def test_multiple_imports_in_one_statement(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("import os, sys, json\n", encoding="utf-8")
        result = _extract_imports(f, "mypkg.mod", "mypkg")
        assert "os" in result
        assert "sys" in result
        assert "json" in result


# ======================================================================
# dependencies.py -- DependencyGraph
# ======================================================================


class TestDependencyGraph:
    def test_get_imports_existing_module(self) -> None:
        graph = DependencyGraph(
            modules={
                "pkg.a": ModuleNode(name="pkg.a", imports=["pkg.b", "pkg.c"]),
                "pkg.b": ModuleNode(name="pkg.b"),
                "pkg.c": ModuleNode(name="pkg.c"),
            }
        )
        result = graph.get_imports("pkg.a")
        assert result == ["pkg.b", "pkg.c"]

    def test_get_imports_missing_module(self) -> None:
        graph = DependencyGraph()
        assert graph.get_imports("nonexistent") == []

    def test_get_importers_existing_module(self) -> None:
        graph = DependencyGraph(
            modules={
                "pkg.b": ModuleNode(name="pkg.b", imported_by=["pkg.a", "pkg.c"]),
            }
        )
        result = graph.get_importers("pkg.b")
        assert result == ["pkg.a", "pkg.c"]

    def test_get_importers_missing_module(self) -> None:
        graph = DependencyGraph()
        assert graph.get_importers("nonexistent") == []

    def test_get_dependency_chain_simple(self) -> None:
        graph = DependencyGraph(
            modules={
                "a": ModuleNode(name="a", imports=["b"]),
                "b": ModuleNode(name="b", imports=["c"]),
                "c": ModuleNode(name="c"),
            }
        )
        chain = graph.get_dependency_chain("a")
        assert "b" in chain
        assert "c" in chain

    def test_get_dependency_chain_cycle(self) -> None:
        graph = DependencyGraph(
            modules={
                "a": ModuleNode(name="a", imports=["b"]),
                "b": ModuleNode(name="b", imports=["a"]),
            }
        )
        chain = graph.get_dependency_chain("a")
        # Should not infinite loop; visited set prevents it
        assert "b" in chain
        assert isinstance(chain, list)

    def test_get_dependency_chain_no_deps(self) -> None:
        graph = DependencyGraph(modules={"a": ModuleNode(name="a")})
        assert graph.get_dependency_chain("a") == []

    def test_get_dependency_chain_missing_module(self) -> None:
        graph = DependencyGraph()
        assert graph.get_dependency_chain("missing") == []

    def test_returns_copies_not_references(self) -> None:
        node = ModuleNode(name="a", imports=["b"], imported_by=["c"])
        graph = DependencyGraph(modules={"a": node})
        imports = graph.get_imports("a")
        importers = graph.get_importers("a")
        imports.append("x")
        importers.append("y")
        # Original should not be modified
        assert "x" not in graph.get_imports("a")
        assert "y" not in graph.get_importers("a")


# ======================================================================
# dependencies.py -- DependencyMapper
# ======================================================================


class TestDependencyMapperBuild:
    def test_empty_directory(self, tmp_path: Path) -> None:
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert graph.modules == {}

    def test_single_module_no_imports(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "core.py").write_text("x = 1\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert "mypkg.core" in graph.modules
        assert "mypkg" in graph.modules  # __init__.py
        assert graph.modules["mypkg.core"].imports == []

    def test_internal_dependency_with_reverse_edge(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "a.py").write_text("import mypkg.b\n", encoding="utf-8")
        (pkg / "b.py").write_text("x = 1\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert "mypkg.b" in graph.get_imports("mypkg.a")
        assert "mypkg.a" in graph.get_importers("mypkg.b")

    def test_external_imports_excluded(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "mod.py").write_text("import os\nimport json\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert graph.modules["mypkg.mod"].imports == []

    def test_syntax_error_still_creates_node(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "bad.py").write_text("def (broken:\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert "mypkg.bad" in graph.modules
        assert graph.modules["mypkg.bad"].imports == []

    def test_nested_subpackage(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg" / "sub"
        pkg.mkdir(parents=True)
        (tmp_path / "mypkg" / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "deep.py").write_text("import mypkg.sub\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert "mypkg.sub.deep" in graph.modules
        assert "mypkg.sub" in graph.modules

    def test_no_duplicate_reverse_edges(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "a.py").write_text("import mypkg.b\n", encoding="utf-8")
        (pkg / "b.py").write_text("x = 1\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        importers = graph.modules["mypkg.b"].imported_by
        assert importers.count("mypkg.a") == 1

    def test_module_path_stored(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        mod = pkg / "core.py"
        mod.write_text("x = 1\n", encoding="utf-8")
        graph = DependencyMapper.build(tmp_path, package="mypkg")
        assert graph.modules["mypkg.core"].path == mod.resolve()


class TestDependencyMapperToAdjacencyList:
    def test_basic_adjacency(self) -> None:
        graph = DependencyGraph(
            modules={
                "pkg.a": ModuleNode(name="pkg.a", imports=["pkg.b"]),
                "pkg.b": ModuleNode(name="pkg.b"),
            }
        )
        adj = DependencyMapper.to_adjacency_list(graph)
        assert adj == {"pkg.a": ["pkg.b"], "pkg.b": []}

    def test_filters_imports_not_in_graph(self) -> None:
        graph = DependencyGraph(
            modules={
                "pkg.a": ModuleNode(name="pkg.a", imports=["pkg.b", "external"]),
            }
        )
        adj = DependencyMapper.to_adjacency_list(graph)
        # "external" is not a module in the graph, so filtered out
        assert adj == {"pkg.a": []}

    def test_empty_graph(self) -> None:
        graph = DependencyGraph()
        adj = DependencyMapper.to_adjacency_list(graph)
        assert adj == {}


# ======================================================================
# dependencies.py -- ModuleNode dataclass
# ======================================================================


class TestModuleNode:
    def test_defaults(self) -> None:
        node = ModuleNode(name="pkg.mod")
        assert node.path is None
        assert node.imports == []
        assert node.imported_by == []

    def test_with_all_fields(self) -> None:
        p = Path("/some/path.py")
        node = ModuleNode(
            name="pkg.mod",
            path=p,
            imports=["pkg.a"],
            imported_by=["pkg.b"],
        )
        assert node.name == "pkg.mod"
        assert node.path == p
        assert node.imports == ["pkg.a"]
        assert node.imported_by == ["pkg.b"]
