from __future__ import annotations

from patent_client_agents.shared.corpus.outline.models import (
    OutlineSearchHit,
    OutlineSearchResponse,
    OutlineSection,
    OutlineVersion,
)


class UpGuidelinesSearchHit(OutlineSearchHit):
    pass


class UpGuidelinesSearchResponse(OutlineSearchResponse):
    hits: list[UpGuidelinesSearchHit]


class UpGuidelinesSection(OutlineSection):
    pass


class UpGuidelinesVersion(OutlineVersion):
    pass
