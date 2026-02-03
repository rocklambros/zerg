"""Integration tests for multi-language project detection."""

from pathlib import Path

from zerg.security_rules import detect_project_stack


class TestMultiLanguageDetection:
    """Test suite for multi-language project stack detection."""

    def test_detect_python_and_node(self, tmp_path: Path) -> None:
        """Detect Python and JavaScript from marker files.

        Creates requirements.txt and package.json, then verifies
        both languages are detected in the project stack.
        """
        # Create Python marker
        (tmp_path / "requirements.txt").write_text("pytest>=7.0\nclick>=8.0\n")
        # Create JavaScript marker
        (tmp_path / "package.json").write_text('{"name": "test", "version": "1.0.0"}')

        stack = detect_project_stack(tmp_path)

        assert "python" in stack.languages, f"Expected 'python' in {stack.languages}"
        assert "javascript" in stack.languages, f"Expected 'javascript' in {stack.languages}"

    def test_detect_go_and_rust(self, tmp_path: Path) -> None:
        """Detect Go and Rust from marker files.

        Creates go.mod and Cargo.toml, then verifies
        both languages are detected in the project stack.
        """
        # Create Go marker
        (tmp_path / "go.mod").write_text("module example.com/test\n\ngo 1.22\n")
        # Create Rust marker
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\nversion = "0.1.0"\n')

        stack = detect_project_stack(tmp_path)

        assert "go" in stack.languages, f"Expected 'go' in {stack.languages}"
        assert "rust" in stack.languages, f"Expected 'rust' in {stack.languages}"
