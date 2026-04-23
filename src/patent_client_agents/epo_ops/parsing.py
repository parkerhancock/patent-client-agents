"""XML parsing helpers for EPO OPS responses."""

from __future__ import annotations

from collections.abc import Iterable

import lxml.etree as etree

from law_tools_core.exceptions import ParseError

from .models import (
    BiblioRecord,
    BiblioResponse,
    Claim,
    ClassificationMapping,
    ClassificationMappingResponse,
    CpcClassificationItem,
    CpciBiblioRecord,
    CpciBiblioResponse,
    CpciClassification,
    CpcRetrievalResponse,
    CpcScheme,
    CpcSearchResponse,
    CpcSearchResult,
    CpcTitlePart,
    DocumentId,
    FamilyMember,
    FamilyResponse,
    FullTextResponse,
    LegalEvent,
    LegalEventsResponse,
    NumberConversionResponse,
    SearchResponse,
    SearchResult,
)

NS = {
    "ops": "http://ops.epo.org",
    "epo": "http://www.epo.org/exchange",
    "ft": "http://www.epo.org/fulltext",
    "cpc": "http://www.epo.org/cpcexport",
}


class XmlParseError(ParseError):
    """Raised when mandatory XML nodes are missing.

    Inherits from ParseError for unified exception handling.
    """

    def __init__(
        self,
        message: str,
        source: str | None = None,
        raw_content: str | None = None,
    ) -> None:
        super().__init__(message, source, raw_content)


def _as_element(data: str | bytes | etree._Element) -> etree._Element:  # type: ignore[attr-defined]
    if isinstance(data, etree._Element):  # pragma: no cover - defensive
        return data
    if isinstance(data, bytes):
        return etree.fromstring(data)
    if isinstance(data, str):
        return etree.fromstring(data.encode("utf-8"))
    raise TypeError(f"Unsupported XML payload type: {type(data)!r}")


def _first(nodes: Iterable[etree._Element]) -> etree._Element | None:  # type: ignore[attr-defined]
    for node in nodes:
        return node
    return None


def _text(node: etree._Element, xpath: str) -> str | None:  # type: ignore[attr-defined]
    result = node.xpath(xpath, namespaces=NS)
    for value in result:
        if isinstance(value, str):
            cleaned = value.strip()
        elif isinstance(value, bytes):
            cleaned = value.decode().strip()
        elif hasattr(value, "itertext"):
            cleaned = "".join(value.itertext()).strip()
        else:
            cleaned = str(value).strip()
        if cleaned:
            return cleaned
    return None


def _collect_texts(node: etree._Element, xpath: str) -> list[str]:  # type: ignore[attr-defined]
    values: list[str] = []
    for match in node.xpath(xpath, namespaces=NS):
        if isinstance(match, str):
            text = match.strip()
        else:
            text = "".join(match.itertext()).strip()
        if text:
            values.append(text)
    return values


def _parse_document_id(node: etree._Element | None) -> DocumentId:  # type: ignore[attr-defined]
    if node is None:
        return DocumentId()
    doc_type = node.tag.split("}")[-1] if "}" in node.tag else node.tag
    return DocumentId(
        doc_type=doc_type,
        number=_text(node, "./epo:doc-number"),
        country=_text(node, "./epo:country"),
        kind=_text(node, "./epo:kind"),
        date=_text(node, "./epo:date"),
        format=node.get("document-id-type"),
        id_type=node.get("document-id-type"),
        name=_text(node, "./epo:name"),
    )


