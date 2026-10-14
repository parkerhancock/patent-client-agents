from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from typing import Any

from .models import (
    DataWebReport,
    DownloadedAttachment,
    EdisAttachment,
    EdisDocument,
    EdisInvestigation,
    HtsExportResponse,
    HtsSearchResult,
    IdsInvestigation,
    SavedQuerySummary,
)


def _text(value: ET.Element | None) -> str | None:
    if value is None:
        return None
    if value.text is None:
        return None
    return value.text.strip() or None


def parse_investigations(xml_text: str) -> list[EdisInvestigation]:
    root = ET.fromstring(xml_text)
    results: list[EdisInvestigation] = []
    for inv in root.findall(".//investigation"):
        payload: dict[str, Any] = {}
        for child in inv:
            payload[child.tag] = _text(child)
        results.append(EdisInvestigation.model_validate(payload))
    return results


def parse_documents(xml_text: str) -> list[EdisDocument]:
    root = ET.fromstring(xml_text)
    documents: list[EdisDocument] = []
    for doc in root.findall(".//document"):
        payload: dict[str, Any] = {}
        for child in doc:
            value = _text(child)
            if child.tag == "id" and value is not None:
                payload[child.tag] = int(value)
            else:
                payload[child.tag] = value
        documents.append(EdisDocument.model_validate(payload))
    return documents


_ATTACHMENT_INT_FIELDS = {"id", "documentId", "fileSize", "pageCount"}


def parse_attachments(xml_text: str) -> list[EdisAttachment]:
    root = ET.fromstring(xml_text)
    attachments: list[EdisAttachment] = []
    for att in root.findall(".//attachment"):
        payload: dict[str, Any] = {}
        for child in att:
            value = _text(child)
            if child.tag in _ATTACHMENT_INT_FIELDS and value is not None:
                payload[child.tag] = int(value)
            else:
                payload[child.tag] = value
        attachments.append(EdisAttachment.model_validate(payload))
    return attachments


def build_downloaded_attachment(
    document_id: int,
    attachment_id: int,
    filename: str | None,
    content: bytes,
    content_type: str | None,
) -> DownloadedAttachment:
    encoded = base64.b64encode(content).decode("ascii")
    return DownloadedAttachment(
        document_id=document_id,
        attachment_id=attachment_id,
        filename=filename,
        content_type=content_type,
        content_base64=encoded,
    )


def parse_dataweb_report(payload: dict[str, Any]) -> DataWebReport:
    dto = payload.get("dto") or {}
    return DataWebReport(dto=dto, raw=payload)


def parse_saved_queries(payload: list[dict[str, Any]]) -> list[SavedQuerySummary]:
    return [SavedQuerySummary.model_validate(item) for item in payload]


def parse_ids_investigations(payload: dict[str, Any]) -> list[IdsInvestigation]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    return [IdsInvestigation.model_validate(item) for item in data]


def parse_hts_search(payload: list[dict[str, Any]] | dict[str, Any]) -> list[HtsSearchResult]:
    # API returns a raw list directly
    if isinstance(payload, list):
        return [HtsSearchResult.model_validate(item) for item in payload]
    results = payload.get("results")
    if isinstance(results, list):
        return [HtsSearchResult.model_validate(item) for item in results]
    entries = payload.get("items")
    if isinstance(entries, list):
        return [HtsSearchResult.model_validate(item) for item in entries]
    return []


def parse_hts_export(payload: list[dict[str, Any]]) -> HtsExportResponse:
    return HtsExportResponse(entries=payload, raw=payload)
