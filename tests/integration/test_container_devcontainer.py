"""Integration tests for dynamic devcontainer generation."""

import json
from pathlib import Path

from zerg.devcontainer_features import (
    DynamicDevcontainerGenerator,
    get_features_for_languages,
    get_post_create_commands,
)


class TestDynamicDevcontainer:
    """Test suite for dynamic devcontainer configuration generation."""

    def test_multi_language_features(self) -> None:
        """Generate features for multiple languages.

        Verifies that requesting Python and JavaScript features
        returns appropriate devcontainer feature URLs.
        """
        features = get_features_for_languages({"python", "javascript"})

        feature_urls = list(features.keys())

        # Check Python feature present
        has_python = any("python" in url.lower() for url in feature_urls)
        assert has_python, f"Expected python feature in {feature_urls}"

        # Check Node/JavaScript feature present
        has_node = any("node" in url.lower() for url in feature_urls)
        assert has_node, f"Expected node feature in {feature_urls}"

    def test_custom_install_for_r(self) -> None:
        """Generate custom install commands for R language.

        R is not a standard devcontainer feature, so it should
        generate postCreateCommand entries for installation.
        """
        commands = get_post_create_commands({"r"})

        # Should have R installation command
        has_r_install = any("r" in cmd.lower() or "r-base" in cmd.lower() for cmd in commands)
        assert has_r_install, f"Expected R install command in {commands}"

    def test_write_devcontainer_file(self, tmp_path: Path) -> None:
        """Write devcontainer.json to disk.

        Creates a generator, writes the config, and verifies
        the output file is valid JSON with expected structure.
        """
        generator = DynamicDevcontainerGenerator(
            name="Test Container",
            install_claude=False,
        )

        # Create output directory
        output_dir = tmp_path / ".devcontainer"
        output_dir.mkdir(parents=True, exist_ok=True)

        # write_devcontainer requires languages as first arg, output_dir as second
        output_path = generator.write_devcontainer(
            languages={"python"},
            output_dir=output_dir,
        )

        # Verify file exists
        assert output_path.exists(), f"Expected file at {output_path}"
        assert output_path.name == "devcontainer.json"

        # Verify valid JSON
        config = json.loads(output_path.read_text())

        # Verify required fields
        assert "name" in config, "Config should have 'name' field"
