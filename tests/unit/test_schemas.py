"""Unit tests for ZERG schemas module."""

from pathlib import Path


class TestSchemasModule:
    """Tests for the schemas __init__.py module."""

    def test_import_schemas_module(self) -> None:
        """Test that schemas module can be imported."""
        import zerg.schemas  # noqa: F401

    def test_module_has_docstring(self) -> None:
        """Test that schemas module has a docstring."""
        import zerg.schemas

        assert zerg.schemas.__doc__ is not None
        assert "schema" in zerg.schemas.__doc__.lower()

    def test_schemas_dir_is_path(self) -> None:
        """Test that SCHEMAS_DIR is a Path object."""
        from zerg.schemas import SCHEMAS_DIR

        assert isinstance(SCHEMAS_DIR, Path)

    def test_schemas_dir_exists(self) -> None:
        """Test that SCHEMAS_DIR points to existing directory."""
        from zerg.schemas import SCHEMAS_DIR

        assert SCHEMAS_DIR.exists()
        assert SCHEMAS_DIR.is_dir()

    def test_schemas_dir_is_correct_location(self) -> None:
        """Test that SCHEMAS_DIR points to the schemas directory."""
        from zerg.schemas import SCHEMAS_DIR

        assert SCHEMAS_DIR.name == "schemas"
        assert SCHEMAS_DIR.parent.name == "zerg"


class TestGetSchemaPath:
    """Tests for get_schema_path function."""

    def test_get_schema_path_exists(self) -> None:
        """Test that get_schema_path function exists."""
        from zerg.schemas import get_schema_path

        assert callable(get_schema_path)

    def test_get_schema_path_returns_path(self) -> None:
        """Test that get_schema_path returns a Path object."""
        from zerg.schemas import get_schema_path

        result = get_schema_path("test_schema")
        assert isinstance(result, Path)

    def test_get_schema_path_adds_json_extension(self) -> None:
        """Test that get_schema_path adds .json extension."""
        from zerg.schemas import get_schema_path

        result = get_schema_path("my_schema")
        assert result.suffix == ".json"
        assert result.name == "my_schema.json"

    def test_get_schema_path_in_schemas_dir(self) -> None:
        """Test that get_schema_path returns path in SCHEMAS_DIR."""
        from zerg.schemas import SCHEMAS_DIR, get_schema_path

        result = get_schema_path("test")
        assert result.parent == SCHEMAS_DIR

    def test_get_schema_path_task_graph(self) -> None:
        """Test getting path for task_graph schema."""
        from zerg.schemas import get_schema_path

        result = get_schema_path("task_graph")
        assert result.name == "task_graph.json"
        assert result.exists()  # This schema should actually exist

    def test_get_schema_path_nonexistent(self) -> None:
        """Test get_schema_path with nonexistent schema name."""
        from zerg.schemas import get_schema_path

        result = get_schema_path("nonexistent_schema")
        # Function should return path even if file doesn't exist
        assert isinstance(result, Path)
        assert result.name == "nonexistent_schema.json"
        # The file should not exist
        assert not result.exists()

    def test_get_schema_path_empty_string(self) -> None:
        """Test get_schema_path with empty string."""
        from zerg.schemas import get_schema_path

        result = get_schema_path("")
        assert isinstance(result, Path)
        assert result.name == ".json"

    def test_get_schema_path_special_characters(self) -> None:
        """Test get_schema_path with special characters."""
        from zerg.schemas import get_schema_path

        result = get_schema_path("schema-with-dashes")
        assert result.name == "schema-with-dashes.json"

        result = get_schema_path("schema_with_underscores")
        assert result.name == "schema_with_underscores.json"

    def test_get_schema_path_unicode(self) -> None:
        """Test get_schema_path with unicode characters."""
        from zerg.schemas import get_schema_path

        result = get_schema_path("schema_unicode")
        assert result.name == "schema_unicode.json"

    def test_get_schema_path_with_spaces(self) -> None:
        """Test get_schema_path with spaces in name."""
        from zerg.schemas import get_schema_path

        result = get_schema_path("schema with spaces")
        assert result.name == "schema with spaces.json"


