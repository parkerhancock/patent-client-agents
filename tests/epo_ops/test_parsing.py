"""Tests for EPO OPS XML parsing."""

from __future__ import annotations

import pytest

from patent_client_agents.epo_ops.parsing import (
    NS,
    XmlParseError,
    _as_element,
    _collect_texts,
    _text,
)


class TestXmlParseError:
    """Tests for XmlParseError exception."""

    def test_inherits_from_core(self) -> None:
        from law_tools_core.exceptions import ParseError

        error = XmlParseError("test message")
        assert isinstance(error, ParseError)

    def test_stores_source_and_content(self) -> None:
        error = XmlParseError(
            "test message",
            source="test.xml",
            raw_content="<xml>content</xml>",
        )
        assert error.source == "test.xml"
        assert error.raw_content == "<xml>content</xml>"


class TestAsElement:
    """Tests for _as_element helper."""

    def test_from_bytes(self) -> None:
        xml = b"<root><child>text</child></root>"
        elem = _as_element(xml)
        assert elem.tag == "root"
        assert elem.find("child") is not None

    def test_from_string(self) -> None:
        xml = "<root><child>text</child></root>"
        elem = _as_element(xml)
        assert elem.tag == "root"

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError, match="Unsupported XML payload type"):
            _as_element(12345)  # type: ignore[arg-type]


class TestTextExtraction:
    """Tests for text extraction helpers."""

    def test_text_from_element(self) -> None:
        xml = b"<root><child>hello world</child></root>"
        elem = _as_element(xml)
        result = _text(elem, "./child/text()")
        assert result == "hello world"

    def test_text_strips_whitespace(self) -> None:
        xml = b"<root><child>  hello  </child></root>"
        elem = _as_element(xml)
        result = _text(elem, "./child/text()")
        assert result == "hello"

    def test_text_returns_none_for_missing(self) -> None:
        xml = b"<root><child></child></root>"
        elem = _as_element(xml)
        result = _text(elem, "./missing/text()")
        assert result is None

    def test_collect_texts(self) -> None:
        xml = b"<root><item>one</item><item>two</item><item>three</item></root>"
        elem = _as_element(xml)
        result = _collect_texts(elem, "./item/text()")
        assert result == ["one", "two", "three"]

    def test_collect_texts_strips_whitespace(self) -> None:
        xml = b"<root><item>  one  </item><item>  </item><item>two</item></root>"
        elem = _as_element(xml)
        result = _collect_texts(elem, "./item/text()")
        assert result == ["one", "two"]  # Empty items filtered


class TestNamespaces:
    """Tests for namespace definitions."""

    def test_namespaces_defined(self) -> None:
        assert "ops" in NS
        assert "epo" in NS
        assert "ft" in NS
        assert "cpc" in NS

    def test_namespace_values(self) -> None:
        assert "epo.org" in NS["ops"]
        assert "epo.org/exchange" in NS["epo"]


class TestFirst:
    """Tests for _first helper."""

    def test_returns_first_element(self) -> None:
        from patent_client_agents.epo_ops.parsing import _first

        xml = b"<root><item>one</item><item>two</item></root>"
        elem = _as_element(xml)
        result = _first(elem.xpath("./item"))
        assert result is not None
        assert result.text == "one"

    def test_returns_none_for_empty(self) -> None:
        from patent_client_agents.epo_ops.parsing import _first

        xml = b"<root></root>"
        elem = _as_element(xml)
        result = _first(elem.xpath("./item"))
        assert result is None


class TestParseDocumentId:
    """Tests for _parse_document_id helper."""

    def test_parses_document_id(self) -> None:
        from patent_client_agents.epo_ops.parsing import _parse_document_id

        xml = b"""<doc-id xmlns="http://www.epo.org/exchange">
            <country>US</country>
            <doc-number>12345678</doc-number>
            <kind>A1</kind>
            <date>20230515</date>
        </doc-id>"""
        elem = _as_element(xml)
        doc_id = _parse_document_id(elem)
        assert doc_id.country == "US"
        assert doc_id.doc_number == "12345678"
        assert doc_id.kind == "A1"
        assert doc_id.date == "20230515"

    def test_returns_empty_for_none(self) -> None:
        from patent_client_agents.epo_ops.parsing import _parse_document_id

        doc_id = _parse_document_id(None)
        assert doc_id.country is None
        assert doc_id.doc_number is None


class TestParseSearchResponse:
    """Tests for parse_search_response function."""

    def test_parses_search_results(self) -> None:
        from patent_client_agents.epo_ops.parsing import parse_search_response

        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange">
            <ops:biblio-search total-result-count="125">
                <ops:query>ta=electric vehicle</ops:query>
                <ops:range begin="1" end="25"/>
                <ops:search-result>
                    <ops:publication-reference family-id="12345">
                        <epo:document-id>
                            <epo:country>US</epo:country>
                            <epo:doc-number>10123456</epo:doc-number>
                            <epo:kind>B2</epo:kind>
                            <epo:date>20230601</epo:date>
                        </epo:document-id>
                    </ops:publication-reference>
                </ops:search-result>
            </ops:biblio-search>
        </ops:world-patent-data>"""

        result = parse_search_response(xml)
        assert result.query == "ta=electric vehicle"
        assert result.total_results == 125
        assert result.range_begin == 1
        assert result.range_end == 25
        assert len(result.results) == 1
        assert result.results[0].docdb_number == "US10123456B2"
        assert result.results[0].country == "US"
        assert result.results[0].doc_number == "10123456"
        assert result.results[0].kind == "B2"

    def test_handles_empty_results(self) -> None:
        from patent_client_agents.epo_ops.parsing import parse_search_response

        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange">
            <ops:biblio-search total-result-count="0">
                <ops:query>invalid query</ops:query>
            </ops:biblio-search>
        </ops:world-patent-data>"""

        result = parse_search_response(xml)
        assert result.total_results == 0
        assert len(result.results) == 0


