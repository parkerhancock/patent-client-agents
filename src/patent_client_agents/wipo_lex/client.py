"""Async client for the WIPO Lex public web surface.

WIPO Lex does not publish a documented JSON API. The site renders all
human-facing pages as server-rendered HTML — the same surface used by the
JS frontend's ``wu-*`` web components. We treat the result and detail
pages as a stable HTTP surface and parse the small metadata layer the
pages carry on OpenGraph + ``<meta>`` tags.

Scope today is the **legislation** collection (search + detail). The
``treaties`` and ``judgments`` collections share the same shape and can
be added later by re-using ``transformers`` against their own ``/results``
and ``/details/{id}`` paths.

Etiquette: defaults to a polite User-Agent identifying the library; uses
the standard ``BaseAsyncClient`` cache so repeated fetches of the same
detail page hit SQLite rather than WIPO's CDN.
"""

from __future__ import annotations

import os
from typing import Any

from law_tools_core import BaseAsyncClient

from .models import (
    LegislationDetail,
    LegislationSearchResponse,
    SubjectMatter,
    TypeOfText,
)
from .transformers import parse_legislation_detail, parse_legislation_search


class WipoLexClient(BaseAsyncClient):
    """Async client for ``www.wipo.int/wipolex``.

    See the module docstring for the scope and stability contract.
    """

    DEFAULT_BASE_URL: str = os.getenv("WIPO_LEX_BASE_URL", "https://www.wipo.int")
    CACHE_NAME: str = "wipo_lex"
    DEFAULT_TIMEOUT: float = 30.0

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            headers={
                "User-Agent": "patent-client-agents-wipolex/0.1 (+https://patentclient.com)",
                "Accept": "text/html,application/xhtml+xml",
            },
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Legislation
    # ------------------------------------------------------------------

    async def search_legislation(
        self,
        *,
        country_codes: list[str] | None = None,
        subject_matter: list[SubjectMatter | int] | None = None,
        type_of_text: list[TypeOfText | int] | None = None,
        keywords: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_historical: bool = False,
    ) -> LegislationSearchResponse:
        """Search the WIPO Lex legislation collection.

        Args:
            country_codes: ISO 3166-1 alpha-2 codes (e.g. ``["CA", "US"]``).
            subject_matter: One or more :class:`SubjectMatter` codes (or ints).
            type_of_text: One or more :class:`TypeOfText` codes.
            keywords: Full-text search over title + notes.
            start_date: Lower bound on legislation date (``YYYY-MM-DD``).
            end_date: Upper bound on legislation date.
            include_historical: If True, include superseded/historical texts.

        Returns:
            :class:`LegislationSearchResponse` — list of hits + the query URL.
        """
        params: list[tuple[str, str]] = []
        for code in country_codes or []:
            params.append(("countryOrgs", code))
        for code in subject_matter or []:
            params.append(("subjectMatter", str(int(code))))
        for code in type_of_text or []:
            params.append(("typeOfText", str(int(code))))
        if keywords:
            params.append(("keywords", keywords))
        if start_date:
            params.append(("sDate", start_date))
        if end_date:
            params.append(("eDate", end_date))
        params.append(("last", "true" if include_historical else "false"))

        # WIPO Lex's search endpoint expects repeated keys (e.g.
        # ``sub=1&sub=2``); represent as list[tuple] which httpx accepts.
        # The base_client signature types params as dict[str, Any] | None,
        # so this is a real widening — suppress to keep the deferred fix
        # off the critical path.
        response = await self._request(
            "GET",
            "/wipolex/en/legislation/results",
            params=params,  # ty: ignore[invalid-argument-type]
            context="search_legislation",
        )
        html_text = response.text
        return parse_legislation_search(
            html_text, base_url=self.base_url, query_url=str(response.request.url)
        )

    async def get_legislation(self, legislation_id: str | int) -> LegislationDetail:
        """Fetch the metadata + attachment links for a single legislation entry.

        Args:
            legislation_id: WIPO Lex internal ID (e.g. ``"23293"`` for the
                Canadian Patent Act).

        Returns:
            :class:`LegislationDetail` with title, jurisdiction, summary,
            canonical URL, and the list of downloadable file links.
        """
        path = f"/wipolex/en/legislation/details/{legislation_id}"
        response = await self._request("GET", path, context="get_legislation")
        return parse_legislation_detail(
            response.text, base_url=self.base_url, legislation_id=str(legislation_id)
        )


__all__ = ["WipoLexClient"]
