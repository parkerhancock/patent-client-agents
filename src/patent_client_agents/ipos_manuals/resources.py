"""Resource helpers for the IPOS Singapore manuals corpus."""

from __future__ import annotations

from importlib import resources

USAGE_RESOURCE_URI = "resource://ipos_manuals/usage"


def get_usage_resource() -> str:
    return (
        resources.files("patent_client_agents.ipos_manuals.docs")
        .joinpath("usage.md")
        .read_text(encoding="utf-8")
    )
