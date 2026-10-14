from __future__ import annotations

from patent_client_agents.shared.corpus.outline.models import (
    OutlineSearchHit,
    OutlineSearchResponse,
    OutlineSection,
    OutlineVersion,
)


class CaseLawSearchHit(OutlineSearchHit):
    pass


class CaseLawSearchResponse(OutlineSearchResponse):
    hits: list[CaseLawSearchHit]


class CaseLawSection(OutlineSection):
    pass


class CaseLawVersion(OutlineVersion):
    pass
