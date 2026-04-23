"""HTML parsing helpers for Google Patents metadata."""

from __future__ import annotations

import re
from typing import TypedDict

from lxml.html import HtmlElement, tostring


def _text(element: HtmlElement | None) -> str:
    return element.text_content().strip() if element is not None else ""


def _first_text(root: HtmlElement, xpath: str) -> str:
    """Return the first text result for the given XPath or an empty string."""

    results = root.xpath(xpath)
    if isinstance(results, str):
        return results.strip()
    if not results:
        return ""
    value = results[0]
    if isinstance(value, HtmlElement):
        return _text(value)
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _first_attr(root: HtmlElement, xpath: str, attribute: str) -> str | None:
    """Return an attribute value from the first matched element."""

    results = root.xpath(xpath)
    if not results:
        return None
    element = results[0]
    if not isinstance(element, HtmlElement):
        return None
    value = element.get(attribute)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _find_dt(root: HtmlElement, pattern: re.Pattern[str]) -> HtmlElement | None:
    """Locate the first <dt> whose text matches the regex."""

    for dt in root.xpath("//dt"):
        if pattern.search(_text(dt)):
            return dt
    return None


def _dd_text(dt_element: HtmlElement | None) -> str:
    """Return the text content of the next <dd> sibling."""

    if dt_element is None:
        return ""
    sibling = dt_element.getnext()
    while sibling is not None and sibling.tag != "dd":
        sibling = sibling.getnext()
    return _text(sibling)


def _event_entries(root: HtmlElement) -> list[HtmlElement]:
    """Return DD elements within the events section."""

    events_section = root.xpath("//section[@itemprop='events']")
    if not events_section:
        return []
    return events_section[0].xpath(".//dd")


def _extract_title(root: HtmlElement) -> str:
    meta_title = _first_text(root, "//meta[@name='DC.title']/@content")
    if meta_title:
        return meta_title
    fallback = _first_text(root, "normalize-space(//title)")
    if fallback and " - " in fallback:
        parts = [part.strip() for part in fallback.split(" - ") if part.strip()]
        if len(parts) >= 2:
            return parts[1]
    return fallback or "Title not found"


def _extract_abstract(root: HtmlElement) -> str:
    meta = _first_text(root, "//meta[@name='description']/@content")
    if meta:
        return meta
    section = root.xpath("//section[contains(@class, 'abstract')]")
    if section:
        return _text(section[0])
    return ""


def _extract_original_text_from_element(element: HtmlElement) -> str | None:
    """Extract original language text from google-src-text spans within an element.

    Google Patents wraps original (non-English) text in:
    <span class="google-src-text">original text here</span>

    Returns None if no original text spans are found.
    """
    src_spans = element.xpath(".//span[@class='google-src-text']")
    if not src_spans:
        return None

    parts: list[str] = []
    for span in src_spans:
        text = span.text_content()
        if text:
            parts.append(re.sub(r"\s+", " ", text).strip())

    return " ".join(parts) if parts else None


def _extract_original_title(root: HtmlElement) -> str | None:
    """Extract original language title from HTML."""
    # Try the title section first
    title_section = root.xpath("//section[@itemprop='title']")
    if title_section:
        return _extract_original_text_from_element(title_section[0])

    # Try the page title
    title_element = root.xpath("//title")
    if title_element:
        return _extract_original_text_from_element(title_element[0])

    return None


def _extract_original_abstract(root: HtmlElement) -> str | None:
    """Extract original language abstract from HTML."""
    section = root.xpath("//section[contains(@class, 'abstract')]")
    if section:
        return _extract_original_text_from_element(section[0])
    return None


def _find_description_section(root: HtmlElement) -> HtmlElement | None:
    """Find the description section by itemprop or class."""
    # Try itemprop first (modern Google Patents structure)
    section = root.xpath("//section[@itemprop='description']")
    if section:
        return section[0]
    # Fall back to class-based selector
    section = root.xpath("//section[contains(@class, 'description')]")
    if section:
        return section[0]
    return None


def _extract_description(root: HtmlElement) -> str:
    """Extract description as plain text (truncated for backward compatibility)."""
    section = _find_description_section(root)
    if section is None:
        return ""
    paragraphs = [p for p in section.xpath(".//p") if isinstance(p, HtmlElement)]
    if paragraphs:
        desc_text = "\n\n".join(_text(p) for p in paragraphs[:5] if _text(p))
    else:
        desc_text = _text(section)
    desc_text = desc_text.strip()
    if len(desc_text) > 2000:
        return f"{desc_text[:2000]}..."
    return desc_text


