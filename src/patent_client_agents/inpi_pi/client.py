"""Async client for INPI France ``api-gateway.inpi.fr`` (TM + Design only).

Wraps the INPI apidiffusion REST surface for French national trademarks
(WIPO ST.66 v1.0) and designs (WIPO ST.86 v1.0). Authentication is a
session-bearer + XSRF flow bound to a personal ``data.inpi.fr`` account;
see :mod:`patent_client_agents.inpi_pi.session` for the lifecycle.

Patents — deliberately absent
-----------------------------
**No patent methods are exposed.** For FR patent coverage, use
``patent_client_agents.epo_ops`` (country code ``FR``); INPADOC covers
EP-routed FR designations and FR national-route filings with adequate
fidelity. The INPI national patents API exists, but its bibliographic
coverage duplicates EPO INPADOC for the same filings and adds no signal
worth the second auth surface. The connector standards `single source
of truth` principle (CONNECTOR_STANDARDS.md §6) prefers one canonical
upstream per dataset.

Usage::

    async with InpiPiClient(username="...", password="...") as client:
        hits = await client.search_trademarks(q="Apple", nice_class=["9"])
        record = await client.get_trademark("4216963")

Environment Variables:
    INPI_USERNAME: personal data.inpi.fr account username
    INPI_PASSWORD: personal data.inpi.fr account password
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from collections.abc import Callable, Iterable
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from law_tools_core.base_client import BaseAsyncClient
from law_tools_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    RateLimitError,
    ValidationError,
)
from law_tools_core.resilience import default_retryer

from .models import InpiDesignRow, InpiTrademarkRow
from .session import XSRF_HEADER_NAME, InpiSession, fetch_xsrf, login, refresh

logger = logging.getLogger(__name__)

BASE_URL = "https://api-gateway.inpi.fr"

# Client-side throttle: 10 requests / 60 s (synopsis §3). Matches INPI's
# documented polite-use guidance; INPI does not publish a hard per-key
# RPM, but throttle-before-burst is the right default given the CGU
# "no obstruction of third-party access" clause (spec §6).
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60.0

# Per-fetch and per-page caps from spec §3 / §5.4 (CONNECTOR_STANDARDS).
MAX_LIST_ACCEPT = 50  # ``get_*`` accepts up to 50 identifiers per call
MAX_OFFSET = 500  # INPI SolR pagination cap
DEFAULT_PAGE_LIMIT = 25
MAX_PAGE_LIMIT = 100

# INPI apidiffusion endpoint paths (TM + Design). The gateway hosts
# parallel ``/api/marques`` and ``/api/dessins`` subtrees; trailing-slash
# discipline matters less here since httpx normalizes, but we keep these
# canonical for log readability.
PATH_MARQUES_SEARCH = "/services/apidiffusion/api/marques/search"
PATH_MARQUE_NOTICE = "/services/apidiffusion/api/marques"
PATH_DESSINS_SEARCH = "/services/apidiffusion/api/dessins/search"
PATH_DESSIN_NOTICE = "/services/apidiffusion/api/dessins"


# =============================================================================
# Helpers
# =============================================================================


def _coerce_list(value: str | Iterable[str]) -> list[str]:
    """Normalize a single-id-or-list argument to a list of strings."""
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _solr_escape(value: str) -> str:
    """Quote a SolR Lucene term so embedded whitespace stays one token.

    Wraps in double quotes when the value contains whitespace or any of
    the Lucene reserved characters. Internal quotes are backslash-escaped.
    This is enough to keep simple INPI use cases (Nice classes,
    applicant names, status codes) safe; users who need raw SolR power
    can pass the literal expression through ``q``.
    """
    if not any(c.isspace() or c in '+-&|!(){}[]^"~*?:\\/' for c in value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _build_solr_query(
    *,
    q: str | None = None,
    nice_class: list[str] | None = None,
    locarno_class: list[str] | None = None,
    applicant: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """Compose a SolR Lucene query string from structured args.

    The output is the literal value of the INPI ``q`` parameter. Each
    structured field maps to a SolR index name documented in the INPI
    tech doc:

    * ``nice_class`` → ``ClassNumber`` (TM)
    * ``locarno_class`` → ``ClassNumber`` (Design)
    * ``applicant`` → ``DEPOSANT`` (per INPI SolR field naming)
    * ``status`` → ``MarkCurrentStatusCode`` / ``DesignCurrentStatusCode``
    * ``date_from`` / ``date_to`` → ``ApplicationDate:[from TO to]``

    The raw ``q`` argument is appended verbatim (joined with ``AND``)
    so callers can mix structured filters with hand-written SolR
    fragments — useful for the FT search-everywhere style.
    """
    clauses: list[str] = []
    if q:
        clauses.append(q.strip())
    if nice_class:
        clauses.append(
            "(" + " OR ".join(f"ClassNumber:{_solr_escape(c)}" for c in nice_class) + ")"
        )
    if locarno_class:
        clauses.append(
            "(" + " OR ".join(f"ClassNumber:{_solr_escape(c)}" for c in locarno_class) + ")"
        )
    if applicant:
        clauses.append(f"DEPOSANT:{_solr_escape(applicant)}")
    if status:
        clauses.append(f"MarkCurrentStatusCode:{_solr_escape(status)}")
    if date_from or date_to:
        lo = date_from or "*"
        hi = date_to or "*"
        clauses.append(f"ApplicationDate:[{lo} TO {hi}]")
    return " AND ".join(clauses) if clauses else "*:*"


# =============================================================================
# Throttle
# =============================================================================


class _SlidingWindowThrottle:
    """Bounded-rate sliding-window throttle.

    Implements the 10-req/min INPI guidance via a ``deque`` of recent
    request timestamps plus an ``asyncio.Semaphore`` bound at the
    request cap. The clock callable is injectable so tests can advance
    time without sleeping; production uses :func:`time.monotonic`.
    """

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_REQUESTS,
        window_seconds: float = RATE_LIMIT_WINDOW_SECONDS,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a request can be made within the rate cap."""
        async with self._lock:
            now = self._clock()
            cutoff = now - self.window_seconds
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.max_requests:
                wait_for = self._timestamps[0] + self.window_seconds - now
                if wait_for > 0:
                    logger.debug("INPI throttle: sleeping %.2fs", wait_for)
                    await asyncio.sleep(wait_for)
                now = self._clock()
                cutoff = now - self.window_seconds
                while self._timestamps and self._timestamps[0] < cutoff:
                    self._timestamps.popleft()
            self._timestamps.append(self._clock())


