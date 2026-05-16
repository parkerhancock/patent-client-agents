"""Pydantic models for the IPOS Singapore statutes corpus."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IposStatute(BaseModel):
    """A single Singapore IP Act carried by the corpus."""

    statute: str = Field(
        description=(
            "Stable lowercase key — one of 'patents', 'tm', 'designs', "
            "'copyright'. 'tm' covers the Trade Marks Act 1998; 'designs' "
            "covers the Registered Designs Act 2000."
        )
    )
    short_name: str = Field(
        description=(
            "Citation-ready short name, e.g. 'Patents Act', 'Trade Marks "
            "Act', 'Registered Designs Act', 'Copyright Act'."
        )
    )
    title: str = Field(description="Full official title (revised-edition aware).")
    source_url: str = Field(
        description="Singapore Statutes Online URL for the in-force consolidation."
    )
    source_version: str | None = Field(
        default=None,
        description=(
            "Vendor-style version label when stamped at build time — e.g. "
            "'2020 Revised Edition'. ``None`` when the build script did "
            "not record a discrete version label."
        ),
    )


class IposSection(BaseModel):
    """A single section of a Singapore IP Act, with full text."""

    statute: str
    short_name: str
    statute_title: str
    section_label: str = Field(
        description="Section label as it appears upstream, e.g. '13', '13A', '27(1)'."
    )
    title: str | None = Field(default=None, description="Section heading.")
    breadcrumb: str | None = Field(
        default=None,
        description="Informational breadcrumb, e.g. 'Patents Act › Section 13'.",
    )
    source_url: str
    source_version: str | None = None
    text: str


class IposStatuteSearchHit(BaseModel):
    statute: str
    short_name: str
    section_label: str
    title: str | None = None
    breadcrumb: str | None = None
    snippet: str = Field(
        description=(
            "FTS5-rendered snippet with <mark>...</mark> tags around the "
            "matched terms. Token width tuned to ~200 characters."
        )
    )
    rank: float | None = Field(
        default=None,
        description="BM25 rank score (lower = more relevant) when sort='relevance'.",
    )


class IposStatuteSearchResponse(BaseModel):
    query: str
    hits: list[IposStatuteSearchHit]
    page: int
    per_page: int
    has_more: bool


class IposCorpusMeta(BaseModel):
    schema_version: int
    snapshot_date: str | None = None
    section_count: int
    statute_count: int
    source_version: str | None = None
