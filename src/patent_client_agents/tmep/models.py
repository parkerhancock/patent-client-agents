from __future__ import annotations

from patent_client_agents.shared.corpus.outline.models import (
    OutlineSearchHit,
    OutlineSearchResponse,
    OutlineSection,
    OutlineVersion,
)


class TmepSearchHit(OutlineSearchHit):
    """A single search result from the TMEP."""


class TmepSearchResponse(OutlineSearchResponse):
    """Response from a TMEP search query."""

    hits: list[TmepSearchHit]


class TmepSection(OutlineSection):
    """A section of the TMEP."""


class TmepVersion(OutlineVersion):
    """An available TMEP version."""
