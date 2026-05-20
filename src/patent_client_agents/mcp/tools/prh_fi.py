"""PRH (Finland) — MCP tools.

Read-only access to the Finnish Patent and Registration Office's
three undocumented but unauthenticated JSON APIs:
``patenttitietopalvelu.prh.fi`` (patents + UM + SPC + EP-FI),
``tavaramerkkitietopalvelu.prh.fi`` (trademarks + well-known TMR),
and ``mallioikeustietopalvelu.prh.fi`` (designs). No env vars
required; production callers should send a courtesy registration to
``avoindata@prh.fi``.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from law_tools_core.mcp.downloads import download_response
from patent_client_agents.prh_fi import PrhClient
from patent_client_agents.prh_fi.client import (
    DESIGN_HOST,
    DESIGN_PATH,
    PATENT_HOST,
    PATENT_PATH,
    SERVER_RESULT_CAP,
    TMR_PATH,
    TRADEMARK_HOST,
    TRADEMARK_PATH,
)

prh_fi_mcp = FastMCP("PRH Finland")

_PRH_SOURCE_NAME = "Patentti- ja rekisterihallitus (PRH, Finland)"
_PRH_FANOUT_CONCURRENCY = 5


def _provenance(source_url: str) -> Any:
    return make_provenance(source_url=source_url, source_name=_PRH_SOURCE_NAME)


def _dump(model: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", model.model_dump(by_alias=True, exclude_none=False))


def _coerce_list(value: str | list[str], *, tool: str) -> list[str]:
    items = [value] if isinstance(value, str) else list(value)
    items = [s.strip() for s in items if isinstance(s, str) and s.strip()]
    if not items:
        raise ValidationError(f"{tool} requires at least one application number")
    return items


def _project_dossier_row(row: Any, *, full: bool) -> dict[str, Any]:
    """Dump a dossier-search row. Lean view drops the thumbnail URL
    triplet (the image_url alone is sufficient) and the ``ordinal``
    field (a 1-indexed echo of result-list position)."""
    data = _dump(row)
    if full:
        return data
    for k in ("thumbnailUrl", "largeThumbnailUrl", "ordinal"):
        data.pop(k, None)
    return data


def _project_patent_search_row(row: Any, *, full: bool) -> dict[str, Any]:
    """Dump a patent-search row. Lean view drops the ``ordinal`` slot."""
    data = _dump(row)
    if full:
        return data
    data.pop("ordinal", None)
    return data


_PATENT_GET_LEAN_DROP = {
    # Heavy file-history listing — useful but bulky; available via full=True.
    "documents",
    # paymentDetails is a deeply-nested object; agents rarely need the timeline.
    "paymentDetails",
    # events are usually empty for granted patents and the per-event schema is opaque.
    "events",
}


def _project_patent_get(record: Any, *, full: bool) -> dict[str, Any]:
    """Dump a PatentGetRecord. Lean view drops the file-history pointer
    list, payment timeline, and raw events."""
    data = _dump(record)
    if full:
        return data
    for k in _PATENT_GET_LEAN_DROP:
        data.pop(k, None)
    return data


def _summarize_search(label: str, total: int, returned: int, hint: str | None) -> str:
    cap_note = ""
    if total >= SERVER_RESULT_CAP and returned >= SERVER_RESULT_CAP:
        cap_note = f" (capped at {SERVER_RESULT_CAP:,}; narrow query for more)"
    if hint:
        return f"PRH {label} — {total:,} total hits for `{hint}`, returned {returned}{cap_note}."
    return f"PRH {label} — {total:,} total hits, returned {returned}{cap_note}."


# ----------------------------------------------------------------------
# search_prh_patents
# ----------------------------------------------------------------------


@prh_fi_mcp.tool(annotations=READ_ONLY)
async def search_prh_patents(
    applicant: Annotated[
        str | None,
        "Applicant name filter (substring match). Example: 'Nokia'.",
    ] = None,
    inventor: Annotated[str | None, "Inventor name filter."] = None,
    patent_title: Annotated[str | None, "Title text filter (any language)."] = None,
    application_number: Annotated[
        str | None,
        "Exact PRH application number, e.g. '20100001'.",
    ] = None,
    registration_number: Annotated[
        str | None,
        "Exact PRH registration (patent) number.",
    ] = None,
    ipc_classification: Annotated[
        str | None,
        "IPC class filter, e.g. 'H04R'.",
    ] = None,
    cpc_classification: Annotated[
        str | None,
        "CPC class filter.",
    ] = None,
    filing_start_date: Annotated[
        str | None,
        "Earliest filing date, YYYY-MM-DD.",
    ] = None,
    filing_end_date: Annotated[
        str | None,
        "Latest filing date, YYYY-MM-DD.",
    ] = None,
    patent_types: Annotated[
        list[str] | None,
        "Filter by patent route. Vocabulary: 'PatentDossier' (national), "
        "'PatentDossierUtilityModel', 'PatentEurope' (EP-FI), 'Spc'. "
        "Default returns all four.",
    ] = None,
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Search Finland national patents, utility models, SPCs, and EP-FI validations at PRH.

    Wraps ``POST patenttitietopalvelu.prh.fi/nis-api-gateway-pat/patent``.
    The upstream form takes 30 fields; the most useful filters are
    exposed here directly. Inclusion-filter defaults
    (``dossierStatus``, ``patentTypes``, ``publicationTypes``) are
    supplied automatically so a caller setting only ``applicant`` still
    gets results. Server caps the response at 3,000 rows.

    Related tools: ``get_prh_patent`` for the full register record
    with prosecution events and named examiner; ``search_epo_patents``
    for FI-validated EP patents at INPADOC fidelity.
    """
    async with PrhClient() as client:
        result = await client.search_patents(
            applicant=applicant,
            inventor=inventor,
            patent_title=patent_title,
            application_number=application_number,
            registration_number=registration_number,
            ipc_classification=ipc_classification,
            cpc_classification=cpc_classification,
            filing_start_date=filing_start_date,
            filing_end_date=filing_end_date,
            patent_types=patent_types,
        )
    items = [_project_patent_search_row(r, full=full) for r in result.results]
    hint = applicant or inventor or patent_title or application_number
    return ListEnvelope[dict](
        summary=_summarize_search("patents", result.total_results, len(items), hint),
        items=items,
        more_available=result.total_results > len(items),
        next_cursor=None,
        provenance=_provenance(f"{PATENT_HOST}{PATENT_PATH}"),
    )