def _extract_description_html(root: HtmlElement) -> str | None:
    """Extract the full description section as raw HTML."""
    section = _find_description_section(root)
    if section is None:
        return None
    result = tostring(section, encoding="unicode")
    # tostring with encoding="unicode" returns str, but type checker doesn't know
    return result if isinstance(result, str) else None


def _extract_current_assignee(root: HtmlElement) -> str:
    meta = _first_text(root, "//meta[@name='DC.contributor' and @scheme='assignee']/@content")
    if meta:
        return meta
    dt = _find_dt(root, re.compile("Current Assignee", re.IGNORECASE))
    return _dd_text(dt)


def _extract_inventors(root: HtmlElement) -> list[str]:
    inventors: list[str] = []
    inventors.extend(
        name.strip()
        for name in root.xpath("//meta[@name='DC.contributor' and @scheme='inventor']/@content")
        if isinstance(name, str) and name.strip()
    )
    if inventors:
        return inventors

    dt = _find_dt(root, re.compile("Inventor", re.IGNORECASE))
    if dt is None:
        return []
    inventor_text = _dd_text(dt)
    if not inventor_text:
        return []
    return [name.strip() for name in inventor_text.split(",") if name.strip()]


def _extract_status(root: HtmlElement) -> str:
    status_span = root.xpath("//dd[@itemprop='legalStatusIfi']//span[@itemprop='status']")
    if status_span:
        text = _text(status_span[0])
        if text:
            return text

    status_event = root.xpath("//time[normalize-space()='Status']")
    if status_event:
        status_span = status_event[0].xpath("following-sibling::span[@itemprop='title'][1]")
        if status_span:
            text = _text(status_span[0])
            if text:
                return text

    return "Unknown"


def _extract_date_via_dt(root: HtmlElement, pattern: re.Pattern[str]) -> str:
    dt = _find_dt(root, pattern)
    return _dd_text(dt)


def _extract_expiration(root: HtmlElement) -> str:
    # Semantic ifiExpiration span (most reliable)
    ifi = root.xpath("//span[@itemprop='ifiExpiration']/text()")
    if ifi:
        val = ifi[0].strip()
        if val:
            return val

    expiry = _extract_date_via_dt(root, re.compile("Adjusted expiration", re.IGNORECASE))
    if expiry:
        return expiry

    expiry = _extract_date_via_dt(root, re.compile("Expiration", re.IGNORECASE))
    if expiry:
        return expiry

    for event in _event_entries(root):
        title = (
            _text(event.xpath(".//span[@itemprop='title']")[0])
            if event.xpath(".//span[@itemprop='title']")
            else ""
        )
        if "expiration" not in title.lower():
            continue
        time_element = event.xpath(".//time")
        if time_element:
            datetime_attr = time_element[0].get("datetime")
            if isinstance(datetime_attr, str) and datetime_attr.strip():
                return datetime_attr.strip()
            direct_text = _text(time_element[0])
            if direct_text:
                return direct_text
    return ""


def _extract_grant_and_publication(
    root: HtmlElement,
    patent_number: str,
) -> dict[str, str]:
    grant_date = _extract_date_via_dt(
        root, re.compile(f"Publication of {re.escape(patent_number)}")
    )
    publication_date = ""

    if not grant_date:
        grant_date = _extract_date_via_dt(root, re.compile("Application granted", re.IGNORECASE))

    publication_date = _extract_date_via_dt(root, re.compile("Publication date", re.IGNORECASE))

    if not grant_date:
        for event in _event_entries(root):
            title = (
                _text(event.xpath(".//span[@itemprop='title']")[0])
                if event.xpath(".//span[@itemprop='title']")
                else ""
            )
            lowered = title.lower()
            time_element = event.xpath(".//time")
            if not time_element:
                continue
            date_value = time_element[0].get("datetime") or _text(time_element[0])
            if not isinstance(date_value, str) or not date_value.strip():
                continue
            date_value = date_value.strip()
            if not grant_date and "application granted" in lowered:
                grant_date = date_value
            if not publication_date and (
                "publication" in lowered or "publicly available" in lowered
            ):
                publication_date = date_value

    if not publication_date:
        publication_date = grant_date

    return {
        "grant_date": grant_date or "",
        "publication_date": publication_date or "",
    }


