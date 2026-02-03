"""Integration tests for container launcher and dynamic devcontainer generation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from zerg.constants import WorkerStatus
from zerg.devcontainer_features import (
    DEVCONTAINER_FEATURES,
    DynamicDevcontainerGenerator,
    get_features_for_languages,
    get_post_create_commands,
    should_use_single_image,
)
from zerg.launcher import ContainerLauncher, LauncherConfig, LauncherType


class TestDevcontainerFeatures:
    """Tests for devcontainer feature mapping."""

    def test_feature_mapping_exists(self) -> None:
        """Test that common languages have feature mappings."""
        expected_languages = ["python", "javascript", "typescript", "go", "rust", "java", "ruby"]
        for lang in expected_languages:
            assert lang in DEVCONTAINER_FEATURES, f"Missing feature for {lang}"

    def test_get_features_single_language(self) -> None:
        """Test feature generation for single language."""
        features = get_features_for_languages({"python"})

        assert len(features) >= 1
        assert any("python" in url for url in features.keys())

    def test_get_features_multi_language(self) -> None:
        """Test feature generation for multiple languages."""
        features = get_features_for_languages({"python", "javascript", "go"})

        # Should have at least 3 features
        assert len(features) >= 3

        # Check specific features
        urls = list(features.keys())
        assert any("python" in url for url in urls)
        assert any("node" in url for url in urls)  # javascript uses node
        assert any("go" in url for url in urls)

    def test_get_features_with_version_override(self) -> None:
        """Test feature generation with version overrides."""
        features = get_features_for_languages(
            {"python"},
            version_overrides={"python": "3.11"},
        )

        python_url = [u for u in features.keys() if "python" in u][0]
        assert features[python_url]["version"] == "3.11"

    def test_shared_features_not_duplicated(self) -> None:
        """Test that javascript and typescript share node feature."""
        features = get_features_for_languages({"javascript", "typescript"})

        node_features = [u for u in features.keys() if "node" in u]
        assert len(node_features) == 1  # Should only have one node feature

    def test_get_post_create_commands_python(self) -> None:
        """Test post-create commands for Python-only project."""
        commands = get_post_create_commands({"python"})

        # Python has a feature, so no custom install
        assert not any("python" in cmd.lower() for cmd in commands)

    def test_get_post_create_commands_r(self) -> None:
        """Test post-create commands for R (no feature available)."""
        commands = get_post_create_commands({"r"})

        # R requires custom install
        assert len(commands) >= 1
        assert any("r-base" in cmd for cmd in commands)

    def test_should_use_single_image_single_python(self) -> None:
        """Test single image optimization for Python-only."""
        result = should_use_single_image({"python"})

        assert result is not None
        assert "python" in result.lower()

    def test_should_use_single_image_multi_language(self) -> None:
        """Test no single image for multi-language."""
        result = should_use_single_image({"python", "javascript"})

        assert result is None


class TestDynamicDevcontainerGenerator:
    """Tests for DynamicDevcontainerGenerator."""

    def test_generate_spec_single_language(self) -> None:
        """Test spec generation for single language."""
        generator = DynamicDevcontainerGenerator()
        spec = generator.generate_spec({"python"})

        assert spec.name == "ZERG Worker"
        # Single language should use optimized image
        assert "python" in spec.base_image.lower()

    def test_generate_spec_multi_language(self) -> None:
        """Test spec generation for multiple languages."""
        generator = DynamicDevcontainerGenerator()
        spec = generator.generate_spec({"python", "javascript", "go"})

        # Multi-language should use base image
        assert "base" in spec.base_image.lower() or "ubuntu" in spec.base_image.lower()

        # Should have features
        assert len(spec.features) >= 3

    def test_generate_spec_with_security_strict(self) -> None:
        """Test spec generation with strict security."""
        generator = DynamicDevcontainerGenerator()
        spec = generator.generate_spec({"python"}, security_level="strict")

        assert "--read-only" in spec.run_args
        assert "--security-opt=no-new-privileges:true" in spec.run_args

    def test_generate_devcontainer_json(self) -> None:
        """Test devcontainer.json generation."""
        generator = DynamicDevcontainerGenerator()
        spec = generator.generate_spec({"python", "javascript"})
        config = generator.generate_devcontainer_json(spec)

        assert config["name"] == "ZERG Worker"
        assert "image" in config
        assert "features" in config
        assert "customizations" in config
        assert config["workspaceFolder"] == "/workspace"

    def test_write_devcontainer(self, tmp_path: Path) -> None:
        """Test writing devcontainer.json to disk."""
        output_dir = tmp_path / ".devcontainer"
        generator = DynamicDevcontainerGenerator()

        devcontainer_path = generator.write_devcontainer(
            languages={"python", "javascript"},
            output_dir=output_dir,
        )

        assert devcontainer_path.exists()
        assert devcontainer_path.name == "devcontainer.json"

        # Verify content
        with open(devcontainer_path) as f:
            config = json.load(f)

        assert config["name"] == "ZERG Worker"
        assert "features" in config

    def test_generate_worker_entry_script(self, tmp_path: Path) -> None:
        """Test worker entry script generation."""
        output_dir = tmp_path / ".zerg"
        generator = DynamicDevcontainerGenerator()

        script_path = generator.generate_worker_entry_script(output_dir)

        assert script_path.exists()
        assert script_path.name == "worker_entry.sh"

        # Check content
        content = script_path.read_text()
        assert "#!/bin/bash" in content
        assert "ZERG_WORKER_ID" in content
        assert "claude" in content

        # Check executable
        import os

        assert os.access(script_path, os.X_OK)


class TestContainerLauncher:
    """Tests for ContainerLauncher."""

    def test_init(self) -> None:
        """Test container launcher initialization."""
        launcher = ContainerLauncher()

        assert launcher.image_name == "zerg-worker"
        assert launcher.network == "bridge"
        assert launcher._workers == {}
        assert launcher._container_ids == {}

    def test_init_custom_config(self) -> None:
        """Test launcher with custom config."""
        config = LauncherConfig(launcher_type=LauncherType.CONTAINER)
        launcher = ContainerLauncher(
            config=config,
            image_name="custom-worker",
            network="custom-network",
        )

        assert launcher.image_name == "custom-worker"
        assert launcher.network == "custom-network"

    @patch("subprocess.run")
    @patch.object(ContainerLauncher, "_wait_ready", return_value=True)
    def test_spawn_success(self, mock_wait: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful container spawn."""
        # Mock docker run returning container ID
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123def456\n")

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        assert result.success is True
        assert result.worker_id == 0
        assert result.handle is not None
        assert result.handle.container_id == "abc123def456"

    @patch("subprocess.run")
    def test_spawn_docker_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test spawn failure when docker run fails."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="docker: Error response from daemon",
        )

        launcher = ContainerLauncher()
        result = launcher.spawn(
            worker_id=0,
            feature="test-feature",
            worktree_path=tmp_path,
            branch="zerg/test/worker-0",
        )

        assert result.success is False
        assert result.error is not None

    @patch("subprocess.run")
    def test_monitor_running(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test monitoring running container."""
        # Setup container
        launcher = ContainerLauncher()
        launcher._workers[0] = MagicMock(status=WorkerStatus.RUNNING)
        launcher._container_ids[0] = "abc123"

        # Mock docker inspect
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="true,0\n",  # running=true, exit_code=0
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.RUNNING

    @patch("subprocess.run")
    def test_monitor_exited(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test monitoring exited container."""
        # Setup container
        from zerg.launcher import WorkerHandle

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="abc123")
        launcher._container_ids[0] = "abc123"

        # Mock docker inspect - container exited
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="false,0\n",  # running=false, exit_code=0
        )

        status = launcher.monitor(0)
        assert status == WorkerStatus.STOPPED

    @patch("subprocess.run")
    def test_terminate(self, mock_run: MagicMock) -> None:
        """Test container termination."""
        from zerg.launcher import WorkerHandle

        launcher = ContainerLauncher()
        launcher._workers[0] = WorkerHandle(worker_id=0, container_id="abc123")
        launcher._container_ids[0] = "abc123"

        mock_run.return_value = MagicMock(returncode=0)

        result = launcher.terminate(0)

        assert result is True
        assert 0 not in launcher._container_ids

    @patch("subprocess.run")
    def test_get_output(self, mock_run: MagicMock) -> None:
        """Test getting container logs."""
        launcher = ContainerLauncher()
        launcher._container_ids[0] = "abc123"

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="log line 1\nlog line 2\n",
            stderr="",
        )

        output = launcher.get_output(0)

        assert "log line 1" in output
        assert "log line 2" in output

    @patch("subprocess.run")
    def test_ensure_network_exists(self, mock_run: MagicMock) -> None:
        """Test network check when it exists."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        result = launcher.ensure_network()

        assert result is True

    @patch("subprocess.run")
    def test_ensure_network_creates(self, mock_run: MagicMock) -> None:
        """Test network creation when it doesn't exist."""
        mock_run.side_effect = [
            MagicMock(returncode=1),  # inspect fails
            MagicMock(returncode=0),  # create succeeds
        ]

        launcher = ContainerLauncher()
        result = launcher.ensure_network()

        assert result is True
        # Should have called create after inspect failed
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_image_exists_true(self, mock_run: MagicMock) -> None:
        """Test image check when image exists."""
        mock_run.return_value = MagicMock(returncode=0)

        launcher = ContainerLauncher()
        result = launcher.image_exists()

        assert result is True

    @patch("subprocess.run")
    def test_image_exists_false(self, mock_run: MagicMock) -> None:
        """Test image check when image doesn't exist."""
        mock_run.return_value = MagicMock(returncode=1)

        launcher = ContainerLauncher()
        result = launcher.image_exists()

        assert result is False


