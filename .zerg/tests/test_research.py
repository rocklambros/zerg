"""Tests for ZERG v2 Research Command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestResearchSource:
    """Tests for ResearchSource enum."""

    def test_sources_exist(self):
        """Test research sources are defined."""
        from research import ResearchSource

        assert hasattr(ResearchSource, "DOCS")
        assert hasattr(ResearchSource, "WEB")
        assert hasattr(ResearchSource, "CODE")
        assert hasattr(ResearchSource, "PAPERS")


class TestResearchDepth:
    """Tests for ResearchDepth enum."""

    def test_depths_exist(self):
        """Test research depths are defined."""
        from research import ResearchDepth

        assert hasattr(ResearchDepth, "QUICK")
        assert hasattr(ResearchDepth, "STANDARD")
        assert hasattr(ResearchDepth, "DEEP")


class TestResearchConfig:
    """Tests for ResearchConfig dataclass."""

    def test_config_defaults(self):
        """Test ResearchConfig default values."""
        from research import ResearchConfig

        config = ResearchConfig()
        assert "docs" in config.sources
        assert config.depth == "standard"
        assert config.max_results == 10


class TestResearchItem:
    """Tests for ResearchItem dataclass."""

    def test_item_creation(self):
        """Test ResearchItem can be created."""
        from research import ResearchItem

        item = ResearchItem(
            title="Test", url="https://example.com", source_type="docs", snippet="A snippet"
        )
        assert item.title == "Test"
        assert item.url == "https://example.com"

    def test_item_to_dict(self):
        """Test ResearchItem serialization."""
        from research import ResearchItem

        item = ResearchItem(
            title="Doc", url="https://docs.com", source_type="docs", snippet="Text"
        )
        data = item.to_dict()
        assert data["title"] == "Doc"
        assert data["source_type"] == "docs"


class TestResearchResult:
    """Tests for ResearchResult dataclass."""

    def test_result_creation(self):
        """Test ResearchResult can be created."""
        from research import ResearchResult

        result = ResearchResult(query="OAuth2", quick_answer="OAuth2 is...")
        assert result.query == "OAuth2"

    def test_result_to_dict(self):
        """Test ResearchResult serialization."""
        from research import ResearchResult

        result = ResearchResult(query="API", quick_answer="An API is...")
        data = result.to_dict()
        assert data["query"] == "API"

    def test_result_to_markdown(self):
        """Test ResearchResult markdown output."""
        from research import ResearchItem, ResearchResult

        items = [
            ResearchItem(
                title="Article", url="https://a.com", source_type="web", snippet="Text"
            )
        ]
        result = ResearchResult(query="REST", quick_answer="REST is...", items=items)
        md = result.to_markdown()
        assert "# Research: REST" in md
        assert "Quick Answer" in md


class TestDocsSearcher:
    """Tests for DocsSearcher."""

    def test_searcher_creation(self):
        """Test DocsSearcher can be created."""
        from research import DocsSearcher

        searcher = DocsSearcher()
        assert searcher is not None

    def test_search_returns_items(self):
        """Test search returns ResearchItems."""
        from research import DocsSearcher

        searcher = DocsSearcher()
        items = searcher.search("python decorators")
        assert len(items) > 0
        assert items[0].source_type == "docs"


class TestResearchAggregator:
    """Tests for ResearchAggregator."""

    def test_aggregator_creation(self):
        """Test ResearchAggregator can be created."""
        from research import ResearchAggregator

        agg = ResearchAggregator()
        assert agg is not None

    def test_research_returns_result(self):
        """Test research returns ResearchResult."""
        from research import ResearchAggregator, ResearchResult

        agg = ResearchAggregator()
        result = agg.research("python async")
        assert isinstance(result, ResearchResult)
        assert len(result.items) > 0


class TestResearchCommand:
    """Tests for ResearchCommand."""

    def test_command_creation(self):
        """Test ResearchCommand can be created."""
        from research import ResearchCommand

        cmd = ResearchCommand()
        assert cmd is not None

    def test_command_run(self):
        """Test running research."""
        from research import ResearchCommand, ResearchResult

        cmd = ResearchCommand()
        result = cmd.run(query="JWT authentication")
        assert isinstance(result, ResearchResult)
        assert result.query == "JWT authentication"

    def test_command_quick_depth(self):
        """Test quick depth limits results."""
        from research import ResearchCommand

        cmd = ResearchCommand()
        result = cmd.run(query="test", depth="quick")
        assert len(result.items) <= 3

    def test_command_format_json(self):
        """Test JSON output formatting."""
        import json

        from research import ResearchCommand, ResearchResult

        cmd = ResearchCommand()
        result = ResearchResult(query="test", quick_answer="answer")
        output = cmd.format_result(result, format="json")
        data = json.loads(output)
        assert data["query"] == "test"