def _extract_application_number(root: HtmlElement, page_text: str) -> str | None:
    direct = _first_text(root, "//dd[@itemprop='applicationNumber']")
    if direct:
        digits_only = re.sub(r"[^0-9]", "", direct)
        if len(digits_only) >= 8:
            series = digits_only[:2]
            serial = digits_only[2:8]
            formatted_serial = f"{serial[:3]},{serial[3:]}"
            return f"US {series}/{formatted_serial}"
        return direct.strip()

    filed_dt = _find_dt(root, re.compile("Application filed", re.IGNORECASE))
    if filed_dt is not None:
        digits_only = re.sub(r"[^0-9]", "", _dd_text(filed_dt))
        if len(digits_only) >= 8:
            series = digits_only[:2]
            serial = digits_only[2:8]
            formatted_serial = f"{serial[:3]},{serial[3:]}"
            return f"US {series}/{formatted_serial}"

    patterns = [
        r"Application\s+No\.?\s*(US\s*)?(\d{2})[\-/]?(\d{3})[, -]?(\d{3})",
        r"App\.?\s+No\.?\s*(US\s*)?(\d{2})[\-/]?(\d{3})[, -]?(\d{3})",
        r"Serial\s+No\.?\s*(US\s*)?(\d{2})[\-/]?(\d{3})[, -]?(\d{3})",
        r'applicationNumberText":"(\d{2})(\d{3})(\d{3})"',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_text)
        if match:
            groups = match.groups()
            if len(groups) >= 3:
                series_digits = groups[-3] or ""
                serial_first = groups[-2] or ""
                serial_second = groups[-1] or ""
                if series_digits and serial_first and serial_second:
                    return f"US {series_digits}/{serial_first},{serial_second}"
    return None


def _extract_pdf_url(root: HtmlElement) -> str | None:
    pdf_meta = _first_text(root, "//meta[@name='citation_pdf_url']/@content")
    if pdf_meta:
        return pdf_meta
    pdf_link = _first_attr(root, "//a[@itemprop='pdfLink']", "href")
    if pdf_link:
        return pdf_link
    first_pdf = _first_text(
        root,
        "//a[contains(@href, 'patentimages') and contains(@href, '.pdf')]/@href",
    )
    return first_pdf or None


def _extract_family_id(root: HtmlElement) -> str | None:
    """Extract the INPADOC family ID."""
    family_section = root.xpath("//section[@itemprop='family']")
    if not family_section:
        return None
    # Look for h2 containing "ID="
    h2_elements = family_section[0].xpath(".//h2")
    for h2 in h2_elements:
        text = _text(h2)
        if text.startswith("ID="):
            return text[3:]  # Remove "ID=" prefix
    return None


def _extract_cpc_classifications(root: HtmlElement) -> list[dict[str, str]]:
    """Extract CPC classification codes with descriptions."""
    classifications: list[dict[str, str]] = []
    seen: set[str] = set()

    code_elements = root.xpath("//*[@itemprop='Code']")
    for code_el in code_elements:
        code = _text(code_el)
        # Skip single-letter hierarchy codes and duplicates
        if len(code) <= 3 or code in seen:
            continue
        seen.add(code)

        # Get description from sibling element
        desc_el = code_el.xpath("following-sibling::span[@itemprop='Description']")
        description = _text(desc_el[0]) if desc_el else ""

        classifications.append({"code": code, "description": description})

    return classifications


def _extract_citations(root: HtmlElement, itemprop: str) -> list[dict[str, str | None]]:
    """Extract patent citations (backward or forward references)."""
    citations: list[dict[str, str | None]] = []

    rows = root.xpath(f"//tr[@itemprop='{itemprop}']")
    for row in rows:
        pub_num = row.xpath(".//span[@itemprop='publicationNumber']/text()")
        pub_date = row.xpath(".//td[@itemprop='publicationDate']/text()")
        assignee = row.xpath(".//span[@itemprop='assigneeOriginal']/text()")
        title = row.xpath(".//span[@itemprop='title']/text()")

        if pub_num:
            citations.append(
                {
                    "publication_number": pub_num[0].strip(),
                    "publication_date": pub_date[0].strip() if pub_date else None,
                    "assignee": assignee[0].strip() if assignee else None,
                    "title": title[0].strip() if title else None,
                }
            )

    return citations


