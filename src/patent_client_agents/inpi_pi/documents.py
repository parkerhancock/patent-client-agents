"""Parser for JPO document-bundle ZIP archives.

The JPO ``app_doc_cont_*`` endpoints return ZIP archives containing
either JPO-flavoured XML files (patents) or semi-structured HTM files
(designs and trademarks). This module unpacks those archives and
parses each entry into typed Pydantic models.

Three endpoints feed three (related but distinct) bundle shapes:

* ``application_documents`` (``app_doc_cont_opinion_amendment``) —
  applicant-filed opinions and amendments. Patent layout::

      A53_<dispatch_id>/JPOXMLDOC01-jpbibl.xml      (opinion / 意見書)
      A523_<dispatch_id>/JPOXMLDOC01-jpbibl.xml     (amendment / 手続補正書)
      ...

  Each subdirectory holds one filed document. The index XML's root
  element classifies the document (``jp:response-a53`` for opinion,
  ``jp:amendment-a523`` for amendment, etc.) and the
  ``jp:document-code`` element gives the JPO four-digit document code.

  Designs and trademarks return HTM files in the same archive, with
  filenames like ``<dispatch_id>P.HTM`` (Shift-JIS encoded HTML, not
  XML).

* ``mailed_documents`` (``app_doc_cont_refusal_reason_decision``) —
  JPO-mailed refusal-reason notices, decisions of refusal, and
  decisions of grant. Patent layout::

      <dispatch_id>-jpntce.xml
      <dispatch_id>-jpntce.xml
      ...

  Design / trademark layout::

      <dispatch_id>P.HTM
      <dispatch_id>P.HTM
      ...

* ``refusal_notices`` (``app_doc_cont_refusal_reason``) — strict subset
  of mailed: only notices of reasons for refusal. Same layout
  per-IP-type as ``mailed``.

Encoding
--------
**Both XML and HTM payloads are Shift-JIS encoded, not UTF-8.** Decode
explicitly with ``raw.decode("shift_jis")`` (or ``cp932`` as a tolerant
fallback — they share the same codepoints for everything JPO emits).
Trying to decode as UTF-8 will raise ``UnicodeDecodeError`` on the
first kana.

Handbook §2(1) states explicitly: "fourteen types of patent APIs
available [...] one of them is to retrieve procedural documents in
XML format (Patent) or HTM format (design and trademark)". So the
file extension is ip_type-driven, not doc_kind-driven.

The handbook's "XML Tag Structures" reference is the source of truth
for the patent XML schema. The handbook ships separately from
``jpo_api_handbook_v14_e.md`` (it's the per-DTD document set
``pat-rspn.dtd`` etc.). What we model here was reverse-engineered from
production XML/HTM against a handful of representative applications and
covers the fields most useful to an agent doing prosecution-history
review (parties, filed date, document type, body text). The original
ZIP is always available via ``DocumentBundleResult.zip_bytes`` /
``download_url`` for callers that need fields we don't surface.

Empty-bundle policy
-------------------
If the JPO returns status 107 / 108 (no documents on file), the upstream
:class:`DocumentBundleResult` carries neither inline bytes nor a redirect
URL. :func:`parse_document_bundle` accepts that case and returns a bundle
with ``entries=[]`` — never raises.
"""

from __future__ import annotations

import html
import io
import logging
import re
import zipfile
from typing import Literal
from xml.etree import ElementTree as ET

from .models_documents import (
    DocumentBundle,
    DocumentEntry,
    DocumentKind,
    IpType,
)

logger = logging.getLogger(__name__)

# JPO XML namespace — every element is prefixed ``jp:`` and bound to this URI.
_JP_NS = "http://www.jpo.go.jp"
_NS = {"jp": _JP_NS}


def _qname(local: str) -> str:
    """Return Clark-notation QName for the JPO namespace."""
    return f"{{{_JP_NS}}}{local}"


def _strip_ns(tag: str) -> str:
    """Drop the namespace from a Clark-notation tag (``{ns}name`` -> ``name``)."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _text(elem: ET.Element | None) -> str:
    """Get an element's text content (concatenating descendants), trimmed."""
    if elem is None:
        return ""
    parts: list[str] = []
    for chunk in elem.itertext():
        parts.append(chunk)
    return "".join(parts).strip()


