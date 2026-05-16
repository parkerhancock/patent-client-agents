"""Pydantic models for the ILPO Israel statutes corpus."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IlpoStatute(BaseModel):
    """One statute as carried in the corpus catalog."""

    statute: str = Field(
        description=(
            "Stable lowercase key. One of 'patents', 'trademarks', "
            "'designs', 'copyright', or 'commercial_torts' (the last "
            "being Israel's standalone trade-secret statute)."
        )
    )
    section_count: int = Field(description="Number of sections in this statute.")
    source_url: str | None = Field(
        default=None,
        description=("WIPO Lex / gov.il URL the statute was fetched from at corpus-build time."),
    )


class IlpoSection(BaseModel):
    """One section of an Israeli IP statute."""

    statute: str = Field(description="Statute key — see :class:`IlpoStatute`.")
    section_number: str = Field(description="Section number as printed (e.g. '3', '6', '167A').")
    section_label: str = Field(
        description=(
            "Citation-ready label, e.g. 'Section 3 Patents Law' or "
            "'Article 6 Commercial Torts Law' (the Commercial Torts "
            "Law uses 'Article' as its section unit)."
        )
    )
    title: str | None = Field(
        default=None,
        description="Section heading, when one was parsed out.",
    )
    text: str
    source_url: str | None = None


class IlpoSearchHit(BaseModel):
    statute: str
    section_number: str
    section_label: str
    title: str | None = None
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


class IlpoSearchResponse(BaseModel):
    query: str
    hits: list[IlpoSearchHit]
    page: int
    per_page: int
    has_more: bool


class IlpoCorpusMeta(BaseModel):
    schema_version: int
    snapshot_date: str | None = None
    source_version: str | None = None
    section_count: int