def _extract_family_members(root: HtmlElement) -> list[dict[str, str | None]]:
    """Extract patent family members."""
    members: list[dict[str, str | None]] = []

    rows = root.xpath("//tr[@itemprop='applications']")
    for row in rows:
        app_num = row.xpath(".//span[@itemprop='applicationNumber']/text()")
        pub_num = row.xpath(".//span[@itemprop='representativePublication']/text()")
        status = row.xpath(".//span[@itemprop='ifiStatus']/text()")
        priority_date = row.xpath(".//td[@itemprop='priorityDate']/text()")
        filing_date = row.xpath(".//td[@itemprop='filingDate']/text()")
        title = row.xpath(".//td[@itemprop='title']/text()")

        if app_num:
            members.append(
                {
                    "application_number": app_num[0].strip(),
                    "publication_number": pub_num[0].strip() if pub_num else None,
                    "status": status[0].strip() if status else None,
                    "priority_date": priority_date[0].strip() if priority_date else None,
                    "filing_date": filing_date[0].strip() if filing_date else None,
                    "title": title[0].strip() if title else None,
                }
            )

    return members


def _extract_country_filings(root: HtmlElement) -> list[dict[str, str | int | None]]:
    """Extract country filings from the patent family."""
    filings: list[dict[str, str | int | None]] = []

    rows = root.xpath("//tr[@itemprop='countryStatus']")
    for row in rows:
        country = row.xpath(".//span[@itemprop='countryCode']/text()")
        count = row.xpath(".//span[@itemprop='num']/text()")
        rep_pub = row.xpath(".//span[@itemprop='representativePublication']/text()")

        if country:
            filings.append(
                {
                    "country_code": country[0].strip(),
                    "count": int(count[0].strip()) if count else 1,
                    "representative_publication": rep_pub[0].strip() if rep_pub else None,
                }
            )

    return filings


def _extract_similar_patents(root: HtmlElement) -> list[str]:
    """Extract similar patent document numbers."""
    similar: list[str] = []

    pub_nums = root.xpath(
        "//tr[@itemprop='similarDocuments']//span[@itemprop='publicationNumber']/text()"
    )
    for num in pub_nums:
        stripped = num.strip()
        if stripped:
            similar.append(stripped)

    return similar


def _extract_priority_applications(root: HtmlElement) -> list[dict[str, str | None]]:
    """Extract priority application claims."""
    priorities: list[dict[str, str | None]] = []

    rows = root.xpath("//tr[@itemprop='priorityApps']")
    for row in rows:
        app_num = row.xpath(".//span[@itemprop='applicationNumber']/text()")
        pub_num = row.xpath(".//span[@itemprop='representativePublication']/text()")
        priority_date = row.xpath(".//td[@itemprop='priorityDate']/text()")
        filing_date = row.xpath(".//td[@itemprop='filingDate']/text()")
        title = row.xpath(".//td[@itemprop='title']/text()")

        if app_num:
            priorities.append(
                {
                    "application_number": app_num[0].strip(),
                    "publication_number": pub_num[0].strip() if pub_num else None,
                    "priority_date": priority_date[0].strip() if priority_date else None,
                    "filing_date": filing_date[0].strip() if filing_date else None,
                    "title": title[0].strip() if title else None,
                }
            )

    return priorities


def _extract_legal_events(root: HtmlElement) -> list[dict[str, str | None]]:
    """Extract legal events (assignments, fee payments, status changes)."""
    events: list[dict[str, str | None]] = []

    # Events section contains dd elements with event data
    events_section = root.xpath("//section[@itemprop='events']")
    if not events_section:
        return events

    # Each dd element represents an event
    dd_elements = events_section[0].xpath(".//dd")
    for dd in dd_elements:
        # Get event date
        time_el = dd.xpath(".//time")
        event_date: str | None = None
        if time_el:
            datetime_attr = time_el[0].get("datetime")
            if isinstance(datetime_attr, str) and datetime_attr.strip():
                event_date = datetime_attr.strip()
            else:
                event_date = _text(time_el[0]) or None

        # Get event title/type
        title_el = dd.xpath(".//span[@itemprop='title']")
        title = _text(title_el[0]) if title_el else None

        # Get assignee info (for assignment events)
        assignee_el = dd.xpath(".//span[@itemprop='assigneeNew']")
        assignee = _text(assignee_el[0]) if assignee_el else None

        # Get assignor info (for assignment events)
        assignor_el = dd.xpath(".//span[@itemprop='assigneeOld']")
        assignor = _text(assignor_el[0]) if assignor_el else None

        # Get status info
        status_el = dd.xpath(".//span[@itemprop='status']")
        status = _text(status_el[0]) if status_el else None

        # Only include if we have at least a title or date
        if title or event_date:
            events.append(
                {
                    "date": event_date,
                    "title": title,
                    "assignee": assignee if assignee else None,
                    "assignor": assignor if assignor else None,
                    "status": status if status else None,
                }
            )

    return events


