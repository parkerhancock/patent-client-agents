"""Schema-tested MCP tools for the Swiss IPI Swissreg datadelivery API."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from mcp_data_core.mcp.conditional import conditional_resource, conditional_tool
from patent_client_agents.ipi_swissreg import api
from patent_client_agents.ipi_swissreg.client import (
    BASE_URL,
    LIST_ACCEPT_CAP,
    MAX_PAGE_SIZE,
    IpiSwissregClient,
)
from patent_client_agents.ipi_swissreg.models import (
    IpiPatentRecord,
    IpiPublicationRecord,
    IpiSearchMeta,
    IpiSpcRecord,
    IpiTrademarkRecord,
)
from patent_client_agents.ipi_swissreg.resources import USAGE

ipi_swissreg_mcp = FastMCP("Swiss IPI, Swissreg datadelivery")
_REQUIRED_ENV = ["IPI_DATA_USERNAME", "IPI_DATA_PASSWORD"]
_SOURCE_NAME = (
    "Swiss Federal Institute of Intellectual Property (IPI), Swissreg datadelivery API. "
    "Schema-tested against public IPI XSDs; live account compatibility unverified."
)
_FANOUT_CONCURRENCY = 5


def _provenance() -> Any:
    return make_provenance(source_url=BASE_URL, source_name=_SOURCE_NAME)


def _dump(record: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", record.model_dump(mode="json"))


def _date(value: Any) -> str | None:
    return value.isoformat() if value else None


def _lean_patent(record: IpiPatentRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "patent_number": record.patent_number,
        "application_number": record.application_number,
        "publication_number": record.publication_number,
        "title": record.title,
        "status": record.status,
        "owner": record.owner,
        "application_date": _date(record.application_date),
        "publication_date": _date(record.publication_date),
        "grant_date": _date(record.grant_date),
        "ipc": record.ipc,
        "cpc": record.cpc,
        "inventors": record.inventors,
    }


def _lean_trademark(record: IpiTrademarkRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "trademark_number": record.trademark_number,
        "application_number": record.application_number,
        "title": record.title,
        "word_element": record.word_element,
        "status": record.status,
        "owner": record.owner,
        "application_date": _date(record.application_date),
        "registration_date": _date(record.registration_date),
        "expiry_date": _date(record.expiry_date),
        "nice_classification": record.nice_classification,
    }


def _lean_spc(record: IpiSpcRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "spc_number": record.spc_number,
        "application_number": record.application_number,
        "product": record.product,
        "basic_patent_number": record.basic_patent_number,
        "authorisation_number": record.authorisation_number,
        "status": record.status,
        "owner": record.owner,
        "application_date": _date(record.application_date),
        "grant_date": _date(record.grant_date),
        "maximum_term_of_protection_date": _date(record.maximum_term_of_protection_date),
    }


def _lean_publication(record: IpiPublicationRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "right_type": record.right_type,
        "publication_title": record.publication_title,
        "publication_text": record.publication_text,
        "published_remark": record.published_remark,
        "reason_for_publication": record.reason_for_publication,
        "ip_right_number": record.ip_right_number,
        "publication_date": _date(record.publication_date),
        "owner": record.owner,
        "classification": record.classification,
    }


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValidationError(f"limit must be between 1 and {MAX_PAGE_SIZE}")


def _numbers(value: str | list[str]) -> list[str]:
    values = [value] if isinstance(value, str) else list(value)
    if not values or any(not number.strip() for number in values):
        raise ValidationError("At least one non-empty register number is required")
    if len(values) > LIST_ACCEPT_CAP:
        raise ValidationError(f"A maximum of {LIST_ACCEPT_CAP} register numbers is allowed")
    return values


def _search_envelope(
    label: str,
    query: str,
    rows: list[Any],
    meta: IpiSearchMeta,
    lean: Callable[[Any], dict[str, Any]],
    full: bool,
) -> ListEnvelope[dict]:
    items = [_dump(row) for row in rows] if full else [lean(row) for row in rows]
    count = (
        f"{len(items)} of {meta.total_item_count}"
        if meta.total_item_count is not None
        else str(len(items))
    )
    return ListEnvelope(
        summary=f"Swiss IPI {label} search for `{query}`: {count} records. Schema-tested only.",
        items=items,
        more_available=bool(meta.next_cursor),
        next_cursor=meta.next_cursor,
        provenance=_provenance(),
    )


async def _fetch(
    values: str | list[str],
    method_name: str,
    lean: Callable[[Any], dict[str, Any]],
    label: str,
    full: bool,
) -> ListEnvelope[dict]:
    numbers = _numbers(values)
    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)
    async with IpiSwissregClient() as client:
        method: Callable[[str], Awaitable[Any]] = getattr(client, method_name)

        async def one(number: str) -> Any:
            async with semaphore:
                return await method(number)

        rows = await asyncio.gather(*(one(number) for number in numbers))
    items = [_dump(row) for row in rows] if full else [lean(row) for row in rows]
    return ListEnvelope(
        summary=f"Swiss IPI {label} fetch: {len(items)} records. Schema-tested only.",
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(),
    )


@conditional_resource(
    ipi_swissreg_mcp,
    "pca://ipi-swissreg/usage",
    mime_type="text/markdown",
    name="Swiss IPI connector status and usage",
    description="Schema-test status, account setup, limits, and community validation request.",
    requires_env=_REQUIRED_ENV,
)
async def ipi_swissreg_usage() -> str:
    return USAGE


@conditional_tool(ipi_swissreg_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_ipi_patents(
    query: Annotated[str, "Free-text query across Swiss patent fields."],
    limit: Annotated[int, "Maximum records for this page, from 1 through 64."] = 25,
    cursor: Annotated[str | None, "Opaque NextPage cursor from a prior response."] = None,
    full: Annotated[bool, "Include normalized raw XML fields."] = False,
) -> ListEnvelope[dict]:
    """Search Swiss patents. Prefer EPO OPS for ordinary CH bibliography."""
    _validate_limit(limit)
    rows, meta = await api.search_ipi_patents(query, limit=limit, cursor=cursor)
    return _search_envelope("patent", query, rows, meta, _lean_patent, full)


@conditional_tool(ipi_swissreg_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_ipi_patent(patent_number: str | list[str], full: bool = False) -> ListEnvelope[dict]:
    """Fetch Swiss patents. Prefer EPO OPS for ordinary CH bibliography."""
    return await _fetch(patent_number, "get_patent", _lean_patent, "patent", full)


@conditional_tool(ipi_swissreg_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_ipi_patent_publications(
    query: str,
    limit: int = 25,
    cursor: str | None = None,
    full: bool = False,
) -> ListEnvelope[dict]:
    """Search Swiss patent publication notices. Schema-tested only."""
    _validate_limit(limit)
    rows, meta = await api.search_ipi_patent_publications(query, limit=limit, cursor=cursor)
    return _search_envelope("patent publication", query, rows, meta, _lean_publication, full)


@conditional_tool(ipi_swissreg_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_ipi_trademarks(
    query: str,
    limit: int = 25,
    cursor: str | None = None,
    full: bool = False,
) -> ListEnvelope[dict]:
    """Search Swiss national trademark records. Schema-tested only."""
    _validate_limit(limit)
    rows, meta = await api.search_ipi_trademarks(query, limit=limit, cursor=cursor)
    return _search_envelope("trademark", query, rows, meta, _lean_trademark, full)


@conditional_tool(ipi_swissreg_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_ipi_trademark(
    trademark_number: str | list[str], full: bool = False
) -> ListEnvelope[dict]:
    """Fetch Swiss trademark records by trademark number. Schema-tested only."""
    return await _fetch(trademark_number, "get_trademark", _lean_trademark, "trademark", full)


@conditional_tool(ipi_swissreg_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_ipi_spcs(
    query: str,
    limit: int = 25,
    cursor: str | None = None,
    full: bool = False,
) -> ListEnvelope[dict]:
    """Search Swiss supplementary protection certificates. Schema-tested only."""
    _validate_limit(limit)
    rows, meta = await api.search_ipi_spcs(query, limit=limit, cursor=cursor)
    return _search_envelope("SPC", query, rows, meta, _lean_spc, full)


@conditional_tool(ipi_swissreg_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_ipi_spc(spc_number: str | list[str], full: bool = False) -> ListEnvelope[dict]:
    """Fetch Swiss SPC records by certificate number. Schema-tested only."""
    return await _fetch(spc_number, "get_spc", _lean_spc, "SPC", full)


@conditional_tool(ipi_swissreg_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_ipi_spc_publications(
    query: str,
    limit: int = 25,
    cursor: str | None = None,
    full: bool = False,
) -> ListEnvelope[dict]:
    """Search Swiss SPC publication notices. Schema-tested only."""
    _validate_limit(limit)
    rows, meta = await api.search_ipi_spc_publications(query, limit=limit, cursor=cursor)
    return _search_envelope("SPC publication", query, rows, meta, _lean_publication, full)


__all__ = ["ipi_swissreg_mcp"]
