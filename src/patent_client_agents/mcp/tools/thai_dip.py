"""Catalogue-schema tested MCP tools for Thailand's DIP Data Exchange."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, cast

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from mcp_data_core.mcp.conditional import conditional_resource, conditional_tool
from patent_client_agents.thai_dip import api
from patent_client_agents.thai_dip.client import (
    BASE_URL,
    LIST_ACCEPT_CAP,
    RESULT_LIMIT,
    ThaiDipClient,
)
from patent_client_agents.thai_dip.models import (
    ThaiDipCopyrightRecord,
    ThaiDipGiRecord,
    ThaiDipPatentRecord,
    ThaiDipTrademarkRecord,
)
from patent_client_agents.thai_dip.resources import USAGE

thai_dip_mcp = FastMCP("Thailand DIP Data Exchange")
_REQUIRED_ENV = ["DIP_DATA_EXCHANGE_TOKEN"]
_SOURCE_NAME = (
    "Department of Intellectual Property, Thailand, DIP Data Exchange. "
    "Catalogue-schema tested with synthetic fixtures; live compatibility unverified."
)
_FANOUT_CONCURRENCY = 5


def _provenance(endpoint: str) -> Any:
    return make_provenance(
        source_url=f"{BASE_URL}/{endpoint}",
        source_name=_SOURCE_NAME,
    )


def _dump(record: Any, full: bool) -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        record.model_dump(mode="json", exclude=None if full else {"raw"}),
    )


def _numbers(value: str | list[str]) -> list[str]:
    values = [value] if isinstance(value, str) else list(value)
    values = [item.strip() for item in values if item.strip()]
    if not values:
        raise ValidationError("At least one identifier is required")
    if len(values) > LIST_ACCEPT_CAP:
        raise ValidationError(f"A maximum of {LIST_ACCEPT_CAP} identifiers is allowed")
    return values


def _search_result(
    label: str,
    query: str,
    rows: list[Any],
    total: int,
    endpoint: str,
    full: bool,
) -> ListEnvelope[dict]:
    items = [_dump(row, full) for row in rows]
    return ListEnvelope(
        summary=(
            f"Thailand DIP {label} search for `{query}`: {len(items)} of {total} records. "
            "Catalogue-schema tested; live compatibility unverified."
        ),
        items=items,
        more_available=total > len(items),
        next_cursor=None,
        provenance=_provenance(endpoint),
    )


def _fetch_result(label: str, rows: list[Any], endpoint: str, full: bool) -> ListEnvelope[dict]:
    items = [_dump(row, full) for row in rows]
    return ListEnvelope(
        summary=(
            f"Thailand DIP {label} exact-identifier search: {len(items)} records. "
            "The upstream API has no distinct fetch operation."
        ),
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(endpoint),
    )


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= RESULT_LIMIT:
        raise ValidationError(f"limit must be between 1 and {RESULT_LIMIT}")


@conditional_resource(
    thai_dip_mcp,
    "pca://thai-dip/usage",
    mime_type="text/markdown",
    name="Thailand DIP connector status and usage",
    description="BYOK setup, test status, upstream limits, and community validation request.",
    requires_env=_REQUIRED_ENV,
)
async def thai_dip_usage() -> str:
    return USAGE


@conditional_tool(thai_dip_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_thai_dip_patents(
    query: str,
    right_type: Literal["invention", "design", "petty_patent"] = "invention",
    field: Literal["title", "application_number", "publication_number", "patent_number"] = "title",
    limit: int = 25,
    full: bool = False,
) -> ListEnvelope[dict]:
    """Search Thai invention patents, design patents, or petty patents.

    Related tools: get_thai_dip_patent.
    """
    _validate_limit(limit)
    rows, total = await api.search_thai_dip_patents(
        query, right_type=right_type, field=field, limit=limit
    )
    endpoint = {
        "invention": "PATENT_NOIP",
        "design": "PRODUCTPATENT",
        "petty_patent": "PETTYPATENT",
    }[right_type]
    return _search_result("patent", query, rows, total, endpoint, full)


@conditional_tool(thai_dip_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_thai_dip_patent(
    application_number: str | list[str],
    right_type: Literal["invention", "design", "petty_patent"] = "invention",
    full: bool = False,
) -> ListEnvelope[dict]:
    """Fetch Thai patent records by exact application-number search.

    DIP exposes no distinct fetch operation, so this uses the documented search endpoint.
    Related tools: search_thai_dip_patents.
    """
    numbers = _numbers(application_number)
    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)
    async with ThaiDipClient() as client:

        async def fetch(number: str) -> ThaiDipPatentRecord:
            async with semaphore:
                return await client.get_patent(number, right_type=right_type)

        rows = await asyncio.gather(*(fetch(number) for number in numbers))
    endpoint = {
        "invention": "PATENT_NOIP",
        "design": "PRODUCTPATENT",
        "petty_patent": "PETTYPATENT",
    }[right_type]
    return _fetch_result("patent", rows, endpoint, full)


@conditional_tool(thai_dip_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_thai_dip_trademarks(
    query: str,
    field: Literal["name", "application_number", "registration_number", "expiry_date"] = "name",
    limit: int = 25,
    full: bool = False,
) -> ListEnvelope[dict]:
    """Search Thai national trademarks.

    Related tools: get_thai_dip_trademark.
    """
    _validate_limit(limit)
    rows, total = await api.search_thai_dip_trademarks(query, field=field, limit=limit)
    return _search_result("trademark", query, rows, total, "TM", full)


@conditional_tool(thai_dip_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_thai_dip_trademark(
    application_number: str | list[str], full: bool = False
) -> ListEnvelope[dict]:
    """Fetch Thai trademarks by exact application-number search.

    DIP exposes no distinct fetch operation, so this uses the documented search endpoint.
    Related tools: search_thai_dip_trademarks.
    """
    numbers = _numbers(application_number)
    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)
    async with ThaiDipClient() as client:

        async def fetch(number: str) -> ThaiDipTrademarkRecord:
            async with semaphore:
                return await client.get_trademark(number)

        rows = await asyncio.gather(*(fetch(number) for number in numbers))
    return _fetch_result("trademark", rows, "TM", full)


@conditional_tool(thai_dip_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_thai_dip_copyrights(
    query: str,
    field: Literal[
        "work_name", "work_type", "request_number", "registration_number", "owner"
    ] = "work_name",
    limit: int = 25,
    full: bool = False,
) -> ListEnvelope[dict]:
    """Search Thailand's voluntary copyright notification register.

    Related tools: get_thai_dip_copyright, search_thai_dip_songs.
    """
    _validate_limit(limit)
    rows, total = await api.search_thai_dip_copyrights(query, field=field, limit=limit)
    return _search_result("copyright", query, rows, total, "CPR", full)


@conditional_tool(thai_dip_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_thai_dip_copyright(
    request_number: str | list[str], full: bool = False
) -> ListEnvelope[dict]:
    """Fetch copyright records by exact request-number search.

    DIP exposes no distinct fetch operation, so this uses the documented search endpoint.
    Related tools: search_thai_dip_copyrights, search_thai_dip_songs.
    """
    numbers = _numbers(request_number)
    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)
    async with ThaiDipClient() as client:

        async def fetch(number: str) -> ThaiDipCopyrightRecord:
            async with semaphore:
                return await client.get_copyright(number)

        rows = await asyncio.gather(*(fetch(number) for number in numbers))
    return _fetch_result("copyright", rows, "CPR", full)


@conditional_tool(thai_dip_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_thai_dip_songs(
    query: str,
    field: Literal["song_name", "album_name", "lyric_author", "composer"] = "song_name",
    limit: int = 25,
    full: bool = False,
) -> ListEnvelope[dict]:
    """Search the Thai music-copyright dataset.

    DIP documents no identifier request field, so this dataset has no fetch tool.
    Related tools: search_thai_dip_copyrights, get_thai_dip_copyright.
    """
    _validate_limit(limit)
    rows, total = await api.search_thai_dip_songs(query, field=field, limit=limit)
    return _search_result("music-copyright", query, rows, total, "CPRSONG", full)


@conditional_tool(thai_dip_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_thai_dip_geographical_indications(
    query: str,
    field: Literal["name", "application_id"] = "name",
    limit: int = 25,
    full: bool = False,
) -> ListEnvelope[dict]:
    """Search Thailand's geographical-indication register.

    Related tools: get_thai_dip_geographical_indication.
    """
    _validate_limit(limit)
    rows, total = await api.search_thai_dip_geographical_indications(
        query, field=field, limit=limit
    )
    return _search_result("geographical-indication", query, rows, total, "GI", full)


@conditional_tool(thai_dip_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_thai_dip_geographical_indication(
    application_id: str | list[str], full: bool = False
) -> ListEnvelope[dict]:
    """Fetch GI records by exact numeric application-ID search.

    DIP exposes no distinct fetch operation, so this uses the documented search endpoint.
    Related tools: search_thai_dip_geographical_indications.
    """
    numbers = _numbers(application_id)
    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)
    async with ThaiDipClient() as client:

        async def fetch(number: str) -> ThaiDipGiRecord:
            async with semaphore:
                return await client.get_geographical_indication(number)

        rows = await asyncio.gather(*(fetch(number) for number in numbers))
    return _fetch_result("geographical-indication", rows, "GI", full)
