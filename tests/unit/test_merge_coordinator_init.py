"""Tests for MergeCoordinator __init__ and prepare_merge methods."""

from pathlib import Path
from unittest.mock import patch

from zerg.config import QualityGate, ZergConfig
from zerg.merge import MergeCoordinator


class TestMergeCoordinatorInit:
    """Tests for MergeCoordinator initialization."""

    def test_init_with_default_config(self, tmp_repo: Path) -> None:
        """Test __init__ with default config loads ZergConfig."""
        with patch("zerg.merge.ZergConfig.load") as mock_load:
            mock_config = ZergConfig()
            mock_load.return_value = mock_config

            coordinator = MergeCoordinator(feature="test-feature", repo_path=tmp_repo)

            mock_load.assert_called_once()
            assert coordinator.feature == "test-feature"
            assert coordinator.config is mock_config

    def test_init_with_custom_config(self, tmp_repo: Path) -> None:
        """Test __init__ with custom config does not load from file."""
        custom_config = ZergConfig()
        custom_config.quality_gates = [QualityGate(name="custom-lint", command="echo lint", required=True)]

        with patch("zerg.merge.ZergConfig.load") as mock_load:
            coordinator = MergeCoordinator(
                feature="test-feature",
                config=custom_config,
                repo_path=tmp_repo,
            )

            mock_load.assert_not_called()
            assert coordinator.config is custom_config
            assert len(coordinator.config.quality_gates) == 1
            assert coordinator.config.quality_gates[0].name == "custom-lint"

    def test_init_with_custom_repo_path(self, tmp_repo: Path) -> None:
        """Test __init__ with custom repo_path resolves to absolute path."""
        config = ZergConfig()

        coordinator = MergeCoordinator(
            feature="test-feature",
            config=config,
            repo_path=tmp_repo,
        )

        assert coordinator.repo_path == tmp_repo.resolve()
        assert coordinator.repo_path.is_absolute()

    def test_init_with_string_repo_path(self, tmp_repo: Path) -> None:
        """Test __init__ with string repo_path converts to Path."""
        config = ZergConfig()

        coordinator = MergeCoordinator(
            feature="test-feature",
            config=config,
            repo_path=str(tmp_repo),
        )

        assert coordinator.repo_path == tmp_repo.resolve()
        assert isinstance(coordinator.repo_path, Path)

    def test_init_creates_git_ops_instance(self, tmp_repo: Path) -> None:
        """Test __init__ creates GitOps instance with repo_path."""
        config = ZergConfig()

        coordinator = MergeCoordinator(
            feature="test-feature",
            config=config,
            repo_path=tmp_repo,
        )

        assert coordinator.git is not None
        assert coordinator.git.repo_path == tmp_repo.resolve()

    def test_init_creates_gate_runner_instance(self, tmp_repo: Path) -> None:
        """Test __init__ creates GateRunner instance with config."""
        config = ZergConfig()

        coordinator = MergeCoordinator(
            feature="test-feature",
            config=config,
            repo_path=tmp_repo,
        )

        assert coordinator.gates is not None


class TestMergeCoordinatorPrepareMerge:
    """Tests for MergeCoordinator.prepare_merge method."""

    def test_prepare_merge_creates_correct_staging_branch_name(self, tmp_repo: Path) -> None:
        """Test prepare_merge creates staging branch with correct naming."""
        config = ZergConfig()
        coordinator = MergeCoordinator(
            feature="my-feature",
            config=config,
            repo_path=tmp_repo,
        )

        staging_branch = coordinator.prepare_merge(level=1, target_branch="main")

        # The GitOps.create_staging_branch formats as zerg/{feature}/staging
        assert staging_branch == "zerg/my-feature/staging"

    def test_prepare_merge_creates_branch_from_target(self, tmp_repo: Path) -> None:
        """Test prepare_merge creates branch from specified target."""
        config = ZergConfig()
        coordinator = MergeCoordinator(
            feature="test-feature",
            config=config,
            repo_path=tmp_repo,
        )

        staging_branch = coordinator.prepare_merge(level=1, target_branch="main")

        # Verify branch was created
        assert coordinator.git.branch_exists(staging_branch)

    def test_prepare_merge_logs_creation(self, tmp_repo: Path) -> None:
        """Test prepare_merge logs staging branch creation."""
        config = ZergConfig()
        coordinator = MergeCoordinator(
            feature="test-feature",
            config=config,
            repo_path=tmp_repo,
        )

        with patch("zerg.merge.logger") as mock_logger:
            staging_branch = coordinator.prepare_merge(level=1, target_branch="main")

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "staging branch" in call_args.lower()
            assert staging_branch in call_args
            assert "main" in call_args

    def test_prepare_merge_default_target_is_main(self, tmp_repo: Path) -> None:
        """Test prepare_merge uses 'main' as default target branch."""
        config = ZergConfig()
        coordinator = MergeCoordinator(
            feature="test-feature",
            config=config,
            repo_path=tmp_repo,
        )

        # Call without specifying target_branch
        staging_branch = coordinator.prepare_merge(level=1)

        # Should use main as default
        assert coordinator.git.branch_exists(staging_branch)

    def test_prepare_merge_returns_staging_branch_name(self, tmp_repo: Path) -> None:
        """Test prepare_merge returns the staging branch name."""
        config = ZergConfig()
        coordinator = MergeCoordinator(
            feature="test-feature",
            config=config,
            repo_path=tmp_repo,
        )

        result = coordinator.prepare_merge(level=2, target_branch="main")

        assert isinstance(result, str)
        assert result.startswith("zerg/")
        assert "staging" in result