def parse_search_response(xml_data: str | bytes) -> SearchResponse:
    root = _as_element(xml_data)
    query = _text(root, ".//ops:query")
    begin = _text(root, ".//ops:range/@begin")
    end = _text(root, ".//ops:range/@end")
    total = _text(root, ".//ops:biblio-search/@total-result-count")

    results: list[SearchResult] = []
    nodes = root.xpath(".//ops:search-result/ops:publication-reference", namespaces=NS)
    for pub in nodes:
        country = _text(pub, ".//epo:country")
        doc_number = _text(pub, ".//epo:doc-number")
        kind = _text(pub, ".//epo:kind")
        docdb_number = None
        if country and doc_number:
            docdb_number = f"{country}{doc_number}{kind or ''}"
        result = SearchResult(
            docdb_number=docdb_number,
            country=country,
            doc_number=doc_number,
            kind=kind,
            family_id=pub.get("family-id"),
            publication_date=_text(pub, ".//epo:date"),
        )
        results.append(result)

    return SearchResponse(
        query=query,
        range_begin=int(begin) if begin and begin.isdigit() else None,
        range_end=int(end) if end and end.isdigit() else None,
        total_results=int(total) if total and total.isdigit() else None,
        results=results,
    )


def parse_biblio_response(xml_data: str | bytes) -> BiblioResponse:
    root = _as_element(xml_data)
    documents: list[BiblioRecord] = []
    for exchange_doc in root.xpath(".//epo:exchange-document", namespaces=NS):
        publication_doc = _first(
            exchange_doc.xpath(
                './/epo:publication-reference/epo:document-id[@document-id-type="docdb"]',
                namespaces=NS,
            )
        )
        application_doc = _first(
            exchange_doc.xpath(
                './/epo:application-reference/epo:document-id[@document-id-type="docdb"]',
                namespaces=NS,
            )
        )
        priority_nodes = exchange_doc.xpath(".//epo:priority-claim/epo:document-id", namespaces=NS)
        priority_claims = [_parse_document_id(node) for node in priority_nodes]
        applicants = _collect_texts(exchange_doc, ".//epo:applicant//epo:name")
        inventors = _collect_texts(exchange_doc, ".//epo:inventor//epo:name")
        ipc_classes = [
            " ".join(text.split())
            for text in _collect_texts(
                exchange_doc, ".//epo:classifications-ipcr/epo:classification-ipcr"
            )
        ]
        cpc_nodes = exchange_doc.xpath(
            './/epo:patent-classification[epo:classification-scheme[@scheme="CPCI"]]',
            namespaces=NS,
        )
        cpc_classes = []
        for node in cpc_nodes:
            text = " ".join("".join(node.itertext()).split())
            if text:
                cpc_classes.append(text)
        docdb_number = None
        if publication_doc is not None:
            country = _text(publication_doc, "./epo:country") or ""
            doc_number = _text(publication_doc, "./epo:doc-number") or ""
            kind = _text(publication_doc, "./epo:kind") or ""
            docdb_number = f"{country}{doc_number}{kind}"
        record = BiblioRecord(
            docdb_number=docdb_number,
            application_number=_text(application_doc, "./epo:doc-number")
            if application_doc is not None
            else None,
            publication_reference=_parse_document_id(publication_doc),
            application_reference=_parse_document_id(application_doc),
            family_id=exchange_doc.get("family-id"),
            title=_text(exchange_doc, './/epo:invention-title[@lang="en"]')
            or _text(exchange_doc, ".//epo:invention-title"),
            abstract=_text(exchange_doc, './/epo:abstract[@lang="en"]')
            or _text(exchange_doc, ".//epo:abstract"),
            applicants=applicants,
            inventors=inventors,
            ipc_classes=ipc_classes,
            cpc_classes=cpc_classes,
            priority_claims=priority_claims,
        )
        documents.append(record)
    return BiblioResponse(documents=documents)


