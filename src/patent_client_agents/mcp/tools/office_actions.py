"""USPTO Office Action MCP tools.

Search USPTO office action rejections, citations, full text, and enriched
citation metadata. Also fetch a single office action's full content by its
stable document identifier. Backed by the USPTO ODP office action endpoints
on ``api.uspto.gov`` (X-API-KEY auth).
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, encode_cursor, make_provenance
from law_tools_core.exceptions import NotFoundError, ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.uspto_office_actions import OfficeActionClient

office_actions_mcp = FastMCP("Office Actions")


# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). USPTO ODP office-action
# endpoints live under api.uspto.gov; this is a category-1 registered-IP
# proxy source, so Provenance does NOT carry corpus_synced_at / version.
# ──────────────────────────────────────────────────────────────────────

_USPTO_ODP_BASE = "https://api.uspto.gov"
_USPTO_OA_NAME = "USPTO Office Actions Dataset"


def _office_actions_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}``."""
    return make_provenance(
        source_url=f"{_USPTO_ODP_BASE}{path}",
        source_name=_USPTO_OA_NAME,
    )


# Map result_type → (client method, dataset path, lean projector).
_DATASET_PATHS = {
    "rejections": "/api/v1/patent/oa/oa_rejections/v2/records",
    "citations": "/api/v1/patent/oa/oa_citations/v2/records",
    "text": "/api/v1/patent/oa/oa_actions/v1/records",
    "enriched_citations": "/api/v1/patent/oa/enriched_cited_reference_metadata/v3/records",
}

