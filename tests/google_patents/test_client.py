"""Tests for Google Patents client."""

from __future__ import annotations

import pytest

from ip_tools.google_patents.client import (
    GooglePatentsClient,
    GooglePatentsSearchResponse,
    PatentData,
    _build_chemical_data,
    _build_child_applications,
    _build_citations,
    _build_citations_simple,
    _build_concepts,
    _build_country_filings,
    _build_definitions,
    _build_detail_url,
    _build_detailed_npl,
    _build_external_links,
    _build_family_members,
    _build_landscapes,
    _build_legal_events,
    _build_non_patent_literature,
    _build_pdf_url,
    _build_priority_applications,
    _build_query_url,
    _build_thumbnail_url,
    _clean_list,
    _custom_encode,
    _html_to_markdown,
    _normalize_patent_number,
    _parse_search_results,
)


class TestGooglePatentsImports:
    """Test that Google Patents module imports work correctly."""

    def test_import_client(self) -> None:
        """Verify GooglePatentsClient can be imported."""
        assert GooglePatentsClient is not None

    def test_import_patent_data(self) -> None:
        """Verify PatentData model can be imported."""
        assert PatentData is not None


@pytest.fixture
def google_patents_client() -> GooglePatentsClient:
    """Create a GooglePatentsClient instance for testing."""
    return GooglePatentsClient(use_cache=False)


class TestGooglePatentsClient:
    """Tests for GooglePatentsClient."""

    def test_client_instantiation(self, google_patents_client: GooglePatentsClient) -> None:
        """Verify client can be instantiated via fixture."""
        assert google_patents_client is not None
        assert google_patents_client._use_cache is False

    def test_client_default_cache(self) -> None:
        """Verify default cache setting is True."""
        client = GooglePatentsClient()
        assert client._use_cache is True

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        async with GooglePatentsClient() as client:
            assert client is not None

    @pytest.mark.asyncio
    async def test_aexit(self) -> None:
        client = GooglePatentsClient()
        await client.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


class TestCustomEncode:
    def test_special_chars(self) -> None:
        assert _custom_encode("a&b") == "a%26b"
        assert _custom_encode("a b") == "a+b"
        assert _custom_encode("a?b") == "a%3fb"
        assert _custom_encode("a/b") == "a%2fb"

    def test_no_encoding_needed(self) -> None:
        assert _custom_encode("hello") == "hello"


class TestCleanList:
    def test_none(self) -> None:
        assert _clean_list(None) == []

    def test_empty(self) -> None:
        assert _clean_list([]) == []

    def test_strips_whitespace(self) -> None:
        assert _clean_list(["  a  ", " b ", "  "]) == ["a", "b"]


class TestNormalizePatentNumber:
    def test_adds_us_prefix(self) -> None:
        assert _normalize_patent_number("7654321B2") == "US7654321B2"

    def test_uppercase(self) -> None:
        assert _normalize_patent_number("us7654321b2") == "US7654321B2"

    def test_pub_app_padding(self) -> None:
        # US app pub with 6-digit serial -> should insert leading 0
        result = _normalize_patent_number("US2004123456A1")
        assert result == "US20040123456A1"

    def test_wo_normalization(self) -> None:
        result = _normalize_patent_number("WO04123456A1")
        # Should expand 2-digit year to 4-digit
        assert result.startswith("WO2004")


class TestBuildUrls:
    def test_build_detail_url(self) -> None:
        assert _build_detail_url("patent/US1234") == "https://patents.google.com/patent/US1234"
        assert _build_detail_url(None) is None
        assert _build_detail_url("") is None

    def test_build_pdf_url(self) -> None:
        assert (
            _build_pdf_url("path/doc.pdf")
            == "https://patentimages.storage.googleapis.com/path/doc.pdf"
        )
        assert _build_pdf_url(None) is None
        assert _build_pdf_url("") is None

    def test_build_thumbnail_url(self) -> None:
        assert (
            _build_thumbnail_url("thumb.png")
            == "https://patentimages.storage.googleapis.com/thumb.png"
        )
        assert _build_thumbnail_url(None) is None
        assert _build_thumbnail_url("") is None


