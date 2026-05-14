"""Async client for the UPC decisions-and-orders index.

The Unified Patent Court publishes its decisions and orders as a Drupal
``views``-backed table at
``https://www.unifiedpatentcourt.org/en/decisions-and-orders``. Each row
carries the case identifier, division, case type, parties, and one or
more PDF/A attachments.

Important live-state finding (2026-05): the per-decision detail pages at
``/en/node/<id>`` are gated by Cloudflare's interactive challenge, but
the listing pages and the PDF binaries are not. The harvester therefore
reads only the listing pages — every structured field needed lives in
the row already.

Pagination uses the ``?page=N`` query parameter (0-indexed). The pager
exposes a ``Last page`` link from which we recover the total page count.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from lxml import html
from lxml.html import HtmlElement

from law_tools_core.base_client import BaseAsyncClient

from .models import (
    UpcDecision,
    UpcDecisionSearchResponse,
    UpcDivision,
    UpcLanguage,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.unifiedpatentcourt.org"
DEFAULT_LANGUAGE = "en"
DEFAULT_USER_AGENT = (
    "patent-client-agents-upc/0.11 (+https://github.com/parkerhancock/patent-client-agents)"
)

# Accept any of: UPC_CFI_1747/2025, UPC-CFI-478/2025, UPC_CFI_0001695/2025,
# UPC_CoA_335/2023, UPC-COA-35/2026, ACT_551054/2023.
_CASE_ID_RE = re.compile(
    r"""
    \b
    (?P<prefix>UPC[_-](?:CFI|CoA|COA)|ACT)
    [_-]
    (?P<number>\d{1,7})
    [/]
    (?P<year>\d{4})
    \b
    """,
    re.VERBOSE,
)

_PARTIES_SPLIT_RE = re.compile(r"\bv\.\s*", re.IGNORECASE)


def _canonicalize_case_id(raw: str) -> str:
    """Return the canonical underscored form of a UPC case identifier.

    Examples:
        ``UPC-CFI-478/2025`` → ``UPC_CFI_478/2025``
        ``UPC-COA-35/2026``  → ``UPC_CoA_35/2026``
        ``UPC_CFI_0001695/2025`` stays as-is (zero-padding preserved when present).
    """
    match = _CASE_ID_RE.search(raw)
    if not match:
        return raw.strip()
    prefix = match.group("prefix").replace("-", "_")
    if prefix.upper() == "UPC_COA":
        prefix = "UPC_CoA"
    return f"{prefix}_{match.group('number')}/{match.group('year')}"


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_parties(raw: str) -> list[str]:
    """Split a parties cell on 'v.' boundaries.

    The cell uses ``<br />`` between numbered parties on the same side
    and a literal ``v.`` between sides; lxml's ``text_content()`` keeps
    the line breaks as whitespace, so we split on the verbatim ``v.``
    separator and trim.
    """
    if not raw:
        return []
    sides = _PARTIES_SPLIT_RE.split(raw)
    return [_normalize_whitespace(side) for side in sides if side.strip()]


def _extract_row_cells(row: HtmlElement) -> dict[str, HtmlElement]:
    """Map a Drupal Views row's ``<td>`` cells by their field name.

    The UPC site is inconsistent: the document cell uses
    ``headers='view-field-upc-document-table-column'`` but reuses
    ``class='views-field-field-judgement-parties-long'`` from the
    parties column, so we have to disambiguate parties-vs-document by
    inspecting the cell content (media-document article = document cell).
    """
    cells: dict[str, HtmlElement] = {}
    for cell in row.xpath(".//td"):
        headers_attr = cell.get("headers") or ""
        if "view-field-judgement-application-no-1" in headers_attr:
            cells["case"] = cell
        elif "view-field-location" in headers_attr:
            cells["court"] = cell
        elif "view-field-upc-case-type" in headers_attr:
            cells["type"] = cell
        elif "view-field-upc-document" in headers_attr:
            cells["document"] = cell
        elif "view-field-judgement-parties-long" in headers_attr:
            cells.setdefault("parties", cell)
    return cells


def _row_case_data(cell: HtmlElement, base_url: str) -> tuple[str, list[str], str]:
    """Extract case_id (canonical), raw refs, and detail_url from the case cell."""
    raw_refs: list[str] = []
    detail_url = ""
    # Each <br>-separated text node is a reference; the trailing <a> is
    # the "Full Details" link to /en/node/<id>.
    for piece in cell.xpath("./br/preceding-sibling::text() | ./text()"):
        text = _normalize_whitespace(piece)
        if text and _CASE_ID_RE.search(text):
            raw_refs.append(text)
    # Also harvest siblings that appear between <br/>s
    for piece in cell.itertext():
        text = _normalize_whitespace(piece)
        if text and _CASE_ID_RE.search(text) and text not in raw_refs:
            raw_refs.append(text)
    detail_anchor = cell.xpath(".//a[contains(@class, 'btn--primary')]")
    if detail_anchor:
        href = detail_anchor[0].get("href") or ""
        if href:
            detail_url = href if href.startswith("http") else f"{base_url}{href}"
    case_id = _canonicalize_case_id(raw_refs[0]) if raw_refs else ""
    return case_id, raw_refs, detail_url


def _row_pdf_urls(cell: HtmlElement, base_url: str) -> list[str]:
    """Pull all linked PDF URLs out of a document cell."""
    urls: list[str] = []
    for a in cell.xpath(".//a[@href]"):
        href = a.get("href", "")
        if href.lower().endswith(".pdf"):
            urls.append(href if href.startswith("http") else f"{base_url}{href}")
    # Dedupe while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped


def parse_decisions_page(
    html_text: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
) -> tuple[list[UpcDecision], int]:
    """Parse a decisions-and-orders listing page.

    Returns:
        A ``(rows, total_pages)`` tuple. ``total_pages`` is recovered
        from the pager's "Last page" link; when the listing fits on a
        single page (no pager rendered), this falls back to ``1``.
    """
    tree = html.fromstring(html_text)
    rows: list[UpcDecision] = []
    seen_cases: set[str] = set()
    for tr in tree.xpath("//table//tbody//tr"):
        cells = _extract_row_cells(tr)
        if "case" not in cells:
            continue
        case_id, raw_refs, detail_url = _row_case_data(cells["case"], base_url)
        if not case_id or case_id in seen_cases:
            continue
        seen_cases.add(case_id)
        court_cell = cells.get("court")
        type_cell = cells.get("type")
        parties_cell = cells.get("parties")
        document_cell = cells.get("document")
        rows.append(
            UpcDecision(
                case_id=case_id,
                raw_references=raw_refs,
                detail_url=detail_url,
                court=_normalize_whitespace(court_cell.text_content())
                if court_cell is not None
                else "",
                type_of_action=_normalize_whitespace(type_cell.text_content())
                if type_cell is not None
                else "",
                parties=_parse_parties(
                    parties_cell.text_content() if parties_cell is not None else ""
                ),
                pdf_urls=_row_pdf_urls(document_cell, base_url)
                if document_cell is not None
                else [],
            )
        )

    total_pages = 1
    last_page_links = tree.xpath("//li[contains(@class, 'pager__item--last')]//a/@href")
    if last_page_links:
        match = re.search(r"[?&]page=(\d+)", last_page_links[0])
        if match:
            # ``page=`` is 0-indexed; total page count is N+1.
            total_pages = int(match.group(1)) + 1
    return rows, total_pages


def _parse_options(tree: HtmlElement, select_name: str) -> list[tuple[str, str]]:
    """Pull (value, label) pairs from a named <select>."""
    options: list[tuple[str, str]] = []
    for option in tree.xpath(f"//select[@name='{select_name}']//option"):
        value = option.get("value") or ""
        label = _normalize_whitespace(option.text_content())
        if value and value != "All" and label:
            options.append((value, label))
    return options


class UpcDecisionsClient(BaseAsyncClient):
    """HTML-scraping client for the UPC decisions-and-orders feed."""

    DEFAULT_BASE_URL = DEFAULT_BASE_URL
    CACHE_NAME = "upc_decisions"
    DEFAULT_TIMEOUT = 60.0

    def __init__(
        self,
        *,
        language: str = DEFAULT_LANGUAGE,
        user_agent: str = DEFAULT_USER_AGENT,
        client: httpx.AsyncClient | None = None,
        use_cache: bool = True,
        timeout: float | None = None,
    ) -> None:
        if language not in {"en", "fr", "de"}:
            raise ValueError("language must be one of 'en', 'fr', 'de'")
        super().__init__(
            client=client,
            use_cache=use_cache,
            headers={"User-Agent": user_agent, "Accept": "text/html"},
            timeout=timeout,
        )
        self._language = language

    @property
    def language(self) -> str:
        return self._language

    def _index_path(self) -> str:
        return f"/{self._language}/decisions-and-orders"

    async def search(
        self,
        *,
        page: int = 0,
        judgement_type: str | None = None,
        court_type: str | None = None,
        division: str | int | None = None,
        proceedings_lang: str | int | None = None,
    ) -> UpcDecisionSearchResponse:
        """Fetch a single listing page, optionally filtered.

        Args:
            page: 0-indexed page number. Defaults to 0 (most recent).
            judgement_type: ``order``, ``decision``, or None for both.
            court_type: One of ``1`` (CoA), ``2`` (Central CFI),
                ``3`` (Local CFI), ``4`` (Regional CFI), or None.
            division: Specific division ID (string or int) from
                :meth:`list_divisions`. Passed as ``division_1``.
            proceedings_lang: Procedural-language ID from
                :meth:`list_languages` (e.g. ``33`` for English).
        """
        # Drupal Views quirk: ``?page=0`` renders the View's *empty*
        # template (the View interprets the param as "page offset 0
        # beyond the natural first page" rather than "first page").
        # Omitting the param entirely is the canonical way to fetch
        # page 0. For page>=1 the param works as expected.
        params: dict[str, Any] = {}
        if page > 0:
            params["page"] = page
        if judgement_type:
            params["judgement_type"] = judgement_type
        if court_type:
            params["court_type"] = str(court_type)
        if division is not None:
            params["division_1"] = str(division)
        if proceedings_lang is not None:
            params["proceedings_lang"] = str(proceedings_lang)
        response = await self._request("GET", self._index_path(), params=params)
        rows, total_pages = parse_decisions_page(response.text, base_url=self.base_url)
        return UpcDecisionSearchResponse(page=page, total_pages=total_pages, hits=rows)

    async def get_decision(self, case_id: str) -> UpcDecision | None:
        """Look up a single decision by its canonical case ID.

        Walks pages until a matching ``case_id`` row is found. Useful
        for resolving a single citation without paging the whole index.
        Returns ``None`` if no row matches across the whole index.
        """
        canonical = _canonicalize_case_id(case_id)
        first = await self.search(page=0)
        for hit in first.hits:
            if hit.case_id == canonical:
                return hit
        for next_page in range(1, first.total_pages):
            chunk = await self.search(page=next_page)
            for hit in chunk.hits:
                if hit.case_id == canonical:
                    return hit
        return None

    async def list_divisions(self) -> list[UpcDivision]:
        """Return the division-filter options from the index page."""
        response = await self._request("GET", self._index_path())
        tree = html.fromstring(response.text)
        divisions: list[UpcDivision] = []
        seen: set[str] = set()
        # The page renders separate <select>s for division_1..division_4;
        # iterate them all and dedupe by ID.
        for field in ("division_1", "division_2", "division_3", "division_4"):
            for value, label in _parse_options(tree, field):
                if value in seen:
                    continue
                seen.add(value)
                divisions.append(UpcDivision(id=value, name=label))
        return divisions

    async def list_languages(self) -> list[UpcLanguage]:
        """Return the procedural-language filter options."""
        response = await self._request("GET", self._index_path())
        tree = html.fromstring(response.text)
        return [
            UpcLanguage(id=value, name=label)
            for value, label in _parse_options(tree, "proceedings_lang")
        ]

    async def download_pdf(self, pdf_url: str) -> bytes:
        """Fetch a PDF/A attachment by its absolute URL.

        Decisions are PDF/A as mandated by the RoP; the response is
        returned verbatim so callers can persist, OCR, or text-extract
        as needed.
        """
        if not pdf_url.startswith("http"):
            raise ValueError(
                "download_pdf expects an absolute URL (use the value from "
                "UpcDecision.pdf_urls verbatim)."
            )
        response = await self._client.get(pdf_url)
        self._raise_for_status(response, context=f"GET {pdf_url}")
        return response.content


__all__ = [
    "UpcDecisionsClient",
    "parse_decisions_page",
    "DEFAULT_BASE_URL",
]
