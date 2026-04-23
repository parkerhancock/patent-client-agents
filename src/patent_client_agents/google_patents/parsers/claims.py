"""lxml-based helpers for parsing Google Patents claims."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from lxml import html
from lxml.html import HtmlElement

logger = logging.getLogger(__name__)


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_original_text(element: HtmlElement) -> str | None:
    """Extract original language text from google-src-text spans.

    Google Patents wraps original (non-English) text in:
    <span class="google-src-text">original text here</span>

    Returns None if no original text spans are found (English patents).
    """
    src_spans = element.xpath(".//span[@class='google-src-text']")
    if not src_spans:
        return None

    # Collect text from all google-src-text spans
    parts: list[str] = []
    for span in src_spans:
        text = span.text_content()
        if text:
            parts.append(_normalize_spaces(text))

    if not parts:
        return None

    return " ".join(parts)


def _extract_translated_text(element: HtmlElement) -> str:
    """Extract translated text, excluding google-src-text spans.

    For patents with translations, this returns only the English text.
    For English patents, returns all text.
    """
    # Clone the element to avoid modifying the original
    from copy import deepcopy

    element_copy = deepcopy(element)

    # Remove all google-src-text spans from the copy
    for span in element_copy.xpath(".//span[@class='google-src-text']"):
        span.getparent().remove(span)

    # Also remove the "notranslate" wrapper spans that contain both
    for span in element_copy.xpath(".//span[@class='notranslate']"):
        # Replace span with its children
        parent = span.getparent()
        if parent is not None:
            index = parent.index(span)
            for child in reversed(list(span)):
                parent.insert(index, child)
            if span.tail:
                prev = span.getprevious()
                if prev is not None:
                    prev.tail = (prev.tail or "") + span.tail
                else:
                    parent.text = (parent.text or "") + span.tail
            parent.remove(span)

    return _normalize_spaces(element_copy.text_content())


def _strip_leading_number(value: str) -> str:
    cleaned = re.sub(r"^\d+\.\s*", "", value)
    cleaned = cleaned.replace(" ,", ",").replace(" ;", ";")
    return cleaned.strip()


def _split_long_limitations(text: str) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    words = cleaned.split()
    if len(words) <= 50:
        return [cleaned]

    parts = re.split(r",\s*wherein\b", cleaned, flags=re.IGNORECASE)
    if len(parts) == 1:
        return [cleaned]

    results: list[str] = []
    for index, part in enumerate(parts):
        segment = part.strip()
        if not segment:
            continue
        if index > 0 and not segment.lower().startswith("wherein"):
            segment = f"wherein {segment}"
        results.append(segment)
    return results or [cleaned]


def _has_class(element: HtmlElement, class_name: str) -> bool:
    classes = element.get("class", "")
    return class_name in classes.split()


def _direct_text_before_nested(text_div: HtmlElement) -> str:
    parts: list[str] = []
    if text_div.text and text_div.text.strip():
        parts.append(text_div.text.strip())

    for child in text_div:
        tag_name = child.tag if isinstance(child.tag, str) else ""
        if tag_name.lower() == "div" and _has_class(child, "claim-text"):
            break
        child_text = child.text_content().strip()
        if child_text:
            parts.append(child_text)
        if child.tail and child.tail.strip():
            parts.append(child.tail.strip())
    return _normalize_spaces(" ".join(parts))


def _leaf_claim_texts(text_div: HtmlElement) -> Iterable[str]:
    leaf_nodes = text_div.xpath(
        ".//div[contains(concat(' ', normalize-space(@class), ' '), ' claim-text ')]"
        "[not(.//div[contains(concat(' ', normalize-space(@class), ' '), ' claim-text ')])]"
    )
    for leaf in leaf_nodes:
        text = _normalize_spaces(leaf.text_content())
        if text:
            yield text


def _extract_limitations(claim_div: HtmlElement) -> list[str]:
    """Extract ALL limitations including intermediate structural nodes.

    This function recursively processes nested claim-text divs to capture
    the complete hierarchical structure, including intermediate nodes like
    "a first chip comprising:" that were previously skipped.

    Fixed: Previously only extracted preamble + leaf nodes, missing intermediate
    structural elements in hierarchical claims.
    """
    # Try <div class="claim-text"> first, then <claim-text> elements
    text_divs = claim_div.xpath(
        "./div[contains(concat(' ', normalize-space(@class), ' '), ' claim-text ')]"
    )
    if not text_divs:
        # Try <claim-text> elements directly (newer structure)
        text_divs = claim_div.xpath("./claim-text")

    if not text_divs:
        return _split_long_limitations(_normalize_spaces(claim_div.text_content()))

    limitations: list[str] = []
    for text_div in text_divs:
        # Get the direct text of this node (before any nested divs)
        # This captures the text at THIS level, which could be:
        # - A preamble ("1. An apparatus comprising:")
        # - An intermediate structural element ("a first chip comprising:")
        # - A leaf limitation ("a plurality of first active circuits...")
        direct_text = _direct_text_before_nested(text_div)
        if direct_text:
            limitations.append(direct_text)

        # Check for nested claim-text divs or elements
        nested = text_div.xpath(
            "./div[contains(concat(' ', normalize-space(@class), ' '), ' claim-text ')]"
        )
        if not nested:
            nested = text_div.xpath("./claim-text")

        if nested:
            # Recursively process each nested div
            # This ensures we capture ALL levels of hierarchy
            for nested_div in nested:
                limitations.extend(_extract_limitations_recursive(nested_div))
        # Note: If there are no nested divs, we've already captured the text above

    cleaned: list[str] = []
    for limitation in limitations:
        cleaned.extend(_split_long_limitations(_strip_leading_number(limitation)))
    return cleaned


def _extract_limitations_recursive(text_div: HtmlElement) -> list[str]:
    """Helper function to recursively extract limitations from nested divs.

    This is called by _extract_limitations to process nested claim-text divs.
    """
    limitations: list[str] = []

    # Get direct text at this level
    direct_text = _direct_text_before_nested(text_div)
    if direct_text:
        limitations.append(direct_text)

    # Process any nested claim-text divs or elements
    nested = text_div.xpath(
        "./div[contains(concat(' ', normalize-space(@class), ' '), ' claim-text ')]"
    )
    if not nested:
        nested = text_div.xpath("./claim-text")

    for nested_div in nested:
        limitations.extend(_extract_limitations_recursive(nested_div))

    return limitations


def _to_root(document: HtmlElement | str) -> HtmlElement:
    if isinstance(document, HtmlElement):
        return document
    return html.fromstring(document)


def extract_claims(
    document: HtmlElement | str,
) -> tuple[list[dict[str, str | None]], dict[str, list[str]], dict[str, list[str]]]:
    """Extract claim dictionaries and structured limitations from HTML content.

    Returns:
        Tuple of:
        - claims: List of claim dicts with number, text, original_text, type, depends_on
        - structured_limitations: Dict mapping claim number to list of limitation strings
        - original_limitations: Dict mapping claim number to list of original language limitations
    """

    root = _to_root(document)

    # Try multiple container selectors (Google Patents uses different structures)
    claims_container = root.xpath(
        "//div[contains(concat(' ', normalize-space(@class), ' '), ' claims ')]"
    )
    if not claims_container:
        # Try section with itemprop="claims" (newer structure)
        claims_container = root.xpath("//section[@itemprop='claims']")

    if not claims_container:
        logger.info("No claims section found in patent HTML")
        return [], {}, {}

    container = claims_container[0]

    # Try multiple claim element selectors
    claim_elements = container.xpath(
        ".//div[contains(concat(' ', normalize-space(@class), ' '), ' claim ')][@num]"
    )
    if not claim_elements:
        # Try <claim> elements directly (newer structure)
        claim_elements = container.xpath(".//claim[@num]")

    claims: list[dict[str, str | None]] = []
    structured_limitations: dict[str, list[str]] = {}
    original_limitations: dict[str, list[str]] = {}

    for claim_element in claim_elements:
        raw_number = claim_element.get("num") or ""
        if isinstance(raw_number, list):
            raw_number = raw_number[0] if raw_number else ""
        claim_number = str(raw_number).lstrip("0").strip()
        if not claim_number:
            continue

        # Extract original language text (if present)
        original_text = _extract_original_text(claim_element)
        if original_text:
            original_text = _strip_leading_number(original_text)

        # For patents with translations, get only the translated text
        # For English patents, this gets all text (same as before)
        if original_text:
            full_text = _strip_leading_number(_extract_translated_text(claim_element))
        else:
            full_text = _strip_leading_number(_normalize_spaces(claim_element.text_content()))

        # Determine dependency from claim-ref elements
        depends_on: str | None = None
        id_refs = claim_element.xpath(".//claim-ref/@idref")
        if id_refs:
            first_ref = id_refs[0]
            if isinstance(first_ref, str) and first_ref.startswith("CLM-"):
                depends_on = first_ref.replace("CLM-", "").lstrip("0")

        # Determine claim type from class attribute or dependency
        class_attr = claim_element.get("class", "")
        if "child" in class_attr.split():
            claim_type = "dependent"
        elif depends_on:
            claim_type = "dependent"
        else:
            claim_type = "independent"

        claims.append(
            {
                "number": claim_number,
                "text": full_text,
                "original_text": original_text,
                "type": claim_type,
                "depends_on": depends_on,
            }
        )

        # Extract limitations (translated)
        limitations = _extract_limitations(claim_element)
        structured_limitations[claim_number] = [item for item in limitations if item]

        # Extract original language limitations if available
        if original_text:
            orig_lims = _extract_original_limitations(claim_element)
            original_limitations[claim_number] = [item for item in orig_lims if item]

    return claims, structured_limitations, original_limitations


def _extract_original_limitations(claim_element: HtmlElement) -> list[str]:
    """Extract limitations from original language text spans."""
    limitations: list[str] = []

    # Find all claim-text divs or elements
    text_divs = claim_element.xpath(
        ".//div[contains(concat(' ', normalize-space(@class), ' '), ' claim-text ')]"
    )
    if not text_divs:
        text_divs = claim_element.xpath(".//claim-text")

    for text_div in text_divs:
        original = _extract_original_text(text_div)
        if original:
            # Strip leading claim number if present
            cleaned = _strip_leading_number(original)
            if cleaned:
                limitations.append(cleaned)

    return limitations