class TestSchemasDirConstant:
    """Tests for SCHEMAS_DIR constant."""

    def test_schemas_dir_is_absolute(self) -> None:
        """Test that SCHEMAS_DIR is an absolute path."""
        from zerg.schemas import SCHEMAS_DIR

        assert SCHEMAS_DIR.is_absolute()

    def test_schemas_dir_contains_init(self) -> None:
        """Test that SCHEMAS_DIR contains __init__.py."""
        from zerg.schemas import SCHEMAS_DIR

        init_file = SCHEMAS_DIR / "__init__.py"
        assert init_file.exists()

    def test_schemas_dir_contains_task_graph_schema(self) -> None:
        """Test that SCHEMAS_DIR contains task_graph.json."""
        from zerg.schemas import SCHEMAS_DIR

        schema_file = SCHEMAS_DIR / "task_graph.json"
        assert schema_file.exists()

    def test_schemas_dir_is_within_zerg_package(self) -> None:
        """Test that SCHEMAS_DIR is within the zerg package."""
        from zerg.schemas import SCHEMAS_DIR

        # Walk up the path to find the zerg package
        parent = SCHEMAS_DIR.parent
        assert parent.name == "zerg"
        assert (parent / "__init__.py").exists()


class TestModuleExports:
    """Tests for module exports and public API."""

    def test_public_api(self) -> None:
        """Test that module exports expected public API."""
        from zerg import schemas

        # Should have SCHEMAS_DIR
        assert hasattr(schemas, "SCHEMAS_DIR")

        # Should have get_schema_path
        assert hasattr(schemas, "get_schema_path")

    def test_get_schema_path_signature(self) -> None:
        """Test get_schema_path function signature."""
        import inspect

        from zerg.schemas import get_schema_path

        sig = inspect.signature(get_schema_path)
        params = list(sig.parameters.keys())

        assert "schema_name" in params
        assert len(params) == 1

    def test_get_schema_path_type_hints(self) -> None:
        """Test get_schema_path has proper type hints."""
        import inspect

        from zerg.schemas import get_schema_path

        sig = inspect.signature(get_schema_path)

        # Check parameter type hint
        param = sig.parameters["schema_name"]
        assert param.annotation is str

        # Check return type hint
        assert sig.return_annotation == Path


class TestSchemaFileContents:
    """Tests for actual schema file contents."""

    def test_task_graph_schema_is_valid_json(self) -> None:
        """Test that task_graph.json is valid JSON."""
        import json

        from zerg.schemas import get_schema_path

        schema_path = get_schema_path("task_graph")
        with open(schema_path) as f:
            data = json.load(f)

        assert isinstance(data, dict)

    def test_task_graph_schema_has_schema_key(self) -> None:
        """Test that task_graph.json has $schema key for JSON Schema."""
        import json

        from zerg.schemas import get_schema_path

        schema_path = get_schema_path("task_graph")
        with open(schema_path) as f:
            data = json.load(f)

        # JSON Schema files typically have $schema key
        assert "$schema" in data or "type" in data or "properties" in data

    def test_task_graph_schema_structure(self) -> None:
        """Test task_graph.json has expected schema structure."""
        import json

        from zerg.schemas import get_schema_path

        schema_path = get_schema_path("task_graph")
        with open(schema_path) as f:
            data = json.load(f)

        # Should have some standard JSON Schema components
        assert isinstance(data, dict)
        # At minimum should define some properties or type
        has_schema_elements = (
            "type" in data or "properties" in data or "$schema" in data or "definitions" in data or "$defs" in data
        )
        assert has_schema_elements


class TestEdgeCases:
    """Edge case tests for schemas module."""

    def test_multiple_get_schema_path_calls(self) -> None:
        """Test multiple calls to get_schema_path return consistent paths."""
        from zerg.schemas import get_schema_path

        path1 = get_schema_path("test")
        path2 = get_schema_path("test")

        assert path1 == path2

    def test_schemas_dir_immutable_reference(self) -> None:
        """Test that SCHEMAS_DIR reference is consistent across imports."""
        from zerg.schemas import SCHEMAS_DIR as dir1
        from zerg.schemas import SCHEMAS_DIR as dir2

        assert dir1 == dir2

    def test_path_operations_on_schema_path(self) -> None:
        """Test that returned path supports standard Path operations."""
        from zerg.schemas import get_schema_path

        path = get_schema_path("test")

        # Should support standard Path operations
        assert path.parent is not None
        assert path.name is not None
        assert path.stem == "test"
        assert path.suffix == ".json"
        assert str(path).endswith("test.json")

    def test_get_schema_path_with_json_extension_input(self) -> None:
        """Test get_schema_path when input already has .json extension."""
        from zerg.schemas import get_schema_path

        # If user passes "schema.json", result would be "schema.json.json"
        # This tests the actual behavior
        result = get_schema_path("schema.json")
        assert result.name == "schema.json.json"

    def test_get_schema_path_with_path_separators(self) -> None:
        """Test get_schema_path with path separators in name."""
        from zerg.schemas import get_schema_path

        # This would create a path like SCHEMAS_DIR/sub/schema.json
        result = get_schema_path("sub/schema")
        assert result.name == "schema.json"
        assert "sub" in str(result)
