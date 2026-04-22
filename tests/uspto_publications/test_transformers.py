"""Tests for USPTO publications transformers module."""

from __future__ import annotations

import datetime as dt

from ip_tools.uspto_publications.transformers import (
    _coerce_int,
    _ensure_list,
    _normalize_str,
    _parse_cpc,
    _parse_date,
    _parse_intl,
    _parse_month,
    _parse_npl,
    _split,
    _zip_records,
    convert_biblio,
    convert_biblio_page,
    convert_document_payload,
    extract_document_structure,
    take_first,
)


class TestCoerceInt:
    """Tests for _coerce_int function."""

    def test_coerces_int(self) -> None:
        assert _coerce_int(42) == 42

    def test_coerces_string(self) -> None:
        assert _coerce_int("123") == 123

    def test_coerces_float(self) -> None:
        assert _coerce_int(3.7) == 3

    def test_returns_none_for_none(self) -> None:
        assert _coerce_int(None) is None

    def test_returns_none_for_empty_string(self) -> None:
        assert _coerce_int("") is None

    def test_returns_none_for_invalid(self) -> None:
        assert _coerce_int("not a number") is None


class TestNormalizeStr:
    """Tests for _normalize_str function."""

    def test_normalizes_string(self) -> None:
        assert _normalize_str("hello") == "hello"

    def test_converts_int_to_string(self) -> None:
        assert _normalize_str(42) == "42"

    def test_returns_none_for_none(self) -> None:
        assert _normalize_str(None) is None

    def test_returns_none_for_empty_string(self) -> None:
        assert _normalize_str("") is None


class TestEnsureList:
    """Tests for _ensure_list function."""

    def test_returns_list_unchanged(self) -> None:
        result = _ensure_list([1, 2, 3])
        assert result == [1, 2, 3]

    def test_wraps_single_value(self) -> None:
        result = _ensure_list(42)
        assert result == [42]

    def test_wraps_string(self) -> None:
        result = _ensure_list("hello")
        assert result == ["hello"]

    def test_returns_empty_for_none(self) -> None:
        result = _ensure_list(None)
        assert result == []


class TestTakeFirst:
    """Tests for take_first function."""

    def test_takes_first_from_list(self) -> None:
        result = take_first(["a", "b", "c"])
        assert result == "a"

    def test_skips_none(self) -> None:
        result = take_first([None, "b", "c"])
        assert result == "b"

    def test_skips_empty_string(self) -> None:
        result = take_first(["", "b", "c"])
        assert result == "b"

    def test_skips_empty_list_value(self) -> None:
        result = take_first([[], "b", "c"])
        assert result == "b"

    def test_returns_single_value(self) -> None:
        result = take_first("single")
        assert result == "single"

    def test_returns_none_for_all_empty(self) -> None:
        result = take_first([None, "", []])
        assert result is None

    def test_returns_none_for_none(self) -> None:
        result = take_first(None)
        assert result is None


class TestParseDate:
    """Tests for _parse_date function."""

    def test_parses_iso_date(self) -> None:
        result = _parse_date("2023-05-15")
        assert result == "2023-05-15"

    def test_parses_compact_date(self) -> None:
        result = _parse_date("20230515")
        assert result == "2023-05-15"

    def test_parses_datetime_with_t(self) -> None:
        result = _parse_date("2023-05-15T10:30:00Z")
        assert result == "2023-05-15"

    def test_parses_datetime_object(self) -> None:
        result = _parse_date(dt.date(2023, 5, 15))
        assert result == "2023-05-15"

    def test_parses_numeric_value(self) -> None:
        result = _parse_date(20230515)
        assert result == "2023-05-15"

    def test_returns_none_for_none(self) -> None:
        result = _parse_date(None)
        assert result is None

    def test_returns_none_for_empty_string(self) -> None:
        result = _parse_date("")
        assert result is None

    def test_returns_none_for_invalid(self) -> None:
        result = _parse_date("invalid date")
        assert result is None


class TestParseMonth:
    """Tests for _parse_month function."""

    def test_parses_month_string(self) -> None:
        result = _parse_month("202305")
        assert result == "2023-05-01"

    def test_parses_with_extra_digits(self) -> None:
        result = _parse_month("20230515")
        assert result == "2023-05-01"

    def test_returns_none_for_none(self) -> None:
        result = _parse_month(None)
        assert result is None

    def test_returns_none_for_empty(self) -> None:
        result = _parse_month("")
        assert result is None

    def test_returns_none_for_short_string(self) -> None:
        result = _parse_month("2023")
        assert result is None

    def test_returns_none_for_invalid_month(self) -> None:
        result = _parse_month("2023AB")
        assert result is None


