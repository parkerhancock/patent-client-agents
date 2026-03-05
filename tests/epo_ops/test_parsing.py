"""Tests for EPO OPS XML parsing functions."""

import pytest

from ip_tools.epo_ops.parsing import (
    XmlParseError,
    _bool_attr,
    _int_attr,
    parse_biblio_response,
    parse_claims,
    parse_classification_mapping,
    parse_cpc_retrieval,
    parse_cpc_search,
    parse_cpci_biblio,
    parse_family,
    parse_legal_events,
    parse_number_conversion,
    parse_register_biblio,
    parse_register_events,
    parse_register_procedural_steps,
    parse_register_search,
    parse_register_upp,
    parse_search_response,
)


class TestParseSearchResponse:
    """Tests for parse_search_response."""

    def test_basic_search_response(self):
        """Test parsing a basic search response."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <ops:biblio-search total-result-count="2">
                <ops:query>ta=robot</ops:query>
                <ops:range begin="1" end="2"/>
                <ops:search-result>
                    <ops:publication-reference>
                        <epo:document-id document-id-type="docdb">
                            <epo:country>EP</epo:country>
                            <epo:doc-number>1234567</epo:doc-number>
                            <epo:kind>A1</epo:kind>
                        </epo:document-id>
                    </ops:publication-reference>
                    <ops:publication-reference>
                        <epo:document-id document-id-type="docdb">
                            <epo:country>US</epo:country>
                            <epo:doc-number>9876543</epo:doc-number>
                            <epo:kind>B2</epo:kind>
                        </epo:document-id>
                    </ops:publication-reference>
                </ops:search-result>
            </ops:biblio-search>
        </ops:world-patent-data>
        """
        result = parse_search_response(xml)

        assert result.total_results == 2
        assert result.query == "ta=robot"
        assert result.range_begin == 1
        assert result.range_end == 2
        assert len(result.results) == 2
        assert result.results[0].country == "EP"
        assert result.results[0].doc_number == "1234567"
        assert result.results[0].kind == "A1"
        assert result.results[1].country == "US"

    def test_empty_search_response(self):
        """Test parsing a search response with no results."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <ops:biblio-search total-result-count="0">
                <ops:query>ta=nonexistent</ops:query>
                <ops:range begin="1" end="0"/>
                <ops:search-result/>
            </ops:biblio-search>
        </ops:world-patent-data>
        """
        result = parse_search_response(xml)

        assert result.total_results == 0
        assert len(result.results) == 0


class TestParseBiblioResponse:
    """Tests for parse_biblio_response."""

    def test_basic_biblio(self):
        """Test parsing basic bibliographic data."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <ops:register-search>
                <epo:exchange-documents>
                    <epo:exchange-document country="EP" doc-number="1234567" kind="A1" family-id="12345">
                        <epo:bibliographic-data>
                            <epo:publication-reference>
                                <epo:document-id document-id-type="docdb">
                                    <epo:country>EP</epo:country>
                                    <epo:doc-number>1234567</epo:doc-number>
                                    <epo:kind>A1</epo:kind>
                                    <epo:date>20200101</epo:date>
                                </epo:document-id>
                            </epo:publication-reference>
                            <epo:invention-title lang="en">Test Invention Title</epo:invention-title>
                            <epo:parties>
                                <epo:applicants>
                                    <epo:applicant>
                                        <epo:applicant-name>
                                            <epo:name>ACME Corporation</epo:name>
                                        </epo:applicant-name>
                                    </epo:applicant>
                                </epo:applicants>
                                <epo:inventors>
                                    <epo:inventor>
                                        <epo:inventor-name>
                                            <epo:name>John Doe</epo:name>
                                        </epo:inventor-name>
                                    </epo:inventor>
                                </epo:inventors>
                            </epo:parties>
                            <epo:classifications-ipcr>
                                <epo:classification-ipcr>
                                    <epo:text>H04L 9/32</epo:text>
                                </epo:classification-ipcr>
                            </epo:classifications-ipcr>
                        </epo:bibliographic-data>
                        <epo:abstract lang="en">This is the abstract text.</epo:abstract>
                    </epo:exchange-document>
                </epo:exchange-documents>
            </ops:register-search>
        </ops:world-patent-data>
        """
        result = parse_biblio_response(xml)

        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.family_id == "12345"
        assert doc.title == "Test Invention Title"
        assert doc.abstract == "This is the abstract text."
        assert "ACME Corporation" in doc.applicants
        assert "John Doe" in doc.inventors