_SEARCH_METHODS = {
    "rejections": "search_rejections",
    "citations": "search_citations",
    "text": "search_office_action_text",
    "enriched_citations": "search_enriched_citations",
}


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic record to a dict (or pass through dicts)."""
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump())  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


def _stub_rejection(rec: dict) -> dict:
    """Lean projection for a rejection record (§5.5)."""
    rej_types: list[str] = []
    if rec.get("has_rej_101"):
        rej_types.append("§101")
    if rec.get("has_rej_102"):
        rej_types.append("§102")
    if rec.get("has_rej_103"):
        rej_types.append("§103")
    if rec.get("has_rej_112"):
        rej_types.append("§112")
    if rec.get("has_rej_dp"):
        rej_types.append("DP")
    return {
        "document_identifier": rec.get("id"),
        "application_number": rec.get("patent_application_number"),
        "mail_date": rec.get("submission_date"),
        "document_code": rec.get("legacy_document_code_identifier"),
        "art_unit": rec.get("group_art_unit_number"),
        "rejection_types": rej_types,
        "legal_section_code": rec.get("legal_section_code"),
        "national_class": rec.get("national_class"),
    }


def _stub_citation(rec: dict) -> dict:
    """Lean projection for a citation record (§5.5)."""
    return {
        "document_identifier": rec.get("id"),
        "application_number": rec.get("patent_application_number"),
        "reference_identifier": rec.get("reference_identifier"),
        "parsed_reference_identifier": rec.get("parsed_reference_identifier"),
        "legal_section_code": rec.get("legal_section_code"),
        "examiner_cited": rec.get("examiner_cited_reference_indicator"),
        "art_unit": rec.get("group_art_unit_number"),
        "tech_center": rec.get("tech_center"),
    }


def _stub_text(rec: dict) -> dict:
    """Lean projection for an office-action text record (§5.5)."""
    return {
        "document_identifier": rec.get("id"),
        "application_number": rec.get("patent_application_number"),
        "mail_date": rec.get("submission_date"),
        "document_code": rec.get("legacy_document_code_identifier"),
        "invention_title": rec.get("invention_title"),
        "art_unit": rec.get("group_art_unit_number"),
        "patent_number": rec.get("patent_number"),
        "application_type_category": rec.get("application_type_category"),
    }


def _stub_enriched_citation(rec: dict) -> dict:
    """Lean projection for an enriched citation record (§5.5)."""
    return {
        "document_identifier": rec.get("id"),
        "application_number": rec.get("patent_application_number"),
        "cited_document_identifier": rec.get("cited_document_identifier"),
        "publication_number": rec.get("publication_number"),
        "inventor_name_text": rec.get("inventor_name_text"),
        "country_code": rec.get("country_code"),
        "kind_code": rec.get("kind_code"),
        "office_action_category": rec.get("office_action_category"),
        "office_action_date": rec.get("office_action_date"),
        "citation_category_code": rec.get("citation_category_code"),
        "npl_indicator": rec.get("npl_indicator"),
    }


_STUBS = {
    "rejections": _stub_rejection,
    "citations": _stub_citation,
    "text": _stub_text,
    "enriched_citations": _stub_enriched_citation,
}


def _summarize_office_action(record: dict) -> str:
    """One-line Markdown summary for a single office-action text record."""
    doc_id = record.get("id") or "(no id)"
    appl = record.get("patent_application_number") or "(no appl#)"
    code = record.get("legacy_document_code_identifier") or "?"
    mailed = record.get("submission_date") or "?"
    title = record.get("invention_title") or "(no title)"
    art_unit = record.get("group_art_unit_number") or "?"
    head = f"**Office action {doc_id}** — application {appl}, type {code}"
    line = f"Mailed {mailed}; art unit {art_unit}; title: {title}."
    return f"{head}\n{line}"


# Lucene-escape characters that have special meaning in Solr queries.
# Conservative list — sufficient for the alphanumeric document IDs USPTO
# emits, but defensive against any caller-supplied string.
_LUCENE_SPECIALS = r'+-&|!(){}[]^"~*?:\/'


def _escape_lucene(value: str) -> str:
    out: list[str] = []
    for ch in value:
        if ch in _LUCENE_SPECIALS:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


_OA_FANOUT_CONCURRENCY = 5


@office_actions_mcp.tool(annotations=READ_ONLY)
async def search_office_actions(
    criteria: Annotated[
        str,
        "Lucene query. Valid fields depend on result_type: "
        "  rejections → patentApplicationNumber, hasRej101, hasRej102, hasRej103, "
        "hasRej112, hasRejDP, legalSectionCode, nationalClass, groupArtUnitNumber, "
        "submissionDate, aliceIndicator, allowedClaimIndicator. "
        "  citations → patentApplicationNumber, referenceIdentifier, "
        "parsedReferenceIdentifier, legalSectionCode, examinerCitedReferenceIndicator, "
        "applicantCitedExaminerReferenceIndicator, groupArtUnitNumber, techCenter. "
        "  text → patentApplicationNumber, inventionTitle, submissionDate, "
        "legacyDocumentCodeIdentifier (CTNF/CTFR/NOA/…), groupArtUnitNumber, "
        "patentNumber, applicationTypeCategory. "
        "  enriched_citations → patentApplicationNumber, citedDocumentIdentifier, "
        "publicationNumber, inventorNameText, countryCode, kindCode, "
        "officeActionCategory, citationCategoryCode, officeActionDate, "
        "examinerCitedReferenceIndicator, nplIndicator, groupArtUnitNumber.",
    ],
    result_type: Annotated[
        str,
        "What to search: 'rejections' (per-claim rejection records with 101/102/103/112/"
        "DP indicators plus Alice/Bilski/Mayo/Myriad flags), 'citations' (prior-art "
        "references cited with examiner/applicant indicators), 'text' (full office-"
        "action body text with structured sections), or 'enriched_citations' (citations "
        "with inventor names, country/kind codes, and passage locations).",
    ] = "rejections",
    start: Annotated[int, "Result offset for pagination"] = 0,
    rows: Annotated[int, "Maximum results to return (max 100)"] = 25,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub (~8 scalars: identifier, "
        "application number, document code, mail date, rejection types or reference "
        "id, art unit, etc.). When True, each hit is the full Solr record — for "
        "'text', this includes the full bodyText and structured sections (large).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search USPTO office-action data (rejections, citations, text, or enriched citations).

    All four result types share the same Lucene ``criteria`` surface but
    accept different field names — see the ``criteria`` description for
    the valid fields per type. Returns lean stubs by default; pass
    ``full=True`` for the full Solr record per hit.

    For a single office action's full text by document identifier, use
    ``get_office_action`` instead.

    Related tools: get_office_action, search_applications, list_file_history,
    get_application.
    """
    rt = result_type.strip().lower()
    method_name = _SEARCH_METHODS.get(rt)
    if method_name is None:
        raise ValidationError(
            f"result_type must be one of {sorted(_SEARCH_METHODS)}; got {result_type!r}"
        )

    async with OfficeActionClient() as client:
        method = getattr(client, method_name)
        result = await method(criteria, start=start, rows=rows)

    dumped = _dump(result)
    raw_items = list(dumped.get("results") or [])
    total = int(dumped.get("num_found") or 0)
    shown = len(raw_items)

    if full:
        items: list[dict] = raw_items
    else:
        stub = _STUBS[rt]
        items = [stub(r) for r in raw_items]

    more = (start + shown) < total
    next_cursor = encode_cursor({"start": start + shown, "rows": rows}) if more else None

    summary_total = f"{shown} of {total} hits" if total else f"{shown} hits"
    return ListEnvelope[dict](
        summary=f"USPTO office actions ({rt}) — `{criteria}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=next_cursor,
        provenance=_office_actions_provenance(_DATASET_PATHS[rt]),
    )


