from __future__ import annotations

from pydantic import Field

from patent_client_agents.shared.corpus.outline.models import (
    OutlineSearchHit,
    OutlineSearchResponse,
    OutlineSection,
    OutlineVersion,
)


class MpepSearchHit(OutlineSearchHit):
    pass


class MpepSearchResponse(OutlineSearchResponse):
    hits: list[MpepSearchHit]


class MpepSection(OutlineSection):
    source_url: str | None = None
    content_sha256: str | None = None
    section_revision: str | None = None
    corpus_metadata: dict[str, str | None] = Field(default_factory=dict)


class MpepVersion(OutlineVersion):
    pass
