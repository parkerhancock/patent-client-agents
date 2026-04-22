"""Tests for Google Patents builder functions."""

from __future__ import annotations

from typing import Any

from ip_tools.google_patents.client import (
    ChildApplication,
    Concept,
    CountryFiling,
    Definition,
    DetailedNpl,
    FamilyMember,
    Landscape,
    LegalEvent,
    NonPatentLiterature,
    PatentCitation,
    PriorityApplication,
    _build_child_applications,
    _build_citations,
    _build_citations_simple,
    _build_concepts,
    _build_country_filings,
    _build_definitions,
    _build_detailed_npl,
    _build_family_members,
    _build_landscapes,
    _build_legal_events,
    _build_non_patent_literature,
    _build_priority_applications,
)


class TestBuildCitations:
    """Tests for _build_citations function."""

    def test_builds_citations_with_examiner_cited(self) -> None:
        raw = [
            {
                "publication_number": "US7654321B2",
                "publication_date": "2010-02-02",
                "assignee": "Example Corp",
                "title": "Test Patent",
                "examiner_cited": True,
            }
        ]
        result = _build_citations(raw)
        assert len(result) == 1
        assert isinstance(result[0], PatentCitation)
        assert result[0].publication_number == "US7654321B2"
        assert result[0].examiner_cited is True

    def test_builds_citations_without_examiner_cited(self) -> None:
        raw = [{"publication_number": "US1234567A", "examiner_cited": False}]
        result = _build_citations(raw)
        assert result[0].examiner_cited is False

    def test_skips_empty_publication_number(self) -> None:
        raw = [
            {"publication_number": "US1234567A"},
            {"publication_number": None},
            {"publication_number": "US7654321B2"},
        ]
        result = _build_citations(raw)
        assert len(result) == 2

    def test_handles_empty_list(self) -> None:
        result = _build_citations([])
        assert result == []

    def test_handles_non_string_values(self) -> None:
        raw = [
            {
                "publication_number": "US1234567A",
                "publication_date": 12345,  # type: ignore[dict-item]
                "assignee": 999,  # type: ignore[dict-item]
                "title": ["invalid"],  # type: ignore[dict-item]
            }
        ]
        result = _build_citations(raw)
        assert len(result) == 1
        assert result[0].publication_date is None
        assert result[0].assignee is None
        assert result[0].title is None


class TestBuildCitationsSimple:
    """Tests for _build_citations_simple function."""

    def test_builds_citations(self) -> None:
        raw: list[dict[str, str | None]] = [
            {
                "publication_number": "EP1234567A1",
                "publication_date": "2015-03-15",
                "assignee": "Euro Corp",
                "title": "European Patent",
            }
        ]
        result = _build_citations_simple(raw)
        assert len(result) == 1
        assert result[0].publication_number == "EP1234567A1"
        assert result[0].examiner_cited is False

    def test_skips_missing_publication_number(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"title": "No pub num", "publication_number": None},
            {"publication_number": "US1234567A"},
        ]
        result = _build_citations_simple(raw)
        assert len(result) == 1


class TestBuildFamilyMembers:
    """Tests for _build_family_members function."""

    def test_builds_family_members(self) -> None:
        raw: list[dict[str, str | None]] = [
            {
                "application_number": "US15123456",
                "publication_number": "US10123456B2",
                "status": "Active",
                "priority_date": "2018-01-01",
                "filing_date": "2018-06-15",
                "title": "Family Patent",
            }
        ]
        result = _build_family_members(raw)
        assert len(result) == 1
        assert isinstance(result[0], FamilyMember)
        assert result[0].application_number == "US15123456"
        assert result[0].status == "Active"

    def test_skips_missing_application_number(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"title": "No app num", "application_number": None},
            {"application_number": "US15123456"},
        ]
        result = _build_family_members(raw)
        assert len(result) == 1

    def test_handles_empty_list(self) -> None:
        result = _build_family_members([])
        assert result == []


