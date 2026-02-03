"""Comprehensive tests for zerg.doc_engine modules: mermaid, publisher, sidebar, __init__.

Targets coverage gaps not addressed by tests/test_doc_engine.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.doc_engine.mermaid import (
    MermaidGenerator,
    _sanitize_id,
    _strip_common_prefix,
    _wrap,
)
from zerg.doc_engine.publisher import PublishResult, WikiPublisher
from zerg.doc_engine.sidebar import SidebarConfig, SidebarGenerator, SidebarSection

# ---------------------------------------------------------------------------
# mermaid.py
# ---------------------------------------------------------------------------


class TestSanitizeId:
    """Tests for the _sanitize_id helper."""

    def test_alphanumeric_passthrough(self) -> None:
        assert _sanitize_id("abc123") == "abc123"

    def test_dots_replaced(self) -> None:
        assert _sanitize_id("pkg.mod") == "pkg_mod"

    def test_spaces_replaced(self) -> None:
        assert _sanitize_id("some name") == "some_name"

    def test_special_chars_replaced(self) -> None:
        assert _sanitize_id("a-b/c@d") == "a_b_c_d"

    def test_underscores_preserved(self) -> None:
        assert _sanitize_id("my_var") == "my_var"

    def test_empty_string(self) -> None:
        assert _sanitize_id("") == ""


class TestStripCommonPrefix:
    """Tests for the _strip_common_prefix helper."""

    def test_empty_list(self) -> None:
        assert _strip_common_prefix([]) == {}

    def test_single_name(self) -> None:
        result = _strip_common_prefix(["pkg.mod"])
        # Single name: prefix_len goes as far as all segments match,
        # which is all of them, so short form falls back to last segment.
        assert result == {"pkg.mod": "mod"}

    def test_no_common_prefix(self) -> None:
        result = _strip_common_prefix(["alpha.one", "beta.two"])
        assert result == {"alpha.one": "alpha.one", "beta.two": "beta.two"}

    def test_shared_prefix(self) -> None:
        result = _strip_common_prefix(["pkg.sub.a", "pkg.sub.b"])
        assert result == {"pkg.sub.a": "a", "pkg.sub.b": "b"}

    def test_different_lengths(self) -> None:
        # zip stops at shortest, so only first segment compared
        result = _strip_common_prefix(["a.b.c", "a.x"])
        assert result == {"a.b.c": "b.c", "a.x": "x"}

    def test_identical_names(self) -> None:
        result = _strip_common_prefix(["a.b", "a.b"])
        # All segments match, prefix_len == 2, so ".".join([]) == "" -> falls back to last
        assert result["a.b"] == "b"


class TestWrap:
    """Tests for the _wrap helper."""

    def test_wraps_in_mermaid_fence(self) -> None:
        result = _wrap(["graph TD", "    A --> B"])
        assert result.startswith("```mermaid\n")
        assert result.endswith("\n```")

    def test_empty_lines(self) -> None:
        result = _wrap([])
        assert "```mermaid" in result


class TestMermaidDependencyGraph:
    """Edge cases for MermaidGenerator.dependency_graph."""

    @pytest.fixture
    def gen(self) -> MermaidGenerator:
        return MermaidGenerator()

    def test_subgraph_grouping(self, gen: MermaidGenerator) -> None:
        """When multiple nodes share the same first short-name segment, they
        should be grouped into a subgraph."""
        modules = {
            "root.sub.a": ["root.sub.b"],
            "root.sub.b": [],
            "root.other": [],
        }
        result = gen.dependency_graph(modules)
        assert "subgraph" in result
        assert "sub" in result

    def test_dep_not_in_short_is_skipped(self, gen: MermaidGenerator) -> None:
        """Dependencies referencing modules not in the all_names set are skipped."""
        modules = {"pkg.a": ["external.lib"]}
        result = gen.dependency_graph(modules)
        # external.lib IS in all_names because it appears in deps,
        # so an edge should be present
        assert "-->" in result

    def test_no_title(self, gen: MermaidGenerator) -> None:
        result = gen.dependency_graph({"a": []})
        assert "%%" not in result

    def test_single_member_package_no_subgraph(self, gen: MermaidGenerator) -> None:
        """A package segment with only one member should not produce a subgraph."""
        modules = {"pkg.a": [], "other.b": []}
        result = gen.dependency_graph(modules)
        # Both are single members of their package groups, no subgraph
        assert "subgraph" not in result


class TestMermaidWorkflow:
    """Edge cases for MermaidGenerator.workflow."""

    @pytest.fixture
    def gen(self) -> MermaidGenerator:
        return MermaidGenerator()

    def test_missing_keys_use_defaults(self, gen: MermaidGenerator) -> None:
        steps = [{}]
        result = gen.workflow(steps)
        assert "Unknown->>+Unknown:" in result

    def test_partial_keys(self, gen: MermaidGenerator) -> None:
        steps = [{"actor": "Client"}]
        result = gen.workflow(steps)
        assert "Client->>+Unknown:" in result


class TestMermaidStateMachine:
    """Edge cases for MermaidGenerator.state_machine."""

    @pytest.fixture
    def gen(self) -> MermaidGenerator:
        return MermaidGenerator()

    def test_empty(self, gen: MermaidGenerator) -> None:
        result = gen.state_machine([], [])
        assert "stateDiagram-v2" in result

    def test_special_chars_in_state(self, gen: MermaidGenerator) -> None:
        result = gen.state_machine(["State A"], [])
        assert "State_A : State A" in result


class TestMermaidDataFlow:
    """Edge cases for MermaidGenerator.data_flow."""

    @pytest.fixture
    def gen(self) -> MermaidGenerator:
        return MermaidGenerator()

    def test_unknown_node_type_defaults_to_process(self, gen: MermaidGenerator) -> None:
        nodes = [{"id": "x", "label": "X", "type": "unknown_type"}]
        edges = []
        result = gen.data_flow(nodes, edges)
        # Unknown type falls back to ("[", "]") which is process shape
        assert 'x["X"]' in result

    def test_node_without_label_uses_id(self, gen: MermaidGenerator) -> None:
        nodes = [{"id": "mynode"}]
        edges = []
        result = gen.data_flow(nodes, edges)
        assert "mynode" in result

    def test_node_without_type_defaults_to_process(self, gen: MermaidGenerator) -> None:
        nodes = [{"id": "n", "label": "N"}]
        edges = []
        result = gen.data_flow(nodes, edges)
        assert 'n["N"]' in result

    def test_edge_without_label(self, gen: MermaidGenerator) -> None:
        nodes = [{"id": "a"}, {"id": "b"}]
        edges = [{"from": "a", "to": "b"}]
        result = gen.data_flow(nodes, edges)
        assert "a --> b" in result

    def test_edge_with_label(self, gen: MermaidGenerator) -> None:
        nodes = [{"id": "a"}, {"id": "b"}]
        edges = [{"from": "a", "to": "b", "label": "data"}]
        result = gen.data_flow(nodes, edges)
        assert "a -->|data| b" in result

    def test_store_shape(self, gen: MermaidGenerator) -> None:
        nodes = [{"id": "db", "label": "DB", "type": "store"}]
        result = gen.data_flow(nodes, [])
        assert '[("DB")]' in result

    def test_external_shape(self, gen: MermaidGenerator) -> None:
        nodes = [{"id": "ext", "label": "Ext", "type": "external"}]
        result = gen.data_flow(nodes, [])
        assert '(["Ext"])' in result


class TestMermaidClassDiagram:
    """Edge cases for MermaidGenerator.class_diagram."""

    @pytest.fixture
    def gen(self) -> MermaidGenerator:
        return MermaidGenerator()

    def test_none_bases(self, gen: MermaidGenerator) -> None:
        classes = [{"name": "Foo", "methods": [], "attributes": [], "bases": None}]
        result = gen.class_diagram(classes)
        assert "class Foo" in result
        assert "<|--" not in result

    def test_none_methods(self, gen: MermaidGenerator) -> None:
        classes = [{"name": "Bar", "methods": None, "attributes": None, "bases": None}]
        result = gen.class_diagram(classes)
        assert "class Bar" in result

    def test_class_with_base_not_in_classes_list(self, gen: MermaidGenerator) -> None:
        """Base classes referenced but not defined should still produce edges."""
        classes = [{"name": "Child", "methods": [], "attributes": [], "bases": ["Parent"]}]
        result = gen.class_diagram(classes)
        assert "Parent <|-- Child" in result

    def test_multiple_inheritance(self, gen: MermaidGenerator) -> None:
        classes = [
            {"name": "C", "methods": [], "attributes": [], "bases": ["A", "B"]},
        ]
        result = gen.class_diagram(classes)
        assert "A <|-- C" in result
        assert "B <|-- C" in result


# ---------------------------------------------------------------------------
# publisher.py
# ---------------------------------------------------------------------------


class TestPublishResult:
    """Tests for the PublishResult dataclass."""

    def test_defaults(self) -> None:
        r = PublishResult(success=True)
        assert r.success is True
        assert r.pages_copied == 0
        assert r.commit_sha == ""
        assert r.error == ""
        assert r.dry_run is False
        assert r.actions == []

    def test_fields_set(self) -> None:
        r = PublishResult(
            success=False,
            pages_copied=3,
            commit_sha="abc123",
            error="boom",
            dry_run=True,
            actions=["step1"],
        )
        assert r.pages_copied == 3
        assert r.actions == ["step1"]


class TestWikiPublisherPublish:
    """Tests for WikiPublisher.publish input validation and routing."""

    @pytest.fixture
    def publisher(self) -> WikiPublisher:
        return WikiPublisher()

    def test_nonexistent_wiki_dir(self, publisher: WikiPublisher, tmp_path: Path) -> None:
        result = publisher.publish(
            tmp_path / "nope",
            "https://github.com/user/repo.wiki.git",
        )
        assert result.success is False
        assert "does not exist" in result.error

    def test_empty_wiki_dir(self, publisher: WikiPublisher, tmp_path: Path) -> None:
        result = publisher.publish(tmp_path, "https://github.com/user/repo.wiki.git")
        assert result.success is False
        assert "No .md files" in result.error

    def test_dry_run(self, publisher: WikiPublisher, tmp_path: Path) -> None:
        (tmp_path / "Home.md").write_text("# Home", encoding="utf-8")
        (tmp_path / "Other.md").write_text("# Other", encoding="utf-8")
        result = publisher.publish(
            tmp_path,
            "https://github.com/user/repo.wiki.git",
            dry_run=True,
        )
        assert result.success is True
        assert result.dry_run is True
        assert result.pages_copied == 2
        assert any("git clone" in a for a in result.actions)
        assert any("git push" in a for a in result.actions)
        assert any("git add" in a for a in result.actions)
        assert any("git commit" in a for a in result.actions)
        assert any("Home.md" in a for a in result.actions)

    def test_dry_run_custom_message(self, publisher: WikiPublisher, tmp_path: Path) -> None:
        (tmp_path / "Page.md").write_text("content", encoding="utf-8")
        result = publisher.publish(
            tmp_path,
            "https://example.com/repo.wiki.git",
            dry_run=True,
            commit_message="custom msg",
        )
        assert result.success is True
        assert any("custom msg" in a for a in result.actions)


class TestWikiPublisherPublishReal:
    """Tests for the actual _publish path with mocked git commands."""

    @pytest.fixture
    def publisher(self) -> WikiPublisher:
        return WikiPublisher()

    @pytest.fixture
    def wiki_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "wiki_src"
        d.mkdir()
        (d / "Home.md").write_text("# Home", encoding="utf-8")
        (d / "Setup.md").write_text("# Setup", encoding="utf-8")
        return d

    @patch.object(WikiPublisher, "_rev_parse_head", return_value="abc123def456")
    @patch.object(WikiPublisher, "_has_changes", return_value=True)
    @patch.object(WikiPublisher, "_git")
    @patch("zerg.doc_engine.publisher.shutil.copy2")
    @patch("zerg.doc_engine.publisher.tempfile.mkdtemp")
    def test_successful_publish(
        self,
        mock_mkdtemp: MagicMock,
        mock_copy2: MagicMock,
        mock_git: MagicMock,
        mock_has_changes: MagicMock,
        mock_rev_parse: MagicMock,
        publisher: WikiPublisher,
        wiki_dir: Path,
        tmp_path: Path,
    ) -> None:
        clone_tmp = tmp_path / "zerg-wiki-tmp"
        clone_tmp.mkdir()
        mock_mkdtemp.return_value = str(clone_tmp)
        clone_dir = clone_tmp / "wiki"
        clone_dir.mkdir()

        result = publisher.publish(wiki_dir, "https://github.com/u/r.wiki.git")

        assert result.success is True
        assert result.pages_copied == 2
        assert result.commit_sha == "abc123def456"
        assert result.error == ""

        # Verify git clone was called
        mock_git.assert_any_call(["clone", "https://github.com/u/r.wiki.git", str(clone_dir)])
        # Verify git add was called
        mock_git.assert_any_call(["add", "-A"], cwd=clone_dir)
        # Verify git push was called
        mock_git.assert_any_call(["push", "origin", "master"], cwd=clone_dir)

    @patch.object(WikiPublisher, "_has_changes", return_value=False)
    @patch.object(WikiPublisher, "_git")
    @patch("zerg.doc_engine.publisher.shutil.copy2")
    @patch("zerg.doc_engine.publisher.tempfile.mkdtemp")
    def test_no_changes_to_commit(
        self,
        mock_mkdtemp: MagicMock,
        mock_copy2: MagicMock,
        mock_git: MagicMock,
        mock_has_changes: MagicMock,
        publisher: WikiPublisher,
        wiki_dir: Path,
        tmp_path: Path,
    ) -> None:
        clone_tmp = tmp_path / "zerg-wiki-tmp"
        clone_tmp.mkdir()
        mock_mkdtemp.return_value = str(clone_tmp)
        (clone_tmp / "wiki").mkdir()

        result = publisher.publish(wiki_dir, "https://github.com/u/r.wiki.git")

        assert result.success is True
        assert result.commit_sha == ""  # no commit was made

    @patch.object(
        WikiPublisher, "_git", side_effect=subprocess.CalledProcessError(128, "git", stderr="fatal: repo not found")
    )
    @patch("zerg.doc_engine.publisher.tempfile.mkdtemp")
    def test_git_failure(
        self,
        mock_mkdtemp: MagicMock,
        mock_git: MagicMock,
        publisher: WikiPublisher,
        wiki_dir: Path,
        tmp_path: Path,
    ) -> None:
        clone_tmp = tmp_path / "zerg-wiki-tmp"
        clone_tmp.mkdir()
        mock_mkdtemp.return_value = str(clone_tmp)

        result = publisher.publish(wiki_dir, "https://github.com/u/r.wiki.git")

        assert result.success is False
        assert "Git operation failed" in result.error
        assert "repo not found" in result.error

    @patch.object(
        WikiPublisher, "_git", side_effect=subprocess.CalledProcessError(1, "git", stderr=None, output="some output")
    )
    @patch("zerg.doc_engine.publisher.tempfile.mkdtemp")
    def test_git_failure_no_stderr(
        self,
        mock_mkdtemp: MagicMock,
        mock_git: MagicMock,
        publisher: WikiPublisher,
        wiki_dir: Path,
        tmp_path: Path,
    ) -> None:
        clone_tmp = tmp_path / "zerg-wiki-tmp"
        clone_tmp.mkdir()
        mock_mkdtemp.return_value = str(clone_tmp)

        result = publisher.publish(wiki_dir, "https://github.com/u/r.wiki.git")

        assert result.success is False
        assert "some output" in result.error

    @patch.object(WikiPublisher, "_git")
    @patch("zerg.doc_engine.publisher.shutil.copy2", side_effect=OSError("disk full"))
    @patch("zerg.doc_engine.publisher.tempfile.mkdtemp")
    def test_os_error(
        self,
        mock_mkdtemp: MagicMock,
        mock_copy2: MagicMock,
        mock_git: MagicMock,
        publisher: WikiPublisher,
        wiki_dir: Path,
        tmp_path: Path,
    ) -> None:
        clone_tmp = tmp_path / "zerg-wiki-tmp"
        clone_tmp.mkdir()
        mock_mkdtemp.return_value = str(clone_tmp)
        (clone_tmp / "wiki").mkdir()

        result = publisher.publish(wiki_dir, "https://github.com/u/r.wiki.git")

        assert result.success is False
        assert "File operation failed" in result.error
        assert "disk full" in result.error

    def test_default_commit_message(self, publisher: WikiPublisher) -> None:
        assert publisher.COMMIT_MESSAGE == "docs: update wiki pages via ZERG doc engine"

    def test_custom_commit_message_in_publish(self, publisher: WikiPublisher, wiki_dir: Path, tmp_path: Path) -> None:
        with (
            patch.object(WikiPublisher, "_rev_parse_head", return_value="sha"),
            patch.object(WikiPublisher, "_has_changes", return_value=True),
            patch.object(WikiPublisher, "_git") as mock_git,
            patch("zerg.doc_engine.publisher.shutil.copy2"),
            patch("zerg.doc_engine.publisher.tempfile.mkdtemp") as mock_mkdtemp,
        ):
            clone_tmp = tmp_path / "zerg-wiki-tmp2"
            clone_tmp.mkdir()
            mock_mkdtemp.return_value = str(clone_tmp)
            (clone_tmp / "wiki").mkdir()

            publisher.publish(
                wiki_dir,
                "https://github.com/u/r.wiki.git",
                commit_message="my custom message",
            )

            # Check that commit used the custom message
            commit_calls = [c for c in mock_git.call_args_list if len(c.args) > 0 and "commit" in c.args[0]]
            assert len(commit_calls) == 1
            assert "my custom message" in commit_calls[0].args[0]


class TestWikiPublisherGitHelpers:
    """Tests for static git helper methods."""

    @patch("zerg.doc_engine.publisher.subprocess.run")
    def test_git_runs_command(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=["git", "status"], returncode=0, stdout="", stderr="")
        WikiPublisher._git(["status"])
        mock_run.assert_called_once_with(
            ["git", "status"],
            cwd=None,
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("zerg.doc_engine.publisher.subprocess.run")
    def test_git_with_cwd(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=["git", "status"], returncode=0, stdout="", stderr="")
        cwd = Path("/some/dir")
        WikiPublisher._git(["status"], cwd=cwd)
        mock_run.assert_called_once_with(
            ["git", "status"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("zerg.doc_engine.publisher.subprocess.run")
    def test_has_changes_true(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        assert WikiPublisher._has_changes(Path("/repo")) is True

    @patch("zerg.doc_engine.publisher.subprocess.run")
    def test_has_changes_false(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        assert WikiPublisher._has_changes(Path("/repo")) is False

    @patch("zerg.doc_engine.publisher.subprocess.run")
    def test_rev_parse_head(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="  abc123  \n", stderr="")
        assert WikiPublisher._rev_parse_head(Path("/repo")) == "abc123"


# ---------------------------------------------------------------------------
# sidebar.py
# ---------------------------------------------------------------------------


class TestSidebarGeneratorEdgeCases:
    """Additional edge cases for SidebarGenerator beyond test_doc_engine.py."""

    @pytest.fixture
    def gen(self) -> SidebarGenerator:
        return SidebarGenerator()

    def test_generate_no_pages_filter_all_available(self, gen: SidebarGenerator) -> None:
        result = gen.generate()
        # All pages should be rendered as wiki links, none as "coming soon"
        assert "coming soon" not in result

    def test_generate_with_empty_pages_list(self, gen: SidebarGenerator) -> None:
        """An empty pages list means no pages exist, so all are 'coming soon'."""
        result = gen.generate(pages=[])
        assert "coming soon" in result

    def test_section_all_pages_unavailable_still_rendered(self, gen: SidebarGenerator) -> None:
        config = SidebarConfig(
            title="Test",
            sections=[SidebarSection(title="Sec", pages=["NoSuchPage"])],
        )
        result = gen.generate(pages=["OtherPage"], config=config)
        assert "**Sec**" in result
        assert "coming soon" in result

    def test_generate_with_config_no_sections(self, gen: SidebarGenerator) -> None:
        config = SidebarConfig(title="Custom", sections=[])
        result = gen.generate(config=config)
        assert "## Custom" in result
        # Falls back to DEFAULT_SECTIONS
        assert "**Home**" in result

    def test_generate_footer_content(self, gen: SidebarGenerator) -> None:
        footer = gen.generate_footer()
        assert "Generated by ZERG doc engine" in footer
        assert gen.REPO_URL in footer

    def test_filter_pages_empty_list(self, gen: SidebarGenerator) -> None:
        result = gen._filter_pages([], existing=set())
        assert result == []

    def test_page_display_name_replaces_hyphens(self, gen: SidebarGenerator) -> None:
        config = SidebarConfig(
            title="Test",
            sections=[SidebarSection(title="S", pages=["My-Page-Name"])],
        )
        result = gen.generate(config=config)
        assert "My Page Name" in result

    def test_sidebar_section_defaults(self) -> None:
        section = SidebarSection(title="T", pages=["P"])
        assert section.icon == ""
        assert section.pages == ["P"]

    def test_sidebar_config_defaults(self) -> None:
        config = SidebarConfig()
        assert config.title == "ZERG Wiki"
        assert config.sections == []

    def test_section_with_icon(self, gen: SidebarGenerator) -> None:
        config = SidebarConfig(
            title="W",
            sections=[SidebarSection(title="Icons", pages=["A"], icon=">>")],
        )
        result = gen.generate(config=config)
        assert ">> **Icons**" in result

    def test_empty_pages_section_skipped(self, gen: SidebarGenerator) -> None:
        """A section with an empty pages list should be skipped entirely (line 166)."""
        config = SidebarConfig(
            title="Test",
            sections=[
                SidebarSection(title="EmptySection", pages=[]),
                SidebarSection(title="HasPages", pages=["Home"]),
            ],
        )
        result = gen.generate(config=config)
        # The empty section should not appear in output
        assert "EmptySection" not in result
        # The non-empty section should appear
        assert "**HasPages**" in result


# ---------------------------------------------------------------------------
# __init__.py
# ---------------------------------------------------------------------------


class TestDocEngineInit:
    """Tests for zerg.doc_engine.__init__ exports."""

    def test_all_exports(self) -> None:
        import zerg.doc_engine as pkg

        assert "ComponentDetector" in pkg.__all__
        assert "ComponentType" in pkg.__all__

    def test_component_detector_importable(self) -> None:
        from zerg.doc_engine import ComponentDetector

        assert ComponentDetector is not None

    def test_component_type_importable(self) -> None:
        from zerg.doc_engine import ComponentType

        assert ComponentType is not None
        assert hasattr(ComponentType, "MODULE")
        assert hasattr(ComponentType, "COMMAND")
        assert hasattr(ComponentType, "CONFIG")
        assert hasattr(ComponentType, "TYPES")
        assert hasattr(ComponentType, "API")


# ---------------------------------------------------------------------------
# Additional publisher edge cases
# ---------------------------------------------------------------------------


class TestWikiPublisherCleanup:
    """Verify temp directory cleanup in various scenarios."""

    @pytest.fixture
    def publisher(self) -> WikiPublisher:
        return WikiPublisher()

    @pytest.fixture
    def wiki_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "pages"
        d.mkdir()
        (d / "A.md").write_text("# A", encoding="utf-8")
        return d

    @patch("zerg.doc_engine.publisher.shutil.rmtree")
    @patch.object(WikiPublisher, "_git", side_effect=subprocess.CalledProcessError(1, "git", stderr="fail"))
    @patch("zerg.doc_engine.publisher.tempfile.mkdtemp")
    def test_tmpdir_cleaned_on_git_error(
        self,
        mock_mkdtemp: MagicMock,
        mock_git: MagicMock,
        mock_rmtree: MagicMock,
        publisher: WikiPublisher,
        wiki_dir: Path,
        tmp_path: Path,
    ) -> None:
        clone_tmp = tmp_path / "zerg-wiki-cleanup"
        clone_tmp.mkdir()
        mock_mkdtemp.return_value = str(clone_tmp)

        publisher.publish(wiki_dir, "https://example.com/repo.wiki.git")

        mock_rmtree.assert_called_once_with(clone_tmp, ignore_errors=True)

    def test_publish_accepts_string_wiki_dir(self, publisher: WikiPublisher, tmp_path: Path) -> None:
        """wiki_dir should accept both str and Path."""
        result = publisher.publish(
            str(tmp_path / "nonexistent"),
            "https://example.com/repo.wiki.git",
        )
        assert result.success is False
        assert "does not exist" in result.error

    @patch.object(WikiPublisher, "_git", side_effect=subprocess.CalledProcessError(1, "git", stderr=None, output=None))
    @patch("zerg.doc_engine.publisher.tempfile.mkdtemp")
    def test_git_failure_no_stderr_no_stdout(
        self,
        mock_mkdtemp: MagicMock,
        mock_git: MagicMock,
        publisher: WikiPublisher,
        wiki_dir: Path,
        tmp_path: Path,
    ) -> None:
        clone_tmp = tmp_path / "zerg-wiki-nostd"
        clone_tmp.mkdir()
        mock_mkdtemp.return_value = str(clone_tmp)

        result = publisher.publish(wiki_dir, "https://example.com/repo.wiki.git")

        assert result.success is False
        assert "Git operation failed" in result.error
