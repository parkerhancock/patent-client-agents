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

import hashlib
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Annotated, Any, cast
from urllib.parse import urlsplit

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, decode_cursor, encode_cursor, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.filenames import cafc_opinion as _cafc_name
from mcp_data_core.mcp import download_response, register_source
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.cafc import CAFCClient, PatentClassifier
from patent_client_agents.cafc.models import CAFCOpinion

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


def _page_args(offset: int, limit: int, next_cursor: str | None) -> tuple[int, int]:
    if next_cursor is not None:
        try:
            cursor = decode_cursor(next_cursor)
            offset, limit = cursor["offset"], cursor["limit"]
        except (ValueError, KeyError) as exc:
            raise ValidationError("invalid CAFC next_cursor") from exc
    if type(offset) is not int or offset < 0:
        raise ValidationError("offset must be a non-negative integer")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValidationError("CAFC page size must be between 1 and 100")
    return offset, limit


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
        opinions = await client.search(query=appeal_number, max_results=100)
        matches = {
            o.pdf_url: o for o in opinions if o.appeal_number and appeal_number in o.appeal_number
        }
        if len(matches) != 1 or len(opinions) >= 100:
            raise ValidationError("Select exact document_url using download_cafc_pdf")
        match = next(iter(matches.values()))
        pdf_bytes = await client.download_pdf(match)
        return pdf_bytes, f"cafc_{appeal_number}.pdf"


register_source("cafc/opinions", _fetch_cafc_opinion, "application/pdf")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@cafc_mcp.tool(annotations=READ_ONLY)
async def search_cafc_opinions(
    query: Annotated[str | None, "Search text to filter CAFC opinions"] = None,
    patent_only: Annotated[
        bool, "Apply a heuristic case-name patent classifier to each source page"
    ] = False,
    limit: Annotated[int, "Maximum source rows per page (1-100)"] = 25,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: appeal "
        "number, short case name, release date, origin, document type, "
        "precedential status, patent classification, PDF URL. When True, "
        "each hit carries the full CAFCOpinion record (file_path, "
        "patent_confidence, patent_keywords, etc.).",
    ] = False,
    offset: Annotated[int, "Offset into the upstream filtered index"] = 0,
    next_cursor: Annotated[
        str | None, "Continuation from the previous page; overrides offset and page size"
    ] = None,
) -> ListEnvelope[dict]:
    """Search U.S. Court of Appeals for the Federal Circuit opinions and orders.

    Free-text search across the upstream DataTables index — passes ``query``
    to the search field rather than filtering a paginated fetch client-side.
    ``patent_only=True`` runs a heuristic PatentClassifier over case names;
    it is not complete patent-case coverage. Pages may have zero matching
    items while more_available remains true. Continue with next_cursor and
    the same query/patent_only filters; cursors are offsets, not snapshots.
    Returns lean stubs by default so an agent can triage hits; pass
    ``full=True`` for the upstream row shape. Use ``download_cafc_pdf`` with
    an appeal number to pull a specific opinion PDF.

    Related tools: search_cafc_patent_opinions, download_cafc_pdf.
    """
    offset, limit = _page_args(offset, limit, next_cursor)
    async with CAFCClient() as client:
        opinions = await client.search(query=query, max_results=limit + 1, offset=offset)
        more = len(opinions) > limit
        opinions = opinions[:limit]
        source_rows = len(opinions)
        if patent_only:
            classifier = PatentClassifier()
            opinions = [o for o in opinions if classifier.classify(o.case_name)[0]]

    dumped = [_dump(o) for o in opinions]
    items = dumped if full else [_stub_opinion(r) for r in dumped]  # type: ignore[arg-type]

    query_label = f"`{query}`" if query else "(recent opinions)"
    scope = " (patent only; heuristic case-name filter)" if patent_only else ""
    return ListEnvelope[dict](
        summary=(
            f"CAFC opinions — {query_label}{scope}: {len(items)} hits. "
            f"Inspected {source_rows} source rows at offset {offset}."
        ),
        items=items,
        more_available=more,
        next_cursor=encode_cursor({"offset": offset + source_rows, "limit": limit})
        if more
        else None,
        provenance=_cafc_provenance("/home/case-information/opinions-orders/"),
    )


