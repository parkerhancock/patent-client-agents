"""Pydantic models for USPTO Dataset API office action endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class OfficeActionRejection(BaseModel):
    """A single office action rejection record."""

    id: str = ""
    patent_application_number: str = Field("", alias="patentApplicationNumber")
    legal_section_code: str = Field("", alias="legalSectionCode")
    action_type_category: str = Field("", alias="actionTypeCategory")
    legacy_document_code_identifier: str = Field("", alias="legacyDocumentCodeIdentifier")
    submission_date: str = Field("", alias="submissionDate")
    group_art_unit_number: str = Field("", alias="groupArtUnitNumber")
    national_class: str = Field("", alias="nationalClass")
    national_subclass: str = Field("", alias="nationalSubclass")
    claim_number_array_document: list[str] = Field(
        default_factory=list, alias="claimNumberArrayDocument"
    )
    has_rej_101: int = Field(0, alias="hasRej101")
    has_rej_102: int = Field(0, alias="hasRej102")
    has_rej_103: int = Field(0, alias="hasRej103")
    has_rej_112: int = Field(0, alias="hasRej112")
    has_rej_dp: int = Field(0, alias="hasRejDP")
    cite_103_max: int = Field(0, alias="cite103Max")
    cite_103_eq1: int = Field(0, alias="cite103EQ1")
    cite_103_gt3: int = Field(0, alias="cite103GT3")
    allowed_claim_indicator: bool = Field(False, alias="allowedClaimIndicator")
    alice_indicator: bool = Field(False, alias="aliceIndicator")
    bilski_indicator: bool = Field(False, alias="bilskiIndicator")
    mayo_indicator: bool = Field(False, alias="mayoIndicator")
    myriad_indicator: bool = Field(False, alias="myriadIndicator")
    closing_missing: int = Field(0, alias="closingMissing")
    header_missing: int = Field(0, alias="headerMissing")
    form_paragraph_missing: int = Field(0, alias="formParagraphMissing")
    reject_form_mismatch: int = Field(0, alias="rejectFormMissmatch")
    paragraph_number: str = Field("", alias="paragraphNumber")

    model_config = {"populate_by_name": True, "extra": "allow"}


class OfficeActionCitation(BaseModel):
    """A single office action citation record."""

    id: str = ""
    patent_application_number: str = Field("", alias="patentApplicationNumber")
    reference_identifier: str = Field("", alias="referenceIdentifier")
    parsed_reference_identifier: str = Field("", alias="parsedReferenceIdentifier")
    legal_section_code: str = Field("", alias="legalSectionCode")
    action_type_category: str = Field("", alias="actionTypeCategory")
    group_art_unit_number: str = Field("", alias="groupArtUnitNumber")
    tech_center: str = Field("", alias="techCenter")
    work_group: str = Field("", alias="workGroup")
    paragraph_number: str = Field("", alias="paragraphNumber")
    examiner_cited_reference_indicator: bool = Field(False, alias="examinerCitedReferenceIndicator")
    applicant_cited_examiner_reference_indicator: bool = Field(
        False, alias="applicantCitedExaminerReferenceIndicator"
    )
    office_action_citation_reference_indicator: bool = Field(
        False, alias="officeActionCitationReferenceIndicator"
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


def _coerce_str(v: Any) -> str:
    """Coerce Solr values to str — handles lists, ints, etc."""
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v) if v is not None else ""


class OfficeActionText(BaseModel):
    """A single office action text record.

    The oa_actions Solr endpoint returns many scalar fields as single-element
    lists (e.g. ``["CTNF"]`` instead of ``"CTNF"``). Validators coerce these.
    """

    id: str = ""
    patent_application_number: str = Field("", alias="patentApplicationNumber")
    submission_date: str = Field("", alias="submissionDate")
    legacy_document_code_identifier: str = Field("", alias="legacyDocumentCodeIdentifier")
    body_text: list[str] = Field(default_factory=list, alias="bodyText")
    invention_title: str = Field("", alias="inventionTitle")
    application_status_number: int = Field(0, alias="applicationStatusNumber")
    filing_date: str = Field("", alias="filingDate")
    grant_date: str = Field("", alias="grantDate")
    patent_number: str = Field("", alias="patentNumber")
    group_art_unit_number: str = Field("", alias="groupArtUnitNumber")
    national_class: list[str] = Field(default_factory=list, alias="nationalClass")
    work_group: list[str] = Field(default_factory=list, alias="workGroup")
    customer_number: int | None = Field(None, alias="customerNumber")
    application_type_category: str = Field("", alias="applicationTypeCategory")
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


class EnrichedCitation(BaseModel):
    """A single enriched citation metadata record."""

    id: str = ""
    patent_application_number: str = Field("", alias="patentApplicationNumber")
    cited_document_identifier: str = Field("", alias="citedDocumentIdentifier")
    publication_number: str = Field("", alias="publicationNumber")
    inventor_name_text: str = Field("", alias="inventorNameText")
    kind_code: str = Field("", alias="kindCode")
    country_code: str = Field("", alias="countryCode")
    office_action_date: str = Field("", alias="officeActionDate")
    office_action_category: str = Field("", alias="officeActionCategory")
    citation_category_code: str = Field("", alias="citationCategoryCode")
    related_claim_number_text: str = Field("", alias="relatedClaimNumberText")
    passage_location_text: list[str] = Field(default_factory=list, alias="passageLocationText")
    quality_summary_text: str = Field("", alias="qualitySummaryText")
    group_art_unit_number: str = Field("", alias="groupArtUnitNumber")
    tech_center: str = Field("", alias="techCenter")
    work_group_number: str = Field("", alias="workGroupNumber")
    npl_indicator: bool = Field(False, alias="nplIndicator")
    examiner_cited_reference_indicator: bool = Field(False, alias="examinerCitedReferenceIndicator")
    applicant_cited_examiner_reference_indicator: bool = Field(
        False, alias="applicantCitedExaminerReferenceIndicator"
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class DatasetApiResponse(BaseModel):
    """Standard response from USPTO Dataset API endpoints."""

    num_found: int = Field(0, alias="numFound")
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
