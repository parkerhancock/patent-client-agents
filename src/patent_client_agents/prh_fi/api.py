"""Module-level helpers for the PRH (Finland) connector."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .client import PrhClient
from .models import (
    DossierSearchResponse,
    PatentGetRecord,
    PatentSearchResponse,
)


async def search_prh_patents(**filters: Any) -> PatentSearchResponse:
    async with PrhClient() as client:
        return await client.search_patents(**filters)


async def get_prh_patent(application_number: str) -> PatentGetRecord:
    async with PrhClient() as client:
        return await client.get_patent(application_number)


async def get_prh_patents(
    application_numbers: Iterable[str],
) -> list[PatentGetRecord]:
    async with PrhClient() as client:
        return await client.get_patents(application_numbers)


async def search_prh_trademarks(**filters: Any) -> DossierSearchResponse:
    async with PrhClient() as client:
        return await client.search_trademarks(**filters)


async def search_prh_well_known_trademarks(**filters: Any) -> DossierSearchResponse:
    async with PrhClient() as client:
        return await client.search_well_known_trademarks(**filters)


async def search_prh_designs(**filters: Any) -> DossierSearchResponse:
    async with PrhClient() as client:
        return await client.search_designs(**filters)


__all__ = [
    "search_prh_patents",
    "get_prh_patent",
    "get_prh_patents",
    "search_prh_trademarks",
    "search_prh_well_known_trademarks",
    "search_prh_designs",
]