def _find_text_descendant(root: ET.Element, local_name: str) -> str:
    """Find the first descendant by local name, returning its text content."""
    qn = _qname(local_name)
    for elem in root.iter(qn):
        txt = _text(elem)
        if txt:
            return txt
    return ""


def _decode_xml(raw: bytes) -> str:
    """Decode JPO XML bytes as Shift-JIS, with cp932 fallback for full coverage.

    JPO emits ``<?xml encoding="Shift_JIS"?>`` but their content
    occasionally includes characters that strict Shift-JIS rejects but
    cp932 (Microsoft's Shift-JIS extension) handles fine. Try strict
    first; fall back without raising.
    """
    try:
        return raw.decode("shift_jis")
    except UnicodeDecodeError:
        return raw.decode("cp932", errors="replace")


def _parse_application_doc_xml(filename: str, raw: bytes, ip_type: IpType) -> DocumentEntry:
    """Parse one applicant-filed XML index (opinion or amendment).

    Root elements seen in production:

    * ``jp:pat-rspns`` -> ``jp:response-a53`` (opinion / 意見書)
    * ``jp:pat-amnd``  -> ``jp:amendment-a523`` (amendment / 手続補正書)
    * Design / trademark variants follow the same pattern with
      ``des-rspns`` / ``tm-rspns`` etc. (handled generically here).
    """
    text = _decode_xml(raw)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.warning("Failed to parse %s: %s", filename, exc)
        return DocumentEntry(
            filename=filename,
            ip_type=ip_type,
            doc_kind="application",
            parse_error=str(exc),
        )

    # Document code lives in the first element-tag-named "document-code"
    # under any direct child of the root. We use a generic descendant
    # search so this works across opinion / amendment / future variants.
    doc_code = _find_text_descendant(root, "document-code")

    # Document name (e.g. "意見書" / "手続補正書") — present on mailed
    # docs, absent on applicant-filed docs but kept in the field for a
    # uniform shape.
    document_name = _find_text_descendant(root, "document-name")

    # Application number is in jp:application-reference/jp:document-id/jp:doc-number
    application_number = _find_text_descendant(root, "doc-number")

    # Filing/dispatch date — applicant docs typically don't carry a
    # <jp:date> element at all (only an opaque dispatch number).
    legal_date = _find_text_descendant(root, "date")
    dispatch_number = _find_text_descendant(root, "dispatch-number")

    # Applicant / agent names: collected from any <jp:applicant>/<jp:agent>
    # descendant's <jp:name>.
    applicant_names: list[str] = []
    for parent_tag in ("applicant", "agent"):
        for parent in root.iter(_qname(parent_tag)):
            name = _find_text_descendant(parent, "name")
            if name and name not in applicant_names:
                applicant_names.append(name)

    # Body text: depends on root variant. Try a few likely ancestors.
    body_text = ""
    for body_tag in (
        "opinion-contents-article",
        "amendment-article",
        "comment-article",
        "contents-of-amendment",
    ):
        elem = next(iter(root.iter(_qname(body_tag))), None)
        if elem is not None:
            body_text = _text(elem)
            if body_text:
                break

    # Root variant tag (e.g. ``response-a53``) — useful to disambiguate
    # opinion vs amendment vs other.
    root_local = _strip_ns(root.tag)
    variant = ""
    if len(root) > 0:
        variant = _strip_ns(root[0].tag)

    return DocumentEntry(
        filename=filename,
        ip_type=ip_type,
        doc_kind="application",
        document_code=doc_code,
        document_name=document_name,
        document_variant=variant or root_local,
        application_number=application_number,
        legal_date=legal_date,
        applicant_names=applicant_names,
        dispatch_number=dispatch_number,
        body_text=body_text,
    )


