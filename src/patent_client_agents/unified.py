"""Cross-source fused helpers.

Patent-client-agents exposes two kinds of APIs:

* **Source-specific clients** in each submodule (``google_patents``,
  ``uspto_odp``, ``uspto_publications``, ``epo_ops``, …). These mirror a
  single upstream service one-to-one.
* **Fused helpers** in this module. These cascade across multiple upstream
  services to deliver a canonical shape regardless of which backend served
  the data.

The MCP tool layer is a thin wrapper over this module; keep behavior here
and the MCP surface stays trivial to maintain.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

from law_tools_core.exceptions import LawToolsCoreError, NotFoundError

logger = logging.getLogger(__name__)

__all__ = [
    "PatentPdf",
    "build_canonical_claim",
    "download_patent_pdf",
    "get_patent_claims",
    "google_limitations_from_html",
    "odp_limitations_from_text",
]


# ---------------------------------------------------------------------------
# Claims: canonical shape + per-source extractors
# ---------------------------------------------------------------------------


def odp_limitations_from_text(claim_text: str) -> list[dict[str, Any]]:
    """Parse ODP's 4-space-indented claim text into ``[{"text", "depth"}]`` tuples.

    The grant-XML-derived ``claim_text`` preserves tree structure via leading
    spaces (4 per nesting level). Empirically verified to produce the same
    limitation boundaries and depth sequence as Google Patents' nested
    ``<claim-text>`` divs (experiment 2026-04-23 on US10000000B2).
    """
    result: list[dict[str, Any]] = []
    for line in claim_text.split("\n"):
        if not line.strip():
            continue
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        depth = indent // 4
        text = stripped.rstrip()
        if depth == 0 and text[:1].isdigit():
            dot_idx = text.find(". ")
            if dot_idx > 0 and text[:dot_idx].isdigit():
                text = text[dot_idx + 2 :]
        result.append({"text": text.strip(), "depth": depth})
    return result


def google_limitations_from_html(raw_html: str) -> dict[int, dict[str, Any]]:
    """Walk Google Patents HTML and extract per-claim limitations with depth.

    Returns ``{claim_number: {"limitations": [{text, depth}], "claim_type": str,
    "depends_on": int | None}}``. Depth comes from the nested
    ``<claim-text>`` / ``<div class="claim-text">`` element tree.
    """
    from lxml import html as _html

    from patent_client_agents.google_patents.parsers.claims import (
        _direct_text_before_nested,
        _strip_leading_number,
    )

    root = _html.fromstring(raw_html)
    claim_elements = root.xpath(
        "//claim[@num] | //div[contains(concat(' ', normalize-space(@class), ' '), ' claim ')][@num]"
    )

    def _walk_inner(node: Any, depth: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        direct = _direct_text_before_nested(node)
        if direct:
            result.append({"text": direct, "depth": depth})
        deeper = node.xpath(
            "./div[contains(concat(' ', normalize-space(@class), ' '), ' claim-text ')]"
        )
        if not deeper:
            deeper = node.xpath("./claim-text")
        for sub in deeper:
            result.extend(_walk_inner(sub, depth + 1))
        return result

    def _walk_claim(claim_node: Any) -> list[dict[str, Any]]:
        nested = claim_node.xpath(
            "./div[contains(concat(' ', normalize-space(@class), ' '), ' claim-text ')]"
        )
        if not nested:
            nested = claim_node.xpath("./claim-text")
        out: list[dict[str, Any]] = []
        for child in nested:
            direct = _direct_text_before_nested(child)
            if direct:
                out.append({"text": _strip_leading_number(direct), "depth": 0})
            deeper = child.xpath(
                "./div[contains(concat(' ', normalize-space(@class), ' '), ' claim-text ')]"
            )
            if not deeper:
                deeper = child.xpath("./claim-text")
            for sub in deeper:
                out.extend(_walk_inner(sub, 1))
        return out

    by_number: dict[int, dict[str, Any]] = {}
    for ce in claim_elements:
        num_raw = (ce.get("num") or "").lstrip("0")
        try:
            number = int(num_raw)
        except ValueError:
            continue
        limitations = _walk_claim(ce)
        id_refs = ce.xpath(".//claim-ref/@idref")
        depends_on: int | None = None
        if id_refs:
            first_ref = id_refs[0]
            if isinstance(first_ref, str) and first_ref.startswith("CLM-"):
                try:
                    depends_on = int(first_ref.replace("CLM-", "").lstrip("0"))
                except ValueError:
                    depends_on = None
        class_attr = ce.get("class", "") or ""
        claim_type = "dependent" if ("child" in class_attr.split() or depends_on) else "independent"
        by_number[number] = {
            "limitations": limitations,
            "claim_type": claim_type,
            "depends_on": depends_on,
        }
    return by_number


def build_canonical_claim(
    claim_number: int,
    limitations: list[dict[str, Any]],
    claim_type: str,
    depends_on: int | None,
) -> dict[str, Any]:
    """Normalize a single claim into the canonical shape.

    ``claim_text`` is rebuilt from ``limitations`` so the output is
    byte-identical regardless of whether the source was ODP grant XML or
    Google Patents HTML.
    """
    indented = "\n".join(("    " * lim["depth"]) + lim["text"] for lim in limitations)
    claim_text = f"{claim_number}. {indented}" if indented else f"{claim_number}. "
    return {
        "claim_number": claim_number,
        "limitations": limitations,
        "claim_text": claim_text,
        "claim_type": claim_type,
        "depends_on": depends_on,
    }


async def get_patent_claims(patent_number: str) -> list[dict[str, Any]]:
    """Fetch canonical claims for a patent.

    Cascades two sources:

    1. USPTO ODP grant XML (authoritative for US patents post-~2000)
    2. Google Patents HTML (worldwide fallback, including pre-2000 US patents)

    Returns a list of claims in the canonical shape produced by
    :func:`build_canonical_claim`. Raises :class:`NotFoundError` if neither
    source has the patent.
    """
    from patent_client_agents.google_patents import GooglePatentsClient
    from patent_client_agents.uspto_odp.clients.applications import ApplicationsClient

    if patent_number.strip().upper().startswith("US"):
        try:
            async with ApplicationsClient() as odp:
                odp_claims = await odp.get_granted_claims(patent_number)
            if odp_claims:
                return [
                    build_canonical_claim(
                        claim_number=c["claim_number"],
                        limitations=odp_limitations_from_text(c["claim_text"]),
                        claim_type=c["claim_type"],
                        depends_on=c["depends_on"],
                    )
                    for c in odp_claims
                ]
        except LawToolsCoreError as exc:
            logger.info("ODP grant XML unavailable for %s: %s", patent_number, exc)

    async with GooglePatentsClient() as client:
        patent = await client._get_patent_data(patent_number)
    if patent is None or not patent.raw_html:
        raise NotFoundError(f"Claims not found for patent {patent_number}")
    by_number = google_limitations_from_html(patent.raw_html)
    if not by_number:
        raise NotFoundError(f"Claims not found for patent {patent_number}")
    return [
        build_canonical_claim(
            claim_number=num,
            limitations=data["limitations"],
            claim_type=data["claim_type"],
            depends_on=data["depends_on"],
        )
        for num, data in sorted(by_number.items())
    ]


# ---------------------------------------------------------------------------
# PDF download: Google → PPUBS → EPO cascade
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatentPdf:
    """Result of :func:`download_patent_pdf`.

    Attributes:
        pdf_bytes: Raw PDF content.
        source: Which backend served the bytes — one of ``"google_patents"``,
            ``"ppubs"``, or ``"epo"``. Google PDFs are already OCR'ed; PPUBS
            and EPO returns need separate OCR for text extraction.
        filename: Suggested filename (source-specific naming convention).
        patent_number: The number as resolved by the serving source (may
            include/omit country or kind code relative to the input).
        patent_title: Populated when the source returns it (currently PPUBS only).
    """

    pdf_bytes: bytes
    source: str
    filename: str
    patent_number: str
    patent_title: str | None = None


async def download_patent_pdf(patent_number: str) -> PatentPdf:
    """Download a patent PDF, cascading Google → PPUBS → EPO.

    Cascades until one source returns bytes:

    1. Google Patents (preferred — PDFs are pre-OCR'ed for text extraction)
    2. USPTO PPUBS (US patents; cleanly 404s on non-US, falls through)
    3. EPO OPS (worldwide fallback assembled from page images)

    Non-not-found errors (auth, transient HTTP failures) surface immediately
    rather than being masked by silent fallback. Raises :class:`NotFoundError`
    only if all three sources say the PDF does not exist.
    """
    from law_tools_core.filenames import (
        epo_pdf as _epo_pdf_name,
    )
    from law_tools_core.filenames import (
        patent_pdf as _patent_pdf_name,
    )
    from law_tools_core.filenames import (
        publication_pdf as _publication_pdf_name,
    )

    tried: list[str] = []

    # 1) Google Patents
    try:
        from patent_client_agents.google_patents import GooglePatentsClient

        async with GooglePatentsClient() as client:
            pdf_bytes = await client.download_patent_pdf(patent_number)
        return PatentPdf(
            pdf_bytes=pdf_bytes,
            source="google_patents",
            filename=_patent_pdf_name(patent_number),
            patent_number=patent_number,
        )
    except (NotFoundError, FileNotFoundError, ValueError) as exc:
        logger.info("Google Patents did not have PDF for %s: %s", patent_number, exc)
        tried.append(f"google_patents ({exc})")

    # 2) USPTO PPUBS
    try:
        from patent_client_agents.uspto_publications import resolve_and_download_pdf

        result = await resolve_and_download_pdf(patent_number)
        pdf_bytes = base64.b64decode(result.pdf_base64)
        pub_no = result.publication_number or patent_number
        return PatentPdf(
            pdf_bytes=pdf_bytes,
            source="ppubs",
            filename=_publication_pdf_name(pub_no),
            patent_number=pub_no,
            patent_title=result.patent_title,
        )
    except (NotFoundError, FileNotFoundError, ValueError) as exc:
        logger.info("PPUBS did not have PDF for %s: %s", patent_number, exc)
        tried.append(f"ppubs ({exc})")

    # 3) EPO OPS
    try:
        from patent_client_agents.epo_ops.client import client_from_env

        async with client_from_env() as client:
            result = await client.download_pdf(number=patent_number)
        pdf_bytes = base64.b64decode(result.pdf_base64)
        return PatentPdf(
            pdf_bytes=pdf_bytes,
            source="epo",
            filename=_epo_pdf_name(patent_number),
            patent_number=patent_number,
        )
    except (NotFoundError, FileNotFoundError, ValueError, RuntimeError) as exc:
        logger.info("EPO OPS did not have PDF for %s: %s", patent_number, exc)
        tried.append(f"epo ({exc})")

    raise NotFoundError(
        f"No PDF found for {patent_number!r} in any source. Tried: {'; '.join(tried)}"
    )