class TestHtmlToMarkdown:
    def test_none_input(self) -> None:
        assert _html_to_markdown(None) is None

    def test_empty_string(self) -> None:
        assert _html_to_markdown("") is None

    def test_simple_html(self) -> None:
        result = _html_to_markdown("<p>Hello world</p>")
        assert result is not None
        assert "Hello world" in result


# ---------------------------------------------------------------------------
# Builder function tests
# ---------------------------------------------------------------------------


class TestBuildCitations:
    def test_with_valid_data(self) -> None:
        data = [
            {
                "publication_number": "US1234567A",
                "publication_date": "2020-01-01",
                "assignee": "Corp",
                "title": "Patent",
                "examiner_cited": True,
            }
        ]
        result = _build_citations(data)
        assert len(result) == 1
        assert result[0].publication_number == "US1234567A"
        assert result[0].examiner_cited is True

    def test_skips_missing_pub_num(self) -> None:
        data: list[dict] = [{"publication_number": None}]
        assert _build_citations(data) == []

    def test_non_string_values(self) -> None:
        data = [
            {
                "publication_number": "US123",
                "publication_date": 12345,
                "assignee": 999,
                "title": None,
                "examiner_cited": False,
            }
        ]
        result = _build_citations(data)
        assert len(result) == 1
        assert result[0].publication_date is None
        assert result[0].assignee is None


class TestBuildCitationsSimple:
    def test_basic(self) -> None:
        data = [{"publication_number": "US999", "publication_date": "2021-01-01"}]
        result = _build_citations_simple(data)
        assert len(result) == 1
        assert result[0].examiner_cited is False

    def test_skips_empty(self) -> None:
        assert _build_citations_simple([{"publication_number": None}]) == []


class TestBuildFamilyMembers:
    def test_basic(self) -> None:
        data = [{"application_number": "US12345", "status": "Active"}]
        result = _build_family_members(data)
        assert len(result) == 1
        assert result[0].application_number == "US12345"

    def test_skips_no_app_num(self) -> None:
        assert _build_family_members([{"application_number": None}]) == []


class TestBuildCountryFilings:
    def test_basic(self) -> None:
        data = [{"country_code": "US", "count": 3, "representative_publication": "US123B2"}]
        result = _build_country_filings(data)
        assert len(result) == 1
        assert result[0].count == 3
        assert result[0].representative_publication == "US123B2"

    def test_count_default(self) -> None:
        data = [{"country_code": "JP", "count": None, "representative_publication": None}]
        result = _build_country_filings(data)
        assert result[0].count == 1
        assert result[0].representative_publication is None

    def test_skips_no_country(self) -> None:
        assert _build_country_filings([{"country_code": None}]) == []


class TestBuildPriorityApplications:
    def test_basic(self) -> None:
        data = [{"application_number": "US12345", "priority_date": "2020-01-01"}]
        result = _build_priority_applications(data)
        assert len(result) == 1

    def test_skips_no_app_num(self) -> None:
        assert _build_priority_applications([{"application_number": None}]) == []


class TestBuildLegalEvents:
    def test_with_title(self) -> None:
        data = [
            {
                "title": "Assignment",
                "date": "2020-01-01",
                "assignee": None,
                "assignor": None,
                "status": None,
            }
        ]
        result = _build_legal_events(data)
        assert len(result) == 1

    def test_with_date_only(self) -> None:
        data = [{"title": None, "date": "2020-01-01"}]
        result = _build_legal_events(data)
        assert len(result) == 1

    def test_skips_no_title_or_date(self) -> None:
        data = [{"title": None, "date": None}]
        assert _build_legal_events(data) == []


class TestBuildNonPatentLiterature:
    def test_basic(self) -> None:
        data = [{"citation": "Smith 2020", "examiner_cited": "true"}]
        result = _build_non_patent_literature(data)
        assert len(result) == 1
        assert result[0].examiner_cited is True

    def test_not_examiner_cited(self) -> None:
        data = [{"citation": "Jones 2019", "examiner_cited": "false"}]
        result = _build_non_patent_literature(data)
        assert result[0].examiner_cited is False

    def test_skips_no_citation(self) -> None:
        assert _build_non_patent_literature([{"citation": None}]) == []


