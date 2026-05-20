"""Async client for the PRH (Finland) public JSON APIs.

Three hosts, one client. All endpoints are unauthenticated.

* ``patenttitietopalvelu.prh.fi/nis-api-gateway-pat/`` —
  patent / UM / SPC / EP-FI corpus search + per-record GET.
* ``tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/`` —
  national trademarks + well-known trademarks register (TMR).
* ``mallioikeustietopalvelu.prh.fi/nis-api-gateway/`` —
  national designs.

The patent search payload is a 30-field form-state body (decoded from
the React bundle 2026-05-18). Three list-valued slots —
``dossierStatus``, ``patentTypes``, ``publicationTypes`` — act as
**inclusion** filters: empty list returns zero hits, full default
list returns everything. The constants live in :data:`DEFAULT_PATENT_STATUSES`,
:data:`DEFAULT_PATENT_TYPES`, and :data:`DEFAULT_PUBLICATION_TYPES`.

TM and design searches use simpler bodies with scalar string fields
(empty body returns the full corpus, capped server-side at 3,000 rows).

Production callers should send a courtesy registration to
``avoindata@prh.fi``; Finland implements the EU Open Data Directive
(2019/1024) and the sister business-register service is explicit
CC-BY 4.0 — but no public ToS covers the IP search APIs directly.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from law_tools_core import BaseAsyncClient

from .models import (
    DossierSearchResponse,
    PatentGetRecord,
    PatentSearchResponse,
)

PATENT_HOST: str = "https://patenttitietopalvelu.prh.fi"
TRADEMARK_HOST: str = "https://tavaramerkkitietopalvelu.prh.fi"
DESIGN_HOST: str = "https://mallioikeustietopalvelu.prh.fi"

PATENT_PATH: str = "/nis-api-gateway-pat/patent"
TRADEMARK_PATH: str = "/nis-api-gateway/trademark"
TMR_PATH: str = "/nis-api-gateway/tmr"
DESIGN_PATH: str = "/nis-api-gateway/design"

DEFAULT_USER_AGENT: str = (
    "patent-client-agents/0 (+https://patentclient.com; contact avoindata@prh.fi)"
)

# Server-side row cap on every search endpoint — narrower queries
# required for high-population applicants.
SERVER_RESULT_CAP: int = 3000

# Inclusion-filter defaults decoded from the patent SPA bundle
# (constants ``In``, ``Mn``, ``Ln`` in main.05f306a4.js, 2026-05-18).
# Empty arrays return zero hits — these are inclusion lists.
DEFAULT_PATENT_TYPES: list[str] = [
    "PatentDossier",
    "PatentDossierUtilityModel",
    "PatentEurope",
    "Spc",
]

DEFAULT_PATENT_STATUSES: list[str] = [
    "Application_refused",
    "Application_dismissed",
    "Expired",
    "Renounced",
    "Annulled",
    "Opposition",
    "UMopposition",
    "Appeal",
    "Patent_revoked",
    "Application_withdrawn",
    "Application_filed",
    "Valid",
    "Limited",
    "Approved",
    "Basic_patent_has_lapsed",
    "EP_660_notvalidated",
    "EP_630_oppo_B2",
    "EP_620_grant_B1",
    "EP_632_limit_B3",
    "EP_700_applrefused",
    "EP_800_application_dismissed",
    "EP_600_imported",
    "EP_640_revoked",
    "EP_631_oppo_T4",
    "EP_635_limit_T6",
    "EP_650_appwthdr",
    "EP_621_valid_T3",
    "EP_625_opposition",
    "Lapsed",
    "Revoked",
    "Refused",
    "Reinstated",
    "Withdrawn",
    "Granted",
    "Application_pending",
    "Pending",
]

DEFAULT_PUBLICATION_TYPES: list[str] = [
    "UM_Revoked",
    "UM_Notification",
    "UM_Granted_Y1",
    "UM_Corrected_Y8",
    "UM_AvailableToPublic_U1",
    "UM_AnnulledPartial_Z1",
    "PT_Transferred",
    "PT_SPCWithdrawn",
    "PT_SPCRefused",
    "PT_SPCLapsed",
    "PT_SPCGranted_Certificate",
    "PT_SPCFiled",
    "PT_SPCDismissed",
    "PT_SPCContinuationGranted",
    "PT_SPCContinuationFiled",
    "PT_Revoked",
    "PT_Reinstated",
    "PT_Refused",
    "PT_OppositionAmended_B2",
    "PT_Opposition_Refused",
    "PT_Notification",
    "PT_Limited_B3",
    "PT_Lapsed",
    "PT_Granted_B1",
    "PT_Granted_B",
    "PT_Expired",
    "PT_EPTranslationAmended_T6",
    "PT_EPTranslation_T3",
    "PT_EPTranslation_T2",
    "PT_AvailableToPublic_A1",
    "PT_Application_withdrawn",
    "PT_Application_refused",
    "PT_Application_dismissed",
    "PT_Application_filed",
    "PT_Annulled",
    "PT_AnnulledPartial",
    "PT_AcceptedApplicationT1",
    "PT_AcceptedApplication",
]


def _drop_none_values(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def build_patent_search_body(
    *,
    basic_search: str | None = None,
    patent_title: str | None = None,
    application_number: str | None = None,
    registration_number: str | None = None,
    priority_number: str | None = None,
    applicant: str | None = None,
    assignee: str | None = None,
    inventor: str | None = None,
    representative: str | None = None,
    ipc_classification: str | None = None,
    cpc_classification: str | None = None,
    spc_base_patent_number: str | None = None,
    application_start_date: str | None = None,
    application_end_date: str | None = None,
    filing_start_date: str | None = None,
    filing_end_date: str | None = None,
    grant_start_date: str | None = None,
    grant_end_date: str | None = None,
    publication_start_date: str | None = None,
    publication_end_date: str | None = None,
    priority_start_date: str | None = None,
    priority_end_date: str | None = None,
    open_start_date: str | None = None,
    open_end_date: str | None = None,
    opposition_period_start_start_date: str | None = None,
    opposition_period_start_end_date: str | None = None,
    dossier_statuses: list[str] | None = None,
    patent_types: list[str] | None = None,
    publication_types: list[str] | None = None,
) -> dict[str, Any]:
    """Build the 30-field patent-search request body.

    Empty list values on ``dossier_statuses`` / ``patent_types`` /
    ``publication_types`` would return zero hits; we default each to
    the full upstream vocabulary so a caller who only sets filters
    they care about still gets results.
    """
    return {
        "patentTitle": patent_title or "",
        "applicationNumber": application_number or "",
        "registrationNumber": registration_number or "",
        "priorityNumber": priority_number or "",
        "dossierStatus": (
            dossier_statuses if dossier_statuses is not None else list(DEFAULT_PATENT_STATUSES)
        ),
        "applicant": applicant or "",
        "assignee": assignee or "",
        "inventor": inventor or "",
        "representative": representative or "",
        "applicationStartDate": application_start_date or "",
        "applicationEndDate": application_end_date or "",
        "filingStartDate": filing_start_date or "",
        "filingEndDate": filing_end_date or "",
        "oppositionPeriodStartStartDate": opposition_period_start_start_date or "",
        "oppositionPeriodStartEndDate": opposition_period_start_end_date or "",
        "grantStartDate": grant_start_date or "",
        "grantEndDate": grant_end_date or "",
        "openStartDate": open_start_date or "",
        "openEndDate": open_end_date or "",
        "publicationStartDate": publication_start_date or "",
        "publicationEndDate": publication_end_date or "",
        "priorityStartDate": priority_start_date or "",
        "priorityEndDate": priority_end_date or "",
        "ipcClassification": ipc_classification or "",
        "cpcClassification": cpc_classification or "",
        "basicSearch": basic_search or "",
        "patentTypes": (patent_types if patent_types is not None else list(DEFAULT_PATENT_TYPES)),
        "noAuthoAppm": "",
        "spcBasePatentNumber": spc_base_patent_number or "",
        "publicationTypes": (
            publication_types if publication_types is not None else list(DEFAULT_PUBLICATION_TYPES)
        ),
    }


def build_trademark_search_body(
    *,
    trademark_word: str | None = None,
    application_number: str | None = None,
    registration_number: str | None = None,
    dossier_status: str | None = None,
    trademark_kind: str | None = None,
    applicant_name: str | None = None,
    representative_name: str | None = None,
    business_id: str | None = None,
    application_start_date: str | None = None,
    application_end_date: str | None = None,
    registration_start_date: str | None = None,
    registration_end_date: str | None = None,
    expiration_start_date: str | None = None,
    expiration_end_date: str | None = None,
    opposition_period_start_start_date: str | None = None,
    opposition_period_start_end_date: str | None = None,
    goods_and_services_term: str | None = None,
    goods_and_services_class_number: str | None = None,
    vienna_class: str | None = None,
    filing_number: str | None = None,
    basic_search: str | None = None,
) -> dict[str, Any]:
    """Build the 21-field trademark-search request body."""
    return {
        "trademarkWord": trademark_word or "",
        "applicationNumber": application_number or "",
        "registrationNumber": registration_number or "",
        "dossierStatus": dossier_status or "",
        "trademarkKind": trademark_kind or "",
        "applicantName": applicant_name or "",
        "representativeName": representative_name or "",
        "businessID": business_id or "",
        "applicationStartDate": application_start_date or "",
        "applicationEndDate": application_end_date or "",
        "oppositionPeriodStartStartDate": opposition_period_start_start_date or "",
        "oppositionPeriodStartEndDate": opposition_period_start_end_date or "",
        "registrationStartDate": registration_start_date or "",
        "registrationEndDate": registration_end_date or "",
        "expirationStartDate": expiration_start_date or "",
        "expirationEndDate": expiration_end_date or "",
        "goodsAndServicesTerm": goods_and_services_term or "",
        "goodsAndServicesClassNumber": goods_and_services_class_number or "",
        "viennaClass": vienna_class or "",
        "filingNumber": filing_number or "",
        "basicSearch": basic_search or "",
    }


def build_design_search_body(
    *,
    product_title: str | None = None,
    application_number: str | None = None,
    registration_number: str | None = None,
    dossier_status: str | None = None,
    designer_name: str | None = None,
    applicant_name: str | None = None,
    representative_name: str | None = None,
    business_id: str | None = None,
    application_start_date: str | None = None,
    application_end_date: str | None = None,
    publication_date_start_date: str | None = None,
    publication_date_end_date: str | None = None,
    registration_start_date: str | None = None,
    registration_end_date: str | None = None,
    opposition_period_start_start_date: str | None = None,
    opposition_period_start_end_date: str | None = None,
    class_number: str | None = None,
    filing_number: str | None = None,
    basic_search: str | None = None,
) -> dict[str, Any]:
    """Build the 19-field design-search request body."""
    return {
        "productTitle": product_title or "",
        "applicationNumber": application_number or "",
        "registrationNumber": registration_number or "",
        "dossierStatus": dossier_status or "",
        "designerName": designer_name or "",
        "applicantName": applicant_name or "",
        "representativeName": representative_name or "",
        "businessID": business_id or "",
        "applicationStartDate": application_start_date or "",
        "applicationEndDate": application_end_date or "",
        "oppositionPeriodStartStartDate": opposition_period_start_start_date or "",
        "oppositionPeriodStartEndDate": opposition_period_start_end_date or "",
        "publicationDateStartDate": publication_date_start_date or "",
        "publicationDateEndDate": publication_date_end_date or "",
        "registrationStartDate": registration_start_date or "",
        "registrationEndDate": registration_end_date or "",
        "classNumber": class_number or "",
        "filingNumber": filing_number or "",
        "basicSearch": basic_search or "",
    }


class PrhClient(BaseAsyncClient):
    """Async client for PRH's three public JSON APIs.

    All methods are read-only. The client shares one cache database
    and one httpx connection pool across the three hosts; per-method
    helpers pass absolute URLs so the base-URL machinery on
    :class:`BaseAsyncClient` stays out of the way.

    Example::

        async with PrhClient() as client:
            patent = await client.get_patent("20100001")
            tm_page = await client.search_trademarks(trademark_word="SISU")
    """

    CACHE_NAME: str = "prh_fi"
    DEFAULT_TIMEOUT: float = 30.0
    DEFAULT_BASE_URL: str = ""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        merged_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        if headers:
            merged_headers.update(headers)
        super().__init__(client=client, headers=merged_headers, **kwargs)

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}{path}"

    # ------------------------------------------------------------------
    # Patent search + GET
    # ------------------------------------------------------------------

    async def search_patents(self, **filters: Any) -> PatentSearchResponse:
        """``POST patenttitietopalvelu.prh.fi/nis-api-gateway-pat/patent``.

        Accepts every field from :func:`build_patent_search_body`.
        Inclusion-filter defaults are applied for ``dossier_statuses``,
        ``patent_types``, and ``publication_types`` when the caller
        passes ``None``.
        """
        body = build_patent_search_body(**filters)
        payload = await self._request_json(
            "POST",
            f"{PATENT_HOST}{PATENT_PATH}",
            json=body,
            context="prh_fi.search_patents",
        )
        return PatentSearchResponse.model_validate(payload)

    async def get_patent(self, application_number: str) -> PatentGetRecord:
        """``GET patenttitietopalvelu.prh.fi/nis-api-gateway-pat/patent/{n}``.

        Returns the full register record — trilingual title + abstracts,
        prosecution events, file-history pointers, named examiner,
        payment timeline, and SPC authorizations.
        """
        appno = (application_number or "").strip()
        if not appno:
            raise ValueError("application_number must be a non-empty string")
        payload = await self._request_json(
            "GET",
            f"{PATENT_HOST}{PATENT_PATH}/{appno}",
            context=f"prh_fi.get_patent[{appno}]",
        )
        return PatentGetRecord.model_validate(payload)

    async def get_patents(self, application_numbers: Iterable[str]) -> list[PatentGetRecord]:
        """Sequential portfolio fetch by application number.

        The MCP wrapper layers bounded concurrency on top.
        """
        results: list[PatentGetRecord] = []
        for appno in application_numbers:
            results.append(await self.get_patent(appno))
        return results

    # ------------------------------------------------------------------
    # Trademark + TMR
    # ------------------------------------------------------------------

    async def search_trademarks(self, **filters: Any) -> DossierSearchResponse:
        """``POST tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/trademark``."""
        body = build_trademark_search_body(**filters)
        payload = await self._request_json(
            "POST",
            f"{TRADEMARK_HOST}{TRADEMARK_PATH}",
            json=body,
            context="prh_fi.search_trademarks",
        )
        return DossierSearchResponse.model_validate(payload)

    async def search_well_known_trademarks(self, **filters: Any) -> DossierSearchResponse:
        """``POST tavaramerkkitietopalvelu.prh.fi/nis-api-gateway/tmr``.

        The well-known trademarks register (TMR) — marks recognized as
        well-known in Finland under §6 of the Trade Marks Act
        (544/2019). 111 records as of 2026-05-19; the body shape mirrors
        the regular trademark search.
        """
        body = build_trademark_search_body(**filters)
        payload = await self._request_json(
            "POST",
            f"{TRADEMARK_HOST}{TMR_PATH}",
            json=body,
            context="prh_fi.search_well_known_trademarks",
        )
        return DossierSearchResponse.model_validate(payload)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    async def search_designs(self, **filters: Any) -> DossierSearchResponse:
        """``POST mallioikeustietopalvelu.prh.fi/nis-api-gateway/design``."""
        body = build_design_search_body(**filters)
        payload = await self._request_json(
            "POST",
            f"{DESIGN_HOST}{DESIGN_PATH}",
            json=body,
            context="prh_fi.search_designs",
        )
        return DossierSearchResponse.model_validate(payload)

    # ------------------------------------------------------------------
    # Image downloads (TM + design)
    # ------------------------------------------------------------------

    async def download_trademark_image(
        self,
        application_number: str,
        registration_number: str | None = None,
        *,
        variant: str = "image",
    ) -> tuple[bytes, str]:
        """``GET tavaramerkkitietopalvelu.prh.fi/opendata/trademark/{variant}/...``.

        Returns ``(content, content_type)``. Variants:

        * ``image`` — full-size mark image (GIF or JPEG).
        * ``thumbnail`` — small thumbnail (JPEG).
        * ``thumbnail/large`` — large thumbnail (JPEG).

        ``registration_number`` is optional — the well-known TMR
        register surfaces images under just the application number.
        """
        if variant not in {"image", "thumbnail", "thumbnail/large"}:
            raise ValueError(
                f"variant must be 'image' / 'thumbnail' / 'thumbnail/large', got {variant!r}"
            )
        appno = (application_number or "").strip()
        if not appno:
            raise ValueError("application_number must be a non-empty string")
        path_segments: list[str] = [appno]
        if registration_number:
            path_segments.append(registration_number.strip())
        url = f"{TRADEMARK_HOST}/opendata/trademark/{variant}/" + "/".join(path_segments)
        response = await self._request("GET", url, context="prh_fi.download_trademark_image")
        content_type = response.headers.get("content-type", "application/octet-stream")
        return response.content, content_type

    async def download_design_image(
        self,
        image_id: str,
        *,
        variant: str = "image",
    ) -> tuple[bytes, str]:
        """``GET mallioikeustietopalvelu.prh.fi/opendata/design/{variant}/{image_id}``.

        Returns ``(content, content_type)``. Variants:

        * ``image`` — full-size design image (typically JPEG).
        * ``thumbnail`` — small thumbnail.
        * ``thumbnail/medium`` — medium thumbnail.

        ``image_id`` is the per-embodiment identifier from a dossier
        row, e.g. ``M19710014.1.1``.
        """
        if variant not in {"image", "thumbnail", "thumbnail/medium"}:
            raise ValueError(
                f"variant must be 'image' / 'thumbnail' / 'thumbnail/medium', got {variant!r}"
            )
        ident = (image_id or "").strip()
        if not ident:
            raise ValueError("image_id must be a non-empty string")
        url = f"{DESIGN_HOST}/opendata/design/{variant}/{ident}"
        response = await self._request("GET", url, context="prh_fi.download_design_image")
        content_type = response.headers.get("content-type", "application/octet-stream")
        return response.content, content_type


__all__ = [
    "PrhClient",
    "PATENT_HOST",
    "TRADEMARK_HOST",
    "DESIGN_HOST",
    "PATENT_PATH",
    "TRADEMARK_PATH",
    "TMR_PATH",
    "DESIGN_PATH",
    "DEFAULT_USER_AGENT",
    "SERVER_RESULT_CAP",
    "DEFAULT_PATENT_TYPES",
    "DEFAULT_PATENT_STATUSES",
    "DEFAULT_PUBLICATION_TYPES",
    "build_patent_search_body",
    "build_trademark_search_body",
    "build_design_search_body",
]
