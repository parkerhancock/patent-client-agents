"""Async client for the New Zealand IPONZ v5 API.

The read-only contract follows IPONZ's public OpenAPI 3.0 definition and
published patent, trade mark, and design XSD bundles. Compatibility is tested
with schema-derived fixtures because no maintainer subscription is configured.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any, Literal, cast
from urllib.parse import quote

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
    IponzDesignRecord,
    IponzPatentRecord,
    IponzRegisterSummary,
    IponzTrademarkRecord,
    parse_iponz_date,
)

PRODUCTION_BASE_URL = "https://api.business.govt.nz/gateway/intellectual-property-office-nz/v5"
SANDBOX_BASE_URL = "https://api.business.govt.nz/sandbox/intellectual-property-office-nz/v5"
PORTAL_URL = "https://portal.api.business.govt.nz/api/iponz"
LIST_ACCEPT_CAP = 50
MAX_LIST_RESULTS = 2000

IponzEnvironment = Literal["production", "sandbox"]


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


def _raw(element: ET.Element) -> dict[str, Any]:
    return {_local(element.tag): _element_to_value(element)}


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
    result: list[str] = []
    for alias in aliases:
        result.extend(leaves.get(_key(alias), []))
    return list(dict.fromkeys(result))


def _find(element: ET.Element, name: str) -> ET.Element | None:
    wanted = _key(name)
    return next((node for node in element.iter() if _key(node.tag) == wanted), None)


def _party_names(element: ET.Element, container_name: str) -> list[str]:
    names: list[str] = []
    wanted = _key(container_name)
    for container in element.iter():
        if _key(container.tag) != wanted:
            continue
        for node in container.iter():
            if _key(node.tag) in {"organizationname", "freeformatnameline", "ownername"}:
                value = (node.text or "").strip()
                if value:
                    names.append(value)
        first_names = [
            (node.text or "").strip()
            for node in container.iter()
            if _key(node.tag) == "firstname" and (node.text or "").strip()
        ]
        last_names = [
            (node.text or "").strip()
            for node in container.iter()
            if _key(node.tag) == "lastname" and (node.text or "").strip()
        ]
        names.extend(" ".join(parts) for parts in zip(first_names, last_names, strict=False))
    return list(dict.fromkeys(names))


def _parse_xml(content: bytes) -> ET.Element:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ApiError(
            "IPONZ returned malformed XML", -1, content[:500].decode(errors="replace")
        ) from exc
    error = _find(root, "TransactionError")
    if error is not None:
        leaves = _leaves(error)
        code = _first(leaves, "TransactionErrorCode")
        text = _first(leaves, "TransactionErrorText") or "request failed"
        raise ApiError(f"IPONZ transaction error {code or 'unknown'}: {text}", -1, "")
    return root


def _parse_patent(root: ET.Element) -> IponzPatentRecord:
    record = _find(root, "PatentInformation")
    if record is None:
        record = root
    leaves = _leaves(record)
    number = _first(leaves, "PatentNumber")
    if not number:
        raise ApiError("IPONZ patent XML lacks PatentNumber", -1, "")
    return IponzPatentRecord(
        identifier=number,
        patent_number=number,
        international_application_number=_first(leaves, "InternationalApplicationNumber"),
        wipo_publication_number=_first(leaves, "WIPOPublicationNumber"),
        title=_first(leaves, "PatentTitle"),
        abstract=_first(leaves, "PatentAbstract"),
        status=_first(leaves, "PatentCurrentStatusCode"),
        complete_filed_date=parse_iponz_date(_first(leaves, "CompleteFiledDate")),
        national_phase_entry_date=parse_iponz_date(_first(leaves, "NationalPhaseEntryDate")),
        published_date=parse_iponz_date(_first(leaves, "PublishedDate")),
        grant_date=parse_iponz_date(_first(leaves, "GrantDate")),
        expiry_date=parse_iponz_date(_first(leaves, "ExpiryDate")),
        applicants=_party_names(record, "ApplicantDetails"),
        inventors=_party_names(record, "InventorDetails"),
        classifications=_many(leaves, "ClassDescription", "ClassificationCode", "Symbol"),
        raw=_raw(record),
    )


def _parse_trademark(root: ET.Element) -> IponzTrademarkRecord:
    record = _find(root, "TradeMarkInformation")
    if record is None:
        record = root
    leaves = _leaves(record)
    application_number = _first(leaves, "ApplicationNumber")
    if not application_number:
        raise ApiError("IPONZ trade mark XML lacks ApplicationNumber", -1, "")
    registration_number = _first(leaves, "RegistrationNumber")
    return IponzTrademarkRecord(
        identifier=registration_number or application_number,
        application_number=application_number,
        registration_number=registration_number,
        international_registration_number=_first(leaves, "InternationalRegistrationNumber"),
        title=_first(leaves, "MarkTitle"),
        status=_first(leaves, "MarkCurrentStatusCode"),
        application_date=parse_iponz_date(_first(leaves, "ApplicationDate")),
        registration_date=parse_iponz_date(_first(leaves, "RegistrationDate")),
        expiry_date=parse_iponz_date(_first(leaves, "ExpiryDate")),
        applicants=_party_names(record, "ApplicantDetails"),
        nice_classes=_many(leaves, "ClassNumber"),
        word_marks=_many(leaves, "MarkVerbalElementText"),
        raw=_raw(record),
    )


def _parse_design(root: ET.Element) -> IponzDesignRecord:
    record = _find(root, "DesignInformation")
    if record is None:
        record = root
    leaves = _leaves(record)
    registration_number = _first(leaves, "RegistrationNumber")
    if not registration_number:
        raise ApiError("IPONZ design XML lacks RegistrationNumber", -1, "")
    return IponzDesignRecord(
        identifier=registration_number,
        registration_number=registration_number,
        design_identifier=_first(leaves, "DesignIdentifier"),
        title=_first(leaves, "DesignTitle"),
        novelty_statement=_first(leaves, "NoveltyStatement"),
        status=_first(leaves, "DesignCurrentStatusCode"),
        application_date=parse_iponz_date(_first(leaves, "ApplicationDate")),
        registration_date=parse_iponz_date(_first(leaves, "RegistrationDate")),
        expiry_date=parse_iponz_date(_first(leaves, "ExpiryDate")),
        applicants=_party_names(record, "ApplicantDetails"),
        articles=_many(leaves, "ArticleTitle"),
        raw=_raw(record),
    )


def _parse_summaries(
    root: ET.Element, right_type: Literal["patent", "trademark", "design"]
) -> list[IponzRegisterSummary]:
    tags = {"patent": "Patent", "trademark": "TradeMark", "design": "Design"}
    identifiers = {
        "patent": "PatentNumber",
        "trademark": "ApplicationNumber",
        "design": "RegistrationNumber",
    }
    statuses = {
        "patent": "PatentCurrentStatusCode",
        "trademark": "MarkCurrentStatusCode",
        "design": "DesignCurrentStatusCode",
    }
    dates = {"patent": "FilingDate", "trademark": "FilingDate", "design": "RegistrationDate"}
    rows: list[IponzRegisterSummary] = []
    for node in root.iter():
        if _key(node.tag) != _key(tags[right_type]):
            continue
        leaves = _leaves(node)
        identifier = _first(leaves, identifiers[right_type])
        if identifier:
            rows.append(
                IponzRegisterSummary(
                    identifier=identifier,
                    right_type=right_type,
                    status=_first(leaves, statuses[right_type]),
                    event_date=parse_iponz_date(_first(leaves, dates[right_type])),
                    raw=_raw(node),
                )
            )
    return rows


def _date_range(start: date, end: date) -> str:
    if start < date(2010, 1, 1):
        raise ConfigurationError("IPONZ date ranges cannot start before 2010-01-01")
    if end < start:
        raise ConfigurationError("IPONZ date range end must be on or after its start")
    try:
        anniversary = start.replace(year=start.year + 1)
    except ValueError:
        anniversary = start.replace(year=start.year + 1, day=28)
    if end >= anniversary:
        raise ConfigurationError("IPONZ date ranges must be shorter than one year")
    return f"{start:%Y%m%d}-{end:%Y%m%d}"


def _identifier(value: str, *, numeric: bool) -> str:
    resolved = value.strip()
    if not resolved:
        raise ConfigurationError("IPONZ register number must not be empty")
    if numeric and not resolved.isdigit():
        raise ConfigurationError("IPONZ patent and trade mark numbers must contain only digits")
    return quote(resolved, safe="")


class IponzClient(BaseAsyncClient):
    """Read-only client for public IPONZ patent, trade mark, and design data."""

    DEFAULT_BASE_URL = PRODUCTION_BASE_URL
    CACHE_NAME = "iponz_new_zealand"

    def __init__(
        self,
        subscription_key: str | None = None,
        *,
        access_token: str | None = None,
        environment: IponzEnvironment | None = None,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        resolved_key = subscription_key or os.getenv("IPONZ_SUBSCRIPTION_KEY")
        if not resolved_key:
            raise ConfigurationError(
                "IPONZ subscription key required. Set IPONZ_SUBSCRIPTION_KEY. "
                f"Subscribe at {PORTAL_URL}."
            )
        env_raw = environment or os.getenv("IPONZ_ENV", "production")
        if env_raw not in {"production", "sandbox"}:
            raise ConfigurationError(
                f"IPONZ_ENV must be 'production' or 'sandbox', got {env_raw!r}"
            )
        self.environment = cast("IponzEnvironment", env_raw)
        resolved_base = base_url or (
            SANDBOX_BASE_URL if self.environment == "sandbox" else PRODUCTION_BASE_URL
        )
        if client is None and not resolved_base.startswith("https://"):
            raise ConfigurationError("IPONZ API URL must use HTTPS")
        headers = {
            "Accept": "application/xml, text/xml, application/soap+xml",
            "Ocp-Apim-Subscription-Key": resolved_key,
            "User-Agent": "patent-client-agents-iponz/0.1",
        }
        token = access_token or os.getenv("IPONZ_ACCESS_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        super().__init__(
            base_url=resolved_base.rstrip("/"),
            client=client,
            headers=headers,
            timeout=60.0,
            use_cache=False,
        )

    @staticmethod
    def _rate_limit(response: httpx.Response) -> RateLimitError:
        value = response.headers.get("Retry-After")
        try:
            retry_after = float(value) if value is not None else None
        except ValueError:
            retry_after = None
        return RateLimitError(
            "IPONZ rate limit exceeded",
            429,
            response.text[:500],
            retry_after=retry_after,
        )

    async def _get_xml(self, path: str) -> ET.Element:
        response = await self._client.get(f"{self.base_url}{path}")
        if response.status_code in {401, 403}:
            raise AuthenticationError("IPONZ authentication failed", response.status_code, None)
        if response.status_code == 404:
            raise NotFoundError("IPONZ record not found", 404, response.text[:500])
        if response.status_code == 429:
            raise self._rate_limit(response)
        if not response.is_success:
            raise ApiError(
                f"IPONZ HTTP {response.status_code}", response.status_code, response.text[:500]
            )
        return _parse_xml(response.content)

    async def get_patent(self, patent_number: str) -> IponzPatentRecord:
        number = _identifier(patent_number, numeric=True)
        return _parse_patent(await self._get_xml(f"/patent/{number}"))

    async def list_patents_updated(self, start: date, end: date) -> list[IponzRegisterSummary]:
        value = _date_range(start, end)
        return _parse_summaries(await self._get_xml(f"/patents/updated/{value}"), "patent")

    async def get_trademark(self, trademark_number: str) -> IponzTrademarkRecord:
        number = _identifier(trademark_number, numeric=True)
        return _parse_trademark(await self._get_xml(f"/trademarks/{number}"))

    async def list_trademarks_updated(self, start: date, end: date) -> list[IponzRegisterSummary]:
        value = _date_range(start, end)
        return _parse_summaries(await self._get_xml(f"/trademarks/updated/{value}"), "trademark")

    async def get_design(self, design_number: str) -> IponzDesignRecord:
        number = _identifier(design_number, numeric=False)
        return _parse_design(await self._get_xml(f"/design/{number}"))

    async def list_designs_updated(self, start: date, end: date) -> list[IponzRegisterSummary]:
        value = _date_range(start, end)
        return _parse_summaries(await self._get_xml(f"/designs/updated/{value}"), "design")

    async def list_designs_registered(self, start: date, end: date) -> list[IponzRegisterSummary]:
        value = _date_range(start, end)
        return _parse_summaries(await self._get_xml(f"/designs/registered/{value}"), "design")
