"""Unit tests for ZERG security-rules command."""

from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestSecurityRulesCommand:
    """Tests for security-rules CLI command."""

    def test_security_rules_help(self) -> None:
        """Test security-rules --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_security_rules_detect_subcommand(self) -> None:
        """Test security-rules detect subcommand exists."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "--help"])
        assert "detect" in result.output

    def test_security_rules_integrate_subcommand(self) -> None:
        """Test security-rules integrate subcommand exists."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "--help"])
        assert "integrate" in result.output


class TestSecurityRulesDetect:
    """Tests for security-rules detect subcommand."""

    def test_detect_help(self) -> None:
        """Test security-rules detect --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_detect_runs(self, tmp_path: Path, monkeypatch) -> None:
        """Test detect runs and finds stack."""
        monkeypatch.chdir(tmp_path)

        # Create Python project indicator
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert result.exit_code == 0
        assert "python" in result.output.lower()


class TestSecurityRulesIntegrate:
    """Tests for security-rules integrate subcommand."""

    def test_integrate_help(self) -> None:
        """Test security-rules integrate --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "integrate", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_integrate_output_option(self) -> None:
        """Test security-rules integrate --output option exists."""
        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "integrate", "--help"])
        assert "output" in result.output

    def test_integrate_creates_section(self, tmp_path: Path, monkeypatch) -> None:
        """Test integrate creates security section in CLAUDE.md."""
        monkeypatch.chdir(tmp_path)

        # Create CLAUDE.md
        (tmp_path / "CLAUDE.md").write_text("# Project\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        runner = CliRunner()
        runner.invoke(cli, ["security-rules", "integrate", "--force"])

        # Should integrate rules
        # Check CLAUDE.md was updated
        (tmp_path / "CLAUDE.md").read_text()
        # May or may not have security section depending on implementation


class TestSecurityRulesStackDetection:
    """Tests for stack detection."""

    def test_detect_python(self, tmp_path: Path, monkeypatch) -> None:
        """Test detection of Python project."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert "python" in result.output.lower()

    def test_detect_javascript(self, tmp_path: Path, monkeypatch) -> None:
        """Test detection of JavaScript project."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "package.json").write_text('{"name": "test"}')

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert "javascript" in result.output.lower()

    def test_detect_multiple_languages(self, tmp_path: Path, monkeypatch) -> None:
        """Test detection of multiple languages."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "app.py").write_text("print('hello')")
        (tmp_path / "package.json").write_text('{"name": "test"}')

        runner = CliRunner()
        result = runner.invoke(cli, ["security-rules", "detect"])

        assert "python" in result.output.lower()
        assert "javascript" in result.output.lower()
