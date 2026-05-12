"""USPTO Trademark Manual of Examining Procedure (TMEP) client."""

from __future__ import annotations

import json
import re

import httpx

from .models import TmepSearchResponse, TmepSection, TmepVersion
from .transformers import (
    parse_search_response,
    parse_section_html,
    parse_toc_for_section,
    parse_versions,
)
from .utils import BASE_URL, build_search_params

# Pattern to detect if input looks like a section number vs an href
# Section numbers: 1207, 1207.01, 1207.01(a), 710.01(c)
# Hrefs: TMEP-1200d1e8145.html, changed1e1.html
SECTION_NUMBER_PATTERN = re.compile(r"^\d+(\.\d+)?(\([a-z]\))?(\(\d+\))?$", re.IGNORECASE)


class TmepClient:
    """Async client for searching and retrieving TMEP sections.

    Example:
        async with TmepClient() as client:
            results = await client.search("likelihood of confusion")
            for hit in results.hits:
                print(f"{hit.title}: {hit.href}")

            section = await client.get_section("TMEP-1200d1e8145.html")
            print(section.text)
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Initialize the TMEP client.

        Args:
            client: Optional httpx client to use. If not provided, one is created.
        """
        headers = {
            # Note: Do NOT send Accept: application/json - the TMEP API
            # paradoxically returns HTML when JSON is requested
            "User-Agent": "law-tools/0.1 (tmep-client)",
        }
        timeout = httpx.Timeout(10.0, connect=10.0, read=30.0, write=10.0)
        self._client = client or httpx.AsyncClient(headers=headers, timeout=timeout)
        self._owns_client = client is None

    async def __aenter__(self) -> TmepClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()

    async def resolve_section_href(
        self,
        section_number: str,
        *,
        version: str = "current",
    ) -> str | None:
        """Resolve a section number to its href by searching the TMEP.

        Args:
            section_number: The section number (e.g., "1207", "1207.01(a)").
            version: TMEP version to search.

        Returns:
            The href (e.g., "TMEP-1200d1e8145.html") or None if not found.
        """
        # For subsections with parentheticals like "1207.01(a)", search for
        # the base section number since parentheses break the search.
        search_term = re.sub(r"\([^)]+\)", "", section_number)

        params = {
            "q": search_term,
            "ccb": "on",
            "icb": "off",
            "ncb": "off",
            "ver": version,
            "syn": "exact",
            "results": "compact",
            "sort": "outline",
            "cnt": 50,
        }
        response = await self._client.get(
            f"{BASE_URL}/RDMS/TMEP/search",
            params=build_search_params(params),
        )
        response.raise_for_status()
        text = response.content.decode("utf-8", errors="replace")
        payload = json.loads(text)

        toc_html = payload.get("list", "")
        return parse_toc_for_section(toc_html, section_number)

    async def search(
        self,
        query: str,
        *,
        version: str = "current",
        include_content: bool = True,
        include_index: bool = False,
        include_notes: bool = False,
        syntax: str = "adj",
        snippet: str = "compact",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> TmepSearchResponse:
        """Search the TMEP.

        Args:
            query: Search query string.
            version: TMEP version (e.g., "current", "Nov2025", "Oct2024").
            include_content: Include content sections in search.
            include_index: Include index in search.
            include_notes: Include notes in search.
            syntax: Search syntax - "adj" (adjacent), "and", "or", "exact".
            snippet: Snippet display - "compact" or "full".
            sort: Sort order - "relevance" or "outline".
            per_page: Results per page (max 100).
            page: Page number (1-based).

        Returns:
            TmepSearchResponse with search hits.
        """
        params = {
            "q": query,
            "ccb": "on" if include_content else "off",
            "icb": "on" if include_index else "off",
            "ncb": "on" if include_notes else "off",
            "ver": version,
            "syn": syntax,
            "results": snippet,
            "sort": sort,
            "cnt": per_page,
            "startPage": (page - 1) * per_page if page > 1 else "",
        }
        response = await self._client.get(
            f"{BASE_URL}/RDMS/TMEP/search",
            params=build_search_params(params),
        )
        response.raise_for_status()
        # Handle non-UTF-8 characters in TMEP content
        text = response.content.decode("utf-8", errors="replace")
        payload = json.loads(text)
        return parse_search_response(payload, BASE_URL, page, per_page)

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
        highlight_query: str | None = None,
    ) -> TmepSection:
        """Get a specific TMEP section.

        Args:
            section: Either a section number (e.g., "1207", "1207.01(a)") or
                an href (e.g., "TMEP-1200d1e8145.html"). Section numbers are
                automatically resolved to hrefs.
            version: TMEP version.
            highlight_query: Optional query to highlight in the section.

        Returns:
            TmepSection with content.

        Raises:
            ValueError: If a section number cannot be resolved to an href.
        """
        # Determine if this is a section number or an href
        href = section
        if SECTION_NUMBER_PATTERN.match(section):
            resolved = await self.resolve_section_href(section, version=version)
            if resolved is None:
                raise ValueError(f"Could not find TMEP section '{section}'")
            href = resolved

        if highlight_query:
            url = f"{BASE_URL}/RDMS/TMEP/result"
            params = {"href": href, "q": highlight_query, "ver": version}
            response = await self._client.get(url, params=params)
        else:
            url = f"{BASE_URL}/RDMS/TMEP/content"
            params = {"version": version, "href": href}
            response = await self._client.get(url, params=params)
        response.raise_for_status()
        html = response.text
        return parse_section_html(html, version=version, href=href)

    async def list_versions(self) -> list[TmepVersion]:
        """List available TMEP versions.

        Returns:
            List of TmepVersion objects.
        """
        response = await self._client.get(f"{BASE_URL}/RDMS/TMEP/current")
        response.raise_for_status()
        html = response.text
        return parse_versions(html)
