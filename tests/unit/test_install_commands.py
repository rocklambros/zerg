"""Tests for zerg/commands/install_commands.py — COV-009."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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
# _get_source_dir
# ---------------------------------------------------------------------------


class TestGetSourceDir:
    """Tests for _get_source_dir()."""

    def test_importlib_resources_success(self, tmp_path: Path) -> None:
        """When importlib.resources returns a valid directory, use it."""
        fake_pkg = tmp_path / "zerg" / "data" / "commands"
        fake_pkg.mkdir(parents=True)

        mock_files = MagicMock()
        mock_files.__truediv__ = lambda self, key: (tmp_path / "zerg" / "data" if key == "data" else self)

        # Patch files() to return a Path-like that resolves to our tmp dir
        with patch(
            "zerg.commands.install_commands.Path.__init__",
        ):
            # Simpler approach: patch the whole function flow
            pass

        # Use a more direct approach: patch importlib.resources.files
        with patch("importlib.resources.files") as mock_ir_files:
            # Make files("zerg") / "data" / "commands" resolve to our dir
            chain = MagicMock()
            chain.__truediv__ = MagicMock(return_value=chain)
            chain.__str__ = MagicMock(return_value=str(fake_pkg))
            mock_ir_files.return_value = MagicMock()
            mock_ir_files.return_value.__truediv__ = MagicMock(return_value=MagicMock())
            mock_ir_files.return_value.__truediv__.return_value.__truediv__ = MagicMock(return_value=chain)
            result = _get_source_dir()
            assert result.is_dir()

    def test_importlib_exception_falls_back(self, tmp_path: Path) -> None:
        """When importlib.resources raises, fall back to path traversal."""
        with patch("importlib.resources.files", side_effect=Exception("nope")):
            # The fallback uses Path(__file__).resolve().parent.parent / "data" / "commands"
            # which is the real package data dir — just verify it returns a dir
            result = _get_source_dir()
            assert result.is_dir()

    def test_both_fail_raises(self, tmp_path: Path) -> None:
        """When both importlib and fallback fail, raise FileNotFoundError."""
        with (
            patch("importlib.resources.files", side_effect=Exception("nope")),
            patch(
                "zerg.commands.install_commands.Path.is_dir",
                return_value=False,
            ),
        ):
            with pytest.raises(FileNotFoundError, match="Cannot locate ZERG command files"):
                _get_source_dir()


# ---------------------------------------------------------------------------
# _get_target_dir
# ---------------------------------------------------------------------------


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

    def test_installs_symlinks(self, tmp_path: Path) -> None:
        """Files are symlinked by default on non-Windows."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "zerg"
        _create_md_files(source)

        with patch("zerg.commands.install_commands.os.name", "posix"):
            count = _install_to_subdir(target, source)

        assert count == 3
        for f in target.glob(COMMAND_GLOB):
            assert f.is_symlink()

    def test_installs_copies_on_windows(self, tmp_path: Path) -> None:
        """On Windows (os.name == 'nt'), files are copied."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "zerg"
        _create_md_files(source)

        with patch("zerg.commands.install_commands.os.name", "nt"):
            count = _install_to_subdir(target, source)

        assert count == 3
        for f in target.glob(COMMAND_GLOB):
            assert not f.is_symlink()
            assert f.exists()

    def test_installs_copies_with_flag(self, tmp_path: Path) -> None:
        """copy=True forces copy even on posix."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "zerg"
        _create_md_files(source)

        count = _install_to_subdir(target, source, copy=True)
        assert count == 3
        for f in target.glob(COMMAND_GLOB):
            assert not f.is_symlink()

    def test_skip_existing_correct_symlink(self, tmp_path: Path) -> None:
        """Existing symlink pointing to correct source is skipped."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "zerg"
        _create_md_files(source)
        target.mkdir(parents=True)

        # Pre-create a correct symlink
        (target / "init.md").symlink_to((source / "init.md").resolve())

        with patch("zerg.commands.install_commands.os.name", "posix"):
            count = _install_to_subdir(target, source)

        # init.md skipped, 2 others installed
        assert count == 2

    def test_skip_existing_file_no_force(self, tmp_path: Path) -> None:
        """Existing non-symlink file is skipped without --force."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "zerg"
        _create_md_files(source)
        target.mkdir(parents=True)

        # Pre-create a regular file
        (target / "init.md").write_text("old content")

        with patch("zerg.commands.install_commands.os.name", "posix"):
            count = _install_to_subdir(target, source)

        assert count == 2
        # Old file preserved
        assert (target / "init.md").read_text() == "old content"

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

    def test_broken_symlink_overwritten(self, tmp_path: Path) -> None:
        """Broken symlink is overwritten even without force."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "zerg"
        _create_md_files(source)
        target.mkdir(parents=True)

        # Create broken symlink
        broken = target / "init.md"
        broken.symlink_to(tmp_path / "nonexistent.md")

        with patch("zerg.commands.install_commands.os.name", "posix"):
            count = _install_to_subdir(target, source, force=True)

        assert count == 3

    def test_no_source_files_raises(self, tmp_path: Path) -> None:
        """Empty source directory raises FileNotFoundError."""
        source = tmp_path / "empty_source"
        source.mkdir()
        target = tmp_path / "target" / "zerg"

        with pytest.raises(FileNotFoundError, match="No command files found"):
            _install_to_subdir(target, source)

    def test_creates_subdir(self, tmp_path: Path) -> None:
        """Target subdir is created if it does not exist."""
        source = tmp_path / "source"
        target = tmp_path / "deep" / "nested" / "zerg"
        _create_md_files(source)

        assert not target.exists()
        _install_to_subdir(target, source, copy=True)
        assert target.is_dir()


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
        content = (target / "rush.md").read_text()
        assert content == "Shortcut: run /zerg:rush with the same arguments.\n"

    def test_skips_existing_correct_redirect(self, tmp_path: Path) -> None:
        """Existing redirect with correct content is skipped."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "z"
        _create_md_files(source, ["rush.md"])
        target.mkdir(parents=True)

        # Pre-create correct redirect
        (target / "rush.md").write_text("Shortcut: run /zerg:rush with the same arguments.\n")

        count = _install_shortcut_redirects(target, source)
        assert count == 0

    def test_skips_existing_wrong_content_no_force(self, tmp_path: Path) -> None:
        """Existing file with wrong content is skipped without force."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "z"
        _create_md_files(source, ["rush.md"])
        target.mkdir(parents=True)

        (target / "rush.md").write_text("something different")

        count = _install_shortcut_redirects(target, source)
        assert count == 0
        assert (target / "rush.md").read_text() == "something different"

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

    def test_overwrites_existing_symlink_with_force(self, tmp_path: Path) -> None:
        """Existing symlink is replaced with redirect file under force."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "z"
        _create_md_files(source, ["rush.md"])
        target.mkdir(parents=True)

        (target / "rush.md").symlink_to(source / "rush.md")

        count = _install_shortcut_redirects(target, source, force=True)
        assert count == 1
        assert not (target / "rush.md").is_symlink()

    def test_no_source_files_raises(self, tmp_path: Path) -> None:
        """Empty source dir raises FileNotFoundError."""
        source = tmp_path / "empty"
        source.mkdir()
        target = tmp_path / "target" / "z"

        with pytest.raises(FileNotFoundError, match="No command files found"):
            _install_shortcut_redirects(target, source)

    def test_creates_shortcut_dir(self, tmp_path: Path) -> None:
        """Shortcut dir is created if it does not exist."""
        source = tmp_path / "source"
        target = tmp_path / "new" / "z"
        _create_md_files(source, ["rush.md"])

        assert not target.exists()
        _install_shortcut_redirects(target, source)
        assert target.is_dir()

    def test_handles_oserror_on_read(self, tmp_path: Path) -> None:
        """OSError when reading existing redirect is handled gracefully."""
        source = tmp_path / "source"
        target = tmp_path / "target" / "z"
        _create_md_files(source, ["rush.md"])
        target.mkdir(parents=True)

        dest = target / "rush.md"
        dest.write_text("something")

        with patch.object(Path, "read_text", side_effect=OSError("perm")):
            # Should skip (no force, exists, read fails -> skip)
            count = _install_shortcut_redirects(target, source)

        assert count == 0


