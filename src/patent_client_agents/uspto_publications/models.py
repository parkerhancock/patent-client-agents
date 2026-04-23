from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

from .utils import html_to_text


def _coerce_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _coerce_application_number(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace("/", "").replace(" ", "").strip()
    if normalized.startswith("D"):
        normalized = "29" + normalized[1:]
    return normalized or None


HtmlString = Annotated[str | None, BeforeValidator(html_to_text)]
ApplicationNumber = Annotated[str | None, BeforeValidator(_coerce_application_number)]


class Claim(BaseModel):
    number: int
    limitations: list[str]
    depends_on: list[int] = Field(default_factory=list)
    dependent_claims: list[int] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return f"{self.number}. " + "\n".join(self.limitations)

    @property
    def independent(self) -> bool:
        return not self.depends_on

    @property
    def dependent(self) -> bool:
        return bool(self.depends_on)


class Document(BaseModel):
    abstract_html: str | None = None
    abstract: HtmlString = Field(default=None, alias="abstract_html")
    government_interest: str | None = None
    background_html: str | None = None
    background: HtmlString = Field(default=None, alias="background_html")
    description_html: str | None = None
    description: HtmlString = Field(default=None, alias="description_html")
    brief_html: str | None = None
    brief: HtmlString = Field(default=None, alias="brief_html")
    claim_statement: str | None = None
    claims_html: str | None = None
    claims_text: HtmlString = Field(default=None, alias="claims_html")
    claims: list[Claim] = Field(default_factory=list)


class DocumentStructure(BaseModel):
    number_of_claims: int | None = None
    number_of_drawing_sheets: int | None = None
    number_of_figures: int | None = None
    page_count: int | None = None
    front_page_end: int | None = None
    front_page_start: int | None = None
    bib_start: int | None = None
    bib_end: int | None = None
    abstract_start: int | None = None
    abstract_end: int | None = None
    drawings_start: int | None = None
    drawings_end: int | None = None
    description_start: int | None = None
    description_end: int | None = None
    specification_start: int | None = None
    specification_end: int | None = None
    claims_end: int | None = None
    claims_start: int | None = None
    amend_start: int | None = None
    amend_end: int | None = None
    cert_correction_end: int | None = None
    cert_correction_start: int | None = None
    cert_reexamination_end: int | None = None
    cert_reexamination_start: int | None = None
    ptab_start: int | None = None
    ptab_end: int | None = None
    search_report_start: int | None = None
    search_report_end: int | None = None
    supplemental_start: int | None = None
    supplemental_end: int | None = None


class UsReference(BaseModel):
    publication_number: str | None = None
    pub_month: dt.date | None = None
    patentee_name: str | None = None
    cited_by_examiner: bool | None = None


class ForeignReference(BaseModel):
    citation_classification: str | None = None
    citation_cpc: str | None = None
    country_code: str | None = None
    patent_number: str | None = None
    pub_month: dt.date | None = None
    cited_by_examiner: bool | None = None


class NplReference(BaseModel):
    citation: str | None = None
    cited_by_examiner: bool | None = None


class RelatedApplication(BaseModel):
    child_patent_country: str | None = None
    child_patent_number: str | None = None
    country_code: str | None = None
    filing_date: dt.date | None = None
    number: str | None = None
    parent_status_code: str | None = None
    patent_issue_date: dt.date | None = None
    patent_number: str | None = None


class ForeignPriorityApplication(BaseModel):
    country: str | None = None
    app_filing_date: dt.date | None = None
    app_number: str | None = None


class Inventor(BaseModel):
    name: str | None = None
    city: str | None = None
    country: str | None = None
    postal_code: str | None = None
    state: str | None = None


class Applicant(BaseModel):
    city: str | None = None
    country: str | None = None
    name: str | None = None
    state: str | None = None
    zip_code: str | None = None
    authority_type: str | None = None


class Assignee(BaseModel):
    city: str | None = None
    country: str | None = None
    name: str | None = None
    postal_code: str | None = None
    state: str | None = None
    type_code: str | None = None


class CpcCode(BaseModel):
    cpc_class: str | None = None
    cpc_subclass: str | None = None
    version: dt.date | None = None


class IntlCode(BaseModel):
    intl_class: str | None = None
    intl_subclass: str | None = None
    version: dt.date | None = None


class PublicSearchDocument(BaseModel):
    guid: str | None = None
    publication_number: str | None = None
    publication_date: dt.date | None = None
    appl_id: ApplicationNumber = None
    patent_title: str | None = None
    app_filing_date: dt.date | None = None
    application_type: str | None = None
    family_identifier_cur: int | None = None
    related_apps: list[RelatedApplication] = Field(default_factory=list)
    foreign_priority: list[ForeignPriorityApplication] = Field(default_factory=list)
    type: str | None = None
    inventors: list[Inventor] = Field(default_factory=list)
    inventors_short: str | None = None
    applicants: list[Applicant] = Field(default_factory=list)
    assignees: list[Assignee] = Field(default_factory=list)
    group_art_unit: str | None = None
    primary_examiner: str | None = None
    assistant_examiner: list[str] = Field(default_factory=list)
    legal_firm_name: list[str] = Field(default_factory=list)
    attorney_name: list[str] = Field(default_factory=list)
    document: Document | None = None
    document_structure: DocumentStructure | None = None
    image_file_name: str | None = None
    image_location: str | None = None
    composite_id: str | None = None
    database_name: str | None = None
    derwent_week_int: int | None = None
    us_references: list[UsReference] = Field(default_factory=list)
    foreign_references: list[ForeignReference] = Field(default_factory=list)
    npl_references: list[NplReference] = Field(default_factory=list)
    cpc_inventive: list[CpcCode] = Field(default_factory=list)
    cpc_additional: list[CpcCode] = Field(default_factory=list)
    intl_class_issued: list[str] = Field(default_factory=list)
    intl_class_current_primary: list[IntlCode] = Field(default_factory=list)
    intl_class_currrent_secondary: list[IntlCode] = Field(default_factory=list)
    us_class_current: list[str] = Field(default_factory=list)
    us_class_issued: list[str] = Field(default_factory=list)
    field_of_search_us: list[str] = Field(default_factory=list)
    field_of_search_cpc: list[str] = Field(default_factory=list)


class PublicSearchBiblio(BaseModel):
    guid: str | None = None
    publication_number: str | None = None
    publication_date: dt.date | None = None
    patent_title: str | None = None
    type: str | None = None
    main_classification_code: str | None = None
    applicant_names: list[str] = Field(default_factory=list)
    assignee_names: list[str] = Field(default_factory=list)
    uspc_full_classification: list[str] = Field(default_factory=list)
    ipc_code: list[str] = Field(default_factory=list)
    cpc_additional: list[str] = Field(default_factory=list)
    app_filing_date: dt.date | None = None
    related_appl_filing_date: list[dt.date] = Field(default_factory=list)
    primary_examiner: str | None = None
    assistant_examiner: str | None = None
    appl_id: ApplicationNumber = None
    document_structure: DocumentStructure | None = None


class PublicSearchBiblioPage(BaseModel):
    num_found: int
    per_page: int
    page: int
    docs: list[PublicSearchBiblio] = Field(default_factory=list)
