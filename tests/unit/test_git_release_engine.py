"""Tests for zerg.git.release_engine -- automated release workflow."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.git.config import GitConfig, GitReleaseConfig
from zerg.git.release_engine import (
    ChangelogGenerator,
    ReleaseCreator,
    ReleaseEngine,
    SemverCalculator,
    VersionFileUpdater,
)
from zerg.git.types import CommitInfo, CommitType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _commit(
    sha: str = "abc1234567890",
    message: str = "fix: patch bug",
    author: str = "dev",
    date: str = "2026-01-15T10:00:00+00:00",
    commit_type: CommitType | None = None,
) -> CommitInfo:
    """Create a CommitInfo with sensible defaults."""
    return CommitInfo(
        sha=sha,
        message=message,
        author=author,
        date=date,
        commit_type=commit_type,
    )


def _make_runner(
    tag_list: str = "",
    log_output: str = "",
    tag_exists: bool = False,
) -> MagicMock:
    """Build a mock GitRunner with controlled output."""
    runner = MagicMock()
    runner.repo_path = Path("/fake/repo")

    def _run_side_effect(*args, **kwargs):
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 0
        joined = " ".join(args)

        if "tag" in joined and "--list" in joined and "--sort" in joined:
            result.stdout = tag_list
        elif "tag" in joined and "--list" in joined:
            result.stdout = tag_list if tag_exists else ""
        elif "log" in joined:
            result.stdout = log_output
        elif "tag" in joined and "-a" in joined:
            result.stdout = ""
        elif "push" in joined:
            result.stdout = ""
        elif "add" in joined:
            result.stdout = ""
        elif "commit" in joined:
            result.stdout = ""
        else:
            result.stdout = ""
        return result

    runner._run.side_effect = _run_side_effect
    return runner


# ---------------------------------------------------------------------------
# TestSemverCalculator
# ---------------------------------------------------------------------------


class TestSemverCalculator:
    """Tests for SemverCalculator."""

    def setup_method(self) -> None:
        self.config = GitReleaseConfig()
        self.calc = SemverCalculator(self.config)

    def test_get_latest_version_with_tags(self) -> None:
        """Should return the latest valid semver tag."""
        runner = _make_runner(tag_list="v2.1.0\nv2.0.0\nv1.5.3\n")
        result = self.calc.get_latest_version(runner)
        assert result == "2.1.0"

    def test_get_latest_version_no_tags(self) -> None:
        """Should return 0.0.0 when no tags exist."""
        runner = _make_runner(tag_list="")
        result = self.calc.get_latest_version(runner)
        assert result == "0.0.0"

    def test_get_latest_version_skips_invalid_tags(self) -> None:
        """Should skip non-semver tags and find the first valid one."""
        runner = _make_runner(tag_list="vinvalid\nv1.0.0\n")
        result = self.calc.get_latest_version(runner)
        assert result == "1.0.0"

    def test_calculate_bump_feat_is_minor(self) -> None:
        """feat commits should result in a minor bump."""
        commits = [_commit(message="feat: add login")]
        assert self.calc.calculate_bump(commits) == "minor"

    def test_calculate_bump_fix_is_patch(self) -> None:
        """fix commits should result in a patch bump."""
        commits = [_commit(message="fix: resolve crash")]
        assert self.calc.calculate_bump(commits) == "patch"

    def test_calculate_bump_breaking_is_major(self) -> None:
        """BREAKING CHANGE in body should result in a major bump."""
        commits = [_commit(message="feat: redesign API\n\nBREAKING CHANGE: removed v1")]
        assert self.calc.calculate_bump(commits) == "major"

    def test_calculate_bump_breaking_bang_is_major(self) -> None:
        """! after type should result in a major bump."""
        commits = [_commit(message="feat!: new API")]
        assert self.calc.calculate_bump(commits) == "major"

    def test_calculate_bump_mixed_takes_highest(self) -> None:
        """Mixed commits should use the highest bump level."""
        commits = [
            _commit(message="fix: bug"),
            _commit(message="feat: feature"),
            _commit(message="chore: cleanup"),
        ]
        assert self.calc.calculate_bump(commits) == "minor"

    def test_next_version_basic(self) -> None:
        """Should correctly bump major, minor, and patch."""
        assert self.calc.next_version("1.2.3", "major") == "2.0.0"
        assert self.calc.next_version("1.2.3", "minor") == "1.3.0"
        assert self.calc.next_version("1.2.3", "patch") == "1.2.4"

    def test_next_version_with_pre_release(self) -> None:
        """Should append pre-release identifier."""
        result = self.calc.next_version("1.2.3", "major", pre="alpha")
        assert result == "2.0.0-alpha.1"

    def test_next_version_invalid_version_raises(self) -> None:
        """Should raise ValueError for invalid current version."""
        with pytest.raises(ValueError, match="Invalid semver"):
            self.calc.next_version("not.a.version.string", "patch")

    def test_next_version_invalid_bump_raises(self) -> None:
        """Should raise ValueError for invalid bump type."""
        with pytest.raises(ValueError, match="Invalid bump type"):
            self.calc.next_version("1.0.0", "huge")


# ---------------------------------------------------------------------------
# TestChangelogGenerator
# ---------------------------------------------------------------------------


class TestChangelogGenerator:
    """Tests for ChangelogGenerator."""

    def setup_method(self) -> None:
        self.gen = ChangelogGenerator()

    def test_generate_with_mixed_commits(self) -> None:
        """Should group commits into proper sections."""
        commits = [
            _commit(sha="aaa1111", message="feat: add auth"),
            _commit(sha="bbb2222", message="fix: login crash"),
            _commit(sha="ccc3333", message="refactor: cleanup models"),
            _commit(sha="ddd4444", message="perf: optimize query"),
        ]
        result = self.gen.generate(commits, "1.1.0", "2026-02-01")

        assert "## [1.1.0] - 2026-02-01" in result
        assert "### Added" in result
        assert "add auth (aaa1111)" in result
        assert "### Fixed" in result
        assert "login crash (bbb2222)" in result
        assert "### Changed" in result
        assert "cleanup models (ccc3333)" in result
        assert "### Performance" in result
        assert "optimize query (ddd4444)" in result

    def test_generate_non_conventional_goes_to_other(self) -> None:
        """Non-conventional commits should go to Other section."""
        commits = [_commit(sha="eee5555", message="random update")]
        result = self.gen.generate(commits, "1.0.1", "2026-02-01")
        assert "### Other" in result

    def test_update_changelog_inserts_after_unreleased(self, tmp_path: Path) -> None:
        """Should insert new entry after ## [Unreleased] section."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n",
            encoding="utf-8",
        )
        new_entry = "## [1.1.0] - 2026-02-01\n\n### Added\n- feature (abc1234)"

        self.gen.update_changelog(changelog, new_entry)

        content = changelog.read_text(encoding="utf-8")
        assert "## [1.1.0] - 2026-02-01" in content
        # Unreleased should still be present
        assert "## [Unreleased]" in content
        # New entry should come before old release
        unreleased_pos = content.index("[Unreleased]")
        new_entry_pos = content.index("[1.1.0]")
        old_entry_pos = content.index("[1.0.0]")
        assert unreleased_pos < new_entry_pos < old_entry_pos

    def test_update_changelog_creates_new_file(self, tmp_path: Path) -> None:
        """Should create a new changelog if none exists."""
        changelog = tmp_path / "CHANGELOG.md"
        new_entry = "## [0.1.0] - 2026-02-01\n\n### Added\n- initial (abc1234)"

        self.gen.update_changelog(changelog, new_entry)

        assert changelog.exists()
        content = changelog.read_text(encoding="utf-8")
        assert "# Changelog" in content
        assert "## [Unreleased]" in content
        assert "## [0.1.0] - 2026-02-01" in content


