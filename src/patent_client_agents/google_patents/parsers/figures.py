"""HTML parsing helpers for Google Patents figure metadata."""

from __future__ import annotations

import re
from typing import Any

from lxml.html import HtmlElement

_FIGURE_ITEMS_XPATH = "//li[@itemprop='images']"


def _absolute_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    if cleaned.startswith("//"):
        return f"https:{cleaned}"
    if cleaned.startswith("/"):
        return f"https://patents.google.com{cleaned}"
    return cleaned


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _extract_image_id(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").split("/")[-1]


def _extract_bounds(callout: HtmlElement) -> dict[str, int | None]:
    bounds: dict[str, int | None] = {"left": None, "top": None, "right": None, "bottom": None}
    span = callout.xpath(".//span[@itemprop='bounds']")
    if not span:
        return bounds
    container = span[0]
    for key in ("left", "top", "right", "bottom"):
        values = container.xpath(f"./meta[@itemprop='{key}']/@content")
        bounds[key] = _parse_int(values[0]) if values else None
    return bounds


def _infer_page_number(node: HtmlElement, url: str | None) -> int | None:
    page_values = node.xpath(".//meta[@itemprop='figurePage']/@content")
    for value in page_values:
        parsed = _parse_int(value)
        if parsed is not None:
            return parsed
    identifier = _extract_image_id(url)
    if identifier:
        match = re.search(r"-D0*([0-9]+)", identifier)
        if match:
            parsed = _parse_int(match.group(1))
            if parsed is not None:
                return parsed
    return None


def _extract_callouts(node: HtmlElement) -> list[dict[str, Any]]:
    callouts: list[dict[str, Any]] = []
    for callout in node.xpath(".//li[@itemprop='callouts']"):
        figure_page = _parse_int(
            next(iter(callout.xpath("./meta[@itemprop='figurePage']/@content")), None)
        )
        reference_id = next(iter(callout.xpath("./meta[@itemprop='id']/@content")), None)
        label = next(iter(callout.xpath("./meta[@itemprop='label']/@content")), None)
        bounds = _extract_bounds(callout)
        callouts.append(
            {
                "figure_page": figure_page,
                "reference_id": reference_id.strip() if reference_id else None,
                "label": label.strip() if label else None,
                "bounds": bounds,
            }
        )
    return callouts


def extract_figures(root: HtmlElement) -> list[dict[str, Any]]:
    """Return metadata for each figure image present in the document."""

    figures: list[dict[str, Any]] = []
    for index, node in enumerate(root.xpath(_FIGURE_ITEMS_XPATH)):
        thumbnail = _absolute_url(
            next(iter(node.xpath(".//img[@itemprop='thumbnail']/@src")), None)
        )
        full = _absolute_url(next(iter(node.xpath(".//meta[@itemprop='full']/@content")), None))
        if not thumbnail and not full:
            continue
        page_number = _infer_page_number(node, full or thumbnail)
        image_id = _extract_image_id(full or thumbnail)
        callouts = _extract_callouts(node)
        figures.append(
            {
                "index": index,
                "page_number": page_number,
                "image_id": image_id,
                "thumbnail_url": thumbnail,
                "full_image_url": full or thumbnail,
                "callouts": callouts,
            }
        )
    return figures
