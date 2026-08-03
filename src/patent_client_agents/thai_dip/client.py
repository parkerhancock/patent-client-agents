"""Async client for Thailand's DIP Data Exchange register APIs.

The request fields and response names come from DIP's public per-API catalogue.
Compatibility is tested with synthetic JSON fixtures, not a live DIP account.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Literal, TypeVar, cast

import httpx

from mcp_data_core.base_client import BaseAsyncClient
from mcp_data_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
)

from .models import (
    ThaiDipCopyrightRecord,
    ThaiDipGiRecord,
    ThaiDipPatentRecord,
    ThaiDipSongRecord,
    ThaiDipTrademarkRecord,
)

BASE_URL = "https://api.ipthailand.go.th/DIP-APIDynamic/api/Search"
CATALOGUE_URL = "https://api.ipthailand.go.th/data-exchange/view/home.aspx"
LIST_ACCEPT_CAP = 50
RESULT_LIMIT = 100

PatentKind = Literal["invention", "design", "petty_patent"]
PatentField = Literal["title", "application_number", "publication_number", "patent_number"]
TrademarkField = Literal["name", "application_number", "registration_number", "expiry_date"]
CopyrightField = Literal["work_name", "work_type", "request_number", "registration_number", "owner"]
SongField = Literal["song_name", "album_name", "lyric_author", "composer"]
GiField = Literal["name", "application_id"]

_PATENT_ENDPOINTS: dict[PatentKind, str] = {
    "invention": "PATENT_NOIP",
    "design": "PRODUCTPATENT",
    "petty_patent": "PETTYPATENT",
}
_PATENT_FIELDS: dict[PatentField, tuple[str, bool]] = {
    "title": ("patent_name", True),
    "application_number": ("app_no", False),
    "publication_number": ("pub_no", False),
    "patent_number": ("patent_no", False),
}
_TRADEMARK_FIELDS: dict[TrademarkField, tuple[str, bool]] = {
    "name": ("tr_name", False),
    "application_number": ("req_no", True),
    "registration_number": ("regis_no", False),
    "expiry_date": ("expire_date", False),
}
_COPYRIGHT_FIELDS: dict[CopyrightField, tuple[str, bool]] = {
    "work_name": ("work_name", True),
    "work_type": ("typename", True),
    "request_number": ("request_no", False),
    "registration_number": ("register_no", False),
    "owner": ("owner_name", True),
}
_SONG_FIELDS: dict[SongField, tuple[str, bool]] = {
    "song_name": ("reg_songs_name", True),
    "album_name": ("album_name", True),
    "lyric_author": ("lyric_author_name", True),
    "composer": ("compose_author_name", True),
}
_GI_FIELDS: dict[GiField, tuple[str, bool]] = {
    "name": ("giname", True),
    "application_id": ("app_no_number", False),
}

RecordT = TypeVar(
    "RecordT",
    ThaiDipPatentRecord,
    ThaiDipTrademarkRecord,
    ThaiDipCopyrightRecord,
    ThaiDipSongRecord,
    ThaiDipGiRecord,
)


def _value(row: dict[str, Any], *names: str) -> Any:
    folded = {str(key).upper(): value for key, value in row.items()}
    for name in names:
        value = folded.get(name.upper())
        if value not in (None, ""):
            return value
    return None


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _query(field: tuple[str, bool], value: str) -> dict[str, str]:
    text = value.strip()
    if not text or len(text) > 500:
        raise ConfigurationError("DIP query must contain 1 to 500 characters")
    name, wildcard = field
    return {name: f"%{text}%" if wildcard else text}


def _patent(row: dict[str, Any], kind: PatentKind) -> ThaiDipPatentRecord:
    identifier = _text(_value(row, "APP_NO", "PATENT_NO", "PUB_NO"))
    if not identifier:
        raise ApiError("DIP patent response lacks an identifier", -1, "")
    return ThaiDipPatentRecord(
        identifier=identifier,
        right_type=kind,
        application_number=_text(_value(row, "APP_NO")),
        publication_number=_text(_value(row, "PUB_NO")),
        patent_number=_text(_value(row, "PATENT_NO")),
        title=_text(_value(row, "PATENT_NAME")),
        status=_text(_value(row, "LATEST_STATUS")),
        filing_date=_value(row, "FILING_DATE"),
        publication_date=_value(row, "PUBLIC_DATE"),
        grant_date=_value(row, "GRANT_DATE"),
        expiry_date=_value(row, "EXPIRE_DATE"),
        applicant=_text(_value(row, "APPLICANT")),
        inventor=_text(_value(row, "INV")),
        agent=_text(_value(row, "AGE")),
        ipc=_text(_value(row, "IPC")),
        abstract=_text(_value(row, "APP_ABS", "PATENT_ABS")),
        raw=row,
    )


def _trademark(row: dict[str, Any]) -> ThaiDipTrademarkRecord:
    identifier = _text(_value(row, "REQ_NO", "REGIS_NO"))
    if not identifier:
        raise ApiError("DIP trademark response lacks an identifier", -1, "")
    return ThaiDipTrademarkRecord(
        identifier=identifier,
        application_number=_text(_value(row, "REQ_NO")),
        registration_number=_text(_value(row, "REGIS_NO")),
        mark_name=_text(_value(row, "TR_NAME", "MARKDESC")),
        status=_text(_value(row, "TRADEMARK_STATUS", "REQUEST_STATUS")),
        application_date=_value(row, "REQ_DATE"),
        registration_date=_value(row, "REGIS_DATE"),
        publication_date=_value(row, "PUBLIC_DATE"),
        expiry_date=_value(row, "EXPIRE_DATE"),
        owner=_text(_value(row, "OWNER_NAME")),
        nice_class=_text(_value(row, "NICE_CLASS_CODE", "NCLASS_NAME")),
        goods=_text(_value(row, "NICE_CLASS_TNAME")),
        raw=row,
    )


def _copyright(row: dict[str, Any]) -> ThaiDipCopyrightRecord:
    identifier = _text(_value(row, "REQUEST_NO", "REGISTER_NO", "PKID"))
    if not identifier:
        raise ApiError("DIP copyright response lacks an identifier", -1, "")
    return ThaiDipCopyrightRecord(
        identifier=identifier,
        request_number=_text(_value(row, "REQUEST_NO")),
        registration_number=_text(_value(row, "REGISTER_NO")),
        work_name=_text(_value(row, "WORK_NAME")),
        category=_text(_value(row, "CATEGORY")),
        work_type=_text(_value(row, "TYPENAME")),
        submit_date=_value(row, "SUBMIT_DATE", "SUBMIT_DATEV2"),
        owner=_text(_value(row, "OWNER_NAME", "OWNER_GOV_NAME")),
        creator=_text(_value(row, "CREATOR_NAME")),
        description=_text(_value(row, "WORK_DESCRIPTION")),
        raw=row,
    )


def _song(row: dict[str, Any]) -> ThaiDipSongRecord:
    identifier = _text(_value(row, "PKID", "ID"))
    if not identifier:
        raise ApiError("DIP song response lacks an identifier", -1, "")
    return ThaiDipSongRecord(
        identifier=identifier,
        song_name=_text(_value(row, "REG_SONGS_NAME")),
        album_name=_text(_value(row, "ALBUM_NAME")),
        lyric_author=_text(_value(row, "LYRIC_AUTHOR_NAME")),
        composer=_text(_value(row, "COMPOSE_AUTHOR_NAME")),
        song_type=_text(_value(row, "SONG_TYPE")),
        license_owner=_text(_value(row, "LICENSE_OWNER_NAME")),
        license_end_date=_value(row, "LICENSE_TERMINATION_DATE"),
        raw=row,
    )


def _gi(row: dict[str, Any]) -> ThaiDipGiRecord:
    identifier = _text(_value(row, "APP_NO_NUMBER", "REQUEST", "APPLICATIONNUMBER", "PKID"))
    if not identifier:
        raise ApiError("DIP geographical-indication response lacks an identifier", -1, "")
    return ThaiDipGiRecord(
        identifier=identifier,
        request_number=_text(_value(row, "REQUEST")),
        application_number=_text(_value(row, "APPLICATIONNUMBER")),
        name=_text(_value(row, "GINAME")),
        product=_text(_value(row, "GIPRODUCT")),
        category=_text(_value(row, "GICATEGORYNAME")),
        product_type=_text(_value(row, "GITYPENAME")),
        province=_text(_value(row, "PROVINCENAME")),
        region=_text(_value(row, "REGIONNAME")),
        application_date=_value(row, "APPLICATIONDATE", "SUBMITDATE"),
        publication_date=_value(row, "PUBLICATIONDATE"),
        raw=row,
    )


class ThaiDipClient(BaseAsyncClient):
    """Client for seven register datasets in Thailand's DIP Data Exchange."""

    DEFAULT_BASE_URL = BASE_URL
    CACHE_NAME = "thai_dip"

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        resolved_token = token or os.getenv("DIP_DATA_EXCHANGE_TOKEN")
        if not resolved_token:
            raise ConfigurationError(
                "Thailand DIP Data Exchange token required. Set DIP_DATA_EXCHANGE_TOKEN. "
                f"Apply through {CATALOGUE_URL}."
            )
        resolved_base = (base_url or BASE_URL).rstrip("/")
        if client is None and not resolved_base.startswith("https://"):
            raise ConfigurationError("Thailand DIP Data Exchange requires an HTTPS base URL")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {resolved_token}",
        }
        super().__init__(
            base_url=resolved_base,
            client=client,
            headers=headers,
            timeout=30.0,
            use_cache=True,
        )
        if client is not None:
            client.headers.update(headers)

    async def _post(
        self,
        endpoint: str,
        payload: dict[str, str],
        parser: Callable[[dict[str, Any]], RecordT],
        limit: int,
    ) -> tuple[list[RecordT], int]:
        if not 1 <= limit <= RESULT_LIMIT:
            raise ConfigurationError(f"limit must be between 1 and {RESULT_LIMIT}")
        response = await self._client.post(f"{self.base_url}/{endpoint}", json=payload)
        if response.status_code in {401, 403}:
            raise AuthenticationError(
                "Thailand DIP rejected the Data Exchange token", response.status_code, ""
            )
        if response.status_code == 429:
            raise RateLimitError("Thailand DIP rate limit exceeded", 429, response.text[:500])
        if not response.is_success:
            raise ApiError(
                f"Thailand DIP HTTP {response.status_code}",
                response.status_code,
                response.text[:500],
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise ApiError("Thailand DIP returned malformed JSON", -1, response.text[:500]) from exc
        if not isinstance(body, list):
            message = body.get("message") if isinstance(body, dict) else None
            raise ApiError(
                f"Thailand DIP returned an unexpected response{f': {message}' if message else ''}",
                -1,
                response.text[:500],
            )
        rows = [parser(cast("dict[str, Any]", row)) for row in body if isinstance(row, dict)]
        return rows[:limit], len(rows)

    async def search_patents(
        self,
        query: str,
        *,
        right_type: PatentKind = "invention",
        field: PatentField = "title",
        limit: int = 25,
    ) -> tuple[list[ThaiDipPatentRecord], int]:
        endpoint = _PATENT_ENDPOINTS[right_type]
        return await self._post(
            endpoint,
            _query(_PATENT_FIELDS[field], query),
            lambda row: _patent(row, right_type),
            limit,
        )

    async def get_patent(
        self, number: str, *, right_type: PatentKind = "invention"
    ) -> ThaiDipPatentRecord:
        rows, _ = await self.search_patents(
            number, right_type=right_type, field="application_number", limit=1
        )
        if not rows:
            raise NotFoundError(f"Thailand DIP patent not found: {number}", 404, "")
        return rows[0]

    async def search_trademarks(
        self, query: str, *, field: TrademarkField = "name", limit: int = 25
    ) -> tuple[list[ThaiDipTrademarkRecord], int]:
        return await self._post("TM", _query(_TRADEMARK_FIELDS[field], query), _trademark, limit)

    async def get_trademark(self, number: str) -> ThaiDipTrademarkRecord:
        rows, _ = await self.search_trademarks(number, field="application_number", limit=1)
        if not rows:
            raise NotFoundError(f"Thailand DIP trademark not found: {number}", 404, "")
        return rows[0]

    async def search_copyrights(
        self, query: str, *, field: CopyrightField = "work_name", limit: int = 25
    ) -> tuple[list[ThaiDipCopyrightRecord], int]:
        return await self._post("CPR", _query(_COPYRIGHT_FIELDS[field], query), _copyright, limit)

    async def get_copyright(self, number: str) -> ThaiDipCopyrightRecord:
        rows, _ = await self.search_copyrights(number, field="request_number", limit=1)
        if not rows:
            raise NotFoundError(f"Thailand DIP copyright record not found: {number}", 404, "")
        return rows[0]

    async def search_songs(
        self, query: str, *, field: SongField = "song_name", limit: int = 25
    ) -> tuple[list[ThaiDipSongRecord], int]:
        return await self._post("CPRSONG", _query(_SONG_FIELDS[field], query), _song, limit)

    async def search_geographical_indications(
        self, query: str, *, field: GiField = "name", limit: int = 25
    ) -> tuple[list[ThaiDipGiRecord], int]:
        return await self._post("GI", _query(_GI_FIELDS[field], query), _gi, limit)

    async def get_geographical_indication(self, application_id: str) -> ThaiDipGiRecord:
        rows, _ = await self.search_geographical_indications(
            application_id, field="application_id", limit=1
        )
        if not rows:
            raise NotFoundError(
                f"Thailand DIP geographical indication not found: {application_id}", 404, ""
            )
        return rows[0]