def parse_claims(xml_data: str | bytes, section: str) -> FullTextResponse:
    root = _as_element(xml_data)
    document_id = _first(root.xpath(".//ft:document-id", namespaces=NS))
    docdb_number = None
    if document_id is not None:
        country = _text(document_id, "./ft:country") or ""
        doc_number = _text(document_id, "./ft:doc-number") or ""
        kind = _text(document_id, "./ft:kind") or ""
        docdb_number = f"{country}{doc_number}{kind}"

    if section == "claims":
        claims: list[Claim] = []
        for claim_node in root.xpath(".//ft:claim", namespaces=NS):
            number_attr = claim_node.get("num")
            number = int(number_attr) if number_attr and number_attr.isdigit() else None
            text = "\n".join(
                part.strip()
                for part in claim_node.xpath(".//ft:claim-text/text()", namespaces=NS)
                if part and part.strip()
            )
            claims.append(Claim(number=number, text=text or None))
        raw_text = "\n\n".join(
            line.strip()
            for line in root.xpath(".//ft:claims//text()", namespaces=NS)
            if line.strip()
        )
        return FullTextResponse(
            docdb_number=docdb_number, section=section, claims=claims, raw_text=raw_text
        )

    description_parts = [
        " ".join(
            piece.strip() for piece in para.xpath(".//text()", namespaces=NS) if piece.strip()
        ).strip()
        for para in root.xpath(".//ft:description/ft:p", namespaces=NS)
    ]
    description_text = "\n\n".join(part for part in description_parts if part)
    if not description_text:
        description_text = "\n\n".join(
            piece.strip()
            for piece in root.xpath(".//ft:description//text()", namespaces=NS)
            if piece.strip()
        )
    return FullTextResponse(
        docdb_number=docdb_number,
        section=section,
        description=description_text or None,
        raw_text=description_text or None,
    )


def parse_family(xml_data: str | bytes) -> FamilyResponse:
    root = _as_element(xml_data)
    publication_number = _text(
        root,
        './/ops:patent-family/ops:publication-reference/epo:document-id[@document-id-type="docdb"]/epo:doc-number',
    )
    num_records_raw = _text(root, ".//ops:patent-family/@total-result-count")
    num_records = int(num_records_raw) if num_records_raw and num_records_raw.isdigit() else None

    members: list[FamilyMember] = []
    for member in root.xpath(".//ops:family-member", namespaces=NS):
        publication_refs = [
            _parse_document_id(node)
            for node in member.xpath(".//epo:publication-reference/epo:document-id", namespaces=NS)
        ]
        application_refs = [
            _parse_document_id(node)
            for node in member.xpath(".//epo:application-reference/epo:document-id", namespaces=NS)
        ]
        priority_claims = [
            _parse_document_id(node)
            for node in member.xpath(".//epo:priority-claim/epo:document-id", namespaces=NS)
        ]
        pub_number = None
        if publication_refs:
            first_ref = publication_refs[0]
            if first_ref.country and first_ref.doc_number:
                pub_number = f"{first_ref.country}{first_ref.doc_number}{first_ref.kind or ''}"
        application_number = None
        if application_refs:
            first_app = application_refs[0]
            if first_app.country and first_app.doc_number:
                application_number = (
                    f"{first_app.country}{first_app.doc_number}{first_app.kind or ''}"
                )
        members.append(
            FamilyMember(
                family_id=member.get("family-id"),
                publication_number=pub_number,
                application_number=application_number,
                publication_references=publication_refs,
                application_references=application_refs,
                priority_claims=priority_claims,
            )
        )

    return FamilyResponse(
        publication_number=publication_number,
        num_records=num_records,
        members=members,
    )


def parse_legal_events(xml_data: str | bytes) -> LegalEventsResponse:
    root = _as_element(xml_data)
    publication_ref = _first(
        root.xpath(
            './/ops:patent-family/ops:publication-reference/epo:document-id[@document-id-type="docdb"]',
            namespaces=NS,
        )
    )
    publication_reference = _parse_document_id(publication_ref)

    events: list[LegalEvent] = []
    for event_node in root.xpath(".//ops:legal", namespaces=NS):
        country = _text(event_node, ".//ops:L001EP")
        code = _text(event_node, ".//ops:L008EP")
        regional_code = _text(event_node, ".//ops:L502EP")
        event_code = None
        if code and country:
            event_code = f"{country}.{code}"
        if regional_code and (country := _text(event_node, ".//ops:L501EP")):
            event_code = f"{country}.{regional_code}"
        events.append(
            LegalEvent(
                event_code=event_code,
                event_date=_text(event_node, ".//ops:L007EP"),
                event_country=_text(event_node, ".//ops:L501EP")
                or _text(event_node, ".//ops:L001EP"),
                country_code=_text(event_node, ".//ops:L001EP"),
                filing_or_publication=_text(event_node, ".//ops:L002EP"),
                document_number=_text(event_node, ".//ops:L003EP"),
                ip_type=_text(event_node, ".//ops:L005EP"),
                free_text=_text(event_node, ".//ops:L510EP"),
                text_record="\n".join(
                    part.strip()
                    for part in event_node.xpath(".//ops:pre/text()", namespaces=NS)
                    if part.strip()
                )
                or None,
                metadata={
                    "status_of_data": _text(event_node, ".//ops:L013"),
                    "subscriber_exchange_date": _text(event_node, ".//ops:L018EP"),
                },
            )
        )

    return LegalEventsResponse(publication_reference=publication_reference, events=events)


