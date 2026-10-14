"""Tests for USITC transformers."""

from __future__ import annotations

from typing import Any

from patent_client_agents.usitc.transformers import (
    _text,
    build_downloaded_attachment,
    parse_attachments,
    parse_dataweb_report,
    parse_documents,
    parse_hts_search,
    parse_ids_investigations,
    parse_investigations,
)


class TestTextHelper:
    """Tests for _text helper function."""

    def test_extracts_text(self) -> None:
        import xml.etree.ElementTree as ET

        elem = ET.fromstring("<root>hello</root>")
        assert _text(elem) == "hello"

    def test_strips_whitespace(self) -> None:
        import xml.etree.ElementTree as ET

        elem = ET.fromstring("<root>  hello  </root>")
        assert _text(elem) == "hello"

    def test_returns_none_for_empty(self) -> None:
        import xml.etree.ElementTree as ET

        elem = ET.fromstring("<root>   </root>")
        assert _text(elem) is None

    def test_returns_none_for_none(self) -> None:
        assert _text(None) is None


class TestParseInvestigations:
    """Tests for parse_investigations function."""

    def test_parses_xml(self) -> None:
        xml = """
        <root>
            <investigation>
                <investigationNumber>337-TA-1234</investigationNumber>
                <investigationPhase>Final</investigationPhase>
                <investigationTitle>Certain Electronic Devices</investigationTitle>
                <investigationType>Sec 337</investigationType>
                <investigationStatus>Active</investigationStatus>
                <docketNumber>3456</docketNumber>
                <documentListUri>https://edis.usitc.gov/data/document?investigationNumber=337-TA-1234</documentListUri>
            </investigation>
        </root>
        """
        result = parse_investigations(xml)
        assert len(result) == 1
        assert result[0].investigation_number == "337-TA-1234"
        assert result[0].investigation_phase == "Final"
        assert result[0].title == "Certain Electronic Devices"
        assert result[0].investigation_type == "Sec 337"
        assert result[0].document_list_uri is not None

    def test_handles_empty_xml(self) -> None:
        xml = "<root></root>"
        result = parse_investigations(xml)
        assert result == []


class TestParseDocuments:
    """Tests for parse_documents function."""

    def test_parses_xml(self) -> None:
        xml = """
        <root>
            <document>
                <id>12345</id>
                <documentType>Motion</documentType>
                <documentTitle>Motion for Summary Determination</documentTitle>
                <securityLevel>Public</securityLevel>
                <investigationNumber>337-TA-1234</investigationNumber>
                <firmOrganization>Example LLP</firmOrganization>
                <filedBy>Jane Doe</filedBy>
                <onBehalfOf>Widget Corp</onBehalfOf>
                <documentDate>2024-06-01 00:00:00.0</documentDate>
                <officialReceivedDate>2024-06-01 12:30:00.0</officialReceivedDate>
                <attachmentListUri>https://edis.usitc.gov/data/attachment/12345</attachmentListUri>
            </document>
        </root>
        """
        result = parse_documents(xml)
        assert len(result) == 1
        assert result[0].id == 12345
        assert result[0].investigation_number == "337-TA-1234"
        assert result[0].title == "Motion for Summary Determination"
        assert result[0].security_level == "Public"
        assert result[0].filed_by == "Jane Doe"
        assert result[0].firm_organization == "Example LLP"
        assert result[0].on_behalf_of == "Widget Corp"
        assert result[0].document_date is not None
        assert result[0].attachment_list_uri is not None

    def test_handles_confidential_document(self) -> None:
        xml = """
        <root>
            <document>
                <id>12345</id>
                <securityLevel>Confidential</securityLevel>
            </document>
        </root>
        """
        result = parse_documents(xml)
        assert result[0].security_level == "Confidential"


class TestParseAttachments:
    """Tests for parse_attachments function."""

    def test_parses_xml(self) -> None:
        xml = """
        <root>
            <attachment>
                <id>999</id>
                <documentId>12345</documentId>
                <title>Exhibit A</title>
                <fileSize>1024</fileSize>
                <pageCount>10</pageCount>
            </attachment>
        </root>
        """
        result = parse_attachments(xml)
        assert len(result) == 1
        assert result[0].id == 999
        assert result[0].document_id == 12345
        assert result[0].file_size == 1024
        assert result[0].page_count == 10


class TestBuildDownloadedAttachment:
    """Tests for build_downloaded_attachment function."""

    def test_builds_attachment(self) -> None:
        result = build_downloaded_attachment(
            document_id=123,
            attachment_id=456,
            filename="document.pdf",
            content=b"PDF content here",
            content_type="application/pdf",
        )
        assert result.document_id == 123
        assert result.attachment_id == 456
        assert result.filename == "document.pdf"
        assert result.content_type == "application/pdf"
        # Verify base64 encoding
        import base64

        decoded = base64.b64decode(result.content_base64)
        assert decoded == b"PDF content here"


class TestParseDatawebReport:
    """Tests for parse_dataweb_report function."""

    def test_extracts_dto(self) -> None:
        payload: dict[str, Any] = {
            "dto": {"columns": ["col1"], "rows": [[1, 2]]},
            "other": "data",
        }
        result = parse_dataweb_report(payload)
        assert result.dto == {"columns": ["col1"], "rows": [[1, 2]]}
        assert result.raw == payload

    def test_handles_missing_dto(self) -> None:
        payload: dict[str, Any] = {"other": "data"}
        result = parse_dataweb_report(payload)
        assert result.dto == {}


class TestParseIdsInvestigations:
    """Tests for parse_ids_investigations function."""

    def test_parses_data(self) -> None:
        payload: dict[str, Any] = {
            "data": [
                {
                    "Investigation ID": 1234,
                    "Investigation Number": "337-TA-1234",
                    "Product Group Code Description": "Electronics",
                    "Phase Number": "Final",
                }
            ]
        }
        result = parse_ids_investigations(payload)
        assert len(result) == 1
        assert result[0].investigation_id == 1234
        assert result[0].investigation_number == "337-TA-1234"
        assert result[0].product_group == "Electronics"

    def test_handles_missing_data(self) -> None:
        assert parse_ids_investigations({}) == []
        assert parse_ids_investigations({"data": None}) == []


class TestParseHtsSearch:
    """Tests for parse_hts_search function."""

    def test_parses_results(self) -> None:
        payload: dict[str, Any] = {
            "results": [{"htsno": "8471.30.01", "description": "Computers", "chapter": "84"}]
        }
        result = parse_hts_search(payload)
        assert len(result) == 1
        assert result[0].hts_number == "8471.30.01"
        assert result[0].description == "Computers"

    def test_parses_items_fallback(self) -> None:
        payload: dict[str, Any] = {"items": [{"htsno": "8471.30.01", "description": "Computers"}]}
        result = parse_hts_search(payload)
        assert len(result) == 1

    def test_handles_empty(self) -> None:
        assert parse_hts_search({}) == []
