"""Async client for CAFC opinions via WordPress DataTables API.

Scrapes the Federal Circuit's opinions page, extracting the WordPress
nonce for authenticated DataTables API requests. Supports date and
origin filtering, pagination, PDF download, and patent classification.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from mcp_data_core import BaseAsyncClient
from mcp_data_core.exceptions import McpDataCoreError
from patent_client_agents.cafc.classifier import PatentClassifier
from patent_client_agents.cafc.models import CAFCOpinion

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.cafc.uscourts.gov"
_OPINIONS_PATH = "/home/case-information/opinions-orders/"
_API_PATH = "/wp-admin/admin-ajax.php?action=get_wdtable&table_id=1"
_OPINIONS_URL = f"{_BASE_URL}{_OPINIONS_PATH}"
_PATENT_ORIGINS = ("PTO", "DCT", "ITC", "CFC")

# CAFC's edge (CloudFront + WordPress) blocks plain httpx user agents on the
# WordPress AJAX endpoint with a 403. A regular desktop UA passes.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
}

_AJAX_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": _BASE_URL,
    "Referer": _OPINIONS_URL,
}

# WordPress DataTables column config (fixed for the CAFC opinions table).
_COLUMNS = [
    {"name": "Release_Date", "searchable": "true", "orderable": "true", "search_regex": "false"},
    {"name": "Appeal_Number", "searchable": "true", "orderable": "true", "search_regex": "false"},
    {"name": "Origin", "searchable": "true", "orderable": "true", "search_regex": "true"},
    {"name": "Document_Type", "searchable": "true", "orderable": "true", "search_regex": "true"},
    {"name": "Case_Name", "searchable": "true", "orderable": "true", "search_regex": "false"},
    {"name": "Status", "searchable": "true", "orderable": "true", "search_regex": "true"},
    {"name": "File_Path", "searchable": "false", "orderable": "false", "search_regex": "false"},
]


class CAFCError(McpDataCoreError):
    """Error from the CAFC WordPress API."""


class CAFCClient(BaseAsyncClient):
    """Async client for Federal Circuit opinions.

    Fetches opinions from the CAFC website's WordPress DataTables API.
    Supports filtering by date range and origin code, pagination,
    patent classification, and PDF download.

    Example::

        async with CAFCClient() as client:
            opinions = await client.search(
                date_from=date(2025, 1, 1),
                origins=["PTO"],
            )
            for op in opinions:
                print(op.appeal_number, op.case_name, op.is_patent_case)
    """

    DEFAULT_BASE_URL: str = _BASE_URL
    CACHE_NAME: str = "cafc"
    DEFAULT_TIMEOUT: float = 60.0

    def __init__(self, *, classify: bool = True, **kwargs: Any) -> None:
        """Initialize.

        Args:
            classify: Whether to auto-classify opinions as patent cases.
            **kwargs: Forwarded to :class:`BaseAsyncClient`.
        """
        super().__init__(headers=_BROWSER_HEADERS, **kwargs)
        self._classify = classify
        self._classifier = PatentClassifier() if classify else None
        self._nonce: str | None = None
        self._draw = 1

    async def __aenter__(self) -> CAFCClient:
        await super().__aenter__()
        await self._init_session()
        return self

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        *,
        query: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        origins: list[str] | None = None,
        max_results: int | None = None,
    ) -> list[CAFCOpinion]:
        """Search CAFC opinions with optional text, date, and origin filters.

        Args:
            query: Free-text search passed to the upstream DataTables
                ``search[value]`` field. Matches across searchable
                columns (case name, etc.). Without this, the upstream
                returns the full recent list and any client-side filter
                only sees ``length`` rows — which usually misses hits.
            date_from: Start date (inclusive).
            date_to: End date (inclusive). Defaults to today.
            origins: Origin codes to filter (e.g. ``["PTO", "DCT"]``).
            max_results: Cap on number of results.

        Returns:
            List of :class:`CAFCOpinion` objects.
        """
        opinions: list[CAFCOpinion] = []
        page_size = 100
        start = 0

        while True:
            result = await self._fetch_page(
                start=start,
                length=page_size,
                query=query,
                date_from=date_from,
                date_to=date_to,
                origins=origins,
            )
            rows = result.get("data", [])
            if not rows:
                break

            for row in rows:
                opinion = self._parse_row(row)
                opinions.append(opinion)
                if max_results and len(opinions) >= max_results:
                    return opinions

            if len(rows) < page_size:
                break
            start += page_size

        return opinions

    async def search_patent_opinions(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        max_results: int | None = None,
    ) -> list[CAFCOpinion]:
        """Search only patent-relevant opinions (PTO, DCT, ITC, CFC origins)."""
        return await self.search(
            date_from=date_from,
            date_to=date_to,
            origins=list(_PATENT_ORIGINS),
            max_results=max_results,
        )

    async def recent(self, days: int = 30) -> list[CAFCOpinion]:
        """Convenience: fetch opinions from the last *days* days."""
        return await self.search(date_from=date.today() - timedelta(days=days))

    async def download_pdf(
        self,
        opinion: CAFCOpinion,
        *,
        output_path: str | Path | None = None,
    ) -> bytes:
        """Download the PDF for an opinion.

        Args:
            opinion: The opinion (must have ``file_path``).
            output_path: Optional path to write the PDF.

        Returns:
            PDF content as bytes.
        """
        if not opinion.file_path:
            msg = f"No file_path for opinion {opinion.appeal_number}"
            raise CAFCError(msg)

        # PDF lives at the absolute URL pointed at by file_path or pdf_url;
        # both already include the host so go around BaseAsyncClient's
        # base_url prefixing by issuing the raw GET ourselves.
        url = opinion.pdf_url or f"{_BASE_URL}/{opinion.file_path.lstrip('/')}"
        response = await self._client.get(url)
        response.raise_for_status()
        content = response.content

        if output_path is not None:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(content)

        return content

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _init_session(self) -> None:
        """Visit the opinions page and extract the WordPress nonce."""
        response = await self._request("GET", _OPINIONS_PATH, context="cafc init")
        text = response.text

        # The nonce is in a hidden input:
        #   <input id="wdtNonceFrontendServerSide_1" value="abc1234567">
        match = re.search(
            r'id="wdtNonceFrontendServerSide_1"[^>]+value="([a-f0-9]{10})"',
            text,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'value="([a-f0-9]{10})"[^>]+id="wdtNonceFrontendServerSide_1"',
                text,
                re.IGNORECASE,
            )
        if not match:
            msg = "Could not extract WordPress nonce from CAFC opinions page"
            raise CAFCError(msg)
        self._nonce = match.group(1)
        logger.debug("CAFC nonce acquired: %s", self._nonce)

    async def _fetch_page(
        self,
        *,
        start: int,
        length: int,
        query: str | None = None,
        date_from: date | None,
        date_to: date | None,
        origins: list[str] | None,
    ) -> dict[str, Any]:
        """Fetch one page of results from the DataTables API."""
        data = self._build_form_data(
            start=start,
            length=length,
            query=query,
            date_from=date_from,
            date_to=date_to,
            origins=origins,
        )
        return await self._request_json(
            "POST",
            _API_PATH,
            data=data,
            headers=_AJAX_HEADERS,
            context="cafc fetch page",
        )

    def _build_form_data(
        self,
        *,
        start: int,
        length: int,
        query: str | None = None,
        date_from: date | None,
        date_to: date | None,
        origins: list[str] | None,
    ) -> dict[str, str]:
        """Build the WordPress DataTables form payload."""
        data: dict[str, str] = {
            "draw": str(self._draw),
            "start": str(start),
            "length": str(length),
            "search[value]": query or "",
            "search[regex]": "false",
            "order[0][column]": "0",
            "order[0][dir]": "desc",
            "wdtNonce": self._nonce or "",
            "sRangeSeparator": "|",
        }
        self._draw += 1

        for i, col in enumerate(_COLUMNS):
            data[f"columns[{i}][data]"] = str(i)
            data[f"columns[{i}][name]"] = col["name"]
            data[f"columns[{i}][searchable]"] = col["searchable"]
            data[f"columns[{i}][orderable]"] = col["orderable"]
            data[f"columns[{i}][search][value]"] = ""
            data[f"columns[{i}][search][regex]"] = col["search_regex"]

        if date_from and date_to:
            data["columns[0][search][value]"] = (
                f"{date_from.strftime('%m/%d/%Y')}|{date_to.strftime('%m/%d/%Y')}"
            )
        elif date_from:
            data["columns[0][search][value]"] = (
                f"{date_from.strftime('%m/%d/%Y')}|{date.today().strftime('%m/%d/%Y')}"
            )

        if origins:
            data["columns[2][search][value]"] = "|".join(origins)

        return data

    def _parse_row(self, row: list[str]) -> CAFCOpinion:
        """Parse a DataTables row into a CAFCOpinion."""
        release_date_str = row[0] if len(row) > 0 else ""
        appeal_number = row[1] if len(row) > 1 else ""
        origin = row[2] if len(row) > 2 else ""
        document_type = row[3] if len(row) > 3 else ""
        case_name_html = row[4] if len(row) > 4 else ""
        status = row[5] if len(row) > 5 else ""
        file_path = row[6] if len(row) > 6 else ""

        # Parse release date
        release_date: date | None = None
        try:
            release_date = datetime.strptime(release_date_str, "%m/%d/%Y").date()
        except (ValueError, TypeError):
            pass

        # Extract clean case name from HTML: <span sort="Case Name">Case Name [OPINION]</span>
        match = re.search(r'sort="([^"]+)"', case_name_html)
        case_name = match.group(1) if match else re.sub(r"<[^>]+>", "", case_name_html)
        case_name_short = re.sub(r"\s*\[[^\]]+\]\s*$", "", case_name).strip()

        pdf_url = ""
        if file_path:
            pdf_url = f"{_BASE_URL}/{file_path.lstrip('/')}"

        is_patent = False
        confidence = 0.0
        keywords: list[str] = []
        if self._classifier:
            is_patent, confidence, keywords = self._classifier.classify(case_name)

        return CAFCOpinion(
            appeal_number=appeal_number,
            release_date=release_date,
            origin=origin,
            document_type=document_type,
            case_name=case_name,
            case_name_short=case_name_short,
            precedential_status=status,
            file_path=file_path,
            pdf_url=pdf_url,
            is_patent_case=is_patent,
            patent_confidence=confidence,
            patent_keywords=keywords,
        )
