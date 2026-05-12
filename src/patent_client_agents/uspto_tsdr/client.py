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
        # Parse ST96 XML response
        return self._parse_status_xml(response.text, serial_number)

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
        return LastUpdateInfo(
            serialNumber=serial_number,
            lastUpdateDate=last_date,
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

    def _parse_status_xml(self, xml_content: str, serial_number: str) -> TrademarkStatus:
        """Parse ST96 XML response into TrademarkStatus model."""
        try:
            root = ET.fromstring(xml_content)
            ns = {
                "c": "http://www.wipo.int/standards/XMLSchema/ST96/Common",
                "tm": "http://www.wipo.int/standards/XMLSchema/ST96/Trademark",
            }

            def ft(path: str) -> str | None:
                elem = root.find(path, ns)
                return elem.text.strip() if elem is not None and elem.text else None

            # Parse owners from Applicant and Registrant bags
            owners: list[Owner] = []
            for tag in ("tm:ApplicantBag/tm:Applicant", "tm:Registrant"):
                for owner_elem in root.findall(f".//{tag}", ns):
                    name = None
                    for name_path in (
                        "c:Contact/c:Name/c:EntityName",
                        "c:Contact/c:Name/c:OrganizationName/c:OrganizationStandardName",
                        "c:Contact/c:Name/c:PersonName/c:PersonFullName",
                    ):
                        n = owner_elem.find(name_path, ns)
                        if n is not None and n.text:
                            name = n.text.strip()
                            break
                    addr = owner_elem.find(
                        "c:Contact/c:PostalAddressBag/c:PostalAddress/c:PostalStructuredAddress",
                        ns,
                    )
                    if addr is None:
                        addr = owner_elem.find(
                            "c:Contact/c:PostalAddressBag/c:PostalStructuredAddress", ns
                        )
                    city = state = country = postcode = address = None
                    if addr is not None:
                        city_el = addr.find("c:CityName", ns)
                        city = (
                            city_el.text.strip() if city_el is not None and city_el.text else None
                        )
                        state_el = addr.find("c:GeographicRegionName", ns)
                        state = (
                            state_el.text.strip()
                            if state_el is not None and state_el.text
                            else None
                        )
                        country_el = addr.find("c:CountryCode", ns)
                        country = (
                            country_el.text.strip()
                            if country_el is not None and country_el.text
                            else None
                        )
                        pc_el = addr.find("c:PostalCode", ns)
                        postcode = pc_el.text.strip() if pc_el is not None and pc_el.text else None
                        addr_el = addr.find("c:AddressLineText", ns)
                        address = (
                            addr_el.text.strip() if addr_el is not None and addr_el.text else None
                        )
                    entity_el = owner_elem.find("c:LegalEntityName", ns)
                    entity_type = (
                        entity_el.text.strip() if entity_el is not None and entity_el.text else None
                    )
                    if name:
                        owners.append(
                            Owner(
                                name=name,
                                address=address,
                                city=city,
                                state=state,
                                country=country,
                                postcode=postcode,
                                entityType=entity_type,
                            )
                        )

            # Parse goods and services
            gs_list: list[GoodsServices] = []
            for gs_elem in root.findall(".//tm:GoodsServices", ns):
                class_num = None
                class_desc = None
                first_use = None
                first_use_commerce = None
                cn_el = gs_elem.find(
                    "tm:GoodsServicesClassificationBag/tm:GoodsServicesClassification"
                    "/tm:ClassNumber",
                    ns,
                )
                if cn_el is not None and cn_el.text:
                    class_num = int(cn_el.text.strip())
                desc_el = gs_elem.find(
                    "tm:ClassDescriptionBag/tm:ClassDescription/tm:GoodsServicesDescriptionText",
                    ns,
                )
                if desc_el is not None and desc_el.text:
                    class_desc = desc_el.text.strip()
                fu_el = gs_elem.find("tm:NationalGoodsServices/tm:FirstUsedDate", ns)
                if fu_el is not None and fu_el.text:
                    first_use = fu_el.text.strip()
                fuc_el = gs_elem.find("tm:NationalGoodsServices/tm:FirstUsedCommerceDate", ns)
                if fuc_el is not None and fuc_el.text:
                    first_use_commerce = fuc_el.text.strip()
                if class_num is not None or class_desc:
                    gs_list.append(
                        GoodsServices(
                            classNumber=class_num,
                            classDescription=class_desc,
                            firstUseDate=first_use,
                            firstUseDateInCommerce=first_use_commerce,
                        )
                    )

            # Parse prosecution history (mark events)
            events: list[ProsecutionEvent] = []
            for event_elem in root.findall(".//tm:MarkEventBag/tm:MarkEvent", ns):
                date_el = event_elem.find("tm:MarkEventDate", ns)
                # Description and code are nested under NationalMarkEvent
                nat = event_elem.find("tm:NationalMarkEvent", ns)
                desc_el = nat.find("tm:MarkEventDescriptionText", ns) if nat is not None else None
                code_el = nat.find("tm:MarkEventCode", ns) if nat is not None else None
                if date_el is not None or desc_el is not None:
                    events.append(
                        ProsecutionEvent(
                            eventDate=(
                                date_el.text.strip()
                                if date_el is not None and date_el.text
                                else None
                            ),
                            eventDescription=(
                                desc_el.text.strip()
                                if desc_el is not None and desc_el.text
                                else None
                            ),
                            eventCode=(
                                code_el.text.strip()
                                if code_el is not None and code_el.text
                                else None
                            ),
                        )
                    )

            # Strip timezone suffix from dates (e.g. "2010-06-22-04:00" -> "2010-06-22")
            def clean_date(d: str | None) -> str | None:
                if d and len(d) > 10:
                    return d[:10]
                return d

            status_desc = ft(".//tm:MarkCurrentStatusExternalDescriptionText")
            if not status_desc:
                status_desc = ft(".//tm:NationalStatusExternalDescriptionText")

            return TrademarkStatus(
                serialNumber=serial_number,
                registrationNumber=ft(".//c:RegistrationNumber"),
                markText=ft(".//tm:MarkVerbalElementText"),
                markType=ft(".//tm:MarkCategory"),
                statusCode=ft(".//tm:MarkCurrentStatusCode"),
                statusDescription=status_desc,
                statusDate=clean_date(ft(".//tm:MarkCurrentStatusDate")),
                filingDate=clean_date(ft(".//tm:ApplicationDate")),
                registrationDate=clean_date(ft(".//c:RegistrationDate")),
                renewalDate=clean_date(ft(".//tm:RenewalDate")),
                owners=owners,
                goodsServices=gs_list,
                prosecutionHistory=events,
            )
        except ET.ParseError:
            return TrademarkStatus(serialNumber=serial_number)

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

                doc = TsdrDocument(
                    docId=f"{sn}-{doc_type}" if doc_type else sn,
                    docType=doc_type,
                    docCategory=category,
                    docDate=mail_date[:10] if mail_date and len(mail_date) > 10 else mail_date,
                    description=doc_desc,
                    pageCount=int(pages) if pages else None,
                    mailDate=mail_date[:10] if mail_date and len(mail_date) > 10 else mail_date,
                )
                documents.append(doc)
        except ET.ParseError:
            pass
        return documents


__all__ = ["TsdrClient"]