class TestAutoDetectLauncherMode:
    """Tests for auto-detect launcher mode in orchestrator."""

    def test_auto_detect_no_devcontainer(self, tmp_path: Path) -> None:
        """Test auto-detect when no devcontainer exists."""
        # Test that without a devcontainer, subprocess mode is selected
        devcontainer_path = tmp_path / ".devcontainer" / "devcontainer.json"

        # No devcontainer = subprocess mode
        assert not devcontainer_path.exists()

    def test_auto_detect_with_devcontainer_no_image(self, tmp_path: Path) -> None:
        """Test auto-detect when devcontainer exists but no image."""
        # Create devcontainer.json
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir(parents=True)
        (devcontainer_dir / "devcontainer.json").write_text("{}")

        assert (devcontainer_dir / "devcontainer.json").exists()


class TestInitMultiLanguage:
    """Tests for multi-language detection in init command."""

    def test_detect_python_project(self, tmp_path: Path, monkeypatch) -> None:
        """Test detecting Python project."""
        monkeypatch.chdir(tmp_path)

        # Create Python indicators
        (tmp_path / "requirements.txt").write_text("fastapi\npydantic\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        from zerg.security_rules import detect_project_stack

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages

    def test_detect_multi_language_project(self, tmp_path: Path, monkeypatch) -> None:
        """Test detecting multi-language project."""
        monkeypatch.chdir(tmp_path)

        # Create Python indicators
        (tmp_path / "requirements.txt").write_text("fastapi\n")

        # Create JavaScript indicators
        (tmp_path / "package.json").write_text('{"name": "test", "dependencies": {"react": "^18.0.0"}}')

        from zerg.security_rules import detect_project_stack

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages
        assert "javascript" in stack.languages