class TestParseBiblioResponse:
    """Tests for parse_biblio_response function."""

    def test_parses_biblio_record(self) -> None:
        from patent_client_agents.epo_ops.parsing import parse_biblio_response

        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange">
            <epo:exchange-document family-id="12345">
                <epo:publication-reference>
                    <epo:document-id document-id-type="docdb">
                        <epo:country>US</epo:country>
                        <epo:doc-number>10123456</epo:doc-number>
                        <epo:kind>B2</epo:kind>
                    </epo:document-id>
                </epo:publication-reference>
                <epo:bibliographic-data>
                    <epo:invention-title lang="en">Test Invention Title</epo:invention-title>
                    <epo:abstract lang="en">This is the abstract text.</epo:abstract>
                    <epo:parties>
                        <epo:applicants>
                            <epo:applicant>
                                <epo:name>Test Corporation</epo:name>
                            </epo:applicant>
                        </epo:applicants>
                        <epo:inventors>
                            <epo:inventor>
                                <epo:name>John Inventor</epo:name>
                            </epo:inventor>
                        </epo:inventors>
                    </epo:parties>
                </epo:bibliographic-data>
            </epo:exchange-document>
        </ops:world-patent-data>"""

        result = parse_biblio_response(xml)
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.docdb_number == "US10123456B2"
        assert doc.family_id == "12345"
        assert doc.title == "Test Invention Title"
        assert doc.abstract == "This is the abstract text."
        assert "Test Corporation" in doc.applicants
        assert "John Inventor" in doc.inventors

    def test_handles_missing_fields(self) -> None:
        from patent_client_agents.epo_ops.parsing import parse_biblio_response

        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange">
            <epo:exchange-document>
            </epo:exchange-document>
        </ops:world-patent-data>"""

        result = parse_biblio_response(xml)
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.title is None
        assert doc.abstract is None
        assert doc.applicants == []


class TestParseClaims:
    """Tests for parse_claims function."""

    def test_parses_claims(self) -> None:
        from patent_client_agents.epo_ops.parsing import parse_claims

        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ft:fulltext-document xmlns:ft="http://www.epo.org/fulltext">
            <ft:document-id>
                <ft:country>US</ft:country>
                <ft:doc-number>10123456</ft:doc-number>
                <ft:kind>B2</ft:kind>
            </ft:document-id>
            <ft:claims>
                <ft:claim num="1">
                    <ft:claim-text>A method comprising step one.</ft:claim-text>
                </ft:claim>
                <ft:claim num="2">
                    <ft:claim-text>The method of claim 1.</ft:claim-text>
                </ft:claim>
            </ft:claims>
        </ft:fulltext-document>"""

        result = parse_claims(xml, "claims")
        assert result.docdb_number == "US10123456B2"
        assert result.section == "claims"
        assert len(result.claims) == 2
        assert result.claims[0].number == 1
        assert "step one" in (result.claims[0].text or "")
        assert result.claims[1].number == 2

    def test_parses_description(self) -> None:
        from patent_client_agents.epo_ops.parsing import parse_claims

        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ft:fulltext-document xmlns:ft="http://www.epo.org/fulltext">
            <ft:document-id>
                <ft:country>EP</ft:country>
                <ft:doc-number>3456789</ft:doc-number>
                <ft:kind>A1</ft:kind>
            </ft:document-id>
            <ft:description>
                <ft:p>This is the first paragraph of the description.</ft:p>
                <ft:p>This is the second paragraph.</ft:p>
            </ft:description>
        </ft:fulltext-document>"""

        result = parse_claims(xml, "description")
        assert result.docdb_number == "EP3456789A1"
        assert result.section == "description"
        assert result.description is not None
        assert "first paragraph" in result.description
        assert "second paragraph" in result.description


class TestParseFamily:
    """Tests for parse_family function."""

    def test_parses_family_response(self) -> None:
        from patent_client_agents.epo_ops.parsing import parse_family

        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange">
            <ops:patent-family total-result-count="3">
                <ops:publication-reference>
                    <epo:document-id document-id-type="docdb">
                        <epo:doc-number>US10123456</epo:doc-number>
                    </epo:document-id>
                </ops:publication-reference>
                <ops:family-member>
                    <epo:publication-reference>
                        <epo:document-id>
                            <epo:country>US</epo:country>
                            <epo:doc-number>10123456</epo:doc-number>
                            <epo:kind>B2</epo:kind>
                        </epo:document-id>
                    </epo:publication-reference>
                    <epo:application-reference>
                        <epo:document-id>
                            <epo:country>US</epo:country>
                            <epo:doc-number>15123456</epo:doc-number>
                        </epo:document-id>
                    </epo:application-reference>
                </ops:family-member>
            </ops:patent-family>
        </ops:world-patent-data>"""

        result = parse_family(xml)
        assert result.publication_number == "US10123456"
        assert result.num_records == 3
        assert len(result.members) == 1
        assert result.members[0].publication_number == "US10123456B2"