def _parse_mailed_doc_xml(
    filename: str,
    raw: bytes,
    ip_type: IpType,
    doc_kind: Literal["mailed", "refusal"],
) -> DocumentEntry:
    """Parse one JPO-mailed notice XML index.

    Common roots:

    * ``jp:notice-pat-exam-rn`` -> ``jp:notice-of-rejection-a131-rn``
      (notice of reasons for refusal)
    * ``jp:notice-pat-exam-rn`` -> ``jp:decision-of-refusal-...`` (decision)
    * ``jp:notice-pat-exam-rn`` -> ``jp:decision-of-grant-...``
      (decision to grant)
    * Design / trademark variants share the same structure with
      ``des-`` / ``tm-`` prefixes.
    """
    text = _decode_xml(raw)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.warning("Failed to parse %s: %s", filename, exc)
        return DocumentEntry(
            filename=filename,
            ip_type=ip_type,
            doc_kind=doc_kind,
            parse_error=str(exc),
        )

    document_name = _find_text_descendant(root, "document-name")
    application_number = _find_text_descendant(root, "doc-number")

    # Drafting date is the canonical "when issued"
    drafting = root.find(".//jp:drafting-date/jp:date", _NS)
    legal_date = _text(drafting) or _find_text_descendant(root, "date")

    # Examiner / drafting person
    drafter = ""
    drafter_elem = root.find(".//jp:draft-person-group/jp:name", _NS)
    if drafter_elem is not None:
        drafter = _text(drafter_elem)

    # Article references — list of statutes cited
    article_group = root.find(".//jp:article-group", _NS)
    articles: list[str] = []
    if article_group is not None:
        for art in article_group.findall("jp:article", _NS):
            txt = _text(art)
            if txt:
                articles.append(txt)

    # Body text — conclusion-part-article for refusal notices, etc.
    body_text = ""
    for body_tag in (
        "conclusion-part-article",
        "reason-of-rejection-article",
        "main-text-article",
        "reasons-article",
    ):
        elem = next(iter(root.iter(_qname(body_tag))), None)
        if elem is not None:
            body_text = _text(elem)
            if body_text:
                break

    root_local = _strip_ns(root.tag)
    variant = ""
    if len(root) > 0:
        variant = _strip_ns(root[0].tag)

    return DocumentEntry(
        filename=filename,
        ip_type=ip_type,
        doc_kind=doc_kind,
        document_code="",  # mailed docs use document-name; document-code rarely present
        document_name=document_name,
        document_variant=variant or root_local,
        application_number=application_number,
        legal_date=legal_date,
        drafter_name=drafter,
        articles=articles,
        body_text=body_text,
    )


def _parse_htm_doc(
    filename: str,
    raw: bytes,
    ip_type: IpType,
    doc_kind: DocumentKind,
) -> DocumentEntry:
    """Parse a JPO HTM index (design / trademark mailed documents).

    Designs and trademarks return Shift-JIS-encoded HTML rather than
    JPO-namespaced XML (handbook §2(1)). The HTM structure is
    semi-deterministic: a ``<PRE>`` block whose first labelled lines
    carry the document name (FONT SIZE="6"), application number,
    examiner, drafting date, applicant.
    """
    text = _decode_xml(raw)

    # Extract body text from <PRE>...</PRE>; fall back to stripped HTML.
    pre_match = re.search(r"<PRE[^>]*>(.*?)</PRE>", text, re.DOTALL | re.IGNORECASE)
    if pre_match:
        body_html = pre_match.group(1)
    else:
        body_html = text

    # Strip tags and decode HTML entities.
    body_text = html.unescape(re.sub(r"<[^>]+>", "", body_html)).strip()

    # Document name is the first line in a SIZE=6 / SIZE="6" font block.
    name_match = re.search(r'<FONT[^>]*SIZE="?6"?[^>]*>([^<]+)</FONT>', text, re.IGNORECASE)
    document_name = html.unescape(name_match.group(1)).strip() if name_match else ""

    # The body has lines like "  特許庁審査官    藤澤　崇彦   ..."
    drafter = ""
    m = re.search(
        r"(?:特許庁|意匠登録|商標登録)?(?:審査官|審査長)\s+(\S+(?:\s\S+)*?)(?=\s{2,}|$|\n)",
        body_text,
    )
    if m:
        drafter = m.group(1).strip()

    # Drafting date: "起案日　　　令和　４年　３月１０日" — capture as-is, the
    # whole Japanese-formatted date. The patent XML path stores YYYYMMDD;
    # for HTM we store the wareki/Japanese-formatted string and let the
    # caller convert if needed.
    legal_date = ""
    m = re.search(r"起案日[^\S\n]*[:：]?\s*([^\n]+)", body_text)
    if m:
        legal_date = m.group(1).strip()

    # Application number: 意願２０２１−０１９５００ or similar
    application_number = ""
    m = re.search(r"(?:意願|商願|特願)([\d０-９−\-－−]+)", body_text)
    if m:
        application_number = m.group(1).strip()

    # Statute references — look for 第\d+条 patterns
    article_pattern = re.compile(
        r"(?:意匠法|商標法|特許法)?第[\d０-９]+条(?:第[\d０-９]+項)?(?:第[\d０-９]+号)?"
    )
    articles: list[str] = []
    for art in article_pattern.findall(body_text):
        if art and art not in articles:
            articles.append(art)

    return DocumentEntry(
        filename=filename,
        ip_type=ip_type,
        doc_kind=doc_kind,
        document_name=document_name,
        document_variant="htm",  # marker that this came from HTM not XML
        application_number=application_number,
        legal_date=legal_date,
        drafter_name=drafter,
        articles=articles,
        body_text=body_text,
    )