class TestParseClaims:
    """Tests for parse_claims."""

    def test_basic_claims(self):
        """Test parsing claim text."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:ft="http://www.epo.org/fulltext">
            <ft:fulltext-documents>
                <ft:fulltext-document>
                    <ft:claims lang="en">
                        <ft:claim>
                            <ft:claim-text>1. A method comprising step A.</ft:claim-text>
                        </ft:claim>
                        <ft:claim>
                            <ft:claim-text>2. The method of claim 1, further comprising step B.</ft:claim-text>
                        </ft:claim>
                    </ft:claims>
                </ft:fulltext-document>
            </ft:fulltext-documents>
        </ops:world-patent-data>
        """
        result = parse_claims(xml, section="claims")

        assert result.section == "claims"
        assert len(result.claims) == 2
        assert "step A" in result.claims[0].text
        assert "step B" in result.claims[1].text


class TestParseFamily:
    """Tests for parse_family."""

    def test_basic_family(self):
        """Test parsing patent family data."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <ops:patent-family total-result-count="3">
                <ops:family-member family-id="12345">
                    <epo:publication-reference>
                        <epo:document-id document-id-type="docdb">
                            <epo:country>EP</epo:country>
                            <epo:doc-number>1234567</epo:doc-number>
                            <epo:kind>A1</epo:kind>
                        </epo:document-id>
                    </epo:publication-reference>
                    <epo:application-reference>
                        <epo:document-id document-id-type="docdb">
                            <epo:country>EP</epo:country>
                            <epo:doc-number>20200001</epo:doc-number>
                        </epo:document-id>
                    </epo:application-reference>
                </ops:family-member>
                <ops:family-member family-id="12345">
                    <epo:publication-reference>
                        <epo:document-id document-id-type="docdb">
                            <epo:country>US</epo:country>
                            <epo:doc-number>11111111</epo:doc-number>
                            <epo:kind>B2</epo:kind>
                        </epo:document-id>
                    </epo:publication-reference>
                </ops:family-member>
            </ops:patent-family>
        </ops:world-patent-data>
        """
        result = parse_family(xml)

        assert result.num_records == 3
        assert len(result.members) == 2
        assert result.members[0].family_id == "12345"


