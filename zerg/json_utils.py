"""JSON serialization utilities with optional orjson acceleration.

Provides a unified interface for JSON operations that uses orjson when
available for better performance, falling back to the stdlib json module.

All functions guarantee str return types (never bytes), even when orjson
is the backend (orjson natively returns bytes from dumps).

Install the 'performance' extra to enable orjson:
    pip install zerg[performance]
"""

from __future__ import annotations

from typing import IO, Any

__all__ = ["HAS_ORJSON", "dump", "dumps", "load", "loads"]

try:
    import orjson as _orjson

    HAS_ORJSON: bool = True

    def loads(data: str | bytes) -> Any:
        """Parse a JSON string or bytes object.

        Args:
            data: JSON-encoded string or bytes.

        Returns:
            Deserialized Python object.
        """
        return _orjson.loads(data)

    def dumps(obj: Any, *, indent: bool = False) -> str:
        """Serialize an object to a JSON string.

        Args:
            obj: Object to serialize.
            indent: If True, pretty-print with 2-space indentation.

        Returns:
            JSON-encoded string (always str, never bytes).
        """
        option = _orjson.OPT_INDENT_2 if indent else 0
        return _orjson.dumps(obj, option=option).decode()

    def load(fp: IO[str] | IO[bytes]) -> Any:
        """Deserialize JSON from a file-like object.

        Args:
            fp: File-like object with a .read() method.

        Returns:
            Deserialized Python object.
        """
        return _orjson.loads(fp.read())

    def dump(obj: Any, fp: IO[str], *, indent: bool = False) -> None:
        """Serialize an object as JSON into a file-like object.

        Args:
            obj: Object to serialize.
            fp: File-like object with a .write() method.
            indent: If True, pretty-print with 2-space indentation.
        """
        fp.write(dumps(obj, indent=indent))

except ImportError:
    import json as _json

    HAS_ORJSON = False

    def loads(data: str | bytes) -> Any:  # type: ignore[no-redef]
        """Parse a JSON string or bytes object.

        Args:
            data: JSON-encoded string or bytes.

        Returns:
            Deserialized Python object.
        """
        return _json.loads(data)

    def dumps(obj: Any, *, indent: bool = False) -> str:  # type: ignore[no-redef]
        """Serialize an object to a JSON string.

        Args:
            obj: Object to serialize.
            indent: If True, pretty-print with 2-space indentation.

        Returns:
            JSON-encoded string.
        """
        return _json.dumps(obj, indent=2 if indent else None)

    def load(fp: IO[str] | IO[bytes]) -> Any:  # type: ignore[no-redef]
        """Deserialize JSON from a file-like object.

        Args:
            fp: File-like object with a .read() method.

        Returns:
            Deserialized Python object.
        """
        return _json.load(fp)

    def dump(obj: Any, fp: IO[str], *, indent: bool = False) -> None:  # type: ignore[no-redef]
        """Serialize an object as JSON into a file-like object.

        Args:
            obj: Object to serialize.
            fp: File-like object with a .write() method.
            indent: If True, pretty-print with 2-space indentation.
        """
        _json.dump(obj, fp, indent=2 if indent else None)
