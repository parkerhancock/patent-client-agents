"""USPTO Open Data Portal MCP tools."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast
from urllib.parse import urlparse

from fastmcp import FastMCP

from law_tools_core.envelope import (
    ListEnvelope,
    make_provenance,
)
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.downloads import read_resource, register_source
from patent_client_agents.uspto_odp import PtabTrialsClient, UsptoOdpClient

uspto_mcp = FastMCP("USPTO")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers — USPTO ODP source-specific wrappers around
# law_tools_core.envelope. The applications surface is the template
# referenced by CONNECTOR_STANDARDS.md §5.9; other USPTO tools (PTAB,
# petitions, bulk data) follow the same pattern in a later sweep.
# ──────────────────────────────────────────────────────────────────────

_USPTO_ODP_BASE = "https://api.uspto.gov"
_USPTO_ODP_NAME = "USPTO Open Data Portal"


def _odp_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}``."""
    return make_provenance(
        source_url=f"{_USPTO_ODP_BASE}{path}",
        source_name=_USPTO_ODP_NAME,
    )


def _summarize_application(record: dict) -> str:
    """One-line Markdown summary for a single application record."""
    meta = record.get("applicationMetaData") or {}
    appl = record.get("applicationNumberText") or "(no appl#)"
    title = meta.get("inventionTitle") or "(no title)"
    status = meta.get("applicationStatusDescriptionText") or "(unknown status)"
    filing = meta.get("filingDate") or "?"
    pat = meta.get("patentNumber")
    grant = meta.get("grantDate")
    head = f"**US application {appl}** — {title}"
    line = f"Status: {status}. Filed {filing}"
    if pat and grant:
        line += f"; issued as US {pat} on {grant}."
    elif pat:
        line += f"; issued as US {pat}."
    else:
        line += "."
    return f"{head}\n{line}"


# USPTO ODP URL fields that require API key auth — must be stripped from responses
_AUTH_URL_FIELDS = {"fileDownloadURI", "downloadURI", "downloadUrl", "fileLocationURI"}


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model and strip auth-required URLs.

    Every caller passes a Pydantic model from the upstream client; the
    fallback ``return obj`` branch exists only to be defensive if a dict
    slips through. Typed as ``dict[str, Any]`` so call sites can use
    ``.get(...)`` and similar without per-call type narrowing.

    ``hasattr`` and ``isinstance(obj, dict)`` don't narrow ``object`` in
    ty's view, so we cast the results. The pyright/mypy ``union-attr``
    suppression remains for the model_dump attribute lookup.
    """
    if hasattr(obj, "model_dump"):
        data: dict[str, Any] = cast("dict[str, Any]", obj.model_dump())  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
        _strip_auth_urls(data)
        return data
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


def _strip_auth_urls(data: Any) -> None:
    """Recursively remove auth-required URL fields from nested dicts/lists.

    Typed as ``Any`` because this walks JSON-shaped data of arbitrary
    depth — the recursion sees dicts, lists, scalars interchangeably.
    Stricter typing would force per-call casts at every recursive step.
    """
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


@uspto_mcp.resource(
    "pca://uspto/applications/{application_number}/documents/{document_identifier}",
    mime_type="application/pdf",
    name="USPTO prosecution document",
    description=(
        "One file-history document for a USPTO application, as a PDF. "
        "URI parameters: application_number (8+ digits) and document_identifier "
        "(from list_file_history)."
    ),
)
async def _application_document_resource(application_number: str, document_identifier: str):
    return await read_resource(
        f"uspto/applications/{application_number}/documents/{document_identifier}"
    )


@uspto_mcp.resource(
    "pca://ptab/documents/{document_identifier}",
    mime_type="application/pdf",
    name="PTAB document",
    description=(
        "PTAB trial document PDF (party filing, board decision, etc.). "
        "URI parameter is the document_identifier from search_ptab or list_ptab_children."
    ),
)
async def _ptab_document_resource(document_identifier: str):
    return await read_resource(f"ptab/documents/{document_identifier}")


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
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: application "
        "number, title, patent/publication number, filing/grant/status "
        "dates, status text, type category, first applicant/inventor, "
        "examiner, art unit, docket number, CPC bag. When True, every hit "
        "carries the full ODP record (inventor bag, applicant bag, "
        "attorney of record, continuity, PTA history, prosecution events, "
        "etc.) — large; prefer ``get_application`` for one record.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search USPTO patent applications by metadata fields (title, CPC, dates, status).

    Returns a lean stub per hit by default so result sets stay small.
    When you need the full record for one application, call
    ``get_application``. To get full records across the result set, pass
    ``full=True`` (expect a much larger payload).

    NOTE: This searches application metadata only — not claims or specification
    text. For full-text patent search (within claims, description, abstract),
    use search_patent_publications instead.

    Related tools: get_application, list_file_history, get_patent_family.
    """
    async with UsptoOdpClient() as client:
        result = await client.search_applications(
            query=query, limit=limit, offset=offset, full=full
        )

    dumped = _dump(result)
    items = list(dumped.get("patentBag") or dumped.get("results") or [])
    total_match = dumped.get("count") or dumped.get("recordTotalQuantity")
    shown = len(items)
    more = bool(total_match and shown + offset < int(total_match))
    summary_total = f"{shown} of {total_match} hits" if total_match else f"{shown} hits"
    return ListEnvelope[dict](
        summary=f"USPTO Applications — `{query}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_odp_provenance("/api/v1/patent/applications/search"),
    )


_GET_APPLICATION_FANOUT_CONCURRENCY = 5


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_application(
    application_number: Annotated[
        str | list[str],
        "USPTO application number (8+ digits), or a list of such numbers for "
        "portfolio workflows. Examples: '16123456', ['16123456', '17654321']. "
        "NOT a patent number (like '10123456B2') or publication number "
        "(like 'US20230012345A1'). If you have a patent number, use "
        "get_patent_family to find the application number first.",
    ],
) -> ListEnvelope[dict]:
    """Get application metadata: status, filing/grant dates, examiner, CPC, and title.

    Accepts either a single application number or a list (per §5.4); the
    response is always a ListEnvelope so the shape is stable. Bounded
    concurrent fan-out internally.

    Does NOT return patent text (claims, spec, abstract). For patent text,
    use get_patent_publication. For prosecution documents, use
    list_file_history.

    Related tools: search_applications, list_file_history, get_patent_family,
    get_patent_assignment.
    """
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )

    semaphore = asyncio.Semaphore(_GET_APPLICATION_FANOUT_CONCURRENCY)

    async def _fetch_one(client: UsptoOdpClient, appl: str) -> dict:
        async with semaphore:
            response = await client.get_application(appl)
            return _dump(response)  # type: ignore[return-value]

    async with UsptoOdpClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(results) == 1:
        summary = _summarize_application(_extract_first_record(results[0]))
    else:
        summary = f"Fetched {len(results)} USPTO applications: " + ", ".join(numbers)

    path = "/api/v1/patent/applications" + ("/" + numbers[0] if len(numbers) == 1 else "")
    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_odp_provenance(path),
    )