class TestBuildConcepts:
    def test_basic(self) -> None:
        data = [{"name": "Machine Learning", "image_url": "https://example.com/ml.png"}]
        result = _build_concepts(data)
        assert len(result) == 1
        assert result[0].name == "Machine Learning"

    def test_skips_no_name(self) -> None:
        assert _build_concepts([{"name": None}]) == []


class TestBuildLandscapes:
    def test_basic(self) -> None:
        data = [{"name": "AI", "type": "technology"}]
        result = _build_landscapes(data)
        assert len(result) == 1

    def test_skips_no_name(self) -> None:
        assert _build_landscapes([{"name": None}]) == []


class TestBuildDefinitions:
    def test_basic(self) -> None:
        data = [{"term": "widget", "definition": "A device", "paragraph": "0042"}]
        result = _build_definitions(data)
        assert len(result) == 1
        assert result[0].paragraph == "0042"

    def test_skips_incomplete(self) -> None:
        assert _build_definitions([{"term": "x", "definition": None}]) == []
        assert _build_definitions([{"term": None, "definition": "y"}]) == []


class TestBuildChildApplications:
    def test_basic(self) -> None:
        data = [{"application_number": "US16/001", "relation_type": "Continuation"}]
        result = _build_child_applications(data)
        assert len(result) == 1

    def test_skips_no_app_num(self) -> None:
        assert _build_child_applications([{"application_number": None}]) == []


class TestBuildDetailedNpl:
    def test_basic(self) -> None:
        data = [{"title": "Paper Title", "url": "https://example.com"}]
        result = _build_detailed_npl(data)
        assert len(result) == 1

    def test_skips_no_title(self) -> None:
        assert _build_detailed_npl([{"title": None}]) == []


class TestBuildChemicalData:
    def test_with_smiles(self) -> None:
        data = [
            {
                "smiles": "CC",
                "inchi_key": None,
                "id": "1",
                "name": "ethane",
                "domain": None,
                "similarity": None,
            }
        ]
        result = _build_chemical_data(data)
        assert len(result) == 1

    def test_with_inchi(self) -> None:
        data = [
            {
                "smiles": None,
                "inchi_key": "ABC123",
                "id": None,
                "name": None,
                "domain": None,
                "similarity": None,
            }
        ]
        result = _build_chemical_data(data)
        assert len(result) == 1

    def test_skips_no_chemical_data(self) -> None:
        data = [{"smiles": None, "inchi_key": None}]
        assert _build_chemical_data(data) == []


class TestBuildExternalLinks:
    def test_basic(self) -> None:
        data = [{"url": "https://example.com", "id": "test", "name": "Test"}]
        result = _build_external_links(data)
        assert len(result) == 1

    def test_skips_no_url(self) -> None:
        assert _build_external_links([{"url": None}]) == []


# ---------------------------------------------------------------------------
# Query URL builder tests
# ---------------------------------------------------------------------------


