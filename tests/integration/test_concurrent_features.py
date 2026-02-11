"""Integration tests for concurrent feature isolation via ZERG_FEATURE env var.

Tests verify the detect_feature() priority chain:
1. ZERG_FEATURE env var (terminal-session-scoped, multi-epic safe)
2. .gsd/.current-feature file (explicit user intent from /zerg:plan)
3. .zerg/state/*.json (most recently modified state file)

These tests ensure multiple terminals can run different features
concurrently without interfering with each other.
"""

from pathlib import Path

from zerg.commands._utils import detect_feature


class TestEnvVarPriority:
    """Tests that ZERG_FEATURE env var takes priority over file-based detection."""

    def test_env_var_takes_priority_over_file(self, tmp_path: Path, monkeypatch) -> None:
        """ZERG_FEATURE env var must win over .gsd/.current-feature file."""
        monkeypatch.chdir(tmp_path)

        # Set up .gsd/.current-feature with a different feature name
        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True)
        (gsd_dir / ".current-feature").write_text("epic-2\n")

        # Set the env var to a competing feature name
        monkeypatch.setenv("ZERG_FEATURE", "epic-1")

        result = detect_feature()

        assert result == "epic-1", f"Expected env var 'epic-1' to win over file 'epic-2', got '{result}'"

    def test_two_features_isolated_via_env_var(self, tmp_path: Path, monkeypatch) -> None:
        """Simulates two terminals with different ZERG_FEATURE values.

        Each terminal sets a different ZERG_FEATURE. Switching the env var
        between calls must return the correct feature each time, proving
        that terminal-scoped isolation works.
        """
        monkeypatch.chdir(tmp_path)

        # Terminal A is working on epic-alpha
        monkeypatch.setenv("ZERG_FEATURE", "epic-alpha")
        result_a = detect_feature()
        assert result_a == "epic-alpha"

        # Terminal B is working on epic-beta (same process, different env)
        monkeypatch.setenv("ZERG_FEATURE", "epic-beta")
        result_b = detect_feature()
        assert result_b == "epic-beta"

        # Results must differ, proving isolation
        assert result_a != result_b, "Two different ZERG_FEATURE values must produce different results"


class TestEnvVarFallthrough:
    """Tests that empty or unset ZERG_FEATURE falls through to file detection."""

    def test_empty_env_var_falls_through_to_file(self, tmp_path: Path, monkeypatch) -> None:
        """Empty ZERG_FEATURE must fall through to .gsd/.current-feature."""
        monkeypatch.chdir(tmp_path)

        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True)
        (gsd_dir / ".current-feature").write_text("epic-from-file\n")

        # Set env var to empty string -- should not count as a value
        monkeypatch.setenv("ZERG_FEATURE", "")

        result = detect_feature()

        assert result == "epic-from-file", f"Empty ZERG_FEATURE should fall through to file, got '{result}'"

    def test_unset_env_var_falls_through_to_file(self, tmp_path: Path, monkeypatch) -> None:
        """Absent ZERG_FEATURE must fall through to .gsd/.current-feature."""
        monkeypatch.chdir(tmp_path)

        gsd_dir = tmp_path / ".gsd"
        gsd_dir.mkdir(parents=True)
        (gsd_dir / ".current-feature").write_text("fallback-feature\n")

        # Ensure the env var is completely absent
        monkeypatch.delenv("ZERG_FEATURE", raising=False)

        result = detect_feature()

        assert result == "fallback-feature", f"Unset ZERG_FEATURE should fall through to file, got '{result}'"


class TestEnvVarWhitespace:
    """Tests that whitespace in ZERG_FEATURE is handled correctly."""

    def test_whitespace_env_var_stripped(self, tmp_path: Path, monkeypatch) -> None:
        """Leading/trailing whitespace in ZERG_FEATURE must be stripped."""
        monkeypatch.chdir(tmp_path)

        monkeypatch.setenv("ZERG_FEATURE", "  epic-spaces  ")

        result = detect_feature()

        assert result == "epic-spaces", f"Whitespace should be stripped from ZERG_FEATURE, got '{result!r}'"