@office_actions_mcp.tool(annotations=READ_ONLY)
async def get_office_action(
    document_identifier: Annotated[
        str | list[str],
        "Office-action document identifier (the Solr ``id`` field returned "
        "from ``search_office_actions``; e.g. 'oa001'). Pass a list for "
        "portfolio workflows; the response shape stays a ListEnvelope.",
    ],
) -> ListEnvelope[dict]:
    """Get one or more USPTO office actions in full — body text, sections, and metadata.

    Resolves each ``document_identifier`` against the ``oa_actions``
    Solr endpoint (the only office-action dataset that carries the full
    body text and structured sections). Use ``search_office_actions``
    with ``result_type='text'`` to discover document identifiers.

    Accepts either a single string or a list (§5.4); the response is
    always a ListEnvelope so the shape is stable. Bounded concurrent
    fan-out internally.

    Related tools: search_office_actions, search_applications,
    list_file_history, get_application.
    """
    ids = (
        [document_identifier] if isinstance(document_identifier, str) else list(document_identifier)
    )
    if not ids:
        raise ValidationError("get_office_action requires at least one document_identifier")

    semaphore = asyncio.Semaphore(_OA_FANOUT_CONCURRENCY)

    async def _fetch_one(client: OfficeActionClient, doc_id: str) -> dict | None:
        query = f"id:{_escape_lucene(doc_id)}"
        async with semaphore:
            response = await client.search_office_action_text(query, start=0, rows=1)
        dumped = _dump(response)
        results = list(dumped.get("results") or [])
        return results[0] if results else None

    async with OfficeActionClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, d) for d in ids])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [d for d, r in zip(ids, fetched, strict=True) if r is None]

    if len(ids) == 1:
        if not items:
            raise NotFoundError(
                f"Office action {ids[0]!r} not found. Use search_office_actions "
                f"with result_type='text' to discover valid document identifiers."
            )
        summary = _summarize_office_action(items[0])
        path = _DATASET_PATHS["text"]
    else:
        head = f"Fetched {len(items)} of {len(ids)} USPTO office actions."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")
        path = _DATASET_PATHS["text"]

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_office_actions_provenance(path),
    )
