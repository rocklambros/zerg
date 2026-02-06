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
from zerg.git.types import CommitInfo


def _commit(
    sha="abc1234567890", message="fix: patch bug", author="dev", date="2026-01-15T10:00:00+00:00", commit_type=None
) -> CommitInfo:
    return CommitInfo(sha=sha, message=message, author=author, date=date, commit_type=commit_type)


def _make_runner(tag_list="", log_output="") -> MagicMock:
    runner = MagicMock()
    runner.repo_path = Path("/fake/repo")

    def _run_side_effect(*args, **kwargs):
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 0
        joined = " ".join(args)
        if "tag" in joined and "--sort" in joined:
            result.stdout = tag_list
        elif "tag" in joined and "--list" in joined:
            result.stdout = tag_list
        elif "log" in joined:
            result.stdout = log_output
        else:
            result.stdout = ""
        return result

    runner._run.side_effect = _run_side_effect
    return runner


class TestSemverCalculator:
    def setup_method(self):
        self.calc = SemverCalculator(GitReleaseConfig())

    def test_get_latest_version(self) -> None:
        assert self.calc.get_latest_version(_make_runner(tag_list="v2.1.0\nv1.0.0\n")) == "2.1.0"
        assert self.calc.get_latest_version(_make_runner(tag_list="")) == "0.0.0"

    def test_calculate_bump(self) -> None:
        assert self.calc.calculate_bump([_commit(message="feat: add login")]) == "minor"
        assert self.calc.calculate_bump([_commit(message="fix: crash")]) == "patch"
        assert self.calc.calculate_bump([_commit(message="feat!: new API")]) == "major"

    def test_next_version(self) -> None:
        assert self.calc.next_version("1.2.3", "major") == "2.0.0"
        assert self.calc.next_version("1.2.3", "minor") == "1.3.0"
        assert self.calc.next_version("1.2.3", "patch") == "1.2.4"

    def test_next_version_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid semver"):
            self.calc.next_version("bad", "patch")
        with pytest.raises(ValueError, match="Invalid bump type"):
            self.calc.next_version("1.0.0", "huge")


class TestChangelogGenerator:
    def test_generate_with_mixed_commits(self) -> None:
        commits = [
            _commit(sha="aaa", message="feat: add auth"),
            _commit(sha="bbb", message="fix: login crash"),
        ]
        result = ChangelogGenerator().generate(commits, "1.1.0", "2026-02-01")
        assert "## [1.1.0]" in result and "### Added" in result and "### Fixed" in result

    def test_update_changelog(self, tmp_path: Path) -> None:
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n")
        ChangelogGenerator().update_changelog(changelog, "## [1.1.0] - 2026-02-01\n\n### Added\n- feat (abc)")
        content = changelog.read_text()
        assert content.index("[Unreleased]") < content.index("[1.1.0]") < content.index("[1.0.0]")


class TestVersionFileUpdater:
    def test_detect_and_update(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\nversion = "1.0.0"\n')
        runner = MagicMock()
        runner.repo_path = tmp_path
        updater = VersionFileUpdater()
        files = updater.detect_version_files(runner)
        assert len(files) == 1 and files[0]["type"] == "pyproject.toml"
        assert updater.update_version(tmp_path / "pyproject.toml", "2.0.0") is True
        assert 'version = "2.0.0"' in (tmp_path / "pyproject.toml").read_text()

    def test_update_rejects_invalid(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('version = "1.0.0"\n')
        assert VersionFileUpdater().update_version(pyproject, "not-semver") is False
        assert VersionFileUpdater().update_version(tmp_path / "missing.toml", "1.0.0") is False


class TestReleaseCreator:
    def test_create_dry_run(self) -> None:
        result = ReleaseCreator().create(_make_runner(), "2.0.0", "notes", GitReleaseConfig(), dry_run=True)
        assert result["tag"] == "v2.0.0" and result["pushed"] is False

    def test_create_gh_not_available(self) -> None:
        with patch("shutil.which", return_value=None):
            result = ReleaseCreator().create(_make_runner(), "1.0.0", "notes", GitReleaseConfig())
        assert result["gh_release"] is False


class TestReleaseEngine:
    def test_run_no_commits(self) -> None:
        runner = _make_runner(log_output="")
        assert ReleaseEngine(runner, GitConfig()).run() == 1

    def test_run_dry_run(self) -> None:
        log_output = "abc1234567890\nfeat: new stuff\nDev\n2026-01-15T10:00:00+00:00\n"
        runner = _make_runner(log_output=log_output)
        assert ReleaseEngine(runner, GitConfig()).run(dry_run=True) == 0
