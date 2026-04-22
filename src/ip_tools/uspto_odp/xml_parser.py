"""Parse USPTO ODP ST.96 XML documents into structured data.

Handles three document types from the ODP file wrapper XML archive:

- **CLM** (Claims): Parsed into structured claim objects with dependency info.
- **SPEC** (Specification): Converted to markdown text with section headings.
- **ABST** (Abstract): Extracted as plain text.

Other document types (NOA, CTRS, REM, IDS, etc.) are converted to markdown
on a best-effort basis using the same heading/paragraph logic as SPEC.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET


def _strip_ns(tag: str) -> str:
    """Remove XML namespace prefix from a tag name."""
    return tag.split("}")[-1] if "}" in tag else tag


def _iter_text(el: ET.Element) -> str:
    """Recursively extract all text content from an element, ignoring tags."""
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        tag = _strip_ns(child.tag)
        # Skip noise elements
        if tag in ("BoundaryDataReference", "OCRConfidenceData"):
            if child.tail:
                parts.append(child.tail)
            continue
        parts.append(_iter_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


_CLAIM_INDENT = "    "  # 4 spaces per nesting level


def _join_inline(existing: str, fragment: str) -> str:
    """Join a text fragment to an existing line, suppressing the space before punctuation."""
    if fragment and fragment[0] in ".,;:!?)]}":
        return existing + fragment
    return existing + " " + fragment


def _collect_claim_lines(ct_el: ET.Element, depth: int, nested_tag: str) -> list[str]:
    """Recursively collect text from nested claim-text elements.

    ``nested_tag`` is the name of the nested element that triggers a new
    indentation level: ``ClaimText`` for ST.96, ``claim-text`` for grant XML.
    Each nesting level is indented by 4 spaces.
    """
    lines: list[str] = []
    own = (ct_el.text or "").strip()
    if own:
        lines.append(_CLAIM_INDENT * depth + own)

    def _append_inline(text: str) -> None:
        if not text:
            return
        if lines:
            lines[-1] = _join_inline(lines[-1], text)
        else:
            lines.append(_CLAIM_INDENT * depth + text)

    for child in ct_el:
        tag = _strip_ns(child.tag)
        if tag == nested_tag:
            lines.extend(_collect_claim_lines(child, depth + 1, nested_tag))
        else:
            _append_inline(_iter_text(child).strip())
        _append_inline((child.tail or "").strip())
    return lines


def _parse_clm_idref(idref: str) -> int | None:
    """Parse a ``CLM-00001`` idref into an integer claim number."""
    if not idref.startswith("CLM-"):
        return None
    stripped = idref.replace("CLM-", "").lstrip("0")
    try:
        return int(stripped)
    except ValueError:
        return None


def parse_claims_xml(xml_text: str) -> dict[str, Any]:
    """Parse a CLM (Claims) ST.96 XML document.

    Returns a dict with document metadata and a ``claims`` list where each
    claim has ``claim_number``, ``claim_text``, ``claim_type``, and
    ``depends_on`` — matching the Google Patents claim shape.
    """
    root = ET.fromstring(xml_text)

    # --- metadata ---
    meta: dict[str, Any] = {}
    for el in root:
        tag = _strip_ns(el.tag)
        if tag == "DocumentMetadata":
            for child in el:
                ctag = _strip_ns(child.tag)
                if ctag == "ApplicationNumberText":
                    meta["applicationNumber"] = (child.text or "").strip()
                elif ctag == "OfficialDate":
                    meta["officialDate"] = (child.text or "").strip()
                elif ctag == "PageTotalQuantity":
                    meta["pageTotalQuantity"] = int(child.text or 0)
                elif ctag == "DocumentCode":
                    meta["documentCode"] = (child.text or "").strip()

    # --- claim statement (e.g. "WHAT IS CLAIMED IS:") ---
    claim_statement: str | None = None
    for el in root.iter():
        if _strip_ns(el.tag) == "ClaimStatement":
            claim_statement = _iter_text(el).strip()
            break

    # --- claims ---
    claims: list[dict[str, Any]] = []
    for claim_el in root.iter():
        if _strip_ns(claim_el.tag) != "Claim":
            continue

        claim_number: int | None = None
        lines_for_claim: list[str] = []
        depends_on: int | None = None

        for child in claim_el:
            ctag = _strip_ns(child.tag)
            if ctag == "ClaimNumber":
                try:
                    claim_number = int((child.text or "").strip())
                except ValueError:
                    claim_number = None
            elif ctag == "ClaimText":
                lines_for_claim.extend(_collect_claim_lines(child, depth=0, nested_tag="ClaimText"))
                # Check for ClaimReference inside this ClaimText
                if depends_on is None:
                    for ref in child.iter():
                        if _strip_ns(ref.tag) != "ClaimReference":
                            continue
                        idrefs = next(
                            (v for k, v in ref.attrib.items() if _strip_ns(k) == "idrefs"),
                            "",
                        )
                        parsed = _parse_clm_idref(idrefs) if idrefs else None
                        if parsed is not None:
                            depends_on = parsed
                            break

        claim_text = "\n".join(lines_for_claim).strip()

        claims.append(
            {
                "claim_number": claim_number,
                "claim_text": claim_text,
                "claim_type": "dependent" if depends_on else "independent",
                "depends_on": depends_on,
            }
        )

    return {
        **meta,
        "claimStatement": claim_statement,
        "claims": claims,
    }


def parse_grant_claims_xml(xml_text: str) -> list[dict[str, Any]]:
    """Parse patent claims from a USPTO patent grant XML file.

    Grant XML uses the older DTD format with lowercase hyphenated tags
    (``<claim>``, ``<claim-text>``, ``<claim-ref>``) rather than the ST.96
    PascalCase tags. Returns a list of claim dicts matching the same shape
    as ``parse_claims_xml``.
    """
    import re

    root = ET.fromstring(xml_text)
    claims: list[dict[str, Any]] = []

    for claim_el in root.iter():
        if _strip_ns(claim_el.tag) != "claim":
            continue

        lines_for_claim: list[str] = []
        for ct in claim_el:
            if _strip_ns(ct.tag) == "claim-text":
                lines_for_claim.extend(_collect_claim_lines(ct, depth=0, nested_tag="claim-text"))
        claim_text = "\n".join(lines_for_claim).strip()
        if not claim_text:
            continue

        raw_num = claim_el.get("num") or claim_el.get("id") or ""
        num_str = re.sub(r"\D", "", raw_num)
        claim_number = int(num_str) if num_str else len(claims) + 1

        depends_on: int | None = None
        for ref in claim_el.iter():
            if _strip_ns(ref.tag) == "claim-ref":
                parsed = _parse_clm_idref(ref.get("idref", ""))
                if parsed is not None:
                    depends_on = parsed
                    break

        claims.append(
            {
                "claim_number": claim_number,
                "claim_text": claim_text,
                "claim_type": "dependent" if depends_on else "independent",
                "depends_on": depends_on,
            }
        )

    return claims


def parse_spec_xml(xml_text: str) -> dict[str, Any]:
    """Parse a SPEC (Specification) or ABST (Abstract) ST.96 XML document.

    Returns a dict with document metadata and a ``description`` field
    containing the full text as markdown.
    """
    root = ET.fromstring(xml_text)

    # --- metadata ---
    meta: dict[str, Any] = {}
    for el in root:
        tag = _strip_ns(el.tag)
        if tag == "DocumentMetadata":
            for child in el:
                ctag = _strip_ns(child.tag)
                if ctag == "ApplicationNumberText":
                    meta["applicationNumber"] = (child.text or "").strip()
                elif ctag == "OfficialDate":
                    meta["officialDate"] = (child.text or "").strip()
                elif ctag == "PageTotalQuantity":
                    meta["pageTotalQuantity"] = int(child.text or 0)
                elif ctag == "ParagraphTotalQuantity":
                    meta["paragraphTotalQuantity"] = int(child.text or 0)
                elif ctag == "DocumentCode":
                    meta["documentCode"] = (child.text or "").strip()

    # --- convert body to markdown ---
    md_parts: list[str] = []
    seen_text: set[str] = set()  # deduplicate

    for el in root:
        tag = _strip_ns(el.tag)

        if tag == "Heading":
            heading = _iter_text(el).strip()
            if heading and heading not in seen_text:
                seen_text.add(heading)
                md_parts.append(f"\n## {heading}\n")

        elif tag == "P":
            text = _iter_text(el).strip()
            if not text or text in seen_text:
                continue
            seen_text.add(text)
            md_parts.append(text + "\n")

        elif tag == "Image":
            # Note image references without embedding
            filename = None
            for child in el:
                if _strip_ns(child.tag) == "FileName":
                    filename = (child.text or "").strip()
            if filename:
                md_parts.append(f"\n[Figure: {filename}]\n")

    description = "\n".join(md_parts).strip()

    return {
        **meta,
        "description": description,
    }


def parse_document_xml(xml_text: str) -> dict[str, Any]:
    """Auto-detect document type and parse accordingly.

    Dispatches to ``parse_claims_xml`` for CLM documents and
    ``parse_spec_xml`` for everything else (SPEC, ABST, etc.).
    """
    # Peek at the root tag to detect document type
    root = ET.fromstring(xml_text)
    root_tag = _strip_ns(root.tag)

    if root_tag == "ClaimsDocument":
        return parse_claims_xml(xml_text)

    # SPEC, ABST, and other document types all use the same
    # heading/paragraph structure
    return parse_spec_xml(xml_text)
