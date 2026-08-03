"""Async client for the Swiss IPI Swissreg datadelivery API.

The XML contract follows the public IPI XSD catalog. Compatibility is tested
with schema-derived fixtures because no maintainer account is configured.
"""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar

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
    IpiPatentRecord,
    IpiPublicationRecord,
    IpiSearchMeta,
    IpiSpcRecord,
    IpiTrademarkRecord,
    parse_ipi_date,
)

BASE_URL = "https://www.swissreg.ch/public/api/v1"
TOKEN_URL = "https://idp.ipi.ch/auth/realms/egov/protocol/openid-connect/token"
TOKEN_CLIENT_ID = "datadelivery-api-client"
CORE_NS = "urn:ige:schema:xsd:datadeliverycore-1.0.0"
COMMON_NS = "urn:ige:schema:xsd:datadeliverycommon-1.0.0"
LIST_ACCEPT_CAP = 50
MAX_PAGE_SIZE = 64
_SIGNUP_URL = "https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api"

ET.register_namespace("core", CORE_NS)
ET.register_namespace("common", COMMON_NS)

RecordT = TypeVar("RecordT")


@dataclass(frozen=True)
class _Action(Generic[RecordT]):
    name: str
    request_element: str
    namespace: str
    identifier_field: str | None
    parser: Callable[[ET.Element], RecordT]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _key(tag: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _local(tag).lower())


