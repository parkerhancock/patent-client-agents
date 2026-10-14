from __future__ import annotations

from patent_client_agents.shared.corpus.outline.models import (
    OutlineSearchHit,
    OutlineSearchResponse,
    OutlineSection,
    OutlineVersion,
)


class MoppSearchHit(OutlineSearchHit):
    pass


class MoppSearchResponse(OutlineSearchResponse):
    hits: list[MoppSearchHit]


class MoppSection(OutlineSection):
    pass


class MoppVersion(OutlineVersion):
    pass
