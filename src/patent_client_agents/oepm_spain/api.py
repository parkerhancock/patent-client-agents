"""High-level async helpers for Spain's OEPM CEO service."""

from __future__ import annotations

from patent_client_agents.shared.api import one_shot

from .client import OepmSpainClient
from .models import OepmDesignRecord, OepmPatentRecord, OepmTrademarkRecord


def _new_client() -> OepmSpainClient:
    return OepmSpainClient()


@one_shot(_new_client, OepmSpainClient.get_patent)
async def get_oepm_patent(identifier: str) -> OepmPatentRecord: ...


@one_shot(_new_client, OepmSpainClient.get_trademark)
async def get_oepm_trademark(identifier: str) -> OepmTrademarkRecord: ...


@one_shot(_new_client, OepmSpainClient.get_design)
async def get_oepm_design(identifier: str) -> OepmDesignRecord: ...
