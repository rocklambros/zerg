"""Automated release workflow with semver and changelog generation.

Provides version calculation from conventional commits, changelog generation
in Keep a Changelog format, version file updates, and GitHub release creation.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from zerg.git.config import GitConfig, GitReleaseConfig
from zerg.git.types import CommitInfo, CommitType
from zerg.logging import get_logger

if TYPE_CHECKING:
    from zerg.git.base import GitRunner

logger = get_logger("git.release_engine")

# Strict semver pattern: major.minor.patch with optional pre-release
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

# Conventional commit message pattern
_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>\w+)(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?:\s*(?P<description>.+)",
    re.MULTILINE,
)

# Commit types that map to minor bumps
_MINOR_TYPES = frozenset({CommitType.FEAT})

# Commit types that map to patch bumps
_PATCH_TYPES = frozenset(
    {
        CommitType.FIX,
        CommitType.PERF,
        CommitType.REFACTOR,
    }
)

# Map conventional commit type strings to changelog sections
_TYPE_TO_SECTION: dict[str, str] = {
    "feat": "Added",
    "fix": "Fixed",
    "refactor": "Changed",
    "perf": "Performance",
    "revert": "Removed",
}


class SemverCalculator:
    """Calculates next version from conventional commits."""

    def __init__(self, config: GitReleaseConfig) -> None:
        self.config = config

    def get_latest_version(self, runner: GitRunner) -> str:
        """Get the latest version tag matching the configured prefix.

        Args:
            runner: GitRunner instance for tag queries.

        Returns:
            Version string without prefix (e.g., "1.2.3"), or "0.0.0" if none found.
        """
        prefix = self.config.tag_prefix
        try:
            result = runner._run(
                "tag",
                "--list",
                f"{prefix}*",
                "--sort=-v:refname",
                check=False,
            )
            tags = [line.strip() for line in (result.stdout or "").strip().splitlines() if line.strip()]
        except Exception:
            logger.debug("Failed to list tags, defaulting to 0.0.0")
            return "0.0.0"

        for tag in tags:
            version = tag.removeprefix(prefix)
            if _SEMVER_RE.match(version):
                return version

        return "0.0.0"

    def calculate_bump(self, commits: list[CommitInfo]) -> str:
        """Determine the bump level from a list of commits.

        Rules:
        - BREAKING CHANGE in body or ! after type -> "major"
        - feat -> "minor"
        - fix, perf, refactor -> "patch"
        - Everything else -> "patch"

        Args:
            commits: List of CommitInfo objects to analyze.

        Returns:
            One of "major", "minor", or "patch".
        """
        has_minor = False

        for commit in commits:
            msg = commit.message

            # Check for breaking change indicators
            if self._is_breaking(msg):
                return "major"

            # Parse conventional commit type
            match = _CONVENTIONAL_RE.match(msg)
            if match:
                commit_type_str = match.group("type").lower()
                try:
                    ct = CommitType(commit_type_str)
                except ValueError:
                    continue

                if ct in _MINOR_TYPES:
                    has_minor = True
                # patch types don't need tracking -- patch is the default

        return "minor" if has_minor else "patch"

    def next_version(self, current: str, bump: str, pre: str | None = None) -> str:
        """Calculate the next version string.

        Args:
            current: Current version (e.g., "1.2.3").
            bump: One of "major", "minor", "patch".
            pre: Optional pre-release identifier (e.g., "alpha", "beta", "rc").

        Returns:
            Next version string (e.g., "2.0.0" or "2.0.0-alpha.1").

        Raises:
            ValueError: If current version or bump type is invalid.
        """
        match = _SEMVER_RE.match(current)
        if not match:
            raise ValueError(f"Invalid semver: {current}")

        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))

        if bump == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump == "minor":
            minor += 1
            patch = 0
        elif bump == "patch":
            patch += 1
        else:
            raise ValueError(f"Invalid bump type: {bump}")

        version = f"{major}.{minor}.{patch}"
        if pre:
            version = f"{version}-{pre}.1"

        return version

    @staticmethod
    def _is_breaking(message: str) -> bool:
        """Check if a commit message indicates a breaking change."""
        # Check for ! after type
        match = _CONVENTIONAL_RE.match(message)
        if match and match.group("breaking"):
            return True

        # Check for BREAKING CHANGE in body
        if "BREAKING CHANGE" in message or "BREAKING-CHANGE" in message:
            return True

        return False


class ChangelogGenerator:
    """Generates changelog entries in Keep a Changelog format."""

    def generate(self, commits: list[CommitInfo], version: str, date: str) -> str:
        """Generate a changelog entry for a release.

        Groups commits by type into sections: Added, Changed, Fixed,
        Removed, Performance, Other.

        Args:
            commits: List of commits to include.
            version: Version string for the header.
            date: Date string for the header (YYYY-MM-DD).

        Returns:
            Formatted changelog entry string.
        """
        sections: dict[str, list[str]] = {}

        for commit in commits:
            section = self._classify_commit(commit)
            short_sha = commit.sha[:7] if len(commit.sha) >= 7 else commit.sha
            # Extract description from conventional commit or use full message
            description = self._extract_description(commit.message)
            entry = f"- {description} ({short_sha})"
            sections.setdefault(section, []).append(entry)

        # Build output in standard order
        section_order = ["Added", "Changed", "Fixed", "Removed", "Performance", "Other"]
        lines = [f"## [{version}] - {date}"]

        for section_name in section_order:
            if section_name in sections:
                lines.append("")
                lines.append(f"### {section_name}")
                for entry in sections[section_name]:
                    lines.append(entry)

        lines.append("")
        return "\n".join(lines)

    def update_changelog(self, changelog_path: Path, new_entry: str) -> None:
        """Insert a new entry into an existing changelog file.

        Inserts after the ``## [Unreleased]`` line. If no Unreleased section
        exists, inserts at the top of the file (after the title if present).

        Args:
            changelog_path: Path to the CHANGELOG.md file.
            new_entry: The formatted changelog entry to insert.
        """
        resolved = changelog_path.resolve()

        if not resolved.exists():
            # Create new changelog with standard header
            content = (
                "# Changelog\n\n"
                "All notable changes to this project will be documented in this file.\n\n"
                "## [Unreleased]\n\n"
                f"{new_entry}\n"
            )
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return

        existing = resolved.read_text(encoding="utf-8")
        lines = existing.splitlines(keepends=True)

        # Find ## [Unreleased] line
        unreleased_idx = None
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("## [unreleased]"):
                unreleased_idx = i
                break

        if unreleased_idx is not None:
            # Insert after Unreleased header (and any blank line after it)
            insert_at = unreleased_idx + 1
            while insert_at < len(lines) and lines[insert_at].strip() == "":
                insert_at += 1
            insertion = new_entry + "\n\n"
            lines.insert(insert_at, insertion)
        else:
            # Insert at top, after title line if present
            insert_at = 0
            if lines and lines[0].startswith("# "):
                insert_at = 1
                # Skip blank lines after title
                while insert_at < len(lines) and lines[insert_at].strip() == "":
                    insert_at += 1
            insertion = "\n" + new_entry + "\n\n"
            lines.insert(insert_at, insertion)

        resolved.write_text("".join(lines), encoding="utf-8")

    @staticmethod
    def _classify_commit(commit: CommitInfo) -> str:
        """Classify a commit into a changelog section."""
        match = _CONVENTIONAL_RE.match(commit.message)
        if match:
            type_str = match.group("type").lower()
            return _TYPE_TO_SECTION.get(type_str, "Other")

        # Fallback: use commit_type field if available
        if commit.commit_type:
            type_str = commit.commit_type.value
            return _TYPE_TO_SECTION.get(type_str, "Other")

        return "Other"

    @staticmethod
    def _extract_description(message: str) -> str:
        """Extract the description from a conventional commit message."""
        match = _CONVENTIONAL_RE.match(message)
        if match:
            return match.group("description").strip()
        # Return first line for non-conventional messages
        return message.split("\n", 1)[0].strip()


class VersionFileUpdater:
    """Detects and updates version strings in project files."""

    # Patterns for version strings in various file formats
    _PATTERNS: dict[str, re.Pattern[str]] = {
        "pyproject.toml": re.compile(r'^(version\s*=\s*")([^"]+)(")', re.MULTILINE),
        "package.json": re.compile(r'^(\s*"version"\s*:\s*")([^"]+)(")', re.MULTILINE),
        "Cargo.toml": re.compile(r'^(version\s*=\s*")([^"]+)(")', re.MULTILINE),
    }

    def detect_version_files(self, runner: GitRunner) -> list[dict[str, str]]:
        """Detect files containing version information.

        Checks for pyproject.toml, package.json, and Cargo.toml in the
        repository root.

        Args:
            runner: GitRunner for repository path access.

        Returns:
            List of dicts with 'path' and 'type' keys.
        """
        results: list[dict[str, str]] = []
        root = runner.repo_path

        for filename in ("pyproject.toml", "package.json", "Cargo.toml"):
            filepath = (root / filename).resolve()
            if not filepath.is_relative_to(root):
                continue
            if filepath.exists():
                results.append({"path": str(filepath), "type": filename})

        return results

    def update_version(self, file_path: Path, new_version: str) -> bool:
        """Update the version string in a project file.

        Args:
            file_path: Path to the version file.
            new_version: New version string to set.

        Returns:
            True if the version was updated, False if not found or unchanged.
        """
        resolved = file_path.resolve()
        if not resolved.exists():
            return False

        filename = resolved.name
        pattern = self._PATTERNS.get(filename)
        if pattern is None:
            logger.warning("No version pattern for file: %s", filename)
            return False

        # Validate version string
        if not _SEMVER_RE.match(new_version):
            logger.warning("Invalid version string: %s", new_version)
            return False

        content = resolved.read_text(encoding="utf-8")
        new_content, count = pattern.subn(rf"\g<1>{new_version}\g<3>", content)

        if count == 0:
            return False

        resolved.write_text(new_content, encoding="utf-8")
        return True


class ReleaseCreator:
    """Creates git tags and GitHub releases."""

    def create(
        self,
        runner: GitRunner,
        version: str,
        changelog_entry: str,
        config: GitReleaseConfig,
        dry_run: bool = False,
    ) -> dict[str, str | bool]:
        """Create a release with tag and optional GitHub release.

        Args:
            runner: GitRunner for git operations.
            version: Version string (without prefix).
            changelog_entry: Changelog content for the release notes.
            config: Release configuration.
            dry_run: If True, only log what would happen.

        Returns:
            Dict with 'tag', 'pushed', 'gh_release' status.
        """
        tag_name = f"{config.tag_prefix}{version}"
        result: dict[str, str | bool] = {
            "tag": tag_name,
            "pushed": False,
            "gh_release": False,
        }

        if dry_run:
            logger.info("[DRY RUN] Would create tag: %s", tag_name)
            logger.info("[DRY RUN] Would push tag: %s", tag_name)
            if config.github_release:
                logger.info("[DRY RUN] Would create GitHub release: %s", tag_name)
            return result

        # Create annotated tag
        runner._run(
            "tag",
            "-a",
            tag_name,
            "-m",
            f"Release {tag_name}",
        )
        logger.info("Created tag: %s", tag_name)

        # Push tag
        try:
            runner._run("push", "origin", tag_name)
            result["pushed"] = True
            logger.info("Pushed tag: %s", tag_name)
        except Exception as exc:
            logger.warning("Failed to push tag: %s", exc)

        # Create GitHub release if configured and gh is available
        if config.github_release:
            result["gh_release"] = self._create_gh_release(tag_name, changelog_entry)

        return result

    @staticmethod
    def _create_gh_release(tag_name: str, notes: str) -> bool:
        """Create a GitHub release using the gh CLI.

        Args:
            tag_name: Tag name for the release.
            notes: Release notes content.

        Returns:
            True if the release was created successfully.
        """
        if not shutil.which("gh"):
            logger.info("gh CLI not found, skipping GitHub release")
            return False

        try:
            subprocess.run(
                [
                    "gh",
                    "release",
                    "create",
                    tag_name,
                    "--title",
                    tag_name,
                    "--notes",
                    notes,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            logger.info("Created GitHub release: %s", tag_name)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            logger.warning("Failed to create GitHub release: %s", exc)
            return False


class ReleaseEngine:
    """Main entry point for the automated release workflow.

    Orchestrates version calculation, changelog generation, file updates,
    tagging, and GitHub release creation.
    """

    def __init__(self, runner: GitRunner, config: GitConfig) -> None:
        self.runner = runner
        self.config = config
        self._semver = SemverCalculator(config.release)
        self._changelog = ChangelogGenerator()
        self._version_files = VersionFileUpdater()
        self._release = ReleaseCreator()

    def run(
        self,
        bump: str | None = None,
        pre: str | None = None,
        dry_run: bool = False,
    ) -> int:
        """Execute the full release workflow.

        Flow: get latest version -> get commits since tag -> calculate bump
        (or use override) -> generate changelog -> update files -> commit ->
        tag -> push -> gh release.

        Args:
            bump: Override bump type ("major", "minor", "patch").
                  If None, calculated from commits.
            pre: Optional pre-release identifier ("alpha", "beta", "rc").
            dry_run: If True, don't make any changes.

        Returns:
            0 for success, 1 for failure.
        """
        try:
            return self._execute(bump=bump, pre=pre, dry_run=dry_run)
        except Exception as exc:
            logger.error("Release failed: %s", exc)
            return 1

    def _execute(
        self,
        bump: str | None = None,
        pre: str | None = None,
        dry_run: bool = False,
    ) -> int:
        """Internal release execution."""
        release_cfg = self.config.release

        # Step 1: Get latest version
        current = self._semver.get_latest_version(self.runner)
        logger.info("Current version: %s", current)

        # Step 2: Get commits since last tag
        tag_name = f"{release_cfg.tag_prefix}{current}"
        commits = self._get_commits_since(tag_name)
        if not commits:
            logger.info("No commits since %s, nothing to release", tag_name)
            return 1

        # Step 3: Calculate or use override bump
        effective_bump = bump or self._semver.calculate_bump(commits)
        logger.info("Bump type: %s", effective_bump)

        # Step 4: Calculate next version
        new_version = self._semver.next_version(current, effective_bump, pre)
        logger.info("New version: %s", new_version)

        # Step 5: Generate changelog entry
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        changelog_entry = self._changelog.generate(commits, new_version, today)

        if dry_run:
            logger.info("[DRY RUN] Changelog entry:\n%s", changelog_entry)
            logger.info("[DRY RUN] Would update version files to %s", new_version)
            self._release.create(self.runner, new_version, changelog_entry, release_cfg, dry_run=True)
            return 0

        # Step 6: Update changelog file
        changelog_path = Path(self.runner.repo_path) / release_cfg.changelog_file
        self._changelog.update_changelog(changelog_path, changelog_entry)

        # Step 7: Update version files
        version_files = self._version_files.detect_version_files(self.runner)
        for vf in version_files:
            self._version_files.update_version(Path(vf["path"]), new_version)

        # Step 8: Commit changes
        self.runner._run("add", "-A")
        self.runner._run(
            "commit",
            "-m",
            f"chore(release): {release_cfg.tag_prefix}{new_version}",
        )

        # Step 9: Tag and release
        self._release.create(self.runner, new_version, changelog_entry, release_cfg)

        logger.info("Released %s%s", release_cfg.tag_prefix, new_version)
        return 0

    def _get_commits_since(self, tag: str) -> list[CommitInfo]:
        """Get commits since the given tag.

        Args:
            tag: Tag name to get commits since.

        Returns:
            List of CommitInfo objects.
        """
        # Check if tag exists
        tag_check = self.runner._run(
            "tag",
            "--list",
            tag,
            check=False,
        )
        tag_exists = bool((tag_check.stdout or "").strip())

        if tag_exists:
            log_range = f"{tag}..HEAD"
        else:
            log_range = "HEAD"

        try:
            result = self.runner._run(
                "log",
                log_range,
                "--format=%H%n%s%n%an%n%aI",
                "--no-merges",
                check=False,
            )
        except Exception:
            return []

        output = (result.stdout or "").strip()
        if not output:
            return []

        lines = output.splitlines()
        commits: list[CommitInfo] = []

        # Each commit is 4 lines: sha, subject, author, date
        i = 0
        while i + 3 < len(lines):
            sha = lines[i].strip()
            message = lines[i + 1].strip()
            author = lines[i + 2].strip()
            date = lines[i + 3].strip()
            i += 4

            # Skip empty entries
            if not sha:
                continue

            # Detect commit type
            commit_type = self._parse_commit_type(message)
            commits.append(
                CommitInfo(
                    sha=sha,
                    message=message,
                    author=author,
                    date=date,
                    commit_type=commit_type,
                )
            )

        return commits

    @staticmethod
    def _parse_commit_type(message: str) -> CommitType | None:
        """Parse conventional commit type from message."""
        match = _CONVENTIONAL_RE.match(message)
        if match:
            type_str = match.group("type").lower()
            try:
                return CommitType(type_str)
            except ValueError:
                return None
        return None