@uspto_mcp.tool(annotations=READ_ONLY)
async def list_file_history(
    application_number: Annotated[
        str,
        "USPTO application number (8+ digits). Examples: '16123456'. "
        "NOT a patent number or publication number.",
    ],
) -> ListEnvelope[dict]:
    """List prosecution file-history documents for an application.

    Returns each document with its identifier, code, description, date,
    direction (incoming/outgoing/internal), page count, and available
    formats (XML, PDF, MS_WORD). Pass the ``document_identifier`` to
    ``get_file_history_item`` to fetch the content.

    Key document codes: CLM (claims as filed/amended), SPEC (specification),
    ABST (abstract), CTFR/CTNF (office actions), REM (applicant remarks),
    NOA (notice of allowance), CTRS (restriction requirement), IDS
    (information disclosure statement).

    Related tools: get_application, get_file_history_item, download_file_history.
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

    return ListEnvelope[dict](
        summary=(
            f"USPTO application {application_number} — {len(documents)} file-history documents."
        ),
        items=documents,
        provenance=_odp_provenance(f"/api/v1/patent/applications/{application_number}/documents"),
    )


def _extract_first_record(payload: dict) -> dict:
    """Pull the first record out of a single get_application response.

    USPTO ODP returns ``{"patentBag": [{...}]}`` for a single application.
    Falls back to the payload itself if the bag is absent.
    """
    bag = payload.get("patentBag") or payload.get("results")
    if bag and isinstance(bag, list):
        return bag[0]
    return payload


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
        "image-only PDFs. 'xml': raw ST.96 XML (raises if XML was not filed "
        "for this document). For PDFs of one or more documents, use "
        "``download_file_history`` instead (it handles n=1 as a raw PDF).",
    ] = "auto",
) -> dict:
    """Get the text content of a file-history document.

    Returns readable text regardless of how USPTO filed the document —
    agents do not need to pre-check format availability. Focused on
    *content* (structured text or XML); for PDF bytes, call
    ``download_file_history`` (with ``item_ids=[document_identifier]``
    for a single document, or a list for bulk).

    Call ``list_file_history`` first to discover valid
    ``document_identifier`` values for an application.
    """
    from law_tools_core.exceptions import NotFoundError, ValidationError
    from law_tools_core.filenames import file_history_item as _fh_name
    from patent_client_agents.uspto_odp.clients.applications import ApplicationsClient

    if format == "pdf":
        raise ValidationError(
            "format='pdf' was removed from get_file_history_item — use "
            "download_file_history(application_number, item_ids=[document_identifier]) "
            "to get a PDF download_url."
        )

    async with ApplicationsClient() as client:
        try:
            result = await client.get_document_content(
                application_number, document_identifier, format=format
            )
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


_FILE_HISTORY_BULK_CAP = 50


def _parse_iso_date(value: str | None, *, field_name: str):
    """Parse ``YYYY-MM-DD`` to a ``date`` or return ``None``. Raises ``ValidationError`` on bad input."""
    if not value:
        return None
    from datetime import date as _date

    from law_tools_core.exceptions import ValidationError

    try:
        return _date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be ISO date YYYY-MM-DD; got {value!r}") from exc


@uspto_mcp.tool(annotations=READ_ONLY)
async def download_file_history(
    application_number: Annotated[
        str,
        "USPTO application number (8+ digits). Examples: '16123456'.",
    ],
    item_ids: Annotated[
        list[str] | None,
        "Specific document_identifier values from list_file_history. "
        "None means 'all documents matching the other filters'.",
    ] = None,
    document_codes: Annotated[
        list[str] | None,
        "Filter to USPTO document type codes (e.g. ['CTNF', 'IDS', 'NOA']). "
        "See list_file_history for available codes in this application.",
    ] = None,
    after: Annotated[
        str | None,
        "Include only documents on or after this date (ISO YYYY-MM-DD).",
    ] = None,
    before: Annotated[
        str | None,
        "Include only documents on or before this date (ISO YYYY-MM-DD).",
    ] = None,
):
    """Bulk-download file-history documents for a USPTO application.

    Returns one ``ResourceLink`` per matching PDF (or a single ResourceLink
    if exactly one matches) alongside a structured manifest with the same
    per-document URIs. Resource-aware MCP clients (e.g. Claude CoWork)
    fetch the per-doc bytes through ``resources/read``; the manifest also
    carries a zip ``download_url`` for clients that can hit the HTTP
    fallback domain. Cap: 50 documents per call. Filters AND together;
    if more than 50 documents match, the call refuses and asks you to
    narrow.

    Use ``list_file_history`` to discover document_identifier values and
    document codes for an application.
    """
    from datetime import date as _date

    from law_tools_core.exceptions import ValidationError
    from law_tools_core.filenames import file_history_item as _fh_name
    from law_tools_core.mcp.downloads import (
        BulkItem,
        download_bulk_tool_result,
        fetch_with_cache,
    )

    after_d = _parse_iso_date(after, field_name="after")
    before_d = _parse_iso_date(before, field_name="before")

    async with UsptoOdpClient() as client:
        response = await client.get_documents(application_number)

    raw_docs = response.model_dump().get("documents") or []
    item_id_set = set(item_ids) if item_ids else None
    doc_code_set = set(document_codes) if document_codes else None

    matched: list[dict[str, object]] = []
    for raw in raw_docs:
        doc_id = raw.get("documentIdentifier")
        if not doc_id:
            continue
        if item_id_set is not None and doc_id not in item_id_set:
            continue
        code = raw.get("documentCode")
        if doc_code_set is not None and code not in doc_code_set:
            continue
        date_str = raw.get("officialDate") or raw.get("documentDate")
        if after_d or before_d:
            doc_d: _date | None
            try:
                doc_d = _date.fromisoformat((date_str or "")[:10]) if date_str else None
            except ValueError:
                doc_d = None
            if after_d and (doc_d is None or doc_d < after_d):
                continue
            if before_d and (doc_d is None or doc_d > before_d):
                continue
        matched.append(
            {
                "document_identifier": doc_id,
                "code": code,
                "date": date_str,
                "description": raw.get("documentCodeDescriptionText"),
                "direction": raw.get("directionCategory"),
                "page_count": raw.get("pageCount"),
            }
        )

    if not matched:
        raise ValidationError(
            f"No file-history documents in application {application_number} "
            f"match the given filters."
        )
    if len(matched) > _FILE_HISTORY_BULK_CAP:
        raise ValidationError(
            f"File history for {application_number} has {len(matched)} documents "
            f"matching the filters; max {_FILE_HISTORY_BULK_CAP} per call. "
            f"Narrow with item_ids, document_codes, after, or before — or page "
            f"manually using list_file_history."
        )

    bulk_items = [
        BulkItem(
            item_id=str(d["document_identifier"]),
            resource_path=(
                f"uspto/applications/{application_number}/documents/{d['document_identifier']}"
            ),
            metadata={
                "document_code": d.get("code"),
                "document_date": d.get("date"),
                "description": d.get("description"),
                "direction": d.get("direction"),
                "page_count": d.get("page_count"),
            },
        )
        for d in matched
    ]

    async def _fetcher(item: BulkItem) -> tuple[bytes, str]:
        # Reuse the registered uspto/applications fetcher via cache. Rename the
        # file with the human-friendly file_history_item convention so the zip
        # entry is self-describing without consulting the manifest.
        content, _ = await fetch_with_cache(item.resource_path)
        nice_name = _fh_name(
            application_number=application_number,
            document_code=str(item.metadata.get("document_code"))
            if item.metadata.get("document_code")
            else None,
            mail_date=str(item.metadata.get("document_date"))[:10]
            if item.metadata.get("document_date")
            else None,
            document_identifier=item.item_id,
            extension="pdf",
        )
        return content, nice_name

    return await download_bulk_tool_result(
        bulk_items,
        _fetcher,
        container_label=f"{application_number}_file_history",
        container_metadata={
            "container": application_number,
            "application_number": application_number,
        },
        content_type_single="application/pdf",
    )


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


_PATENT_ASSIGNMENT_FANOUT_CONCURRENCY = 5


def _summarize_patent_assignment_response(record: dict) -> str:
    """One-line Markdown summary of an ODP assignment response for one application."""
    appl = record.get("applicationNumberText") or "(no appl#)"
    bag = record.get("assignmentBag") or []
    if not bag:
        return f"**US application {appl}** — no recorded assignments."
    first = bag[0]
    rf = first.get("reelAndFrameNumber") or "(no reel/frame)"
    conveyance = first.get("conveyanceText") or "(no conveyance)"
    assignees = first.get("assigneeBag") or []
    assignee_name = (
        assignees[0].get("assigneeNameText")
        if assignees and isinstance(assignees[0], dict)
        else None
    )
    head = (
        f"**US application {appl}** — {len(bag)} assignment"
        f"{'s' if len(bag) != 1 else ''} on record."
    )
    line = f"Latest reel/frame {rf}: {conveyance}"
    if assignee_name:
        line += f" → {assignee_name}"
    line += "."
    return f"{head}\n{line}"


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_patent_assignment(
    application_number: Annotated[
        str | list[str],
        "USPTO application number (8+ digits), or a list of such numbers for "
        "portfolio workflows. Examples: '16123456', ['16123456', '17654321']. "
        "NOT a patent number or publication number. The response is always "
        "a ListEnvelope so the shape is stable.",
    ],
) -> ListEnvelope[dict]:
    """Get USPTO patent assignment and ownership-transfer history for one or many applications.

    Returns recorded assignments (reel/frame, conveyance type, assignors,
    assignees, dates) for each application. Accepts either a single
    application number or a list (§5.4); bounded concurrent fan-out
    internally, order matches the input. For text-based searches across
    assignments (by assignee/assignor/conveyance), use
    ``search_patent_assignments``.

    Related tools: search_patent_assignments, get_application,
    search_applications.
    """
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        from law_tools_core.exceptions import ValidationError

        raise ValidationError("get_patent_assignment requires at least one application number")

    semaphore = asyncio.Semaphore(_PATENT_ASSIGNMENT_FANOUT_CONCURRENCY)

    async def _fetch_one(client: UsptoOdpClient, appl: str) -> dict:
        async with semaphore:
            return _dump(await client.get_assignment(appl))  # type: ignore[return-value]

    async with UsptoOdpClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(results) == 1:
        summary = _summarize_patent_assignment_response(results[0])
        path = f"/api/v1/patent/applications/{numbers[0]}/assignment"
    else:
        summary = f"Fetched assignments for {len(results)} applications: " + ", ".join(numbers)
        path = "/api/v1/patent/applications/assignment"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_odp_provenance(path),
    )


# ---------------------------------------------------------------------------
# PTAB (trials, appeals, interferences)
# ---------------------------------------------------------------------------
#
# search_ptab / get_ptab / list_ptab_children multiplex over five PTAB record
# types via a `type` parameter (§5.1 soft-cap accepted; the alternative was
# 15+ tools). The audit (§5.13) flagged the abstract names, so each
# docstring's first sentence expands "PTAB" and names the record types.


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

# Upstream response bag keys keyed by PTAB type.
_PTAB_BAG_KEY = {
    "proceeding": "patentTrialProceedingDataBag",
    "trial_decision": "patentTrialDocumentDataBag",
    "trial_document": "patentTrialDocumentDataBag",
    "appeal_decision": "patentAppealDataBag",
    "interference_decision": "patentInterferenceDataBag",
}

_PTAB_FANOUT_CONCURRENCY = 5


def _stub_ptab_record(record: dict, ptab_type: str) -> dict:
    """Lean projection (§5.5) of a PTAB record.

    Branches by ``ptab_type`` because the upstream shapes differ:

    - ``proceeding`` — trial_number + status + filing/institution/decision
      dates + patent number, patent owner, petitioner.
    - ``trial_decision`` / ``trial_document`` — document_identifier +
      filing_date + filing_party + document_type + trial_number. Decisions
      additionally carry decision_type / issue_date.
    - ``appeal_decision`` — document_identifier + appeal_number + issue_date
      + decision_type + appeal_outcome + application_number + applicant.
    - ``interference_decision`` — document_identifier + interference_number
      + issue_date + decision_type + outcome + senior_party + junior_party.
    """
    out: dict = {"type": ptab_type}
    if ptab_type == "proceeding":
        meta = record.get("trialMetaData") or {}
        po = record.get("patentOwnerData") or record.get("respondentData") or {}
        rp = record.get("regularPetitionerData") or {}
        out.update(
            {
                "trial_number": record.get("trialNumber"),
                "trial_type_code": meta.get("trialTypeCode"),
                "status": meta.get("trialStatusCategory"),
                "petition_filing_date": meta.get("petitionFilingDate"),
                "institution_decision_date": meta.get("institutionDecisionDate"),
                "latest_decision_date": meta.get("latestDecisionDate"),
                "termination_date": meta.get("terminationDate"),
                "patent_number": po.get("patentNumber"),
                "application_number": po.get("applicationNumberText"),
                "patent_owner": po.get("patentOwnerName") or po.get("realPartyInInterestName"),
                "petitioner": rp.get("realPartyInInterestName"),
            }
        )
        return out
    if ptab_type in ("trial_decision", "trial_document"):
        dd = record.get("documentData") or {}
        out.update(
            {
                "trial_number": record.get("trialNumber"),
                "document_identifier": dd.get("documentIdentifier"),
                "document_type": dd.get("documentTypeDescriptionText"),
                "document_title": dd.get("documentTitleText") or dd.get("documentName"),
                "filing_date": dd.get("documentFilingDate"),
                "filing_party": dd.get("filingPartyCategory"),
            }
        )
        if ptab_type == "trial_decision":
            decision = record.get("decisionData") or {}
            out["decision_type"] = decision.get("decisionTypeCategory")
            out["decision_issue_date"] = decision.get("decisionIssueDate")
            out["trial_outcome"] = decision.get("trialOutcomeCategory")
        return out
    if ptab_type == "appeal_decision":
        dd = record.get("documentData") or {}
        decision = record.get("decisionData") or {}
        appellant = record.get("appellantData") or {}
        out.update(
            {
                "appeal_number": record.get("appealNumber"),
                "document_identifier": dd.get("documentIdentifier"),
                "decision_issue_date": decision.get("decisionIssueDate"),
                "decision_type": decision.get("decisionTypeCategory"),
                "appeal_outcome": decision.get("appealOutcomeCategory"),
                "application_number": appellant.get("applicationNumberText"),
                "patent_number": appellant.get("patentNumber"),
                "applicant": appellant.get("patentOwnerName")
                or appellant.get("realPartyInInterestName"),
            }
        )
        return out
    if ptab_type == "interference_decision":
        dd = record.get("decisionDocumentData") or record.get("documentData") or {}
        senior = record.get("seniorPartyData") or {}
        junior = record.get("juniorPartyData") or {}
        out.update(
            {
                "interference_number": record.get("interferenceNumber"),
                "document_identifier": dd.get("documentIdentifier"),
                "decision_issue_date": dd.get("decisionIssueDate"),
                "decision_type": dd.get("decisionTypeCategory"),
                "interference_outcome": dd.get("interferenceOutcomeCategory"),
                "senior_party": senior.get("realPartyInInterestName")
                or senior.get("patentOwnerName"),
                "junior_party": junior.get("realPartyInInterestName")
                or junior.get("patentOwnerName"),
            }
        )
        return out
    return out


def _summarize_ptab(record: dict, ptab_type: str) -> str:
    """One-line Markdown summary of a single PTAB record. Always names the type."""
    if ptab_type == "proceeding":
        meta = record.get("trialMetaData") or {}
        trial = record.get("trialNumber") or "(no trial#)"
        status = meta.get("trialStatusCategory") or "(unknown status)"
        kind = meta.get("trialTypeCode") or ""
        po = record.get("patentOwnerData") or record.get("respondentData") or {}
        owner = po.get("patentOwnerName") or po.get("realPartyInInterestName") or "(no owner)"
        head = f"**PTAB trial {trial}** ({kind}) — {status}"
        return f"{head}\nPatent owner: {owner}."
    if ptab_type in ("trial_decision", "trial_document"):
        dd = record.get("documentData") or {}
        trial = record.get("trialNumber") or "(no trial#)"
        doc_id = dd.get("documentIdentifier") or "(no doc id)"
        title = dd.get("documentTitleText") or dd.get("documentName") or "(no title)"
        filing = dd.get("documentFilingDate") or "?"
        decision_type = ""
        if ptab_type == "trial_decision":
            decision = record.get("decisionData") or {}
            dt = decision.get("decisionTypeCategory")
            if dt:
                decision_type = f" ({dt})"
        head = (
            f"**PTAB trial {ptab_type.removeprefix('trial_')} {doc_id}** — {title}{decision_type}"
        )
        return f"{head}\nTrial: {trial}. Filed {filing}."
    if ptab_type == "appeal_decision":
        dd = record.get("documentData") or {}
        decision = record.get("decisionData") or {}
        doc_id = dd.get("documentIdentifier") or "(no doc id)"
        appeal = record.get("appealNumber") or "(no appeal#)"
        outcome = decision.get("appealOutcomeCategory") or "(no outcome)"
        issued = decision.get("decisionIssueDate") or "?"
        head = f"**PTAB appeal decision {doc_id}** — appeal {appeal}, outcome: {outcome}"
        return f"{head}\nIssued {issued}."
    if ptab_type == "interference_decision":
        dd = record.get("decisionDocumentData") or record.get("documentData") or {}
        doc_id = dd.get("documentIdentifier") or "(no doc id)"
        intf = record.get("interferenceNumber") or "(no intf#)"
        outcome = dd.get("interferenceOutcomeCategory") or "(no outcome)"
        issued = dd.get("decisionIssueDate") or "?"
        head = f"**PTAB interference decision {doc_id}** — interference {intf}, outcome: {outcome}"
        return f"{head}\nIssued {issued}."
    return "PTAB record."


def _extract_ptab_first(payload: dict, ptab_type: str) -> dict:
    """Pull the first record out of a get_ptab response payload."""
    bag_key = _PTAB_BAG_KEY[ptab_type]
    bag = payload.get(bag_key)
    if bag and isinstance(bag, list):
        return bag[0]
    return payload


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
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub whose fields "
        "depend on ``type`` — proceedings carry trial number + status + key "
        "dates + patent owner / petitioner; decisions and documents carry "
        "document_identifier + filing_date + party + (for decisions) "
        "decision_type + outcome. When True, every hit is the full PTAB "
        "record — large; prefer ``get_ptab`` for one.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search Patent Trial and Appeal Board (PTAB) records across AIA trials, ex parte appeals, and pre-AIA interferences.

    The PTAB is the USPTO administrative tribunal for AIA trials
    (IPR/PGR/CBM/DER), ex parte appeals from examiner rejections, and
    pre-AIA interferences. The ``type`` parameter picks which record kind
    to search; appeals and interferences are legally distinct from AIA
    trials. Returns a lean stub per hit by default; pass ``full=True`` for
    the upstream PTAB record per hit.

    Related tools: get_ptab, list_ptab_children, download_ptab_trial_documents,
    download_ptab_trial_decisions, download_ptab_appeal_decisions,
    download_ptab_interference_decisions.
    """
    key = type.strip().lower()
    method_name = _PTAB_SEARCH_METHOD.get(key)
    if method_name is None:
        from law_tools_core.exceptions import ValidationError

        raise ValidationError(f"type must be one of {sorted(_PTAB_SEARCH_METHOD)}; got {type!r}")
    async with UsptoOdpClient() as client:
        method = getattr(client, method_name)
        result = await method(query=query, limit=limit, offset=offset)

    dumped = _dump(result) if hasattr(result, "model_dump") else result
    bag_key = _PTAB_BAG_KEY[key]
    raw_items = list(dumped.get(bag_key) or [])
    total = dumped.get("count")
    items = raw_items if full else [_stub_ptab_record(r, key) for r in raw_items]
    shown = len(items)
    more = bool(total and shown + offset < int(total))
    summary_total = f"{shown} of {total} hits" if total else f"{shown} hits"
    return ListEnvelope[dict](
        summary=f"PTAB {key} — `{query}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_odp_provenance(f"/api/v1/ptab/{key.replace('_', '-')}s/search"),
    )


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
        str | list[str],
        "Trial number for 'proceeding' (e.g. 'IPR2024-00001'); document "
        "identifier for all other types. Pass a list for portfolio workflows; "
        "the response is always a ListEnvelope.",
    ],
) -> ListEnvelope[dict]:
    """Fetch one or more Patent Trial and Appeal Board (PTAB) records — proceeding, decision, or document — by identifier.

    The PTAB is the USPTO administrative tribunal for AIA trials, ex parte
    appeals, and pre-AIA interferences. The ``type`` parameter selects the
    record kind. Accepts either a single identifier or a list (§5.4) and
    fans out with bounded concurrency; order matches the input.

    Related tools: search_ptab, list_ptab_children, download_ptab_trial_documents,
    download_ptab_trial_decisions, download_ptab_appeal_decisions,
    download_ptab_interference_decisions.
    """
    key = type.strip().lower()
    if key not in _PTAB_GET_METHOD:
        from law_tools_core.exceptions import ValidationError

        raise ValidationError(f"type must be one of {sorted(_PTAB_GET_METHOD)}; got {type!r}")
    method_name, _id_kind = _PTAB_GET_METHOD[key]
    ids = [identifier] if isinstance(identifier, str) else list(identifier)
    if not ids:
        from law_tools_core.exceptions import ValidationError

        raise ValidationError("get_ptab requires at least one identifier")

    semaphore = asyncio.Semaphore(_PTAB_FANOUT_CONCURRENCY)

    async def _fetch_one(client: UsptoOdpClient, ident: str) -> dict:
        async with semaphore:
            method = getattr(client, method_name)
            return _dump(await method(ident))  # type: ignore[return-value]

    async with UsptoOdpClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, i) for i in ids])

    if len(results) == 1:
        first = _extract_ptab_first(results[0], key)
        summary = _summarize_ptab(first, key)
    else:
        summary = f"Fetched {len(results)} PTAB {key} records: " + ", ".join(ids)

    base_path = f"/api/v1/ptab/{key.replace('_', '-')}s"
    path = base_path + ("/" + ids[0] if len(ids) == 1 else "")
    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_odp_provenance(path),
    )


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
) -> ListEnvelope[dict]:
    """List Patent Trial and Appeal Board (PTAB) children — decisions or documents attached to a parent record.

    The parent can be an AIA trial number, a USPTO application number (for
    ex parte appeals), or a pre-AIA interference number. For trials, pass
    ``include='both'`` to enumerate decisions and party filings in one
    call. Use the document identifiers to fetch full records via
    ``get_ptab`` or PDFs via the ``download_ptab_*`` family.

    Related tools: search_ptab, get_ptab, download_ptab_trial_documents,
    download_ptab_trial_decisions, download_ptab_appeal_decisions,
    download_ptab_interference_decisions.
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
            items: list[dict] = []
            if inc in ("decisions", "both"):
                decisions = _dump(await client.get_trial_decisions_by_trial(parent_identifier))
                for entry in decisions.get("patentTrialDocumentDataBag") or []:
                    items.append(
                        _stub_ptab_record(
                            {**entry, "trialNumber": parent_identifier}, "trial_decision"
                        )
                    )
            if inc in ("documents", "both"):
                documents = _dump(await client.get_trial_documents_by_trial(parent_identifier))
                for entry in documents.get("patentTrialDocumentDataBag") or []:
                    items.append(
                        _stub_ptab_record(
                            {**entry, "trialNumber": parent_identifier}, "trial_document"
                        )
                    )
            summary = (
                f"PTAB trial {parent_identifier} — {len(items)} {inc} record"
                f"{'s' if len(items) != 1 else ''}."
            )
            return ListEnvelope[dict](
                summary=summary,
                items=items,
                provenance=_odp_provenance(f"/api/v1/ptab/trials/{parent_identifier}/{inc}"),
            )
        if pt == "application":
            if inc not in ("decisions",):
                raise ValidationError("parent_type='application' only supports include='decisions'")
            result = _dump(await client.get_appeal_decisions_by_number(parent_identifier))
            items = [
                _stub_ptab_record(entry, "appeal_decision")
                for entry in result.get("patentAppealDataBag") or []
            ]
            summary = (
                f"PTAB ex parte appeal decisions for application {parent_identifier} "
                f"— {len(items)} decision{'s' if len(items) != 1 else ''}."
            )
            return ListEnvelope[dict](
                summary=summary,
                items=items,
                provenance=_odp_provenance(
                    f"/api/v1/ptab/appeals/by-application/{parent_identifier}"
                ),
            )
        if pt == "interference":
            if inc not in ("decisions",):
                raise ValidationError(
                    "parent_type='interference' only supports include='decisions'"
                )
            result = _dump(await client.get_interference_decisions_by_number(parent_identifier))
            items = [
                _stub_ptab_record(entry, "interference_decision")
                for entry in result.get("patentInterferenceDataBag") or []
            ]
            summary = (
                f"PTAB interference decisions for {parent_identifier} "
                f"— {len(items)} decision{'s' if len(items) != 1 else ''}."
            )
            return ListEnvelope[dict](
                summary=summary,
                items=items,
                provenance=_odp_provenance(
                    f"/api/v1/ptab/interferences/by-number/{parent_identifier}"
                ),
            )
        raise ValidationError(
            f"parent_type must be 'trial', 'application', or 'interference'; got {parent_type!r}"
        )


# ---------------------------------------------------------------------------
# PTAB bulk downloads (container-scoped)
# ---------------------------------------------------------------------------
#
# Single-document PTAB downloads were removed in favor of the container-bulk
# tools below. The ``ptab/documents/{id}`` fetcher registration above (see
# ``_fetch_ptab_document``) stays so any signed URLs minted before the
# removal still resolve from cache, and so the bulk tool's ``fetch_with_cache``
# path keeps working.


_PTAB_TRIAL_DOCUMENTS_CAP = 100
_PTAB_TRIAL_DECISIONS_CAP = 50
_PTAB_APPEAL_DECISIONS_CAP = 50
_PTAB_INTERFERENCE_DECISIONS_CAP = 50


def _ptab_parse_date(value: str | None, *, field_name: str):
    if not value:
        return None
    from datetime import date as _date

    from law_tools_core.exceptions import ValidationError

    try:
        return _date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be ISO date YYYY-MM-DD; got {value!r}") from exc


async def _ptab_download_pdf(file_download_uri: str) -> bytes:
    """Download a PTAB PDF given a ``fileDownloadURI`` from any list/get response."""
    async with PtabTrialsClient() as client:
        uri_path = urlparse(str(file_download_uri)).path
        return await client.download_document_pdf(uri_path)


async def _run_ptab_bulk(
    *,
    candidates: list[dict],
    container_label: str,
    container_metadata: dict,
    cap: int,
    container_kind: str,
) -> dict:
    """Shared bulk-download pipeline for the 4 PTAB tools.

    Each candidate dict must carry: ``item_id``, ``resource_path``,
    ``file_download_uri``, ``filename``, and any extra metadata for the
    manifest. Filtering (by item_ids / date) is done by the caller before
    this runs.
    """
    from law_tools_core.exceptions import ValidationError
    from law_tools_core.mcp.downloads import (
        BulkItem,
        download_bulk_tool_result,
        fetch_with_cache,
    )

    if not candidates:
        raise ValidationError(
            f"No PTAB {container_kind} match the given filters for {container_label!r}."
        )
    if len(candidates) > cap:
        raise ValidationError(
            f"PTAB {container_kind} for {container_label!r} has {len(candidates)} items "
            f"matching the filters; max {cap} per call. Narrow with item_ids or "
            f"date filters (after/before)."
        )

    # Fetch-internal hints (URI + target filename) live in a side dict keyed
    # by item_id so they don't pollute the BulkItem.metadata surfaced in the
    # manifest, and so they can't shadow kwargs like ``filename`` when the
    # n=1 short-circuit splats metadata into ``download_response``.
    _fetch_plan: dict[str, tuple[str, str]] = {}
    bulk_items = []
    _INTERNAL_KEYS = {"resource_path", "item_id", "filename", "file_download_uri"}
    for cand in candidates:
        manifest_metadata = {k: v for k, v in cand.items() if k not in _INTERNAL_KEYS}
        bulk_items.append(
            BulkItem(
                item_id=cand["item_id"],
                resource_path=cand["resource_path"],
                metadata=manifest_metadata,
            )
        )
        _fetch_plan[cand["item_id"]] = (cand["file_download_uri"], cand["filename"])

    async def _fetcher(item: BulkItem) -> tuple[bytes, str]:
        uri, filename = _fetch_plan[item.item_id]

        async def _inline() -> tuple[bytes, str]:
            return await _ptab_download_pdf(uri), filename

        return await fetch_with_cache(item.resource_path, fetcher=_inline)

    return await download_bulk_tool_result(
        bulk_items,
        _fetcher,
        container_label=container_label,
        container_metadata=container_metadata,
        content_type_single="application/pdf",
    )


def _extract_trial_bag_entry(entry) -> dict | None:
    """Pull (doc_id, URI, metadata) out of a PtabTrialDocument or PtabTrialDecision entry."""
    dd = getattr(entry, "documentData", None)
    if not dd:
        return None
    doc_id = getattr(dd, "documentIdentifier", None)
    uri = getattr(dd, "fileDownloadURI", None) or getattr(dd, "downloadURI", None)
    if not doc_id or not uri:
        return None
    filing_date = getattr(dd, "documentFilingDate", None)
    decision = getattr(entry, "decisionData", None)
    if decision is not None and not filing_date:
        filing_date = getattr(decision, "decisionIssueDate", None)
    return {
        "item_id": str(doc_id),
        "file_download_uri": str(uri),
        "document_filing_date": filing_date,
        "document_title": getattr(dd, "documentTitleText", None)
        or getattr(dd, "documentName", None),
        "document_type": getattr(dd, "documentTypeDescriptionText", None),
        "document_number": getattr(dd, "documentNumber", None),
        "filing_party_category": getattr(dd, "filingPartyCategory", None),
        "decision_type": getattr(decision, "decisionTypeCategory", None) if decision else None,
    }


def _filter_by_date(
    candidates: list[dict],
    *,
    date_key: str,
    after,
    before,
) -> list[dict]:
    """Keep only candidates whose ``date_key`` value is within [after, before]."""
    if after is None and before is None:
        return candidates
    from datetime import date as _date

    out = []
    for c in candidates:
        raw = c.get(date_key)
        parsed: _date | None
        try:
            parsed = _date.fromisoformat((raw or "")[:10]) if raw else None
        except ValueError:
            parsed = None
        if after and (parsed is None or parsed < after):
            continue
        if before and (parsed is None or parsed > before):
            continue
        out.append(c)
    return out


@uspto_mcp.tool(annotations=READ_ONLY)
async def download_ptab_trial_documents(
    trial_number: Annotated[
        str,
        "AIA trial number (e.g. 'IPR2024-00001', 'PGR2023-00012', 'CBM2019-00001'). "
        "Every document filed by the parties in this trial is a candidate.",
    ],
    item_ids: Annotated[
        list[str] | None,
        "Specific document_identifier values from list_ptab_children(parent_type='trial', "
        "include='documents'). None means 'all documents matching the other filters'.",
    ] = None,
    after: Annotated[
        str | None,
        "Include only documents filed on or after this date (ISO YYYY-MM-DD).",
    ] = None,
    before: Annotated[
        str | None,
        "Include only documents filed on or before this date (ISO YYYY-MM-DD).",
    ] = None,
):
    """Bulk-download party filings for one AIA trial.

    Returns per-document ``ResourceLink``s (one per matching paper)
    plus a structured manifest. Resource-aware MCP clients fetch the
    per-doc bytes via ``resources/read``; the response also includes a
    zip ``download_url`` for HTTP-fallback clients. Fetches everything
    the parties filed in the trial — petitions, responses, motions,
    replies, exhibits, depositions, notices — all of it. Cap: 100
    documents per call. Big IPRs with many exhibits may need narrowing
    via ``item_ids`` (use ``list_ptab_children`` to enumerate) or date
    filters.

    For board-issued papers (institution decisions, FWDs, orders), use
    ``download_ptab_trial_decisions`` instead.

    Related tools: search_ptab, get_ptab, list_ptab_children,
    download_ptab_trial_decisions.
    """
    after_d = _ptab_parse_date(after, field_name="after")
    before_d = _ptab_parse_date(before, field_name="before")

    async with UsptoOdpClient() as client:
        response = await client.get_trial_documents_by_trial(trial_number)
    bag = getattr(response, "patentTrialDocumentDataBag", None) or []

    id_set = set(item_ids) if item_ids else None
    candidates: list[dict] = []
    for entry in bag:
        extracted = _extract_trial_bag_entry(entry)
        if extracted is None:
            continue
        if id_set and extracted["item_id"] not in id_set:
            continue
        extracted["resource_path"] = f"ptab/documents/{extracted['item_id']}"
        extracted["filename"] = _ptab_document_filename(
            proceeding_number=trial_number,
            entry=extracted,
        )
        candidates.append(extracted)

    candidates = _filter_by_date(
        candidates, date_key="document_filing_date", after=after_d, before=before_d
    )

    return await _run_ptab_bulk(
        candidates=candidates,
        container_label=f"{trial_number}_trial_documents",
        container_metadata={"container": trial_number, "trial_number": trial_number},
        cap=_PTAB_TRIAL_DOCUMENTS_CAP,
        container_kind="trial documents",
    )


@uspto_mcp.tool(annotations=READ_ONLY)
async def download_ptab_trial_decisions(
    trial_number: Annotated[
        str,
        "AIA trial number (e.g. 'IPR2024-00001'). Every decision issued "
        "by the board in this trial is a candidate.",
    ],
    item_ids: Annotated[list[str] | None, "Specific document_identifier values."] = None,
    after: Annotated[str | None, "Only decisions issued on or after (ISO YYYY-MM-DD)."] = None,
    before: Annotated[str | None, "Only decisions issued on or before (ISO YYYY-MM-DD)."] = None,
):
    """Bulk-download board decisions for one AIA trial.

    Returns a structured manifest plus a zip ``download_url`` for
    HTTP-fallback clients. Institution decisions, scheduling orders,
    FWDs, board orders — papers issued by the board itself. Cap: 50
    per call. For party filings (petitions, responses, exhibits) use
    ``download_ptab_trial_documents``.

    Note: PTAB decision PDFs are reachable only through the zip
    ``download_url`` — per-decision MCP resource URIs are not exposed
    for this category (no registered single-doc fetcher). Use this in
    URL-comfortable clients; in CoWork-style allowlist-gated setups,
    fall back to ``download_ptab_trial_documents`` for the party
    filings, which do surface per-doc resource links.

    Related tools: search_ptab, get_ptab, list_ptab_children,
    download_ptab_trial_documents.
    """
    after_d = _ptab_parse_date(after, field_name="after")
    before_d = _ptab_parse_date(before, field_name="before")

    async with UsptoOdpClient() as client:
        response = await client.get_trial_decisions_by_trial(trial_number)
    bag = getattr(response, "patentTrialDocumentDataBag", None) or []

    id_set = set(item_ids) if item_ids else None
    candidates: list[dict] = []
    for entry in bag:
        extracted = _extract_trial_bag_entry(entry)
        if extracted is None:
            continue
        if id_set and extracted["item_id"] not in id_set:
            continue
        extracted["resource_path"] = f"ptab/trial-decisions/{extracted['item_id']}"
        extracted["filename"] = _ptab_document_filename(
            proceeding_number=trial_number,
            entry=extracted,
            fallback_code=extracted.get("decision_type"),
        )
        candidates.append(extracted)

    candidates = _filter_by_date(
        candidates, date_key="document_filing_date", after=after_d, before=before_d
    )

    return await _run_ptab_bulk(
        candidates=candidates,
        container_label=f"{trial_number}_trial_decisions",
        container_metadata={"container": trial_number, "trial_number": trial_number},
        cap=_PTAB_TRIAL_DECISIONS_CAP,
        container_kind="trial decisions",
    )


@uspto_mcp.tool(annotations=READ_ONLY)
async def download_ptab_appeal_decisions(
    application_number: Annotated[
        str,
        "USPTO application number (8+ digits; appeals attach to applications, not trial "
        "numbers). Examples: '16123456'. Every ex parte appeal decision issued for this "
        "application is a candidate.",
    ],
    item_ids: Annotated[list[str] | None, "Specific document_identifier values."] = None,
    after: Annotated[str | None, "Only decisions issued on or after (ISO YYYY-MM-DD)."] = None,
    before: Annotated[str | None, "Only decisions issued on or before (ISO YYYY-MM-DD)."] = None,
):
    """Bulk-download ex parte appeal decisions for one USPTO application.

    Returns a structured manifest plus a zip ``download_url`` for
    HTTP-fallback clients. Appeals are a distinct vehicle from AIA
    trials. Cap: 50 per call. Use
    ``list_ptab_children(parent_type='application')`` to preview what's
    available.

    Note: per-decision MCP resource URIs are not exposed for this
    category — fetch the zip via ``download_url``.

    Related tools: search_ptab, get_ptab, list_ptab_children, get_application.
    """
    after_d = _ptab_parse_date(after, field_name="after")
    before_d = _ptab_parse_date(before, field_name="before")

    async with UsptoOdpClient() as client:
        response = await client.get_appeal_decisions_by_number(application_number)
    bag = getattr(response, "patentAppealDataBag", None) or []

    id_set = set(item_ids) if item_ids else None
    candidates: list[dict] = []
    for entry in bag:
        dd = getattr(entry, "documentData", None)
        if not dd:
            continue
        doc_id = getattr(dd, "documentIdentifier", None)
        uri = getattr(dd, "fileDownloadURI", None) or getattr(dd, "downloadURI", None)
        if not doc_id or not uri:
            continue
        if id_set and doc_id not in id_set:
            continue
        decision = getattr(entry, "decisionData", None)
        candidates.append(
            {
                "item_id": str(doc_id),
                "file_download_uri": str(uri),
                "document_filing_date": getattr(dd, "documentFilingDate", None),
                "decision_issue_date": getattr(decision, "decisionIssueDate", None)
                if decision
                else None,
                "decision_type": getattr(decision, "decisionTypeCategory", None)
                if decision
                else None,
                "appeal_outcome": getattr(decision, "appealOutcomeCategory", None)
                if decision
                else None,
                "document_type": getattr(dd, "documentTypeDescriptionText", None),
                "document_name": getattr(dd, "documentName", None),
                "resource_path": f"ptab/appeal-decisions/{doc_id}",
                "filename": _ptab_decision_filename(
                    container=application_number,
                    doc_id=str(doc_id),
                    code=getattr(decision, "decisionTypeCategory", None) if decision else None,
                    date=getattr(decision, "decisionIssueDate", None)
                    if decision
                    else getattr(dd, "documentFilingDate", None),
                ),
            }
        )

    candidates = _filter_by_date(
        candidates, date_key="decision_issue_date", after=after_d, before=before_d
    )

    return await _run_ptab_bulk(
        candidates=candidates,
        container_label=f"{application_number}_appeal_decisions",
        container_metadata={
            "container": application_number,
            "application_number": application_number,
        },
        cap=_PTAB_APPEAL_DECISIONS_CAP,
        container_kind="appeal decisions",
    )


@uspto_mcp.tool(annotations=READ_ONLY)
async def download_ptab_interference_decisions(
    interference_number: Annotated[
        str,
        "Pre-AIA interference number. Every decision issued in this interference is a candidate.",
    ],
    item_ids: Annotated[list[str] | None, "Specific document_identifier values."] = None,
    after: Annotated[str | None, "Only decisions issued on or after (ISO YYYY-MM-DD)."] = None,
    before: Annotated[str | None, "Only decisions issued on or before (ISO YYYY-MM-DD)."] = None,
):
    """Bulk-download decisions for one pre-AIA interference.

    Returns a structured manifest plus a zip ``download_url`` for
    HTTP-fallback clients. Interferences are a legacy tribunal distinct
    from AIA trials and appeals. Cap: 50 per call.

    Note: per-decision MCP resource URIs are not exposed for this
    category — fetch the zip via ``download_url``.

    Related tools: search_ptab, get_ptab, list_ptab_children.
    """
    after_d = _ptab_parse_date(after, field_name="after")
    before_d = _ptab_parse_date(before, field_name="before")

    async with UsptoOdpClient() as client:
        response = await client.get_interference_decisions_by_number(interference_number)
    bag = getattr(response, "patentInterferenceDataBag", None) or []

    id_set = set(item_ids) if item_ids else None
    candidates: list[dict] = []
    for entry in bag:
        dd = getattr(entry, "decisionDocumentData", None) or getattr(entry, "documentData", None)
        if not dd:
            continue
        doc_id = getattr(dd, "documentIdentifier", None)
        uri = getattr(dd, "fileDownloadURI", None)
        if not doc_id or not uri:
            continue
        if id_set and doc_id not in id_set:
            continue
        candidates.append(
            {
                "item_id": str(doc_id),
                "file_download_uri": str(uri),
                "decision_issue_date": getattr(dd, "decisionIssueDate", None),
                "decision_type": getattr(dd, "decisionTypeCategory", None),
                "interference_outcome": getattr(dd, "interferenceOutcomeCategory", None),
                "document_title": getattr(dd, "documentTitleText", None)
                or getattr(dd, "documentName", None),
                "resource_path": f"ptab/interference-decisions/{doc_id}",
                "filename": _ptab_decision_filename(
                    container=interference_number,
                    doc_id=str(doc_id),
                    code=getattr(dd, "decisionTypeCategory", None),
                    date=getattr(dd, "decisionIssueDate", None),
                ),
            }
        )

    candidates = _filter_by_date(
        candidates, date_key="decision_issue_date", after=after_d, before=before_d
    )

    return await _run_ptab_bulk(
        candidates=candidates,
        container_label=f"{interference_number}_interference_decisions",
        container_metadata={
            "container": interference_number,
            "interference_number": interference_number,
        },
        cap=_PTAB_INTERFERENCE_DECISIONS_CAP,
        container_kind="interference decisions",
    )


def _ptab_document_filename(
    *,
    proceeding_number: str,
    entry: dict,
    fallback_code: str | None = None,
) -> str:
    """Build a filename for a PTAB trial doc/decision via the shared ptab_document helper."""
    from law_tools_core.filenames import ptab_document as _ptab_name

    return _ptab_name(
        proceeding_number=proceeding_number,
        filing_date=entry.get("document_filing_date"),
        document_code=entry.get("document_type") or fallback_code,
        document_identifier=entry["item_id"],
    )


def _ptab_decision_filename(
    *,
    container: str,
    doc_id: str,
    code: str | None,
    date: str | None,
) -> str:
    """Build a filename for an appeal/interference decision."""
    from law_tools_core.filenames import ptab_document as _ptab_name

    return _ptab_name(
        proceeding_number=container,
        filing_date=date,
        document_code=code,
        document_identifier=doc_id,
    )


# ---------------------------------------------------------------------------
# Petitions
# ---------------------------------------------------------------------------


_PETITION_FANOUT_CONCURRENCY = 5


def _stub_petition(record: dict) -> dict:
    """Lean projection (§5.5) of a USPTO petition decision record."""
    return {
        "petition_decision_record_identifier": record.get("petitionDecisionRecordIdentifier"),
        "application_number": record.get("applicationNumberText"),
        "patent_number": record.get("patentNumber"),
        "decision_date": record.get("decisionDate"),
        "decision_type_code": record.get("decisionTypeCode"),
        "petition_type": record.get("decisionPetitionTypeCodeDescriptionText"),
        "deciding_office": record.get("finalDecidingOfficeName"),
        "applicant": record.get("firstApplicantName"),
        "invention_title": record.get("inventionTitle"),
        "petition_mail_date": record.get("petitionMailDate"),
    }


def _summarize_petition(record: dict) -> str:
    """One-line Markdown summary of a single petition decision record."""
    pid = record.get("petitionDecisionRecordIdentifier") or "(no id)"
    appl = record.get("applicationNumberText") or "(no appl#)"
    pt = record.get("decisionPetitionTypeCodeDescriptionText") or "(no type)"
    dt = record.get("decisionTypeCode") or "(no decision)"
    decided = record.get("decisionDate") or "?"
    office = record.get("finalDecidingOfficeName") or ""
    head = f"**USPTO petition {pid}** — {pt}"
    line = f"Application {appl}. Decision: {dt} on {decided}"
    if office:
        line += f" by {office}"
    line += "."
    return f"{head}\n{line}"


def _extract_petition_first(payload: dict) -> dict:
    """Pull the first record out of a get_petition response payload."""
    bag = payload.get("petitionDecisionDataBag")
    if bag and isinstance(bag, list):
        return bag[0]
    return payload


@uspto_mcp.tool(annotations=READ_ONLY)
async def search_petitions(
    query: Annotated[str, "Search query for petition decisions"],
    limit: Annotated[int, "Maximum number of results"] = 25,
    offset: Annotated[int, "Result offset for pagination"] = 0,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: petition "
        "decision identifier, application number, patent number, decision "
        "date and type, petition type, deciding office, applicant, "
        "invention title. When True, every hit carries the full ODP "
        "petition decision record (statutes/rules bags, issue text, "
        "ingestion timestamps, etc.).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search USPTO petition decisions across the Open Data Portal.

    Petition decisions are USPTO rulings on procedural and substantive
    petitions filed during prosecution (e.g., revival, withdrawal of
    holding of abandonment, prioritized examination). Returns lean stubs
    by default. Use ``get_petition`` for a full record by decision
    identifier; petitions attach to applications, so ``search_applications``
    and ``get_application`` give you the underlying prosecution context.

    Related tools: get_petition, search_applications, get_application.
    """
    async with UsptoOdpClient() as client:
        result = await client.search_petitions(q=query, limit=limit, offset=offset)

    dumped = _dump(result) if hasattr(result, "model_dump") else result
    raw_items = list(dumped.get("petitionDecisionDataBag") or [])
    total = dumped.get("count")
    items = raw_items if full else [_stub_petition(r) for r in raw_items]
    shown = len(items)
    more = bool(total and shown + offset < int(total))
    summary_total = f"{shown} of {total} hits" if total else f"{shown} hits"
    return ListEnvelope[dict](
        summary=f"USPTO petitions — `{query}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_odp_provenance("/api/v1/patent/petitions/search"),
    )


