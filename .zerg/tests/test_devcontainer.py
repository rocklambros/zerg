"""Tests for ZERG v2 DevContainer generation and build."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDevcontainerConfig:
    """Tests for DevcontainerConfig dataclass."""

    def test_config_defaults(self):
        """Test DevcontainerConfig default values."""
        from devcontainer import DevcontainerConfig

        config = DevcontainerConfig()
        assert config.name == "zerg-worker"
        assert config.python_version == "3.12"
        assert config.node_version == "20"
        assert config.install_claude is True

    def test_config_custom(self):
        """Test DevcontainerConfig with custom values."""
        from devcontainer import DevcontainerConfig

        config = DevcontainerConfig(
            name="custom-worker",
            python_version="3.11",
            install_claude=False,
        )
        assert config.name == "custom-worker"
        assert config.python_version == "3.11"
        assert config.install_claude is False


class TestBuildResult:
    """Tests for BuildResult dataclass."""

    def test_build_result_success(self):
        """Test successful BuildResult."""
        from devcontainer import BuildResult

        result = BuildResult(
            success=True,
            image_name="test-image",
            image_id="sha256:abc123",
            build_time_seconds=45.5,
        )
        assert result.success is True
        assert result.image_name == "test-image"

    def test_build_result_failure(self):
        """Test failed BuildResult."""
        from devcontainer import BuildResult

        result = BuildResult(
            success=False,
            image_name="test-image",
            error="Build failed: missing dependency",
        )
        assert result.success is False
        assert "Build failed" in result.error

    def test_build_result_to_dict(self):
        """Test BuildResult serialization."""
        from devcontainer import BuildResult

        result = BuildResult(success=True, image_name="img", image_id="123")
        data = result.to_dict()
        assert data["success"] is True
        assert data["image_name"] == "img"


class TestDockerfileTemplates:
    """Tests for Dockerfile templates."""

    def test_python_template_exists(self):
        """Test Python Dockerfile template exists."""
        from devcontainer import DOCKERFILE_TEMPLATES

        assert "python" in DOCKERFILE_TEMPLATES
        assert "FROM python:" in DOCKERFILE_TEMPLATES["python"]

    def test_typescript_template_exists(self):
        """Test TypeScript Dockerfile template exists."""
        from devcontainer import DOCKERFILE_TEMPLATES

        assert "typescript" in DOCKERFILE_TEMPLATES
        assert "FROM node:" in DOCKERFILE_TEMPLATES["typescript"]

    def test_go_template_exists(self):
        """Test Go Dockerfile template exists."""
        from devcontainer import DOCKERFILE_TEMPLATES

        assert "go" in DOCKERFILE_TEMPLATES
        assert "FROM golang:" in DOCKERFILE_TEMPLATES["go"]

    def test_rust_template_exists(self):
        """Test Rust Dockerfile template exists."""
        from devcontainer import DOCKERFILE_TEMPLATES

        assert "rust" in DOCKERFILE_TEMPLATES
        assert "FROM rust:" in DOCKERFILE_TEMPLATES["rust"]

    def test_default_template_exists(self):
        """Test default Dockerfile template exists."""
        from devcontainer import DOCKERFILE_TEMPLATES

        assert "default" in DOCKERFILE_TEMPLATES


class TestDevcontainerGenerator:
    """Tests for DevcontainerGenerator."""

    def test_generator_creation(self):
        """Test DevcontainerGenerator can be created."""
        from devcontainer import DevcontainerGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = DevcontainerGenerator(Path(tmpdir))
            assert gen is not None

    def test_generate_creates_directory(self):
        """Test generate creates .devcontainer directory."""
        from devcontainer import DevcontainerGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            gen = DevcontainerGenerator(project_path)
            result = gen.generate(language="python")
            assert result.exists()
            assert result.name == ".devcontainer"

    def test_generate_creates_dockerfile(self):
        """Test generate creates Dockerfile."""
        from devcontainer import DevcontainerGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            gen = DevcontainerGenerator(project_path)
            gen.generate(language="python")
            dockerfile = project_path / ".devcontainer" / "Dockerfile"
            assert dockerfile.exists()
            content = dockerfile.read_text()
            assert "FROM python:" in content

    def test_generate_creates_devcontainer_json(self):
        """Test generate creates devcontainer.json."""
        import json

        from devcontainer import DevcontainerGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            gen = DevcontainerGenerator(project_path)
            gen.generate(language="typescript")
            config_file = project_path / ".devcontainer" / "devcontainer.json"
            assert config_file.exists()
            config = json.loads(config_file.read_text())
            assert "name" in config
            assert "build" in config

    def test_generate_creates_docker_compose(self):
        """Test generate creates docker-compose.yaml."""
        from devcontainer import DevcontainerGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            gen = DevcontainerGenerator(project_path)
            gen.generate(language="python")
            compose = project_path / ".devcontainer" / "docker-compose.yaml"
            assert compose.exists()
            content = compose.read_text()
            assert "services:" in content

    def test_generate_creates_post_create(self):
        """Test generate creates post-create.sh."""
        from devcontainer import DevcontainerGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            gen = DevcontainerGenerator(project_path)
            gen.generate(language="python")
            script = project_path / ".devcontainer" / "post-create.sh"
            assert script.exists()
            # Check executable
            assert script.stat().st_mode & 0o111

    def test_generate_typescript_extensions(self):
        """Test TypeScript generation includes extensions."""
        import json

        from devcontainer import DevcontainerGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            gen = DevcontainerGenerator(project_path)
            gen.generate(language="typescript")
            config_file = project_path / ".devcontainer" / "devcontainer.json"
            config = json.loads(config_file.read_text())
            extensions = config["customizations"]["vscode"]["extensions"]
            assert "dbaeumer.vscode-eslint" in extensions


class TestDevcontainerBuilder:
    """Tests for DevcontainerBuilder."""

    def test_builder_creation(self):
        """Test DevcontainerBuilder can be created."""
        from devcontainer import DevcontainerBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DevcontainerBuilder(Path(tmpdir))
            assert builder is not None

    def test_image_exists_false_for_nonexistent(self):
        """Test image_exists returns False for non-existent image."""
        from devcontainer import DevcontainerBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DevcontainerBuilder(Path(tmpdir))
            # Use a name that definitely doesn't exist
            exists = builder.image_exists("zerg-nonexistent-test-image-12345")
            assert exists is False

    def test_build_without_dockerfile_fails(self):
        """Test build fails when Dockerfile is missing."""
        from devcontainer import DevcontainerBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DevcontainerBuilder(Path(tmpdir))
            result = builder.build(image_name="test")
            assert result.success is False
            assert "Dockerfile not found" in result.error


class TestDevcontainerManager:
    """Tests for DevcontainerManager."""

    def test_manager_creation(self):
        """Test DevcontainerManager can be created."""
        from devcontainer import DevcontainerManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = DevcontainerManager(Path(tmpdir))
            assert manager is not None

    def test_setup_generates_files(self):
        """Test setup generates devcontainer files."""
        from devcontainer import DevcontainerManager

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = DevcontainerManager(project_path)
            # Don't build (requires Docker)
            devcontainer_path, _ = manager.setup(
                language="python",
                build=False,
            )
            assert devcontainer_path.exists()
            assert (devcontainer_path / "Dockerfile").exists()

    def test_setup_with_framework(self):
        """Test setup with framework parameter."""
        from devcontainer import DevcontainerManager

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = DevcontainerManager(project_path)
            devcontainer_path, _ = manager.setup(
                language="python",
                framework="fastapi",
                build=False,
            )
            assert devcontainer_path.exists()
