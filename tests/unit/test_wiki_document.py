"""Tests for zerg/commands/wiki.py and zerg/commands/document.py.

Covers all functions, branches, and edge cases with mocked doc_engine dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_doc_engine():
    """Return a dict of mock classes for all doc_engine imports."""
    mock_detector = MagicMock()
    mock_extractor = MagicMock()
    mock_mapper = MagicMock()
    mock_mermaid = MagicMock()
    mock_renderer = MagicMock()
    mock_crossref = MagicMock()
    mock_sidebar = MagicMock()

    # Default return values
    mock_renderer_inst = mock_renderer.return_value
    mock_renderer_inst.render.return_value = "# Mock Page\nContent here"

    mock_crossref_inst = mock_crossref.return_value
    mock_crossref_inst.build_glossary.return_value = []
    mock_crossref_inst.generate_glossary_page.return_value = "# Glossary"

    mock_sidebar_inst = mock_sidebar.return_value
    mock_sidebar_inst.generate.return_value = "## Sidebar"

    mock_extractor_inst = mock_extractor.return_value
    mock_extractor_inst.extract.return_value = MagicMock(
        classes=[MagicMock()],
        functions=[MagicMock(), MagicMock()],
    )

    return {
        "ComponentDetector": mock_detector,
        "SymbolExtractor": mock_extractor,
        "DependencyMapper": mock_mapper,
        "MermaidGenerator": mock_mermaid,
        "DocRenderer": mock_renderer,
        "CrossRefBuilder": mock_crossref,
        "SidebarGenerator": mock_sidebar,
    }


# ======================================================================
# wiki command tests
# ======================================================================


class TestWikiCommand:
    """Tests for the wiki click command."""

    @pytest.fixture()
    def runner(self):
        return CliRunner()

    @pytest.fixture()
    def mocks(self):
        return _make_mock_doc_engine()

    def test_wiki_default_incremental_mode(self, runner, tmp_path, mocks):
        """Default invocation uses incremental mode."""
        from zerg.commands.wiki import wiki

        zerg_dir = tmp_path / "zerg"
        zerg_dir.mkdir()
        (zerg_dir / "foo.py").write_text("# foo module")

        output_dir = tmp_path / "wiki_out"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob") as mock_rglob,
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            mock_rglob.return_value = [zerg_dir / "foo.py"]
            result = runner.invoke(
                wiki,
                ["--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "incremental" in result.output

    def test_wiki_full_mode(self, runner, tmp_path, mocks):
        """--full flag activates full regeneration mode."""
        from zerg.commands.wiki import wiki

        output_dir = tmp_path / "wiki_out"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob", return_value=[]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--full", "--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "full" in result.output

    def test_wiki_dry_run_no_files_written(self, runner, tmp_path, mocks):
        """--dry-run flag prints message and skips file writes."""
        from zerg.commands.wiki import wiki

        output_dir = tmp_path / "wiki_out"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob", return_value=[]),
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("pathlib.Path.write_text") as mock_write,
        ):
            result = runner.invoke(
                wiki,
                ["--dry-run", "--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Dry run" in result.output
        mock_mkdir.assert_not_called()
        mock_write.assert_not_called()

    def test_wiki_generates_pages(self, runner, tmp_path, mocks):
        """Wiki generates pages from discovered Python files."""
        from zerg.commands.wiki import wiki

        zerg_dir = tmp_path / "zerg"
        zerg_dir.mkdir()
        py_file = zerg_dir / "launcher.py"
        py_file.write_text("# launcher")

        output_dir = tmp_path / "wiki_out"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob", return_value=[py_file]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Generated 1 pages" in result.output

    def test_wiki_skips_dunder_files(self, runner, tmp_path, mocks):
        """Files starting with __ are excluded from page generation."""
        from zerg.commands.wiki import wiki

        zerg_dir = tmp_path / "zerg"
        zerg_dir.mkdir()
        init_file = zerg_dir / "__init__.py"
        init_file.write_text("")
        normal_file = zerg_dir / "core.py"
        normal_file.write_text("# core")

        output_dir = tmp_path / "wiki_out"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob", return_value=[init_file, normal_file]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Generated 1 pages from 1 source files" in result.output

    def test_wiki_render_failure_continues(self, runner, tmp_path, mocks):
        """If rendering a page fails, the wiki continues with remaining files."""
        from zerg.commands.wiki import wiki

        zerg_dir = tmp_path / "zerg"
        zerg_dir.mkdir()
        file_a = zerg_dir / "good.py"
        file_a.write_text("# good")
        file_b = zerg_dir / "bad.py"
        file_b.write_text("# bad")

        output_dir = tmp_path / "wiki_out"

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.side_effect = [
            RuntimeError("parse error"),
            "# Good Page",
        ]

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob", return_value=[file_b, file_a]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Generated 1 pages from 2 source files" in result.output

    def test_wiki_glossary_written_when_present(self, runner, tmp_path, mocks):
        """Glossary page is written when crossref returns entries."""
        from zerg.commands.wiki import wiki

        zerg_dir = tmp_path / "zerg"
        zerg_dir.mkdir()
        py_file = zerg_dir / "mod.py"
        py_file.write_text("# mod")

        output_dir = tmp_path / "wiki_out"

        crossref_inst = mocks["CrossRefBuilder"].return_value
        glossary_entry = MagicMock()
        crossref_inst.build_glossary.return_value = [glossary_entry]
        crossref_inst.generate_glossary_page.return_value = "# Glossary\nTerms here"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob", return_value=[py_file]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        crossref_inst.generate_glossary_page.assert_called_once()

    def test_wiki_glossary_not_written_in_dry_run(self, runner, tmp_path, mocks):
        """Glossary is not written to disk during dry run even if entries exist."""
        from zerg.commands.wiki import wiki

        crossref_inst = mocks["CrossRefBuilder"].return_value
        crossref_inst.build_glossary.return_value = [MagicMock()]
        crossref_inst.generate_glossary_page.return_value = "# Glossary"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob", return_value=[]),
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("pathlib.Path.write_text") as mock_write,
        ):
            result = runner.invoke(
                wiki,
                ["--dry-run"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        mock_mkdir.assert_not_called()
        mock_write.assert_not_called()

    def test_wiki_push_success(self, runner, tmp_path, mocks):
        """--push flag triggers WikiPublisher with correct wiki URL."""
        from zerg.commands.wiki import wiki

        output_dir = tmp_path / "wiki_out"

        mock_publisher = MagicMock()
        pub_result = MagicMock(success=True, pages_copied=5)
        mock_publisher.return_value.publish.return_value = pub_result

        mock_subprocess_result = MagicMock(
            returncode=0,
            stdout="https://github.com/user/repo.git\n",
        )

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("zerg.doc_engine.publisher.WikiPublisher", mock_publisher),
            patch("subprocess.run", return_value=mock_subprocess_result),
            patch("pathlib.Path.rglob", return_value=[]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--push", "--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Pushed 5 pages" in result.output
        mock_publisher.return_value.publish.assert_called_once()
        call_args = mock_publisher.return_value.publish.call_args
        assert call_args[0][1] == "https://github.com/user/repo.wiki.git"

    def test_wiki_push_url_without_git_suffix(self, runner, tmp_path, mocks):
        """Push appends .wiki.git when remote URL has no .git suffix."""
        from zerg.commands.wiki import wiki

        output_dir = tmp_path / "wiki_out"

        mock_publisher = MagicMock()
        pub_result = MagicMock(success=True, pages_copied=3)
        mock_publisher.return_value.publish.return_value = pub_result

        mock_subprocess_result = MagicMock(
            returncode=0,
            stdout="https://github.com/user/repo\n",
        )

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("zerg.doc_engine.publisher.WikiPublisher", mock_publisher),
            patch("subprocess.run", return_value=mock_subprocess_result),
            patch("pathlib.Path.rglob", return_value=[]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--push", "--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        call_args = mock_publisher.return_value.publish.call_args
        assert call_args[0][1] == "https://github.com/user/repo.wiki.git"

    def test_wiki_push_git_remote_failure(self, runner, tmp_path, mocks):
        """Push exits with error when git remote detection fails."""
        from zerg.commands.wiki import wiki

        output_dir = tmp_path / "wiki_out"

        mock_subprocess_result = MagicMock(returncode=1, stdout="")

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("subprocess.run", return_value=mock_subprocess_result),
            patch("pathlib.Path.rglob", return_value=[]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--push", "--output", str(output_dir)],
            )

        assert result.exit_code != 0
        assert "Could not detect git remote" in result.output

    def test_wiki_push_publish_failure(self, runner, tmp_path, mocks):
        """Push exits with error when publisher reports failure."""
        from zerg.commands.wiki import wiki

        output_dir = tmp_path / "wiki_out"

        mock_publisher = MagicMock()
        pub_result = MagicMock(success=False, error="auth failed")
        mock_publisher.return_value.publish.return_value = pub_result

        mock_subprocess_result = MagicMock(
            returncode=0,
            stdout="https://github.com/user/repo.git\n",
        )

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("zerg.doc_engine.publisher.WikiPublisher", mock_publisher),
            patch("subprocess.run", return_value=mock_subprocess_result),
            patch("pathlib.Path.rglob", return_value=[]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--push", "--output", str(output_dir)],
            )

        assert result.exit_code != 0
        assert "auth failed" in result.output

    def test_wiki_unexpected_exception_exits_1(self, runner, mocks):
        """Unexpected exception is caught and prints error."""
        from zerg.commands.wiki import wiki

        mocks["DependencyMapper"].return_value.build.side_effect = RuntimeError("boom")

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.mkdir"),
        ):
            result = runner.invoke(wiki, [])

        assert result.exit_code != 0
        assert "boom" in result.output

    def test_wiki_sidebar_written(self, runner, tmp_path, mocks):
        """Sidebar file is generated and written when not dry run."""
        from zerg.commands.wiki import wiki

        output_dir = tmp_path / "wiki_out"

        sidebar_inst = mocks["SidebarGenerator"].return_value
        sidebar_inst.generate.return_value = "## ZERG Wiki\n\n**Reference**"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob", return_value=[]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(
                wiki,
                ["--output", str(output_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        sidebar_inst.generate.assert_called_once()

    def test_wiki_default_output_path(self, runner, mocks):
        """Default output path is .zerg/wiki when --output is not specified."""
        from zerg.commands.wiki import wiki

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            patch("zerg.doc_engine.sidebar.SidebarGenerator", mocks["SidebarGenerator"]),
            patch("pathlib.Path.rglob", return_value=[]),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.write_text"),
        ):
            result = runner.invoke(wiki, [], catch_exceptions=False)

        assert result.exit_code == 0
        assert ".zerg/wiki" in result.output


# ======================================================================
# document command tests
# ======================================================================


class TestDocumentCommand:
    """Tests for the document click command."""

    @pytest.fixture()
    def runner(self):
        return CliRunner()

    @pytest.fixture()
    def mocks(self):
        return _make_mock_doc_engine()

    def test_document_file_not_found(self, runner):
        """Command exits with error when target file does not exist."""
        from zerg.commands.document import document

        result = runner.invoke(document, ["/nonexistent/path.py"])
        assert result.exit_code != 0
        assert "File not found" in result.output

    def test_document_auto_detect_type(self, runner, tmp_path, mocks):
        """Auto-detection is used when --type is auto (default)."""
        from zerg.commands.document import document

        target = tmp_path / "module.py"
        target.write_text("# module code\ndef hello(): pass")

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Module Docs"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(
                document,
                [str(target)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Detected type" in result.output
        detector_inst.detect.assert_called_once()

    def test_document_explicit_type_override(self, runner, tmp_path, mocks):
        """--type flag overrides auto-detection."""
        from zerg.commands.document import document

        target = tmp_path / "config.py"
        target.write_text("# config")

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Config Docs"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.detector.ComponentType") as MockComponentType,
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            MockComponentType.return_value = MagicMock(value="config")
            result = runner.invoke(
                document,
                [str(target), "--type", "config"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Using type" in result.output

    def test_document_output_to_file(self, runner, tmp_path, mocks):
        """--output flag writes documentation to a file."""
        from zerg.commands.document import document

        target = tmp_path / "mymod.py"
        target.write_text("# my module")

        output_file = tmp_path / "docs" / "mymod.md"

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Generated Docs"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(
                document,
                [str(target), "--output", str(output_file)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Documentation written to" in result.output
        assert output_file.read_text() == "# Generated Docs"

    def test_document_output_to_stdout(self, runner, tmp_path, mocks):
        """Without --output, documentation is printed to console."""
        from zerg.commands.document import document

        target = tmp_path / "mymod.py"
        target.write_text("# my module")

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Rendered Documentation"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(
                document,
                [str(target)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Rendered Documentation" in result.output

    def test_document_shows_extraction_stats(self, runner, tmp_path, mocks):
        """Output includes class and function counts from extraction."""
        from zerg.commands.document import document

        target = tmp_path / "mymod.py"
        target.write_text("class Foo: pass")

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        extractor_inst = mocks["SymbolExtractor"].return_value
        extractor_inst.extract.return_value = MagicMock(
            classes=[MagicMock(), MagicMock()],
            functions=[MagicMock()],
        )

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Docs"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(
                document,
                [str(target)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "2 classes" in result.output
        assert "1 functions" in result.output

    def test_document_unexpected_exception(self, runner, tmp_path, mocks):
        """Unexpected exception is caught and exits with error."""
        from zerg.commands.document import document

        target = tmp_path / "mymod.py"
        target.write_text("# module")

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        extractor_inst = mocks["SymbolExtractor"].return_value
        extractor_inst.extract.side_effect = RuntimeError("extraction failed")

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(document, [str(target)])

        assert result.exit_code != 0
        assert "extraction failed" in result.output

    def test_document_depth_option(self, runner, tmp_path, mocks):
        """--depth option is accepted without error."""
        from zerg.commands.document import document

        target = tmp_path / "mymod.py"
        target.write_text("# module")

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Deep Docs"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(
                document,
                [str(target), "--depth", "deep"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0

    def test_document_update_flag(self, runner, tmp_path, mocks):
        """--update flag is accepted without error."""
        from zerg.commands.document import document

        target = tmp_path / "mymod.py"
        target.write_text("# module")

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Updated Docs"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(
                document,
                [str(target), "--update"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0

    def test_document_all_component_types(self, runner, tmp_path, mocks):
        """All valid --type choices are accepted."""
        from zerg.commands.document import document

        target = tmp_path / "mymod.py"
        target.write_text("# module")

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Docs"

        for ctype in ["module", "command", "config", "api", "types"]:
            with (
                patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
                patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
                patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
                patch("zerg.doc_engine.detector.ComponentType") as MockCT,
                patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
                patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
                patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
            ):
                MockCT.return_value = MagicMock(value=ctype)
                result = runner.invoke(
                    document,
                    [str(target), "--type", ctype],
                    catch_exceptions=False,
                )

            assert result.exit_code == 0, f"Failed for type: {ctype}"

    def test_document_output_creates_parent_dirs(self, runner, tmp_path, mocks):
        """Output path creates parent directories automatically."""
        from zerg.commands.document import document

        target = tmp_path / "mymod.py"
        target.write_text("# module")

        output_file = tmp_path / "deep" / "nested" / "docs" / "out.md"

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Deep Output"

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(
                document,
                [str(target), "--output", str(output_file)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert output_file.exists()
        assert output_file.read_text() == "# Deep Output"

    def test_document_mapper_builds_on_parent_dir(self, runner, tmp_path, mocks):
        """DependencyMapper.build is called with the target's parent directory."""
        from zerg.commands.document import document

        subdir = tmp_path / "src"
        subdir.mkdir()
        target = subdir / "mymod.py"
        target.write_text("# module")

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        renderer_inst = mocks["DocRenderer"].return_value
        renderer_inst.render.return_value = "# Docs"

        mapper_inst = mocks["DependencyMapper"].return_value

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(
                document,
                [str(target)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        mapper_inst.build.assert_called_once_with(subdir)