def parse_number_conversion(xml_data: str | bytes) -> NumberConversionResponse:
    root = _as_element(xml_data)
    input_node = _first(root.xpath(".//ops:input//epo:document-id", namespaces=NS))
    output_node = _first(root.xpath(".//ops:output//epo:document-id", namespaces=NS))
    messages = _collect_texts(root, './/ops:meta[@name="status"]/@value')
    service_version = _text(root, './/ops:meta[@name="version"]/@value')
    return NumberConversionResponse(
        input_document=_parse_document_id(input_node),
        output_document=_parse_document_id(output_node),
        service_version=service_version,
        messages=messages,
    )


def _bool_attr(node: etree._Element, attr: str) -> bool | None:  # type: ignore[attr-defined]
    value = node.get(attr)
    if value is None:
        return None
    return value.lower() in {"true", "1", "yes"}


def _int_attr(node: etree._Element, attr: str) -> int | None:  # type: ignore[attr-defined]
    value = node.get(attr)
    if value and value.isdigit():
        return int(value)
    return None


def _parse_cpc_title_parts(node: etree._Element) -> tuple[str | None, list[CpcTitlePart]]:  # type: ignore[attr-defined]
    title_node = _first(node.xpath("./cpc:class-title", namespaces=NS))
    if title_node is None:
        return None, []
    parts: list[CpcTitlePart] = []
    lines: list[str] = []
    for part in title_node.xpath("./cpc:title-part", namespaces=NS):
        text = " ".join(
            fragment.strip()
            for fragment in part.xpath(".//cpc:text//text()", namespaces=NS)
            if fragment.strip()
        )
        media_node = _first(part.xpath(".//cpc:media", namespaces=NS))
        parts.append(
            CpcTitlePart(
                text=text or None,
                scheme=part.get("scheme") or None,
                media_id=media_node.get("id") if media_node is not None else None,
                media_type=media_node.get("type") if media_node is not None else None,
            )
        )
        if text:
            lines.append(text)
    joined = " ".join(lines) if lines else None
    return joined, parts


def _parse_cpc_item(node: etree._Element) -> CpcClassificationItem:  # type: ignore[attr-defined]
    title, title_parts = _parse_cpc_title_parts(node)
    children = [
        _parse_cpc_item(child) for child in node.xpath("./cpc:classification-item", namespaces=NS)
    ]
    metadata = _collect_texts(node, "./cpc:meta-data/text()")
    return CpcClassificationItem(
        symbol=_text(node, "./cpc:classification-symbol"),
        level=_int_attr(node, "level"),
        additional_only=_bool_attr(node, "additional-only"),
        sort_key=node.get("sort-key"),
        date_revised=node.get("date-revised"),
        not_allocatable=_bool_attr(node, "not-allocatable"),
        breakdown_code=_bool_attr(node, "breakdown-code"),
        link=node.get("link-file"),
        title=title,
        title_parts=title_parts,
        metadata=metadata,
        children=children,
    )


def parse_cpc_retrieval(xml_data: str | bytes) -> CpcRetrievalResponse:
    root = _as_element(xml_data)
    scheme_node = _first(root.xpath(".//cpc:class-scheme", namespaces=NS))
    if scheme_node is None:
        raise XmlParseError("Missing cpc:class-scheme in CPC retrieval response.")
    items = [
        _parse_cpc_item(node)
        for node in scheme_node.xpath("./cpc:classification-item", namespaces=NS)
    ]
    scheme = CpcScheme(
        scheme_type=scheme_node.get("scheme-type"),
        export_date=scheme_node.get("export-date"),
        items=items,
    )
    return CpcRetrievalResponse(scheme=scheme)