# ----------------------------------------------------------------------
# get_prh_patent
# ----------------------------------------------------------------------


@prh_fi_mcp.tool(annotations=READ_ONLY)
async def get_prh_patent(
    application_number: Annotated[
        str | list[str],
        "PRH application number(s), e.g. '20100001'. Pass a list for portfolio fan-outs.",
    ],
    full: Annotated[
        bool,
        "When False (default), drops the file-history pointer list, "
        "payment timeline, and raw events array to keep responses lean.",
    ] = False,
) -> ListEnvelope[dict]:
    """Fetch one or more Finland patent register records from PRH.

    Wraps ``GET patenttitietopalvelu.prh.fi/nis-api-gateway-pat/patent/{n}``.
    Returns the full register entry with trilingual title and abstracts
    (FI/SV/EN), prosecution events, file-history pointers, named
    examiner, payment timeline, and SPC authorizations.

    Related tools: ``search_prh_patents`` to find candidate
    application numbers; ``get_epo_biblio`` for FI-validated EP patents
    at INPADOC fidelity.
    """
    numbers = _coerce_list(application_number, tool="get_prh_patent")
    semaphore = asyncio.Semaphore(_PRH_FANOUT_CONCURRENCY)

    async def _fetch_one(client: PrhClient, num: str) -> Any:
        async with semaphore:
            return await client.get_patent(num)

    async with PrhClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    items = [_project_patent_get(r, full=full) for r in results]
    summary = (
        f"PRH patent records — {len(items)} record{'s' if len(items) != 1 else ''} "
        f"for {', '.join(numbers[:5])}{' …' if len(numbers) > 5 else ''}."
    )
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(f"{PATENT_HOST}{PATENT_PATH}/"),
    )


# ----------------------------------------------------------------------
# search_prh_trademarks
# ----------------------------------------------------------------------


