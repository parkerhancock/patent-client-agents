from __future__ import annotations

import re
from typing import cast

from lxml import html

from .models import MpepSearchHit, MpepSearchResponse, MpepSection, MpepVersion


def parse_search_response(
    payload: dict[str, str],
    base_url: str,
    page: int,
    per_page: int,
) -> MpepSearchResponse:
    list_html = payload.get("list") or ""
    soup = html.fromstring(list_html or "<div></div>")
    hits: list[MpepSearchHit] = []

    for anchor in soup.cssselect("a[href]"):
        href = anchor.get("href", "") or ""
        title = "".join(anchor.itertext()).strip()
        if not href:
            continue
        if href.startswith("#/result/"):
            result_path = href.lstrip("#")
            full_url = f"{base_url}/RDMS/MPEP/{result_path}"
            section_href = href.split("?")[0].replace("#/result/", "")
            path = _build_path(anchor)
            hits.append(
                MpepSearchHit(
                    title=title,
                    href=section_href,
                    path=path,
                    result_url=full_url,
                )
            )
    has_more = False
    # eMPEP doesn't expose total hits; assume more if we returned per_page hits
    if len(hits) >= per_page:
        has_more = True
    return MpepSearchResponse(hits=hits, page=page, per_page=per_page, has_more=has_more)


def _build_path(anchor: html.HtmlElement) -> list[str]:
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


def parse_section_html(raw_html: str, version: str, href: str) -> MpepSection:
    tree = html.fromstring(raw_html)
    for element in tree.xpath("//script | //style"):
        element.drop_tree()
    title_el = tree.xpath("//h1[1]")
    title = "".join(title_el[0].itertext()).strip() if title_el else None
    text = tree.text_content().strip()
    cleaned_html = cast(str, html.tostring(tree, encoding="unicode"))
    return MpepSection(href=href, html=cleaned_html, text=text, version=version, title=title)


def parse_versions(raw_html: str) -> list[MpepVersion]:
    tree = html.fromstring(raw_html)
    select_nodes = tree.cssselect("select#edition-select")
    if not select_nodes:
        return []
    select = select_nodes[0]
    versions: list[MpepVersion] = []
    for option in select.cssselect("option"):
        label = "".join(option.itertext()).strip()
        value = (option.get("value") or "").lstrip("/")
        versions.append(
            MpepVersion(
                label=label,
                value=value,
                current=option.get("selected") is not None,
            )
        )
    return versions


def _extract_href_from_element(href: str) -> str | None:
    """Extract the section href from a TOC element's href attribute."""
    if "#/result/" in href:
        # Get the filename between #/result/ and ?
        match = re.search(r"#/result/([^?]+)", href)
        if match:
            return match.group(1)
    elif href.endswith(".html"):
        # Direct href without fragment
        return href.split("/")[-1].split("?")[0]
    return None


def parse_toc_for_section(toc_html: str, section_number: str) -> str | None:
    """Parse the ToC HTML to find the href for a section number.

    The ToC contains links like:
        <a href="#/result/d0e197244.html?q=...">2106 - Patent Subject Matter Eligibility</a>

    For chapter-level sections (like 0700), the ToC uses <span> tags instead:
        <span href="#/result/d0e55397.html?q=...">0700 - Examination of Applications</span>

    This extracts the href for the matching section.

    Args:
        toc_html: The 'list' field from the search response containing ToC HTML.
        section_number: The section number to find (e.g., "2106", "2106.04(a)").

    Returns:
        The href (e.g., "d0e197244.html") or None if not found.
    """
    if not toc_html:
        return None

    tree = html.fromstring(toc_html)

    # Normalize section number for matching (handle parentheses)
    # "2106.04(a)" should match "2106.04(a)" in the title
    section_pattern = re.escape(section_number)

    # Check both <a> and <span> elements with href attributes
    # The TOC uses <span href="..."> for chapter-level sections like "0700"
    for element in tree.iter():
        href = element.get("href", "") or ""
        if not href:
            continue

        title = "".join(element.itertext()).strip()

        # Check if this element's title starts with the section number
        # Match patterns like "2106 - Title" or "2106.04(a) - Title"
        if re.match(rf"^{section_pattern}\s*[-–—]", title):
            result = _extract_href_from_element(href)
            if result:
                return result

    return None
