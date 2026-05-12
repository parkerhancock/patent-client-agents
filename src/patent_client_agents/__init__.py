"""IP Tools - Intellectual property data tools for AI agents."""

from law_tools_core.logging import configure as _configure_logging

from .unified import (
    PatentPdf,
    build_canonical_claim,
    download_patent_pdf,
    get_patent_claims,
    google_limitations_from_html,
    odp_limitations_from_text,
)

__version__ = "0.8.0"

_configure_logging("patent_client_agents")

__all__ = [
    "PatentPdf",
    "build_canonical_claim",
    "download_patent_pdf",
    "get_patent_claims",
    "google_limitations_from_html",
    "odp_limitations_from_text",
]
