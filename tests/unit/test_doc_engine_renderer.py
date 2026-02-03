"""Comprehensive tests for zerg.doc_engine.renderer and zerg.doc_engine.templates.

Covers: DocRenderer (all render methods), all private helper functions,
template placeholders, edge cases, and branch coverage.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zerg.doc_engine.extractor import ClassInfo, FunctionInfo, ImportInfo, SymbolTable
from zerg.doc_engine.renderer import (
    DocRenderer,
    _build_class_diagram,
    _build_classes_table,
    _build_dataclass_details,
    _build_dependency_diagram,
    _build_endpoints_table,
    _build_enums_table,
    _build_functions_table,
    _build_imports_list,
    _build_type_defs_table,
    _count_lines,
    _extract_md_section,
    _extract_md_summary,
    _extract_md_title,
    _mermaid_id,
    _module_title,
    _relative,
)
from zerg.doc_engine.templates import (
    API_TEMPLATE,
    COMMAND_TEMPLATE,
    CONFIG_TEMPLATE,
    MODULE_TEMPLATE,
    TEMPLATES,
    TYPES_TEMPLATE,
)

# ======================================================================
# Fixtures
# ======================================================================


def _make_function(
    name: str = "my_func",
    args: list[str] | None = None,
    return_type: str | None = None,
    docstring: str | None = None,
    decorators: list[str] | None = None,
    is_async: bool = False,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        lineno=1,
        docstring=docstring,
        args=args or [],
        return_type=return_type,
        decorators=decorators or [],
        is_method=False,
        is_async=is_async,
    )


def _make_method(
    name: str = "method",
    args: list[str] | None = None,
    return_type: str | None = None,
    docstring: str | None = None,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        lineno=1,
        docstring=docstring,
        args=args or ["self"],
        return_type=return_type,
        decorators=[],
        is_method=True,
        is_async=False,
    )


def _make_class(
    name: str = "MyClass",
    bases: list[str] | None = None,
    methods: list[FunctionInfo] | None = None,
    docstring: str | None = None,
    decorators: list[str] | None = None,
) -> ClassInfo:
    return ClassInfo(
        name=name,
        lineno=1,
        docstring=docstring,
        bases=bases or [],
        methods=methods or [],
        decorators=decorators or [],
    )


def _make_import(module: str, names: list[str] | None = None, is_from: bool = False) -> ImportInfo:
    return ImportInfo(module=module, names=names or [module], is_from=is_from)


def _make_symbol_table(
    path: Path,
    module_docstring: str | None = "Test module.",
    classes: list[ClassInfo] | None = None,
    functions: list[FunctionInfo] | None = None,
    imports: list[ImportInfo] | None = None,
    constants: list[str] | None = None,
    type_aliases: list[str] | None = None,
) -> SymbolTable:
    return SymbolTable(
        path=path,
        module_docstring=module_docstring,
        classes=classes or [],
        functions=functions or [],
        imports=imports or [],
        constants=constants or [],
        type_aliases=type_aliases or [],
    )


# ======================================================================
# templates.py tests
# ======================================================================


class TestTemplates:
    """Verify template constants and TEMPLATES dict."""

    def test_templates_dict_has_all_keys(self) -> None:
        expected = {"MODULE", "COMMAND", "CONFIG", "TYPES", "API"}
        assert set(TEMPLATES.keys()) == expected

    def test_module_template_is_string(self) -> None:
        assert isinstance(MODULE_TEMPLATE, str)

    def test_command_template_is_string(self) -> None:
        assert isinstance(COMMAND_TEMPLATE, str)

    def test_config_template_is_string(self) -> None:
        assert isinstance(CONFIG_TEMPLATE, str)

    def test_types_template_is_string(self) -> None:
        assert isinstance(TYPES_TEMPLATE, str)

    def test_api_template_is_string(self) -> None:
        assert isinstance(API_TEMPLATE, str)

    def test_templates_dict_values_match_constants(self) -> None:
        assert TEMPLATES["MODULE"] is MODULE_TEMPLATE
        assert TEMPLATES["COMMAND"] is COMMAND_TEMPLATE
        assert TEMPLATES["CONFIG"] is CONFIG_TEMPLATE
        assert TEMPLATES["TYPES"] is TYPES_TEMPLATE
        assert TEMPLATES["API"] is API_TEMPLATE

    def test_module_template_has_expected_placeholders(self) -> None:
        for placeholder in [
            "{title}",
            "{summary}",
            "{path}",
            "{lines}",
            "{class_count}",
            "{function_count}",
            "{classes_table}",
            "{functions_table}",
            "{imports_list}",
            "{dependency_diagram}",
            "{see_also}",
        ]:
            assert placeholder in MODULE_TEMPLATE

    def test_command_template_has_expected_placeholders(self) -> None:
        for placeholder in [
            "{title}",
            "{summary}",
            "{usage}",
            "{options_table}",
            "{examples}",
            "{workflow_diagram}",
            "{see_also}",
        ]:
            assert placeholder in COMMAND_TEMPLATE

    def test_config_template_has_expected_placeholders(self) -> None:
        for placeholder in [
            "{title}",
            "{summary}",
            "{options_rows}",
            "{example_config}",
            "{env_vars}",
            "{see_also}",
        ]:
            assert placeholder in CONFIG_TEMPLATE

    def test_types_template_has_expected_placeholders(self) -> None:
        for placeholder in [
            "{title}",
            "{summary}",
            "{type_defs_table}",
            "{enums_table}",
            "{dataclass_details}",
            "{class_diagram}",
            "{see_also}",
        ]:
            assert placeholder in TYPES_TEMPLATE

    def test_api_template_has_expected_placeholders(self) -> None:
        for placeholder in [
            "{title}",
            "{summary}",
            "{endpoints_table}",
            "{schemas}",
            "{authentication}",
            "{see_also}",
        ]:
            assert placeholder in API_TEMPLATE


# ======================================================================
# _relative
# ======================================================================


class TestRelative:
    def test_relative_inside_root(self, tmp_path: Path) -> None:
        child = tmp_path / "sub" / "file.py"
        assert _relative(child, tmp_path) == "sub/file.py"

    def test_relative_outside_root_returns_absolute(self, tmp_path: Path) -> None:
        other = Path("/some/other/path/file.py")
        result = _relative(other, tmp_path)
        assert result == str(other)

    def test_relative_same_as_root(self, tmp_path: Path) -> None:
        # Edge: path is the root itself
        result = _relative(tmp_path, tmp_path)
        assert result == "."


# ======================================================================
# _module_title
# ======================================================================


class TestModuleTitle:
    def test_simple_module(self, tmp_path: Path) -> None:
        path = tmp_path / "zerg" / "launcher.py"
        result = _module_title(path, tmp_path)
        assert result == "zerg.launcher"

    def test_nested_module(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "c.py"
        result = _module_title(path, tmp_path)
        assert result == "a.b.c"

    def test_non_py_file(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        result = _module_title(path, tmp_path)
        assert result == "config.yaml"


# ======================================================================
# _count_lines
# ======================================================================


class TestCountLines:
    def test_count_lines_normal(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")
        assert _count_lines(f) == 3

    def test_count_lines_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        assert _count_lines(f) == 0

    def test_count_lines_missing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.py"
        assert _count_lines(f) == 0

    def test_count_lines_single_line_no_newline(self, tmp_path: Path) -> None:
        f = tmp_path / "single.py"
        f.write_text("x = 1", encoding="utf-8")
        assert _count_lines(f) == 1


# ======================================================================
# _build_classes_table
# ======================================================================


class TestBuildClassesTable:
    def test_empty_classes(self) -> None:
        result = _build_classes_table([])
        assert result == "_No classes defined._"

    def test_single_class_no_bases_no_docstring(self) -> None:
        cls = _make_class("Foo")
        result = _build_classes_table([cls])
        assert "| `Foo` |" in result
        assert "| - |" in result  # bases
        assert "| 0 |" in result  # methods count

    def test_single_class_with_bases_and_docstring(self) -> None:
        cls = _make_class("Dog", bases=["Animal", "Pet"], docstring="A good boy.\nMore details.")
        result = _build_classes_table([cls])
        assert "Animal, Pet" in result
        assert "A good boy." in result
        # Multi-line docstring should only show first line
        assert "More details." not in result

    def test_class_with_methods(self) -> None:
        methods = [_make_method("bark"), _make_method("fetch")]
        cls = _make_class("Dog", methods=methods)
        result = _build_classes_table([cls])
        assert "| 2 |" in result

    def test_multiple_classes(self) -> None:
        classes = [_make_class("A"), _make_class("B"), _make_class("C")]
        result = _build_classes_table(classes)
        assert "`A`" in result
        assert "`B`" in result
        assert "`C`" in result

    def test_class_docstring_truncated_at_80_chars(self) -> None:
        long_doc = "x" * 100
        cls = _make_class("Long", docstring=long_doc)
        result = _build_classes_table([cls])
        # The desc should be truncated to 80 chars
        assert "x" * 80 in result
        assert "x" * 81 not in result


# ======================================================================
# _build_functions_table
# ======================================================================


class TestBuildFunctionsTable:
    def test_empty_functions(self) -> None:
        result = _build_functions_table([])
        assert result == "_No module-level functions defined._"

    def test_single_function_no_args_no_return(self) -> None:
        fn = _make_function("do_stuff")
        result = _build_functions_table([fn])
        assert "| `do_stuff` |" in result
        assert "| `-` |" in result  # args
        assert "| `-` |" in result  # return type

    def test_function_with_args_and_return(self) -> None:
        fn = _make_function("add", args=["a: int", "b: int"], return_type="int", docstring="Add two numbers.")
        result = _build_functions_table([fn])
        assert "a: int, b: int" in result
        assert "`int`" in result
        assert "Add two numbers." in result

    def test_function_docstring_truncated(self) -> None:
        fn = _make_function("f", docstring="y" * 100)
        result = _build_functions_table([fn])
        assert "y" * 80 in result
        assert "y" * 81 not in result

    def test_multiple_functions(self) -> None:
        fns = [_make_function("a"), _make_function("b")]
        result = _build_functions_table(fns)
        assert "`a`" in result
        assert "`b`" in result


# ======================================================================
# _build_imports_list
# ======================================================================


class TestBuildImportsList:
    def test_empty_imports(self) -> None:
        assert _build_imports_list([]) == "_No imports._"

    def test_regular_import(self) -> None:
        imp = _make_import("os")
        result = _build_imports_list([imp])
        assert "- `import os`" in result

    def test_from_import(self) -> None:
        imp = ImportInfo(module="pathlib", names=["Path", "PurePath"], is_from=True)
        result = _build_imports_list([imp])
        assert "- `from pathlib import Path, PurePath`" in result

    def test_mixed_imports(self) -> None:
        imports = [
            _make_import("os"),
            ImportInfo(module="sys", names=["argv"], is_from=True),
        ]
        result = _build_imports_list(imports)
        assert "import os" in result
        assert "from sys import argv" in result


# ======================================================================
# _build_dependency_diagram
# ======================================================================


class TestBuildDependencyDiagram:
    def test_no_imports(self) -> None:
        result = _build_dependency_diagram("my_module", [])
        assert "my_module" in result
        assert "-->" not in result

    def test_with_imports(self) -> None:
        imports = [_make_import("os"), _make_import("sys")]
        result = _build_dependency_diagram("my_mod", imports)
        assert "-->" in result
        assert '"os"' in result
        assert '"sys"' in result

    def test_import_with_none_module(self) -> None:
        imp = ImportInfo(module="", names=["x"], is_from=True)
        # module is empty string, so imp.module or "unknown" -> "unknown"
        # Actually empty string is falsy, so it becomes "unknown"
        result = _build_dependency_diagram("mod", [imp])
        assert '"unknown"' in result


# ======================================================================
# _mermaid_id
# ======================================================================


class TestMermaidId:
    def test_simple_name(self) -> None:
        assert _mermaid_id("mymodule") == "mymodule"

    def test_dots_replaced(self) -> None:
        assert _mermaid_id("zerg.launcher") == "zerg_launcher"

    def test_slashes_replaced(self) -> None:
        assert _mermaid_id("a/b/c") == "a_b_c"

    def test_special_chars_replaced(self) -> None:
        assert _mermaid_id("a-b@c!d") == "a_b_c_d"

    def test_underscores_preserved(self) -> None:
        assert _mermaid_id("my_module") == "my_module"


# ======================================================================
# _build_type_defs_table
# ======================================================================


class TestBuildTypeDefsTable:
    def test_no_aliases_no_constants(self, tmp_path: Path) -> None:
        symbols = _make_symbol_table(tmp_path / "t.py")
        result = _build_type_defs_table(symbols)
        assert result == "_No type aliases or constants defined._"

    def test_with_type_aliases(self, tmp_path: Path) -> None:
        symbols = _make_symbol_table(tmp_path / "t.py", type_aliases=["MyType", "OtherType"])
        result = _build_type_defs_table(symbols)
        assert "| `MyType` | TypeAlias |" in result
        assert "| `OtherType` | TypeAlias |" in result

    def test_with_constants(self, tmp_path: Path) -> None:
        symbols = _make_symbol_table(tmp_path / "t.py", constants=["MAX_SIZE", "TIMEOUT"])
        result = _build_type_defs_table(symbols)
        assert "| `MAX_SIZE` | Constant |" in result
        assert "| `TIMEOUT` | Constant |" in result

    def test_with_both(self, tmp_path: Path) -> None:
        symbols = _make_symbol_table(tmp_path / "t.py", type_aliases=["Alias"], constants=["CONST"])
        result = _build_type_defs_table(symbols)
        assert "TypeAlias" in result
        assert "Constant" in result


# ======================================================================
# _build_enums_table
# ======================================================================


class TestBuildEnumsTable:
    def test_no_enums(self) -> None:
        classes = [_make_class("Foo", bases=["object"])]
        result = _build_enums_table(classes)
        assert result == "_No enums defined._"

    def test_empty_classes(self) -> None:
        assert _build_enums_table([]) == "_No enums defined._"

    def test_with_enum(self) -> None:
        cls = _make_class(
            "Color",
            bases=["Enum"],
            methods=[_make_method("red"), _make_method("green")],
        )
        result = _build_enums_table([cls])
        assert "| `Color` |" in result
        assert "Enum" in result
        assert "2 methods" in result

    def test_enum_with_str_enum(self) -> None:
        cls = _make_class("Status", bases=["str", "Enum"])
        result = _build_enums_table([cls])
        assert "| `Status` |" in result

    def test_mixed_classes_only_enums_shown(self) -> None:
        enum_cls = _make_class("Color", bases=["Enum"])
        regular_cls = _make_class("Config", bases=["object"])
        result = _build_enums_table([enum_cls, regular_cls])
        assert "Color" in result
        assert "Config" not in result


# ======================================================================
# _build_dataclass_details
# ======================================================================


class TestBuildDataclassDetails:
    def test_no_dataclasses(self) -> None:
        classes = [_make_class("Foo", decorators=["staticmethod"])]
        result = _build_dataclass_details(classes)
        assert result == "_No dataclasses or TypedDicts defined._"

    def test_empty_classes(self) -> None:
        assert _build_dataclass_details([]) == "_No dataclasses or TypedDicts defined._"

    def test_with_dataclass(self) -> None:
        methods = [_make_method("__init__", args=["self", "x: int"])]
        cls = _make_class("Point", decorators=["dataclass"], docstring="A 2D point.", methods=methods)
        result = _build_dataclass_details([cls])
        assert "### Point" in result
        assert "A 2D point." in result
        assert "`__init__(" in result

    def test_dataclass_no_docstring(self) -> None:
        cls = _make_class("Bare", decorators=["dataclass"])
        result = _build_dataclass_details([cls])
        assert "### Bare" in result
        assert "-" in result  # fallback for no docstring

    def test_multiple_dataclasses(self) -> None:
        dc1 = _make_class("A", decorators=["dataclass"])
        dc2 = _make_class("B", decorators=["dataclass"])
        result = _build_dataclass_details([dc1, dc2])
        assert "### A" in result
        assert "### B" in result


# ======================================================================
# _build_class_diagram
# ======================================================================


class TestBuildClassDiagram:
    def test_empty_classes(self) -> None:
        assert _build_class_diagram([]) == "    class Empty"

    def test_single_class_no_bases(self) -> None:
        cls = _make_class("Foo")
        result = _build_class_diagram([cls])
        assert "    class Foo" in result
        assert "<|--" not in result

    def test_class_with_base(self) -> None:
        cls = _make_class("Dog", bases=["Animal"])
        result = _build_class_diagram([cls])
        assert "    class Dog" in result
        assert "    Animal <|-- Dog" in result

    def test_class_with_special_base_name(self) -> None:
        cls = _make_class("Sub", bases=["some.module.Base"])
        result = _build_class_diagram([cls])
        # Dots should be replaced with underscores
        assert "some_module_Base <|-- Sub" in result

    def test_multiple_classes(self) -> None:
        classes = [
            _make_class("Base"),
            _make_class("Child", bases=["Base"]),
        ]
        result = _build_class_diagram(classes)
        assert "class Base" in result
        assert "class Child" in result
        assert "Base <|-- Child" in result


# ======================================================================
# _build_endpoints_table
# ======================================================================


class TestBuildEndpointsTable:
    def test_empty_functions(self) -> None:
        assert _build_endpoints_table([]) == "_No endpoints defined._"

    def test_single_endpoint(self) -> None:
        fn = _make_function(
            "health",
            args=["request"],
            return_type="Response",
            decorators=["app.route('/health')"],
        )
        result = _build_endpoints_table([fn])
        assert "| `health` |" in result
        assert "app.route('/health')" in result
        assert "`request`" in result
        assert "`Response`" in result

    def test_endpoint_no_decorators_no_args(self) -> None:
        fn = _make_function("index")
        result = _build_endpoints_table([fn])
        assert "| `-` |" in result  # decorators
        assert "| `-` |" in result  # args

    def test_endpoint_no_return_type(self) -> None:
        fn = _make_function("void_handler", return_type=None)
        result = _build_endpoints_table([fn])
        assert "| `-` |" in result


# ======================================================================
# Markdown extraction helpers
# ======================================================================


class TestExtractMdTitle:
    def test_extract_h1(self) -> None:
        assert _extract_md_title("# My Title\n\nSome text.") == "My Title"

    def test_no_h1(self) -> None:
        assert _extract_md_title("## Subtitle\n\nText.") is None

    def test_h2_not_confused_with_h1(self) -> None:
        assert _extract_md_title("## Not H1\n# Actual H1") == "Actual H1"

    def test_empty_text(self) -> None:
        assert _extract_md_title("") is None

    def test_h1_with_extra_spaces(self) -> None:
        assert _extract_md_title("#   Spaced Title  \n") == "Spaced Title"

    def test_multiple_h1_returns_first(self) -> None:
        text = "# First\n\n# Second"
        assert _extract_md_title(text) == "First"


class TestExtractMdSummary:
    def test_normal_summary(self) -> None:
        text = "# Title\n\nThis is the summary paragraph.\n\n## Next"
        result = _extract_md_summary(text)
        assert result == "This is the summary paragraph."

    def test_multiline_summary(self) -> None:
        text = "# Title\n\nLine one.\nLine two.\n\n## Next"
        result = _extract_md_summary(text)
        assert result == "Line one. Line two."

    def test_no_title_returns_fallback(self) -> None:
        text = "Just some text without heading."
        result = _extract_md_summary(text)
        assert result == "No summary available."

    def test_title_with_no_paragraph(self) -> None:
        text = "# Title\n\n## Immediately Next"
        result = _extract_md_summary(text)
        assert result == "No summary available."

    def test_title_followed_by_blank_lines_then_paragraph(self) -> None:
        text = "# Title\n\n\n\nParagraph here.\n"
        result = _extract_md_summary(text)
        assert result == "Paragraph here."

    def test_empty_text(self) -> None:
        result = _extract_md_summary("")
        assert result == "No summary available."


class TestExtractMdSection:
    def test_extract_existing_section(self) -> None:
        text = "# Title\n\n## Usage\n\nDo this thing.\n\n## Options\n\nSome options."
        result = _extract_md_section(text, "Usage")
        assert result == "Do this thing."

    def test_extract_last_section(self) -> None:
        text = "# Title\n\n## Options\n\nOption A.\nOption B."
        result = _extract_md_section(text, "Options")
        assert "Option A." in result
        assert "Option B." in result

    def test_nonexistent_section(self) -> None:
        text = "# Title\n\n## Usage\n\nContent."
        result = _extract_md_section(text, "NonExistent")
        assert result is None

    def test_empty_text(self) -> None:
        assert _extract_md_section("", "Usage") is None

    def test_section_with_content_until_next_heading(self) -> None:
        text = "## First\n\nContent A.\n\n## Second\n\nContent B."
        result = _extract_md_section(text, "First")
        assert result == "Content A."


# ======================================================================
# DocRenderer - init and render dispatch
# ======================================================================


class TestDocRendererInit:
    def test_instantiation(self, tmp_path: Path) -> None:
        renderer = DocRenderer(project_root=tmp_path)
        assert renderer._root == tmp_path

    def test_root_converted_to_path(self) -> None:
        renderer = DocRenderer(project_root="/tmp")
        assert isinstance(renderer._root, Path)


class TestDocRendererDispatch:
    """Test the render() method's component type dispatch logic."""

    def test_render_autodetect_module(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text('"""Mod doc."""\nx = 1\n', encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f)
        assert "Module Info" in md

    def test_render_override_module(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("x = 1\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f, component_type="MODULE")
        assert "Module Info" in md

    def test_render_override_case_insensitive(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("x = 1\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f, component_type="module")
        assert "Module Info" in md

    def test_render_override_types(self, tmp_path: Path) -> None:
        f = tmp_path / "types.py"
        f.write_text("class A:\n    pass\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f, component_type="TYPES")
        assert "(Types)" in md

    def test_render_override_api(self, tmp_path: Path) -> None:
        f = tmp_path / "api.py"
        f.write_text("def health():\n    pass\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f, component_type="API")
        assert "(API)" in md

    def test_render_command(self, tmp_path: Path) -> None:
        cmd_dir = tmp_path / "data" / "commands"
        cmd_dir.mkdir(parents=True)
        f = cmd_dir / "run.md"
        f.write_text("# Run\n\nExecute things.\n\n## Usage\n\nrun it\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f)
        assert "Run" in md
        assert "Usage" in md

    def test_render_config(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("key: value\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f)
        assert "Configuration:" in md

    def test_render_fallback_unknown_type(self, tmp_path: Path) -> None:
        """If detect returns an unknown ComponentType, fallback to module rendering."""
        f = tmp_path / "mod.py"
        f.write_text("x = 1\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        # Patch detector to return a value not covered by the if-chain
        # We need to create a scenario where none of the if branches match.
        # Since all ComponentType values are covered, we mock the detector.
        with patch.object(renderer, "_detector") as mock_det:
            mock_det.detect.return_value = MagicMock()
            with patch.object(renderer, "_extractor") as mock_ext:
                mock_ext.extract.return_value = _make_symbol_table(f)
                md = renderer.render(f)
                assert "Module Info" in md

    def test_render_invalid_component_type_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("x = 1\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        with pytest.raises(KeyError):
            renderer.render(f, component_type="INVALID")


# ======================================================================
# DocRenderer.render_module
# ======================================================================


class TestRenderModule:
    def test_render_module_full(self, tmp_path: Path) -> None:
        f = tmp_path / "mymod.py"
        f.write_text("# 10 lines\n" * 10, encoding="utf-8")
        symbols = _make_symbol_table(
            f,
            module_docstring="My module.",
            classes=[_make_class("Foo", bases=["Bar"], docstring="A foo.")],
            functions=[_make_function("do", args=["x: int"], return_type="str", docstring="Do it.")],
            imports=[_make_import("os"), ImportInfo(module="sys", names=["argv"], is_from=True)],
        )
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_module(symbols)

        assert "mymod" in md
        assert "My module." in md
        assert "Foo" in md
        assert "do" in md
        assert "import os" in md
        assert "from sys import argv" in md
        assert "See Also" in md
        assert "10" in md  # lines count

    def test_render_module_no_docstring(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("", encoding="utf-8")
        symbols = _make_symbol_table(f, module_docstring=None)
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_module(symbols)
        assert "No module docstring." in md

    def test_render_module_empty_classes_and_functions(self, tmp_path: Path) -> None:
        f = tmp_path / "mod.py"
        f.write_text("", encoding="utf-8")
        symbols = _make_symbol_table(f)
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_module(symbols)
        assert "_No classes defined._" in md
        assert "_No module-level functions defined._" in md


# ======================================================================
# DocRenderer.render_command
# ======================================================================


class TestRenderCommand:
    def test_render_command_full(self, tmp_path: Path) -> None:
        f = tmp_path / "run.md"
        f.write_text(
            "# Run\n\nExecute the run.\n\n## Usage\n\nrun [opts]\n\n"
            "## Options\n\n| Flag | Desc |\n\n## Examples\n\n```bash\nrun\n```\n",
            encoding="utf-8",
        )
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_command(f)
        assert "Run" in md
        assert "Execute the run." in md
        assert "run [opts]" in md
        assert "Flag" in md

    def test_render_command_no_title(self, tmp_path: Path) -> None:
        f = tmp_path / "bare.md"
        f.write_text("No heading here, just text.\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_command(f)
        # Falls back to stem
        assert "bare" in md

    def test_render_command_missing_sections(self, tmp_path: Path) -> None:
        f = tmp_path / "minimal.md"
        f.write_text("# Minimal\n\nJust a command.\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_command(f)
        assert "Minimal" in md
        assert "_No options documented._" in md
        assert "_No examples documented._" in md

    def test_render_command_usage_fallback(self, tmp_path: Path) -> None:
        f = tmp_path / "cmd.md"
        f.write_text("# MyCmd\n\nDescription.\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_command(f)
        # Usage falls back to title
        assert "MyCmd" in md


# ======================================================================
# DocRenderer.render_config
# ======================================================================


class TestRenderConfig:
    def test_render_config_basic(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("key: value\nother: 42\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_config(f)
        assert "Configuration: config.yaml" in md
        assert "key: value" in md
        assert "other: 42" in md
        assert "See Also" in md

    def test_render_config_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_config(f)
        assert "# empty" in md

    def test_render_config_truncates_long_content(self, tmp_path: Path) -> None:
        f = tmp_path / "big.yaml"
        f.write_text("x" * 3000, encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_config(f)
        # Template uses text[:2000]
        assert "x" * 2000 in md
        # Should not contain more than 2000 x chars in the config block
        # (there may be other text around it, so just check it's truncated)
        config_section = md.split("```yaml")[1].split("```")[0]
        assert len(config_section.strip()) == 2000


# ======================================================================
# DocRenderer.render_types
# ======================================================================


class TestRenderTypes:
    def test_render_types_full(self, tmp_path: Path) -> None:
        f = tmp_path / "types.py"
        f.write_text("", encoding="utf-8")
        symbols = _make_symbol_table(
            f,
            module_docstring="Type defs.",
            classes=[
                _make_class("Color", bases=["Enum"], decorators=[]),
                _make_class(
                    "Point",
                    bases=[],
                    decorators=["dataclass"],
                    docstring="A point.",
                    methods=[_make_method("__init__", args=["self", "x: int"])],
                ),
            ],
            type_aliases=["MyAlias"],
            constants=["MAX"],
        )
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_types(symbols)

        assert "(Types)" in md
        assert "Type defs." in md
        assert "Color" in md
        assert "Point" in md
        assert "MyAlias" in md

    def test_render_types_no_docstring(self, tmp_path: Path) -> None:
        f = tmp_path / "types.py"
        f.write_text("", encoding="utf-8")
        symbols = _make_symbol_table(f, module_docstring=None)
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_types(symbols)
        assert "Type definitions module." in md


# ======================================================================
# DocRenderer.render_api
# ======================================================================


class TestRenderApi:
    def test_render_api_full(self, tmp_path: Path) -> None:
        f = tmp_path / "api.py"
        f.write_text("", encoding="utf-8")
        symbols = _make_symbol_table(
            f,
            module_docstring="API endpoints.",
            functions=[
                _make_function("health", decorators=["app.route('/health')"], return_type="str"),
                _make_function("login", args=["request"], decorators=["app.route('/login', methods=['POST'])"]),
            ],
        )
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_api(symbols)

        assert "(API)" in md
        assert "API endpoints." in md
        assert "health" in md
        assert "login" in md
        assert "Schema extraction not yet implemented" in md
        assert "Authentication details not yet extracted" in md

    def test_render_api_no_docstring(self, tmp_path: Path) -> None:
        f = tmp_path / "api.py"
        f.write_text("", encoding="utf-8")
        symbols = _make_symbol_table(f, module_docstring=None)
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_api(symbols)
        assert "API endpoint definitions." in md

    def test_render_api_no_endpoints(self, tmp_path: Path) -> None:
        f = tmp_path / "api.py"
        f.write_text("", encoding="utf-8")
        symbols = _make_symbol_table(f, functions=[])
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render_api(symbols)
        assert "_No endpoints defined._" in md


# ======================================================================
# Integration: DocRenderer.render with real files
# ======================================================================


class TestDocRendererIntegration:
    def test_render_real_python_module(self, tmp_path: Path) -> None:
        f = tmp_path / "real.py"
        f.write_text(
            '"""Real module."""\n\nimport os\nfrom pathlib import Path\n\n'
            'MAX = 10\n\nclass Foo:\n    """A foo."""\n    def bar(self) -> None:\n'
            '        pass\n\ndef baz(x: int) -> str:\n    """Baz it."""\n    return str(x)\n',
            encoding="utf-8",
        )
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f)
        assert "real" in md
        assert "Real module." in md
        assert "Foo" in md
        assert "baz" in md
        assert "import os" in md
        assert "mermaid" in md

    def test_render_types_py_integration(self, tmp_path: Path) -> None:
        f = tmp_path / "types.py"
        f.write_text(
            '"""Types."""\n\nfrom enum import Enum\n\nclass Color(Enum):\n    RED = 1\n',
            encoding="utf-8",
        )
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f)
        assert "(Types)" in md
        assert "Color" in md

    def test_render_depth_parameter_accepted(self, tmp_path: Path) -> None:
        """depth param is reserved for future use but should not error."""
        f = tmp_path / "mod.py"
        f.write_text("x = 1\n", encoding="utf-8")
        renderer = DocRenderer(project_root=tmp_path)
        md = renderer.render(f, depth="deep")
        assert isinstance(md, str)
