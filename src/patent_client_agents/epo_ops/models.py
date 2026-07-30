"""Pydantic response models for the EPO OPS MCP server."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentId(BaseModel):
    model_config = {"populate_by_name": True}
    country: str | None = None
    doc_number: str | None = Field(default=None, alias="number")
    kind: str | None = None
    date: str | None = None
    doc_type: str | None = None
    format: str | None = None
    id_type: str | None = None
    name: str | None = None


class SearchResult(BaseModel):
    docdb_number: str | None = None
    country: str | None = None
    doc_number: str | None = None
    kind: str | None = None
    publication_date: str | None = None
    application_number: str | None = None
    family_id: str | None = None


class SearchResponse(BaseModel):
    query: str | None = None
    range_begin: int | None = None
    range_end: int | None = None
    total_results: int | None = None
    results: list[SearchResult] = Field(default_factory=list)


class FamilySearchEntry(BaseModel):
    family_id: str
    members: list[SearchResult] = Field(default_factory=list)


class FamilySearchResponse(BaseModel):
    query: str | None = None
    total_results: int | None = None
    range_begin: int | None = None
    range_end: int | None = None
    families: list[FamilySearchEntry] = Field(default_factory=list)


class EpoCitation(BaseModel):
    """Patent or non-patent literature cited in an EPO biblio record."""

    sequence: int | None = None
    cited_by: str | None = None
    cited_phase: str | None = None
    office: str | None = None
    categories: list[str] = Field(default_factory=list)
    relevant_claims: list[str] = Field(default_factory=list)
    passages: list[str] = Field(default_factory=list)
    patent_document: DocumentId | None = None
    non_patent_literature: str | None = None
    source_url: str | None = None


class BiblioRecord(BaseModel):
    docdb_number: str | None = None
    application_number: str | None = None
    publication_reference: DocumentId | None = None
    application_reference: DocumentId | None = None
    family_id: str | None = None
    title: str | None = None
    abstract: str | None = None
    applicants: list[str] = Field(default_factory=list)
    inventors: list[str] = Field(default_factory=list)
    ipc_classes: list[str] = Field(default_factory=list)
    cpc_classes: list[str] = Field(default_factory=list)
    priority_claims: list[DocumentId] = Field(default_factory=list)


class BiblioResponse(BaseModel):
    documents: list[BiblioRecord] = Field(default_factory=list)


class CitationResponse(BaseModel):
    publication_number: str
    citations: list[EpoCitation] = Field(default_factory=list)


class EquivalentsResponse(BaseModel):
    """Simple-family equivalents returned by the OPS equivalents endpoint."""

    input_document: DocumentId | None = None
    equivalents: list[DocumentId] = Field(default_factory=list)


class Claim(BaseModel):
    number: int | None = None
    text: str | None = None
    depends_on: list[int] = Field(default_factory=list)
    dependent_claims: list[int] = Field(default_factory=list)


class FullTextResponse(BaseModel):
    docdb_number: str | None = None
    section: str
    claims: list[Claim] = Field(default_factory=list)
    raw_text: str | None = None
    description: str | None = None


class FamilyMember(BaseModel):
    family_id: str | None = None
    publication_number: str | None = None
    application_number: str | None = None
    publication_references: list[DocumentId] = Field(default_factory=list)
    application_references: list[DocumentId] = Field(default_factory=list)
    priority_claims: list[DocumentId] = Field(default_factory=list)


class FamilyResponse(BaseModel):
    publication_number: str | None = None
    num_records: int | None = None
    members: list[FamilyMember] = Field(default_factory=list)


class LegalEvent(BaseModel):
    event_code: str | None = None
    event_date: str | None = None
    event_country: str | None = None
    country_code: str | None = None
    filing_or_publication: str | None = None
    document_number: str | None = None
    ip_type: str | None = None
    free_text: str | None = None
    text_record: str | None = None
    metadata: dict | None = None


class LegalEventsResponse(BaseModel):
    publication_reference: DocumentId | None = None
    events: list[LegalEvent] = Field(default_factory=list)


class RegisterText(BaseModel):
    text_type: str | None = None
    text: str


class RegisterDate(BaseModel):
    date_type: str | None = None
    date: str


class RegisterGazetteReference(BaseModel):
    number: str | None = None
    date: str | None = None


class RegisterEvent(BaseModel):
    id: str | None = None
    event_type: str | None = None
    event_date: str | None = None
    event_code: str | None = None
    description: str | None = None
    texts: list[RegisterText] = Field(default_factory=list)
    gazette_reference: RegisterGazetteReference | None = None


class RegisterProceduralStep(BaseModel):
    id: str | None = None
    phase: str | None = None
    step_code: str | None = None
    description: str | None = None
    texts: list[RegisterText] = Field(default_factory=list)
    dates: list[RegisterDate] = Field(default_factory=list)
    gazette_reference: RegisterGazetteReference | None = None


class RegisterDocumentMetadata(BaseModel):
    epo_number: str
    status: str | None = None
    produced_by: str | None = None
    language: str | None = None
    dtd_version: str | None = None
    date_produced: str | None = None


class RegisterEventsResponse(RegisterDocumentMetadata):
    """Structured EPO Register dossier events."""

    events: list[RegisterEvent] = Field(default_factory=list)


class RegisterProceduralStepsResponse(RegisterDocumentMetadata):
    """Structured EPO Register procedural steps."""

    procedural_steps: list[RegisterProceduralStep] = Field(default_factory=list)


class NumberConversionResponse(BaseModel):
    input_document: DocumentId
    output_document: DocumentId
    service_version: str | None = None
    messages: list[str] = Field(default_factory=list)


class PdfDownloadResponse(BaseModel):
    publication_number: str
    num_pages: int
    pdf_base64: str


class CpcTitlePart(BaseModel):
    text: str | None = None
    scheme: str | None = None
    media_id: str | None = None
    media_type: str | None = None


class CpcClassificationItem(BaseModel):
    symbol: str | None = None
    level: int | None = None
    additional_only: bool | None = None
    sort_key: str | None = None
    date_revised: str | None = None
    not_allocatable: bool | None = None
    breakdown_code: bool | None = None
    link: str | None = None
    title: str | None = None
    title_parts: list[CpcTitlePart] = Field(default_factory=list)
    metadata: list[str] = Field(default_factory=list)
    children: list[CpcClassificationItem] = Field(default_factory=list)


class CpcScheme(BaseModel):
    scheme_type: str | None = None
    export_date: str | None = None
    items: list[CpcClassificationItem] = Field(default_factory=list)


class CpcRetrievalResponse(BaseModel):
    scheme: CpcScheme


class CpcSearchResult(BaseModel):
    classification_symbol: str
    percentage: float | None = None
    title: str | None = None
    title_parts: list[CpcTitlePart] = Field(default_factory=list)


class CpcSearchResponse(BaseModel):
    query: str
    total_results: int | None = None
    range_begin: int | None = None
    range_end: int | None = None
    results: list[CpcSearchResult] = Field(default_factory=list)


class ClassificationMapping(BaseModel):
    cpc: str | None = None
    ecla: str | None = None
    ipc: str | None = None
    additional_only: bool | None = None


class ClassificationMappingResponse(BaseModel):
    input_schema: str | None = None
    output_schema: str | None = None
    mappings: list[ClassificationMapping] = Field(default_factory=list)


class CpcMediaResponse(BaseModel):
    media_id: str
    mime_type: str
    data_base64: str


class CpciClassification(BaseModel):
    sequence: int | None = None
    section: str | None = None
    class_code: str | None = None
    subclass: str | None = None
    main_group: str | None = None
    subgroup: str | None = None
    classification_value: str | None = None
    generating_offices: list[str] = Field(default_factory=list)


class CpciBiblioRecord(BaseModel):
    docdb_number: str | None = None
    classifications: list[CpciClassification] = Field(default_factory=list)


class CpciBiblioResponse(BaseModel):
    records: list[CpciBiblioRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# EPO Register service — Unitary Patent Package
# ---------------------------------------------------------------------------


class UnitaryPatentStatus(BaseModel):
    """One row in ``<reg:unitary-patent-statuses>``.

    ``status_code`` mirrors the EPO register's integer status code (e.g.
    ``"9"`` = "Unitary effect registered"). ``text`` is the human-readable
    label EPO embeds alongside the code.
    """

    status_code: str
    text: str
    change_date: str | None = None  # YYYYMMDD as published; not parsed


class UnitaryPatentPackage(BaseModel):
    """EPO Register ``/upp`` response, distilled to the unitary fields.

    Returned by :func:`patent_client_agents.epo_ops.get_unitary_patent_package`.
    ``None`` is returned when the register response contains no
    ``<reg:unitary-patent>`` block — that means the EP either was never
    elected for unitary effect, or is too new for the registration to
    have been recorded yet.
    """

    epo_number: str
    statuses: list[UnitaryPatentStatus] = Field(default_factory=list)

    @property
    def latest_status(self) -> UnitaryPatentStatus | None:
        """Most recent status (statuses are returned newest-first)."""
        if not self.statuses:
            return None
        return self.statuses[0]

    @property
    def is_registered(self) -> bool:
        """True iff a "Unitary effect registered" status appears anywhere."""
        return any(
            "registered" in (s.text or "").lower() and "unitary" in (s.text or "").lower()
            for s in self.statuses
        )
