"""USPTO Open Data Portal MCP tools."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse

from fastmcp import FastMCP

from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.downloads import register_source
from patent_client_agents.uspto_odp import PtabTrialsClient, UsptoOdpClient

uspto_mcp = FastMCP("USPTO")


# USPTO ODP URL fields that require API key auth — must be stripped from responses
_AUTH_URL_FIELDS = {"fileDownloadURI", "downloadURI", "downloadUrl", "fileLocationURI"}


def _dump(obj: object) -> object:
    """Serialize a Pydantic model and strip auth-required URLs."""
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()  # type: ignore[union-attr]
        _strip_auth_urls(data)
        return data
    return obj


def _strip_auth_urls(data: object) -> None:
    """Recursively remove auth-required URL fields from nested dicts/lists."""
    if isinstance(data, dict):
        for key in _AUTH_URL_FIELDS & data.keys():
            del data[key]
        for v in data.values():
            _strip_auth_urls(v)
    elif isinstance(data, list):
        for item in data:
            _strip_auth_urls(item)


# ---------------------------------------------------------------------------
# Download fetchers
# ---------------------------------------------------------------------------


async def _fetch_application_document(path: str) -> tuple[bytes, str]:
    """Fetch a USPTO prosecution document. Path: ``{app_number}/documents/{doc_id}``."""
    parts = path.split("/")
    if len(parts) == 3 and parts[1] == "documents":
        app_number, doc_id = parts[0], parts[2]
    elif len(parts) == 2:
        app_number, doc_id = parts[0], parts[1]
    else:
        raise ValueError(f"Expected {{app}}/documents/{{doc_id}}, got: {path}")
    async with UsptoOdpClient() as client:
        pdf_bytes = await client.download_document(app_number, doc_id)
        return pdf_bytes, f"{app_number}_{doc_id}.pdf"


async def _fetch_ptab_document(path: str) -> tuple[bytes, str]:
    """Fetch a PTAB trial document PDF. Path: ``{document_identifier}``.

    Gets document metadata first to find fileDownloadURI, then fetches the
    PDF from that path.
    """
    doc_id = path.strip("/")
    async with PtabTrialsClient() as client:
        response = await client.get_document(doc_id)
        download_uri = None
        bag = getattr(response, "patentTrialDocumentDataBag", None) or []
        for entry in bag:
            dd = getattr(entry, "documentData", None)
            if dd and getattr(dd, "fileDownloadURI", None):
                download_uri = dd.fileDownloadURI
                break
            if getattr(entry, "fileDownloadURI", None):
                download_uri = entry.fileDownloadURI
                break
        if not download_uri:
            raise ValueError(f"No fileDownloadURI found for PTAB document {doc_id}")
        uri_path = urlparse(str(download_uri)).path
        pdf_bytes = await client.download_document_pdf(uri_path)
        return pdf_bytes, f"ptab_{doc_id}.pdf"


register_source("uspto/applications", _fetch_application_document, "application/pdf")
register_source("ptab/documents", _fetch_ptab_document, "application/pdf")


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


@uspto_mcp.tool(annotations=READ_ONLY)
async def search_applications(
    query: Annotated[
        str,
        "Lucene-style query. Searchable fields include: "
        "applicationMetaData.inventionTitle, applicationMetaData.patentNumber, "
        "applicationMetaData.publicationNumber, applicationMetaData.filingDate, "
        "applicationMetaData.grantDate, applicationMetaData.cpcClassificationBag, "
        "applicationMetaData.examinerName, applicationMetaData.applicationTypeCategory "
        "(UTILITY/DESIGN/PLANT/REAEX). "
        "Example: 'applicationMetaData.inventionTitle:\"blockchain authentication\"'",
    ],
    limit: Annotated[int, "Maximum number of results to return"] = 25,
    offset: Annotated[int, "Result offset for pagination"] = 0,
) -> dict:
    """Search USPTO patent applications by metadata fields (title, CPC, dates, status).

    NOTE: This searches application metadata only — not claims or specification
    text. For full-text patent search (within claims, description, abstract),
    use search_patent_publications instead.
    """
    async with UsptoOdpClient() as client:
        result = await client.search_applications(query=query, limit=limit, offset=offset)
        return _dump(result)  # type: ignore[return-value]


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_application(
    application_number: Annotated[
        str,
        "USPTO application number (8+ digits). Examples: '16123456', '17654321'. "
        "NOT a patent number (like '10123456B2') or publication number "
        "(like 'US20230012345A1'). If you have a patent number, use "
        "get_patent_family to find the application number first.",
    ],
) -> dict:
    """Get application metadata: status, filing/grant dates, examiner, CPC, and title.

    Does NOT return patent text (claims, spec, abstract). For patent text,
    use get_patent_publication. For prosecution documents, use
    list_file_history.
    """
    async with UsptoOdpClient() as client:
        result = await client.get_application(application_number)
        return _dump(result)  # type: ignore[return-value]


@uspto_mcp.tool(annotations=READ_ONLY)
async def list_file_history(
    application_number: Annotated[
        str,
        "USPTO application number (8+ digits). Examples: '16123456'. "
        "NOT a patent number or publication number.",
    ],
) -> dict:
    """List prosecution file-history documents for an application.

    Returns each document with its identifier, code, description, date,
    direction (incoming/outgoing/internal), page count, and available
    formats (XML, PDF, MS_WORD). Pass the ``document_identifier`` to
    ``get_file_history_item`` to fetch the content.

    Key document codes: CLM (claims as filed/amended), SPEC (specification),
    ABST (abstract), CTFR/CTNF (office actions), REM (applicant remarks),
    NOA (notice of allowance), CTRS (restriction requirement), IDS
    (information disclosure statement).
    """
    async with UsptoOdpClient() as client:
        response = await client.get_documents(application_number)

    documents: list[dict[str, object]] = []
    for raw in response.model_dump().get("documents", []):
        formats = [
            opt.get("mimeTypeIdentifier")
            for opt in (raw.get("downloadOptionBag") or [])
            if opt.get("mimeTypeIdentifier")
        ]
        documents.append(
            {
                "document_identifier": raw.get("documentIdentifier"),
                "code": raw.get("documentCode"),
                "description": raw.get("documentCodeDescriptionText"),
                "date": raw.get("officialDate") or raw.get("documentDate"),
                "direction": raw.get("directionCategory"),
                "page_count": raw.get("pageCount"),
                "formats": formats,
            }
        )
    return {"application_number": application_number, "documents": documents}


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_file_history_item(
    application_number: Annotated[
        str,
        "USPTO application number (8+ digits). Examples: '16123456'.",
    ],
    document_identifier: Annotated[
        str,
        "Document identifier from list_file_history (e.g. 'IGBCPFXCPXXIFW3').",
    ],
    format: Annotated[
        str,
        "Content format. 'auto' (default): readable structured text — XML "
        "parsed when available, else PDF text layer, else Tesseract OCR for "
        "image-only PDFs. 'pdf': returns a signed download_url for the PDF. "
        "'xml': raw ST.96 XML (raises if XML was not filed for this document).",
    ] = "auto",
) -> dict:
    """Get the content of a file-history document.

    Default 'auto' mode returns readable text regardless of how USPTO
    filed the document — agents do not need to pre-check format
    availability. ``format='pdf'`` returns a signed `download_url` (or
    `file_path` in local stdio mode) instead of inline PDF bytes. Call
    ``list_file_history`` first to discover valid ``document_identifier``
    values for an application.
    """
    import base64

    from law_tools_core.exceptions import NotFoundError
    from law_tools_core.filenames import file_history_item as _fh_name
    from law_tools_core.mcp.downloads import download_response
    from patent_client_agents.uspto_odp.clients.applications import ApplicationsClient

    async with ApplicationsClient() as client:
        try:
            result = await client.get_document_content(
                application_number, document_identifier, format=format
            )
            if result.get("format") == "pdf":
                pdf_bytes = base64.b64decode(result.pop("content_base64"))
                result.pop("size_bytes", None)
                result.pop("content_type", None)
                return {
                    **result,
                    **download_response(
                        f"uspto/applications/{application_number}/documents/{document_identifier}",
                        pdf_bytes,
                        filename=_fh_name(
                            application_number=application_number,
                            document_code=None,
                            mail_date=None,
                            document_identifier=document_identifier,
                            extension="pdf",
                        ),
                        content_type="application/pdf",
                    ),
                }
            if result.get("format") == "xml":
                result["filename"] = _fh_name(
                    application_number=application_number,
                    document_code=None,
                    mail_date=None,
                    document_identifier=document_identifier,
                    extension="xml",
                )
            return result
        except NotFoundError:
            response = await client.get_documents(application_number)
            sample = [
                {
                    "document_identifier": d.documentIdentifier,
                    "code": d.documentCode,
                    "description": d.documentCodeDescriptionText,
                }
                for d in response.documents[:20]
            ]
            raise NotFoundError(
                f"Document {document_identifier!r} not found in application "
                f"{application_number}. First {len(sample)} available documents: "
                f"{sample}. Use list_file_history for the complete list."
            ) from None


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_patent_family(
    identifier: Annotated[
        str,
        "The number to look up. Format depends on identifier_type.",
    ],
    identifier_type: Annotated[
        str,
        "Type of identifier: 'application' (e.g. '16123456'), "
        "'patent' (e.g. '10123456' or 'US10123456B2'), or "
        "'publication' (e.g. 'US20230012345A1'). "
        "Default: 'patent'.",
    ] = "patent",
) -> dict:
    """Get patent family relationships (continuations, divisionals, CIPs).

    Also useful for resolving a patent number to its application number.
    The response includes all family members with their application numbers,
    patent numbers, and relationship types.
    """
    async with UsptoOdpClient() as client:
        result = await client.get_family(identifier, identifier_type=identifier_type)
        return _dump(result)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_patent_assignment(
    application_number: Annotated[
        str,
        "USPTO application number (8+ digits). Examples: '16123456', '17654321'. "
        "NOT a patent number or publication number.",
    ],
) -> dict:
    """Get assignment and ownership transfer history for a patent application."""
    async with UsptoOdpClient() as client:
        result = await client.get_assignment(application_number)
        return _dump(result)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# PTAB (trials, appeals, interferences)
# ---------------------------------------------------------------------------


_PTAB_SEARCH_METHOD = {
    "proceeding": "search_trial_proceedings",
    "trial_decision": "search_trial_decisions",
    "trial_document": "search_trial_documents",
    "appeal_decision": "search_appeal_decisions",
    "interference_decision": "search_interference_decisions",
}

_PTAB_GET_METHOD = {
    "proceeding": ("get_trial_proceeding", "trial_number"),
    "trial_decision": ("get_trial_decision", "document_identifier"),
    "trial_document": ("get_trial_document", "document_identifier"),
    "appeal_decision": ("get_appeal_decision", "document_identifier"),
    "interference_decision": ("get_interference_decision", "document_identifier"),
}


@uspto_mcp.tool(annotations=READ_ONLY)
async def search_ptab(
    type: Annotated[
        str,
        "What to search. 'proceeding' — AIA trial proceedings (IPR/PGR/CBM/DER). "
        "'trial_decision' — decisions issued in AIA trials. "
        "'trial_document' — documents filed in AIA trials. "
        "'appeal_decision' — ex parte appeal decisions (different legal vehicle from "
        "AIA trials). 'interference_decision' — pre-AIA interference decisions.",
    ],
    query: Annotated[str, "Search query"],
    limit: Annotated[int, "Maximum number of results"] = 25,
    offset: Annotated[int, "Result offset for pagination"] = 0,
) -> dict:
    """Search PTAB records across trials, appeals, and interferences.

    Appeals and interferences are legally distinct tribunals from AIA
    trials — pick ``type`` deliberately. For trial-bound searches, use
    ``proceeding`` / ``trial_decision`` / ``trial_document``.
    """
    key = type.strip().lower()
    method_name = _PTAB_SEARCH_METHOD.get(key)
    if method_name is None:
        from law_tools_core.exceptions import ValidationError

        raise ValidationError(f"type must be one of {sorted(_PTAB_SEARCH_METHOD)}; got {type!r}")
    async with UsptoOdpClient() as client:
        method = getattr(client, method_name)
        result = await method(query=query, limit=limit, offset=offset)
        return _dump(result)  # type: ignore[return-value]


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_ptab(
    type: Annotated[
        str,
        "Record type to fetch. 'proceeding' — takes a trial number (e.g. "
        "'IPR2024-00001'). 'trial_decision' / 'trial_document' / "
        "'appeal_decision' / 'interference_decision' — take a document identifier "
        "from the corresponding search.",
    ],
    identifier: Annotated[
        str,
        "Trial number for 'proceeding'; document identifier for all other types.",
    ],
) -> dict:
    """Fetch a single PTAB record (proceeding, decision, or document) by identifier."""
    key = type.strip().lower()
    if key not in _PTAB_GET_METHOD:
        from law_tools_core.exceptions import ValidationError

        raise ValidationError(f"type must be one of {sorted(_PTAB_GET_METHOD)}; got {type!r}")
    method_name, _id_kind = _PTAB_GET_METHOD[key]
    async with UsptoOdpClient() as client:
        method = getattr(client, method_name)
        result = await method(identifier)
        return _dump(result)  # type: ignore[return-value]


@uspto_mcp.tool(annotations=READ_ONLY)
async def list_ptab_children(
    parent_type: Annotated[
        str,
        "What the ``parent_identifier`` refers to. 'trial' — an AIA trial number "
        "(e.g. 'IPR2024-00001'); lists decisions and/or documents. 'application' — "
        "a USPTO application number; lists ex parte appeal decisions for it. "
        "'interference' — an interference number; lists decisions.",
    ],
    parent_identifier: Annotated[str, "Trial number, application number, or interference number"],
    include: Annotated[
        str,
        "For parent_type='trial' only: 'decisions' (default), 'documents', or 'both'. "
        "Appeals and interferences only return decisions.",
    ] = "decisions",
) -> dict:
    """List PTAB children (decisions, documents) attached to a parent record.

    Use ``download_ptab_document`` to retrieve the PDF of any trial document.
    """
    from law_tools_core.exceptions import ValidationError

    pt = parent_type.strip().lower()
    inc = include.strip().lower()
    async with UsptoOdpClient() as client:
        if pt == "trial":
            if inc not in ("decisions", "documents", "both"):
                raise ValidationError(
                    f"include must be 'decisions', 'documents', or 'both' for trials; got {include!r}"
                )
            out: dict[str, object] = {"trial_number": parent_identifier}
            if inc in ("decisions", "both"):
                decisions = await client.get_trial_decisions_by_trial(parent_identifier)
                out["decisions"] = _dump(decisions)
            if inc in ("documents", "both"):
                documents = await client.get_trial_documents_by_trial(parent_identifier)
                out["documents"] = _dump(documents)
            return out
        if pt == "application":
            if inc not in ("decisions",):
                raise ValidationError("parent_type='application' only supports include='decisions'")
            result = await client.get_appeal_decisions_by_number(parent_identifier)
            return {"application_number": parent_identifier, "decisions": _dump(result)}
        if pt == "interference":
            if inc not in ("decisions",):
                raise ValidationError(
                    "parent_type='interference' only supports include='decisions'"
                )
            result = await client.get_interference_decisions_by_number(parent_identifier)
            return {"interference_number": parent_identifier, "decisions": _dump(result)}
        raise ValidationError(
            f"parent_type must be 'trial', 'application', or 'interference'; got {parent_type!r}"
        )


@uspto_mcp.tool(annotations=READ_ONLY)
async def download_ptab_document(
    document_identifier: Annotated[str, "PTAB document identifier from the documents list"],
) -> dict:
    """Download a PTAB trial document PDF.

    Returns a signed `download_url` (or `file_path` in local stdio mode) plus
    `filename`, `content_type`, `size_bytes`, `document_identifier`. Gets
    the document metadata first to find the correct download URI.
    """
    from law_tools_core.filenames import ptab_document as _ptab_name
    from law_tools_core.mcp.downloads import download_response

    async with PtabTrialsClient() as client:
        response = await client.get_document(document_identifier)
        download_uri = None
        proceeding_number: str | None = None
        filing_date: str | None = None
        document_code: str | None = None
        bag = getattr(response, "patentTrialDocumentDataBag", None) or []
        for entry in bag:
            dd = getattr(entry, "documentData", None)
            if dd and getattr(dd, "fileDownloadURI", None):
                download_uri = dd.fileDownloadURI
                proceeding_number = getattr(dd, "proceedingNumber", None) or proceeding_number
                filing_date = getattr(dd, "documentFilingDate", None) or getattr(
                    dd, "officialDate", None
                )
                document_code = getattr(dd, "documentCode", None) or getattr(
                    dd, "documentTypeName", None
                )
                break
        if not download_uri:
            raise ValueError(f"No download URI found for PTAB document {document_identifier}")
        uri_path = urlparse(str(download_uri)).path
        pdf_bytes = await client.download_document_pdf(uri_path)
        return download_response(
            f"ptab/documents/{document_identifier}",
            pdf_bytes,
            filename=_ptab_name(
                proceeding_number=proceeding_number,
                filing_date=str(filing_date) if filing_date else None,
                document_code=document_code,
                document_identifier=document_identifier,
            ),
            content_type="application/pdf",
            document_identifier=document_identifier,
        )


# ---------------------------------------------------------------------------
# Petitions
# ---------------------------------------------------------------------------


@uspto_mcp.tool(annotations=READ_ONLY)
async def search_petitions(
    query: Annotated[str, "Search query for petition decisions"],
    limit: Annotated[int, "Maximum number of results"] = 25,
    offset: Annotated[int, "Result offset for pagination"] = 0,
) -> dict:
    """Search USPTO petition decisions."""
    async with UsptoOdpClient() as client:
        result = await client.search_petitions(q=query, limit=limit, offset=offset)
        return _dump(result)  # type: ignore[return-value]


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_petition(
    petition_id: Annotated[str, "Petition decision record identifier"],
) -> dict:
    """Get details for a specific petition decision."""
    async with UsptoOdpClient() as client:
        result = await client.get_petition(petition_id)
        return _dump(result)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Bulk Data
# ---------------------------------------------------------------------------


@uspto_mcp.tool(annotations=READ_ONLY)
async def search_bulk_datasets(
    query: Annotated[str, "Search query for bulk data products"],
) -> dict:
    """Search available USPTO bulk data products."""
    async with UsptoOdpClient() as client:
        result = await client.search_bulk_datasets(query=query)
        return _dump(result)  # type: ignore[return-value]


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_bulk_dataset(
    product_id: Annotated[str, "Bulk data product identifier"],
) -> dict:
    """Get details and file listing for a specific bulk data product."""
    async with UsptoOdpClient() as client:
        result = await client.get_bulk_dataset_product(product_id)
        return _dump(result)  # type: ignore[return-value]