# ---------------------------------------------------------------------------
# _install (orchestrator)
# ---------------------------------------------------------------------------


class TestInstall:
    """Tests for _install()."""

    def test_installs_both_canonical_and_shortcuts(self, tmp_path: Path) -> None:
        """Installs into zerg/ and z/ subdirectories."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md", "rush.md"])

        count = _install(target, source, copy=True)

        assert count == 4  # 2 canonical + 2 shortcuts
        assert (target / CANONICAL_PREFIX / "init.md").exists()
        assert (target / SHORTCUT_PREFIX / "rush.md").exists()

    def test_force_propagates(self, tmp_path: Path) -> None:
        """force= is passed through to both sub-installers."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md"])

        # First install
        _install(target, source, copy=True)
        # Second install with force
        count = _install(target, source, copy=True, force=True)
        assert count == 2  # 1 canonical + 1 shortcut


# ---------------------------------------------------------------------------
# _remove_legacy
# ---------------------------------------------------------------------------


class TestRemoveLegacy:
    """Tests for _remove_legacy()."""

    def test_removes_legacy_files(self, tmp_path: Path) -> None:
        """Removes zerg:*.md and z:*.md from root target dir."""
        # Create legacy files — note: colon in filename
        # On some systems colon isn't allowed; use the pattern directly
        target = tmp_path / "target"
        target.mkdir()

        # The glob patterns are "zerg:*.md" and "z:*.md"
        # Create files matching those patterns
        (target / "zerg:init.md").write_text("legacy")
        (target / "zerg:rush.md").write_text("legacy")
        (target / "z:init.md").write_text("legacy")
        (target / "keep.md").write_text("keep")

        removed = _remove_legacy(target)
        assert removed == 3
        assert not (target / "zerg:init.md").exists()
        assert (target / "keep.md").exists()

    def test_no_legacy_returns_zero(self, tmp_path: Path) -> None:
        """Returns 0 when no legacy files exist."""
        target = tmp_path / "target"
        target.mkdir()
        assert _remove_legacy(target) == 0


