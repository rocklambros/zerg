"""Tests for zerg/commands/install_commands.py — COV-009."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from zerg.commands.install_commands import (
    CANONICAL_PREFIX,
    COMMAND_GLOB,
    SHORTCUT_PREFIX,
    _get_source_dir,
    _get_target_dir,
    _install,
    _install_shortcut_redirects,
    _install_to_subdir,
    _remove_legacy,
    _uninstall,
    auto_install_commands,
    install_commands,
    uninstall_commands,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_md_files(directory: Path, names: list[str] | None = None) -> list[Path]:
    """Create .md command files in the given directory."""
    names = names or ["init.md", "rush.md", "plan.md"]
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        p = directory / name
        p.write_text(f"# {name}\n")
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# _get_source_dir / _get_target_dir
# ---------------------------------------------------------------------------


class TestGetSourceDir:
    """Tests for _get_source_dir()."""

    def test_importlib_exception_falls_back(self, tmp_path: Path) -> None:
        """When importlib.resources raises, fall back to path traversal."""
        with patch("importlib.resources.files", side_effect=Exception("nope")):
            result = _get_source_dir()
            assert result.is_dir()

    def test_both_fail_raises(self, tmp_path: Path) -> None:
        """When both importlib and fallback fail, raise FileNotFoundError."""
        with (
            patch("importlib.resources.files", side_effect=Exception("nope")),
            patch("zerg.commands.install_commands.Path.is_dir", return_value=False),
        ):
            with pytest.raises(FileNotFoundError, match="Cannot locate ZERG command files"):
                _get_source_dir()


class TestGetTargetDir:
    """Tests for _get_target_dir()."""

    def test_default_target(self, tmp_path: Path) -> None:
        """With None, returns ~/.claude/commands/ and creates it."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        with patch("zerg.commands.install_commands.Path.home", return_value=fake_home):
            result = _get_target_dir(None)
            assert result == fake_home / ".claude" / "commands"
            assert result.is_dir()

    def test_custom_target(self, tmp_path: Path) -> None:
        """With explicit path string, expands and creates it."""
        custom = tmp_path / "custom" / "commands"
        result = _get_target_dir(str(custom))
        assert result == custom.resolve()
        assert result.is_dir()


# ---------------------------------------------------------------------------
# _install_to_subdir
# ---------------------------------------------------------------------------


class TestInstallToSubdir:
    """Tests for _install_to_subdir()."""

    @pytest.mark.parametrize(
        "os_name,copy_flag,expect_symlink",
        [
            ("posix", False, True),
            ("nt", False, False),
            ("posix", True, False),
        ],
        ids=["posix-symlink", "windows-copy", "force-copy"],
    )
    def test_install_method(self, tmp_path: Path, os_name: str, copy_flag: bool, expect_symlink: bool) -> None:
        """Files are symlinked on posix, copied on windows or with copy=True."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "zerg"
        _create_md_files(source)
        with patch("zerg.commands.install_commands.os.name", os_name):
            count = _install_to_subdir(target, source, copy=copy_flag)
        assert count == 3
        for f in target.glob(COMMAND_GLOB):
            assert f.is_symlink() == expect_symlink

    def test_force_overwrites_existing(self, tmp_path: Path) -> None:
        """force=True overwrites existing files."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "zerg"
        _create_md_files(source)
        target.mkdir(parents=True)
        (target / "init.md").write_text("old content")
        with patch("zerg.commands.install_commands.os.name", "posix"):
            count = _install_to_subdir(target, source, force=True)
        assert count == 3
        assert (target / "init.md").is_symlink()

    def test_no_source_files_raises(self, tmp_path: Path) -> None:
        """Empty source directory raises FileNotFoundError."""
        source = tmp_path / "empty_source"
        source.mkdir()
        with pytest.raises(FileNotFoundError, match="No command files found"):
            _install_to_subdir(tmp_path / "target" / "zerg", source)


# ---------------------------------------------------------------------------
# _install_shortcut_redirects
# ---------------------------------------------------------------------------