def parse_cpc_search(xml_data: str | bytes) -> CpcSearchResponse:
    root = _as_element(xml_data)
    query = _text(root, ".//ops:query") or ""
    total = _text(root, ".//ops:classification-search/@total-result-count")
    range_begin = _text(root, ".//ops:range/@begin")
    range_end = _text(root, ".//ops:range/@end")
    results: list[CpcSearchResult] = []
    for node in root.xpath(".//ops:classification-statistics", namespaces=NS):
        symbol = node.get("classification-symbol") or ""
        percentage_raw = node.get("percentage")
        try:
            percentage = float(percentage_raw) if percentage_raw is not None else None
        except ValueError:
            percentage = None
        title, title_parts = _parse_cpc_title_parts(node)
        results.append(
            CpcSearchResult(
                classification_symbol=symbol,
                percentage=percentage,
                title=title,
                title_parts=title_parts,
            )
        )
    return CpcSearchResponse(
        query=query,
        total_results=int(total) if total and total.isdigit() else None,
        range_begin=int(range_begin) if range_begin and range_begin.isdigit() else None,
        range_end=int(range_end) if range_end and range_end.isdigit() else None,
        results=results,
    )


def parse_classification_mapping(xml_data: str | bytes) -> ClassificationMappingResponse:
    root = _as_element(xml_data)
    mappings_node = _first(root.xpath(".//ops:mappings", namespaces=NS))
    input_schema = mappings_node.get("inputSchema") if mappings_node is not None else None
    output_schema = mappings_node.get("outputSchema") if mappings_node is not None else None
    mappings: list[ClassificationMapping] = []
    for node in root.xpath(".//ops:mapping", namespaces=NS):
        mappings.append(
            ClassificationMapping(
                cpc=_text(node, "./ops:cpc"),
                ecla=_text(node, "./ops:ecla"),
                ipc=_text(node, "./ops:ipc"),
                additional_only=_bool_attr(node, "additional-only"),
            )
        )
    return ClassificationMappingResponse(
        input_schema=input_schema,
        output_schema=output_schema,
        mappings=mappings,
    )


def parse_cpci_biblio(xml_data: str | bytes) -> CpciBiblioResponse:
    root = _as_element(xml_data)
    records: list[CpciBiblioRecord] = []
    for exchange_doc in root.xpath(".//epo:exchange-document", namespaces=NS):
        publication_doc = _first(
            exchange_doc.xpath(
                './/epo:publication-reference/epo:document-id[@document-id-type="docdb"]',
                namespaces=NS,
            )
        )
        docdb_number = None
        if publication_doc is not None:
            country = _text(publication_doc, "./epo:country") or ""
            doc_number = _text(publication_doc, "./epo:doc-number") or ""
            kind = _text(publication_doc, "./epo:kind") or ""
            if country and doc_number:
                docdb_number = f"{country}{doc_number}{kind}"
        classifications: list[CpciClassification] = []
        for class_node in exchange_doc.xpath(".//epo:patent-classification", namespaces=NS):
            sequence = _int_attr(class_node, "sequence")
            generating = _text(class_node, "./epo:generating-office")
            offices = (
                [office.strip() for office in (generating or "").split(",") if office.strip()]
                if generating
                else []
            )
            classifications.append(
                CpciClassification(
                    sequence=sequence,
                    section=_text(class_node, "./epo:section"),
                    class_code=_text(class_node, "./epo:class"),
                    subclass=_text(class_node, "./epo:subclass"),
                    main_group=_text(class_node, "./epo:main-group"),
                    subgroup=_text(class_node, "./epo:subgroup"),
                    classification_value=_text(class_node, "./epo:classification-value"),
                    generating_offices=offices,
                )
            )
        if docdb_number or classifications:
            records.append(
                CpciBiblioRecord(
                    docdb_number=docdb_number,
                    classifications=classifications,
                )
            )
    return CpciBiblioResponse(records=records)