class TestBuildCountryFilings:
    """Tests for _build_country_filings function."""

    def test_builds_country_filings(self) -> None:
        raw: list[dict[str, Any]] = [
            {"country_code": "JP", "count": 3, "representative_publication": "JP2020123456A"}
        ]
        result = _build_country_filings(raw)
        assert len(result) == 1
        assert isinstance(result[0], CountryFiling)
        assert result[0].country_code == "JP"
        assert result[0].count == 3

    def test_default_count_is_one(self) -> None:
        raw: list[dict[str, Any]] = [{"country_code": "US"}]
        result = _build_country_filings(raw)
        assert result[0].count == 1

    def test_skips_missing_country_code(self) -> None:
        raw: list[dict[str, Any]] = [{"count": 5}, {"country_code": "DE"}]
        result = _build_country_filings(raw)
        assert len(result) == 1

    def test_handles_none_representative_publication(self) -> None:
        raw: list[dict[str, Any]] = [{"country_code": "CN", "representative_publication": None}]
        result = _build_country_filings(raw)
        assert result[0].representative_publication is None


class TestBuildPriorityApplications:
    """Tests for _build_priority_applications function."""

    def test_builds_priority_applications(self) -> None:
        raw: list[dict[str, str | None]] = [
            {
                "application_number": "US62123456",
                "publication_number": "US2020123456A1",
                "priority_date": "2019-01-15",
                "filing_date": "2020-01-14",
                "title": "Priority App",
            }
        ]
        result = _build_priority_applications(raw)
        assert len(result) == 1
        assert isinstance(result[0], PriorityApplication)
        assert result[0].application_number == "US62123456"

    def test_skips_missing_application_number(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"title": "No app num", "application_number": None},
            {"application_number": "US62123456"},
        ]
        result = _build_priority_applications(raw)
        assert len(result) == 1


class TestBuildLegalEvents:
    """Tests for _build_legal_events function."""

    def test_builds_legal_events(self) -> None:
        raw: list[dict[str, str | None]] = [
            {
                "date": "2021-05-15",
                "title": "Assignment",
                "assignee": "New Owner",
                "assignor": "Old Owner",
                "status": "Recorded",
            }
        ]
        result = _build_legal_events(raw)
        assert len(result) == 1
        assert isinstance(result[0], LegalEvent)
        assert result[0].title == "Assignment"
        assert result[0].assignee == "New Owner"

    def test_includes_event_with_only_title(self) -> None:
        raw: list[dict[str, str | None]] = [{"title": "Status Change"}]
        result = _build_legal_events(raw)
        assert len(result) == 1

    def test_includes_event_with_only_date(self) -> None:
        raw: list[dict[str, str | None]] = [{"date": "2021-01-01"}]
        result = _build_legal_events(raw)
        assert len(result) == 1

    def test_skips_empty_events(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"assignee": "Test", "title": None, "date": None},
            {"title": "Valid Event"},
        ]
        result = _build_legal_events(raw)
        assert len(result) == 1


class TestBuildNonPatentLiterature:
    """Tests for _build_non_patent_literature function."""

    def test_builds_npl(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"citation": "Smith et al., 2020", "examiner_cited": "true"}
        ]
        result = _build_non_patent_literature(raw)
        assert len(result) == 1
        assert isinstance(result[0], NonPatentLiterature)
        assert result[0].citation == "Smith et al., 2020"
        assert result[0].examiner_cited is True

    def test_examiner_cited_false(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"citation": "Jones et al., 2019", "examiner_cited": "false"}
        ]
        result = _build_non_patent_literature(raw)
        assert result[0].examiner_cited is False

    def test_skips_missing_citation(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"examiner_cited": "true", "citation": None},
            {"citation": "Valid citation"},
        ]
        result = _build_non_patent_literature(raw)
        assert len(result) == 1