@prh_fi_mcp.tool(annotations=READ_ONLY)
async def search_prh_trademarks(
    trademark_word: Annotated[
        str | None,
        "Mark text filter (substring match). Example: 'SISU'.",
    ] = None,
    applicant_name: Annotated[str | None, "Applicant name filter."] = None,
    representative_name: Annotated[str | None, "Representative / agent name filter."] = None,
    business_id: Annotated[
        str | None,
        "Finnish Y-tunnus / Business ID filter (NNNNNNN-N).",
    ] = None,
    application_number: Annotated[str | None, "Exact application number."] = None,
    registration_number: Annotated[str | None, "Exact registration number."] = None,
    goods_and_services_class_number: Annotated[
        str | None,
        "Nice class filter, e.g. '9'.",
    ] = None,
    application_start_date: Annotated[str | None, "Earliest application date, YYYY-MM-DD."] = None,
    application_end_date: Annotated[str | None, "Latest application date, YYYY-MM-DD."] = None,
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Search Finland national trademarks at PRH.

    Wraps ``POST tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/trademark``.
    Covers ~283k national trademarks back to 1891. Mark images are
    accessible via the returned ``imageUrl`` paths. Server caps the
    response at 3,000 rows.

    Related tools: ``search_prh_well_known_trademarks`` for the
    well-known marks register (TMR); ``search_euipo_trademarks`` for
    EU-wide trademarks covering Finland.
    """
    async with PrhClient() as client:
        result = await client.search_trademarks(
            trademark_word=trademark_word,
            applicant_name=applicant_name,
            representative_name=representative_name,
            business_id=business_id,
            application_number=application_number,
            registration_number=registration_number,
            goods_and_services_class_number=goods_and_services_class_number,
            application_start_date=application_start_date,
            application_end_date=application_end_date,
        )
    items = [_project_dossier_row(r, full=full) for r in result.results]
    hint = trademark_word or applicant_name or application_number
    return ListEnvelope[dict](
        summary=_summarize_search("trademarks", result.total_results, len(items), hint),
        items=items,
        more_available=result.total_results > len(items),
        next_cursor=None,
        provenance=_provenance(f"{TRADEMARK_HOST}{TRADEMARK_PATH}"),
    )


# ----------------------------------------------------------------------
# search_prh_well_known_trademarks
# ----------------------------------------------------------------------


@prh_fi_mcp.tool(annotations=READ_ONLY)
async def search_prh_well_known_trademarks(
    trademark_word: Annotated[str | None, "Mark text filter."] = None,
    applicant_name: Annotated[str | None, "Applicant name filter."] = None,
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Search the Finnish well-known trademarks register (TMR) at PRH.

    Wraps ``POST tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/tmr``.
    The TMR records marks recognized as well-known in Finland under
    §6 of the Trade Marks Act (544/2019). ~111 records as of
    2026-05-19; each carries a free-text ``targetGroup`` audience
    description (e.g. '15-44-vuotiaat suomalaiset' for the TAFFEL
    snack mark).

    Related tools: ``search_prh_trademarks`` for the regular national
    trademark register.
    """
    async with PrhClient() as client:
        result = await client.search_well_known_trademarks(
            trademark_word=trademark_word,
            applicant_name=applicant_name,
        )
    items = [_project_dossier_row(r, full=full) for r in result.results]
    hint = trademark_word or applicant_name
    return ListEnvelope[dict](
        summary=_summarize_search(
            "well-known trademarks (TMR)", result.total_results, len(items), hint
        ),
        items=items,
        more_available=result.total_results > len(items),
        next_cursor=None,
        provenance=_provenance(f"{TRADEMARK_HOST}{TMR_PATH}"),
    )


# ----------------------------------------------------------------------
# search_prh_designs
# ----------------------------------------------------------------------


@prh_fi_mcp.tool(annotations=READ_ONLY)
async def search_prh_designs(
    product_title: Annotated[str | None, "Product title filter."] = None,
    applicant_name: Annotated[str | None, "Applicant name filter."] = None,
    designer_name: Annotated[str | None, "Designer name filter."] = None,
    class_number: Annotated[
        str | None,
        "Locarno class filter, e.g. '08'.",
    ] = None,
    application_number: Annotated[str | None, "Exact application number."] = None,
    registration_number: Annotated[str | None, "Exact registration number."] = None,
    full: Annotated[bool, "Lean (default) vs upstream-shaped rows."] = False,
) -> ListEnvelope[dict]:
    """Search Finland national design (malli) registrations at PRH.

    Wraps ``POST mallioikeustietopalvelu.prh.fi/nis-api-gateway/design``.
    Covers ~34k national designs back to 1971. Each dossier may
    carry multiple ``designs[]`` embodiments with Locarno
    classifications and image URLs. Server caps the response at 3,000
    rows.

    Related tools: EUIPO Registered Community Designs (covers FI
    transitively); WIPO Hague IR coverage via Hague Monitor.
    """
    async with PrhClient() as client:
        result = await client.search_designs(
            product_title=product_title,
            applicant_name=applicant_name,
            designer_name=designer_name,
            class_number=class_number,
            application_number=application_number,
            registration_number=registration_number,
        )
    items = [_project_dossier_row(r, full=full) for r in result.results]
    hint = product_title or applicant_name or designer_name
    return ListEnvelope[dict](
        summary=_summarize_search("designs", result.total_results, len(items), hint),
        items=items,
        more_available=result.total_results > len(items),
        next_cursor=None,
        provenance=_provenance(f"{DESIGN_HOST}{DESIGN_PATH}"),
    )


_IMAGE_EXT_BY_CONTENT_TYPE = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _ext_for(content_type: str) -> str:
    base = content_type.split(";", 1)[0].strip().lower()
    return _IMAGE_EXT_BY_CONTENT_TYPE.get(base, "bin")


# ----------------------------------------------------------------------
# download_prh_trademark_image
# ----------------------------------------------------------------------


@prh_fi_mcp.tool(annotations=READ_ONLY)
async def download_prh_trademark_image(
    application_number: Annotated[
        str,
        "PRH trademark application number, e.g. 'T196503880'.",
    ],
    registration_number: Annotated[
        str | None,
        "PRH trademark registration number, e.g. '49497'. Omit for "
        "well-known TMR rows (registered without a separate regno).",
    ] = None,
    variant: Annotated[
        str,
        "Image variant: 'image' (default, full-size), 'thumbnail', 'thumbnail/large'.",
    ] = "image",
) -> dict:
    """Download a Finland national trademark mark image from PRH.

    Wraps ``GET tavaramerkkitietopalvelu.prh.fi/opendata/trademark/{variant}/...``.
    Returns a signed ``download_url`` + ``filename`` + ``content_type``
    + ``size_bytes`` (hosted mode) or a local ``file_path`` (stdio
    mode). The same path is reachable via the MCP ``resources/read``
    handler for clients that prefer that transport.

    Use the ``imageUrl`` / ``thumbnailUrl`` / ``largeThumbnailUrl``
    fields from ``search_prh_trademarks`` rows to choose the right
    identifiers.

    Related tools: ``search_prh_trademarks``,
    ``search_prh_well_known_trademarks``, ``download_prh_design_image``.
    """
    async with PrhClient() as client:
        content, content_type = await client.download_trademark_image(
            application_number,
            registration_number,
            variant=variant,
        )
    ext = _ext_for(content_type)
    appno_part = application_number.strip()
    regno_part = (registration_number or "").strip()
    label = f"{appno_part}-{regno_part}" if regno_part else appno_part
    resource_path = (
        f"prh_fi/trademark/{variant.replace('/', '_')}/{appno_part}/{regno_part or 'none'}"
    )
    return await download_response(
        resource_path,
        content,
        filename=f"prh-tm-{label}-{variant.replace('/', '_')}.{ext}",
        content_type=content_type,
        application_number=appno_part,
        registration_number=regno_part or None,
        variant=variant,
    )


# ----------------------------------------------------------------------
# download_prh_design_image
# ----------------------------------------------------------------------


@prh_fi_mcp.tool(annotations=READ_ONLY)
async def download_prh_design_image(
    image_id: Annotated[
        str,
        "Per-embodiment design image identifier, e.g. 'M19710014.1.1' "
        "(from the ``dominantViewImageUrl`` slot on a design dossier row).",
    ],
    variant: Annotated[
        str,
        "Image variant: 'image' (default, full-size), 'thumbnail', 'thumbnail/medium'.",
    ] = "image",
) -> dict:
    """Download a Finland national design embodiment image from PRH.

    Wraps ``GET mallioikeustietopalvelu.prh.fi/opendata/design/{variant}/{image_id}``.
    Returns a signed ``download_url`` + ``filename`` + ``content_type``
    + ``size_bytes`` (hosted mode) or a local ``file_path`` (stdio mode).

    Use the ``dominantViewImageUrl`` / ``dominantViewSmallThumbnailUrl``
    / ``dominantViewMediumThumbnailUrl`` fields from
    ``search_prh_designs`` rows to choose identifiers.

    Related tools: ``search_prh_designs``,
    ``download_prh_trademark_image``.
    """
    async with PrhClient() as client:
        content, content_type = await client.download_design_image(
            image_id,
            variant=variant,
        )
    ext = _ext_for(content_type)
    safe_id = image_id.strip().replace("/", "_")
    resource_path = f"prh_fi/design/{variant.replace('/', '_')}/{safe_id}"
    return await download_response(
        resource_path,
        content,
        filename=f"prh-design-{safe_id}-{variant.replace('/', '_')}.{ext}",
        content_type=content_type,
        image_id=image_id.strip(),
        variant=variant,
    )


__all__ = ["prh_fi_mcp"]
