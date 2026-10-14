from __future__ import annotations

from patent_client_agents.shared.corpus.outline.models import (
    OutlineSearchHit,
    OutlineSearchResponse,
    OutlineSection,
    OutlineVersion,
)


class PctGuidelinesSearchHit(OutlineSearchHit):
    pass


class PctGuidelinesSearchResponse(OutlineSearchResponse):
    hits: list[PctGuidelinesSearchHit]


class PctGuidelinesSection(OutlineSection):
    pass


class PctGuidelinesVersion(OutlineVersion):
    pass
