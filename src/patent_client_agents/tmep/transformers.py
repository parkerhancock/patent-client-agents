from __future__ import annotations

import re
from typing import cast

from lxml import html

from .models import TmepSearchHit, TmepSearchResponse, TmepSection, TmepVersion


def parse_search_response(
    payload: dict[str, str],
    base_url: str,
    page: int,
    per_page: int,
) -> TmepSearchResponse:
    """Parse TMEP search response JSON into structured results."""
    list_html = payload.get("list") or ""
    soup = html.fromstring(list_html or "<div></div>")
    hits: list[TmepSearchHit] = []

    for anchor in soup.cssselect("a[href]"):
        href = anchor.get("href", "") or ""
        title = "".join(anchor.itertext()).strip()
        if not href:
            continue
        # TMEP uses format: #/result/TMEP-1200d1e8145.html?q=...
        if href.startswith("#/result/"):
            result_path = href.lstrip("#")
            full_url = f"{base_url}/RDMS/TMEP/{result_path}"
            # Extract section href (e.g., TMEP-1200d1e8145.html)
            section_href = href.split("?")[0].replace("#/result/", "")
            path = _build_path(anchor)
            hits.append(
                TmepSearchHit(
                    title=title,
                    href=section_href,
                    path=path,
                    result_url=full_url,
                )
            )
    has_more = False
    # TMEP doesn't expose total hits; assume more if we returned per_page hits
    if len(hits) >= per_page:
        has_more = True
    return TmepSearchResponse(hits=hits, page=page, per_page=per_page, has_more=has_more)


def _build_path(anchor: html.HtmlElement) -> list[str]:
    """Build breadcrumb path from anchor element's parent hierarchy."""
    labels: list[str] = []
    parent = anchor.getparent()
    while parent is not None:
        if parent.tag == "span":
            text = "".join(parent.itertext()).strip()
            if text:
                labels.append(text)
        elif parent.tag == "li":
            span_child = next((child for child in parent if child.tag == "span"), None)
            if span_child is not None:
                text = "".join(span_child.itertext()).strip()
                if text:
                    labels.append(text)
        parent = parent.getparent()
    return list(reversed(labels))


def parse_section_html(raw_html: str, version: str, href: str) -> TmepSection:
    """Parse TMEP section HTML into structured content."""
    tree = html.fromstring(raw_html)
    for element in tree.xpath("//script | //style"):
        element.drop_tree()
    title_el = tree.xpath("//h1[1]")
    title = "".join(title_el[0].itertext()).strip() if title_el else None
    text = tree.text_content().strip()
    cleaned_html = cast(str, html.tostring(tree, encoding="unicode"))
    return TmepSection(href=href, html=cleaned_html, text=text, version=version, title=title)


def parse_versions(raw_html: str) -> list[TmepVersion]:
    """Parse version dropdown from TMEP page."""
    tree = html.fromstring(raw_html)
    select_nodes = tree.cssselect("select#edition-select")
    if not select_nodes:
        return []
    select = select_nodes[0]
    versions: list[TmepVersion] = []
    for option in select.cssselect("option"):
        label = "".join(option.itertext()).strip()
        value = (option.get("value") or "").lstrip("/")
        versions.append(
            TmepVersion(
                label=label,
                value=value,
                current=option.get("selected") is not None,
            )
        )
    return versions


def parse_toc_for_section(toc_html: str, section_number: str) -> str | None:
    """Parse the ToC HTML to find the href for a section number.

    The ToC contains links like:
        <a href="#/result/TMEP-1200d1e8145.html?q=...">1207.01 - Likelihood of Confusion</a>

    This extracts the href for the matching section.

    Args:
        toc_html: The 'list' field from the search response containing ToC HTML.
        section_number: The section number to find (e.g., "1207", "1207.01(a)").

    Returns:
        The href (e.g., "TMEP-1200d1e8145.html") or None if not found.
    """
    if not toc_html:
        return None

    tree = html.fromstring(toc_html)

    # Normalize section number for matching (handle parentheses)
    section_pattern = re.escape(section_number)

    for anchor in tree.cssselect("a[href]"):
        href = anchor.get("href", "") or ""
        title = "".join(anchor.itertext()).strip()

        # Check if this anchor's title starts with the section number
        # Match patterns like "1207 - Title" or "1207.01(a) - Title"
        if re.match(rf"^{section_pattern}\s*[-–—]", title):
            # Extract the actual href from "#/result/TMEP-xxx.html?q=..."
            if "#/result/" in href:
                match = re.search(r"#/result/([^?]+)", href)
                if match:
                    return match.group(1)
            elif href.endswith(".html"):
                return href.split("/")[-1].split("?")[0]

    return None
