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

from patent_client_agents.shared.api import one_shot

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


def _new_client() -> TipoClient:
    return TipoClient()


# ---------------------------------------------------------------------------
# Patent helpers
# ---------------------------------------------------------------------------


@one_shot(_new_client, TipoClient.search_patent_appl)
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


@one_shot(_new_client, TipoClient.search_patent_appl)
async def get_tipo_patent(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentApplRow]:
    """Fetch ``/PatentAppl`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_patent_pub)
async def get_tipo_patent_publication(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentPubRow]:
    """Fetch ``/PatentPub`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_patent_rights)
async def get_tipo_patent_rights(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentRightsRow]:
    """Fetch ``/PatentRights`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_patent_priority)
async def get_tipo_patent_priority(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentPriorityRow]:
    """Fetch ``/PatentPriority`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_patent_annuity)
async def get_tipo_patent_annuity(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentAnnuityRow]:
    """Fetch ``/PatentAnnuity`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_patent_twins)
async def get_tipo_patent_twins(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentTwinsRow]:
    """Fetch ``/PatentTwins`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_patent_alteration)
async def get_tipo_patent_alteration(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentAlterationRow]:
    """Fetch ``/PatentAlteration`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_patent_change)
async def get_tipo_patent_change(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentChangeRow]:
    """Fetch ``/PatentChange`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_patent_divide)
async def get_tipo_patent_divide(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[PatentDivideRow]:
    """Fetch ``/PatentDivide`` rows by application number(s)."""


# ---------------------------------------------------------------------------
# Trademark helpers
# ---------------------------------------------------------------------------


@one_shot(_new_client, TipoClient.search_tmark_appl)
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


@one_shot(_new_client, TipoClient.search_tmark_appl)
async def get_tipo_trademark(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkApplRow]:
    """Fetch ``/TmarkAppl`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_tmark_rights)
async def get_tipo_trademark_rights(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkRightsRow]:
    """Fetch ``/TmarkRights`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_tmark_priority)
async def get_tipo_trademark_priority(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkPriorityRow]:
    """Fetch ``/TmarkPriority`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_tmark_pics)
async def get_tipo_trademark_image_urls(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkPicsRow]:
    """Fetch ``/TmarkPics`` rows (image URLs only)."""


@one_shot(_new_client, TipoClient.get_tmark_change)
async def get_tipo_trademark_change(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkChangeRow]:
    """Fetch ``/TmarkChange`` rows by application number(s)."""


@one_shot(_new_client, TipoClient.get_tmark_divide)
async def get_tipo_trademark_divide(
    appl_no: str | list[str],
    *,
    top: int = 100,
    skip: int = 0,
) -> list[TmarkDivideRow]:
    """Fetch ``/TmarkDivide`` rows by application number(s)."""


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
