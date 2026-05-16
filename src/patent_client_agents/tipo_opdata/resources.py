"""MCP resources for the TIPO OpenData connector.

Stub created in chunk 1 of 4; chunk 3 will flesh out the usage doc per
``research/specs/tw-tipo-connector-spec.md``.
"""

from __future__ import annotations

USAGE_RESOURCE_URI = "pca://tipo_opdata/usage"


def get_usage_resource() -> str:
    """Return the usage resource body for the TIPO OpenData connector."""
    return (
        "TIPO OpenData REST connector — see "
        "research/specs/tw-tipo-connector-spec.md"
    )


__all__ = ["USAGE_RESOURCE_URI", "get_usage_resource"]