@uspto_mcp.tool(annotations=READ_ONLY)
async def get_petition(
    petition_number: Annotated[
        str | list[str],
        "USPTO petition decision record identifier (from search_petitions), or "
        "a list of such identifiers for portfolio workflows. The response "
        "shape stays a ListEnvelope whether you pass one or many.",
    ],
) -> ListEnvelope[dict]:
    """Get one or more USPTO petition decision records by identifier.

    Accepts either a single petition decision identifier or a list (§5.4);
    the response is always a ListEnvelope. Bounded concurrent fan-out
    internally; order matches the input.

    Use ``search_petitions`` to discover decision identifiers, and
    ``get_application`` for the underlying prosecution context (each
    petition attaches to an application).

    Related tools: search_petitions, search_applications, get_application.
    """
    ids = [petition_number] if isinstance(petition_number, str) else list(petition_number)
    if not ids:
        from law_tools_core.exceptions import ValidationError

        raise ValidationError("get_petition requires at least one identifier")

    semaphore = asyncio.Semaphore(_PETITION_FANOUT_CONCURRENCY)

    async def _fetch_one(client: UsptoOdpClient, pid: str) -> dict:
        async with semaphore:
            return _dump(await client.get_petition(pid))  # type: ignore[return-value]

    async with UsptoOdpClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, p) for p in ids])

    if len(results) == 1:
        first = _extract_petition_first(results[0])
        summary = _summarize_petition(first)
    else:
        summary = f"Fetched {len(results)} USPTO petition decisions: " + ", ".join(ids)

    path = "/api/v1/patent/petitions" + ("/" + ids[0] if len(ids) == 1 else "")
    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_odp_provenance(path),
    )


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
