"""Tests for zerg.commands._utils — shared command utilities."""

import json
import time
from pathlib import Path

import pytest


class TestDetectFeature:
    """Tests for detect_feature() priority order."""

    def test_current_feature_takes_priority_over_state_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When both .gsd/.current-feature and .zerg/state/*.json exist,
        .current-feature wins because it reflects explicit user intent."""
        monkeypatch.chdir(tmp_path)

        # Create stale state file
        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "stale-feature.json").write_text(json.dumps({"state": "STOPPING"}))

        # Create .current-feature with different name
        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True)
        (gsd_dir / ".current-feature").write_text("active-feature")

        from zerg.commands._utils import detect_feature

        result = detect_feature()
        assert result == "active-feature"

    def test_falls_back_to_state_json_when_no_current_feature(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When .gsd/.current-feature doesn't exist, use state JSON."""
        monkeypatch.chdir(tmp_path)

        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "my-feature.json").write_text(json.dumps({"state": "RUNNING"}))

        from zerg.commands._utils import detect_feature

        result = detect_feature()
        assert result == "my-feature"

    def test_returns_none_when_nothing_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When neither source exists, return None."""
        monkeypatch.chdir(tmp_path)

        from zerg.commands._utils import detect_feature

        result = detect_feature()
        assert result is None

    def test_empty_current_feature_falls_through(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When .current-feature is empty/whitespace, fall through to state JSON."""
        monkeypatch.chdir(tmp_path)

        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True)
        (gsd_dir / ".current-feature").write_text("   \n")

        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "fallback-feature.json").write_text(json.dumps({}))

        from zerg.commands._utils import detect_feature

        result = detect_feature()
        assert result == "fallback-feature"

    def test_state_json_returns_most_recent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When multiple state files exist, return the most recently modified."""
        monkeypatch.chdir(tmp_path)

        state_dir = tmp_path / ".zerg" / "state"
        state_dir.mkdir(parents=True)

        old_file = state_dir / "old-feature.json"
        old_file.write_text(json.dumps({}))

        # Ensure different mtime
        time.sleep(0.05)

        new_file = state_dir / "new-feature.json"
        new_file.write_text(json.dumps({}))

        from zerg.commands._utils import detect_feature

        result = detect_feature()
        assert result == "new-feature"

    def test_reexport_from_status_works(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The detect_feature() re-exported from status.py delegates correctly."""
        monkeypatch.chdir(tmp_path)

        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True)
        (gsd_dir / ".current-feature").write_text("from-status")

        from zerg.commands.status import detect_feature

        result = detect_feature()
        assert result == "from-status"