def _extract_non_patent_literature(root: HtmlElement) -> list[dict[str, str | None]]:
    """Extract non-patent literature citations."""
    npl: list[dict[str, str | None]] = []

    rows = root.xpath("//tr[@itemprop='backwardReferencesNpl']")
    for row in rows:
        # Get the citation text (usually in a td or span)
        citation_el = row.xpath(".//td[@class='npl-publication']/text()")
        if not citation_el:
            citation_el = row.xpath(".//td[1]/text()")

        citation = citation_el[0].strip() if citation_el else None

        # Try to extract examiner cited flag
        examiner_el = row.xpath(".//td[contains(@class, 'examiner')]")
        examiner_cited = bool(examiner_el)

        if citation:
            npl.append(
                {
                    "citation": citation,
                    "examiner_cited": "true" if examiner_cited else "false",
                }
            )

    return npl


def _extract_prior_art_keywords(root: HtmlElement) -> list[str]:
    """Extract prior art keywords from Google Patents."""
    keywords: list[str] = []

    # Prior art keywords are in a specific section
    keyword_els = root.xpath("//section[@itemprop='priorArtKeywords']//span[@itemprop='keyword']")
    for el in keyword_els:
        keyword = _text(el)
        if keyword:
            keywords.append(keyword)

    # Also check for keywords in the meta tags
    meta_keywords = root.xpath("//meta[@name='keywords']/@content")
    if meta_keywords and isinstance(meta_keywords[0], str):
        for kw in meta_keywords[0].split(","):
            stripped = kw.strip()
            if stripped and stripped not in keywords:
                keywords.append(stripped)

    return keywords


def _extract_concepts(root: HtmlElement) -> list[dict[str, str | None]]:
    """Extract Google's extracted concepts."""
    concepts: list[dict[str, str | None]] = []

    # Concepts section
    concept_els = root.xpath("//*[@itemprop='concept']")
    for el in concept_els:
        name_el = el.xpath(".//span[@itemprop='name']")
        name = _text(name_el[0]) if name_el else _text(el)

        # Get image/visual representation if available
        image_el = el.xpath(".//img/@src")
        image_url = image_el[0] if image_el and isinstance(image_el[0], str) else None

        if name:
            concepts.append(
                {
                    "name": name,
                    "image_url": image_url,
                }
            )

    return concepts


def _extract_landscapes(root: HtmlElement) -> list[dict[str, str]]:
    """Extract technology area classifications (landscapes)."""
    landscapes: list[dict[str, str]] = []

    landscape_els = root.xpath("//*[@itemprop='landscapes']")
    for el in landscape_els:
        name_el = el.xpath(".//span[@itemprop='name']")
        type_el = el.xpath(".//span[@itemprop='type']")

        name = _text(name_el[0]) if name_el else ""
        area_type = _text(type_el[0]) if type_el else ""

        if name:
            landscapes.append({"name": name, "type": area_type})

    return landscapes


def _extract_definitions(root: HtmlElement) -> list[dict[str, str]]:
    """Extract term definitions from the patent text."""
    definitions: list[dict[str, str]] = []

    def_els = root.xpath("//*[@itemprop='definitions']")
    for el in def_els:
        subject_el = el.xpath(".//span[@itemprop='subject']")
        definition_el = el.xpath(".//span[@itemprop='definition']")
        num_attr_el = el.xpath(".//meta[@itemprop='num_attr']/@content")

        subject = _text(subject_el[0]) if subject_el else ""
        definition = _text(definition_el[0]) if definition_el else ""
        paragraph = num_attr_el[0] if num_attr_el and isinstance(num_attr_el[0], str) else ""

        if subject and definition:
            definitions.append(
                {
                    "term": subject,
                    "definition": definition,
                    "paragraph": paragraph,
                }
            )

    return definitions


