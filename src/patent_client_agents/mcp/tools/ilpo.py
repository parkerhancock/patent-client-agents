"""ILPO Israel MCP tools — statutes corpus + data.gov.il trade-mark feed.

Two surfaces, deliberately separated:

* **Statutes** read from a pre-built SQLite/FTS5 corpus produced by
  ``patent-client-agents-build-ilpo-statutes-corpus``. CONNECTOR_STANDARDS
  classification: ``category=substantive_law``, ``transport=mcp_local``.
  Provenance carries ``corpus_synced_at`` / ``corpus_version`` per §4,
  sourced from
  :func:`patent_client_agents.ilpo_statutes.get_corpus_status`.
* **TM feed** is a thin CKAN wrapper over ``data.gov.il``. Classification:
  ``category=registered_ip``, ``transport=mcp_proxy``. Shape E (catalog
  list + raw download dict) per §7.2.

Israel's distinctive piece is the **Commercial Torts Law, 5759-1999**
(Articles 6-9, trade secrets; Article 13, statutory damages) — a
standalone trade-secret statute rather than a Civil Code section.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import NotFoundError, ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.ilpo_statutes import (
    IlpoStatutesClient,
    SectionInput,
    StatuteSearchInput,
    get_corpus_status,
    list_statutes,
    search,
)
from patent_client_agents.ilpo_statutes.client import _resolve_statute, parse_citation
from patent_client_agents.ilpo_tm import CKAN_HOST as ILPO_TM_HOST
from patent_client_agents.ilpo_tm import IlpoTmClient

ilpo_mcp = FastMCP("ILPO Israel")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9).
#
# Two source-specific provenance helpers — statutes are mcp_local
# (carry corpus_* fields); the TM feed is mcp_proxy (standard fields
# only). The statutes corpus_synced_at / corpus_version values flow
# from :func:`patent_client_agents.ilpo_statutes.get_corpus_status` so
# the bundled corpus drives the freshness stamp without a code change
# here (CONNECTOR_STANDARDS.md §4).
# ──────────────────────────────────────────────────────────────────────

_ILPO_STATUTES_NAME = "ILPO Israel — Statutes (WIPO Lex)"
_ILPO_STATUTES_URL = "https://www.wipo.int/wipolex/en/profile.jsp?code=IL"
_ILPO_TM_NAME = "ILPO Israel — Trade Marks (data.gov.il)"


def _ilpo_statutes_provenance(source_url: str = _ILPO_STATUTES_URL) -> Any:
    status = get_corpus_status()
    return make_provenance(
        source_url=source_url,
        source_name=_ILPO_STATUTES_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _ilpo_tm_provenance(path: str) -> Any:
    return make_provenance(
        source_url=f"{ILPO_TM_HOST}{path}",
        source_name=_ILPO_TM_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict via ``model_dump(by_alias=True)``."""
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump(by_alias=True))  # type: ignore[union-attr]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


_STATUTES_FANOUT_CONCURRENCY = 5
_DEFAULT_TM_DATASET_ID = "trade-marks"


# ---------------------------------------------------------------------------
# Statutes
# ---------------------------------------------------------------------------


@ilpo_mcp.tool(annotations=READ_ONLY)
async def search_ilpo_statutes(
    query: Annotated[str, "Search query against the Israeli IP statutes corpus."],
    statute: Annotated[
        str | None,
        (
            "Optional statute key — 'patents', 'trademarks', 'designs', "
            "'copyright', or 'commercial_torts'. Aliases like 'trade marks', "
            "'trade secret', or 'trade secrets' are accepted (the latter "
            "two map to Commercial Torts Law, which carries Israel's "
            "standalone trade-secret regime). Omit to search across all "
            "five statutes."
        ),
    ] = None,
    per_page: Annotated[int, "Hits per page, 1..100."] = 10,
    page: Annotated[int, "1-indexed page number."] = 1,
) -> ListEnvelope[dict]:
    """Search the ILPO Israel IP statutes corpus (Patents, TM, Designs, Copyright, Commercial Torts).

    Returns ranked snippets with ``<mark>...</mark>`` highlights around
    matched terms. Use this for citation lookups like ``"Article 6"`` or
    topical searches like ``"trade secret misappropriation"``. The
    Commercial Torts Law is the distinctive piece in this corpus —
    Israel ships a standalone statute for trade-secret protection rather
    than burying the rules in a Civil Code section.

    Related tools: get_ilpo_section.
    """
    params = StatuteSearchInput(
        query=query,
        statute=statute,
        per_page=per_page,
        page=page,
    )
    response = await search(params)
    dumped = _dump(response)
    items = list(dumped.get("hits") or [])
    has_more = bool(dumped.get("has_more"))

    stat_label = statute or "all"
    return ListEnvelope[dict](
        summary=(
            f"ILPO Israel statutes — `{query}` (statute={stat_label}): "
            f"{len(items)} hits (page {page})."
        ),
        items=items,
        more_available=has_more,
        next_cursor=None,
        provenance=_ilpo_statutes_provenance(),
    )