@cafc_mcp.tool(annotations=READ_ONLY)
async def search_cafc_patent_opinions(
    date_from: Annotated[str | None, "Start date (YYYY-MM-DD) to filter opinions"] = None,
    date_to: Annotated[str | None, "End date (YYYY-MM-DD) to filter opinions"] = None,
    max_results: Annotated[int, "Maximum source rows per page (1-100)"] = 25,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: appeal "
        "number, short case name, release date, origin, document type, "
        "precedential status, patent classification, PDF URL. When True, "
        "each hit carries the full CAFCOpinion record.",
    ] = False,
    offset: Annotated[int, "Offset into the upstream filtered index"] = 0,
    next_cursor: Annotated[
        str | None, "Continuation from the previous page; overrides offset and page size"
    ] = None,
) -> ListEnvelope[dict]:
    """Search U.S. Court of Appeals for the Federal Circuit opinions from patent-relevant origins.

    Filters to opinions whose origin is PTO, DCT, ITC, or CFC — the four
    paths that bring patent cases to the Federal Circuit. Optional date
    range narrows the window; date_to requires date_from, and reversed
    bounds are rejected. Origins include non-patent cases as well.
    Continue with next_cursor and the same dates; cursors are offsets, not
    snapshots. Returns lean stubs by default; pass
    ``full=True`` for the upstream row shape. Use ``download_cafc_pdf``
    with an appeal number to pull a specific opinion PDF.

    Related tools: search_cafc_opinions, download_cafc_pdf.
    """
    from datetime import date as date_type

    offset, max_results = _page_args(offset, max_results, next_cursor)
    try:
        start_date = date_type.fromisoformat(date_from) if date_from is not None else None
        end_date = date_type.fromisoformat(date_to) if date_to is not None else None
    except ValueError as exc:
        raise ValidationError("dates must use YYYY-MM-DD") from exc
    if end_date is not None and start_date is None:
        raise ValidationError("date_to requires date_from; an end-only range is unsupported")
    if start_date is not None and start_date > (end_date or date_type.today()):
        raise ValidationError("date_from must not be later than date_to (default: today)")
    async with CAFCClient() as client:
        opinions = await client.search_patent_opinions(
            date_from=start_date, date_to=end_date, max_results=max_results + 1, offset=offset
        )
    more = len(opinions) > max_results
    opinions = opinions[:max_results]

    dumped = [_dump(o) for o in opinions]
    items = dumped if full else [_stub_opinion(r) for r in dumped]  # type: ignore[arg-type]

    range_bits: list[str] = []
    if date_from:
        range_bits.append(f"from {date_from}")
    if date_to:
        range_bits.append(f"to {date_to}")
    range_label = " ".join(range_bits) or "(no date range)"
    return ListEnvelope[dict](
        summary=(
            f"CAFC patent opinions — {range_label}: {len(items)} hits. "
            f"PTO/DCT/ITC/CFC origin scope at offset {offset}; may include non-patent cases."
        ),
        items=items,
        more_available=more,
        next_cursor=(
            encode_cursor({"offset": offset + len(opinions), "limit": max_results})
            if more
            else None
        ),
        provenance=_cafc_provenance("/home/case-information/opinions-orders/"),
    )


@cafc_mcp.tool(annotations=READ_ONLY)
async def download_cafc_pdf(
    appeal_number: Annotated[str, "CAFC appeal number (e.g. '2023-1234')"],
    document_url: Annotated[str | None, "Exact official PDF URL from discovery"] = None,
) -> dict:
    """Download a U.S. Court of Appeals for the Federal Circuit opinion PDF by appeal number.

    Returns a signed `download_url` (or `file_path` in local stdio mode) plus
    `filename`, `content_type`, `size_bytes`, `appeal_number`, `case_name`.

    Related tools: search_cafc_opinions, search_cafc_patent_opinions.
    """
    if document_url is not None:
        parsed = urlsplit(document_url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.cafc.uscourts.gov"
            or not parsed.path.startswith("/opinions-orders/")
            or not parsed.path.lower().endswith(".pdf")
            or parsed.query
            or parsed.fragment
        ):
            raise ValidationError("document_url must be an official CAFC opinions-orders PDF URL")
    async with CAFCClient() as client:
        if document_url is not None:
            match = CAFCOpinion(
                appeal_number=appeal_number, pdf_url=document_url, file_path=parsed.path
            )
        else:
            opinions = await client.search(query=appeal_number, max_results=100)
            matches = {
                o.pdf_url: o
                for o in opinions
                if o.appeal_number and appeal_number in o.appeal_number
            }
            if len(matches) != 1 or len(opinions) >= 100:
                raise ValidationError(
                    "Select document_url from discovery; appeal is ambiguous, absent, or capped"
                )
            match = next(iter(matches.values()))
        pdf_bytes = await client.download_pdf(match)

        retrieved_at = datetime.now(UTC).isoformat()
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
            f"cafc/documents/{hashlib.sha256(pdf_bytes).hexdigest()}",
            pdf_bytes,
            filename=filename,
            content_type="application/pdf",
            appeal_number=appeal_number,
            case_name=match.case_name,
            document_id=match.pdf_url,
            source_url=match.pdf_url,
            content_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            bytes_retrieved_at=retrieved_at,
            source_checked_at=retrieved_at,
            cache_state="live_fetch",
            source_revision=None,
        )


__all__ = ["cafc_mcp"]