def _extract_child_applications(root: HtmlElement) -> list[dict[str, str | None]]:
    """Extract child applications (continuations, divisionals)."""
    children: list[dict[str, str | None]] = []

    rows = root.xpath("//tr[@itemprop='childApps']")
    for row in rows:
        app_num = row.xpath(".//span[@itemprop='applicationNumber']/text()")
        relation_type = row.xpath(".//span[@itemprop='relationType']/text()")
        pub_num = row.xpath(".//span[@itemprop='representativePublication']/text()")
        priority_date = row.xpath(".//td[@itemprop='priorityDate']/text()")
        filing_date = row.xpath(".//td[@itemprop='filingDate']/text()")
        title = row.xpath(".//td[@itemprop='title']/text()")

        if app_num:
            children.append(
                {
                    "application_number": app_num[0].strip(),
                    "relation_type": relation_type[0].strip() if relation_type else None,
                    "publication_number": pub_num[0].strip() if pub_num else None,
                    "priority_date": priority_date[0].strip() if priority_date else None,
                    "filing_date": filing_date[0].strip() if filing_date else None,
                    "title": title[0].strip() if title else None,
                }
            )

    return children


def _extract_apps_claiming_priority(root: HtmlElement) -> list[dict[str, str | None]]:
    """Extract applications claiming priority from this patent."""
    apps: list[dict[str, str | None]] = []

    rows = root.xpath("//tr[@itemprop='appsClaimingPriority']")
    for row in rows:
        app_num = row.xpath(".//span[@itemprop='applicationNumber']/text()")
        pub_num = row.xpath(".//span[@itemprop='representativePublication']/text()")
        priority_date = row.xpath(".//td[@itemprop='priorityDate']/text()")
        filing_date = row.xpath(".//td[@itemprop='filingDate']/text()")
        title = row.xpath(".//td[@itemprop='title']/text()")

        if app_num:
            apps.append(
                {
                    "application_number": app_num[0].strip(),
                    "publication_number": pub_num[0].strip() if pub_num else None,
                    "priority_date": priority_date[0].strip() if priority_date else None,
                    "filing_date": filing_date[0].strip() if filing_date else None,
                    "title": title[0].strip() if title else None,
                }
            )

    return apps


def _extract_detailed_npl(root: HtmlElement) -> list[dict[str, str | None]]:
    """Extract detailed non-patent literature with titles and links."""
    npl: list[dict[str, str | None]] = []

    rows = root.xpath("//tr[@itemprop='detailedNonPatentLiterature']")
    for row in rows:
        title_el = row.xpath(".//span[@itemprop='title']")
        if not title_el:
            continue

        # Get full text content
        title_text = _text(title_el[0])

        # Try to extract the link
        link_el = title_el[0].xpath(".//a/@href")
        link = link_el[0] if link_el and isinstance(link_el[0], str) else None

        if title_text:
            npl.append(
                {
                    "title": title_text,
                    "url": link,
                }
            )

    return npl


def _extract_kind_code(root: HtmlElement) -> str | None:
    """Extract the publication kind code (B1, B2, A1, etc.)."""
    kind_code = root.xpath("//meta[@itemprop='kindCode']/@content")
    if kind_code and isinstance(kind_code[0], str):
        return kind_code[0].strip()
    return None


def _extract_publication_description(root: HtmlElement) -> str | None:
    """Extract human-readable publication type description."""
    desc = root.xpath("//meta[@itemprop='publicationDescription']/@content")
    if desc and isinstance(desc[0], str):
        return desc[0].strip()
    return None


def _extract_citations_with_examiner(
    root: HtmlElement, itemprop: str
) -> list[dict[str, str | None | bool]]:
    """Extract patent citations with examiner-cited flag."""
    citations: list[dict[str, str | None | bool]] = []

    rows = root.xpath(f"//tr[@itemprop='{itemprop}']")
    for row in rows:
        pub_num = row.xpath(".//span[@itemprop='publicationNumber']/text()")
        pub_date = row.xpath(".//td[@itemprop='publicationDate']/text()")
        assignee = row.xpath(".//span[@itemprop='assigneeOriginal']/text()")
        title = row.xpath(".//span[@itemprop='title']/text()")
        examiner_cited = row.xpath(".//span[@itemprop='examinerCited']")

        if pub_num:
            citations.append(
                {
                    "publication_number": pub_num[0].strip(),
                    "publication_date": pub_date[0].strip() if pub_date else None,
                    "assignee": assignee[0].strip() if assignee else None,
                    "title": title[0].strip() if title else None,
                    "examiner_cited": bool(examiner_cited),
                }
            )

    return citations


