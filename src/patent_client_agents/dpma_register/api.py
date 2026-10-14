"""High-level async helpers for DPMAconnectPlus."""

from __future__ import annotations

from patent_client_agents.shared.api import one_shot

from .client import DpmaRegisterClient
from .models import DesignRecord, PatentUtilityRecord, TrademarkRecord


def _new_client() -> DpmaRegisterClient:
    return DpmaRegisterClient()


@one_shot(_new_client, DpmaRegisterClient.search_patents)
async def search_dpma_patents(
    expert_query: str, *, limit: int = 25
) -> tuple[list[PatentUtilityRecord], int | None]: ...


@one_shot(_new_client, DpmaRegisterClient.get_patent)
async def get_dpma_patent(number: str) -> PatentUtilityRecord: ...


@one_shot(_new_client, DpmaRegisterClient.search_trademarks)
async def search_dpma_trademarks(
    expert_query: str, *, limit: int = 25
) -> tuple[list[TrademarkRecord], int | None]: ...


@one_shot(_new_client, DpmaRegisterClient.get_trademark)
async def get_dpma_trademark(number: str) -> TrademarkRecord: ...


@one_shot(_new_client, DpmaRegisterClient.search_designs)
async def search_dpma_designs(
    expert_query: str, *, limit: int = 25
) -> tuple[list[DesignRecord], int | None]: ...


@one_shot(_new_client, DpmaRegisterClient.get_design)
async def get_dpma_design(number: str) -> DesignRecord: ...
