"""Async DPMAconnectPlus client.

Compatibility is tested only with synthetic, namespace-bearing XML fixtures.
No maintainer has validated this parser against an authenticated account yet.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, TypeVar
from urllib.parse import quote

import httpx

from mcp_data_core.base_client import BaseAsyncClient
from mcp_data_core.exceptions import ApiError, ConfigurationError, RateLimitError

from .models import DesignRecord, PatentUtilityRecord, TrademarkRecord, parse_dpma_date

BASE_URL = "https://dpmaconnect.dpma.de/dpmaws/rest-services"
PATENT_SERVICE = "DPMAregisterPatService"
TRADEMARK_SERVICE = "DPMAregisterMarkeService"
DESIGN_SERVICE = "DPMAregisterGsmService"
LIST_ACCEPT_CAP = 50
ACCOUNT_RESULT_CAP = 1000
TEST_RESULT_CAP = 100
_SIGNUP_URL = "https://www.dpma.de/english/search/data_supply_services/dpmaconnect/index.html"

RecordT = TypeVar("RecordT", PatentUtilityRecord, TrademarkRecord, DesignRecord)


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
        text = (node.text or "").strip()
        if text:
            result.setdefault(_key(node.tag), []).append(text)
    return result


def _first(leaves: dict[str, list[str]], *aliases: str) -> str | None:
    for alias in aliases:
        values = leaves.get(_key(alias))
        if values:
            return values[0]
    return None


def _record_elements(root: ET.Element, kind: str) -> list[ET.Element]:
    expected = {
        "patent": {"patenthit", "patentrecord", "patentdocument"},
        "trademark": {"trademarkhit", "markehit", "trademarkrecord", "markerecord"},
        "design": {"designhit", "gsmhit", "designrecord", "gsmrecord"},
    }[kind]
    matches = [node for node in root.iter() if _key(node.tag) in expected]
    return matches or [root]


def _parse_error(root: ET.Element) -> None:
    root_name = _key(root.tag)
    leaves = _leaves(root)
    code = _first(leaves, "errorCode", "code", "faultCode")
    message = _first(leaves, "errorMessage", "message", "faultString")
    if "error" in root_name or "fault" in root_name or code:
        raise ApiError(
            f"DPMAconnectPlus error {code or 'unknown'}: {message or 'unknown error'}", -1, ""
        )


def _parse_xml(xml_bytes: bytes) -> ET.Element:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ApiError(
            "DPMAconnectPlus returned malformed XML", -1, xml_bytes[:500].decode(errors="replace")
        ) from exc
    _parse_error(root)
    return root


def _patent(element: ET.Element) -> PatentUtilityRecord:
    leaves = _leaves(element)
    raw = {_local(element.tag): _element_to_value(element)}
    identifier = _first(
        leaves, "leading-registered-number", "application-number", "document-number"
    )
    if not identifier:
        raise ApiError("DPMA patent XML lacks an identifier", -1, "")
    kind = _first(leaves, "kind-code", "right-type")
    right_type = "utility_model" if kind and kind.upper().startswith("U") else "patent"
    return PatentUtilityRecord(
        identifier=identifier,
        application_number=_first(leaves, "application-number", "leading-registered-number"),
        publication_number=_first(leaves, "publication-number", "document-number"),
        registration_number=_first(leaves, "registration-number", "registered-number"),
        title=_first(leaves, "invention-title", "title"),
        status=_first(leaves, "status", "legal-status"),
        application_date=parse_dpma_date(_first(leaves, "application-date", "filing-date")),
        publication_date=parse_dpma_date(_first(leaves, "publication-date")),
        registration_date=parse_dpma_date(_first(leaves, "registration-date")),
        owner=_first(leaves, "applicant", "owner", "proprietor"),
        classification=_first(leaves, "ipc", "classification"),
        right_type=right_type,
        inventors=leaves.get(_key("inventor"), []),
        raw=raw,
    )


def _trademark(element: ET.Element) -> TrademarkRecord:
    leaves = _leaves(element)
    raw = {_local(element.tag): _element_to_value(element)}
    identifier = _first(leaves, "ApplicationNumber", "registration-number", "mark-number")
    if not identifier:
        raise ApiError("DPMA trademark XML lacks an identifier", -1, "")
    return TrademarkRecord(
        identifier=identifier,
        application_number=_first(leaves, "ApplicationNumber"),
        registration_number=_first(leaves, "RegistrationNumber"),
        mark_text=_first(leaves, "MarkText", "WordMark", "Title"),
        status=_first(leaves, "Status", "MarkStatus"),
        application_date=parse_dpma_date(_first(leaves, "ApplicationDate", "FilingDate")),
        registration_date=parse_dpma_date(_first(leaves, "RegistrationDate")),
        owner=_first(leaves, "Applicant", "Owner", "Proprietor"),
        nice_classification=_first(leaves, "NiceClassification", "NiceClass"),
        vienna_classification=_first(leaves, "ViennaClassification", "ViennaCode"),
        raw=raw,
    )


def _design(element: ET.Element) -> DesignRecord:
    leaves = _leaves(element)
    raw = {_local(element.tag): _element_to_value(element)}
    identifier = _first(leaves, "DesignIdentifier", "DesignNumber", "RegistrationNumber")
    if not identifier:
        raise ApiError("DPMA design XML lacks an identifier", -1, "")
    return DesignRecord(
        identifier=identifier,
        design_number=_first(leaves, "DesignIdentifier", "DesignNumber"),
        application_number=_first(leaves, "ApplicationNumber"),
        registration_number=_first(leaves, "RegistrationNumber"),
        product_indication=_first(leaves, "ProductIndication", "Title"),
        status=_first(leaves, "Status", "DesignStatus"),
        application_date=parse_dpma_date(_first(leaves, "ApplicationDate", "FilingDate")),
        registration_date=parse_dpma_date(_first(leaves, "RegistrationDate")),
        owner=_first(leaves, "Applicant", "Owner", "Proprietor"),
        locarno_classification=_first(leaves, "LocarnoClassification", "LocarnoClass"),
        raw=raw,
    )


class DpmaRegisterClient(BaseAsyncClient):
    """Client for DPMA patent, trademark, and design register services."""

    DEFAULT_BASE_URL = BASE_URL
    CACHE_NAME = "dpma_register"

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        resolved_username = username or os.getenv("DPMA_CONNECTPLUS_USERNAME")
        resolved_password = password or os.getenv("DPMA_CONNECTPLUS_PASSWORD")
        if not resolved_username or not resolved_password:
            raise ConfigurationError(
                "DPMAconnectPlus credentials required. Set DPMA_CONNECTPLUS_USERNAME and "
                f"DPMA_CONNECTPLUS_PASSWORD. Apply at {_SIGNUP_URL}."
            )
        resolved_base = (base_url or BASE_URL).rstrip("/")
        if client is None and not resolved_base.startswith("https://"):
            raise ConfigurationError("DPMAconnectPlus requires an HTTPS base URL")
        auth = httpx.BasicAuth(resolved_username, resolved_password)
        super().__init__(
            base_url=resolved_base,
            client=client,
            auth=auth,
            headers={"Accept": "application/xml"},
            timeout=30.0,
            use_cache=True,
        )
        if client is not None:
            client.auth = auth

    async def _get_xml(self, service: str, operation: str, value: str) -> bytes:
        url = f"{self.base_url}/{service}/{operation}/{quote(value, safe='')}"
        response = await self._client.get(url)
        if response.status_code == 429:
            raise RateLimitError("DPMAconnectPlus rate limit exceeded", 429, response.text[:500])
        if not response.is_success:
            raise ApiError(
                f"DPMAconnectPlus HTTP {response.status_code}",
                response.status_code,
                response.text[:500],
            )
        return response.content

    async def _search(
        self, service: str, query: str, kind: str, limit: int
    ) -> tuple[list[Any], int | None]:
        query = query.strip()
        if not query or len(query) > 2000:
            raise ConfigurationError("DPMA expert query must contain 1 to 2000 characters")
        root = _parse_xml(await self._get_xml(service, "search", query))
        parsers = {"patent": _patent, "trademark": _trademark, "design": _design}
        rows = [parsers[kind](node) for node in _record_elements(root, kind)]
        total_text = _first(_leaves(root), "hitCount", "totalCount", "numberOfHits")
        total = int(total_text) if total_text and total_text.isdigit() else None
        return rows[: max(1, min(limit, ACCOUNT_RESULT_CAP))], total

    async def search_patents(
        self, expert_query: str, *, limit: int = 25
    ) -> tuple[list[PatentUtilityRecord], int | None]:
        return await self._search(PATENT_SERVICE, expert_query, "patent", limit)  # type: ignore[return-value]

    async def get_patent(self, number: str) -> PatentUtilityRecord:
        root = _parse_xml(await self._get_xml(PATENT_SERVICE, "getRegisterInfo", number))
        return _patent(_record_elements(root, "patent")[0])

    async def search_trademarks(
        self, expert_query: str, *, limit: int = 25
    ) -> tuple[list[TrademarkRecord], int | None]:
        return await self._search(TRADEMARK_SERVICE, expert_query, "trademark", limit)  # type: ignore[return-value]

    async def get_trademark(self, number: str) -> TrademarkRecord:
        root = _parse_xml(await self._get_xml(TRADEMARK_SERVICE, "getRegisterInfo", number))
        return _trademark(_record_elements(root, "trademark")[0])

    async def search_designs(
        self, expert_query: str, *, limit: int = 25
    ) -> tuple[list[DesignRecord], int | None]:
        return await self._search(DESIGN_SERVICE, expert_query, "design", limit)  # type: ignore[return-value]

    async def get_design(self, number: str) -> DesignRecord:
        root = _parse_xml(await self._get_xml(DESIGN_SERVICE, "getRegisterInfo", number))
        return _design(_record_elements(root, "design")[0])
