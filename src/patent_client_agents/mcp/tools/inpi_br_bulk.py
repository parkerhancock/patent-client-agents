"""INPI Brazil — Revista da Propriedade Industrial (RPI) bulk catalog MCP tools.

The RPI is INPI Brazil's weekly official bulletin — every administrative
act (filings, office actions, allowances, registrations, oppositions,
appeals, GI grants, IC topography registrations, technology-transfer
contract registrations) publishes here. Eight sections — patents, trade
marks, designs, GIs, software programs, IC topographies,
technology-transfer contracts, and INPI communications — distributed as
PDF + TXT-in-ZIP + XML-in-ZIP files on ``dados.gov.br`` under Decreto
8.777/2016's open license. No auth.

This is the **catalog + download** surface (Shape E in
CONNECTOR_STANDARDS.md §7.2): one tool lists the current resources
within the RPI dataset, and one tool resolves a resource id to a direct
``dados.gov.br`` download URL. The URL is the upstream public URL —
stable, unauthenticated, and routable by any HTTP client; we do not
proxy the bytes through our own download cache.

Full RPI XML ingestion (per-section parsers, INID-code + INPI-dispatch-
code decoders, schema-versioned record models) is intentionally out of
scope for v1; it will land in a follow-up so this PR ships the catalog
surface independently.
"""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import NotFoundError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.inpi_br_bulk import (
    CKAN_HOST,
    INPI_BR_RPI_DATASET_ID,
    InpiBrBulkClient,
)

inpi_br_bulk_mcp = FastMCP("INPI Brazil — RPI")

_INPI_BR_BULK_NAME = "INPI Brazil — RPI (dados.gov.br)"


def _inpi_br_bulk_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{CKAN_HOST}{path}``."""
    return make_provenance(
        source_url=f"{CKAN_HOST}{path}",
        source_name=_INPI_BR_BULK_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict via ``model_dump(by_alias=True)``."""
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump(by_alias=True))  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


# ---------------------------------------------------------------------------
# list_inpi_br_bulk_releases
# ---------------------------------------------------------------------------


@inpi_br_bulk_mcp.tool(annotations=READ_ONLY)
async def list_inpi_br_bulk_releases(
    dataset_id: Annotated[
        str,
        "dados.gov.br dataset id. Defaults to "
        "'revista-da-propriedade-industrial-rpi' (the weekly RPI feed). "
        "Pass an alternate id (e.g. 'bw-p-2020' for the annual Pedidos "
        "de Patentes snapshot) to enumerate that dataset's resources "
        "instead.",
    ] = INPI_BR_RPI_DATASET_ID,
) -> ListEnvelope[dict]:
    """List downloadable INPI Brazil RPI (Revista da Propriedade Industrial) releases.

    Each item carries the resource id (use it as ``resource_id`` in
    ``download_inpi_br_bulk``), the human-readable name, the file format
    and size, the last-modified timestamp, and the canonical dados.gov.br
    download URL. The RPI weekly bulletin covers eight sections —
    patents, trade marks, designs, GIs, software programs, IC
    topographies, technology-transfer contracts, and INPI communications
    — refreshed every Tuesday.

    Related tools: download_inpi_br_bulk, search_inpi_br_statutes,
    get_inpi_br_section.
    """
    async with InpiBrBulkClient() as client:
        dataset = await client.get_dataset(dataset_id)

    dumped = _dump(dataset)
    resources = list(dumped.get("resources") or [])
    items: list[dict] = []
    for raw in resources:
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
        f"INPI Brazil bulk — `{dataset_id}` ({license_label}): "
        f"{len(items)} downloadable resource(s)."
    )
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_inpi_br_bulk_provenance(f"/dataset/{dataset_id}"),
    )


# ---------------------------------------------------------------------------
# download_inpi_br_bulk
# ---------------------------------------------------------------------------


@inpi_br_bulk_mcp.tool(annotations=READ_ONLY)
async def download_inpi_br_bulk(
    resource_id: Annotated[
        str,
        "Resource id from list_inpi_br_bulk_releases. The id is the "
        "stable identifier reported by the dados.gov.br catalog for one "
        "downloadable artifact (e.g. one RPI XML zip for a given week).",
    ],
    dataset_id: Annotated[
        str,
        "Parent dataset id (defaults to "
        "'revista-da-propriedade-industrial-rpi'). Pass a different "
        "value to look the resource up inside a non-default dataset.",
    ] = INPI_BR_RPI_DATASET_ID,
) -> dict:
    """Resolve an INPI Brazil RPI release id to a direct dados.gov.br download URL.

    Returns the upstream URL plus the resource metadata (format, size,
    last-modified). The URL is public and unauthenticated — fetch it
    with any HTTP client. We deliberately do not proxy the bytes through
    our download cache.

    Related tools: list_inpi_br_bulk_releases, search_inpi_br_statutes,
    get_inpi_br_section.
    """
    async with InpiBrBulkClient() as client:
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
                "source_name": _INPI_BR_BULK_NAME,
                "source_url": f"{CKAN_HOST}/dataset/{dataset_id}",
            }
    raise NotFoundError(
        f"resource_id {resource_id!r} not found in dataset {dataset_id!r}. "
        f"Use list_inpi_br_bulk_releases to list current resources."
    )


__all__ = ["inpi_br_bulk_mcp"]
