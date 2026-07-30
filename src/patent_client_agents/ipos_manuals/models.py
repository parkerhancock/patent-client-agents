"""Pydantic models for the IPOS Singapore work-manual corpus."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IposManual(BaseModel):
    """A single IPOS work / examination manual in the corpus."""

    manual: str = Field(
        description=(
            "Stable lowercase key — one of 'peg' (Patent Examination "
            "Guidelines), 'tm' (Trade Marks Work Manual), 'designs' "
            "(Industrial Designs Work Manual)."
        )
    )
    short_name: str = Field(description="Citation-ready short name, e.g. 'PEG', 'TM Work Manual'.")
    title: str = Field(description="Full official title.")
    source_url: str = Field(description="IPOS URL for the manual PDF.")
    source_version: str | None = Field(default=None)


class IposManualSection(BaseModel):
    """A single section of an IPOS manual, with full text."""

    manual: str
    short_name: str
    manual_title: str
    section_label: str = Field(
        description="Section label as it appears upstream, e.g. '1.5.3', '4.A.2'."
    )
    title: str | None = None
    breadcrumb: str | None = None
    source_url: str
    source_version: str | None = None
    text: str


class IposManualSearchHit(BaseModel):
    manual: str
    short_name: str
    section_label: str
    title: str | None = None
    breadcrumb: str | None = None
    snippet: str = Field(
        description=("FTS5-rendered snippet with <mark>...</mark> tags around the matched terms.")
    )
    rank: float | None = Field(
        default=None,
        description="BM25 rank score (lower = more relevant) when sort='relevance'.",
    )


class IposManualSearchResponse(BaseModel):
    query: str
    hits: list[IposManualSearchHit]
    page: int
    per_page: int
    has_more: bool


class IposManualsCorpusMeta(BaseModel):
    schema_version: int
    snapshot_date: str | None = None
    section_count: int
    manual_count: int
    source_version: str | None = None
