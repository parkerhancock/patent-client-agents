from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from typing import Any

import httpx

from mcp_data_core import BaseAsyncClient
from mcp_data_core.exceptions import AuthenticationError

from .models import (
    DataWebReport,
    DownloadedAttachment,
    EdisAttachment,
    EdisDocument,
    EdisInvestigation,
    HtsExportResponse,
    HtsSearchResult,
    IdsInvestigation,
    SavedQuerySummary,
)
from .transformers import (
    build_downloaded_attachment,
    parse_attachments,
    parse_dataweb_report,
    parse_documents,
    parse_hts_export,
    parse_hts_search,
    parse_ids_investigations,
    parse_investigations,
    parse_saved_queries,
)
from .utils import (
    get_env_token,
    normalize_params,
)


def _decode_jwt_exp(token: str) -> datetime | None:
    """Best-effort decode of a JWT's ``exp`` claim to a UTC datetime.

    Returns None for non-JWTs, malformed payloads, or tokens with no ``exp``.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        exp = claims.get("exp")
        if exp is None:
            return None
        return datetime.fromtimestamp(int(exp), tz=UTC)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


class EdisClient(BaseAsyncClient):
    DEFAULT_BASE_URL = os.getenv("USITC_EDIS_BASE_URL", "https://edis.usitc.gov/data")
    CACHE_NAME = "usitc_edis"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        token = get_env_token("USITC_EDIS_TOKEN")
        # Don't set a custom User-Agent here. edis.usitc.gov is fronted
        # by Akamai bot-management which 403s anything that looks like
        # a browser-impersonator OR an unrecognized custom UA (we tried
        # ``law-tools-edis/1.0`` per issue #16 and that 403d too).
        # The native ``python-httpx/x.y.z`` UA — paired with httpx's
        # TLS fingerprint — is allowed as a known programmatic
        # consumer. PCA v0.6.6+ no longer sets a default UA in the
        # cache layer, so omitting it here lets httpx's native UA
        # come through.
        headers: dict[str, str] = {"Accept": "application/xml"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._token = token
        self._token_expires_at: datetime | None = _decode_jwt_exp(token) if token else None
        super().__init__(headers=headers, client=client)

    def require_auth(self) -> None:
        if not self._token:
            raise RuntimeError(
                "USITC_EDIS_TOKEN is required for this operation. "
                "Generate a token at https://edis.usitc.gov → API Token Generator."
            )

    def _assert_token_fresh(self) -> None:
        # EDIS surfaces expired bearer tokens as Akamai 503/403 with HTML
        # bodies (no clean 401), so pre-check the JWT exp claim to fail
        # fast with an actionable message instead of letting the caller
        # chase phantom infra issues.
        if self._token_expires_at is None:
            return
        if datetime.now(UTC) >= self._token_expires_at:
            raise AuthenticationError(
                f"USITC_EDIS_TOKEN expired at "
                f"{self._token_expires_at.isoformat()}. Mint a new token at "
                f"https://edis.usitc.gov → profile → API Token Generator "
                f"and update USITC_EDIS_TOKEN."
            )

    async def _request(self, *args: Any, **kwargs: Any) -> httpx.Response:
        self._assert_token_fresh()
        return await super()._request(*args, **kwargs)

    async def list_investigations(
        self,
        investigation_number: str | None = None,
        investigation_phase: str | None = None,
        **filters: Any,
    ) -> list[EdisInvestigation]:
        # EDIS uses investigation_number and phase as path segments, not query params
        path = "/investigation"
        if investigation_number:
            path = f"/investigation/{investigation_number}"
            if investigation_phase:
                path = f"/investigation/{investigation_number}/{investigation_phase}"
                # Remove from query params since it's in the path
                filters.pop("investigationPhase", None)
        response = await self._request("GET", path, params=normalize_params(filters))
        return parse_investigations(response.text)

    async def list_documents(self, **filters: Any) -> list[EdisDocument]:
        response = await self._request("GET", "/document", params=normalize_params(filters))
        return parse_documents(response.text)

    async def list_attachments(self, document_id: int) -> list[EdisAttachment]:
        response = await self._request("GET", f"/attachment/{document_id}")
        return parse_attachments(response.text)

    async def download_attachment(
        self,
        document_id: int,
        attachment_id: int,
    ) -> DownloadedAttachment:
        self.require_auth()
        response = await self._request(
            "GET",
            f"/download/{document_id}/{attachment_id}",
            headers={"Accept": "*/*"},
        )
        filename = response.headers.get("Content-Disposition")
        content_type = response.headers.get("Content-Type")
        return build_downloaded_attachment(
            document_id=document_id,
            attachment_id=attachment_id,
            filename=filename,
            content=response.content,
            content_type=content_type,
        )


def build_dataweb_query(
    trade_type: str = "Import",
    classification: str = "HTS",
    years: list[str] | None = None,
    timeline: str = "Annual",
    data_metrics: list[str] | None = None,
    scale: str = "1",
    commodities: list[str] | None = None,
    granularity: str = "2",
    countries: list[dict[str, str]] | None = None,
    aggregate_countries: bool = True,
    aggregate_commodities: bool = True,
    max_rows: str = "20000",
) -> dict[str, Any]:
    """Build a complete DataWeb query object from simple parameters.

    The DataWeb API requires a deeply-nested query structure. This helper
    builds it from user-friendly parameters.

    Args:
        trade_type: Import, Export, GenImp, TotExp, Balance, ForeignExp, ImpExp
        classification: HTS, SITC, NAIC, SIC, QUICK, EXPERT
        years: List of year strings, e.g. ["2023", "2024"]. Defaults to current year.
        timeline: "Annual" or "Monthly"
        data_metrics: List of metrics. Defaults to ["CONS_CUSTOMS_VALUE"].
            Common: CONS_CUSTOMS_VALUE, CONS_FIR_UNIT_QUANT, CONS_QUANTITY_2
        scale: "1" (actual), "1000" (thousands), "1000000" (millions)
        commodities: List of commodity codes to filter. None = all.
        granularity: HTS digit level: "2", "4", "6", "8", "10"
        countries: List of {"name": ..., "value": ...} dicts. None = all.
        aggregate_countries: If True, aggregate all countries together.
        aggregate_commodities: If True, aggregate all commodities together.
        max_rows: Maximum result rows.
    """
    if years is None:
        years = ["2024"]
    if data_metrics is None:
        data_metrics = ["CONS_CUSTOMS_VALUE"]

    # Countries section
    if countries:
        countries_section: dict[str, Any] = {
            "aggregation": "Aggregate Countries" if aggregate_countries else "Break Out Countries",
            "countriesSelectType": "selected",
            "countries": countries,
            "countriesExpanded": countries,
            "countryGroups": {"systemGroups": [], "userGroups": []},
        }
    else:
        countries_section = {
            "aggregation": "Aggregate Countries" if aggregate_countries else "Break Out Countries",
            "countriesSelectType": "all",
            "countries": [],
            "countriesExpanded": [{"name": "All Countries", "value": "all"}],
            "countryGroups": {"systemGroups": [], "userGroups": []},
        }

    # Commodities section
    if commodities:
        commodities_section: dict[str, Any] = {
            "aggregation": (
                "Aggregate Commodities" if aggregate_commodities else "Break Out Commodities"
            ),
            "commoditySelectType": "manual",
            "commodities": [],
            "commoditiesExpanded": [],
            "commoditiesManual": ",".join(commodities),
            "commodityGroups": {"systemGroups": [], "userGroups": []},
            "granularity": granularity,
            "codeDisplayFormat": "YES",
            "groupGranularity": None,
            "searchGranularity": None,
        }
    else:
        commodities_section = {
            "aggregation": (
                "Aggregate Commodities" if aggregate_commodities else "Break Out Commodities"
            ),
            "commoditySelectType": "all",
            "commodities": [],
            "commoditiesExpanded": [],
            "commoditiesManual": "",
            "commodityGroups": {"systemGroups": [], "userGroups": []},
            "granularity": granularity,
            "codeDisplayFormat": "YES",
            "groupGranularity": None,
            "searchGranularity": None,
        }

    return {
        "savedQueryName": "",
        "savedQueryDesc": "",
        "isOwner": True,
        "runMonthly": False,
        "reportOptions": {
            "tradeType": trade_type,
            "classificationSystem": classification,
        },
        "searchOptions": {
            "countries": countries_section,
            "commodities": commodities_section,
            "componentSettings": {
                "timeframeSelectType": "fullYears",
                "years": years,
                "yearsTimeline": timeline,
                "dataToReport": data_metrics,
                "scale": scale,
                "startDate": None,
                "endDate": None,
                "startMonth": None,
                "endMonth": None,
            },
            "MiscGroup": {
                "districts": {
                    "aggregation": "Aggregate District",
                    "districtGroups": {"userGroups": []},
                    "districts": [],
                    "districtsExpanded": [{"name": "All Districts", "value": "all"}],
                    "districtsSelectType": "all",
                },
                "importPrograms": {
                    "aggregation": None,
                    "importPrograms": [],
                    "programsSelectType": "all",
                },
                "extImportPrograms": {
                    "aggregation": "Aggregate CSC",
                    "extImportPrograms": [],
                    "extImportProgramsExpanded": [],
                    "programsSelectType": "all",
                },
                "provisionCodes": {
                    "aggregation": "Aggregate RPCODE",
                    "provisionCodesSelectType": "all",
                    "rateProvisionCodes": [],
                    "rateProvisionCodesExpanded": [],
                },
            },
        },
        "sortingAndDataFormat": {
            "DataSort": {"columnOrder": [], "fullColumnOrder": [], "sortOrder": []},
            "reportCustomizations": {
                "exportCombineTables": False,
                "showAllSubtotal": True,
                "subtotalRecords": "",
                "totalRecords": max_rows,
                "exportRawData": False,
            },
        },
    }


class DataWebClient(BaseAsyncClient):
    DEFAULT_BASE_URL = os.getenv("USITC_DATAWEB_BASE_URL", "https://datawebws.usitc.gov/dataweb")
    CACHE_NAME = "usitc_dataweb"
    DEFAULT_TIMEOUT = 60.0

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        token = get_env_token("USITC_DATAWEB_TOKEN")
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._token = token
        super().__init__(headers=headers, client=client)

    def require_auth(self) -> None:
        if not self._token:
            raise RuntimeError("USITC_DATAWEB_TOKEN is required to call DataWeb endpoints.")

    async def run_report(self, query: dict[str, Any]) -> DataWebReport:
        self.require_auth()
        response = await self._request("POST", "/api/v2/report2/runReport", json=query)
        return parse_dataweb_report(response.json())

    async def get_all_countries(self) -> list[dict[str, Any]]:
        self.require_auth()
        payload = await self._request_json("GET", "/api/v2/country/getAllCountries")
        return payload.get("options", []) if isinstance(payload, dict) else []

    async def get_global_vars(self) -> dict[str, Any]:
        self.require_auth()
        payload = await self._request_json("GET", "/api/v2/query/getGlobalVars")
        return payload if isinstance(payload, dict) else {}

    async def list_saved_queries(self) -> list[SavedQuerySummary]:
        self.require_auth()
        payload = await self._request_json("GET", "/api/v2/savedQuery/getAllSavedQueries")
        if not isinstance(payload, list):
            return []
        return parse_saved_queries(payload)


class IdsClient(BaseAsyncClient):
    DEFAULT_BASE_URL = os.getenv("USITC_IDS_BASE_URL", "https://ids.usitc.gov")
    CACHE_NAME = "usitc_ids"
    DEFAULT_TIMEOUT = 10.0

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client=client)

    async def list_investigations(self) -> list[IdsInvestigation]:
        payload = await self._request_json("GET", "/investigations.json")
        return parse_ids_investigations(payload)


class HtsClient(BaseAsyncClient):
    DEFAULT_BASE_URL = os.getenv("USITC_HTS_BASE_URL", "https://hts.usitc.gov/reststop")
    CACHE_NAME = "usitc_hts"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        headers: dict[str, str] = {"Accept": "application/json"}
        super().__init__(headers=headers, client=client)

    async def search(self, keyword: str) -> list[HtsSearchResult]:
        payload = await self._request_json("GET", "/search", params={"keyword": keyword})
        return parse_hts_search(payload)

    async def export_range(
        self,
        from_code: str,
        to_code: str,
        format_: str = "JSON",
        styles: bool = True,
    ) -> HtsExportResponse:
        payload = await self._request_json(
            "GET",
            "/exportList",
            params={
                "from": from_code,
                "to": to_code,
                "format": format_,
                "styles": str(styles).lower(),
            },
        )
        if isinstance(payload, list):
            return parse_hts_export(payload)
        entries = payload.get("entries") if isinstance(payload, dict) else []
        return parse_hts_export(entries or [])