@ilpo_mcp.tool(annotations=READ_ONLY)
async def get_ilpo_section(
    citation: Annotated[
        str | list[str],
        (
            "Citation string, or a list for portfolio reads (§5.4). "
            "Accepted forms: 'Section 3 Patents Law', "
            "'Section 1 Trade Marks Ordinance', "
            "'Article 6 Commercial Torts Law' (trade-secret core), "
            "'Section 11 Designs Law', 'Section 1 Copyright Act'. "
            "Reverse order also works (e.g. 'Patents Law §3'). "
            "Pass a list like ['Article 6 Commercial Torts Law', "
            "'Section 3 Patents Law'] for a batch read."
        ),
    ],
) -> ListEnvelope[dict]:
    """Fetch one or more sections from the ILPO Israel statutes corpus by citation.

    Resolves citations like ``Section 3 Patents Law`` or
    ``Article 6 Commercial Torts Law`` to the corresponding section text.
    Accepts either a single citation or a list; the response is always a
    ListEnvelope so the shape is stable. Bounded concurrent fan-out
    internally; order matches the input.

    Related tools: search_ilpo_statutes.
    """
    citations = [citation] if isinstance(citation, str) else list(citation)
    if not citations:
        raise ValidationError("get_ilpo_section requires at least one citation")

    semaphore = asyncio.Semaphore(_STATUTES_FANOUT_CONCURRENCY)

    async def _fetch_one(client: IlpoStatutesClient, cit: str) -> dict | None:
        async with semaphore:
            section = await client.get_section_by_citation(cit)
        if section is None:
            return None
        return cast("dict[str, Any]", section.model_dump())

    async with IlpoStatutesClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, c) for c in citations])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [c for c, r in zip(citations, fetched, strict=True) if r is None]

    if len(citations) == 1 and items:
        first = items[0]
        title = first.get("title") or "(no title)"
        summary = f"**{first.get('section_label', citations[0])}** — {title}"
    elif len(citations) == 1:
        summary = f"ILPO Israel section {citations[0]!r} — not found."
    else:
        head = f"Fetched {len(items)} of {len(citations)} ILPO sections."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_ilpo_statutes_provenance(),
    )


# ---------------------------------------------------------------------------
# data.gov.il trade-mark feed (CKAN)
# ---------------------------------------------------------------------------


@ilpo_mcp.tool(annotations=READ_ONLY)
async def list_ilpo_tm_releases(
    dataset_id: Annotated[
        str,
        (
            "data.gov.il CKAN dataset id. Defaults to 'trade-marks' "
            "(the canonical ILPO TM register). Pass an alternate id to "
            "enumerate a different dataset's resources."
        ),
    ] = _DEFAULT_TM_DATASET_ID,
) -> ListEnvelope[dict]:
    """List downloadable ILPO Israel trade-mark releases on data.gov.il.

    Each item carries the CKAN resource id (use it as ``resource_id``
    in ``download_ilpo_tm``), the human-readable name, the file format
    and size, the last-modified timestamp, and the canonical
    data.gov.il download URL. The refresh cadence is dataset-dependent
    (typically weekly for the live TM register).

    Related tools: download_ilpo_tm, search_ilpo_statutes.
    """
    async with IlpoTmClient() as client:
        dataset = await client.get_dataset(dataset_id)

    dumped = _dump(dataset)
    raw_resources = list(dumped.get("resources") or [])
    items: list[dict] = []
    for raw in raw_resources:
        items.append(
            {
                "resource_id": raw.get("id"),
                "name": raw.get("name"),
                "description": raw.get("description"),
                "format": raw.get("format"),
                "mimetype": raw.get("mimetype"),
                "size_bytes": raw.get("size"),
                "last_modified": raw.get("last_modified"),
                "download_url": raw.get("url"),
            }
        )

    license_label = dumped.get("license_title") or dumped.get("license_id") or "unknown licence"
    summary = (
        f"ILPO Israel TM feed — `{dataset_id}` ({license_label}): "
        f"{len(items)} downloadable resource(s)."
    )
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_ilpo_tm_provenance(f"/dataset/{dataset_id}"),
    )


@ilpo_mcp.tool(annotations=READ_ONLY)
async def download_ilpo_tm(
    resource_id: Annotated[
        str,
        ("CKAN resource id from list_ilpo_tm_releases. data.gov.il resource ids are UUIDs."),
    ],
    dataset_id: Annotated[
        str,
        "Parent dataset id (defaults to 'trade-marks').",
    ] = _DEFAULT_TM_DATASET_ID,
) -> dict:
    """Resolve an ILPO Israel TM release id to a direct data.gov.il download URL.

    Returns the upstream URL plus the resource metadata (format, size,
    last-modified). The URL is public and unauthenticated — fetch it
    with any HTTP client; we deliberately do not proxy the bytes
    through our download cache because the TM dataset can be large.
    Shape E (Shape E in CONNECTOR_STANDARDS.md §7.2 — raw dict
    carrying ``download_url`` + metadata; not wrapped in an envelope).

    Related tools: list_ilpo_tm_releases.
    """
    async with IlpoTmClient() as client:
        dataset = await client.get_dataset(dataset_id)

    dumped = _dump(dataset)
    for raw in dumped.get("resources") or []:
        if raw.get("id") == resource_id:
            return {
                "resource_id": resource_id,
                "dataset_id": dataset_id,
                "name": raw.get("name"),
                "description": raw.get("description"),
                "format": raw.get("format"),
                "mimetype": raw.get("mimetype"),
                "size_bytes": raw.get("size"),
                "last_modified": raw.get("last_modified"),
                "download_url": raw.get("url"),
                "license": dumped.get("license_title") or dumped.get("license_id"),
                "source_name": _ILPO_TM_NAME,
                "source_url": f"{ILPO_TM_HOST}/dataset/{dataset_id}",
            }
    raise NotFoundError(
        f"resource_id {resource_id!r} not found in dataset {dataset_id!r}. "
        f"Use list_ilpo_tm_releases to list current resources."
    )


# ---------------------------------------------------------------------------
# Helpers re-exported for tests + downstream consumers
# ---------------------------------------------------------------------------

# `list_statutes` and `SectionInput` are imported so tests can patch the
# names at the module path the tools resolve through. Re-exporting them
# keeps the test surface symmetric with the canonical UPC pattern.
__all__ = [
    "ilpo_mcp",
    "SectionInput",
    "list_statutes",
    "parse_citation",
    "_resolve_statute",
]
