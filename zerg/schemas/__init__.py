"""ZERG JSON schemas for validation."""

from pathlib import Path

SCHEMAS_DIR = Path(__file__).parent


def get_schema_path(schema_name: str) -> Path:
    """Get the path to a schema file.

    Args:
        schema_name: Name of the schema (without .json extension)

    Returns:
        Path to the schema file
    """
    return SCHEMAS_DIR / f"{schema_name}.json"