# ---------------------------------------------------------------------------
# TestVersionFileUpdater
# ---------------------------------------------------------------------------


class TestVersionFileUpdater:
    """Tests for VersionFileUpdater."""

    def setup_method(self) -> None:
        self.updater = VersionFileUpdater()

    def test_detect_pyproject_toml(self, tmp_path: Path) -> None:
        """Should detect pyproject.toml in the repo root."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
        runner = MagicMock()
        runner.repo_path = tmp_path

        files = self.updater.detect_version_files(runner)
        assert len(files) == 1
        assert files[0]["type"] == "pyproject.toml"

    def test_detect_package_json(self, tmp_path: Path) -> None:
        """Should detect package.json in the repo root."""
        (tmp_path / "package.json").write_text('{\n  "version": "2.0.0"\n}\n', encoding="utf-8")
        runner = MagicMock()
        runner.repo_path = tmp_path

        files = self.updater.detect_version_files(runner)
        assert len(files) == 1
        assert files[0]["type"] == "package.json"

    def test_detect_multiple_files(self, tmp_path: Path) -> None:
        """Should detect multiple version files."""
        (tmp_path / "pyproject.toml").write_text('version = "1.0.0"\n', encoding="utf-8")
        (tmp_path / "package.json").write_text('{"version": "1.0.0"}\n', encoding="utf-8")
        runner = MagicMock()
        runner.repo_path = tmp_path

        files = self.updater.detect_version_files(runner)
        assert len(files) == 2

    def test_update_pyproject_version(self, tmp_path: Path) -> None:
        """Should update version in pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "myapp"\nversion = "1.0.0"\n', encoding="utf-8")

        result = self.updater.update_version(pyproject, "2.0.0")
        assert result is True

        content = pyproject.read_text(encoding="utf-8")
        assert 'version = "2.0.0"' in content

    def test_update_package_json_version(self, tmp_path: Path) -> None:
        """Should update version in package.json."""
        pkg = tmp_path / "package.json"
        pkg.write_text(
            '{\n  "name": "myapp",\n  "version": "1.0.0"\n}\n',
            encoding="utf-8",
        )

        result = self.updater.update_version(pkg, "3.1.0")
        assert result is True

        content = pkg.read_text(encoding="utf-8")
        assert '"version": "3.1.0"' in content

    def test_update_nonexistent_file_returns_false(self, tmp_path: Path) -> None:
        """Should return False for a file that does not exist."""
        result = self.updater.update_version(tmp_path / "missing.toml", "1.0.0")
        assert result is False

    def test_update_rejects_invalid_version(self, tmp_path: Path) -> None:
        """Should reject invalid version strings."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('version = "1.0.0"\n', encoding="utf-8")

        result = self.updater.update_version(pyproject, "not-semver")
        assert result is False


# ---------------------------------------------------------------------------
# TestReleaseCreator
# ---------------------------------------------------------------------------


class TestReleaseCreator:
    """Tests for ReleaseCreator."""

    def setup_method(self) -> None:
        self.creator = ReleaseCreator()
        self.config = GitReleaseConfig()

    def test_create_with_gh(self) -> None:
        """Should create tag, push, and gh release."""
        runner = _make_runner()

        with patch("shutil.which", return_value="/usr/bin/gh"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = self.creator.create(runner, "1.0.0", "release notes", self.config)

        assert result["tag"] == "v1.0.0"
        assert result["pushed"] is True
        assert result["gh_release"] is True

    def test_create_dry_run(self) -> None:
        """Should not execute any git commands in dry_run mode."""
        runner = _make_runner()

        result = self.creator.create(runner, "2.0.0", "notes", self.config, dry_run=True)

        assert result["tag"] == "v2.0.0"
        assert result["pushed"] is False
        assert result["gh_release"] is False
        # Runner should not have been called for tag/push
        runner._run.assert_not_called()

    def test_create_gh_not_available(self) -> None:
        """Should gracefully skip GitHub release when gh is not found."""
        runner = _make_runner()

        with patch("shutil.which", return_value=None):
            result = self.creator.create(runner, "1.0.0", "notes", self.config)

        assert result["tag"] == "v1.0.0"
        assert result["gh_release"] is False

    def test_create_push_failure_continues(self) -> None:
        """Should handle push failure gracefully."""
        runner = MagicMock()
        runner.repo_path = Path("/fake/repo")

        call_count = 0

        def _run_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            joined = " ".join(args)
            if "push" in joined:
                raise Exception("push failed")
            result = MagicMock(spec=subprocess.CompletedProcess)
            result.stdout = ""
            result.returncode = 0
            return result

        runner._run.side_effect = _run_side_effect

        with patch("shutil.which", return_value=None):
            result = self.creator.create(runner, "1.0.0", "notes", self.config)

        assert result["pushed"] is False


# ---------------------------------------------------------------------------
# TestReleaseEngine
# ---------------------------------------------------------------------------


class TestReleaseEngine:
    """Tests for ReleaseEngine orchestration."""

    def _build_engine(
        self,
        tag_list: str = "",
        log_output: str = "",
        tag_exists: bool = False,
    ) -> tuple[ReleaseEngine, MagicMock]:
        runner = _make_runner(
            tag_list=tag_list,
            log_output=log_output,
            tag_exists=tag_exists,
        )
        config = GitConfig()
        engine = ReleaseEngine(runner, config)
        return engine, runner

    def test_full_run(self, tmp_path: Path) -> None:
        """Should execute complete release workflow."""
        log_output = (
            "abc1234567890abcdef1234567890abcdef123456\nfeat: add new feature\nDeveloper\n2026-01-15T10:00:00+00:00\n"
        )
        runner = MagicMock()
        runner.repo_path = tmp_path

        # Create a pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('version = "0.0.0"\n', encoding="utf-8")

        call_count = 0

        def _run_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock(spec=subprocess.CompletedProcess)
            result.returncode = 0
            joined = " ".join(args)

            if "tag" in joined and "--sort" in joined:
                result.stdout = ""
            elif "tag" in joined and "--list" in joined:
                result.stdout = ""
            elif "log" in joined:
                result.stdout = log_output
            else:
                result.stdout = ""
            return result

        runner._run.side_effect = _run_side_effect

        config = GitConfig()
        engine = ReleaseEngine(runner, config)

        with patch("shutil.which", return_value=None):
            exit_code = engine.run()

        assert exit_code == 0
        # Changelog should have been created
        changelog = tmp_path / "CHANGELOG.md"
        assert changelog.exists()
        content = changelog.read_text(encoding="utf-8")
        assert "add new feature" in content

    def test_run_with_override_bump(self) -> None:
        """Should use the override bump instead of calculating from commits."""
        log_output = "abc1234567890\nfix: minor fix\nDeveloper\n2026-01-15T10:00:00+00:00\n"
        engine, runner = self._build_engine(log_output=log_output)

        with patch("shutil.which", return_value=None):
            exit_code = engine.run(bump="major", dry_run=True)

        assert exit_code == 0

    def test_run_dry_run(self) -> None:
        """Should not modify anything in dry_run mode."""
        log_output = "abc1234567890\nfeat: new stuff\nDeveloper\n2026-01-15T10:00:00+00:00\n"
        engine, runner = self._build_engine(log_output=log_output)

        exit_code = engine.run(dry_run=True)

        assert exit_code == 0
        # In dry_run, no commit or tag commands should happen
        for call in runner._run.call_args_list:
            args_str = " ".join(call[0])
            assert "commit" not in args_str

    def test_run_no_commits_returns_failure(self) -> None:
        """Should return 1 when there are no new commits."""
        engine, _ = self._build_engine(log_output="")
        exit_code = engine.run()
        assert exit_code == 1
