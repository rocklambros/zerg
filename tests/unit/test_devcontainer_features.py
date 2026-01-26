"""Unit tests for ZERG devcontainer features module."""

from zerg.devcontainer_features import (
    CUSTOM_INSTALL_COMMANDS,
    DEFAULT_BASE_IMAGE,
    DEVCONTAINER_FEATURES,
    SINGLE_LANGUAGE_IMAGES,
    DevcontainerSpec,
    get_features_for_languages,
)


class TestDevcontainerFeatures:
    """Tests for devcontainer feature mappings."""

    def test_python_feature_exists(self) -> None:
        """Test Python feature is defined."""
        assert "python" in DEVCONTAINER_FEATURES
        url, options = DEVCONTAINER_FEATURES["python"]
        assert "python" in url
        assert "version" in options

    def test_javascript_feature_exists(self) -> None:
        """Test JavaScript feature is defined."""
        assert "javascript" in DEVCONTAINER_FEATURES
        url, _ = DEVCONTAINER_FEATURES["javascript"]
        assert "node" in url

    def test_typescript_feature_exists(self) -> None:
        """Test TypeScript feature is defined."""
        assert "typescript" in DEVCONTAINER_FEATURES
        url, _ = DEVCONTAINER_FEATURES["typescript"]
        assert "node" in url

    def test_go_feature_exists(self) -> None:
        """Test Go feature is defined."""
        assert "go" in DEVCONTAINER_FEATURES
        url, options = DEVCONTAINER_FEATURES["go"]
        assert "go" in url

    def test_rust_feature_exists(self) -> None:
        """Test Rust feature is defined."""
        assert "rust" in DEVCONTAINER_FEATURES
        url, _ = DEVCONTAINER_FEATURES["rust"]
        assert "rust" in url

    def test_java_feature_exists(self) -> None:
        """Test Java feature is defined."""
        assert "java" in DEVCONTAINER_FEATURES
        url, options = DEVCONTAINER_FEATURES["java"]
        assert "java" in url

    def test_git_feature_exists(self) -> None:
        """Test Git feature is defined."""
        assert "git" in DEVCONTAINER_FEATURES

    def test_github_cli_feature_exists(self) -> None:
        """Test GitHub CLI feature is defined."""
        assert "github-cli" in DEVCONTAINER_FEATURES


class TestCustomInstallCommands:
    """Tests for custom install commands."""

    def test_r_install_command(self) -> None:
        """Test R has install command."""
        assert "r" in CUSTOM_INSTALL_COMMANDS
        assert "r-base" in CUSTOM_INSTALL_COMMANDS["r"]

    def test_julia_install_command(self) -> None:
        """Test Julia has install command."""
        assert "julia" in CUSTOM_INSTALL_COMMANDS
        assert "julia" in CUSTOM_INSTALL_COMMANDS["julia"]

    def test_cpp_install_command(self) -> None:
        """Test C++ has install command."""
        assert "cpp" in CUSTOM_INSTALL_COMMANDS
        assert "build-essential" in CUSTOM_INSTALL_COMMANDS["cpp"]


class TestSingleLanguageImages:
    """Tests for single language optimized images."""

    def test_python_image(self) -> None:
        """Test Python has optimized image."""
        assert "python" in SINGLE_LANGUAGE_IMAGES
        assert "python" in SINGLE_LANGUAGE_IMAGES["python"]

    def test_javascript_image(self) -> None:
        """Test JavaScript has optimized image."""
        assert "javascript" in SINGLE_LANGUAGE_IMAGES
        assert "node" in SINGLE_LANGUAGE_IMAGES["javascript"]

    def test_go_image(self) -> None:
        """Test Go has optimized image."""
        assert "go" in SINGLE_LANGUAGE_IMAGES
        assert "go" in SINGLE_LANGUAGE_IMAGES["go"]


class TestDefaultBaseImage:
    """Tests for default base image."""

    def test_default_base_image_is_ubuntu(self) -> None:
        """Test default base image is Ubuntu-based."""
        assert "ubuntu" in DEFAULT_BASE_IMAGE
        assert "devcontainers" in DEFAULT_BASE_IMAGE


class TestDevcontainerSpec:
    """Tests for DevcontainerSpec dataclass."""

    def test_default_spec(self) -> None:
        """Test default spec values."""
        spec = DevcontainerSpec()

        assert spec.name == "ZERG Worker"
        assert spec.base_image == DEFAULT_BASE_IMAGE
        assert spec.features == {}
        assert spec.post_create_commands == []
        assert spec.extensions == []
        assert spec.env_vars == {}
        assert spec.mounts == []
        assert spec.run_args == []
        assert spec.workspace_folder == "/workspace"

    def test_custom_spec(self) -> None:
        """Test custom spec values."""
        spec = DevcontainerSpec(
            name="Custom Worker",
            base_image="custom:latest",
            features={"test": {}},
            env_vars={"KEY": "value"},
        )

        assert spec.name == "Custom Worker"
        assert spec.base_image == "custom:latest"
        assert spec.features == {"test": {}}
        assert spec.env_vars == {"KEY": "value"}


class TestGetFeaturesForLanguages:
    """Tests for get_features_for_languages function."""

    def test_single_language(self) -> None:
        """Test getting features for single language."""
        features = get_features_for_languages(["python"])

        assert len(features) == 1
        assert any("python" in url for url in features.keys())

    def test_multiple_languages(self) -> None:
        """Test getting features for multiple languages."""
        features = get_features_for_languages(["python", "go", "rust"])

        assert len(features) == 3

    def test_shared_runtime(self) -> None:
        """Test JavaScript and TypeScript share node runtime."""
        features = get_features_for_languages(["javascript", "typescript"])

        # Should only have one entry (node) since they share runtime
        assert len(features) == 1

    def test_version_override(self) -> None:
        """Test version override works."""
        features = get_features_for_languages(
            ["python"],
            version_overrides={"python": "3.11"},
        )

        for url, options in features.items():
            if "python" in url:
                assert options.get("version") == "3.11"

    def test_unknown_language_ignored(self) -> None:
        """Test unknown languages are ignored."""
        features = get_features_for_languages(["python", "unknown-lang"])

        # Should only have Python
        assert len(features) == 1

    def test_empty_languages(self) -> None:
        """Test empty language list."""
        features = get_features_for_languages([])

        assert features == {}

    def test_set_input(self) -> None:
        """Test set input works."""
        features = get_features_for_languages({"python", "go"})

        assert len(features) == 2
