"""USPTO TSDR (Trademark Status & Document Retrieval) API client."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any

from law_tools_core.base_client import BaseAsyncClient
from law_tools_core.exceptions import ConfigurationError

from .models import (
    GoodsServices,
    LastUpdateInfo,
    Owner,
    ProsecutionEvent,
    TrademarkStatus,
    TsdrDocument,
)


class TsdrClient(BaseAsyncClient):
    """Async client for the USPTO TSDR API.

    Provides programmatic access to trademark status, documents, and images.

    Requires a USPTO TSDR API key. Sign in to the USPTO API Key Manager
    (https://account.uspto.gov/api-manager/) with a free MyUSPTO account,
    select the TSDR API product, and click "Request API key". The key is
    emailed and stored under your account.

    Rate limits (per key):
        - Peak (5am–10pm ET): 60 req/min general, 4 req/min PDF/ZIP
        - Off-peak (10pm–5am ET): 120 req/min general, 12 req/min PDF/ZIP

    Example:
        async with TsdrClient() as client:
            # Get trademark status
            status = await client.get_status("97123456")
            print(f"{status.mark_text}: {status.status_description}")

            # Download mark image
            image_data = await client.get_image("97123456")

            # Get all documents
            docs = await client.get_documents("97123456")
    """

    DEFAULT_BASE_URL = "https://tsdrapi.uspto.gov"
    CACHE_NAME = "uspto_tsdr"

    def __init__(
        self,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the TSDR client.

        Args:
            api_key: USPTO TSDR API key. If not provided, reads from
                USPTO_TSDR_API_KEY environment variable.
            **kwargs: Additional arguments passed to BaseAsyncClient.

        Raises:
            ConfigurationError: If no API key is provided or found.
        """
        resolved_key = api_key or os.environ.get("USPTO_TSDR_API_KEY")
        if not resolved_key:
            raise ConfigurationError(
                "USPTO TSDR API key required. Set USPTO_TSDR_API_KEY environment variable "
                "or pass api_key parameter. Sign in to the USPTO API Key Manager at "
                "https://account.uspto.gov/api-manager/ (free MyUSPTO account), select "
                "the TSDR API product, and request a key."
            )

        headers = kwargs.pop("headers", {})
        headers["USPTO-API-KEY"] = resolved_key

        super().__init__(headers=headers, **kwargs)
        self._api_key = resolved_key

    def _format_case_id(self, identifier: str, id_type: str = "sn") -> str:
        """Format a case identifier for API requests.

        Args:
            identifier: Serial number, registration number, or other ID.
            id_type: Type prefix - 'sn' (serial), 'rn' (registration),
                'ir' (international registration), 'ref' (Madrid reference).

        Returns:
            Formatted case ID like 'sn97123456'.
        """
        clean_id = identifier.replace("-", "").replace(" ", "")
        if clean_id.lower().startswith(("sn", "rn", "ir", "ref")):
            return clean_id.lower()
        return f"{id_type}{clean_id}"

    async def get_status(
        self,
        serial_number: str,
        *,
        timeout: float = 30.0,
    ) -> TrademarkStatus:
        """Get trademark status information.

        Args:
            serial_number: USPTO trademark serial number.
            timeout: Request timeout in seconds.

        Returns:
            TrademarkStatus with case information.
        """
        case_id = self._format_case_id(serial_number, "sn")
        response = await self._request(
            "GET",
            f"/ts/cd/casestatus/{case_id}/info",
            context="TSDR status",
            timeout=timeout,
        )
        return self._parse_status_json(response.json(), serial_number)

    async def get_status_json(
        self,
        serial_number: str,
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Get last update info as JSON.

        Args:
            serial_number: USPTO trademark serial number.
            timeout: Request timeout in seconds.

        Returns:
            Dictionary with last update information.
        """
        clean_sn = serial_number.replace("-", "").replace(" ", "")
        response = await self._request(
            "GET",
            "/last-update/info.json",
            params={"sn": clean_sn},
            context="TSDR last update",
            timeout=timeout,
        )
        return response.json()

    async def get_last_update(
        self,
        serial_number: str,
        *,
        timeout: float = 30.0,
    ) -> LastUpdateInfo:
        """Get last update timestamp for a trademark case.

        Derives the last update date from the most recent prosecution
        event in the case status.

        Args:
            serial_number: USPTO trademark serial number.
            timeout: Request timeout in seconds.

        Returns:
            LastUpdateInfo with update timestamp.
        """
        status = await self.get_status(serial_number, timeout=timeout)
        last_date = status.status_date
        if status.prosecution_history:
            # Use the most recent event date
            for event in status.prosecution_history:
                if event.event_date:
                    last_date = event.event_date
                    break
        return LastUpdateInfo.model_validate(
            {
                "serialNumber": serial_number,
                "lastUpdateDate": last_date,
            }
        )

    async def get_documents(
        self,
        serial_number: str,
        *,
        timeout: float = 30.0,
    ) -> list[TsdrDocument]:
        """Get list of documents for a trademark case.

        Args:
            serial_number: USPTO trademark serial number.
            timeout: Request timeout in seconds.

        Returns:
            List of TsdrDocument objects.
        """
        case_id = self._format_case_id(serial_number, "sn")
        response = await self._request(
            "GET",
            f"/ts/cd/casedocs/{case_id}/info",
            context="TSDR documents",
            timeout=timeout,
        )
        return self._parse_documents_xml(response.text)

    async def download_documents_pdf(
        self,
        serial_number: str,
        *,
        timeout: float = 120.0,
    ) -> bytes:
        """Download all documents for a case as a single PDF.

        Note: Rate limited to 4 requests per minute.

        Args:
            serial_number: USPTO trademark serial number.
            timeout: Request timeout in seconds.

        Returns:
            PDF file contents as bytes.
        """
        case_id = self._format_case_id(serial_number, "sn")
        response = await self._request(
            "GET",
            f"/ts/cd/casedocs/{case_id}/download.pdf",
            context="TSDR document download",
            timeout=timeout,
        )
        return response.content

    async def download_documents_zip(
        self,
        serial_number: str,
        *,
        timeout: float = 120.0,
    ) -> bytes:
        """Download all documents for a case as a ZIP archive.

        Note: Rate limited to 4 requests per minute.

        Args:
            serial_number: USPTO trademark serial number.
            timeout: Request timeout in seconds.

        Returns:
            ZIP file contents as bytes.
        """
        case_id = self._format_case_id(serial_number, "sn")
        response = await self._request(
            "GET",
            f"/ts/cd/casedocs/{case_id}/download.zip",
            context="TSDR document download",
            timeout=timeout,
        )
        return response.content

    async def get_image(
        self,
        serial_number: str,
        *,
        timeout: float = 30.0,
    ) -> bytes:
        """Get the trademark mark image.

        Args:
            serial_number: USPTO trademark serial number.
            timeout: Request timeout in seconds.

        Returns:
            Image file contents as bytes.
        """
        clean_sn = serial_number.replace("-", "").replace(" ", "")
        response = await self._request(
            "GET",
            f"/ts/cd/rawImage/{clean_sn}",
            context="TSDR image",
            timeout=timeout,
        )
        return response.content

    async def get_status_html(
        self,
        serial_number: str,
        *,
        timeout: float = 30.0,
    ) -> str:
        """Get trademark status as rendered HTML.

        Args:
            serial_number: USPTO trademark serial number.
            timeout: Request timeout in seconds.

        Returns:
            HTML content string.
        """
        case_id = self._format_case_id(serial_number, "sn")
        response = await self._request(
            "GET",
            f"/ts/cd/casestatus/{case_id}/content.html",
            context="TSDR status HTML",
            timeout=timeout,
        )
        return response.text

    async def batch_status(
        self,
        serial_numbers: list[str],
        *,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """Get status for multiple trademarks in a single request.

        Args:
            serial_numbers: List of serial numbers.
            timeout: Request timeout in seconds.

        Returns:
            Dictionary with case data keyed by serial number.
        """
        ids = ",".join(sn.replace("-", "").replace(" ", "") for sn in serial_numbers)
        response = await self._request(
            "GET",
            "/ts/cd/caseMultiStatus/sn",
            params={"ids": ids},
            context="TSDR batch status",
            timeout=timeout,
        )
        return response.json()

    def _parse_status_json(self, payload: dict[str, Any], serial_number: str) -> TrademarkStatus:
        """Parse the TSDR `casestatus/.../info` JSON response.

        The endpoint switched away from ST96 XML — the JSON shape lives under
        `payload["trademarks"][0]` with `status`, `parties`, `gsList`, and
        `prosecutionHistory` siblings. An empty `trademarks` list (no record)
        returns a near-empty model with only the serial set; a malformed
        payload raises rather than silently swallowing the error.
        """
        records = payload.get("trademarks") or []
        if not records:
            return TrademarkStatus.model_validate({"serialNumber": serial_number})
        tm = records[0]
        st = tm.get("status") or {}

        def clean_date(value: Any) -> str | None:
            if not value:
                return None
            text = str(value)
            return text[:10] if len(text) > 10 else text

        def opt_str(value: Any) -> str | None:
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        owners: list[Owner] = []
        owner_groups = (tm.get("parties") or {}).get("ownerGroups") or {}
        for group in owner_groups.values():
            for raw in group or []:
                name = opt_str(raw.get("name"))
                if not name:
                    continue
                address_lines = [
                    line
                    for line in (opt_str(raw.get("address1")), opt_str(raw.get("address2")))
                    if line
                ]
                address = ", ".join(address_lines) if address_lines else None
                asc = raw.get("addressStateCountry") or {}
                state_country = asc.get("stateCountry") or {}
                iso = asc.get("iso") or {}
                entity = raw.get("entityType") or {}
                owners.append(
                    Owner.model_validate(
                        {
                            "name": name,
                            "address": address,
                            "city": opt_str(raw.get("city")),
                            "state": opt_str(state_country.get("code")),
                            "country": opt_str(iso.get("code")) or opt_str(raw.get("countryCode")),
                            "postcode": opt_str(raw.get("zip")),
                            "entityType": opt_str(entity.get("description")),
                        }
                    )
                )

        gs_list: list[GoodsServices] = []
        for raw in tm.get("gsList") or []:
            prime = raw.get("primeClassCode")
            class_num: int | None = None
            if prime is not None:
                try:
                    class_num = int(str(prime).strip())
                except ValueError:
                    class_num = None
            gs_list.append(
                GoodsServices.model_validate(
                    {
                        "classNumber": class_num,
                        "classDescription": opt_str(raw.get("description")),
                        "firstUseDate": clean_date(raw.get("firstUseDate")),
                        "firstUseDateInCommerce": clean_date(raw.get("firstUseInCommerceDate")),
                    }
                )
            )

        events: list[ProsecutionEvent] = []
        for raw in tm.get("prosecutionHistory") or []:
            events.append(
                ProsecutionEvent.model_validate(
                    {
                        "eventDate": clean_date(raw.get("entryDate")),
                        "eventDescription": opt_str(raw.get("entryDesc")),
                        "eventCode": opt_str(raw.get("entryCode")),
                    }
                )
            )

        mark_flags = (
            ("TRADEMARK", st.get("trademark")),
            ("SERVICE_MARK", st.get("serviceMark")),
            ("CERTIFICATION_MARK", st.get("certificationMark")),
            ("COLLECTIVE_MEMBERSHIP_MARK", st.get("collectiveMembershipMark")),
            ("COLLECTIVE_SERVICE_MARK", st.get("collectiveServiceMark")),
            ("COLLECTIVE_TRADEMARK", st.get("collectiveTradeMark")),
        )
        mark_type = next((label for label, flag in mark_flags if flag), None)

        reg_num = opt_str(st.get("usRegistrationNumber"))
        status_code = opt_str(st.get("status"))

        return TrademarkStatus.model_validate(
            {
                "serialNumber": serial_number,
                "registrationNumber": reg_num,
                "markText": opt_str(st.get("markElement")),
                "markType": mark_type,
                "statusCode": status_code,
                "statusDescription": opt_str(st.get("extStatusDesc"))
                or opt_str(st.get("intStatusDesc")),
                "statusDate": clean_date(st.get("statusDate")),
                "filingDate": clean_date(st.get("filingDate")),
                "registrationDate": clean_date(st.get("registrationDate")),
                "abandonmentDate": clean_date(st.get("dateAbandoned")),
                "cancellationDate": clean_date(st.get("dateCancelled")),
                "expirationDate": clean_date(st.get("dateExpired") or st.get("expirationDate")),
                "renewalDate": clean_date(st.get("renewalDate")),
                "owners": owners,
                "goodsServices": gs_list,
                "prosecutionHistory": events,
            }
        )

    def _parse_documents_xml(self, xml_content: str) -> list[TsdrDocument]:
        """Parse documents XML response."""
        documents: list[TsdrDocument] = []
        try:
            root = ET.fromstring(xml_content)
            ns = {"d": "urn:us:gov:doc:uspto:trademark"}

            for doc_elem in root.findall(".//d:Document", ns):
                sn = doc_elem.findtext("d:SerialNumber", namespaces=ns) or ""
                doc_type = doc_elem.findtext("d:DocumentTypeCode", namespaces=ns)
                doc_desc = doc_elem.findtext("d:DocumentTypeDescriptionText", namespaces=ns)
                category = doc_elem.findtext("d:CategoryTypeCodeDescriptionText", namespaces=ns)
                mail_date = doc_elem.findtext("d:MailRoomDate", namespaces=ns)
                pages = doc_elem.findtext("d:TotalPageQuantity", namespaces=ns)

                doc = TsdrDocument.model_validate(
                    {
                        "docId": f"{sn}-{doc_type}" if doc_type else sn,
                        "docType": doc_type,
                        "docCategory": category,
                        "docDate": mail_date[:10]
                        if mail_date and len(mail_date) > 10
                        else mail_date,
                        "description": doc_desc,
                        "pageCount": int(pages) if pages else None,
                        "mailDate": mail_date[:10]
                        if mail_date and len(mail_date) > 10
                        else mail_date,
                    }
                )
                documents.append(doc)
        except ET.ParseError:
            pass
        return documents


__all__ = ["TsdrClient"]
