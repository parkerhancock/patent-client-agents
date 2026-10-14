"""High-level async helpers for the Swiss IPI datadelivery API."""

from __future__ import annotations

from patent_client_agents.shared.api import one_shot

from .client import IpiSwissregClient
from .models import (
    IpiPatentRecord,
    IpiPublicationRecord,
    IpiSearchMeta,
    IpiSpcRecord,
    IpiTrademarkRecord,
)


def _new_client() -> IpiSwissregClient:
    return IpiSwissregClient()


@one_shot(_new_client, IpiSwissregClient.search_patents)
async def search_ipi_patents(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiPatentRecord], IpiSearchMeta]: ...


@one_shot(_new_client, IpiSwissregClient.get_patent)
async def get_ipi_patent(number: str) -> IpiPatentRecord: ...


@one_shot(_new_client, IpiSwissregClient.search_patent_publications)
async def search_ipi_patent_publications(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiPublicationRecord], IpiSearchMeta]: ...


@one_shot(_new_client, IpiSwissregClient.search_trademarks)
async def search_ipi_trademarks(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiTrademarkRecord], IpiSearchMeta]: ...


@one_shot(_new_client, IpiSwissregClient.get_trademark)
async def get_ipi_trademark(number: str) -> IpiTrademarkRecord: ...


@one_shot(_new_client, IpiSwissregClient.search_spcs)
async def search_ipi_spcs(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiSpcRecord], IpiSearchMeta]: ...


@one_shot(_new_client, IpiSwissregClient.get_spc)
async def get_ipi_spc(number: str) -> IpiSpcRecord: ...


@one_shot(_new_client, IpiSwissregClient.search_spc_publications)
async def search_ipi_spc_publications(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiPublicationRecord], IpiSearchMeta]: ...