def _element_to_value(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    result: dict[str, Any] = {}
    for child in children:
        name = _local(child.tag)
        value = _element_to_value(child)
        if name in result:
            current = result[name]
            result[name] = current + [value] if isinstance(current, list) else [current, value]
        else:
            result[name] = value
    if element.attrib:
        result["_attributes"] = dict(element.attrib)
    return result


def _leaves(element: ET.Element) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for node in element.iter():
        if list(node):
            continue
        value = (node.text or "").strip()
        if value:
            result.setdefault(_key(node.tag), []).append(value)
    return result


def _first(leaves: dict[str, list[str]], *aliases: str) -> str | None:
    for alias in aliases:
        values = leaves.get(_key(alias))
        if values:
            return values[0]
    return None


def _many(leaves: dict[str, list[str]], *aliases: str) -> list[str]:
    values: list[str] = []
    for alias in aliases:
        values.extend(leaves.get(_key(alias), []))
    return list(dict.fromkeys(values))


def _raw(element: ET.Element) -> dict[str, Any]:
    return {_local(element.tag): _element_to_value(element)}


def _patent(element: ET.Element) -> IpiPatentRecord:
    leaves = _leaves(element)
    patent_number = _first(leaves, "PatentNumber", "IPRightNumber")
    application_number = _first(leaves, "ApplicationNumber")
    identifier = patent_number or application_number
    if not identifier:
        raise ApiError("Swiss IPI patent XML lacks an identifier", -1, "")
    return IpiPatentRecord(
        identifier=identifier,
        patent_number=patent_number,
        application_number=application_number,
        publication_number=_first(leaves, "PublicationNumber", "DocumentNumber"),
        title=_first(leaves, "PatentTitle", "InventionTitle", "Title"),
        status=_first(leaves, "IPRightStatus", "FileStatus", "Status"),
        owner=_first(leaves, "OwnerName", "ApplicantName", "Owner", "Applicant"),
        application_date=parse_ipi_date(_first(leaves, "ApplicationDate", "FilingDate")),
        publication_date=parse_ipi_date(_first(leaves, "PublicationDate")),
        grant_date=parse_ipi_date(_first(leaves, "GrantDate")),
        ipc=_many(leaves, "IPCClassification", "IPC"),
        cpc=_many(leaves, "CPCClassification", "CPC"),
        inventors=_many(leaves, "InventorName", "Inventor"),
        raw=_raw(element),
    )


def _trademark(element: ET.Element) -> IpiTrademarkRecord:
    leaves = _leaves(element)
    trademark_number = _first(leaves, "TradeMarkNumber", "TrademarkNumber", "IPRightNumber")
    application_number = _first(leaves, "ApplicationNumber")
    identifier = trademark_number or application_number
    if not identifier:
        raise ApiError("Swiss IPI trademark XML lacks an identifier", -1, "")
    return IpiTrademarkRecord(
        identifier=identifier,
        trademark_number=trademark_number,
        application_number=application_number,
        title=_first(leaves, "TradeMarkTitle", "TrademarkTitle", "Title"),
        word_element=_first(leaves, "MarkVerbalElementText", "WordElement", "MarkText"),
        status=_first(leaves, "IPRightStatus", "FileStatus", "Status"),
        owner=_first(leaves, "OwnerName", "ApplicantName", "Owner", "Applicant"),
        application_date=parse_ipi_date(_first(leaves, "ApplicationDate", "FilingDate")),
        registration_date=parse_ipi_date(_first(leaves, "RegistrationDate")),
        expiry_date=parse_ipi_date(_first(leaves, "ExpiryDate", "ExpirationDate")),
        nice_classification=_many(leaves, "NiceClassNumber", "NiceClassification", "NiceClass"),
        raw=_raw(element),
    )


def _spc(element: ET.Element) -> IpiSpcRecord:
    leaves = _leaves(element)
    spc_number = _first(leaves, "SPCNumber", "IPRightNumber")
    application_number = _first(leaves, "ApplicationNumber")
    identifier = spc_number or application_number
    if not identifier:
        raise ApiError("Swiss IPI SPC XML lacks an identifier", -1, "")
    return IpiSpcRecord(
        identifier=identifier,
        spc_number=spc_number,
        application_number=application_number,
        product=_first(leaves, "Product", "ProductName"),
        basic_patent_number=_first(leaves, "BasicPatentNumber"),
        authorisation_number=_first(leaves, "AuthorisationNumber", "AuthorizationNumber"),
        status=_first(leaves, "IPRightStatus", "FileStatus", "Status"),
        owner=_first(leaves, "OwnerName", "ApplicantName", "Owner", "Applicant"),
        application_date=parse_ipi_date(_first(leaves, "ApplicationDate", "FilingDate")),
        grant_date=parse_ipi_date(_first(leaves, "GrantDate")),
        maximum_term_of_protection_date=parse_ipi_date(
            _first(leaves, "MaximumTermOfProtectionDate", "TermOfProtectionDate")
        ),
        raw=_raw(element),
    )


def _publication(
    right_type: Literal["patent", "spc"],
) -> Callable[[ET.Element], IpiPublicationRecord]:
    def parse(element: ET.Element) -> IpiPublicationRecord:
        leaves = _leaves(element)
        number = _first(
            leaves,
            "IPRightNumber",
            "PatentNumber" if right_type == "patent" else "SPCNumber",
        )
        title = _first(leaves, "PublicationTitle", "Title")
        publication_date = _first(leaves, "PublicationDate")
        identifier = number or title
        if not identifier:
            raise ApiError(f"Swiss IPI {right_type} publication XML lacks an identifier", -1, "")
        return IpiPublicationRecord(
            identifier=identifier,
            right_type=right_type,
            publication_title=title,
            publication_text=_first(leaves, "PublicationText"),
            published_remark=_first(leaves, "PublishedRemark"),
            reason_for_publication=_first(leaves, "ReasonForPublication"),
            ip_right_number=number,
            publication_date=parse_ipi_date(publication_date),
            owner=_first(leaves, "OwnerName", "Owner"),
            classification=_many(leaves, "IPCClassification", "IPC"),
            raw=_raw(element),
        )

    return parse


PATENT = _Action(
    "PatentSearch",
    "PatentSearchRequest",
    "urn:ige:schema:xsd:datadeliverypatent-1.0.0",
    "PatentNumber",
    _patent,
)
PATENT_PUBLICATION = _Action(
    "PatentPublicationSearch",
    "PatentPublicationSearchRequest",
    "urn:ige:schema:xsd:datadeliverypatentpublication-1.0.0",
    None,
    _publication("patent"),
)
TRADEMARK = _Action(
    "TrademarkSearch",
    "TrademarkSearchRequest",
    "urn:ige:schema:xsd:datadeliverytrademark-1.0.0",
    "TradeMarkNumber",
    _trademark,
)
SPC = _Action(
    "SPCSearch",
    "SPCSearchRequest",
    "urn:ige:schema:xsd:datadeliveryspc-1.0.0",
    "SPCNumber",
    _spc,
)
SPC_PUBLICATION = _Action(
    "SPCPublicationSearch",
    "SPCPublicationSearchRequest",
    "urn:ige:schema:xsd:datadeliveryspcpublication-1.0.0",
    None,
    _publication("spc"),
)


def _parse_xml(xml_bytes: bytes) -> ET.Element:
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ApiError(
            "Swiss IPI returned malformed XML", -1, xml_bytes[:500].decode(errors="replace")
        ) from exc


def _parse_meta(result: ET.Element) -> IpiSearchMeta:
    leaves = _leaves(result)

    def integer(name: str) -> int | None:
        value = _first(leaves, name)
        return int(value) if value and value.isdigit() else None

    cursor = None
    for node in result.iter():
        if _key(node.tag) == "continuation" and node.attrib.get("name") == "NextPage":
            cursor = (node.text or "").strip() or None
            break
    return IpiSearchMeta(
        total_item_count=integer("TotalItemCount"),
        item_count_offset=integer("ItemCountOffset"),
        item_count=integer("ItemCount"),
        next_cursor=cursor,
    )


def _payloads(result: ET.Element) -> list[ET.Element]:
    payloads: list[ET.Element] = []
    for data in result.iter():
        if _key(data.tag) not in {"data", "datalax", "dataany"}:
            continue
        for child in data:
            if _key(child.tag) == "wrapper":
                payloads.extend(
                    nested for nested in child if not nested.tag.startswith(f"{{{CORE_NS}}}")
                )
            elif child.tag.startswith(f"{{{CORE_NS}}}"):
                continue
            else:
                payloads.append(child)
    return payloads


def _check_result(result: ET.Element) -> None:
    leaves = _leaves(result)
    levels = [
        node.attrib.get("level", "").lower() for node in result.iter() if node.attrib.get("level")
    ]
    message = _first(leaves, "Message", "LogEntry", "ErrorMessage")
    failed = result.attrib.get("success", "true").lower() == "false"
    if failed or any(level in {"error", "critical"} for level in levels):
        raise ApiError(f"Swiss IPI API error: {message or 'request failed'}", -1, "")


class IpiSwissregClient(BaseAsyncClient):
    """Client for Swiss patent, trademark, SPC, and publication searches."""

    DEFAULT_BASE_URL = BASE_URL
    CACHE_NAME = "ipi_swissreg"

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        totp_token: str | None = None,
        base_url: str | None = None,
        token_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.username = username or os.getenv("IPI_DATA_USERNAME")
        self.password = password or os.getenv("IPI_DATA_PASSWORD")
        self.totp_token = totp_token or os.getenv("IPI_DATA_TOTP_TOKEN")
        if not self.username or not self.password:
            raise ConfigurationError(
                "Swiss IPI credentials required. Set IPI_DATA_USERNAME and IPI_DATA_PASSWORD. "
                f"Apply at {_SIGNUP_URL}."
            )
        resolved_base = (base_url or BASE_URL).rstrip("/")
        self.token_url = token_url or TOKEN_URL
        if client is None and (
            not resolved_base.startswith("https://") or not self.token_url.startswith("https://")
        ):
            raise ConfigurationError("Swiss IPI API and token URLs must use HTTPS")
        super().__init__(
            base_url=resolved_base,
            client=client,
            headers={"Accept": "application/xml"},
            timeout=60.0,
            use_cache=False,
        )
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at = 0.0

    async def _fetch_token(self, *, refresh: bool = False) -> str:
        if refresh and self._refresh_token:
            data = {
                "client_id": TOKEN_CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            }
        else:
            data = {
                "client_id": TOKEN_CLIENT_ID,
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            }
            if self.totp_token:
                data["totp"] = self.totp_token
        response = await self._client.post(self.token_url, data=data)
        if response.status_code == 429:
            raise self._rate_limit(response)
        if response.status_code in {400, 401, 403}:
            raise AuthenticationError("Swiss IPI authentication failed", response.status_code, None)
        if not response.is_success:
            raise ApiError(
                "Swiss IPI token endpoint failed", response.status_code, response.text[:500]
            )
        try:
            payload = response.json()
            access_token = payload["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise AuthenticationError("Swiss IPI token response lacks an access token") from exc
        self._access_token = str(access_token)
        refresh_value = payload.get("refresh_token")
        self._refresh_token = str(refresh_value) if refresh_value else self._refresh_token
        try:
            expires_in = float(payload.get("expires_in", 600))
        except (TypeError, ValueError):
            expires_in = 600
        self._token_expires_at = time.monotonic() + max(0, expires_in)
        return self._access_token

    async def _token(self) -> str:
        if self._access_token and time.monotonic() < self._token_expires_at - 30:
            return self._access_token
        return await self._fetch_token(refresh=bool(self._refresh_token))

    @staticmethod
    def _rate_limit(response: httpx.Response) -> RateLimitError:
        value = response.headers.get("Retry-After")
        try:
            retry_after = float(value) if value is not None else None
        except ValueError:
            retry_after = None
        return RateLimitError(
            "Swiss IPI rate limit exceeded",
            429,
            response.text[:500],
            retry_after=retry_after,
        )

    async def _post_xml(self, body: bytes) -> bytes:
        for attempt in range(2):
            token = await self._token()
            response = await self._client.post(
                self.base_url,
                content=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/xml",
                    "Content-Type": "application/xml",
                },
            )
            if response.status_code == 401 and attempt == 0:
                self._access_token = None
                self._refresh_token = None
                continue
            if response.status_code in {401, 403}:
                raise AuthenticationError(
                    "Swiss IPI API authentication failed", response.status_code, None
                )
            if response.status_code == 429:
                raise self._rate_limit(response)
            if not response.is_success:
                raise ApiError(
                    f"Swiss IPI HTTP {response.status_code}",
                    response.status_code,
                    response.text[:500],
                )
            return response.content
        raise AuthenticationError("Swiss IPI API authentication failed", 401, None)

    @staticmethod
    def _build_request(
        action: _Action[Any],
        *,
        query: str | None,
        limit: int,
        cursor: str | None,
        identifier: str | None = None,
    ) -> bytes:
        root = ET.Element(f"{{{CORE_NS}}}ApiRequest")
        if cursor:
            continuation = ET.SubElement(root, f"{{{CORE_NS}}}Continuation", {"name": "NextPage"})
            continuation.text = cursor
            return ET.tostring(root, encoding="utf-8", xml_declaration=True)
        action_node = ET.SubElement(root, f"{{{CORE_NS}}}Action", {"type": action.name})
        request = ET.SubElement(action_node, f"{{{action.namespace}}}{action.request_element}")
        ET.SubElement(request, f"{{{COMMON_NS}}}Representation", {"details": "Default"})
        ET.SubElement(request, f"{{{COMMON_NS}}}Page", {"size": str(limit)})
        query_node = ET.SubElement(request, f"{{{COMMON_NS}}}Query")
        if identifier and action.identifier_field:
            field = ET.SubElement(query_node, f"{{{action.namespace}}}{action.identifier_field}")
            field.text = identifier
        else:
            any_node = ET.SubElement(query_node, f"{{{COMMON_NS}}}Any")
            any_node.text = query
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    async def _search(
        self,
        action: _Action[RecordT],
        query: str,
        *,
        limit: int,
        cursor: str | None = None,
        identifier: str | None = None,
    ) -> tuple[list[RecordT], IpiSearchMeta]:
        query = query.strip()
        if not cursor and not query:
            raise ConfigurationError("Swiss IPI query must not be empty")
        page_size = max(1, min(limit, MAX_PAGE_SIZE))
        root = _parse_xml(
            await self._post_xml(
                self._build_request(
                    action,
                    query=query,
                    limit=page_size,
                    cursor=cursor,
                    identifier=identifier,
                )
            )
        )
        results = [node for node in root.iter() if _key(node.tag) == "result"]
        result = results[0] if results else root
        _check_result(result)
        rows = [action.parser(node) for node in _payloads(result)]
        return rows[:page_size], _parse_meta(result)

    async def _get(self, action: _Action[RecordT], number: str) -> RecordT:
        rows, _ = await self._search(action, number, limit=1, identifier=number.strip())
        if not rows:
            raise NotFoundError(f"Swiss IPI record not found: {number}", 404, "")
        return rows[0]

    async def search_patents(
        self, query: str, *, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[IpiPatentRecord], IpiSearchMeta]:
        return await self._search(PATENT, query, limit=limit, cursor=cursor)

    async def get_patent(self, number: str) -> IpiPatentRecord:
        return await self._get(PATENT, number)

    async def search_patent_publications(
        self, query: str, *, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[IpiPublicationRecord], IpiSearchMeta]:
        return await self._search(PATENT_PUBLICATION, query, limit=limit, cursor=cursor)

    async def search_trademarks(
        self, query: str, *, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[IpiTrademarkRecord], IpiSearchMeta]:
        return await self._search(TRADEMARK, query, limit=limit, cursor=cursor)

    async def get_trademark(self, number: str) -> IpiTrademarkRecord:
        return await self._get(TRADEMARK, number)

    async def search_spcs(
        self, query: str, *, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[IpiSpcRecord], IpiSearchMeta]:
        return await self._search(SPC, query, limit=limit, cursor=cursor)

    async def get_spc(self, number: str) -> IpiSpcRecord:
        return await self._get(SPC, number)

    async def search_spc_publications(
        self, query: str, *, limit: int = 25, cursor: str | None = None
    ) -> tuple[list[IpiPublicationRecord], IpiSearchMeta]:
        return await self._search(SPC_PUBLICATION, query, limit=limit, cursor=cursor)
