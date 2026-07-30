"""Resource helpers for the INPI Brazil statutes API."""

from __future__ import annotations

from importlib import resources

USAGE_RESOURCE_URI = "resource://inpi_br_statutes/usage"


def get_usage_resource() -> str:
    return (
        resources.files("patent_client_agents.inpi_br_statutes.docs")
        .joinpath("usage.md")
        .read_text(encoding="utf-8")
    )