def _extract_chemical_data(root: HtmlElement) -> list[dict[str, str | None]]:
    """Extract chemical compound data (SMILES, InChI keys)."""
    compounds: list[dict[str, str | None]] = []

    match_els = root.xpath("//*[@itemprop='match']")
    for el in match_els:
        compound_id = el.xpath(".//span[@itemprop='id']/text()")
        name = el.xpath(".//span[@itemprop='name']/text()")
        smiles = el.xpath(".//span[@itemprop='smiles']/text()")
        inchi_key = el.xpath(".//span[@itemprop='inchi_key']/text()")
        domain = el.xpath(".//span[@itemprop='domain']/text()")
        similarity = el.xpath(".//span[@itemprop='similarity']/text()")

        # Only include if there's actual chemical data
        smiles_val = smiles[0].strip() if smiles else None
        inchi_val = inchi_key[0].strip() if inchi_key else None

        if smiles_val or inchi_val:
            compounds.append(
                {
                    "id": compound_id[0].strip() if compound_id else None,
                    "name": name[0].strip() if name else None,
                    "smiles": smiles_val if smiles_val else None,
                    "inchi_key": inchi_val if inchi_val else None,
                    "domain": domain[0].strip() if domain else None,
                    "similarity": similarity[0].strip() if similarity else None,
                }
            )

    return compounds


def _extract_legal_status_category(root: HtmlElement) -> str | None:
    """Extract simplified legal status category (active/not_active)."""
    # Look for the current application's status
    this_app = root.xpath("//*[@itemprop='thisApp']")
    if this_app:
        parent = this_app[0].getparent()
        if parent is not None:
            status_cat = parent.xpath(".//span[@itemprop='legalStatusCat']/text()")
            if status_cat and isinstance(status_cat[0], str):
                return status_cat[0].strip()
    return None


def _extract_family_citations(root: HtmlElement, itemprop: str) -> list[dict[str, str | None]]:
    """Extract family-level patent citations."""
    citations: list[dict[str, str | None]] = []

    rows = root.xpath(f"//tr[@itemprop='{itemprop}']")
    for row in rows:
        pub_num = row.xpath(".//span[@itemprop='publicationNumber']/text()")
        pub_date = row.xpath(".//td[@itemprop='publicationDate']/text()")
        assignee = row.xpath(".//span[@itemprop='assigneeOriginal']/text()")
        title = row.xpath(".//span[@itemprop='title']/text()")

        if pub_num:
            citations.append(
                {
                    "publication_number": pub_num[0].strip(),
                    "publication_date": pub_date[0].strip() if pub_date else None,
                    "assignee": assignee[0].strip() if assignee else None,
                    "title": title[0].strip() if title else None,
                }
            )

    return citations


def _extract_external_links(root: HtmlElement) -> list[dict[str, str]]:
    """Extract external links to USPTO, Espacenet, Global Dossier, etc."""
    links: list[dict[str, str]] = []

    link_els = root.xpath("//*[@itemprop='links']")
    for el in link_els:
        link_id = el.xpath(".//meta[@itemprop='id']/@content")
        url = el.xpath(".//a[@itemprop='url']/@href")
        text = el.xpath(".//span[@itemprop='text']/text()")

        if url and isinstance(url[0], str):
            link_entry: dict[str, str] = {
                "url": url[0].strip(),
            }
            if link_id and isinstance(link_id[0], str):
                link_entry["id"] = link_id[0].strip()
            if text and isinstance(text[0], str):
                link_entry["name"] = text[0].strip()
            links.append(link_entry)

    return links


def _extract_original_assignee(root: HtmlElement) -> str | None:
    """Extract the original assignee (at time of filing)."""
    # Try itemprop first
    assignee = root.xpath("//dd[@itemprop='assigneeOriginal']/text()")
    if assignee and isinstance(assignee[0], str):
        return assignee[0].strip()

    # Fall back to dt/dd pattern
    dt = _find_dt(root, re.compile("Original Assignee", re.IGNORECASE))
    if dt is not None:
        return _dd_text(dt) or None

    return None


