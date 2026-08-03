"""Schema-tested MCP tools for the New Zealand IPONZ v5 API."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any, cast

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from mcp_data_core.mcp.conditional import conditional_resource, conditional_tool
from patent_client_agents.iponz_new_zealand import api
from patent_client_agents.iponz_new_zealand.client import (
    LIST_ACCEPT_CAP,
    MAX_LIST_RESULTS,
    PORTAL_URL,
    PRODUCTION_BASE_URL,
    IponzClient,
)
from patent_client_agents.iponz_new_zealand.models import (
    IponzDesignRecord,
    IponzPatentRecord,
    IponzRegisterSummary,
    IponzTrademarkRecord,
)
from patent_client_agents.iponz_new_zealand.resources import USAGE

iponz_new_zealand_mcp = FastMCP("New Zealand IPONZ")
_REQUIRED_ENV = ["IPONZ_SUBSCRIPTION_KEY"]
_SOURCE_NAME = (
    "Intellectual Property Office of New Zealand (IPONZ) v5 API. "
    "Schema-tested against public OpenAPI and XSD contracts; live subscription unverified."
)
_FANOUT_CONCURRENCY = 5


def _provenance() -> Any:
    return make_provenance(source_url=PRODUCTION_BASE_URL, source_name=_SOURCE_NAME)


def _dump(record: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", record.model_dump(mode="json"))


def _date(value: Any) -> str | None:
    return value.isoformat() if value else None


def _lean_patent(record: IponzPatentRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "patent_number": record.patent_number,
        "international_application_number": record.international_application_number,
        "wipo_publication_number": record.wipo_publication_number,
        "title": record.title,
        "abstract": record.abstract,
        "status": record.status,
        "complete_filed_date": _date(record.complete_filed_date),
        "national_phase_entry_date": _date(record.national_phase_entry_date),
        "published_date": _date(record.published_date),
        "grant_date": _date(record.grant_date),
        "expiry_date": _date(record.expiry_date),
        "applicants": record.applicants,
        "inventors": record.inventors,
        "classifications": record.classifications,
    }


def _lean_trademark(record: IponzTrademarkRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "application_number": record.application_number,
        "registration_number": record.registration_number,
        "international_registration_number": record.international_registration_number,
        "title": record.title,
        "status": record.status,
        "application_date": _date(record.application_date),
        "registration_date": _date(record.registration_date),
        "expiry_date": _date(record.expiry_date),
        "applicants": record.applicants,
        "nice_classes": record.nice_classes,
        "word_marks": record.word_marks,
    }


def _lean_design(record: IponzDesignRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "registration_number": record.registration_number,
        "design_identifier": record.design_identifier,
        "title": record.title,
        "novelty_statement": record.novelty_statement,
        "status": record.status,
        "application_date": _date(record.application_date),
        "registration_date": _date(record.registration_date),
        "expiry_date": _date(record.expiry_date),
        "applicants": record.applicants,
        "articles": record.articles,
    }


def _lean_summary(record: IponzRegisterSummary) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "right_type": record.right_type,
        "status": record.status,
        "event_date": _date(record.event_date),
    }


def _numbers(value: str | list[str]) -> list[str]:
    values = [value] if isinstance(value, str) else list(value)
    if not values or any(not number.strip() for number in values):
        raise ValidationError("At least one non-empty IPONZ register number is required")
    if len(values) > LIST_ACCEPT_CAP:
        raise ValidationError(f"A maximum of {LIST_ACCEPT_CAP} register numbers is allowed")
    return values


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_LIST_RESULTS:
        raise ValidationError(f"limit must be between 1 and {MAX_LIST_RESULTS}")


async def _fetch(
    values: str | list[str],
    method_name: str,
    lean: Callable[[Any], dict[str, Any]],
    label: str,
    full: bool,
) -> ListEnvelope[dict]:
    numbers = _numbers(values)
    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)
    async with IponzClient() as client:
        method: Callable[[str], Awaitable[Any]] = getattr(client, method_name)

        async def one(number: str) -> Any:
            async with semaphore:
                return await method(number)

        rows = await asyncio.gather(*(one(number) for number in numbers))
    items = [_dump(row) for row in rows] if full else [lean(row) for row in rows]
    return ListEnvelope(
        summary=f"IPONZ {label} fetch: {len(items)} records. Schema-tested only.",
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(),
    )


def _list_envelope(
    label: str,
    start: date,
    end: date,
    rows: list[IponzRegisterSummary],
    limit: int,
    full: bool,
) -> ListEnvelope[dict]:
    selected = rows[:limit]
    items = [_dump(row) for row in selected] if full else [_lean_summary(row) for row in selected]
    truncated = len(rows) > limit
    summary = f"IPONZ {label} from {start} through {end}: {len(items)} records."
    if truncated:
        summary += " Split the date range to retrieve omitted records."
    summary += " Schema-tested only."
    return ListEnvelope(
        summary=summary,
        items=items,
        more_available=truncated,
        next_cursor=None,
        provenance=_provenance(),
    )


@conditional_resource(
    iponz_new_zealand_mcp,
    "pca://iponz-new-zealand/usage",
    mime_type="text/markdown",
    name="New Zealand IPONZ connector status and usage",
    description="Schema-test status, subscription setup, and safe read-only scope.",
    requires_env=_REQUIRED_ENV,
)
async def iponz_new_zealand_usage() -> str:
    return USAGE


@conditional_tool(iponz_new_zealand_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_iponz_patent(
    patent_number: str | list[str], full: bool = False
) -> ListEnvelope[dict]:
    """Fetch public New Zealand patent records by official patent number.

    Related tools: list_iponz_patents_updated.
    """
    return await _fetch(patent_number, "get_patent", _lean_patent, "patent", full)


@conditional_tool(iponz_new_zealand_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def list_iponz_patents_updated(
    start: date, end: date, limit: int = 100, full: bool = False
) -> ListEnvelope[dict]:
    """List patents updated in an IPONZ date range shorter than one year.

    Related tools: get_iponz_patent.
    """
    _validate_limit(limit)
    rows = await api.list_iponz_patents_updated(start, end)
    return _list_envelope("patents updated", start, end, rows, limit, full)


@conditional_tool(iponz_new_zealand_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_iponz_trademark(
    trademark_number: str | list[str], full: bool = False
) -> ListEnvelope[dict]:
    """Fetch public New Zealand trade mark records by official number.

    Related tools: list_iponz_trademarks_updated.
    """
    return await _fetch(trademark_number, "get_trademark", _lean_trademark, "trade mark", full)


@conditional_tool(iponz_new_zealand_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def list_iponz_trademarks_updated(
    start: date, end: date, limit: int = 100, full: bool = False
) -> ListEnvelope[dict]:
    """List trade marks updated in an IPONZ date range shorter than one year.

    Related tools: get_iponz_trademark.
    """
    _validate_limit(limit)
    rows = await api.list_iponz_trademarks_updated(start, end)
    return _list_envelope("trade marks updated", start, end, rows, limit, full)


@conditional_tool(iponz_new_zealand_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_iponz_design(
    design_number: str | list[str], full: bool = False
) -> ListEnvelope[dict]:
    """Fetch public New Zealand design records by official number.

    Related tools: list_iponz_designs_updated, list_iponz_designs_registered.
    """
    return await _fetch(design_number, "get_design", _lean_design, "design", full)


@conditional_tool(iponz_new_zealand_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def list_iponz_designs_updated(
    start: date, end: date, limit: int = 100, full: bool = False
) -> ListEnvelope[dict]:
    """List designs updated in an IPONZ date range shorter than one year.

    Related tools: get_iponz_design, list_iponz_designs_registered.
    """
    _validate_limit(limit)
    rows = await api.list_iponz_designs_updated(start, end)
    return _list_envelope("designs updated", start, end, rows, limit, full)


@conditional_tool(iponz_new_zealand_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def list_iponz_designs_registered(
    start: date, end: date, limit: int = 100, full: bool = False
) -> ListEnvelope[dict]:
    """List designs registered in an IPONZ date range shorter than one year.

    Related tools: get_iponz_design, list_iponz_designs_updated.
    """
    _validate_limit(limit)
    rows = await api.list_iponz_designs_registered(start, end)
    return _list_envelope("designs registered", start, end, rows, limit, full)


__all__ = ["PORTAL_URL", "iponz_new_zealand_mcp"]
