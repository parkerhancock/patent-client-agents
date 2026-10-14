from __future__ import annotations

from patent_client_agents.shared.corpus.outline.models import (
    OutlineSearchHit,
    OutlineSearchResponse,
    OutlineSection,
    OutlineVersion,
)


class EpcSearchHit(OutlineSearchHit):
    pass


class EpcSearchResponse(OutlineSearchResponse):
    hits: list[EpcSearchHit]


class EpcSection(OutlineSection):
    pass


class EpcVersion(OutlineVersion):
    pass
