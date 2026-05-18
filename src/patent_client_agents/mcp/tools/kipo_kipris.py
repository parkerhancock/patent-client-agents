"""KIPO KIPRIS Plus MCP tools.

Read-only access to the live Korean Intellectual Property Office
registers (patents + utility models, trademarks, designs) via the
KIPRIS Plus REST API. Env-gated: registers only when
``KIPO_KIPRIS_API_KEY`` is set (ToS §11 BYOK — per-user keys only).

The KIPRIS Plus API is XML-only on the dev tier. Lean responses drop
the Korean-only abstract (``astrt_cont``) and the raw upstream
XML-derived dict; ``full=True`` includes them.

See ``research/specs/kr-kipo-connector-spec.md`` for the connector
contract.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.conditional import conditional_tool
from patent_client_agents.kipo_kipris import (
    DesignRow,
    KiprisClient,
    PatentUtilityRow,
    TrademarkRow,
)
from patent_client_agents.kipo_kipris.client import (
    BASE_URL as _KIPRIS_BASE_URL,
)
from patent_client_agents.kipo_kipris.client import (
    DESIGN as _DESIGN_SERVICE,
)
from patent_client_agents.kipo_kipris.client import (
    LIST_ACCEPT_CAP,
)
from patent_client_agents.kipo_kipris.client import (
    PAT_UTL as _PAT_UTL_SERVICE,
)
from patent_client_agents.kipo_kipris.client import (
    TM as _TM_SERVICE,
)

kipo_kipris_mcp = FastMCP("KIPO — KIPRIS Plus")

_KIPO_REQUIRED_ENV: list[str] = ["KIPO_KIPRIS_API_KEY"]

# §5 Provenance — Provenance has no ``attribution`` slot; we encode the
# ToS §11 BYOK constraint into ``source_name`` so it surfaces on every
# envelope alongside the canonical URL.
_KIPO_ATTRIBUTION = (
    "Source: Korean Intellectual Property Office (KIPO), via KIPRIS "
    "Plus operated by KIPI. Per-user API key required by ToS §11."
)

_KIPO_FANOUT_CONCURRENCY = 5


def _kipo_provenance(service: str, operation: str) -> Any:
    """Build a Provenance for a KIPRIS Plus operation URL."""
    return make_provenance(
        source_url=f"{_KIPRIS_BASE_URL}/{service}/{operation}",
        source_name=_KIPO_ATTRIBUTION,
    )


def _dump(model: Any) -> dict[str, Any]:
    """Serialize a Pydantic row to a dict via ``model_dump(by_alias=True)``."""
    return cast("dict[str, Any]", model.model_dump(by_alias=True))


# ──────────────────────────────────────────────────────────────────────
# Lean projections (§5.5). KIPRIS rows are XML-derived flat dicts;
# the lean shape drops Korean-only abstract + raw upstream payload.
# ──────────────────────────────────────────────────────────────────────


def _lean_patent(row: PatentUtilityRow) -> dict[str, Any]:
    """Lean projection of a patent/UM row (drops ``astrt_cont``)."""
    return {
        "application_number": row.application_number,
        "application_date": row.application_date.isoformat() if row.application_date else None,
        "publication_number": row.publication_number,
        "publication_date": row.publication_date.isoformat() if row.publication_date else None,
        "register_number": row.register_number,
        "register_status": row.register_status,
        "invention_title": row.invention_title,
        "invention_title_english": row.invention_title_english,
        "applicant_name": row.applicant_name,
        "inventor_name": row.inventor_name,
        "ipc_number": row.ipc_number,
    }


def _lean_trademark(row: TrademarkRow) -> dict[str, Any]:
    """Lean projection of a trademark row."""
    return {
        "application_number": row.application_number,
        "application_date": row.application_date.isoformat() if row.application_date else None,
        "registration_number": row.registration_number,
        "registration_date": row.registration_date.isoformat() if row.registration_date else None,
        "title": row.title,
        "classification_code": row.classification_code,
        "vienna_code": row.vienna_code,
        "applicant_name": row.applicant_name,
        "big_drawing": row.big_drawing,
    }


def _lean_design(row: DesignRow) -> dict[str, Any]:
    """Lean projection of a design row (always keeps ``drawing`` image URL)."""
    return {
        "application_number": row.application_number,
        "application_date": row.application_date.isoformat() if row.application_date else None,
        "registration_number": row.registration_number,
        "registration_date": row.registration_date.isoformat() if row.registration_date else None,
        "register_status": row.register_status,
        "article_name": row.article_name,
        "loc_code": row.loc_code,
        "applicant_name": row.applicant_name,
        "inventor_name": row.inventor_name,
        "drawing": row.drawing,
    }


def _validate_raw_items(items: list[dict], model: type[Any]) -> list[Any]:
    """Parse raw KIPRIS dicts into typed row models."""
    return [model.model_validate(item) for item in items]


# ──────────────────────────────────────────────────────────────────────
# Patents + Utility Models — three tools
# ──────────────────────────────────────────────────────────────────────


@conditional_tool(kipo_kipris_mcp, requires_env=_KIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_kipo_patents(
    query: Annotated[
        str,
        "Free-text search string. Matches title, abstract, applicant, "
        "and inventor across KIPRIS patent + utility-model rows.",
    ],
    right_type: Annotated[
        str,
        "Which subset of the combined patent/UM service to return. "
        "One of 'patent', 'utility_model', or 'both' (default).",
    ] = "both",
    num_of_rows: Annotated[
        int,
        "Page size. KIPRIS Plus defaults to 10; max 1000.",
    ] = 10,
    page_no: Annotated[
        int,
        "1-indexed page number.",
    ] = 1,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub (drops the "
        "Korean-only ``astrt_cont`` abstract). When True, every hit "
        "carries the full upstream-shaped row.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search KIPO patents and utility models by free text.

    Returns a lean stub per hit by default; pass ``full=True`` for the
    full XML-derived row. Use ``right_type`` to limit to patents-only
    or utility-models-only.

    Related tools: `search_epo_patents` / `get_epo_biblio` — EPO INPADOC
    provides KR biblio + family at the regional layer with no BYOK
    requirement; prefer KIPO only for KR-language full text, prosecution
    depth, or utility models.
    """
    patent = right_type in ("patent", "both")
    utility = right_type in ("utility_model", "both")
    items, pagination = await __import__(
        "patent_client_agents.kipo_kipris.api", fromlist=["search_kipo_patents"]
    ).search_kipo_patents(
        query=query,
        patent=patent,
        utility=utility,
        num_of_rows=num_of_rows,
        page_no=page_no,
    )
    rows = _validate_raw_items(items, PatentUtilityRow)
    out = [_dump(r) for r in rows] if full else [_lean_patent(r) for r in rows]
    total = pagination.get("totalCount")
    shown = len(out)
    summary_total = f"{shown} of {total} hits" if isinstance(total, int) else f"{shown} hits"
    more = bool(isinstance(total, int) and (page_no * num_of_rows) < total)
    return ListEnvelope[dict](
        summary=f"KIPO patents/UM — `{query}`: {summary_total}.",
        items=out,
        more_available=more,
        next_cursor=None,
        provenance=_kipo_provenance(_PAT_UTL_SERVICE, "getWordSearch"),
    )


