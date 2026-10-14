"""Helpers for building MCP response envelopes."""

from __future__ import annotations

from typing import Any, cast


def dump(obj: object, **model_dump_kwargs: Any) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict, passing dicts through.

    ``model_dump_kwargs`` go to ``model_dump`` unchanged (e.g. ``by_alias=True``
    for upstream camelCase keys, ``mode="json"`` for ISO dates), so each tool
    keeps the output shape it documents.
    """
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump(**model_dump_kwargs))  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"dump expected a Pydantic model or dict, got {type(obj).__name__}")


def dump_any(obj: object) -> Any:
    """Like :func:`dump`, but also maps over lists and passes other values through."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # ty: ignore[call-non-callable]
    if isinstance(obj, list):
        return [dump_any(item) for item in obj]
    return obj
