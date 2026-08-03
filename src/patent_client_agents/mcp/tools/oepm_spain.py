"""WSDL-tested MCP tools for Spain's OEPM CEO register service."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from mcp_data_core.mcp.conditional import conditional_resource, conditional_tool
from patent_client_agents.oepm_spain.client import BASE_URL, LIST_ACCEPT_CAP, OepmSpainClient
from patent_client_agents.oepm_spain.models import (
    OepmDesignRecord,
    OepmPatentRecord,
    OepmTrademarkRecord,
)
from patent_client_agents.oepm_spain.resources import USAGE

oepm_spain_mcp = FastMCP("Spain OEPM CEO register")
_REQUIRED_ENV = ["OEPM_CEO_USERNAME", "OEPM_CEO_PASSWORD"]
_SOURCE_NAME = (
    "Oficina Espanola de Patentes y Marcas (OEPM), CEO web service. "
    "Tested against the public WSDL with synthetic fixtures; live account compatibility unverified."
)
_FANOUT_CONCURRENCY = 5


def _provenance() -> Any:
    return make_provenance(source_url=BASE_URL, source_name=_SOURCE_NAME)


def _dump(record: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", record.model_dump(mode="json"))


def _date(value: Any) -> str | None:
    return value.isoformat() if value else None


def _lean_patent(record: OepmPatentRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "modality": record.modality,
        "application_number": record.application_number,
        "publication_number": record.publication_number,
        "title": record.title,
        "status": record.status,
        "owner": record.owner,
        "applicant": record.applicant,
        "filing_date": _date(record.filing_date),
        "priority_date": _date(record.priority_date),
        "publication_date": _date(record.publication_date),
        "grant_date": _date(record.grant_date),
        "inventors": record.inventors,
        "proceedings": [item.model_dump(mode="json") for item in record.proceedings],
    }


def _lean_trademark(record: OepmTrademarkRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "modality": record.modality,
        "application_number": record.application_number,
        "denomination": record.denomination,
        "mark_type": record.mark_type,
        "status": record.status,
        "owner": record.owner,
        "applicant": record.applicant,
        "filing_date": _date(record.filing_date),
        "publication_date": _date(record.publication_date),
        "next_renewal_date": _date(record.next_renewal_date),
        "nice_classes": record.nice_classes,
        "vienna_classes": record.vienna_classes,
        "image_url": record.image_url,
    }


def _lean_design(record: OepmDesignRecord) -> dict[str, Any]:
    return {
        "identifier": record.identifier,
        "modality": record.modality,
        "application_number": record.application_number,
        "status": record.status,
        "status_code": record.status_code,
        "owner": record.owner,
        "applicant": record.applicant,
        "filing_date": _date(record.filing_date),
        "publication_date": _date(record.publication_date),
        "resolution_date": _date(record.resolution_date),
        "filing_place": record.filing_place,
        "creators": record.creators,
    }


def _identifiers(value: str | list[str]) -> list[str]:
    values = [value] if isinstance(value, str) else list(value)
    if not values or any(not identifier.strip() for identifier in values):
        raise ValidationError("At least one non-empty OEPM file number is required")
    if len(values) > LIST_ACCEPT_CAP:
        raise ValidationError(f"A maximum of {LIST_ACCEPT_CAP} OEPM file numbers is allowed")
    return values


async def _fetch(
    values: str | list[str],
    method_name: str,
    lean: Callable[[Any], dict[str, Any]],
    label: str,
    full: bool,
) -> ListEnvelope[dict]:
    identifiers = _identifiers(values)
    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)
    async with OepmSpainClient() as client:
        method: Callable[[str], Awaitable[Any]] = getattr(client, method_name)

        async def one(identifier: str) -> Any:
            async with semaphore:
                return await method(identifier)

        records = await asyncio.gather(*(one(identifier) for identifier in identifiers))
    items = [_dump(record) for record in records] if full else [lean(record) for record in records]
    return ListEnvelope(
        summary=f"OEPM {label} fetch: {len(items)} records. Public-WSDL tested only.",
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(),
    )


@conditional_resource(
    oepm_spain_mcp,
    "pca://oepm-spain/usage",
    mime_type="text/markdown",
    name="Spain OEPM connector status and usage",
    description="WSDL-test status, account setup, supported lookups, and validation request.",
    requires_env=_REQUIRED_ENV,
)
async def oepm_spain_usage() -> str:
    return USAGE


@conditional_tool(oepm_spain_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_oepm_patent(file_number: str | list[str], full: bool = False) -> ListEnvelope[dict]:
    """Fetch Spanish patent, utility-model, or related invention files by exact number.

    Related tools: get_oepm_trademark, get_oepm_design.
    """
    return await _fetch(file_number, "get_patent", _lean_patent, "invention", full)


@conditional_tool(oepm_spain_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_oepm_trademark(
    file_number: str | list[str], full: bool = False
) -> ListEnvelope[dict]:
    """Fetch Spanish trademark or trade-name files by exact number.

    Related tools: get_oepm_patent, get_oepm_design.
    """
    return await _fetch(file_number, "get_trademark", _lean_trademark, "trademark", full)


@conditional_tool(oepm_spain_mcp, requires_env=_REQUIRED_ENV, annotations=READ_ONLY)
async def get_oepm_design(file_number: str | list[str], full: bool = False) -> ListEnvelope[dict]:
    """Fetch Spanish industrial-design files by exact number.

    Related tools: get_oepm_patent, get_oepm_trademark.
    """
    return await _fetch(file_number, "get_design", _lean_design, "design", full)


__all__ = ["oepm_spain_mcp"]