def parse_document_bundle(
    zip_bytes: bytes | None,
    doc_kind: DocumentKind,
    ip_type: IpType,
    *,
    application_number: str = "",
) -> DocumentBundle:
    """Parse a JPO document-bundle ZIP into a typed :class:`DocumentBundle`.

    Args:
        zip_bytes: Inline ZIP bytes from
            :class:`~patent_client_agents.inpi_pi.models.DocumentBundleResult`.
            ``None`` is allowed (empty bundle).
        doc_kind: Which client method produced the bundle —
            ``"application"`` (opinions/amendments),
            ``"mailed"`` (rejections + decisions),
            or ``"refusal"`` (rejection notices only).
        ip_type: ``"patent"``, ``"design"``, or ``"trademark"`` —
            currently informational only (the schemas converge across
            IP types) but kept on each entry for downstream filtering.
        application_number: The application number queried (echoed
            on the bundle for caller convenience).

    Returns:
        A :class:`DocumentBundle` with one :class:`DocumentEntry` per
        index XML in the archive. Non-XML files (binary attachments)
        are listed in ``binary_attachments`` by filename only — their
        bytes are still in the original ZIP and can be reached via the
        ``download_url`` on the bundle response.

    Raises:
        zipfile.BadZipFile: only if ``zip_bytes`` is non-empty *and*
            not a valid ZIP archive. An empty or ``None`` payload
            simply produces an empty bundle.
    """
    if not zip_bytes:
        return DocumentBundle(
            ip_type=ip_type,
            doc_kind=doc_kind,
            application_number=application_number,
            entries=[],
            binary_attachments=[],
        )

    entries: list[DocumentEntry] = []
    binary_attachments: list[str] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            lower = name.lower()
            raw = zf.read(name)
            if lower.endswith(".xml"):
                # Patent bundles ship XML.
                if doc_kind == "application":
                    entries.append(_parse_application_doc_xml(name, raw, ip_type))
                else:
                    # mailed and refusal share the same XML schema
                    entries.append(_parse_mailed_doc_xml(name, raw, ip_type, doc_kind))
            elif lower.endswith(".htm") or lower.endswith(".html"):
                # Design / trademark bundles ship HTM (per handbook §2(1)).
                entries.append(_parse_htm_doc(name, raw, ip_type, doc_kind))
            else:
                # Anything else is an attached binary (image, PDF, etc.).
                # Reference by name only — bytes are still in the raw ZIP.
                binary_attachments.append(name)

    return DocumentBundle(
        ip_type=ip_type,
        doc_kind=doc_kind,
        application_number=application_number,
        entries=entries,
        binary_attachments=binary_attachments,
    )


__all__ = ["parse_document_bundle"]