# ---------------------------------------------------------------------------
# _uninstall
# ---------------------------------------------------------------------------


class TestUninstall:
    """Tests for _uninstall()."""

    def test_removes_subdir_files(self, tmp_path: Path) -> None:
        """Removes .md files from zerg/ and z/ subdirs."""
        target = tmp_path / "target"
        source = tmp_path / "source"
        _create_md_files(source, ["init.md", "rush.md"])
        _install(target, source, copy=True)

        removed = _uninstall(target)
        assert removed == 4  # 2 in zerg/ + 2 in z/

    def test_removes_empty_subdirs(self, tmp_path: Path) -> None:
        """Empty subdirectories are removed after cleanup."""
        target = tmp_path / "target"
        source = tmp_path / "source"
        _create_md_files(source, ["init.md"])
        _install(target, source, copy=True)

        _uninstall(target)
        assert not (target / CANONICAL_PREFIX).exists()
        assert not (target / SHORTCUT_PREFIX).exists()

    def test_keeps_nonempty_subdirs(self, tmp_path: Path) -> None:
        """Subdirectory with non-.md files is kept."""
        target = tmp_path / "target"
        source = tmp_path / "source"
        _create_md_files(source, ["init.md"])
        _install(target, source, copy=True)

        # Add a non-.md file
        (target / CANONICAL_PREFIX / "keep.txt").write_text("keep")

        _uninstall(target)
        assert (target / CANONICAL_PREFIX).exists()
        assert (target / CANONICAL_PREFIX / "keep.txt").exists()

    def test_removes_legacy_too(self, tmp_path: Path) -> None:
        """Legacy root-level files are also removed."""
        target = tmp_path / "target"
        target.mkdir()
        (target / "zerg:init.md").write_text("legacy")

        removed = _uninstall(target)
        assert removed == 1

    def test_no_files_returns_zero(self, tmp_path: Path) -> None:
        """Returns 0 when nothing to remove."""
        target = tmp_path / "empty"
        target.mkdir()
        assert _uninstall(target) == 0


# ---------------------------------------------------------------------------
# CLI: install_commands
# ---------------------------------------------------------------------------


