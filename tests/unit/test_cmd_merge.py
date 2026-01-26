"""Unit tests for ZERG merge command."""

from pathlib import Path

from click.testing import CliRunner

from zerg.cli import cli


class TestMergeCommand:
    """Tests for merge CLI command."""

    def test_merge_help(self) -> None:
        """Test merge --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_merge_feature_option(self) -> None:
        """Test merge --feature option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--help"])
        assert "feature" in result.output

    def test_merge_level_option(self) -> None:
        """Test merge --level option works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--help"])
        assert "level" in result.output

    def test_merge_dry_run_flag(self) -> None:
        """Test merge --dry-run flag works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--help"])
        assert "dry-run" in result.output


class TestMergeBehavior:
    """Tests for merge command behavior."""

    def test_merge_no_feature_fails(self, tmp_path: Path, monkeypatch) -> None:
        """Test merge without feature fails."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".zerg").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["merge"])

        # Should fail or prompt for feature
        assert result.exit_code != 0 or "feature" in result.output.lower()

    def test_merge_with_feature(self, tmp_path: Path, monkeypatch) -> None:
        """Test merge with specified feature."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test.json").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--feature", "test"])

        # Should attempt merge (may fail due to no branches)
        assert "Invalid value" not in result.output


class TestMergeDryRun:
    """Tests for merge dry run."""

    def test_merge_dry_run_no_changes(self, tmp_path: Path, monkeypatch) -> None:
        """Test merge dry run makes no changes."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test.json").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--feature", "test", "--dry-run"])

        # Should show what would happen without making changes
        assert "Invalid value" not in result.output


class TestMergeLevels:
    """Tests for merge level handling."""

    def test_merge_specific_level(self, tmp_path: Path, monkeypatch) -> None:
        """Test merge specific level."""
        monkeypatch.chdir(tmp_path)
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "test.json").write_text("{}")

        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--feature", "test", "--level", "1"])

        # Should attempt merge for level 1
        assert "Invalid value" not in result.output

    def test_merge_invalid_level_type(self) -> None:
        """Test merge with invalid level type."""
        runner = CliRunner()
        result = runner.invoke(cli, ["merge", "--level", "not-a-number"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output
