"""High-level async helpers for the New Zealand IPONZ API."""

from __future__ import annotations

from datetime import date

from patent_client_agents.shared.api import one_shot

from .client import IponzClient
from .models import (
    IponzDesignRecord,
    IponzPatentRecord,
    IponzRegisterSummary,
    IponzTrademarkRecord,
)


def _new_client() -> IponzClient:
    return IponzClient()


@one_shot(_new_client, IponzClient.get_patent)
async def get_iponz_patent(number: str) -> IponzPatentRecord: ...


@one_shot(_new_client, IponzClient.list_patents_updated)
async def list_iponz_patents_updated(start: date, end: date) -> list[IponzRegisterSummary]: ...


@one_shot(_new_client, IponzClient.get_trademark)
async def get_iponz_trademark(number: str) -> IponzTrademarkRecord: ...


@one_shot(_new_client, IponzClient.list_trademarks_updated)
async def list_iponz_trademarks_updated(start: date, end: date) -> list[IponzRegisterSummary]: ...


@one_shot(_new_client, IponzClient.get_design)
async def get_iponz_design(number: str) -> IponzDesignRecord: ...


@one_shot(_new_client, IponzClient.list_designs_updated)
async def list_iponz_designs_updated(start: date, end: date) -> list[IponzRegisterSummary]: ...


@one_shot(_new_client, IponzClient.list_designs_registered)
async def list_iponz_designs_registered(start: date, end: date) -> list[IponzRegisterSummary]: ...
