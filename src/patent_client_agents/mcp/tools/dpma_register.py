"""Mock-only tested MCP tools for Germany's DPMAconnectPlus registers."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from mcp_data_core.mcp.conditional import conditional_resource, conditional_tool
from patent_client_agents.dpma_register import api
from patent_client_agents.dpma_register.client import (
    ACCOUNT_RESULT_CAP,
    BASE_URL,
    DESIGN_SERVICE,
    PATENT_SERVICE,
    TRADEMARK_SERVICE,
    DpmaRegisterClient,
)
from patent_client_agents.dpma_register.models import (
    DesignRecord,
    PatentUtilityRecord,
    TrademarkRecord,
)
from patent_client_agents.dpma_register.resources import USAGE
from patent_client_agents.shared.envelope import dump
from patent_client_agents.shared.fanout import FetchedList, as_id_list, fetch_many, fetched_summary
from patent_client_agents.shared.provenance import provenance_for

dpma_register_mcp = FastMCP("DPMA Germany, DPMAconnectPlus")
_REQUIRED_ENV = ["DPMA_CONNECTPLUS_USERNAME", "DPMA_CONNECTPLUS_PASSWORD"]
_SOURCE_NAME = (
    "German Patent and Trade Mark Office (DPMA), via DPMAconnectPlus. "
    "Mock-only tested; live compatibility unverified."
)


def _provenance(service: str, operation: str, value: str) -> Any:
    return provenance_for(
        source_url=f"{BASE_URL}/{service}/{operation}/{quote(value, safe='')}",
        source_name=_SOURCE_NAME,
    )


def _lean_patent(record: PatentUtilityRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "right_type": record.right_type,
        "application_number": record.application_number,
        "publication_number": record.publication_number,
        "registration_number": record.registration_number,
        "title": record.title,
        "status": record.status,
        "application_date": record.application_date.isoformat()
        if record.application_date
        else None,
        "publication_date": record.publication_date.isoformat()
        if record.publication_date
        else None,
        "owner": record.owner,
        "classification": record.classification,
    }


def _lean_trademark(record: TrademarkRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "application_number": record.application_number,
        "registration_number": record.registration_number,
        "mark_text": record.mark_text,
        "status": record.status,
        "application_date": record.application_date.isoformat()
        if record.application_date
        else None,
        "registration_date": record.registration_date.isoformat()
        if record.registration_date
        else None,
        "owner": record.owner,
        "nice_classification": record.nice_classification,
        "vienna_classification": record.vienna_classification,
    }


def _lean_design(record: DesignRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "design_number": record.design_number,
        "application_number": record.application_number,
        "registration_number": record.registration_number,
        "product_indication": record.product_indication,
        "status": record.status,
        "application_date": record.application_date.isoformat()
        if record.application_date
        else None,
        "registration_date": record.registration_date.isoformat()
        if record.registration_date
        else None,
        "owner": record.owner,
        "locarno_classification": record.locarno_classification,
    }


def _summary(label: str, query: str, shown: int, total: int | None) -> str:
    count = f"{shown} of {total}" if total is not None else str(shown)
    cap = (
        " Upstream account cap reached; DPMA provides no pagination."
        if total == ACCOUNT_RESULT_CAP
        else ""
    )
    return f"DPMA {label} search for `{query}`: {count} hits.{cap} Mock-only tested."


@conditional_resource(
    dpma_register_mcp,
    "pca://dpma-register/usage",
    mime_type="text/markdown",
    name="DPMAconnectPlus connector status and usage",
    description="Mock-only test status, deployment limits, and community validation request.",
    requires_env=_REQUIRED_ENV,
)
async def dpma_register_usage() -> str:
    return USAGE


@conditional_tool(dpma_register_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_dpma_patents(
    expert_query: Annotated[str, "DPMAregister expert-query syntax."],
    right_type: Literal["patent", "utility_model", "both"] = "both",
    limit: Annotated[int, "Maximum records to return, from 1 through 1000."] = 25,
    full: Annotated[bool, "Include normalized raw XML fields."] = False,
) -> ListEnvelope[dict]:
    """Search German patents and utility models. Mock-only tested.

    Use `get_dpma_patent` for details. Community testing with a real account is welcome.
    """
    if not 1 <= limit <= ACCOUNT_RESULT_CAP:
        raise ValidationError("limit must be between 1 and 1000")
    rows, total = await api.search_dpma_patents(expert_query, limit=limit)
    rows = [row for row in rows if right_type == "both" or row.right_type == right_type]
    items = (
        [dump(row, mode="json") for row in rows] if full else [_lean_patent(row) for row in rows]
    )
    return ListEnvelope(
        summary=_summary("patent and utility-model", expert_query, len(items), total),
        items=items,
        more_available=bool(total is not None and total > len(items)),
        next_cursor=None,
        provenance=_provenance(PATENT_SERVICE, "search", expert_query),
    )


@conditional_tool(dpma_register_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_dpma_patent(
    application_number: str | list[str], full: bool = False
) -> FetchedList[dict]:
    """Fetch German patent or utility-model records. Mock-only tested."""
    numbers = as_id_list(application_number, noun="application number")
    async with DpmaRegisterClient() as client:

        async def fetch(number: str) -> PatentUtilityRecord:
            return await client.get_patent(number)

        rows, not_found = await fetch_many(
            numbers, fetch, single=isinstance(application_number, str)
        )
    items = (
        [dump(row, mode="json") for row in rows] if full else [_lean_patent(row) for row in rows]
    )
    if len(numbers) == 1:
        summary = f"DPMA patent and utility-model fetch: {len(items)} records. Mock-only tested."
    else:
        summary = fetched_summary(
            len(items), len(numbers), "DPMA patent and utility-model records", not_found
        )
    return FetchedList[dict](
        summary=summary,
        items=items,
        not_found=not_found,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(PATENT_SERVICE, "getRegisterInfo", numbers[0]),
    )


@conditional_tool(dpma_register_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_dpma_trademarks(
    expert_query: str, limit: int = 25, full: bool = False
) -> ListEnvelope[dict]:
    """Search German national trademarks. Mock-only tested."""
    if not 1 <= limit <= ACCOUNT_RESULT_CAP:
        raise ValidationError("limit must be between 1 and 1000")
    rows, total = await api.search_dpma_trademarks(expert_query, limit=limit)
    items = (
        [dump(row, mode="json") for row in rows] if full else [_lean_trademark(row) for row in rows]
    )
    return ListEnvelope(
        summary=_summary("trademark", expert_query, len(items), total),
        items=items,
        more_available=bool(total is not None and total > len(items)),
        next_cursor=None,
        provenance=_provenance(TRADEMARK_SERVICE, "search", expert_query),
    )


@conditional_tool(dpma_register_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_dpma_trademark(
    application_number: str | list[str], full: bool = False
) -> FetchedList[dict]:
    """Fetch German national trademark records. Mock-only tested."""
    numbers = as_id_list(application_number, noun="application number")
    async with DpmaRegisterClient() as client:

        async def fetch(number: str) -> TrademarkRecord:
            return await client.get_trademark(number)

        rows, not_found = await fetch_many(
            numbers, fetch, single=isinstance(application_number, str)
        )
    items = (
        [dump(row, mode="json") for row in rows] if full else [_lean_trademark(row) for row in rows]
    )
    if len(numbers) == 1:
        summary = f"DPMA trademark fetch: {len(items)} records. Mock-only tested."
    else:
        summary = fetched_summary(len(items), len(numbers), "DPMA trademarks", not_found)
    return FetchedList[dict](
        summary=summary,
        items=items,
        not_found=not_found,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(TRADEMARK_SERVICE, "getRegisterInfo", numbers[0]),
    )


@conditional_tool(dpma_register_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def search_dpma_designs(
    expert_query: str, limit: int = 25, full: bool = False
) -> ListEnvelope[dict]:
    """Search German national designs. Mock-only tested."""
    if not 1 <= limit <= ACCOUNT_RESULT_CAP:
        raise ValidationError("limit must be between 1 and 1000")
    rows, total = await api.search_dpma_designs(expert_query, limit=limit)
    items = (
        [dump(row, mode="json") for row in rows] if full else [_lean_design(row) for row in rows]
    )
    return ListEnvelope(
        summary=_summary("design", expert_query, len(items), total),
        items=items,
        more_available=bool(total is not None and total > len(items)),
        next_cursor=None,
        provenance=_provenance(DESIGN_SERVICE, "search", expert_query),
    )


@conditional_tool(dpma_register_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_dpma_design(design_number: str | list[str], full: bool = False) -> FetchedList[dict]:
    """Fetch German national design records. Mock-only tested."""
    numbers = as_id_list(design_number, noun="design number")
    async with DpmaRegisterClient() as client:

        async def fetch(number: str) -> DesignRecord:
            return await client.get_design(number)

        rows, not_found = await fetch_many(numbers, fetch, single=isinstance(design_number, str))
    items = (
        [dump(row, mode="json") for row in rows] if full else [_lean_design(row) for row in rows]
    )
    if len(numbers) == 1:
        summary = f"DPMA design fetch: {len(items)} records. Mock-only tested."
    else:
        summary = fetched_summary(len(items), len(numbers), "DPMA designs", not_found)
    return FetchedList[dict](
        summary=summary,
        items=items,
        not_found=not_found,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(DESIGN_SERVICE, "getRegisterInfo", numbers[0]),
    )


__all__ = ["dpma_register_mcp"]