class TestSplit:
    """Tests for _split function."""

    def test_splits_semicolon(self) -> None:
        result = _split("a; b; c")
        assert result == ["a", "b", "c"]

    def test_splits_custom_delimiter(self) -> None:
        result = _split("a,b,c", ",")
        assert result == ["a", "b", "c"]

    def test_handles_list_input(self) -> None:
        result = _split(["a", "b", "c"])
        assert result == ["a", "b", "c"]

    def test_strips_whitespace(self) -> None:
        result = _split("  a  ;  b  ;  c  ")
        assert result == ["a", "b", "c"]

    def test_filters_empty(self) -> None:
        result = _split("a;;b")
        assert result == ["a", "b"]

    def test_returns_empty_for_none(self) -> None:
        result = _split(None)
        assert result == []

    def test_returns_empty_for_empty_string(self) -> None:
        result = _split("")
        assert result == []


class TestParseCpc:
    """Tests for _parse_cpc function."""

    def test_parses_full_cpc(self) -> None:
        result = _parse_cpc("A01B1/00 20060101")
        assert result["cpc_class"] == "A01B"
        assert result["cpc_subclass"] == "1/00"
        assert result["version"] == "2006-01-01"

    def test_parses_cpc_without_version(self) -> None:
        result = _parse_cpc("H04L67/00")
        assert result["cpc_class"] == "H04L"
        assert result["cpc_subclass"] == "67/00"
        assert result["version"] is None

    def test_handles_short_code(self) -> None:
        result = _parse_cpc("A01")
        assert result["cpc_class"] is None
        assert result["cpc_subclass"] == "A01"
        assert result["version"] is None

    def test_handles_empty(self) -> None:
        result = _parse_cpc("")
        assert result["cpc_class"] is None
        assert result["cpc_subclass"] is None
        assert result["version"] is None

    def test_handles_none(self) -> None:
        result = _parse_cpc(None)
        assert result["cpc_class"] is None


class TestParseIntl:
    """Tests for _parse_intl function."""

    def test_parses_full_intl(self) -> None:
        result = _parse_intl("G06F3/00 20060101")
        assert result["intl_class"] == "G06F"
        assert result["intl_subclass"] == "3/00"
        assert result["version"] == "2006-01-01"

    def test_parses_intl_without_version(self) -> None:
        result = _parse_intl("H04L29/08")
        assert result["intl_class"] == "H04L"
        assert result["intl_subclass"] == "29/08"
        assert result["version"] is None

    def test_handles_empty(self) -> None:
        result = _parse_intl("")
        assert result["intl_class"] is None
        assert result["intl_subclass"] is None

    def test_handles_none(self) -> None:
        result = _parse_intl(None)
        assert result["intl_class"] is None


class TestParseNpl:
    """Tests for _parse_npl function."""

    def test_parses_npl_citation(self) -> None:
        result = _parse_npl(["Smith et al., Journal of Science, 2020"])
        assert len(result) == 1
        assert result[0]["citation"] == "Smith et al., Journal of Science, 2020"
        assert result[0]["cited_by_examiner"] is False

    def test_parses_examiner_cited(self) -> None:
        result = _parse_npl(["Smith et al., 2020 cited by Examiner"])
        assert len(result) == 1
        assert "Smith et al." in result[0]["citation"]
        assert result[0]["cited_by_examiner"] is True

    def test_filters_empty_entries(self) -> None:
        result = _parse_npl(["Valid citation", "", "  ", "Another citation"])
        assert len(result) == 2

    def test_handles_empty_list(self) -> None:
        result = _parse_npl([])
        assert result == []


class TestZipRecords:
    """Tests for _zip_records function."""

    def test_zips_parallel_arrays(self) -> None:
        data = {"names": ["Alice", "Bob"], "ages": [30, 25]}
        mapping: list[tuple[str, str, None]] = [
            ("name", "names", None),
            ("age", "ages", None),
        ]
        result = _zip_records(data, mapping)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[0]["age"] == 30
        assert result[1]["name"] == "Bob"
        assert result[1]["age"] == 25

    def test_handles_uneven_arrays(self) -> None:
        data = {"names": ["Alice", "Bob", "Carol"], "ages": [30]}
        mapping: list[tuple[str, str, None]] = [
            ("name", "names", None),
            ("age", "ages", None),
        ]
        result = _zip_records(data, mapping)
        assert len(result) == 3
        assert result[2]["name"] == "Carol"
        assert result[2]["age"] is None

    def test_applies_transform(self) -> None:
        data = {"values": ["10", "20"]}

        def transform(v, idx, d):  # type: ignore[no-untyped-def]
            return int(v) if v else None

        mapping = [("number", "values", transform)]
        result = _zip_records(data, mapping)
        assert result[0]["number"] == 10
        assert result[1]["number"] == 20

    def test_skips_all_empty_records(self) -> None:
        data = {"names": [None, "Bob"], "ages": [None, 25]}
        mapping: list[tuple[str, str, None]] = [
            ("name", "names", None),
            ("age", "ages", None),
        ]
        result = _zip_records(data, mapping)
        assert len(result) == 1
        assert result[0]["name"] == "Bob"


