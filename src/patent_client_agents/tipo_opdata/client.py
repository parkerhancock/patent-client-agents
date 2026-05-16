"""Async client for the TIPO Taiwan OpenData REST API.

Wraps the 15 GET operations published at
``https://cloud.tipo.gov.tw/S220/opdataapi/api/`` per the Swagger 2.0
spec at ``https://cloud.tipo.gov.tw/S220/opdata/api/file/oas``.

Auth model (spec §2): a single ``tk`` UUID token issued by TIPO upon
emailing a Word-form application to ``ipoid@tipo.gov.tw``. The token
travels as a query parameter on every call; there is no OAuth. Set
``TIPO_API_KEY`` in the process environment (or pass ``tk=`` to
:class:`TipoClient`) — both empty raises :class:`ConfigurationError`.

Response shape (all 15 endpoints): a versioned outer envelope
::

    {
        "version": "...",
        "status": "...",
        "top": <int>,
        "skip": <int>,
        "total-count": <int>,
        "<endpoint-array-key>": {"<item-key>": [<row>, ...]}
    }

``<endpoint-array-key>`` and ``<item-key>`` vary per endpoint
(e.g. ``"tw-patent-applI"`` -> ``"patentcontent"``,
``"tmarkappl"`` -> ``"tmarkcontent"``). We resolve the row array
defensively: if there's exactly one nested object holding a list, use
that; otherwise look for known keys (``"patentcontent"``,
``"tmarkcontent"``, ``"twins-announced"``, etc.). Rows are then
validated against the matching ``*Row`` model in :mod:`.models`.

Pagination (spec §3): the API caps ``top`` at 6,000 rows
empirically. :meth:`TipoClient.paginate` auto-walks ``skip`` in
6,000-row pages and yields rows until a short page closes the
sequence. Callers needing strict counts can pass ``top`` explicitly
on the per-endpoint methods.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from law_tools_core import BaseAsyncClient
from law_tools_core.exceptions import ConfigurationError

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

BASE_URL: str = "https://cloud.tipo.gov.tw/S220/opdataapi/api"
"""Production base URL for the TIPO OpenData REST API."""

MAX_TOP: int = 6000
"""Empirical hard cap on ``top`` per request (spec §3 synopsis)."""

_REGISTRATION_HINT: str = (
    "Request a TIPO OpenData ``tk`` UUID token by emailing the Word-form "
    "application to ipoid@tipo.gov.tw (spec §2, §7)."
)

T = TypeVar("T")


def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the row list out of a TIPO envelope.

    TIPO wraps each row array under two nested keys whose names vary
    per endpoint (e.g. ``"tw-patent-applI" -> "patentcontent"``). We
    walk the envelope generically: skip the well-known scalar keys
    (``version``, ``status``, ``top``, ``skip``, ``total-count``),
    then descend into the remaining object to find the inner list.

    Returns an empty list when no list is present — TIPO returns the
    envelope without the data key on zero-row queries.
    """
    _SCALARS = {"version", "status", "top", "skip", "total-count"}
    candidates = [v for k, v in payload.items() if k not in _SCALARS]
    for cand in candidates:
        if isinstance(cand, list):
            return [row for row in cand if isinstance(row, dict)]
        if isinstance(cand, dict):
            # Descend one level: the inner object holds {"<item-key>": [rows]}
            for inner_val in cand.values():
                if isinstance(inner_val, list):
                    return [row for row in inner_val if isinstance(row, dict)]
                if isinstance(inner_val, dict):
                    # Two-level nesting (e.g. twins-announced / twins / patentcontent)
                    for deeper in inner_val.values():
                        if isinstance(deeper, list):
                            return [row for row in deeper if isinstance(row, dict)]
    return []


