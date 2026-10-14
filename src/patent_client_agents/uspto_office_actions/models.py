"""Pydantic models for USPTO Dataset API office action endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from patent_client_agents.shared.models import ApiModel


class OfficeActionRejection(ApiModel):
    """A single office action rejection record."""

    id: str = ""
    patent_application_number: str = ""
    legal_section_code: str = ""
    action_type_category: str = ""
    legacy_document_code_identifier: str = ""
    submission_date: str = ""
    group_art_unit_number: str = ""
    national_class: str = ""
    national_subclass: str = ""
    claim_number_array_document: list[str] = Field(default_factory=list)
    has_rej_101: int = 0
    has_rej_102: int = 0
    has_rej_103: int = 0
    has_rej_112: int = 0
    has_rej_dp: int = Field(0, alias="hasRejDP")
    cite_103_max: int = 0
    cite_103_eq1: int = Field(0, alias="cite103EQ1")
    cite_103_gt3: int = Field(0, alias="cite103GT3")
    allowed_claim_indicator: bool = False
    alice_indicator: bool = False
    bilski_indicator: bool = False
    mayo_indicator: bool = False
    myriad_indicator: bool = False
    closing_missing: int = 0
    header_missing: int = 0
    form_paragraph_missing: int = 0
    reject_form_mismatch: int = Field(0, alias="rejectFormMissmatch")
    paragraph_number: str = ""

    model_config = {"populate_by_name": True, "extra": "allow"}


class OfficeActionCitation(ApiModel):
    """A single office action citation record."""

    id: str = ""
    patent_application_number: str = ""
    reference_identifier: str = ""
    parsed_reference_identifier: str = ""
    legal_section_code: str = ""
    action_type_category: str = ""
    group_art_unit_number: str = ""
    tech_center: str = ""
    work_group: str = ""
    paragraph_number: str = ""
    examiner_cited_reference_indicator: bool = False
    applicant_cited_examiner_reference_indicator: bool = False
    office_action_citation_reference_indicator: bool = False

    model_config = {"populate_by_name": True, "extra": "allow"}


def _coerce_str(v: Any) -> str:
    """Coerce Solr values to str — handles lists, ints, etc."""
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v) if v is not None else ""


class OfficeActionText(ApiModel):
    """A single office action text record.

    The oa_actions Solr endpoint returns many scalar fields as single-element
    lists (e.g. ``["CTNF"]`` instead of ``"CTNF"``). Validators coerce these.
    """

    id: str = ""
    patent_application_number: str = ""
    submission_date: str = ""
    legacy_document_code_identifier: str = ""
    body_text: list[str] = Field(default_factory=list)
    invention_title: str = ""
    application_status_number: int = 0
    filing_date: str = ""
    grant_date: str = ""
    patent_number: str = ""
    group_art_unit_number: str = ""
    national_class: list[str] = Field(default_factory=list)
    work_group: list[str] = Field(default_factory=list)
    customer_number: int | None = None
    application_type_category: str = ""
    sections: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator(
        "patent_application_number",
        "submission_date",
        "legacy_document_code_identifier",
        "invention_title",
        "filing_date",
        "grant_date",
        "patent_number",
        "group_art_unit_number",
        "application_type_category",
        mode="before",
    )
    @classmethod
    def _coerce_solr_str(cls, v: Any) -> str:
        return _coerce_str(v)

    model_config = {"populate_by_name": True, "extra": "allow"}


class EnrichedCitation(ApiModel):
    """A single enriched citation metadata record."""

    id: str = ""
    patent_application_number: str = ""
    cited_document_identifier: str = ""
    publication_number: str = ""
    inventor_name_text: str = ""
    kind_code: str = ""
    country_code: str = ""
    office_action_date: str = ""
    office_action_category: str = ""
    citation_category_code: str = ""
    related_claim_number_text: str = ""
    passage_location_text: list[str] = Field(default_factory=list)
    quality_summary_text: str = ""
    group_art_unit_number: str = ""
    tech_center: str = ""
    work_group_number: str = ""
    npl_indicator: bool = False
    examiner_cited_reference_indicator: bool = False
    applicant_cited_examiner_reference_indicator: bool = False

    model_config = {"populate_by_name": True, "extra": "allow"}


class DatasetApiResponse(ApiModel):
    """Standard response from USPTO Dataset API endpoints."""

    num_found: int = 0
    start: int = 0
    docs: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "allow"}


class RejectionSearchResponse(BaseModel):
    """Response from office action rejections search."""

    num_found: int = 0
    start: int = 0
    results: list[OfficeActionRejection] = Field(default_factory=list)


class CitationSearchResponse(BaseModel):
    """Response from office action citations search."""

    num_found: int = 0
    start: int = 0
    results: list[OfficeActionCitation] = Field(default_factory=list)


class OfficeActionTextSearchResponse(BaseModel):
    """Response from office action text search."""

    num_found: int = 0
    start: int = 0
    results: list[OfficeActionText] = Field(default_factory=list)


class EnrichedCitationSearchResponse(BaseModel):
    """Response from enriched citations search."""

    num_found: int = 0
    start: int = 0
    results: list[EnrichedCitation] = Field(default_factory=list)


__all__ = [
    "DatasetApiResponse",
    "OfficeActionRejection",
    "OfficeActionCitation",
    "OfficeActionText",
    "EnrichedCitation",
    "RejectionSearchResponse",
    "CitationSearchResponse",
    "OfficeActionTextSearchResponse",
    "EnrichedCitationSearchResponse",
]
