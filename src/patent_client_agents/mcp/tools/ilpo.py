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

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import NotFoundError
from mcp_data_core.mcp.annotations import READ_ONLY
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
from patent_client_agents.shared.envelope import dump
from patent_client_agents.shared.fanout import FetchedList, as_id_list, fetch_many, fetched_summary
from patent_client_agents.shared.provenance import provenance_for

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
    return provenance_for(
        source_url=source_url,
        source_name=_ILPO_STATUTES_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _ilpo_tm_provenance(path: str) -> Any:
    return provenance_for(
        source_url=f"{ILPO_TM_HOST}{path}",
        source_name=_ILPO_TM_NAME,
    )


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
    dumped = dump(response, by_alias=True)
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
) -> FetchedList[dict]:
    """Fetch one or more sections from the ILPO Israel statutes corpus by citation.

    Resolves citations like ``Section 3 Patents Law`` or
    ``Article 6 Commercial Torts Law`` to the corresponding section text.
    Accepts either a single citation or a list; the response is always a
    ListEnvelope so the shape is stable. Bounded concurrent fan-out
    internally; order matches the input.

    Related tools: search_ilpo_statutes.
    """
    citations = as_id_list(citation, noun="ILPO statute citation")

    async with IlpoStatutesClient() as client:

        async def _fetch_one(cit: str) -> dict | None:
            section = await client.get_section_by_citation(cit)
            return dump(section) if section is not None else None

        items, not_found = await fetch_many(citations, _fetch_one, single=isinstance(citation, str))

    if len(citations) == 1 and items:
        first = items[0]
        title = first.get("title") or "(no title)"
        summary = f"**{first.get('section_label', citations[0])}** — {title}"
    elif len(citations) == 1:
        summary = f"ILPO Israel section {citations[0]!r} — not found."
    else:
        summary = fetched_summary(len(items), len(citations), "ILPO sections", not_found)

    return FetchedList[dict](
        summary=summary,
        items=items,
        not_found=not_found,
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

    dumped = dump(dataset, by_alias=True)
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

    dumped = dump(dataset, by_alias=True)
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