@conditional_tool(kipo_kipris_mcp, requires_env=_KIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_kipo_patents_advanced(
    invention_title: Annotated[
        str | None, "Match against invention title (Korean or English)."
    ] = None,
    astrt_cont: Annotated[str | None, "Match against abstract content."] = None,
    claim_scope: Annotated[str | None, "Match against claim text."] = None,
    applicant: Annotated[str | None, "Match against applicant name (Korean or romanized)."] = None,
    inventor: Annotated[str | None, "Match against inventor name."] = None,
    ipc: Annotated[str | None, "IPC classification code (e.g. 'G06F')."] = None,
    application_date: Annotated[
        str | None, "Filing date filter (YYYYMMDD or YYYYMMDD~YYYYMMDD range)."
    ] = None,
    publication_date: Annotated[str | None, "Publication date filter (YYYYMMDD or range)."] = None,
    right_type: Annotated[
        str,
        "One of 'patent', 'utility_model', 'both' (default).",
    ] = "both",
    num_of_rows: Annotated[int, "Page size (max 1000)."] = 10,
    page_no: Annotated[int, "1-indexed page number."] = 1,
    full: Annotated[
        bool,
        "When True, return full upstream rows (default lean).",
    ] = False,
) -> ListEnvelope[dict]:
    """Structured-field search over KIPO patents and utility models.

    Every field is optional; KIPRIS ANDs whatever is provided. Use this
    when free-text search is too imprecise (e.g. exact applicant match,
    IPC + date-range filtering).

    Related tools: `search_epo_patents` / `get_epo_biblio` — EPO INPADOC
    provides KR biblio + family at the regional layer with no BYOK
    requirement; prefer KIPO only for KR-language full text, prosecution
    depth, or utility models.
    """
    patent = right_type in ("patent", "both")
    utility = right_type in ("utility_model", "both")
    api = __import__(
        "patent_client_agents.kipo_kipris.api", fromlist=["search_kipo_patents_advanced"]
    )
    items, pagination = await api.search_kipo_patents_advanced(
        invention_title=invention_title,
        astrt_cont=astrt_cont,
        claim_scope=claim_scope,
        applicant=applicant,
        inventor=inventor,
        ipc=ipc,
        application_date=application_date,
        publication_date=publication_date,
        patent=patent,
        utility=utility,
        num_of_rows=num_of_rows,
        page_no=page_no,
    )
    rows = _validate_raw_items(items, PatentUtilityRow)
    out = [_dump(r) for r in rows] if full else [_lean_patent(r) for r in rows]
    total = pagination.get("totalCount")
    shown = len(out)
    summary_total = f"{shown} of {total} hits" if isinstance(total, int) else f"{shown} hits"
    more = bool(isinstance(total, int) and (page_no * num_of_rows) < total)
    return ListEnvelope[dict](
        summary=f"KIPO advanced patent/UM search: {summary_total}.",
        items=out,
        more_available=more,
        next_cursor=None,
        provenance=_kipo_provenance(_PAT_UTL_SERVICE, "getAdvancedSearch"),
    )


@conditional_tool(kipo_kipris_mcp, requires_env=_KIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_kipo_patent(
    application_number: Annotated[
        str | list[str],
        "KIPO application or publication number (digits-only), or a list "
        f"(capped at {LIST_ACCEPT_CAP}) for portfolio workflows. Fan-out "
        "is serial — KIPRIS has no batch endpoint.",
    ],
    full: Annotated[
        bool,
        "When True, return full upstream rows (default lean).",
    ] = False,
) -> ListEnvelope[dict]:
    """Fetch a single KIPO patent / utility model by application or publication number.

    Accepts a single number or a list (capped at 50 per spec §6).
    Iterates serially per ToS §11 quota awareness; response stays a
    ListEnvelope even for a single ID.

    Related tools: `search_epo_patents` / `get_epo_biblio` — EPO INPADOC
    provides KR biblio + family at the regional layer with no BYOK
    requirement; prefer KIPO only for KR-language full text, prosecution
    depth, or utility models.
    """
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_kipo_patent requires at least one application_number")
    if len(numbers) > LIST_ACCEPT_CAP:
        raise ValidationError(
            f"get_kipo_patent capped at {LIST_ACCEPT_CAP} numbers per call "
            f"(received {len(numbers)})"
        )

    all_rows: list[PatentUtilityRow] = []
    async with KiprisClient() as client:
        for num in numbers:
            items, _ = await client.get_patent(num)
            all_rows.extend(_validate_raw_items(items, PatentUtilityRow))

    out = [_dump(r) for r in all_rows] if full else [_lean_patent(r) for r in all_rows]
    summary = f"Fetched {len(out)} KIPO patent/UM record(s) for {len(numbers)} number(s)."
    return ListEnvelope[dict](
        summary=summary,
        items=out,
        more_available=False,
        next_cursor=None,
        provenance=_kipo_provenance(_PAT_UTL_SERVICE, "getAdvancedSearch"),
    )


# ──────────────────────────────────────────────────────────────────────
# Trademarks — three tools
# ──────────────────────────────────────────────────────────────────────


@conditional_tool(kipo_kipris_mcp, requires_env=_KIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_kipo_trademarks(
    query: Annotated[
        str,
        "Free-text search string. Matches mark text, applicant, "
        "and classification codes across KIPRIS trademark rows.",
    ],
    num_of_rows: Annotated[int, "Page size (max 1000)."] = 10,
    page_no: Annotated[int, "1-indexed page number."] = 1,
    full: Annotated[bool, "When True, return full upstream rows (default lean)."] = False,
) -> ListEnvelope[dict]:
    """Search KIPO trademarks by free text.

    Returns a lean stub per hit by default; pass ``full=True`` for the
    full upstream row including Vienna codes and image URLs.
    """
    api = __import__("patent_client_agents.kipo_kipris.api", fromlist=["search_kipo_trademarks"])
    items, pagination = await api.search_kipo_trademarks(
        query=query, num_of_rows=num_of_rows, page_no=page_no
    )
    rows = _validate_raw_items(items, TrademarkRow)
    out = [_dump(r) for r in rows] if full else [_lean_trademark(r) for r in rows]
    total = pagination.get("totalCount")
    shown = len(out)
    summary_total = f"{shown} of {total} hits" if isinstance(total, int) else f"{shown} hits"
    more = bool(isinstance(total, int) and (page_no * num_of_rows) < total)
    return ListEnvelope[dict](
        summary=f"KIPO trademarks — `{query}`: {summary_total}.",
        items=out,
        more_available=more,
        next_cursor=None,
        provenance=_kipo_provenance(_TM_SERVICE, "getWordSearch"),
    )


@conditional_tool(kipo_kipris_mcp, requires_env=_KIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_kipo_trademarks_advanced(
    title: Annotated[str | None, "Match against mark text."] = None,
    applicant: Annotated[str | None, "Match against applicant name."] = None,
    classification: Annotated[str | None, "Nice goods/services class (e.g. '09')."] = None,
    vienna_code: Annotated[str | None, "Vienna figurative classification code."] = None,
    application_date: Annotated[str | None, "Filing date filter (YYYYMMDD or range)."] = None,
    registration_date: Annotated[
        str | None, "Registration date filter (YYYYMMDD or range)."
    ] = None,
    num_of_rows: Annotated[int, "Page size (max 1000)."] = 10,
    page_no: Annotated[int, "1-indexed page number."] = 1,
    full: Annotated[bool, "When True, return full upstream rows (default lean)."] = False,
) -> ListEnvelope[dict]:
    """Structured-field search over KIPO trademarks.

    Every field is optional; KIPRIS ANDs whatever is provided.
    """
    api = __import__(
        "patent_client_agents.kipo_kipris.api",
        fromlist=["search_kipo_trademarks_advanced"],
    )
    items, pagination = await api.search_kipo_trademarks_advanced(
        title=title,
        applicant=applicant,
        classification=classification,
        vienna_code=vienna_code,
        application_date=application_date,
        registration_date=registration_date,
        num_of_rows=num_of_rows,
        page_no=page_no,
    )
    rows = _validate_raw_items(items, TrademarkRow)
    out = [_dump(r) for r in rows] if full else [_lean_trademark(r) for r in rows]
    total = pagination.get("totalCount")
    shown = len(out)
    summary_total = f"{shown} of {total} hits" if isinstance(total, int) else f"{shown} hits"
    more = bool(isinstance(total, int) and (page_no * num_of_rows) < total)
    return ListEnvelope[dict](
        summary=f"KIPO advanced trademark search: {summary_total}.",
        items=out,
        more_available=more,
        next_cursor=None,
        provenance=_kipo_provenance(_TM_SERVICE, "getAdvancedSearch"),
    )


@conditional_tool(kipo_kipris_mcp, requires_env=_KIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_kipo_trademark(
    application_number: Annotated[
        str | list[str],
        "KIPO trademark application or registration number (digits-only), "
        f"or a list (capped at {LIST_ACCEPT_CAP}). Fan-out is serial — "
        "KIPRIS has no batch endpoint.",
    ],
    full: Annotated[bool, "When True, return full upstream rows (default lean)."] = False,
) -> ListEnvelope[dict]:
    """Fetch a single KIPO trademark by application or registration number.

    Accepts a single number or a list (capped at 50).
    """
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_kipo_trademark requires at least one application_number")
    if len(numbers) > LIST_ACCEPT_CAP:
        raise ValidationError(
            f"get_kipo_trademark capped at {LIST_ACCEPT_CAP} numbers per call "
            f"(received {len(numbers)})"
        )

    all_rows: list[TrademarkRow] = []
    async with KiprisClient() as client:
        for num in numbers:
            items, _ = await client.get_trademark(num)
            all_rows.extend(_validate_raw_items(items, TrademarkRow))

    out = [_dump(r) for r in all_rows] if full else [_lean_trademark(r) for r in all_rows]
    summary = f"Fetched {len(out)} KIPO trademark record(s) for {len(numbers)} number(s)."
    return ListEnvelope[dict](
        summary=summary,
        items=out,
        more_available=False,
        next_cursor=None,
        provenance=_kipo_provenance(_TM_SERVICE, "getAdvancedSearch"),
    )


# ──────────────────────────────────────────────────────────────────────
# Designs — three tools
# ──────────────────────────────────────────────────────────────────────


@conditional_tool(kipo_kipris_mcp, requires_env=_KIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_kipo_designs(
    query: Annotated[
        str,
        "Free-text search string. Matches article name, applicant, "
        "and classification codes across KIPRIS design rows.",
    ],
    num_of_rows: Annotated[int, "Page size (max 1000)."] = 10,
    page_no: Annotated[int, "1-indexed page number."] = 1,
    full: Annotated[bool, "When True, return full upstream rows (default lean)."] = False,
) -> ListEnvelope[dict]:
    """Search KIPO designs by free text.

    Returns a lean stub per hit by default; pass ``full=True`` for the
    full upstream row. Lean output still keeps the ``drawing`` image URL.
    """
    api = __import__("patent_client_agents.kipo_kipris.api", fromlist=["search_kipo_designs"])
    items, pagination = await api.search_kipo_designs(
        query=query, num_of_rows=num_of_rows, page_no=page_no
    )
    rows = _validate_raw_items(items, DesignRow)
    out = [_dump(r) for r in rows] if full else [_lean_design(r) for r in rows]
    total = pagination.get("totalCount")
    shown = len(out)
    summary_total = f"{shown} of {total} hits" if isinstance(total, int) else f"{shown} hits"
    more = bool(isinstance(total, int) and (page_no * num_of_rows) < total)
    return ListEnvelope[dict](
        summary=f"KIPO designs — `{query}`: {summary_total}.",
        items=out,
        more_available=more,
        next_cursor=None,
        provenance=_kipo_provenance(_DESIGN_SERVICE, "getWordSearch"),
    )


@conditional_tool(kipo_kipris_mcp, requires_env=_KIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_kipo_designs_advanced(
    article_name: Annotated[
        str | None, "Match against article name (the product the design covers)."
    ] = None,
    applicant: Annotated[str | None, "Match against applicant name."] = None,
    loc_code: Annotated[str | None, "Locarno design classification code."] = None,
    application_date: Annotated[str | None, "Filing date filter (YYYYMMDD or range)."] = None,
    registration_date: Annotated[
        str | None, "Registration date filter (YYYYMMDD or range)."
    ] = None,
    num_of_rows: Annotated[int, "Page size (max 1000)."] = 10,
    page_no: Annotated[int, "1-indexed page number."] = 1,
    full: Annotated[bool, "When True, return full upstream rows (default lean)."] = False,
) -> ListEnvelope[dict]:
    """Structured-field search over KIPO designs.

    Every field is optional; KIPRIS ANDs whatever is provided.
    """
    api = __import__(
        "patent_client_agents.kipo_kipris.api",
        fromlist=["search_kipo_designs_advanced"],
    )
    items, pagination = await api.search_kipo_designs_advanced(
        article_name=article_name,
        applicant=applicant,
        loc_code=loc_code,
        application_date=application_date,
        registration_date=registration_date,
        num_of_rows=num_of_rows,
        page_no=page_no,
    )
    rows = _validate_raw_items(items, DesignRow)
    out = [_dump(r) for r in rows] if full else [_lean_design(r) for r in rows]
    total = pagination.get("totalCount")
    shown = len(out)
    summary_total = f"{shown} of {total} hits" if isinstance(total, int) else f"{shown} hits"
    more = bool(isinstance(total, int) and (page_no * num_of_rows) < total)
    return ListEnvelope[dict](
        summary=f"KIPO advanced design search: {summary_total}.",
        items=out,
        more_available=more,
        next_cursor=None,
        provenance=_kipo_provenance(_DESIGN_SERVICE, "getAdvancedSearch"),
    )


@conditional_tool(kipo_kipris_mcp, requires_env=_KIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_kipo_design(
    application_number: Annotated[
        str | list[str],
        "KIPO design application or registration number (digits-only), "
        f"or a list (capped at {LIST_ACCEPT_CAP}). Fan-out is serial — "
        "KIPRIS has no batch endpoint.",
    ],
    full: Annotated[bool, "When True, return full upstream rows (default lean)."] = False,
) -> ListEnvelope[dict]:
    """Fetch a single KIPO design by application or registration number.

    Accepts a single number or a list (capped at 50). Always includes
    the ``drawing`` image URL field.
    """
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_kipo_design requires at least one application_number")
    if len(numbers) > LIST_ACCEPT_CAP:
        raise ValidationError(
            f"get_kipo_design capped at {LIST_ACCEPT_CAP} numbers per call "
            f"(received {len(numbers)})"
        )

    all_rows: list[DesignRow] = []
    async with KiprisClient() as client:
        for num in numbers:
            items, _ = await client.get_design(num)
            all_rows.extend(_validate_raw_items(items, DesignRow))

    out = [_dump(r) for r in all_rows] if full else [_lean_design(r) for r in all_rows]
    summary = f"Fetched {len(out)} KIPO design record(s) for {len(numbers)} number(s)."
    return ListEnvelope[dict](
        summary=summary,
        items=out,
        more_available=False,
        next_cursor=None,
        provenance=_kipo_provenance(_DESIGN_SERVICE, "getAdvancedSearch"),
    )


# Silence unused-import lints — re-exported for downstream callers and
# kept available in module namespace for tests.
_ = asyncio  # noqa: F841


__all__ = ["kipo_kipris_mcp"]
