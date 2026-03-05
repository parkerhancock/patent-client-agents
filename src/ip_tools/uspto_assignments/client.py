"""Async client for the USPTO Patent Assignment Search API.

This API provides access to patent assignment records from August 1980 to present.
It returns XML responses in Solr format.

Note: For assignment data via the USPTO Open Data Portal (ODP), use
`ip_tools.uspto_odp.UsptoOdpClient.get_assignment()` instead.
This client uses the legacy Assignment Search API which provides
broader search capabilities including patent number and assignee searches.

API Documentation:
    https://assignment.uspto.gov/patent/index.html#/patent/search
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Self

import httpx
from lxml import etree  # type: ignore[import]

from .models import AssignmentParty, AssignmentRecord

logger = logging.getLogger(__name__)


def _clean_patent_number(number: str) -> str:
    """Clean a patent number for API queries."""
    cleaned = re.sub(r"[^0-9A-Za-z]", "", number)
    if cleaned.upper().startswith("US"):
        cleaned = cleaned[2:]
    return cleaned


class UsptoAssignmentsClient:
    """Async client for the USPTO Patent Assignment Search API.

    This client queries the legacy Assignment Search API which provides
    rich search capabilities for patent assignments.

    Example:
        async with UsptoAssignmentsClient() as client:
            records = await client.assignments_for_patent("US8830957")
            for record in records:
                print(f"{record.conveyance_text}: {record.assignees}")
    """

    BASE_URL = "https://assignment-api.uspto.gov"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Override the default API base URL.
            timeout: Request timeout in seconds.
        """
        self._base_url = base_url or self.BASE_URL
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def assignments_for_patent(
        self,
        patent_number: str,
        *,
        rows: int = 200,
    ) -> list[AssignmentRecord]:
        """Get assignment records for a patent number.

        Args:
            patent_number: The patent number (e.g., "US8830957", "8830957").
            rows: Maximum number of records to return.

        Returns:
            List of AssignmentRecord objects.
        """
        cleaned = _clean_patent_number(patent_number)
        return await self._search(
            query=cleaned,
            filter_type="PatentNumber",
            rows=rows,
        )

    async def assignments_for_application(
        self,
        application_number: str,
        *,
        rows: int = 200,
    ) -> list[AssignmentRecord]:
        """Get assignment records for an application number.

        Args:
            application_number: The application number (e.g., "16123456").
            rows: Maximum number of records to return.

        Returns:
            List of AssignmentRecord objects.
        """
        cleaned = _clean_patent_number(application_number)
        return await self._search(
            query=cleaned,
            filter_type="ApplicationNumber",
            rows=rows,
        )

    async def assignments_for_assignee(
        self,
        assignee_name: str,
        *,
        rows: int = 200,
    ) -> list[AssignmentRecord]:
        """Get assignment records for an assignee name.

        Args:
            assignee_name: The assignee name to search.
            rows: Maximum number of records to return.

        Returns:
            List of AssignmentRecord objects.
        """
        return await self._search(
            query=assignee_name,
            filter_type="PatentAssigneeName",
            rows=rows,
        )

    async def _search(
        self,
        query: str,
        filter_type: str,
        rows: int,
    ) -> list[AssignmentRecord]:
        """Execute a search query."""
        client = await self._get_client()
        logger.debug("Searching assignments: query=%s filter=%s rows=%d", query, filter_type, rows)
        response = await client.get(
            "/patent/lookup",
            params={
                "query": query,
                "filter": filter_type,
                "rows": rows,
            },
        )
        response.raise_for_status()
        records = self._parse_response(response.content)
        logger.debug("Assignment search returned %d records", len(records))
        return records

    def _parse_response(self, content: bytes) -> list[AssignmentRecord]:
        """Parse XML response into AssignmentRecord objects."""
        if not content:
            logger.debug("Empty response body, returning no records")
            return []

        root = etree.fromstring(content)
        result_node = root.find("result[@name='response']")
        if result_node is None:
            return []

        records: list[AssignmentRecord] = []
        for doc in result_node.findall("doc"):
            records.append(self._parse_document(doc))
        return records

    def _parse_document(self, doc: etree._Element) -> AssignmentRecord:
        """Parse a single document element."""
        return AssignmentRecord(
            reel_number=self._string_value(doc, "reelNo"),
            frame_number=self._string_value(doc, "frameNo"),
            conveyance_text=self._string_value(doc, "conveyanceText"),
            recorded_date=self._date_value(doc, "recordedDate"),
            execution_date=self._date_value(doc, "patAssignorEarliestExDate"),
            assignors=self._collect_parties(doc, prefix="patAssignor"),
            assignees=self._collect_parties(doc, prefix="patAssignee"),
            patent_numbers=self._array_strings(doc, "patNum"),
            application_numbers=self._array_strings(doc, "applNum"),
        )

    @staticmethod
    def _string_value(doc: etree._Element, field: str) -> str | None:
        """Extract a string value from a document."""
        node = doc.find(f"str[@name='{field}']")
        if node is not None and node.text and node.text.strip().upper() != "NULL":
            return node.text.strip()
        return None

    @staticmethod
    def _date_value(doc: etree._Element, field: str) -> datetime | None:
        """Extract a date value from a document."""
        node = doc.find(f"date[@name='{field}']")
        if node is None or not node.text:
            return None
        text = node.text.strip()
        if not text or text.upper() == "NULL":
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _array_strings(self, doc: etree._Element, field: str) -> list[str]:
        """Extract an array of strings from a document."""
        node = doc.find(f"arr[@name='{field}']")
        if node is None:
            return []
        values: list[str] = []
        for child in node.findall("str"):
            if child.text and child.text.strip().upper() != "NULL":
                values.append(child.text.strip())
        return values

    def _collect_parties(self, doc: etree._Element, *, prefix: str) -> list[AssignmentParty]:
        """Collect party (assignor/assignee) information."""
        names = self._array_strings(doc, f"{prefix}Name")
        addresses1 = self._array_strings(doc, f"{prefix}Address1")
        addresses2 = self._array_strings(doc, f"{prefix}Address2")
        cities = self._array_strings(doc, f"{prefix}City")
        states = self._array_strings(doc, f"{prefix}State")
        countries = self._array_strings(doc, f"{prefix}CountryName")
        postcodes = self._array_strings(doc, f"{prefix}Postcode")

        parties: list[AssignmentParty] = []
        for idx, name in enumerate(names):
            parties.append(
                AssignmentParty(
                    name=name,
                    address1=addresses1[idx] if idx < len(addresses1) else None,
                    address2=addresses2[idx] if idx < len(addresses2) else None,
                    city=cities[idx] if idx < len(cities) else None,
                    state=states[idx] if idx < len(states) else None,
                    country=countries[idx] if idx < len(countries) else None,
                    postcode=postcodes[idx] if idx < len(postcodes) else None,
                )
            )
        return parties


__all__ = ["UsptoAssignmentsClient"]
