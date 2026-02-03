"""Tests for ZERG JS/TS repo map extractor."""

import textwrap
from pathlib import Path

from zerg.repo_map_js import extract_js_file, extract_js_symbols


class TestExtractJSSymbols:
    """Tests for extract_js_symbols."""

    def test_function_declaration(self) -> None:
        source = "function hello(name) {\n  return name;\n}\n"
        symbols = extract_js_symbols(source)
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "hello"
        assert "function hello(name)" in funcs[0].signature

    def test_export_function(self) -> None:
        source = "export function greet(name) {\n  return name;\n}\n"
        symbols = extract_js_symbols(source)
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "greet"

    def test_async_function(self) -> None:
        source = "export async function fetchData(url) {\n  return url;\n}\n"
        symbols = extract_js_symbols(source)
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "fetchData"

    def test_arrow_function_export(self) -> None:
        source = "export const handler = (req, res) => {\n  res.send('ok');\n};\n"
        symbols = extract_js_symbols(source)
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) == 1
        assert funcs[0].name == "handler"

    def test_class_declaration(self) -> None:
        source = "export class MyService extends BaseService {\n  constructor() {}\n}\n"
        symbols = extract_js_symbols(source)
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "MyService"
        assert "extends BaseService" in classes[0].signature

    def test_import_named(self) -> None:
        source = "import { Router, Request } from 'express';\n"
        symbols = extract_js_symbols(source)
        imports = [s for s in symbols if s.kind == "import"]
        assert len(imports) == 2
        names = {s.name for s in imports}
        assert names == {"Router", "Request"}

    def test_import_default(self) -> None:
        source = "import React from 'react';\n"
        symbols = extract_js_symbols(source)
        imports = [s for s in symbols if s.kind == "import"]
        assert len(imports) == 1
        assert imports[0].name == "React"

    def test_interface_declaration(self) -> None:
        source = "export interface UserConfig extends BaseConfig {\n  name: string;\n}\n"
        symbols = extract_js_symbols(source)
        interfaces = [s for s in symbols if s.name == "UserConfig"]
        assert len(interfaces) == 1
        assert "interface UserConfig" in interfaces[0].signature

    def test_type_alias(self) -> None:
        source = "export type Status = 'active' | 'inactive';\n"
        symbols = extract_js_symbols(source)
        types = [s for s in symbols if s.name == "Status"]
        assert len(types) == 1
        assert "type Status" in types[0].signature

    def test_variable_export(self) -> None:
        source = "export const MAX_SIZE: number = 100;\n"
        symbols = extract_js_symbols(source)
        vars_ = [s for s in symbols if s.kind == "variable" and s.name == "MAX_SIZE"]
        assert len(vars_) == 1

    def test_mixed_file(self) -> None:
        source = textwrap.dedent("""\
            import { Router } from 'express';

            export interface Config {
              port: number;
            }

            export class Server extends BaseServer {
              constructor() {}
            }

            export function start(config) {
              return new Server(config);
            }

            export const DEFAULT_PORT = 3000;
        """)
        symbols = extract_js_symbols(source)
        kinds = {s.kind for s in symbols}
        assert "import" in kinds
        assert "class" in kinds
        assert "function" in kinds
        assert "variable" in kinds


class TestExtractJSFile:
    """Tests for extract_js_file."""

    def test_extract_from_file(self, tmp_path: Path) -> None:
        filepath = tmp_path / "test.js"
        filepath.write_text("export function foo() {}\n")

        symbols = extract_js_file(filepath)
        assert len(symbols) >= 1

    def test_nonexistent_file(self) -> None:
        symbols = extract_js_file("/nonexistent/path.js")
        assert symbols == []

    def test_ts_file(self, tmp_path: Path) -> None:
        filepath = tmp_path / "test.ts"
        filepath.write_text("export interface Foo { bar: string; }\n")

        symbols = extract_js_file(filepath)
        assert len(symbols) >= 1