class TestExtractDocumentStructure:
    """Tests for extract_document_structure function."""

    def test_extracts_structure_fields(self) -> None:
        data = {
            "numberOfClaims": "20",
            "numberOfDrawingSheets": "5",
            "pageCount": "30",
        }
        result = extract_document_structure(data)
        assert result["number_of_claims"] == 20
        assert result["number_of_drawing_sheets"] == 5
        assert result["page_count"] == 30

    def test_skips_none_values(self) -> None:
        data = {"numberOfClaims": "20", "numberOfFigures": None}
        result = extract_document_structure(data)
        assert "number_of_claims" in result
        assert "number_of_figures" not in result

    def test_handles_empty_data(self) -> None:
        result = extract_document_structure({})
        assert result == {}


class TestConvertBiblio:
    """Tests for convert_biblio function."""

    def test_converts_basic_fields(self) -> None:
        doc = {
            "guid": "abc123",
            "applicationNumber": "17/123456",
            "publicationReferenceDocumentNumber": "US20230123456A1",
            "inventionTitle": "Test Patent",
        }
        result = convert_biblio(doc)
        assert result["guid"] == "abc123"
        assert result["appl_id"] == "17/123456"
        assert result["publication_number"] == "US20230123456A1"
        assert result["patent_title"] == "Test Patent"

    def test_parses_dates(self) -> None:
        doc = {
            "applicationFilingDate": ["20230101"],
            "datePublished": "2023-06-15",
        }
        result = convert_biblio(doc)
        assert result["app_filing_date"] == "2023-01-01"
        assert result["publication_date"] == "2023-06-15"

    def test_handles_list_fields(self) -> None:
        doc = {
            "applicantName": ["Company A", "Company B"],
            "assigneeName": ["Assignee Corp"],
        }
        result = convert_biblio(doc)
        assert result["applicant_names"] == ["Company A", "Company B"]
        assert result["assignee_names"] == ["Assignee Corp"]


class TestConvertBiblioPage:
    """Tests for convert_biblio_page function."""

    def test_converts_page(self) -> None:
        data = {
            "numFound": "100",
            "perPage": "25",
            "page": "1",
            "patents": [
                {"guid": "abc", "inventionTitle": "Patent 1"},
                {"guid": "def", "inventionTitle": "Patent 2"},
            ],
        }
        result = convert_biblio_page(data)
        assert result["num_found"] == 100
        assert result["per_page"] == 25
        assert result["page"] == 1
        assert len(result["docs"]) == 2

    def test_handles_empty_patents(self) -> None:
        data = {"numFound": "0", "perPage": "25", "page": "1", "patents": []}
        result = convert_biblio_page(data)
        assert result["num_found"] == 0
        assert result["docs"] == []


class TestConvertDocumentPayload:
    """Tests for convert_document_payload function."""

    def test_converts_basic_document(self) -> None:
        data = {
            "guid": "doc123",
            "pubRefDocNumber": "US10123456B2",
            "inventionTitle": "Test Patent",
            "datePublished": "2020-01-01",
            "abstractHtml": "<p>Abstract text</p>",
        }
        result = convert_document_payload(data)
        assert result["guid"] == "doc123"
        assert result["publication_number"] == "US10123456B2"
        assert result["patent_title"] == "Test Patent"
        assert result["publication_date"] == "2020-01-01"
        assert result["document"]["abstract_html"] == "<p>Abstract text</p>"

    def test_parses_claims(self) -> None:
        data = {"claimsHtml": "1. A method.\n2. The method of claim 1."}
        result = convert_document_payload(data)
        assert len(result["document"]["claims"]) == 2

    def test_extracts_inventors(self) -> None:
        data = {
            "inventorsName": ["John Doe", "Jane Smith"],
            "inventorCity": ["Boston", "New York"],
            "inventorCountry": ["US", "US"],
        }
        result = convert_document_payload(data)
        assert len(result["inventors"]) == 2
        assert result["inventors"][0]["name"] == "John Doe"
        assert result["inventors"][0]["city"] == "Boston"

    def test_extracts_us_references(self) -> None:
        data = {
            "urpn": ["US7654321B2", "US8765432B2"],
            "usRefPatenteeName": ["Inventor A", "Inventor B"],
            "usRefGroup": ["examiner", "applicant"],
        }
        result = convert_document_payload(data)
        assert len(result["us_references"]) == 2
        assert result["us_references"][0]["cited_by_examiner"] is True
        assert result["us_references"][1]["cited_by_examiner"] is False

    def test_parses_cpc_codes(self) -> None:
        data = {"cpcInventive": ["A01B1/00", "G06F3/00"]}
        result = convert_document_payload(data)
        assert len(result["cpc_inventive"]) == 2
        assert result["cpc_inventive"][0]["cpc_class"] == "A01B"

    def test_handles_empty_document(self) -> None:
        result = convert_document_payload({})
        assert result["guid"] is None
        assert result["document"]["claims"] == []