class TestInstallShortcutRedirects:
    """Tests for _install_shortcut_redirects()."""

    def test_creates_redirect_files(self, tmp_path: Path) -> None:
        """Redirect files contain the expected content."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "z"
        _create_md_files(source, ["rush.md", "plan.md"])
        count = _install_shortcut_redirects(target, source)
        assert count == 2
        assert "zerg:rush" in (target / "rush.md").read_text()

    def test_force_overwrites(self, tmp_path: Path) -> None:
        """force=True overwrites existing files."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "z"
        _create_md_files(source, ["rush.md"])
        target.mkdir(parents=True)
        (target / "rush.md").write_text("old")
        count = _install_shortcut_redirects(target, source, force=True)
        assert count == 1
        assert "zerg:rush" in (target / "rush.md").read_text()


# ---------------------------------------------------------------------------
# _install / _uninstall / _remove_legacy
# ---------------------------------------------------------------------------


class TestInstallUninstall:
    """Tests for _install, _uninstall, and _remove_legacy."""

    def test_installs_both_canonical_and_shortcuts(self, tmp_path: Path) -> None:
        """Installs into zerg/ and z/ subdirectories."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md", "rush.md"])
        count = _install(target, source, copy=True)
        assert count == 4
        assert (target / CANONICAL_PREFIX / "init.md").exists()
        assert (target / SHORTCUT_PREFIX / "rush.md").exists()

    def test_uninstall_removes_installed(self, tmp_path: Path) -> None:
        """Uninstall removes .md files from zerg/ and z/ subdirs."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md", "rush.md"])
        _install(target, source, copy=True)
        removed = _uninstall(target)
        assert removed == 4

    def test_remove_legacy_files(self, tmp_path: Path) -> None:
        """Removes zerg:*.md and z:*.md from root target dir."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "zerg:init.md").write_text("legacy")
        (target / "z:init.md").write_text("legacy")
        (target / "keep.md").write_text("keep")
        removed = _remove_legacy(target)
        assert removed == 2
        assert (target / "keep.md").exists()

    def test_uninstall_nothing_returns_zero(self, tmp_path: Path) -> None:
        """Returns 0 when nothing to remove."""
        target = tmp_path / "empty"
        target.mkdir()
        assert _uninstall(target) == 0


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


class TestCLI:
    """Tests for install/uninstall Click commands."""

    def test_fresh_install(self, tmp_path: Path) -> None:
        """Full install to empty target reports installed count."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md", "rush.md"])
        runner = CliRunner()
        with patch("zerg.commands.install_commands._get_source_dir", return_value=source):
            result = runner.invoke(install_commands, ["--target", str(target), "--copy"])
        assert result.exit_code == 0
        assert "Installed" in result.output

    def test_install_error_handling(self) -> None:
        """Errors are printed and exit code is 1."""
        runner = CliRunner()
        with patch("zerg.commands.install_commands._get_source_dir", side_effect=FileNotFoundError("boom")):
            result = runner.invoke(install_commands, ["--target", "/dev/null/bad"])
        assert result.exit_code == 1

    def test_uninstall_nothing(self, tmp_path: Path) -> None:
        """When nothing installed, reports no commands found."""
        target = tmp_path / "empty"
        target.mkdir()
        runner = CliRunner()
        result = runner.invoke(uninstall_commands, ["--target", str(target)])
        assert result.exit_code == 0
        assert "No ZERG commands found" in result.output


# ---------------------------------------------------------------------------
# auto_install_commands
# ---------------------------------------------------------------------------


class TestAutoInstallCommands:
    """Tests for auto_install_commands()."""

    def test_skips_when_sentinel_exists(self, tmp_path: Path) -> None:
        """Does nothing when init.md already present."""
        sentinel = tmp_path / ".claude" / "commands" / "zerg" / "init.md"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("exists")
        with patch("zerg.commands.install_commands.Path.home", return_value=tmp_path):
            with patch("zerg.commands.install_commands._install") as mock_install:
                auto_install_commands()
                mock_install.assert_not_called()

    def test_suppresses_exceptions(self, tmp_path: Path) -> None:
        """Errors are logged but not raised."""
        with (
            patch("zerg.commands.install_commands.Path.home", return_value=tmp_path),
            patch("zerg.commands.install_commands._get_source_dir", side_effect=FileNotFoundError("gone")),
        ):
            auto_install_commands()  # Should not raise
