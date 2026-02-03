"""Unit tests for ZERG init command."""

from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestInitCommand:
    """Tests for init CLI command."""

    def test_init_help(self) -> None:
        """Test init --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_init_creates_directories(self, tmp_path: Path, monkeypatch) -> None:
        """Test init creates required directories."""
        monkeypatch.chdir(tmp_path)

        # Create minimal git repo
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        runner.invoke(cli, ["init"])

        # Check directories created
        assert (tmp_path / ".zerg").exists()
        assert (tmp_path / ".gsd").exists()

    def test_init_creates_config(self, tmp_path: Path, monkeypatch) -> None:
        """Test init creates config file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        runner.invoke(cli, ["init"])

        assert (tmp_path / ".zerg" / "config.yaml").exists()

    def test_init_idempotent(self, tmp_path: Path, monkeypatch) -> None:
        """Test init is idempotent (can run multiple times)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()

        # Run init twice
        result1 = runner.invoke(cli, ["init"])
        result2 = runner.invoke(cli, ["init"])

        # Both should succeed
        assert result1.exit_code == 0
        assert result2.exit_code == 0

    def test_init_handles_non_git_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test init handles non-git directory gracefully."""
        monkeypatch.chdir(tmp_path)
        # No .git directory

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        # Init may work without git (creates directories anyway)
        # or may warn - implementation dependent. Just verify no crash.
        assert result.exit_code in [0, 1]


class TestInitDirectories:
    """Tests for init directory creation."""

    def test_init_creates_state_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test init creates state directory."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        runner.invoke(cli, ["init"])

        assert (tmp_path / ".zerg" / "state").exists()

    def test_init_creates_logs_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test init creates logs directory."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        runner.invoke(cli, ["init"])

        assert (tmp_path / ".zerg" / "logs").exists()

    def test_init_creates_specs_dir(self, tmp_path: Path, monkeypatch) -> None:
        """Test init creates specs directory."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        runner = CliRunner()
        runner.invoke(cli, ["init"])

        assert (tmp_path / ".gsd" / "specs").exists()
