"""Tests for zerg.performance.catalog module."""

from __future__ import annotations

from zerg.performance.catalog import FactorCatalog


class TestFactorCatalogLoad:
    """Tests for FactorCatalog.load() and factor queries."""

    def test_load_returns_140_factors(self) -> None:
        catalog = FactorCatalog.load()
        assert len(catalog.factors) == 140

    def test_loaded_factors_have_correct_types(self) -> None:
        catalog = FactorCatalog.load()
        for f in catalog.factors:
            assert isinstance(f.id, int)
            assert isinstance(f.category, str)
            assert isinstance(f.factor, str)
            assert isinstance(f.description, str)
            assert isinstance(f.cli_tools, list)

    def test_filter_static_only_returns_fewer(self) -> None:
        catalog = FactorCatalog.load()
        static = catalog.filter_static_only()
        assert len(static) < len(catalog.factors)
        assert len(static) > 0

    def test_filter_static_only_includes_static_tools(self) -> None:
        catalog = FactorCatalog.load()
        static = catalog.filter_static_only()
        static_tool_names = {
            "semgrep",
            "radon",
            "lizard",
            "vulture",
            "jscpd",
            "deptry",
            "pipdeptree",
            "dive",
            "hadolint",
            "trivy",
            "cloc",
        }
        for factor in static:
            assert any(t in static_tool_names for t in factor.cli_tools), (
                f"Factor {factor.id} has no static tools in {factor.cli_tools}"
            )

    def test_get_tool_factor_mapping_has_expected_keys(self) -> None:
        catalog = FactorCatalog.load()
        mapping = catalog.get_tool_factor_mapping()
        assert isinstance(mapping, dict)
        assert "semgrep" in mapping
        assert "radon" in mapping

    def test_get_tool_factor_mapping_values_are_int_lists(self) -> None:
        catalog = FactorCatalog.load()
        mapping = catalog.get_tool_factor_mapping()
        for tool_name, factor_ids in mapping.items():
            assert isinstance(factor_ids, list), f"{tool_name} value is not a list"
            for fid in factor_ids:
                assert isinstance(fid, int), f"{tool_name} has non-int factor id: {fid}"

    def test_get_factors_by_category_has_cpu_key(self) -> None:
        catalog = FactorCatalog.load()
        by_cat = catalog.get_factors_by_category()
        assert isinstance(by_cat, dict)
        assert "CPU and Compute" in by_cat
        assert len(by_cat["CPU and Compute"]) > 0
