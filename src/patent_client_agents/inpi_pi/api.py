"""High-level async API for INPI France ``api-gateway.inpi.fr`` (TM + Design).

Wraps :class:`InpiPiClient` with four one-shot helpers that handle
client construction + teardown. The preferred pattern is still
``async with InpiPiClient(...) as client: ...`` for workflows that
issue more than one call — the helpers are convenience wrappers for
single-call sites.

Patents — deliberately absent
-----------------------------
**No patent helpers are defined.** For FR patent coverage, use
``patent_client_agents.epo_ops`` (country code ``FR``); INPADOC covers
EP-routed FR designations and FR national-route filings with adequate
fidelity. See the package ``__init__`` and ``client`` module
docstrings for the full substitution rationale.

Usage::

    hits, total = await search_inpi_trademarks(query="Apple", nice_class=["9"])
    rows = await get_inpi_trademark("4216963")
    hits, total = await search_inpi_designs(query="chair", locarno_class=["0601"])
    rows = await get_inpi_design("FR20140182")

All helpers require ``INPI_USERNAME`` and ``INPI_PASSWORD`` env vars
(or explicit ``username`` / ``password`` arguments).
"""

from __future__ import annotations

from .client import InpiPiClient
from .models import InpiDesignRow, InpiTrademarkRow

__all__ = [
    "InpiPiClient",
    "InpiTrademarkRow",
    "InpiDesignRow",
    "search_inpi_trademarks",
    "get_inpi_trademark",
    "search_inpi_designs",
    "get_inpi_design",
]


# =============================================================================
# Trademark (marques) — ST.66 v1.0
# =============================================================================


async def search_inpi_trademarks(
    query: str | None = None,
    *,
    nice_class: list[str] | None = None,
    applicant: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = 25,
    username: str | None = None,
    password: str | None = None,
) -> tuple[list[InpiTrademarkRow], int | None]:
    """Search FR national trademarks (ST.66 v1.0)."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.search_trademarks(
            query,
            nice_class=nice_class,
            applicant=applicant,
            status=status,
            date_from=date_from,
            date_to=date_to,
            offset=offset,
            limit=limit,
        )


async def get_inpi_trademark(
    application_number: str | list[str],
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[InpiTrademarkRow]:
    """Fetch one or more FR national trademark records by application number."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_trademark(application_number)


# =============================================================================
# Design (dessins) — ST.86 v1.0
# =============================================================================


async def search_inpi_designs(
    query: str | None = None,
    *,
    locarno_class: list[str] | None = None,
    applicant: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = 25,
    username: str | None = None,
    password: str | None = None,
) -> tuple[list[InpiDesignRow], int | None]:
    """Search FR national designs (ST.86 v1.0)."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.search_designs(
            query,
            locarno_class=locarno_class,
            applicant=applicant,
            status=status,
            date_from=date_from,
            date_to=date_to,
            offset=offset,
            limit=limit,
        )


async def get_inpi_design(
    application_number: str | list[str],
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[InpiDesignRow]:
    """Fetch one or more FR national design records by application number."""
    async with InpiPiClient(username=username, password=password) as client:
        return await client.get_design(application_number)
