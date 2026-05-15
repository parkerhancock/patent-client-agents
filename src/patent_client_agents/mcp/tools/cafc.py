"""U.S. Court of Appeals for the Federal Circuit (CAFC) MCP tools.

Search opinions, classify as patent cases, and serve opinion PDFs via
the shared ``pca://cafc/...`` download channel.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_proxy``, ``update_strategy=live_proxy`` (per
``coverage/sources.yaml``). Live-proxy substantive-law connectors carry
the standard provenance fields only — ``corpus_synced_at`` /
``corpus_version`` are reserved for ``mcp_local`` corpora.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.filenames import cafc_opinion as _cafc_name
from law_tools_core.mcp import download_response, register_source
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.cafc import CAFCClient, PatentClassifier

cafc_mcp = FastMCP("CAFC")


# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). CAFC is substantive
# law served by live proxy (§4 / coverage/sources.yaml), so provenance
# carries the standard fields only — no corpus_synced_at.
# ──────────────────────────────────────────────────────────────────────

_CAFC_BASE = "https://www.cafc.uscourts.gov"
_CAFC_NAME = "U.S. Court of Appeals for the Federal Circuit"


def _cafc_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}``."""
    return make_provenance(
        source_url=f"{_CAFC_BASE}{path}",
        source_name=_CAFC_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict (or pass through dicts).

    Every caller passes a Pydantic model from the upstream client; the
    fallback exists to be defensive if a dict slips through. Typed as
    ``dict[str, Any]`` so call sites can use ``.get(...)`` without
    per-call narrowing.
    """
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump())  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


def _stub_opinion(record: dict) -> dict:
    """Lean projection of a CAFC opinion row (§5.5).

    Picks the scalar fields an agent uses to triage hits — appeal
    number, short case name, release date, origin code, document type
    (OPINION / ORDER / RULE 36 JUDGMENT), precedential status, patent
    classification flag, and the public PDF URL.
    """
    return {
        "appeal_number": record.get("appeal_number"),
        "case_name_short": record.get("case_name_short") or record.get("case_name"),
        "release_date": record.get("release_date"),
        "origin": record.get("origin"),
        "document_type": record.get("document_type"),
        "precedential_status": record.get("precedential_status"),
        "is_patent_case": record.get("is_patent_case"),
        "pdf_url": record.get("pdf_url"),
    }


# ---------------------------------------------------------------------------
# Download fetcher (registered on import)
# ---------------------------------------------------------------------------


async def _fetch_cafc_opinion(path: str) -> tuple[bytes, str]:
    """Fetch a CAFC opinion PDF. Path: ``{appeal_number}``."""
    appeal_number = path.strip("/")
    async with CAFCClient() as client:
        opinions = await client.search(query=appeal_number, max_results=20)
        match = None
        for o in opinions:
            if o.appeal_number and appeal_number in o.appeal_number:
                match = o
                break
        if match is None:
            raise ValueError(f"No CAFC opinion found for {appeal_number}")
        pdf_bytes = await client.download_pdf(match)
        return pdf_bytes, f"cafc_{appeal_number}.pdf"


register_source("cafc/opinions", _fetch_cafc_opinion, "application/pdf")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@cafc_mcp.tool(annotations=READ_ONLY)
async def search_cafc_opinions(
    query: Annotated[str | None, "Search text to filter CAFC opinions"] = None,
    patent_only: Annotated[bool, "Only return patent-related opinions"] = False,
    limit: Annotated[int, "Maximum number of results"] = 25,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: appeal "
        "number, short case name, release date, origin, document type, "
        "precedential status, patent classification, PDF URL. When True, "
        "each hit carries the full CAFCOpinion record (file_path, "
        "patent_confidence, patent_keywords, etc.).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search U.S. Court of Appeals for the Federal Circuit opinions and orders.

    Free-text search across the upstream DataTables index — passes ``query``
    to the search field rather than filtering a paginated fetch client-side.
    ``patent_only=True`` runs the local PatentClassifier over case names.
    Returns lean stubs by default so an agent can triage hits; pass
    ``full=True`` for the upstream row shape. Use ``download_cafc_pdf`` with
    an appeal number to pull a specific opinion PDF.

    Related tools: search_cafc_patent_opinions, download_cafc_pdf.
    """
    async with CAFCClient() as client:
        # Pass query through to the upstream DataTables search field.
        # Filtering client-side over a paginated fetch effectively
        # filtered only the most recent ``limit`` rows and almost always
        # returned 0 hits — the upstream search is what actually finds
        # matches across the full corpus.
        opinions = await client.search(query=query, max_results=limit)
        if patent_only:
            classifier = PatentClassifier()
            opinions = [o for o in opinions if classifier.classify(o.case_name)[0]]

    dumped = [_dump(o) for o in opinions]
    items = dumped if full else [_stub_opinion(r) for r in dumped]  # type: ignore[arg-type]

    query_label = f"`{query}`" if query else "(recent opinions)"
    scope = " (patent only)" if patent_only else ""
    return ListEnvelope[dict](
        summary=f"CAFC opinions — {query_label}{scope}: {len(items)} hits.",
        items=items,
        provenance=_cafc_provenance("/home/case-information/opinions-orders/"),
    )


@cafc_mcp.tool(annotations=READ_ONLY)
async def search_cafc_patent_opinions(
    date_from: Annotated[str | None, "Start date (YYYY-MM-DD) to filter opinions"] = None,
    date_to: Annotated[str | None, "End date (YYYY-MM-DD) to filter opinions"] = None,
    max_results: Annotated[int, "Maximum number of results"] = 25,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: appeal "
        "number, short case name, release date, origin, document type, "
        "precedential status, patent classification, PDF URL. When True, "
        "each hit carries the full CAFCOpinion record.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search U.S. Court of Appeals for the Federal Circuit opinions from patent-relevant origins.

    Filters to opinions whose origin is PTO, DCT, ITC, or CFC — the four
    paths that bring patent cases to the Federal Circuit. Optional date
    range narrows the window. Returns lean stubs by default; pass
    ``full=True`` for the upstream row shape. Use ``download_cafc_pdf``
    with an appeal number to pull a specific opinion PDF.

    Related tools: search_cafc_opinions, download_cafc_pdf.
    """
    from datetime import date as date_type

    async with CAFCClient() as client:
        kwargs: dict = {"max_results": max_results}
        if date_from:
            kwargs["date_from"] = date_type.fromisoformat(date_from)
        if date_to:
            kwargs["date_to"] = date_type.fromisoformat(date_to)
        opinions = await client.search_patent_opinions(**kwargs)

    dumped = [_dump(o) for o in opinions]
    items = dumped if full else [_stub_opinion(r) for r in dumped]  # type: ignore[arg-type]

    range_bits: list[str] = []
    if date_from:
        range_bits.append(f"from {date_from}")
    if date_to:
        range_bits.append(f"to {date_to}")
    range_label = " ".join(range_bits) or "(no date range)"
    return ListEnvelope[dict](
        summary=f"CAFC patent opinions — {range_label}: {len(items)} hits.",
        items=items,
        provenance=_cafc_provenance("/home/case-information/opinions-orders/"),
    )


@cafc_mcp.tool(annotations=READ_ONLY)
async def download_cafc_pdf(
    appeal_number: Annotated[str, "CAFC appeal number (e.g. '2023-1234')"],
) -> dict:
    """Download a U.S. Court of Appeals for the Federal Circuit opinion PDF by appeal number.

    Returns a signed `download_url` (or `file_path` in local stdio mode) plus
    `filename`, `content_type`, `size_bytes`, `appeal_number`, `case_name`.

    Related tools: search_cafc_opinions, search_cafc_patent_opinions.
    """
    async with CAFCClient() as client:
        opinions = await client.search(query=appeal_number, max_results=20)
        match = None
        for o in opinions:
            if o.appeal_number and appeal_number in o.appeal_number:
                match = o
                break
        if match is None:
            raise ValueError(f"No CAFC opinion found for appeal number {appeal_number}")
        pdf_bytes = await client.download_pdf(match)

        native = PurePosixPath(match.file_path or "").name if match.file_path else ""
        if native.lower().endswith(".pdf"):
            filename = native
        else:
            filename = _cafc_name(
                appeal_number=match.appeal_number or appeal_number,
                opinion_type=(
                    "NONPRECEDENTIAL"
                    if (match.precedential_status or "").lower().startswith("nonpreced")
                    else match.document_type or "OPINION"
                ),
                date=(
                    f"{match.release_date.month}-{match.release_date.day}-{match.release_date.year}"
                    if match.release_date
                    else None
                ),
            )
        return await download_response(
            f"cafc/opinions/{appeal_number}",
            pdf_bytes,
            filename=filename,
            content_type="application/pdf",
            appeal_number=appeal_number,
            case_name=match.case_name,
        )


__all__ = ["cafc_mcp"]
