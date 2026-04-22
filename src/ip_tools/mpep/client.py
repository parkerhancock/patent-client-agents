from __future__ import annotations

import json
import os
import re

import httpx

from law_tools_core import BaseAsyncClient

from .models import MpepSearchResponse, MpepSection, MpepVersion
from .transformers import (
    parse_search_response,
    parse_section_html,
    parse_toc_for_section,
    parse_versions,
)
from .utils import build_search_params

# Pattern to detect if input looks like a section number vs an href
# Section numbers: 2106, 2106.04, 2106.04(a), 706.03(a)(1)
# Hrefs: d0e197244.html, ch2100_d29a1b_13a9e_2dc.html
SECTION_NUMBER_PATTERN = re.compile(r"^\d+(\.\d+)?(\([a-z]\))?(\(\d+\))?$", re.IGNORECASE)


class MpepClient(BaseAsyncClient):
    DEFAULT_BASE_URL: str = os.getenv("MPEP_BASE_URL", "https://mpep.uspto.gov")
    CACHE_NAME: str = "mpep"
    DEFAULT_TIMEOUT: float = 30.0

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(
            client=client,
            headers={
                # Note: Do NOT send Accept: application/json - the MPEP API
                # paradoxically returns HTML when JSON is requested
                "User-Agent": "ip-tools-mpep/0.2",
            },
        )

    async def resolve_section_href(
        self,
        section_number: str,
        *,
        version: str = "current",
    ) -> str | None:
        """Resolve a section number to its href by searching the MPEP.

        Args:
            section_number: The section number (e.g., "2106", "2106.04(a)").
            version: MPEP version to search.

        Returns:
            The href (e.g., "d0e197244.html") or None if not found.
        """
        # For subsections with parentheticals like "2106.04(a)", search for
        # the base section number (e.g., "2106.04") since parentheses break
        # the search. We'll find the exact match in the ToC.
        search_term = re.sub(r"\([^)]+\)", "", section_number)

        # Strip leading zeros for the search API (it doesn't find "0700" but
        # finds "700"). We'll match against the original section_number in the
        # TOC which may include leading zeros.
        search_term = search_term.lstrip("0") or search_term

        # Search for the section number with exact syntax
        params = {
            "q": search_term,
            "ccb": "on",
            "icb": "off",
            "ncb": "off",
            "fcb": "off",
            "ver": version,
            "syn": "exact",
            "results": "compact",
            "sort": "outline",
            "cnt": 50,  # Get more results to find nested subsections
        }
        response = await self._request(
            "GET",
            "/RDMS/MPEP/search",
            params=build_search_params(params),
            context="resolve_section_href",
        )
        text = response.content.decode("utf-8", errors="replace")
        payload = json.loads(text)

        # The 'list' field contains the ToC with section numbers and hrefs
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
        include_form_paragraphs: bool = False,
        syntax: str = "adj",
        snippet: str = "compact",
        sort: str = "relevance",
        per_page: int = 10,
        page: int = 1,
    ) -> MpepSearchResponse:
        params = {
            "q": query,
            "ccb": "on" if include_content else "off",
            "icb": "on" if include_index else "off",
            "ncb": "on" if include_notes else "off",
            "fcb": "on" if include_form_paragraphs else "off",
            "ver": version,
            "syn": syntax,
            "results": snippet,
            "sort": sort,
            "cnt": per_page,
            "startPage": (page - 1) * per_page if page > 1 else "",
        }
        response = await self._request(
            "GET",
            "/RDMS/MPEP/search",
            params=build_search_params(params),
            context="search",
        )
        # Handle non-UTF-8 characters in MPEP content
        text = response.content.decode("utf-8", errors="replace")
        payload = json.loads(text)
        return parse_search_response(payload, self.base_url, page, per_page)

    async def get_section(
        self,
        section: str,
        *,
        version: str = "current",
        highlight_query: str | None = None,
    ) -> MpepSection:
        """Get a specific MPEP section.

        Args:
            section: Either a section number (e.g., "2106", "2106.04(a)") or
                an href (e.g., "d0e197244.html"). Section numbers are
                automatically resolved to hrefs.
            version: MPEP version.
            highlight_query: Optional query to highlight in the section.

        Returns:
            MpepSection with content.

        Raises:
            ValueError: If a section number cannot be resolved to an href.
        """
        # Determine if this is a section number or an href
        href = section
        if SECTION_NUMBER_PATTERN.match(section):
            # This looks like a section number, resolve it
            resolved = await self.resolve_section_href(section, version=version)
            if resolved is None:
                raise ValueError(f"Could not find MPEP section '{section}'")
            href = resolved

        if highlight_query:
            params = {"href": href, "q": highlight_query, "ver": version}
            response = await self._request(
                "GET",
                "/RDMS/MPEP/result",
                params=params,
                context="get_section",
            )
        else:
            # The content API expects just the filename, not a path
            clean_href = href.lstrip("/")
            if clean_href.startswith("current/"):
                clean_href = clean_href[8:]  # Remove "current/" prefix
            params = {
                "version": version,
                "href": clean_href,
            }
            response = await self._request(
                "GET",
                "/RDMS/MPEP/content",
                params=params,
                context="get_section",
            )
        html = response.text
        return parse_section_html(html, version=version, href=href)

    async def list_versions(self) -> list[MpepVersion]:
        response = await self._request(
            "GET",
            "/RDMS/MPEP/current",
            context="list_versions",
        )
        html = response.text
        return parse_versions(html)