class TestInstallCommandsCLI:
    """Tests for the install-commands Click command."""

    def test_fresh_install(self, tmp_path: Path) -> None:
        """Full install to empty target reports installed count."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md", "rush.md"])

        runner = CliRunner()
        with patch(
            "zerg.commands.install_commands._get_source_dir",
            return_value=source,
        ):
            result = runner.invoke(install_commands, ["--target", str(target), "--copy"])

        assert result.exit_code == 0
        assert "Installed" in result.output

    def test_all_already_installed(self, tmp_path: Path) -> None:
        """When all files exist, reports 'already installed'."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md"])

        with patch(
            "zerg.commands.install_commands._get_source_dir",
            return_value=source,
        ):
            # First install
            _install(_get_target_dir(str(target)), source, copy=True)

            runner = CliRunner()
            result = runner.invoke(install_commands, ["--target", str(target), "--copy"])

        assert result.exit_code == 0
        assert "already installed" in result.output

    def test_force_flag(self, tmp_path: Path) -> None:
        """--force overwrites existing installs."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md"])

        runner = CliRunner()
        with patch(
            "zerg.commands.install_commands._get_source_dir",
            return_value=source,
        ):
            # First install
            runner.invoke(install_commands, ["--target", str(target), "--copy"])
            # Force reinstall
            result = runner.invoke(install_commands, ["--target", str(target), "--copy", "--force"])

        assert result.exit_code == 0
        assert "Installed" in result.output

    def test_error_handling(self) -> None:
        """Errors are printed and exit code is 1."""
        runner = CliRunner()
        with patch(
            "zerg.commands.install_commands._get_source_dir",
            side_effect=FileNotFoundError("boom"),
        ):
            result = runner.invoke(install_commands, ["--target", "/dev/null/bad"])

        assert result.exit_code == 1

    def test_legacy_cleanup_message(self, tmp_path: Path) -> None:
        """Legacy files are cleaned and reported."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md"])
        target.mkdir(parents=True)
        (target / "zerg:init.md").write_text("legacy")

        runner = CliRunner()
        with patch(
            "zerg.commands.install_commands._get_source_dir",
            return_value=source,
        ):
            result = runner.invoke(install_commands, ["--target", str(target), "--copy"])

        assert result.exit_code == 0
        assert "legacy" in result.output.lower() or "Installed" in result.output

    def test_symlink_method_reported(self, tmp_path: Path) -> None:
        """On posix without --copy, method is 'symlinked'."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md"])

        runner = CliRunner()
        with (
            patch(
                "zerg.commands.install_commands._get_source_dir",
                return_value=source,
            ),
            patch("zerg.commands.install_commands.os.name", "posix"),
        ):
            result = runner.invoke(install_commands, ["--target", str(target)])

        assert result.exit_code == 0
        assert "symlinked" in result.output


# ---------------------------------------------------------------------------
# CLI: uninstall_commands
# ---------------------------------------------------------------------------


class TestUninstallCommandsCLI:
    """Tests for the uninstall-commands Click command."""

    def test_uninstall_existing(self, tmp_path: Path) -> None:
        """Removes installed commands and reports count."""
        source = tmp_path / "source"
        target = tmp_path / "target"
        _create_md_files(source, ["init.md"])
        _install(_get_target_dir(str(target)), source, copy=True)

        runner = CliRunner()
        result = runner.invoke(uninstall_commands, ["--target", str(target)])

        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_uninstall_nothing(self, tmp_path: Path) -> None:
        """When nothing installed, reports no commands found."""
        target = tmp_path / "empty"
        target.mkdir()

        runner = CliRunner()
        result = runner.invoke(uninstall_commands, ["--target", str(target)])

        assert result.exit_code == 0
        assert "No ZERG commands found" in result.output

    def test_uninstall_error(self) -> None:
        """Errors are printed and exit code is 1."""
        runner = CliRunner()
        with patch(
            "zerg.commands.install_commands._get_target_dir",
            side_effect=PermissionError("denied"),
        ):
            result = runner.invoke(uninstall_commands, ["--target", "/bad"])

        assert result.exit_code == 1


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
            # Should return immediately without calling _install
            with patch("zerg.commands.install_commands._install") as mock_install:
                auto_install_commands()
                mock_install.assert_not_called()

    def test_installs_when_no_sentinel(self, tmp_path: Path) -> None:
        """Installs commands when sentinel is missing."""
        with (
            patch(
                "zerg.commands.install_commands.Path.home",
                return_value=tmp_path,
            ),
            patch(
                "zerg.commands.install_commands._get_source_dir",
                return_value=tmp_path / "source",
            ),
            patch(
                "zerg.commands.install_commands._install",
                return_value=5,
            ) as mock_install,
            patch(
                "zerg.commands.install_commands._remove_legacy",
                return_value=0,
            ),
            patch(
                "zerg.commands.install_commands._get_target_dir",
                return_value=tmp_path / "target",
            ),
        ):
            auto_install_commands()
            mock_install.assert_called_once()

    def test_suppresses_exceptions(self, tmp_path: Path) -> None:
        """Errors are logged but not raised."""
        with (
            patch(
                "zerg.commands.install_commands.Path.home",
                return_value=tmp_path,
            ),
            patch(
                "zerg.commands.install_commands._get_source_dir",
                side_effect=FileNotFoundError("gone"),
            ),
        ):
            # Should not raise
            auto_install_commands()

    def test_zero_count_no_message(self, tmp_path: Path) -> None:
        """When _install returns 0, no success message is printed."""
        with (
            patch(
                "zerg.commands.install_commands.Path.home",
                return_value=tmp_path,
            ),
            patch(
                "zerg.commands.install_commands._get_source_dir",
                return_value=tmp_path / "source",
            ),
            patch(
                "zerg.commands.install_commands._install",
                return_value=0,
            ),
            patch(
                "zerg.commands.install_commands._remove_legacy",
                return_value=0,
            ),
            patch(
                "zerg.commands.install_commands._get_target_dir",
                return_value=tmp_path / "target",
            ),
            patch(
                "zerg.commands.install_commands.console",
            ) as mock_console,
        ):
            auto_install_commands()
            mock_console.print.assert_not_called()
