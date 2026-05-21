"""IP Australia — IP RAPID bulk catalog MCP tools.

IP RAPID is IP Australia's weekly bulk dump of the registered IP
register (patents + trade marks + designs + plant breeder's rights)
published on ``data.gov.au`` under a Creative Commons licence. No
auth.

This is the **catalog + download** surface (Shape E in
CONNECTOR_STANDARDS.md §7.2): one tool lists the current resources
within the IP RAPID dataset, and one tool resolves a resource id to a
direct ``data.gov.au`` download URL. The URL is the upstream CKAN URL
— stable, unauthenticated, and routable by any HTTP client; we do not
proxy the bytes through our own download cache because the data zip is
~1.3 GB.

Full CSV ingestion of the ~40 IP RAPID tables is intentionally out of
scope for v1; it will land in a follow-up so this PR ships the OAuth
search-API surface (patents / trade marks / designs) independently.
"""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import NotFoundError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.ip_australia_bulk import CKAN_HOST, IpAustraliaBulkClient

ip_australia_bulk_mcp = FastMCP("IP Australia — IP RAPID")

_IPA_BULK_NAME = "IP Australia — IP RAPID (data.gov.au)"


def _ipa_bulk_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{CKAN_HOST}{path}``."""
    return make_provenance(
        source_url=f"{CKAN_HOST}{path}",
        source_name=_IPA_BULK_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict via ``model_dump(by_alias=True)``."""
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump(by_alias=True))  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


_DEFAULT_DATASET_ID = "iprapid"


# ---------------------------------------------------------------------------
# list_ipa_bulk_releases
# ---------------------------------------------------------------------------


@ip_australia_bulk_mcp.tool(annotations=READ_ONLY)
async def list_ipa_bulk_releases(
    dataset_id: Annotated[
        str,
        "data.gov.au CKAN dataset id. Defaults to 'iprapid' (the weekly "
        "snapshot). Pass an alternate id (e.g. an annual 'ipgod' release) "
        "to enumerate that dataset's resources instead.",
    ] = _DEFAULT_DATASET_ID,
) -> ListEnvelope[dict]:
    """List downloadable IP RAPID (Australian bulk IP register) releases on data.gov.au.

    Each item carries the CKAN resource id (use it as ``release_id`` in
    ``download_ipa_bulk``), the human-readable name, the file format
    and size, the last-modified timestamp, and the canonical data.gov.au
    download URL. IP RAPID is currently two resources: the data
    dictionary PDF and the full ~1.3 GB CSV zip, refreshed weekly.

    Related tools: download_ipa_bulk, search_ipa_patents,
    search_ipa_trademarks, search_ipa_designs.
    """
    async with IpAustraliaBulkClient() as client:
        dataset = await client.get_dataset(dataset_id)

    dumped = _dump(dataset)
    resources = list(dumped.get("resources") or [])
    items: list[dict] = []
    for raw in resources:
        items.append(
            {
                "release_id": raw.get("id"),
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
        f"IP Australia bulk — `{dataset_id}` ({license_label}): "
        f"{len(items)} downloadable resource(s)."
    )
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_ipa_bulk_provenance(f"/data/dataset/{dataset_id}"),
    )


# ---------------------------------------------------------------------------
# download_ipa_bulk
# ---------------------------------------------------------------------------


@ip_australia_bulk_mcp.tool(annotations=READ_ONLY)
async def download_ipa_bulk(
    release_id: Annotated[
        str,
        "CKAN resource id from list_ipa_bulk_releases (e.g. "
        "'c79b3af6-3720-44ac-9e39-6a68f5635924' for the current "
        "IPRAPID.zip).",
    ],
    dataset_id: Annotated[
        str,
        "Parent dataset id (defaults to 'iprapid'). Pass a different "
        "value to look the resource up inside a non-default dataset.",
    ] = _DEFAULT_DATASET_ID,
) -> dict:
    """Resolve an IP RAPID release id to a direct data.gov.au download URL.

    Returns the upstream URL plus the resource metadata (format, size,
    last-modified). The URL is public and unauthenticated — fetch it
    with any HTTP client. We deliberately do not proxy the ~1.3 GB
    bytes through our download cache.

    Related tools: list_ipa_bulk_releases, search_ipa_patents,
    search_ipa_trademarks, search_ipa_designs.
    """
    async with IpAustraliaBulkClient() as client:
        dataset = await client.get_dataset(dataset_id)

    dumped = _dump(dataset)
    for raw in dumped.get("resources") or []:
        if raw.get("id") == release_id:
            return {
                "release_id": release_id,
                "dataset_id": dataset_id,
                "name": raw.get("name"),
                "description": raw.get("description"),
                "format": raw.get("format"),
                "mimetype": raw.get("mimetype"),
                "size_bytes": raw.get("size"),
                "last_modified": raw.get("last_modified"),
                "download_url": raw.get("url"),
                "license": dumped.get("license_title") or dumped.get("license_id"),
                "source_name": _IPA_BULK_NAME,
                "source_url": f"{CKAN_HOST}/data/dataset/{dataset_id}",
            }
    raise NotFoundError(
        f"release_id {release_id!r} not found in dataset {dataset_id!r}. "
        f"Use list_ipa_bulk_releases to list current resources."
    )


__all__ = ["ip_australia_bulk_mcp"]