# =============================================================================
# Client
# =============================================================================


class InpiPiClient(BaseAsyncClient):
    """Async client for INPI France ``api-gateway.inpi.fr`` (TM + Design).

    Handles the XSRF-bootstrap → login → bearer + refresh-on-401
    lifecycle, applies a 10 req/min client-side throttle, and exposes
    typed search + fetch methods for FR national trademarks (ST.66 v1.0)
    and designs (ST.86 v1.0). Patent methods are deliberately absent —
    see the module docstring for the EPO-OPS substitution rationale.
    """

    DEFAULT_BASE_URL = BASE_URL
    CACHE_NAME = "inpi_pi"
    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Initialize the INPI api-gateway client.

        Args:
            username: INPI ``data.inpi.fr`` account username. Falls back
                to ``INPI_USERNAME``.
            password: INPI ``data.inpi.fr`` account password. Falls back
                to ``INPI_PASSWORD``.
            base_url: Override the default gateway base URL.
            client: Existing ``httpx.AsyncClient`` to reuse (testing).
            clock: Injectable monotonic-clock callable for the
                throttle. Defaults to :func:`time.monotonic`.

        Raises:
            ConfigurationError: When credentials are missing. The error
                message points users at the BYOK signup URL.
        """
        resolved_username = username or os.getenv("INPI_USERNAME")
        resolved_password = password or os.getenv("INPI_PASSWORD")

        if not resolved_username or not resolved_password:
            raise ConfigurationError(
                "INPI API credentials required. Set INPI_USERNAME and "
                "INPI_PASSWORD environment variables, or pass username "
                "and password parameters. Sign up at https://data.inpi.fr/."
            )

        super().__init__(
            base_url=base_url,
            client=client,
            use_cache=True,
            headers={"Accept": "application/json"},
            timeout=self.DEFAULT_TIMEOUT,
        )

        self._username = resolved_username
        self._password = resolved_password
        self._session: InpiSession | None = None
        self._session_lock = asyncio.Lock()
        self._throttle = _SlidingWindowThrottle(clock=clock)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def _ensure_session(self) -> InpiSession:
        """Return a live session, bootstrapping or refreshing as needed.

        Lazily executes the XSRF-bootstrap + login on first call. When
        the cached session's access token is near expiry, attempts a
        refresh; if refresh fails (or no refresh-token is available),
        falls back to a fresh bootstrap + login.
        """
        async with self._session_lock:
            if self._session is None:
                logger.debug("INPI: bootstrapping fresh session")
                xsrf = await fetch_xsrf(self._client, base_url=self.base_url)
                self._session = await login(
                    self._client,
                    self._username,
                    self._password,
                    xsrf,
                    base_url=self.base_url,
                )
                return self._session

            if self._session.is_expired():
                refreshed = await self._refresh_or_relogin(self._session)
                self._session = refreshed
            return self._session

    async def _refresh_or_relogin(self, current: InpiSession) -> InpiSession:
        """Refresh the access token, or fall back to a full re-login."""
        if current.refresh_token and current.xsrf_token:
            try:
                logger.debug("INPI: refreshing session")
                return await refresh(
                    self._client,
                    current.refresh_token,
                    current.xsrf_token,
                    base_url=self.base_url,
                )
            except AuthenticationError as exc:
                logger.debug("INPI refresh failed (%s); re-logging in", exc)
        xsrf = await fetch_xsrf(self._client, base_url=self.base_url)
        return await login(
            self._client, self._username, self._password, xsrf, base_url=self.base_url
        )

    async def _invalidate_session(self) -> None:
        """Drop the cached session so the next call re-bootstraps."""
        async with self._session_lock:
            self._session = None

    # ------------------------------------------------------------------
    # Low-level transport
    # ------------------------------------------------------------------

    async def _request(  # ty: ignore[invalid-method-override]
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
        retry_auth: bool = True,
    ) -> httpx.Response:
        """Issue a throttled, authenticated request to INPI's gateway.

        Applies the 10-req/min sliding-window throttle, attaches the
        bearer + XSRF + cookie state, and retries once on 401 by
        invalidating the cached session and re-authenticating.
        """
        await self._throttle.acquire()
        session = await self._ensure_session()
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {session.access_token}",
            "Accept": accept,
        }
        if session.xsrf_token:
            headers[XSRF_HEADER_NAME] = session.xsrf_token

        async for attempt in default_retryer(max_attempts=3, max_wait=10.0):
            with attempt:
                response = await self._client.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    cookies=session.cookies or None,
                )

                if response.status_code in (401, 403) and retry_auth:
                    await self._invalidate_session()
                    return await self._request(
                        method, path, params=params, accept=accept, retry_auth=False
                    )

                if response.status_code == 429:
                    raise RateLimitError(
                        "INPI API rate limit exceeded",
                        response.status_code,
                        response.text[:500],
                    )

                if not response.is_success:
                    raise ApiError(
                        f"INPI API error: HTTP {response.status_code}",
                        response.status_code,
                        response.text[:500],
                    )

                return response

        raise RuntimeError("INPI retry exhausted without raising")

    # ------------------------------------------------------------------
    # Search response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_search_envelope(
        body: Any, *, row_key_candidates: tuple[str, ...] = ("hits", "rows", "docs", "results")
    ) -> tuple[list[dict[str, Any]], int | None]:
        """Extract ``(rows, total)`` from an INPI search envelope.

        INPI's tech doc describes a JSON envelope of the form
        ``{"total": N, "hits": [...]}`` for SolR-backed search; the
        exact key name varies across the gateway's surfaces. We probe a
        small fixed set of candidates and fall back to treating a bare
        list as the row list.
        """
        if isinstance(body, list):
            coerced: list[dict[str, Any]] = [row for row in body if isinstance(row, dict)]
            return coerced, len(coerced)
        if not isinstance(body, dict):
            return [], None
        for key in row_key_candidates:
            rows = body.get(key)
            if isinstance(rows, list):
                # Use explicit ``in`` checks so a legitimate zero total
                # ({"total": 0, "hits": []}) doesn't get swallowed by
                # truthiness short-circuit.
                total: Any = None
                for total_key in ("total", "totalCount", "numFound"):
                    if total_key in body:
                        total = body[total_key]
                        break
                typed_rows: list[dict[str, Any]] = [r for r in rows if isinstance(r, dict)]
                return typed_rows, (int(total) if isinstance(total, int | float) else None)
        return [], None

    # ------------------------------------------------------------------
    # ST.66 / ST.86 XML notice parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_namespace(tag: str) -> str:
        """Drop the XML namespace prefix from a tag, if present."""
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def _xml_to_dict(cls, element: ET.Element) -> Any:
        """Recursively convert an ``ElementTree`` element to a dict.

        Children with repeated tags are folded into lists. Leaf values
        return as strings; empty leaves return ``None``. This produces
        a shape that matches the JSON envelope INPI emits for the
        same notice, so our Pydantic models accept either input.
        """
        children = list(element)
        if not children:
            text = (element.text or "").strip()
            return text or None
        result: dict[str, Any] = {}
        for child in children:
            tag = cls._strip_namespace(child.tag)
            value = cls._xml_to_dict(child)
            existing = result.get(tag)
            if existing is None:
                result[tag] = value
            elif isinstance(existing, list):
                existing.append(value)
            else:
                result[tag] = [existing, value]
        return result

    @classmethod
    def _parse_st66_notice(cls, xml_bytes: bytes) -> InpiTrademarkRow:
        """Parse an INPI ST.66 v1.0 XML notice into an :class:`InpiTrademarkRow`."""
        root = ET.fromstring(xml_bytes)
        data = cls._xml_to_dict(root)
        if isinstance(data, dict) and "TradeMark" in data:
            data = data["TradeMark"]
        if not isinstance(data, dict):
            raise ValidationError("INPI ST.66 notice did not contain a record element")
        return InpiTrademarkRow.model_validate(data)

    @classmethod
    def _parse_st86_notice(cls, xml_bytes: bytes) -> InpiDesignRow:
        """Parse an INPI ST.86 v1.0 XML notice into an :class:`InpiDesignRow`."""
        root = ET.fromstring(xml_bytes)
        data = cls._xml_to_dict(root)
        if isinstance(data, dict):
            for inner_key in ("Design", "DesignApplicationDetails", "DesignDetails"):
                if inner_key in data:
                    data = data[inner_key]
                    break
        if not isinstance(data, dict):
            raise ValidationError("INPI ST.86 notice did not contain a record element")
        return InpiDesignRow.model_validate(data)

    @classmethod
    def _coerce_notice(cls, response: httpx.Response, parser) -> Any:  # noqa: ANN001
        """Dispatch a notice response to the right parser based on Content-Type."""
        content_type = (response.headers.get("content-type") or "").lower()
        if "xml" in content_type:
            return parser(response.content)
        try:
            body = response.json()
        except ValueError as exc:
            raise ApiError(
                "INPI notice returned non-JSON, non-XML body",
                response.status_code,
                response.text[:500],
            ) from exc
        return body

    # ------------------------------------------------------------------
    # Trademark (marques) — ST.66 v1.0
    # ------------------------------------------------------------------

    async def search_trademarks(
        self,
        query: str | None = None,
        *,
        nice_class: list[str] | None = None,
        applicant: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> tuple[list[InpiTrademarkRow], int | None]:
        """Search FR national trademarks (ST.66 v1.0).

        Returns ``(rows, total)`` where ``rows`` is the parsed list of
        :class:`InpiTrademarkRow` for the requested page and ``total``
        is the SolR total-hit count when the envelope reports one.
        """
        if offset < 0 or offset > MAX_OFFSET:
            raise ValidationError(f"offset must be in [0, {MAX_OFFSET}], got {offset}")
        if limit <= 0 or limit > MAX_PAGE_LIMIT:
            raise ValidationError(f"limit must be in (0, {MAX_PAGE_LIMIT}], got {limit}")

        q = _build_solr_query(
            q=query,
            nice_class=nice_class,
            applicant=applicant,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
        response = await self._request(
            "GET",
            PATH_MARQUES_SEARCH,
            params={"q": q, "offset": offset, "limit": limit},
        )
        rows, total = self._parse_search_envelope(response.json())
        return [InpiTrademarkRow.model_validate(row) for row in rows], total

    async def get_trademark(self, application_number: str | list[str]) -> list[InpiTrademarkRow]:
        """Fetch one or more FR national trademarks by application number.

        Accepts a single string or a list (capped at 50 per §5.4). Calls
        are serialized through the 10-req/min throttle.
        """
        numbers = _coerce_list(application_number)
        if not numbers:
            raise ValidationError("get_trademark requires at least one application_number")
        if len(numbers) > MAX_LIST_ACCEPT:
            raise ValidationError(
                f"get_trademark accepts at most {MAX_LIST_ACCEPT} application_numbers"
            )

        results: list[InpiTrademarkRow] = []
        for appno in numbers:
            response = await self._request(
                "GET",
                f"{PATH_MARQUE_NOTICE}/{appno}",
                accept="application/json, application/xml",
            )
            body = self._coerce_notice(response, self._parse_st66_notice)
            if isinstance(body, InpiTrademarkRow):
                results.append(body)
            elif isinstance(body, dict):
                results.append(InpiTrademarkRow.model_validate(body))
            elif isinstance(body, list) and body:
                results.append(InpiTrademarkRow.model_validate(body[0]))
        return results

    # ------------------------------------------------------------------
    # Design (dessins) — ST.86 v1.0
    # ------------------------------------------------------------------

    async def search_designs(
        self,
        query: str | None = None,
        *,
        locarno_class: list[str] | None = None,
        applicant: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_PAGE_LIMIT,
    ) -> tuple[list[InpiDesignRow], int | None]:
        """Search FR national designs (ST.86 v1.0)."""
        if offset < 0 or offset > MAX_OFFSET:
            raise ValidationError(f"offset must be in [0, {MAX_OFFSET}], got {offset}")
        if limit <= 0 or limit > MAX_PAGE_LIMIT:
            raise ValidationError(f"limit must be in (0, {MAX_PAGE_LIMIT}], got {limit}")

        q = _build_solr_query(
            q=query,
            locarno_class=locarno_class,
            applicant=applicant,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
        response = await self._request(
            "GET",
            PATH_DESSINS_SEARCH,
            params={"q": q, "offset": offset, "limit": limit},
        )
        rows, total = self._parse_search_envelope(response.json())
        return [InpiDesignRow.model_validate(row) for row in rows], total

    async def get_design(self, application_number: str | list[str]) -> list[InpiDesignRow]:
        """Fetch one or more FR national designs by application number."""
        numbers = _coerce_list(application_number)
        if not numbers:
            raise ValidationError("get_design requires at least one application_number")
        if len(numbers) > MAX_LIST_ACCEPT:
            raise ValidationError(
                f"get_design accepts at most {MAX_LIST_ACCEPT} application_numbers"
            )

        results: list[InpiDesignRow] = []
        for appno in numbers:
            response = await self._request(
                "GET",
                f"{PATH_DESSIN_NOTICE}/{appno}",
                accept="application/json, application/xml",
            )
            body = self._coerce_notice(response, self._parse_st86_notice)
            if isinstance(body, InpiDesignRow):
                results.append(body)
            elif isinstance(body, dict):
                results.append(InpiDesignRow.model_validate(body))
            elif isinstance(body, list) and body:
                results.append(InpiDesignRow.model_validate(body[0]))
        return results


__all__ = [
    "InpiPiClient",
    "BASE_URL",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW_SECONDS",
    "MAX_LIST_ACCEPT",
    "MAX_OFFSET",
]
