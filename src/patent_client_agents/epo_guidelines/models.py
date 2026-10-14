from __future__ import annotations

from patent_client_agents.shared.corpus.outline.models import (
    OutlineSearchHit,
    OutlineSearchResponse,
    OutlineSection,
    OutlineVersion,
)


class GuidelinesSearchHit(OutlineSearchHit):
    pass


class GuidelinesSearchResponse(OutlineSearchResponse):
    hits: list[GuidelinesSearchHit]


class GuidelinesSection(OutlineSection):
    pass


class GuidelinesVersion(OutlineVersion):
    pass