class TestBuildQueryUrl:
    def test_keywords_only(self) -> None:
        url = _build_query_url(keywords=["machine learning"])
        assert "q=machine+learning" in url

    def test_cpc_codes(self) -> None:
        url = _build_query_url(keywords=["test"], cpc_codes=["H04L29/06"])
        assert "cpc=" in url

    def test_inventors(self) -> None:
        url = _build_query_url(keywords=["test"], inventors=["John Doe"])
        assert "inventor=" in url

    def test_assignees(self) -> None:
        url = _build_query_url(keywords=["test"], assignees=["Google"])
        assert "assignee=" in url

    def test_countries(self) -> None:
        url = _build_query_url(keywords=["test"], countries=["US", "EP"])
        assert "country=US,EP" in url

    def test_languages(self) -> None:
        url = _build_query_url(keywords=["test"], languages=["EN"])
        assert "language=en" in url

    def test_date_filters(self) -> None:
        url = _build_query_url(
            keywords=["test"], filed_after="2020-01-01", filed_before="2021-12-31"
        )
        assert "after=priority:2020-01-01" in url
        assert "before=priority:2021-12-31" in url

    def test_date_type(self) -> None:
        url = _build_query_url(keywords=["test"], date_type="filing", filed_after="2020-01-01")
        assert "after=filing:2020-01-01" in url

    def test_status(self) -> None:
        url = _build_query_url(keywords=["test"], status="GRANT")
        assert "status=" in url

    def test_patent_type(self) -> None:
        url = _build_query_url(keywords=["test"], patent_type="UTILITY")
        assert "type=" in url

    def test_litigation(self) -> None:
        url = _build_query_url(keywords=["test"], litigation="yes")
        assert "litigation=" in url

    def test_page_size(self) -> None:
        url = _build_query_url(keywords=["test"], page_size=25)
        assert "num=25" in url

    def test_default_page_size_omitted(self) -> None:
        url = _build_query_url(keywords=["test"], page_size=10)
        assert "num=" not in url

    def test_exclude_patents(self) -> None:
        url = _build_query_url(keywords=["test"], include_patents=False)
        assert "patents=false" in url

    def test_include_npl(self) -> None:
        url = _build_query_url(keywords=["test"], include_npl=True)
        assert "scholar" in url

    def test_sort_new(self) -> None:
        url = _build_query_url(keywords=["test"], sort="new")
        assert "sort=new" in url

    def test_sort_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="sort must be"):
            _build_query_url(keywords=["test"], sort="invalid")

    def test_dups(self) -> None:
        url = _build_query_url(keywords=["test"], dups="language")
        assert "dups=" in url

    def test_page(self) -> None:
        url = _build_query_url(keywords=["test"], page=3)
        assert "page=2" in url  # 0-indexed

    def test_page_1_omitted(self) -> None:
        url = _build_query_url(keywords=["test"], page=1)
        assert "page=" not in url

    def test_cluster_results(self) -> None:
        url = _build_query_url(keywords=["test"], cluster_results=True)
        assert "clustered=true" in url

    def test_local(self) -> None:
        url = _build_query_url(keywords=["test"], local="US")
        assert "local=" in url

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one search term"):
            _build_query_url()


# ---------------------------------------------------------------------------
# Search result parsing tests
# ---------------------------------------------------------------------------


class TestParseSearchResults:
    def test_patent_result(self) -> None:
        payload = {
            "results": {
                "cluster": [
                    {
                        "result": [
                            {
                                "id": "patent/US1234",
                                "rank": 1,
                                "patent": {
                                    "title": "Test Patent",
                                    "snippet": "A test",
                                    "publication_number": "US1234567B2",
                                    "filing_date": "2020-01-01",
                                    "pdf": "path/to.pdf",
                                    "thumbnail": "thumb.png",
                                    "family_metadata": {
                                        "aggregated": {"country_status": [{"US": "active"}]}
                                    },
                                },
                            }
                        ]
                    }
                ],
                "total_num_results": 100,
                "total_num_pages": 10,
                "num_page": 0,
            }
        }
        result = _parse_search_results(payload, "q=test")
        assert isinstance(result, GooglePatentsSearchResponse)
        assert result.total_results == 100
        assert len(result.results) == 1
        assert result.results[0].result_type == "patent"
        assert result.has_more is True

    def test_scholar_result(self) -> None:
        payload = {
            "results": {
                "cluster": [
                    {
                        "result": [
                            {
                                "id": "scholar/123",
                                "rank": 1,
                                "scholar": {"title": "Paper", "number": "XYZ"},
                            }
                        ]
                    }
                ],
                "total_num_results": 1,
                "total_num_pages": 1,
                "num_page": 0,
            }
        }
        result = _parse_search_results(payload, "q=test")
        assert result.results[0].result_type == "scholar"

    def test_web_result(self) -> None:
        payload = {
            "results": {
                "cluster": [
                    {
                        "result": [
                            {
                                "id": "web/123",
                                "rank": 1,
                                "webdoc": {"title": "Web Page"},
                            }
                        ]
                    }
                ],
            }
        }
        result = _parse_search_results(payload, "q=test")
        assert result.results[0].result_type == "web"

    def test_unknown_result_type_skipped(self) -> None:
        payload = {
            "results": {
                "cluster": [{"result": [{"id": "unknown/1", "rank": 1}]}],
            }
        }
        result = _parse_search_results(payload, "q=test")
        assert len(result.results) == 0

    def test_empty_results(self) -> None:
        payload = {"results": {}}
        result = _parse_search_results(payload, "q=test")
        assert len(result.results) == 0
        assert result.total_results == 0
