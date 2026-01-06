"""Tests for EPO OPS XML parsing functions."""

from ip_tools.epo_ops.parsing import (
    parse_biblio_response,
    parse_claims,
    parse_family,
    parse_legal_events,
    parse_number_conversion,
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