class TestBuildConcepts:
    """Tests for _build_concepts function."""

    def test_builds_concepts(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"name": "Machine Learning", "image_url": "https://example.com/ml.png"}
        ]
        result = _build_concepts(raw)
        assert len(result) == 1
        assert isinstance(result[0], Concept)
        assert result[0].name == "Machine Learning"
        assert result[0].image_url == "https://example.com/ml.png"

    def test_skips_missing_name(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"image_url": "https://example.com/img.png", "name": None},
            {"name": "Valid Concept"},
        ]
        result = _build_concepts(raw)
        assert len(result) == 1


class TestBuildLandscapes:
    """Tests for _build_landscapes function."""

    def test_builds_landscapes(self) -> None:
        raw: list[dict[str, str]] = [{"name": "Artificial Intelligence", "type": "technology"}]
        result = _build_landscapes(raw)
        assert len(result) == 1
        assert isinstance(result[0], Landscape)
        assert result[0].name == "Artificial Intelligence"
        assert result[0].type == "technology"

    def test_default_type_empty(self) -> None:
        raw: list[dict[str, str]] = [{"name": "Cryptography"}]
        result = _build_landscapes(raw)
        assert result[0].type == ""

    def test_skips_missing_name(self) -> None:
        raw: list[dict[str, str]] = [{"type": "area"}, {"name": "Valid Landscape"}]
        result = _build_landscapes(raw)
        assert len(result) == 1


class TestBuildDefinitions:
    """Tests for _build_definitions function."""

    def test_builds_definitions(self) -> None:
        raw: list[dict[str, str]] = [
            {"term": "processor", "definition": "A computing device", "paragraph": "[0015]"}
        ]
        result = _build_definitions(raw)
        assert len(result) == 1
        assert isinstance(result[0], Definition)
        assert result[0].term == "processor"
        assert result[0].definition == "A computing device"
        assert result[0].paragraph == "[0015]"

    def test_default_paragraph_empty(self) -> None:
        raw: list[dict[str, str]] = [{"term": "memory", "definition": "Storage device"}]
        result = _build_definitions(raw)
        assert result[0].paragraph == ""

    def test_skips_missing_term_or_definition(self) -> None:
        raw: list[dict[str, str]] = [
            {"term": "no_def"},
            {"definition": "no_term"},
            {"term": "valid", "definition": "valid def"},
        ]
        result = _build_definitions(raw)
        assert len(result) == 1


class TestBuildChildApplications:
    """Tests for _build_child_applications function."""

    def test_builds_child_applications(self) -> None:
        raw: list[dict[str, str | None]] = [
            {
                "application_number": "US16234567",
                "relation_type": "continuation",
                "publication_number": "US11234567B2",
                "priority_date": "2018-01-01",
                "filing_date": "2020-03-15",
                "title": "Child Patent",
            }
        ]
        result = _build_child_applications(raw)
        assert len(result) == 1
        assert isinstance(result[0], ChildApplication)
        assert result[0].application_number == "US16234567"
        assert result[0].relation_type == "continuation"

    def test_skips_missing_application_number(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"relation_type": "divisional", "application_number": None},
            {"application_number": "US16234567"},
        ]
        result = _build_child_applications(raw)
        assert len(result) == 1


class TestBuildDetailedNpl:
    """Tests for _build_detailed_npl function."""

    def test_builds_detailed_npl(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"title": "Research Paper", "url": "https://example.com/paper.pdf"}
        ]
        result = _build_detailed_npl(raw)
        assert len(result) == 1
        assert isinstance(result[0], DetailedNpl)
        assert result[0].title == "Research Paper"
        assert result[0].url == "https://example.com/paper.pdf"

    def test_skips_missing_title(self) -> None:
        raw: list[dict[str, str | None]] = [
            {"url": "https://example.com", "title": None},
            {"title": "Valid Title"},
        ]
        result = _build_detailed_npl(raw)
        assert len(result) == 1
