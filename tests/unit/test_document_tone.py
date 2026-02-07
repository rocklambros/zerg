"""Tests for the --tone flag on zerg/commands/document.py.

Covers: default tone, explicit tones, invalid tone, and tone file existence.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


def _make_mock_doc_engine():
    """Return a dict of mock classes for all doc_engine imports."""
    mock_detector = MagicMock()
    mock_extractor = MagicMock()
    mock_mapper = MagicMock()
    mock_mermaid = MagicMock()
    mock_renderer = MagicMock()
    mock_crossref = MagicMock()

    mock_renderer_inst = mock_renderer.return_value
    mock_renderer_inst.render.return_value = "# Mock Docs"

    mock_extractor_inst = mock_extractor.return_value
    mock_extractor_inst.extract.return_value = MagicMock(
        classes=[MagicMock()],
        functions=[MagicMock()],
    )

    return {
        "ComponentDetector": mock_detector,
        "SymbolExtractor": mock_extractor,
        "DependencyMapper": mock_mapper,
        "MermaidGenerator": mock_mermaid,
        "DocRenderer": mock_renderer,
        "CrossRefBuilder": mock_crossref,
    }


class TestDocumentTone:
    """Tests for the --tone flag on the document command."""

    @pytest.fixture()
    def runner(self):
        return CliRunner()

    @pytest.fixture()
    def mocks(self):
        return _make_mock_doc_engine()

    def _invoke(self, runner, mocks, tmp_path, extra_args=None):
        """Helper to invoke the document command with mocked doc_engine."""
        from zerg.commands.document import document

        target = tmp_path / "module.py"
        target.write_text("# module code\ndef hello(): pass")

        from zerg.doc_engine.detector import ComponentType

        detector_inst = mocks["ComponentDetector"].return_value
        detector_inst.detect.return_value = ComponentType.MODULE

        args = [str(target)]
        if extra_args:
            args.extend(extra_args)

        with (
            patch("zerg.doc_engine.crossref.CrossRefBuilder", mocks["CrossRefBuilder"]),
            patch("zerg.doc_engine.dependencies.DependencyMapper", mocks["DependencyMapper"]),
            patch("zerg.doc_engine.detector.ComponentDetector", mocks["ComponentDetector"]),
            patch("zerg.doc_engine.extractor.SymbolExtractor", mocks["SymbolExtractor"]),
            patch("zerg.doc_engine.mermaid.MermaidGenerator", mocks["MermaidGenerator"]),
            patch("zerg.doc_engine.renderer.DocRenderer", mocks["DocRenderer"]),
        ):
            result = runner.invoke(document, args, catch_exceptions=False)

        return result

    def test_default_tone_is_educational(self, runner, mocks, tmp_path):
        """Without --tone flag, the default tone is educational."""
        result = self._invoke(runner, mocks, tmp_path)
        assert result.exit_code == 0
        assert "Tone:" in result.output
        assert "educational" in result.output

    def test_explicit_tone_reference(self, runner, mocks, tmp_path):
        """--tone reference is accepted and displayed."""
        result = self._invoke(runner, mocks, tmp_path, ["--tone", "reference"])
        assert result.exit_code == 0
        assert "reference" in result.output

    def test_explicit_tone_tutorial(self, runner, mocks, tmp_path):
        """--tone tutorial is accepted and displayed."""
        result = self._invoke(runner, mocks, tmp_path, ["--tone", "tutorial"])
        assert result.exit_code == 0
        assert "tutorial" in result.output

    def test_explicit_tone_educational(self, runner, mocks, tmp_path):
        """--tone educational is accepted and displayed."""
        result = self._invoke(runner, mocks, tmp_path, ["--tone", "educational"])
        assert result.exit_code == 0
        assert "educational" in result.output

    def test_invalid_tone_rejected(self, runner, tmp_path):
        """Invalid --tone value is rejected by Click."""
        from zerg.commands.document import document

        target = tmp_path / "module.py"
        target.write_text("# module")

        result = runner.invoke(document, [str(target), "--tone", "bogus"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid choice" in result.output.lower()

    def test_tone_definition_files_exist(self):
        """All tone definition files exist at expected paths."""
        tones_dir = Path("zerg/data/tones")
        for tone in ["educational", "reference", "tutorial"]:
            tone_file = tones_dir / f"{tone}.md"
            assert tone_file.exists(), f"Missing tone file: {tone_file}"
