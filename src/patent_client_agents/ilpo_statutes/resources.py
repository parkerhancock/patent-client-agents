"""Resource helpers for the ILPO Israel statutes corpus."""

from __future__ import annotations

from importlib import resources

USAGE_RESOURCE_URI = "resource://ilpo_statutes/usage"


def get_usage_resource() -> str:
    return (
        resources.files("patent_client_agents.ilpo_statutes.docs")
        .joinpath("usage.md")
        .read_text(encoding="utf-8")
    )
