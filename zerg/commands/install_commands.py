"""ZERG install-commands and uninstall-commands CLI commands."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import click
from rich.console import Console

from zerg.logging import get_logger

console = Console()
logger = get_logger("install-commands")

COMMAND_GLOB = "*.md"
SHORTCUT_PREFIX = "z"
CANONICAL_PREFIX = "zerg"

# Legacy root-level patterns (for cleanup during migration)
LEGACY_PATTERNS = ["zerg:*.md", "z:*.md"]


def _get_source_dir() -> Path:
    """Locate the command .md files shipped with the package.

    Tries ``importlib.resources`` first (works for wheel installs),
    falls back to path traversal (works for editable installs).
    """
    try:
        from importlib.resources import files

        pkg_dir = files("zerg") / "data" / "commands"
        # Resolve to a real path (works for both regular and editable installs)
        resolved = Path(str(pkg_dir))
        if resolved.is_dir():
            return resolved
    except Exception as e:
        logger.debug(f"Install check failed: {e}")

    # Fallback: relative to this file
    fallback = Path(__file__).resolve().parent.parent / "data" / "commands"
    if fallback.is_dir():
        return fallback

    raise FileNotFoundError("Cannot locate ZERG command files. Ensure the package is installed correctly.")


def _get_target_dir(target: str | None) -> Path:
    """Return the target directory, creating it if necessary."""
    d = Path(target).expanduser().resolve() if target else Path.home() / ".claude" / "commands"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _install_to_subdir(
    subdir: Path,
    source_dir: Path,
    *,
    copy: bool = False,
    force: bool = False,
) -> int:
    """Install command files into a subdirectory. Returns count installed."""
    subdir.mkdir(parents=True, exist_ok=True)
    sources = sorted(source_dir.glob(COMMAND_GLOB))
    if not sources:
        raise FileNotFoundError(f"No command files found in {source_dir}")

    use_copy = copy or os.name == "nt"
    installed = 0

    for src in sources:
        dest = subdir / src.name

        # Skip if symlink already points to the right place
        if not force and dest.is_symlink():
            try:
                if dest.resolve() == src.resolve():
                    logger.debug("Already installed: %s", src.name)
                    continue
            except OSError:
                pass  # broken symlink, overwrite it

        # Remove existing file/symlink
        if dest.exists() or dest.is_symlink():
            if not force:
                console.print(f"  [yellow]skip[/yellow] {src.name} (exists, use --force to overwrite)")
                continue
            dest.unlink()

        if use_copy:
            shutil.copy2(src, dest)
        else:
            dest.symlink_to(src.resolve())

        installed += 1

    return installed


def _install_shortcut_redirects(
    shortcut_dir: Path,
    source_dir: Path,
    *,
    force: bool = False,
) -> int:
    """Install z/ shortcut files as thin redirects to zerg/ commands.

    Instead of symlinking to the same source (which Claude Code deduplicates),
    each z/ file contains a redirect instruction that invokes the canonical
    zerg: version. This ensures Claude Code registers both /z:* and /zerg:*
    as distinct skills.

    Returns count installed.
    """
    shortcut_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(source_dir.glob(COMMAND_GLOB))
    if not sources:
        raise FileNotFoundError(f"No command files found in {source_dir}")

    installed = 0
    for src in sources:
        dest = shortcut_dir / src.name
        stem = src.stem  # e.g. "estimate", "debug.core"

        # Build redirect content
        redirect_content = f"Shortcut: run /zerg:{stem} with the same arguments.\n"

        # Skip if already a redirect with correct content
        if not force and dest.exists() and not dest.is_symlink():
            try:
                if dest.read_text() == redirect_content:
                    logger.debug("Shortcut already installed: %s", src.name)
                    continue
            except OSError:
                pass

        # Remove existing file/symlink
        if dest.exists() or dest.is_symlink():
            if not force:
                console.print(f"  [yellow]skip[/yellow] {src.name} (exists, use --force to overwrite)")
                continue
            dest.unlink()

        dest.write_text(redirect_content)
        installed += 1

    return installed


def _install(
    target_dir: Path,
    source_dir: Path,
    *,
    copy: bool = False,
    force: bool = False,
) -> int:
    """Install command files into zerg/ and z/ subdirs. Returns count installed."""
    zerg_dir = target_dir / CANONICAL_PREFIX
    z_dir = target_dir / SHORTCUT_PREFIX

    # Install canonical zerg/ commands (symlinks or copies)
    canonical_count = _install_to_subdir(zerg_dir, source_dir, copy=copy, force=force)

    # Install z/ shortcuts as redirect files (not symlinks, to avoid deduplication)
    shortcut_count = _install_shortcut_redirects(z_dir, source_dir, force=force)

    return canonical_count + shortcut_count


def _remove_legacy(target_dir: Path) -> int:
    """Remove old root-level zerg:*.md and z:*.md files."""
    removed = 0
    for pattern in LEGACY_PATTERNS:
        for path in sorted(target_dir.glob(pattern)):
            path.unlink()
            removed += 1
    return removed


def _uninstall(target_dir: Path) -> int:
    """Remove ZERG command files (subdirs + legacy root-level). Returns count removed."""
    removed = 0

    # Remove subdirectories
    for prefix in [CANONICAL_PREFIX, SHORTCUT_PREFIX]:
        subdir = target_dir / prefix
        if subdir.is_dir():
            for path in sorted(subdir.glob(COMMAND_GLOB)):
                path.unlink()
                removed += 1
            # Remove dir if empty
            try:
                subdir.rmdir()
            except OSError:
                pass  # not empty, leave it

    # Also clean up legacy root-level files
    removed += _remove_legacy(target_dir)

    return removed


@click.command("install-commands")
@click.option(
    "--target",
    "-t",
    default=None,
    help="Target directory (default: ~/.claude/commands/)",
)
@click.option(
    "--copy",
    is_flag=True,
    default=False,
    help="Copy files instead of symlinking (auto-enabled on Windows)",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing files",
)
def install_commands(target: str | None, copy: bool, force: bool) -> None:
    """Install ZERG slash commands globally for Claude Code.

    Creates symlinks (or copies with --copy) from the package's command
    files into ~/.claude/commands/zerg/ and ~/.claude/commands/z/ so they
    are available in every Claude Code session as /zerg:* and /z:*.

    Examples:

        zerg install-commands

        zerg install-commands --force

        zerg install-commands --copy --target /custom/path
    """
    try:
        source_dir = _get_source_dir()
        target_dir = _get_target_dir(target)

        # Clean up legacy root-level files first
        legacy_removed = _remove_legacy(target_dir)
        if legacy_removed > 0:
            console.print(f"  [dim]Cleaned up {legacy_removed} legacy root-level command files[/dim]")

        count = _install(target_dir, source_dir, copy=copy, force=force)
        source_count = len(list(source_dir.glob(COMMAND_GLOB)))
        total = source_count * 2  # zerg/ + z/ shortcuts

        if count == 0:
            console.print(
                f"[green]All {total} ZERG commands already installed[/green] "
                f"({source_count} commands + {source_count} z: shortcuts) in {target_dir}"
            )
        else:
            method = "copied" if (copy or os.name == "nt") else "symlinked"
            console.print(
                f"[green]Installed {count}/{total} ZERG commands[/green] ({method} to {target_dir}/{{zerg,z}}/)"
            )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


@click.command("uninstall-commands")
@click.option(
    "--target",
    "-t",
    default=None,
    help="Target directory (default: ~/.claude/commands/)",
)
def uninstall_commands(target: str | None) -> None:
    """Remove ZERG slash commands from the global Claude Code directory.

    Removes zerg/ and z/ subdirectories and any legacy root-level
    zerg:*.md / z:*.md files.

    Examples:

        zerg uninstall-commands

        zerg uninstall-commands --target /custom/path
    """
    try:
        target_dir = _get_target_dir(target)
        count = _uninstall(target_dir)

        if count == 0:
            console.print("[dim]No ZERG commands found to remove[/dim]")
        else:
            console.print(f"[green]Removed {count} ZERG commands[/green] from {target_dir}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


def auto_install_commands() -> None:
    """Silently install commands if not already present.

    Called from ``zerg init`` to auto-install globally.
    """
    sentinel = Path.home() / ".claude" / "commands" / "zerg" / "init.md"
    if sentinel.exists():
        return

    try:
        source_dir = _get_source_dir()
        target_dir = _get_target_dir(None)

        # Clean up legacy files
        _remove_legacy(target_dir)

        count = _install(target_dir, source_dir)
        if count > 0:
            console.print(f"  [green]\u2713[/green] Installed {count} ZERG slash commands globally")
    except Exception as exc:
        logger.debug("Auto-install commands failed: %s", exc)
