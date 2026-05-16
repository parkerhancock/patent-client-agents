"""Module-level helpers for the TIPO OpenData connector.

Each helper opens a context-managed :class:`TipoClient`, calls the
matching client method, and returns the result. The 14 surfaces map
1:1 with the MCP tool table in
``research/specs/tw-tipo-connector-spec.md`` §3 (the spec exposes
``get_tipo_patent_events`` / ``get_tipo_trademark_events`` as
combined tools; we keep individual ``alteration`` / ``change`` /
``divide`` helpers here for library callers, plus a combining helper
each per the MCP surface).

All helpers require ``TIPO_API_KEY`` (or an explicit ``tk=`` to
:class:`TipoClient`). See :class:`TipoClient` for the auth contract.
"""

from __future__ import annotations

from typing import Any

from .client import TipoClient
from .models import (
    PatentAlterationRow,
    PatentAnnuityRow,
    PatentApplRow,
    PatentChangeRow,
    PatentDivideRow,
    PatentPriorityRow,
    PatentPubRow,
    PatentRightsRow,
    PatentTwinsRow,
    TmarkApplRow,
    TmarkChangeRow,
    TmarkDivideRow,
    TmarkPicsRow,
    TmarkPriorityRow,
    TmarkRightsRow,
)


# ---------------------------------------------------------------------------
# Patent helpers
# ---------------------------------------------------------------------------


async def search_tipo_patents(
    *,
    q: str | None = None,
    applclass: int | str | None = None,
    appl_date_from: str | None = None,
    appl_date_to: str | None = None,
    applicant: str | None = None,
    top: int = 100,
    skip: int = 0,
    **extra: Any,
) -> list[PatentApplRow]:
    """Search ``/PatentAppl`` — TW patent / UM / design applications."""
    async with TipoClient() as client:
        return await client.search_patent_appl(
            q=q,
            applclass=applclass,
            appl_date_from=appl_date_from,
            appl_date_to=appl_date_to,
            applicant=applicant,
            top=top,
            skip=skip,
            **extra,
        )


async def get_tipo_patent(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentApplRow]:
    """Fetch ``/PatentAppl`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.search_patent_appl(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_patent_publication(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentPubRow]:
    """Fetch ``/PatentPub`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_patent_pub(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_patent_rights(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentRightsRow]:
    """Fetch ``/PatentRights`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_patent_rights(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_patent_priority(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentPriorityRow]:
    """Fetch ``/PatentPriority`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_patent_priority(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_patent_annuity(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentAnnuityRow]:
    """Fetch ``/PatentAnnuity`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_patent_annuity(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_patent_twins(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentTwinsRow]:
    """Fetch ``/PatentTwins`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_patent_twins(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_patent_alteration(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentAlterationRow]:
    """Fetch ``/PatentAlteration`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_patent_alteration(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_patent_change(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentChangeRow]:
    """Fetch ``/PatentChange`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_patent_change(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_patent_divide(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentDivideRow]:
    """Fetch ``/PatentDivide`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_patent_divide(appl_no=appl_no, top=top, skip=skip)


# ---------------------------------------------------------------------------
# Trademark helpers
# ---------------------------------------------------------------------------


async def search_tipo_trademarks(
    *,
    q: str | None = None,
    tmark_class: str | int | None = None,
    appl_date_from: str | None = None,
    appl_date_to: str | None = None,
    applicant: str | None = None,
    top: int = 100,
    skip: int = 0,
    **extra: Any,
) -> list[TmarkApplRow]:
    """Search ``/TmarkAppl`` — TW trademark applications."""
    async with TipoClient() as client:
        return await client.search_tmark_appl(
            q=q,
            tmark_class=tmark_class,
            appl_date_from=appl_date_from,
            appl_date_to=appl_date_to,
            applicant=applicant,
            top=top,
            skip=skip,
            **extra,
        )


async def get_tipo_trademark(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkApplRow]:
    """Fetch ``/TmarkAppl`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.search_tmark_appl(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_trademark_rights(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkRightsRow]:
    """Fetch ``/TmarkRights`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_tmark_rights(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_trademark_priority(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkPriorityRow]:
    """Fetch ``/TmarkPriority`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_tmark_priority(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_trademark_image_urls(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkPicsRow]:
    """Fetch ``/TmarkPics`` rows (image URLs only)."""
    async with TipoClient() as client:
        return await client.get_tmark_pics(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_trademark_change(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkChangeRow]:
    """Fetch ``/TmarkChange`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_tmark_change(appl_no=appl_no, top=top, skip=skip)


async def get_tipo_trademark_divide(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkDivideRow]:
    """Fetch ``/TmarkDivide`` rows by application number(s)."""
    async with TipoClient() as client:
        return await client.get_tmark_divide(appl_no=appl_no, top=top, skip=skip)


__all__ = [
    "TipoClient",
    # patents
    "search_tipo_patents",
    "get_tipo_patent",
    "get_tipo_patent_publication",
    "get_tipo_patent_rights",
    "get_tipo_patent_priority",
    "get_tipo_patent_annuity",
    "get_tipo_patent_twins",
    "get_tipo_patent_alteration",
    "get_tipo_patent_change",
    "get_tipo_patent_divide",
    # trademarks
    "search_tipo_trademarks",
    "get_tipo_trademark",
    "get_tipo_trademark_rights",
    "get_tipo_trademark_priority",
    "get_tipo_trademark_image_urls",
    "get_tipo_trademark_change",
    "get_tipo_trademark_divide",
]
