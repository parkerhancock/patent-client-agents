"""Consolidated bulk-data & document-download facade tools (public toolset).

Thin dispatchers over the per-source bulk-catalog and download functions in
``patent_client_agents.mcp.tools.{uspto,patents,cafc,usitc,ip_australia_bulk}``.
No business logic lives here: each branch forwards to an existing function
that already returns its canonical result (a §5.9 envelope for bulk-data
    search, or structured signed-URL records for downloads), so the
§5.15 per-module helpers and the canonical templates stay untouched.

Design note — ``download_document`` folds nine sources behind one ``source``
enum. The nine downloaders do NOT share a homogeneous signature (patent_pdf
takes a patent number; cafc an appeal number; the four PTAB downloaders a
proceeding/application number plus item/date filters; usitc_attachment a
document_id+attachment_id pair; usitc_investigation an investigation number
plus type/date filters; ipa_bulk a CKAN release_id). Forcing them into one
fat positional signature would reintroduce the argument-shape ambiguity this
consolidation exists to remove. Instead we keep a single tool with one
mandatory ``source`` enum plus a small bag of clearly-scoped optional params,
    documented per-source. All nine return the same downstream contract
    (structured signed URLs and download metadata), so ``-> Any`` is honest and one
tool is defensible (the doc's ⚠️ secondary-eval flag).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP

from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.mcp.tools.cafc import download_cafc_pdf
from patent_client_agents.mcp.tools.ip_australia_bulk import (
    download_ipa_bulk,
    list_ipa_bulk_releases,
)

# Clean-source PDF path (PPUBS → EPO; no Google Patents hop). Aliased to the
# original name so the source='patent_pdf' branch below is unchanged.
from patent_client_agents.mcp.tools.patents import (
    download_patent_pdf_clean as download_patent_pdf,
)
from patent_client_agents.mcp.tools.usitc import (
    download_usitc_attachment,
    download_usitc_investigation_documents,
)
from patent_client_agents.mcp.tools.uspto import (
    download_ptab_appeal_decisions,
    download_ptab_interference_decisions,
    download_ptab_trial_decisions,
    download_ptab_trial_documents,
    search_bulk_datasets,
)
from patent_client_agents.usitc.utils import get_env_token
from patent_client_agents.uspto_odp import UsptoOdpClient

from ._download_proxy import rewrite_auth_urls

documents_facade_mcp = FastMCP("Bulk data & documents")

# Mirrors the EDIS gate in .litigation / patent_client_agents.mcp.tools.usitc:
# when neither EDIS token setting is usable the public demo advertises no ITC surface,
# so the usitc_* source values must drop out of the enum too. The dispatch
# branches below stay in place — they are simply unreachable via the schema.
EDIS_ENABLED = bool(get_env_token("USITC_EDIS_TOKEN"))

if EDIS_ENABLED:
    _DownloadSource = Literal[
        "patent_pdf",
        "cafc",
        "ptab_appeal",
        "ptab_interference",
        "ptab_trial",
        "ptab_trial_docs",
        "usitc_attachment",
        "usitc_investigation",
        "ipa_bulk",
    ]
    _SOURCE_DESC = (
        "Which document repository to download from. 'patent_pdf' = a patent/"
        "publication PDF (USPTO PPUBS → EPO OPS cascade). 'cafc' = a "
        "Federal Circuit opinion PDF. 'ptab_appeal'/'ptab_interference' = "
        "PTAB ex parte appeal / pre-AIA interference decisions. 'ptab_trial' = "
        "AIA trial board decisions; 'ptab_trial_docs' = AIA trial party "
        "filings. 'usitc_attachment' = one EDIS attachment; "
        "'usitc_investigation' = all attachments for a 337 investigation. "
        "'ipa_bulk' = resolve an IP Australia IP RAPID release to its URL."
    )
    _IDENTIFIER_DESC = (
        "Primary key for the source. patent_pdf → patent/publication number "
        "('US10123456B2'); cafc → appeal number ('2023-1234'); ptab_trial/"
        "ptab_trial_docs → AIA trial number ('IPR2024-00001'); ptab_appeal → "
        "application number ('16123456'); ptab_interference → interference "
        "number; usitc_investigation → investigation number ('337-TA-1234'); "
        "ipa_bulk → CKAN release id (from search_bulk_data mode='ipa_releases'). "
        "Not used for usitc_attachment (uses document_id/attachment_id)."
    )
else:
    _DownloadSource = Literal[
        "patent_pdf",
        "cafc",
        "ptab_appeal",
        "ptab_interference",
        "ptab_trial",
        "ptab_trial_docs",
        "ipa_bulk",
    ]
    _SOURCE_DESC = (
        "Which document repository to download from. 'patent_pdf' = a patent/"
        "publication PDF (USPTO PPUBS → EPO OPS cascade). 'cafc' = a "
        "Federal Circuit opinion PDF. 'ptab_appeal'/'ptab_interference' = "
        "PTAB ex parte appeal / pre-AIA interference decisions. 'ptab_trial' = "
        "AIA trial board decisions; 'ptab_trial_docs' = AIA trial party "
        "filings. 'ipa_bulk' = resolve an IP Australia IP RAPID release to "
        "its URL."
    )
    _IDENTIFIER_DESC = (
        "Primary key for the source. patent_pdf → patent/publication number "
        "('US10123456B2'); cafc → appeal number ('2023-1234'); ptab_trial/"
        "ptab_trial_docs → AIA trial number ('IPR2024-00001'); ptab_appeal → "
        "application number ('16123456'); ptab_interference → interference "
        "number; ipa_bulk → CKAN release id (from search_bulk_data "
        "mode='ipa_releases')."
    )


async def _get_bulk_dataset_proxied(product_id: str, latest_only: bool) -> dict:
    """Fetch a USPTO bulk product's file listing with proxy-rewritten URLs.

    Calls the ODP client directly (not the open-core ``get_bulk_dataset`` tool,
    which strips the key-gated ``fileDownloadURI`` before we could rewrite it),
    then rewrites each bulk file URL to the signed download proxy via
    ``rewrite_auth_urls``. With no proxy configured the URLs are stripped, so
    the response matches the open-core shape. Each file's ``fileDownloadURI``
    becomes a ready-to-use, keyless download URL; ``fileSize`` is in bytes.
    """
    async with UsptoOdpClient() as client:
        result = await client.get_bulk_dataset_product(
            product_id, include_files=True, latest_only=latest_only or None
        )
    data = result.model_dump()
    rewrite_auth_urls(data)
    return data


@documents_facade_mcp.tool(annotations=READ_ONLY)
async def search_bulk_data(
    mode: Annotated[
        Literal["datasets", "dataset", "ipa_releases"],
        "Which bulk catalog to hit. 'datasets' = search the USPTO bulk data "
        "product catalog by keyword. 'dataset' = fetch one USPTO bulk product's "
        "details and file listing by product id. 'ipa_releases' = list IP "
        "Australia IP RAPID (Australian bulk register) releases on data.gov.au.",
    ],
    query: Annotated[
        str | None,
        "mode='datasets': keyword query over USPTO bulk product names. Required "
        "for that mode; ignored otherwise.",
    ] = None,
    product_id: Annotated[
        str | None,
        "mode='dataset': USPTO bulk data product identifier (from "
        "mode='datasets'). Required for that mode; ignored otherwise.",
    ] = None,
    dataset_id: Annotated[
        str,
        "mode='ipa_releases': data.gov.au CKAN dataset id. Defaults to "
        "'iprapid' (the weekly snapshot). Ignored for the USPTO modes.",
    ] = "iprapid",
    latest_only: Annotated[
        bool,
        "mode='dataset': return only the most recent file in the product "
        "(default False returns the full listing — some products have hundreds). "
        "Ignored for the other modes.",
    ] = False,
) -> Any:
    """Browse bulk IP data catalogs — USPTO bulk products or IP Australia register releases.

    Routes by ``mode``. 'datasets' searches the USPTO bulk product catalog;
    'dataset' fetches one product's file listing (each file carries a
    ready-to-use download URL when the download proxy is configured — fetch it
    directly, no API key needed); 'ipa_releases' enumerates downloadable IP
    Australia IP RAPID register snapshots. Resolve a listed release to a
    download URL with ``download_document`` (source='ipa_bulk').

    Related tools: download_document.
    """
    if mode == "datasets":
        if not query:
            raise ValidationError("search_bulk_data(mode='datasets') requires query.")
        return await search_bulk_datasets(query=query)
    if mode == "dataset":
        if not product_id:
            raise ValidationError("search_bulk_data(mode='dataset') requires product_id.")
        return await _get_bulk_dataset_proxied(product_id, latest_only)
    return await list_ipa_bulk_releases(dataset_id=dataset_id)


@documents_facade_mcp.tool(annotations=READ_ONLY)
async def download_document(
    source: Annotated[_DownloadSource, _SOURCE_DESC],
    identifier: Annotated[str | None, _IDENTIFIER_DESC] = None,
    document_id: Annotated[int | None, "usitc_attachment only: EDIS document id."] = None,
    attachment_id: Annotated[int | None, "usitc_attachment only: EDIS attachment id."] = None,
    dataset_id: Annotated[
        str,
        "ipa_bulk only: parent CKAN dataset id (defaults to 'iprapid').",
    ] = "iprapid",
    item_ids: Annotated[
        list[str] | None,
        "ptab_* and usitc_investigation: specific document identifiers to "
        "fetch. None = all matching the other filters.",
    ] = None,
    document_types: Annotated[
        list[str] | None,
        "usitc_investigation only: filter to these EDIS document types "
        "(e.g. ['Motion', 'Order']). Must match exactly.",
    ] = None,
    after: Annotated[
        str | None,
        "ptab_* and usitc_investigation: only docs on/after this date (YYYY-MM-DD).",
    ] = None,
    before: Annotated[
        str | None,
        "ptab_* and usitc_investigation: only docs on/before this date (YYYY-MM-DD).",
    ] = None,
) -> Any:
    """Download a patent, court, PTAB, USITC, or bulk-register document by source.

    Routes by ``source`` to the matching downloader. Return shape is uniform
    across sources: single-file sources return one structured signed-URL
    record; bulk sources return a zip URL plus a manifest. ptab_trial caps at
    50 decisions and 100 documents; usitc caps at
    25 attachments — narrow with item_ids / document_types / date range.

    Related tools: search_bulk_data, search_ptab, search_cafc_opinions,
    get_patent.
    """
    if source == "patent_pdf":
        if not identifier:
            raise ValidationError("download_document(source='patent_pdf') requires identifier.")
        return await download_patent_pdf(identifier)
    if source == "cafc":
        if not identifier:
            raise ValidationError("download_document(source='cafc') requires identifier.")
        return await download_cafc_pdf(identifier)
    if source == "ptab_trial":
        if not identifier:
            raise ValidationError("download_document(source='ptab_trial') requires identifier.")
        return await download_ptab_trial_decisions(
            identifier, item_ids=item_ids, after=after, before=before
        )
    if source == "ptab_trial_docs":
        if not identifier:
            raise ValidationError(
                "download_document(source='ptab_trial_docs') requires identifier."
            )
        return await download_ptab_trial_documents(
            identifier, item_ids=item_ids, after=after, before=before
        )
    if source == "ptab_appeal":
        if not identifier:
            raise ValidationError("download_document(source='ptab_appeal') requires identifier.")
        return await download_ptab_appeal_decisions(
            identifier, item_ids=item_ids, after=after, before=before
        )
    if source == "ptab_interference":
        if not identifier:
            raise ValidationError(
                "download_document(source='ptab_interference') requires identifier."
            )
        return await download_ptab_interference_decisions(
            identifier, item_ids=item_ids, after=after, before=before
        )
    if source == "usitc_attachment":
        if document_id is None or attachment_id is None:
            raise ValidationError(
                "download_document(source='usitc_attachment') requires "
                "document_id and attachment_id."
            )
        return await download_usitc_attachment(document_id, attachment_id)
    if source == "usitc_investigation":
        if not identifier:
            raise ValidationError(
                "download_document(source='usitc_investigation') requires identifier."
            )
        return await download_usitc_investigation_documents(
            identifier,
            item_ids=item_ids,
            document_types=document_types,
            after=after,
            before=before,
        )
    # source == "ipa_bulk"
    if not identifier:
        raise ValidationError("download_document(source='ipa_bulk') requires identifier.")
    return await download_ipa_bulk(identifier, dataset_id=dataset_id)


__all__ = ["documents_facade_mcp"]