def extract_metadata(
    root: HtmlElement,
    raw_html: str,
    *,
    patent_number: str,
) -> PatentMetadata:
    """Return a dictionary of metadata fields parsed from the HTML tree."""

    metadata: PatentMetadata = {
        "title": _extract_title(root),
        "abstract": _extract_abstract(root),
        "description": _extract_description(root),
        "description_html": _extract_description_html(root),
        "current_assignee": _extract_current_assignee(root),
        "original_assignee": _extract_original_assignee(root),
        # Original language fields
        "original_title": _extract_original_title(root),
        "original_abstract": _extract_original_abstract(root),
        "inventors": _extract_inventors(root),
        "status": _extract_status(root),
        "filing_date": _extract_date_via_dt(root, re.compile("Filing date", re.IGNORECASE)),
        "priority_date": _extract_date_via_dt(root, re.compile("Priority date", re.IGNORECASE)),
        "grant_date": "",
        "publication_date": "",
        "expiration_date": _extract_expiration(root),
        "pdf_url": _extract_pdf_url(root),
        "application_number": None,
        # Publication metadata
        "kind_code": _extract_kind_code(root),
        "publication_description": _extract_publication_description(root),
        "legal_status_category": _extract_legal_status_category(root),
        # Family and classification fields
        "family_id": _extract_family_id(root),
        "cpc_classifications": _extract_cpc_classifications(root),
        "landscapes": _extract_landscapes(root),
        "cited_patents": _extract_citations_with_examiner(root, "backwardReferencesOrig"),
        "citing_patents": _extract_citations_with_examiner(root, "forwardReferencesOrig"),
        "cited_patents_family": _extract_family_citations(root, "backwardReferencesFamily"),
        "citing_patents_family": _extract_family_citations(root, "forwardReferencesFamily"),
        "family_members": _extract_family_members(root),
        "country_filings": _extract_country_filings(root),
        "similar_patents": _extract_similar_patents(root),
        "priority_applications": _extract_priority_applications(root),
        "child_applications": _extract_child_applications(root),
        "apps_claiming_priority": _extract_apps_claiming_priority(root),
        # Legal events and literature fields
        "legal_events": _extract_legal_events(root),
        "non_patent_literature": _extract_non_patent_literature(root),
        "detailed_non_patent_literature": _extract_detailed_npl(root),
        "prior_art_keywords": _extract_prior_art_keywords(root),
        "concepts": _extract_concepts(root),
        "definitions": _extract_definitions(root),
        "chemical_data": _extract_chemical_data(root),
        # External resources
        "external_links": _extract_external_links(root),
    }

    metadata["application_number"] = _extract_application_number(root, raw_html)

    dates = _extract_grant_and_publication(root, patent_number)
    metadata["grant_date"] = dates["grant_date"]
    metadata["publication_date"] = dates["publication_date"]

    if not metadata["filing_date"]:
        metadata["filing_date"] = metadata["priority_date"] or ""

    return metadata


class PatentMetadata(TypedDict):
    title: str
    abstract: str
    description: str
    description_html: str | None
    current_assignee: str
    original_assignee: str | None
    # Original language fields (for non-English patents)
    original_title: str | None
    original_abstract: str | None
    inventors: list[str]
    status: str
    filing_date: str
    priority_date: str
    grant_date: str
    publication_date: str
    expiration_date: str
    pdf_url: str | None
    application_number: str | None
    # Publication metadata
    kind_code: str | None
    publication_description: str | None
    legal_status_category: str | None
    # Family and classification fields
    family_id: str | None
    cpc_classifications: list[dict[str, str]]
    landscapes: list[dict[str, str]]
    cited_patents: list[dict[str, str | None | bool]]
    citing_patents: list[dict[str, str | None | bool]]
    cited_patents_family: list[dict[str, str | None]]
    citing_patents_family: list[dict[str, str | None]]
    family_members: list[dict[str, str | None]]
    country_filings: list[dict[str, str | int | None]]
    similar_patents: list[str]
    priority_applications: list[dict[str, str | None]]
    child_applications: list[dict[str, str | None]]
    apps_claiming_priority: list[dict[str, str | None]]
    # Legal events and literature fields
    legal_events: list[dict[str, str | None]]
    non_patent_literature: list[dict[str, str | None]]
    detailed_non_patent_literature: list[dict[str, str | None]]
    prior_art_keywords: list[str]
    concepts: list[dict[str, str | None]]
    definitions: list[dict[str, str]]
    chemical_data: list[dict[str, str | None]]
    # External resources
    external_links: list[dict[str, str]]