class TestParseLegalEvents:
    """Tests for parse_legal_events."""

    def test_minimal_legal_events(self):
        """Test parsing minimal legal events structure."""
        # Legal events parsing is complex - test that the function doesn't crash
        # on minimal valid input
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <ops:register-search>
                <epo:register-documents>
                    <epo:register-document>
                        <epo:bibliographic-data>
                            <epo:publication-reference>
                                <epo:document-id>
                                    <epo:country>EP</epo:country>
                                    <epo:doc-number>1234567</epo:doc-number>
                                    <epo:kind>A1</epo:kind>
                                </epo:document-id>
                            </epo:publication-reference>
                        </epo:bibliographic-data>
                    </epo:register-document>
                </epo:register-documents>
            </ops:register-search>
        </ops:world-patent-data>
        """
        result = parse_legal_events(xml)

        # Should return a valid response even with no events
        assert result is not None
        assert isinstance(result.events, list)


class TestParseNumberConversion:
    """Tests for parse_number_conversion."""

    def test_number_conversion(self):
        """Test parsing number conversion response."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <ops:standardization>
                <ops:input>
                    <epo:document-id>
                        <epo:country>US</epo:country>
                        <epo:doc-number>10123456</epo:doc-number>
                        <epo:kind>B2</epo:kind>
                    </epo:document-id>
                </ops:input>
                <ops:output>
                    <epo:document-id>
                        <epo:country>US</epo:country>
                        <epo:doc-number>10123456</epo:doc-number>
                        <epo:kind>B2</epo:kind>
                    </epo:document-id>
                </ops:output>
            </ops:standardization>
        </ops:world-patent-data>
        """
        result = parse_number_conversion(xml)

        assert result.input_document.country == "US"
        assert result.output_document.country == "US"
        assert result.input_document.doc_number == "10123456"


class TestParseDescription:
    """Tests for parse_claims with section='description'."""

    def test_description_with_paragraphs(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:ft="http://www.epo.org/fulltext">
            <ft:fulltext-documents>
                <ft:fulltext-document>
                    <ft:document-id>
                        <ft:country>EP</ft:country>
                        <ft:doc-number>1234567</ft:doc-number>
                        <ft:kind>A1</ft:kind>
                    </ft:document-id>
                    <ft:description lang="en">
                        <ft:p>First paragraph of the description.</ft:p>
                        <ft:p>Second paragraph with <ft:b>bold</ft:b> text.</ft:p>
                    </ft:description>
                </ft:fulltext-document>
            </ft:fulltext-documents>
        </ops:world-patent-data>
        """
        result = parse_claims(xml, section="description")

        assert result.section == "description"
        assert result.docdb_number == "EP1234567A1"
        assert "First paragraph" in result.description
        assert "Second paragraph" in result.description
        assert result.raw_text == result.description
        assert len(result.claims) == 0

    def test_description_fallback_no_paragraphs(self):
        """When no <ft:p> elements exist, fall back to all text under description."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:ft="http://www.epo.org/fulltext">
            <ft:fulltext-documents>
                <ft:fulltext-document>
                    <ft:description lang="en">Some raw description text without paragraphs.</ft:description>
                </ft:fulltext-document>
            </ft:fulltext-documents>
        </ops:world-patent-data>
        """
        result = parse_claims(xml, section="description")

        assert result.section == "description"
        assert "raw description text" in result.description

    def test_description_empty(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:ft="http://www.epo.org/fulltext">
            <ft:fulltext-documents>
                <ft:fulltext-document>
                    <ft:description lang="en"></ft:description>
                </ft:fulltext-document>
            </ft:fulltext-documents>
        </ops:world-patent-data>
        """
        result = parse_claims(xml, section="description")

        assert result.section == "description"
        assert result.description is None
        assert result.raw_text is None


class TestBoolAttrAndIntAttr:
    """Tests for _bool_attr and _int_attr helper functions."""

    def test_bool_attr_true_values(self):
        import lxml.etree as etree

        el = etree.fromstring('<item flag="true"/>')
        assert _bool_attr(el, "flag") is True
        el = etree.fromstring('<item flag="1"/>')
        assert _bool_attr(el, "flag") is True
        el = etree.fromstring('<item flag="yes"/>')
        assert _bool_attr(el, "flag") is True

    def test_bool_attr_false_values(self):
        import lxml.etree as etree

        el = etree.fromstring('<item flag="false"/>')
        assert _bool_attr(el, "flag") is False

    def test_bool_attr_missing(self):
        import lxml.etree as etree

        el = etree.fromstring("<item/>")
        assert _bool_attr(el, "flag") is None

    def test_int_attr(self):
        import lxml.etree as etree

        el = etree.fromstring('<item level="3"/>')
        assert _int_attr(el, "level") == 3

    def test_int_attr_missing(self):
        import lxml.etree as etree

        el = etree.fromstring("<item/>")
        assert _int_attr(el, "level") is None

    def test_int_attr_non_digit(self):
        import lxml.etree as etree

        el = etree.fromstring('<item level="abc"/>')
        assert _int_attr(el, "level") is None


class TestParseCpcRetrieval:
    """Tests for parse_cpc_retrieval."""

    def test_basic_cpc_retrieval(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:cpc="http://www.epo.org/cpcexport">
            <cpc:class-scheme scheme-type="cpc" export-date="2024-01-01">
                <cpc:classification-item level="5" additional-only="false"
                        sort-key="H04L0009320000" date-revised="2020-01-01"
                        not-allocatable="false" breakdown-code="true"
                        link-file="H04L0009320000.xml">
                    <cpc:classification-symbol>H04L9/32</cpc:classification-symbol>
                    <cpc:class-title>
                        <cpc:title-part scheme="ipc">
                            <cpc:text>Arrangements for secret or secure communications</cpc:text>
                        </cpc:title-part>
                        <cpc:title-part>
                            <cpc:text>including means for verifying identity</cpc:text>
                            <cpc:media id="fig1" type="image"/>
                        </cpc:title-part>
                    </cpc:class-title>
                    <cpc:meta-data>Some metadata</cpc:meta-data>
                    <cpc:classification-item level="6">
                        <cpc:classification-symbol>H04L9/3226</cpc:classification-symbol>
                        <cpc:class-title>
                            <cpc:title-part>
                                <cpc:text>using a predetermined key</cpc:text>
                            </cpc:title-part>
                        </cpc:class-title>
                    </cpc:classification-item>
                </cpc:classification-item>
            </cpc:class-scheme>
        </ops:world-patent-data>
        """
        result = parse_cpc_retrieval(xml)

        assert result.scheme.scheme_type == "cpc"
        assert result.scheme.export_date == "2024-01-01"
        assert len(result.scheme.items) == 1

        item = result.scheme.items[0]
        assert item.symbol == "H04L9/32"
        assert item.level == 5
        assert item.additional_only is False
        assert item.sort_key == "H04L0009320000"
        assert item.date_revised == "2020-01-01"
        assert item.not_allocatable is False
        assert item.breakdown_code is True
        assert item.link == "H04L0009320000.xml"
        assert "Arrangements for secret" in item.title
        assert "verifying identity" in item.title
        assert len(item.title_parts) == 2
        assert item.title_parts[0].scheme == "ipc"
        assert item.title_parts[1].media_id == "fig1"
        assert item.title_parts[1].media_type == "image"
        assert "Some metadata" in item.metadata

        # Check nested child
        assert len(item.children) == 1
        child = item.children[0]
        assert child.symbol == "H04L9/3226"
        assert child.level == 6
        assert "predetermined key" in child.title

    def test_missing_class_scheme_raises(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:cpc="http://www.epo.org/cpcexport">
        </ops:world-patent-data>
        """
        with pytest.raises(XmlParseError, match="Missing cpc:class-scheme"):
            parse_cpc_retrieval(xml)


class TestParseCpcSearch:
    """Tests for parse_cpc_search."""

    def test_cpc_search(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:cpc="http://www.epo.org/cpcexport">
            <ops:classification-search total-result-count="2">
                <ops:query>robot</ops:query>
                <ops:range begin="1" end="2"/>
                <ops:classification-statistics classification-symbol="B25J9/16" percentage="45.5">
                    <cpc:class-title>
                        <cpc:title-part>
                            <cpc:text>Programme-controlled manipulators</cpc:text>
                        </cpc:title-part>
                    </cpc:class-title>
                </ops:classification-statistics>
                <ops:classification-statistics classification-symbol="B25J11/00" percentage="invalid">
                    <cpc:class-title>
                        <cpc:title-part>
                            <cpc:text>Manipulators not otherwise provided for</cpc:text>
                        </cpc:title-part>
                    </cpc:class-title>
                </ops:classification-statistics>
            </ops:classification-search>
        </ops:world-patent-data>
        """
        result = parse_cpc_search(xml)

        assert result.query == "robot"
        assert result.total_results == 2
        assert result.range_begin == 1
        assert result.range_end == 2
        assert len(result.results) == 2

        assert result.results[0].classification_symbol == "B25J9/16"
        assert result.results[0].percentage == 45.5
        assert "Programme-controlled" in result.results[0].title

        # Invalid percentage should be None
        assert result.results[1].percentage is None


class TestParseClassificationMapping:
    """Tests for parse_classification_mapping."""

    def test_classification_mapping(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org">
            <ops:mappings inputSchema="ipc" outputSchema="cpc">
                <ops:mapping additional-only="false">
                    <ops:cpc>H04L9/32</ops:cpc>
                    <ops:ipc>H04L9/32</ops:ipc>
                </ops:mapping>
                <ops:mapping additional-only="true">
                    <ops:cpc>H04L9/3226</ops:cpc>
                    <ops:ecla>H04L9/32S</ops:ecla>
                </ops:mapping>
            </ops:mappings>
        </ops:world-patent-data>
        """
        result = parse_classification_mapping(xml)

        assert result.input_schema == "ipc"
        assert result.output_schema == "cpc"
        assert len(result.mappings) == 2

        assert result.mappings[0].cpc == "H04L9/32"
        assert result.mappings[0].ipc == "H04L9/32"
        assert result.mappings[0].additional_only is False

        assert result.mappings[1].cpc == "H04L9/3226"
        assert result.mappings[1].ecla == "H04L9/32S"
        assert result.mappings[1].additional_only is True

    def test_no_mappings_node(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org">
        </ops:world-patent-data>
        """
        result = parse_classification_mapping(xml)
        assert result.input_schema is None
        assert result.output_schema is None
        assert len(result.mappings) == 0


class TestParseCpciBiblio:
    """Tests for parse_cpci_biblio."""

    def test_cpci_biblio(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <epo:exchange-documents>
                <epo:exchange-document>
                    <epo:bibliographic-data>
                        <epo:publication-reference>
                            <epo:document-id document-id-type="docdb">
                                <epo:country>EP</epo:country>
                                <epo:doc-number>1234567</epo:doc-number>
                                <epo:kind>A1</epo:kind>
                            </epo:document-id>
                        </epo:publication-reference>
                        <epo:patent-classifications>
                            <epo:patent-classification sequence="1">
                                <epo:section>H</epo:section>
                                <epo:class>04</epo:class>
                                <epo:subclass>L</epo:subclass>
                                <epo:main-group>9</epo:main-group>
                                <epo:subgroup>32</epo:subgroup>
                                <epo:classification-value>I</epo:classification-value>
                                <epo:generating-office>EP, US</epo:generating-office>
                            </epo:patent-classification>
                        </epo:patent-classifications>
                    </epo:bibliographic-data>
                </epo:exchange-document>
            </epo:exchange-documents>
        </ops:world-patent-data>
        """
        result = parse_cpci_biblio(xml)

        assert len(result.records) == 1
        rec = result.records[0]
        assert rec.docdb_number == "EP1234567A1"
        assert len(rec.classifications) == 1

        cls = rec.classifications[0]
        assert cls.sequence == 1
        assert cls.section == "H"
        assert cls.class_code == "04"
        assert cls.subclass == "L"
        assert cls.main_group == "9"
        assert cls.subgroup == "32"
        assert cls.classification_value == "I"
        assert cls.generating_offices == ["EP", "US"]

    def test_cpci_biblio_no_generating_office(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <epo:exchange-documents>
                <epo:exchange-document>
                    <epo:bibliographic-data>
                        <epo:publication-reference>
                            <epo:document-id document-id-type="docdb">
                                <epo:country>US</epo:country>
                                <epo:doc-number>9999999</epo:doc-number>
                                <epo:kind>B2</epo:kind>
                            </epo:document-id>
                        </epo:publication-reference>
                        <epo:patent-classifications>
                            <epo:patent-classification>
                                <epo:section>A</epo:section>
                            </epo:patent-classification>
                        </epo:patent-classifications>
                    </epo:bibliographic-data>
                </epo:exchange-document>
            </epo:exchange-documents>
        </ops:world-patent-data>
        """
        result = parse_cpci_biblio(xml)
        assert len(result.records) == 1
        assert result.records[0].classifications[0].generating_offices == []

    def test_cpci_biblio_empty(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <epo:exchange-documents>
                <epo:exchange-document>
                    <epo:bibliographic-data>
                    </epo:bibliographic-data>
                </epo:exchange-document>
            </epo:exchange-documents>
        </ops:world-patent-data>
        """
        result = parse_cpci_biblio(xml)
        # No publication ref and no classifications -> record is skipped
        assert len(result.records) == 0


class TestParseRegisterSearch:
    """Tests for parse_register_search."""

    def test_register_search(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange"
                               xmlns:reg="http://www.epo.org/register">
            <ops:register-search total-result-count="1">
                <ops:query>pa="Siemens"</ops:query>
                <ops:range begin="1" end="1"/>
                <reg:register-documents>
                    <reg:register-document>
                        <reg:application-reference>
                            <epo:doc-number>EP20200001</epo:doc-number>
                        </reg:application-reference>
                        <reg:publication-reference>
                            <epo:country>EP</epo:country>
                            <epo:doc-number>3999999</epo:doc-number>
                            <epo:kind>A1</epo:kind>
                        </reg:publication-reference>
                        <reg:applicant>
                            <reg:name>Siemens AG</reg:name>
                        </reg:applicant>
                        <reg:invention-title lang="en">A Smart Device</reg:invention-title>
                        <reg:status>Grant of patent</reg:status>
                        <reg:application-date>20200115</reg:application-date>
                    </reg:register-document>
                </reg:register-documents>
            </ops:register-search>
        </ops:world-patent-data>
        """
        result = parse_register_search(xml)

        assert result.query == 'pa="Siemens"'
        assert result.total_results == 1
        assert result.range_begin == 1
        assert result.range_end == 1
        assert len(result.results) == 1

        r = result.results[0]
        assert r.application_number == "EP20200001"
        assert r.publication_number == "EP3999999A1"
        assert r.title == "A Smart Device"
        assert "Siemens AG" in r.applicants
        assert r.status == "Grant of patent"
        assert r.application_date == "20200115"

    def test_register_search_empty(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:reg="http://www.epo.org/register">
            <ops:register-search total-result-count="0">
                <ops:query>pa="Nobody"</ops:query>
                <ops:range begin="1" end="0"/>
            </ops:register-search>
        </ops:world-patent-data>
        """
        result = parse_register_search(xml)
        assert result.total_results == 0
        assert len(result.results) == 0


class TestParseRegisterBiblio:
    """Tests for parse_register_biblio."""

    def test_full_register_biblio(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange"
                               xmlns:reg="http://www.epo.org/register">
            <reg:register-documents>
                <reg:register-document>
                    <reg:application-reference>
                        <epo:doc-number>EP20200001</epo:doc-number>
                    </reg:application-reference>
                    <reg:application-date>20200115</reg:application-date>
                    <reg:publication-reference>
                        <epo:country>EP</epo:country>
                        <epo:doc-number>3999999</epo:doc-number>
                        <epo:kind>B1</epo:kind>
                        <epo:date>20220601</epo:date>
                    </reg:publication-reference>
                    <reg:date-of-grant>20220601</reg:date-of-grant>
                    <reg:invention-title lang="en">A Smart Device</reg:invention-title>
                    <reg:applicant>
                        <reg:name>Siemens AG</reg:name>
                    </reg:applicant>
                    <reg:inventor>
                        <reg:name>Max Mustermann</reg:name>
                    </reg:inventor>
                    <reg:agent>
                        <reg:name>Patent Attorney Firm</reg:name>
                    </reg:agent>
                    <reg:designated-states>
                        <reg:designated-state>
                            <reg:country>DE</reg:country>
                            <reg:effective-date>20220701</reg:effective-date>
                        </reg:designated-state>
                        <reg:designated-state>
                            <reg:country>FR</reg:country>
                        </reg:designated-state>
                    </reg:designated-states>
                    <reg:status>Grant of patent</reg:status>
                    <reg:status-description>The patent has been granted.</reg:status-description>
                    <reg:opposition>
                        <reg:opposition-date>20221001</reg:opposition-date>
                        <reg:status>Opposition pending</reg:status>
                        <reg:party role="opponent">
                            <reg:name>Competitor Inc.</reg:name>
                            <reg:country>US</reg:country>
                        </reg:party>
                        <reg:party role="patent_owner">
                            <reg:name>Siemens AG</reg:name>
                            <reg:country>DE</reg:country>
                        </reg:party>
                    </reg:opposition>
                </reg:register-document>
            </reg:register-documents>
        </ops:world-patent-data>
        """
        result = parse_register_biblio(xml)

        assert result.application_number == "EP20200001"
        assert result.application_date == "20200115"
        assert result.publication_number == "EP3999999B1"
        assert result.publication_date == "20220601"
        assert result.grant_date == "20220601"
        assert result.title == "A Smart Device"
        assert "Siemens AG" in result.applicants
        assert "Max Mustermann" in result.inventors
        assert "Patent Attorney Firm" in result.representatives

        assert len(result.designated_states) == 2
        assert result.designated_states[0].country_code == "DE"
        assert result.designated_states[0].effective_date == "20220701"
        assert result.designated_states[1].country_code == "FR"

        assert result.status == "Grant of patent"
        assert result.status_description == "The patent has been granted."

        assert result.opposition is not None
        assert result.opposition.opposition_date == "20221001"
        assert result.opposition.status == "Opposition pending"
        assert len(result.opposition.parties) == 2
        assert result.opposition.parties[0].name == "Competitor Inc."
        assert result.opposition.parties[0].role == "opponent"
        assert result.opposition.parties[1].name == "Siemens AG"

    def test_register_biblio_no_document(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:reg="http://www.epo.org/register">
        </ops:world-patent-data>
        """
        result = parse_register_biblio(xml)
        assert result.application_number is None
        assert result.publication_number is None

    def test_register_biblio_no_opposition(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange"
                               xmlns:reg="http://www.epo.org/register">
            <reg:register-documents>
                <reg:register-document>
                    <reg:application-reference>
                        <epo:doc-number>EP20200002</epo:doc-number>
                    </reg:application-reference>
                    <reg:invention-title lang="de">Ein Geraet</reg:invention-title>
                </reg:register-document>
            </reg:register-documents>
        </ops:world-patent-data>
        """
        result = parse_register_biblio(xml)
        assert result.application_number == "EP20200002"
        # Falls back to non-English title when no lang="en"
        assert result.title == "Ein Geraet"
        assert result.opposition is None


class TestParseRegisterEvents:
    """Tests for parse_register_events."""

    def test_register_events(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange"
                               xmlns:reg="http://www.epo.org/register">
            <reg:register-documents>
                <reg:register-document>
                    <reg:application-reference>
                        <epo:doc-number>EP20200001</epo:doc-number>
                    </reg:application-reference>
                    <reg:events>
                        <reg:event>
                            <reg:event-code>RFEE</reg:event-code>
                            <reg:event-date>20210115</reg:event-date>
                            <reg:event-description>Renewal fee paid</reg:event-description>
                            <reg:bulletin-number>2021/05</reg:bulletin-number>
                            <reg:bulletin-date>20210203</reg:bulletin-date>
                        </reg:event>
                        <reg:event>
                            <reg:event-code>GRNT</reg:event-code>
                            <reg:event-date>20220601</reg:event-date>
                            <reg:event-description>Grant of patent</reg:event-description>
                        </reg:event>
                    </reg:events>
                </reg:register-document>
            </reg:register-documents>
        </ops:world-patent-data>
        """
        result = parse_register_events(xml)

        assert result.application_number == "EP20200001"
        assert len(result.events) == 2

        e0 = result.events[0]
        assert e0.event_code == "RFEE"
        assert e0.event_date == "20210115"
        assert e0.event_description == "Renewal fee paid"
        assert e0.bulletin_number == "2021/05"
        assert e0.bulletin_date == "20210203"

        e1 = result.events[1]
        assert e1.event_code == "GRNT"

    def test_register_events_no_doc(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:reg="http://www.epo.org/register">
        </ops:world-patent-data>
        """
        result = parse_register_events(xml)
        assert result.application_number is None
        assert len(result.events) == 0


class TestParseRegisterProceduralSteps:
    """Tests for parse_register_procedural_steps."""

    def test_procedural_steps(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange"
                               xmlns:reg="http://www.epo.org/register">
            <reg:register-documents>
                <reg:register-document>
                    <reg:application-reference>
                        <epo:doc-number>EP20200001</epo:doc-number>
                    </reg:application-reference>
                    <reg:procedural-steps>
                        <reg:procedural-step>
                            <reg:phase>Examination</reg:phase>
                            <reg:step-code>EXAM</reg:step-code>
                            <reg:step-description>Substantive examination requested</reg:step-description>
                            <reg:step-date>20210301</reg:step-date>
                            <reg:office>Munich</reg:office>
                        </reg:procedural-step>
                        <reg:procedural-step>
                            <reg:phase>Grant</reg:phase>
                            <reg:step-code>GRNT</reg:step-code>
                            <reg:step-description>Patent granted</reg:step-description>
                            <reg:step-date>20220601</reg:step-date>
                        </reg:procedural-step>
                    </reg:procedural-steps>
                </reg:register-document>
            </reg:register-documents>
        </ops:world-patent-data>
        """
        result = parse_register_procedural_steps(xml)

        assert result.application_number == "EP20200001"
        assert len(result.procedural_steps) == 2

        s0 = result.procedural_steps[0]
        assert s0.phase == "Examination"
        assert s0.step_code == "EXAM"
        assert s0.step_description == "Substantive examination requested"
        assert s0.step_date == "20210301"
        assert s0.office == "Munich"

        s1 = result.procedural_steps[1]
        assert s1.phase == "Grant"
        assert s1.office is None

    def test_procedural_steps_no_doc(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:reg="http://www.epo.org/register">
        </ops:world-patent-data>
        """
        result = parse_register_procedural_steps(xml)
        assert result.application_number is None
        assert len(result.procedural_steps) == 0


class TestParseRegisterUpp:
    """Tests for parse_register_upp."""

    def test_register_upp_with_data(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange"
                               xmlns:reg="http://www.epo.org/register">
            <reg:register-documents>
                <reg:register-document>
                    <reg:application-reference>
                        <epo:doc-number>EP20200001</epo:doc-number>
                    </reg:application-reference>
                    <reg:unitary-patent>
                        <reg:status>Registered</reg:status>
                        <reg:registration-date>20230101</reg:registration-date>
                        <reg:participating-states>
                            <reg:participating-state>
                                <reg:country>DE</reg:country>
                            </reg:participating-state>
                            <reg:participating-state>
                                <reg:country>FR</reg:country>
                            </reg:participating-state>
                            <reg:participating-state>
                                <reg:country>IT</reg:country>
                            </reg:participating-state>
                        </reg:participating-states>
                    </reg:unitary-patent>
                </reg:register-document>
            </reg:register-documents>
        </ops:world-patent-data>
        """
        result = parse_register_upp(xml)

        assert result.application_number == "EP20200001"
        assert result.unitary_patent is not None
        assert result.unitary_patent.upp_status == "Registered"
        assert result.unitary_patent.registration_date == "20230101"
        assert result.unitary_patent.participating_states == ["DE", "FR", "IT"]

    def test_register_upp_no_upp_data(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:epo="http://www.epo.org/exchange"
                               xmlns:reg="http://www.epo.org/register">
            <reg:register-documents>
                <reg:register-document>
                    <reg:application-reference>
                        <epo:doc-number>EP20200002</epo:doc-number>
                    </reg:application-reference>
                </reg:register-document>
            </reg:register-documents>
        </ops:world-patent-data>
        """
        result = parse_register_upp(xml)
        assert result.application_number == "EP20200002"
        assert result.unitary_patent is None

    def test_register_upp_no_doc(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org"
                               xmlns:reg="http://www.epo.org/register">
        </ops:world-patent-data>
        """
        result = parse_register_upp(xml)
        assert result.application_number is None
        assert result.unitary_patent is None


class TestParseLegalEventsDetailed:
    """Additional tests for parse_legal_events with actual event data."""

    def test_legal_events_with_event_data(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:epo="http://www.epo.org/exchange">
            <ops:patent-family>
                <ops:publication-reference>
                    <epo:document-id document-id-type="docdb">
                        <epo:country>EP</epo:country>
                        <epo:doc-number>1234567</epo:doc-number>
                        <epo:kind>A1</epo:kind>
                    </epo:document-id>
                </ops:publication-reference>
                <ops:family-member>
                    <ops:legal>
                        <ops:L001EP>EP</ops:L001EP>
                        <ops:L002EP>publication</ops:L002EP>
                        <ops:L003EP>1234567</ops:L003EP>
                        <ops:L005EP>patent</ops:L005EP>
                        <ops:L007EP>20220101</ops:L007EP>
                        <ops:L008EP>B1</ops:L008EP>
                        <ops:L013>current</ops:L013>
                        <ops:L018EP>20220115</ops:L018EP>
                        <ops:L510EP>Grant of patent in EP</ops:L510EP>
                        <ops:pre>Raw text line 1</ops:pre>
                        <ops:pre>Raw text line 2</ops:pre>
                    </ops:legal>
                    <ops:legal>
                        <ops:L001EP>DE</ops:L001EP>
                        <ops:L501EP>DE</ops:L501EP>
                        <ops:L502EP>R119</ops:L502EP>
                        <ops:L007EP>20230601</ops:L007EP>
                    </ops:legal>
                </ops:family-member>
            </ops:patent-family>
        </ops:world-patent-data>
        """
        result = parse_legal_events(xml)

        assert result.publication_reference is not None
        assert result.publication_reference.country == "EP"
        assert result.publication_reference.doc_number == "1234567"

        assert len(result.events) == 2

        e0 = result.events[0]
        assert e0.event_code == "EP.B1"
        assert e0.event_date == "20220101"
        assert e0.event_country == "EP"
        assert e0.country_code == "EP"
        assert e0.filing_or_publication == "publication"
        assert e0.document_number == "1234567"
        assert e0.ip_type == "patent"
        assert e0.free_text == "Grant of patent in EP"
        assert e0.text_record == "Raw text line 1\nRaw text line 2"
        assert e0.metadata["status_of_data"] == "current"
        assert e0.metadata["subscriber_exchange_date"] == "20220115"

        # Second event uses regional code path (L501EP + L502EP)
        e1 = result.events[1]
        assert e1.event_code == "DE.R119"
        assert e1.event_date == "20230601"
        assert e1.event_country == "DE"