class TipoClient(BaseAsyncClient):
    """Async client for the TIPO Taiwan OpenData REST API.

    All methods are read-only ``GET``\\ s against
    ``https://cloud.tipo.gov.tw/S220/opdataapi/api/...``. The ``tk``
    query parameter is appended automatically on every request from
    the value passed to ``__init__`` or resolved from
    ``TIPO_API_KEY``.

    Example::

        async with TipoClient() as client:
            envelope = await client.search_patent_appl(top=100)
            async for row in client.paginate("/PatentAppl"):
                ...
    """

    CACHE_NAME: str = "tipo_opdata"
    DEFAULT_TIMEOUT: float = 30.0

    def __init__(
        self,
        tk: str | None = None,
        *,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the TIPO client.

        Args:
            tk: TIPO-issued UUID token. Falls back to the
                ``TIPO_API_KEY`` env var.
            base_url: Override the default API base URL (testing only).
            **kwargs: Forwarded to :class:`BaseAsyncClient`.

        Raises:
            ConfigurationError: When neither ``tk`` nor ``TIPO_API_KEY``
                is set to a non-empty value.
        """
        resolved_tk = tk or os.getenv("TIPO_API_KEY")
        if not resolved_tk:
            raise ConfigurationError(
                "TIPO OpenData API key required. Set TIPO_API_KEY environment "
                f"variable or pass tk= to TipoClient. {_REGISTRATION_HINT}"
            )

        super().__init__(
            base_url=base_url or BASE_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "patent-client-agents-tipo-opdata/0.1",
            },
            **kwargs,
        )

        self._tk: str = resolved_tk

    # ------------------------------------------------------------------
    # Low-level GET helper
    # ------------------------------------------------------------------

    def _build_params(
        self,
        *,
        top: int | None,
        skip: int | None,
        filters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Compose the query-string dict for a TIPO request.

        The ``tk`` and ``format=json`` parameters are always present.
        ``top`` is clamped at :data:`MAX_TOP`. ``None``-valued filters
        are dropped so we never send empty query keys.
        """
        params: dict[str, Any] = {"tk": self._tk, "format": "json"}
        if top is not None:
            params["top"] = min(int(top), MAX_TOP)
        if skip is not None:
            params["skip"] = int(skip)
        if filters:
            for key, value in filters.items():
                if value is None:
                    continue
                params[key] = value
        return params

    async def _get_rows(
        self,
        endpoint: str,
        *,
        top: int | None = None,
        skip: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """GET ``endpoint`` and return ``(rows, envelope-meta)``.

        ``envelope-meta`` is the raw response payload so callers can
        read ``total-count`` / ``top`` / ``skip`` if needed.
        """
        params = self._build_params(top=top, skip=skip, filters=filters)
        payload = await self._request_json(
            "GET",
            endpoint,
            params=params,
            context=f"tipo_opdata.get[{endpoint}]",
        )
        return _extract_rows(payload), payload

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    async def paginate(
        self,
        endpoint: str,
        *,
        top: int = MAX_TOP,
        skip: int = 0,
        **filters: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Iterate every row of ``endpoint`` past the 6,000-row cap.

        Walks ``skip`` in pages of ``top`` (clamped to
        :data:`MAX_TOP`) until the API returns a short page, signalling
        end of stream. Yields the raw row dicts; callers are
        responsible for choosing the right ``*Row`` model.

        Args:
            endpoint: Path under the base URL, e.g. ``"/PatentAppl"``.
            top: Page size (clamped to 6,000).
            skip: Initial offset.
            **filters: Forwarded as query parameters.
        """
        page_size = min(int(top), MAX_TOP)
        offset = int(skip)
        while True:
            rows, _ = await self._get_rows(
                endpoint,
                top=page_size,
                skip=offset,
                filters=filters,
            )
            for row in rows:
                yield row
            if len(rows) < page_size:
                return
            offset += page_size

    # ------------------------------------------------------------------
    # Patent endpoints
    # ------------------------------------------------------------------

    async def search_patent_appl(
        self,
        *,
        q: str | None = None,
        applclass: int | str | None = None,
        appl_no: str | list[str] | None = None,
        appl_date_from: str | None = None,
        appl_date_to: str | None = None,
        applicant: str | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[PatentApplRow]:
        """``/PatentAppl`` — patent / UM / design application biblio."""
        filters: dict[str, Any] = {
            "q": q,
            "applclass": applclass,
            "appl-no": _join_list(appl_no),
            "appl-date-from": appl_date_from,
            "appl-date-to": appl_date_to,
            "applicant": applicant,
        }
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/PatentAppl", top=top, skip=skip, filters=filters
        )
        return [PatentApplRow.model_validate(r) for r in rows]

    async def get_patent_pub(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[PatentPubRow]:
        """``/PatentPub`` — KOKAI / KOKOKU publications."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/PatentPub", top=top, skip=skip, filters=filters
        )
        return [PatentPubRow.model_validate(r) for r in rows]

    async def get_patent_rights(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[PatentRightsRow]:
        """``/PatentRights`` — grant + status (carries ``twins-flag``)."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/PatentRights", top=top, skip=skip, filters=filters
        )
        return [PatentRightsRow.model_validate(r) for r in rows]

    async def get_patent_priority(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[PatentPriorityRow]:
        """``/PatentPriority`` — Paris priority claims."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/PatentPriority", top=top, skip=skip, filters=filters
        )
        return [PatentPriorityRow.model_validate(r) for r in rows]

    async def get_patent_annuity(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[PatentAnnuityRow]:
        """``/PatentAnnuity`` — annuity payment schedule."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/PatentAnnuity", top=top, skip=skip, filters=filters
        )
        return [PatentAnnuityRow.model_validate(r) for r in rows]

    async def get_patent_twins(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[PatentTwinsRow]:
        """``/PatentTwins`` — TW Article 32 invention / UM pairs."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/PatentTwins", top=top, skip=skip, filters=filters
        )
        return [PatentTwinsRow.model_validate(r) for r in rows]

    async def get_patent_alteration(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[PatentAlterationRow]:
        """``/PatentAlteration`` — applicant / inventor / agent edits."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/PatentAlteration", top=top, skip=skip, filters=filters
        )
        return [PatentAlterationRow.model_validate(r) for r in rows]

    async def get_patent_change(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[PatentChangeRow]:
        """``/PatentChange`` — application-identifier changes."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/PatentChange", top=top, skip=skip, filters=filters
        )
        return [PatentChangeRow.model_validate(r) for r in rows]

    async def get_patent_divide(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[PatentDivideRow]:
        """``/PatentDivide`` — divisional application links."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/PatentDivide", top=top, skip=skip, filters=filters
        )
        return [PatentDivideRow.model_validate(r) for r in rows]

    # ------------------------------------------------------------------
    # Trademark endpoints
    # ------------------------------------------------------------------

    async def search_tmark_appl(
        self,
        *,
        q: str | None = None,
        appl_no: str | list[str] | None = None,
        appl_date_from: str | None = None,
        appl_date_to: str | None = None,
        applicant: str | None = None,
        tmark_class: str | int | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[TmarkApplRow]:
        """``/TmarkAppl`` — trademark application biblio."""
        filters: dict[str, Any] = {
            "q": q,
            "appl-no": _join_list(appl_no),
            "appl-date-from": appl_date_from,
            "appl-date-to": appl_date_to,
            "applicant": applicant,
            "tmark-class": tmark_class,
        }
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/TmarkAppl", top=top, skip=skip, filters=filters
        )
        return [TmarkApplRow.model_validate(r) for r in rows]

    async def get_tmark_rights(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[TmarkRightsRow]:
        """``/TmarkRights`` — TM registration + status."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/TmarkRights", top=top, skip=skip, filters=filters
        )
        return [TmarkRightsRow.model_validate(r) for r in rows]

    async def get_tmark_priority(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[TmarkPriorityRow]:
        """``/TmarkPriority`` — TM priority claims."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/TmarkPriority", top=top, skip=skip, filters=filters
        )
        return [TmarkPriorityRow.model_validate(r) for r in rows]

    async def get_tmark_pics(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[TmarkPicsRow]:
        """``/TmarkPics`` — TM image URLs (URLs only, no rendering)."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/TmarkPics", top=top, skip=skip, filters=filters
        )
        return [TmarkPicsRow.model_validate(r) for r in rows]

    async def get_tmark_change(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[TmarkChangeRow]:
        """``/TmarkChange`` — TM transfer / name-change events."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/TmarkChange", top=top, skip=skip, filters=filters
        )
        return [TmarkChangeRow.model_validate(r) for r in rows]

    async def get_tmark_divide(
        self,
        *,
        appl_no: str | list[str] | None = None,
        top: int = MAX_TOP,
        skip: int = 0,
        **extra: Any,
    ) -> list[TmarkDivideRow]:
        """``/TmarkDivide`` — TM application divisions."""
        filters: dict[str, Any] = {"appl-no": _join_list(appl_no)}
        filters.update(extra)
        rows, _ = await self._get_rows(
            "/TmarkDivide", top=top, skip=skip, filters=filters
        )
        return [TmarkDivideRow.model_validate(r) for r in rows]


def _join_list(value: str | list[str] | None) -> str | None:
    """Render an appl-no list as a single OR-style query value.

    TIPO's OpenData filters take scalar values; for list inputs we
    join with commas, which the upstream tolerates as an OR-style
    multi-match on the public demo dataset. Returns ``None`` on empty
    / falsy input so it's dropped from the query.
    """
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v or None
    items = [str(x).strip() for x in value if str(x).strip()]
    return ",".join(items) or None


__all__ = ["TipoClient", "BASE_URL", "MAX_TOP"]
