"""Tests for USPTO Publications transformer functions (pure functions)."""

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
    convert_biblio,
    convert_biblio_page,
    convert_document_payload,
    extract_document_structure,
    take_first,
)


class TestCoerceInt:
    def test_valid_int(self):
        assert _coerce_int(42) == 42

    def test_string_int(self):
        assert _coerce_int("123") == 123

    def test_none(self):
        assert _coerce_int(None) is None

    def test_empty_string(self):
        assert _coerce_int("") is None

    def test_invalid(self):
        assert _coerce_int("abc") is None

    def test_float(self):
        assert _coerce_int(3.9) == 3


class TestNormalizeStr:
    def test_valid(self):
        assert _normalize_str("hello") == "hello"

    def test_none(self):
        assert _normalize_str(None) is None

    def test_empty(self):
        assert _normalize_str("") is None

    def test_number(self):
        assert _normalize_str(123) == "123"


class TestEnsureList:
    def test_none(self):
        assert _ensure_list(None) == []

    def test_list(self):
        assert _ensure_list([1, 2]) == [1, 2]

    def test_scalar(self):
        assert _ensure_list("val") == ["val"]


class TestTakeFirst:
    def test_list(self):
        assert take_first(["a", "b"]) == "a"

    def test_none_values(self):
        assert take_first([None, "", "c"]) == "c"

    def test_none(self):
        assert take_first(None) is None

    def test_empty_list(self):
        assert take_first([]) is None

    def test_scalar(self):
        assert take_first("single") == "single"


class TestParseDate:
    def test_iso_date_string(self):
        assert _parse_date("2024-01-15") == "2024-01-15"

    def test_compact_date_string(self):
        assert _parse_date("20240115") == "2024-01-15"

    def test_iso_datetime(self):
        assert _parse_date("2024-01-15T12:00:00Z") == "2024-01-15"

    def test_none(self):
        assert _parse_date(None) is None

    def test_empty(self):
        assert _parse_date("") is None

    def test_integer_date(self):
        assert _parse_date(20240115) == "2024-01-15"

    def test_invalid(self):
        assert _parse_date("not-a-date") is None

    def test_date_object(self):
        import datetime as dt

        assert _parse_date(dt.date(2024, 1, 15)) == "2024-01-15"


class TestParseMonth:
    def test_valid(self):
        assert _parse_month("202401") == "2024-01-01"

    def test_with_day(self):
        assert _parse_month("20240115") == "2024-01-01"

    def test_none(self):
        assert _parse_month(None) is None

    def test_short_string(self):
        assert _parse_month("2024") is None

    def test_invalid(self):
        assert _parse_month("abcdef") is None


class TestSplit:
    def test_semicolon(self):
        assert _split("A; B; C") == ["A", "B", "C"]

    def test_empty(self):
        assert _split("") == []

    def test_none(self):
        assert _split(None) == []

    def test_list_input(self):
        assert _split(["A", "B"]) == ["A", "B"]

    def test_strips_whitespace(self):
        assert _split("  X ;  Y  ") == ["X", "Y"]


class TestParseCpc:
    def test_valid_cpc(self):
        result = _parse_cpc("G06N 3/08 20230101")
        assert result["cpc_class"] == "G06N"
        assert result["cpc_subclass"] == "3/08"
        assert result["version"] == "2023-01-01"

    def test_empty(self):
        result = _parse_cpc("")
        assert result["cpc_class"] is None

    def test_none(self):
        result = _parse_cpc(None)
        assert result["cpc_class"] is None

    def test_short_code(self):
        result = _parse_cpc("G06")
        assert result["cpc_class"] is None
        assert result["cpc_subclass"] == "G06"

    def test_no_version(self):
        result = _parse_cpc("G06N 3/08")
        assert result["cpc_class"] == "G06N"
        assert result["cpc_subclass"] == "3/08"
        assert result["version"] is None


class TestParseIntl:
    def test_valid(self):
        result = _parse_intl("G06F 21/00 20130101")
        assert result["intl_class"] == "G06F"
        assert result["intl_subclass"] == "21/00"
        assert result["version"] == "2013-01-01"

    def test_empty(self):
        result = _parse_intl("")
        assert result["intl_class"] is None

    def test_none(self):
        result = _parse_intl(None)
        assert result["intl_class"] is None


class TestParseNpl:
    def test_basic(self):
        result = _parse_npl(["Smith et al., Machine Learning, 2020"])
        assert len(result) == 1
        assert result[0]["citation"] == "Smith et al., Machine Learning, 2020"
        assert result[0]["cited_by_examiner"] is False

    def test_cited_by_examiner(self):
        result = _parse_npl(["Smith et al., Machine Learning, 2020 cited by examiner"])
        assert len(result) == 1
        assert "Smith" in result[0]["citation"]
        assert result[0]["cited_by_examiner"] is True

    def test_empty_entries(self):
        result = _parse_npl(["", "  ", "Valid citation"])
        assert len(result) == 1
        assert result[0]["citation"] == "Valid citation"

    def test_empty_list(self):
        assert _parse_npl([]) == []


class TestExtractDocumentStructure:
    def test_basic(self):
        data = {
            "numberOfClaims": 20,
            "pageCount": 15,
            "claimsStart": 10,
            "claimsEnd": 14,
        }
        result = extract_document_structure(data)
        assert result["number_of_claims"] == 20
        assert result["page_count"] == 15
        assert result["claims_start"] == 10
        assert result["claims_end"] == 14

    def test_missing_fields(self):
        result = extract_document_structure({})
        assert result == {}

    def test_none_values_excluded(self):
        data = {"numberOfClaims": None, "pageCount": 10}
        result = extract_document_structure(data)
        assert "number_of_claims" not in result
        assert result["page_count"] == 10

    def test_string_ints(self):
        data = {"numberOfClaims": "20", "pageCount": "15"}
        result = extract_document_structure(data)
        assert result["number_of_claims"] == 20
        assert result["page_count"] == 15


class TestConvertBiblio:
    def test_basic_conversion(self):
        raw = {
            "guid": "abc-123",
            "publicationReferenceDocumentNumber": "US11234567B2",
            "inventionTitle": "Test Invention",
            "datePublished": "20240115",
            "applicationNumber": "17/123456",
            "type": "USPAT",
            "databaseName": "USPAT",
            "mainClassificationCode": "G06N",
            "inventorsShort": "Smith; John",
            "primaryExaminer": "Doe; Jane",
            "imageFileName": "US11234567-20240115",
            "imageLocation": "/images/US11234567",
            "numberOfClaims": 20,
            "pageCount": 10,
        }
        result = convert_biblio(raw)
        assert result["guid"] == "abc-123"
        assert result["publication_number"] == "US11234567B2"
        assert result["patent_title"] == "Test Invention"
        assert result["publication_date"] == "2024-01-15"
        assert result["type"] == "USPAT"
        assert result["primary_examiner"] == "Doe; Jane"

    def test_list_fields(self):
        raw = {
            "applicantName": ["Corp A", "Corp B"],
            "assigneeName": "Single Assignee",
            "cpcAdditionalFlattened": "G06N 3/08; H04L 9/32",
        }
        result = convert_biblio(raw)
        assert result["applicant_names"] == ["Corp A", "Corp B"]
        assert result["assignee_names"] == ["Single Assignee"]
        assert result["cpc_additional"] == ["G06N 3/08", "H04L 9/32"]

    def test_empty_doc(self):
        result = convert_biblio({})
        assert result["guid"] is None
        assert result["publication_number"] is None
        assert result["applicant_names"] == []


class TestConvertBiblioPage:
    def test_basic(self):
        raw = {
            "numFound": 100,
            "perPage": 25,
            "page": 1,
            "patents": [
                {
                    "guid": "abc-123",
                    "publicationReferenceDocumentNumber": "US11234567B2",
                    "inventionTitle": "Test Invention",
                    "datePublished": "20240115",
                    "type": "USPAT",
                }
            ],
        }
        result = convert_biblio_page(raw)
        assert result["num_found"] == 100
        assert result["per_page"] == 25
        assert result["page"] == 1
        assert len(result["docs"]) == 1
        assert result["docs"][0]["publication_number"] == "US11234567B2"

    def test_empty_patents(self):
        raw = {"numFound": 0, "perPage": 25, "page": 0, "patents": []}
        result = convert_biblio_page(raw)
        assert result["num_found"] == 0
        assert result["docs"] == []

    def test_none_values_stripped(self):
        raw = {
            "numFound": 1,
            "perPage": 25,
            "page": 0,
            "patents": [{"guid": "x", "inventionTitle": None}],
        }
        result = convert_biblio_page(raw)
        doc = result["docs"][0]
        assert "patent_title" not in doc  # None values stripped


class TestConvertDocumentPayload:
    def test_basic_document(self):
        raw = {
            "guid": "doc-456",
            "pubRefDocNumber": "US11234567B2",
            "inventionTitle": "Test Invention",
            "datePublished": "20240115",
            "applicationNumber": "17/123456",
            "applicationRefFilingType": "utility",
            "type": "USPAT",
            "databaseName": "USPAT",
            "abstractHtml": "<p>An abstract about machine learning.</p>",
            "claimsHtml": None,
            "descriptionHtml": "<p>A detailed description.</p>",
            "inventorsName": ["John Smith", "Jane Doe"],
            "inventorCity": ["San Francisco", "New York"],
            "inventorCountry": ["US", "US"],
            "inventorState": ["CA", "NY"],
            "assigneeName": ["Tech Corp"],
            "assigneeCity": ["Palo Alto"],
            "assigneeCountry": ["US"],
            "assigneeState": ["CA"],
            "assigneeTypeCode": ["02"],
            "primaryExaminer": "Examiner, Primary",
            "examinerGroup": "2100",
            "imageFileName": "US11234567-20240115",
            "imageLocation": "/images/US11234567",
            "numberOfClaims": 20,
            "pageCount": 10,
        }
        result = convert_document_payload(raw)
        assert result["guid"] == "doc-456"
        assert result["publication_number"] == "US11234567B2"
        assert result["patent_title"] == "Test Invention"
        assert result["publication_date"] == "2024-01-15"
        assert result["type"] == "USPAT"
        assert result["primary_examiner"] == "Examiner, Primary"
        assert result["group_art_unit"] == "2100"

    def test_inventors_extraction(self):
        raw = {
            "inventorsName": ["John Smith", "Jane Doe"],
            "inventorCity": ["San Francisco", "New York"],
            "inventorCountry": ["US", "US"],
            "inventorState": ["CA", "NY"],
        }
        result = convert_document_payload(raw)
        assert len(result["inventors"]) == 2
        assert result["inventors"][0]["name"] == "John Smith"
        assert result["inventors"][0]["city"] == "San Francisco"
        assert result["inventors"][1]["name"] == "Jane Doe"

    def test_assignees_extraction(self):
        raw = {
            "assigneeName": ["Tech Corp"],
            "assigneeCity": ["Palo Alto"],
            "assigneeCountry": ["US"],
            "assigneeState": ["CA"],
            "assigneeTypeCode": ["02"],
        }
        result = convert_document_payload(raw)
        assert len(result["assignees"]) == 1
        assert result["assignees"][0]["name"] == "Tech Corp"
        assert result["assignees"][0]["type_code"] == "02"

    def test_us_references(self):
        raw = {
            "urpn": ["US8830957B2", "US9123456B1"],
            "usRefIssueDate": ["201409", "201512"],
            "usRefPatenteeName": ["Smith; John", "Doe; Jane"],
            "usRefGroup": ["cited by examiner", "cited by applicant"],
        }
        result = convert_document_payload(raw)
        refs = result["us_references"]
        assert len(refs) == 2
        assert refs[0]["publication_number"] == "US8830957B2"
        assert refs[0]["pub_month"] == "2014-09-01"
        assert refs[0]["cited_by_examiner"] is True
        assert refs[1]["cited_by_examiner"] is False

    def test_foreign_references(self):
        raw = {
            "foreignRefCountryCode": ["EP", "JP"],
            "foreignRefPatentNumber": ["1234567", "2024-001234"],
            "foreignRefPubDate": ["202401", "202306"],
            "foreignRefGroup": ["cited by examiner", "cited by applicant"],
        }
        result = convert_document_payload(raw)
        refs = result["foreign_references"]
        assert len(refs) == 2
        assert refs[0]["country_code"] == "EP"
        assert refs[0]["pub_month"] == "2024-01-01"
        assert refs[0]["cited_by_examiner"] is True

    def test_npl_references(self):
        raw = {
            "otherRefPub": "Smith et al., ML paper, 2020<br />Jones, AI study cited by examiner",
        }
        result = convert_document_payload(raw)
        npls = result["npl_references"]
        assert len(npls) == 2
        assert npls[0]["cited_by_examiner"] is False
        assert npls[1]["cited_by_examiner"] is True

    def test_related_apps(self):
        raw = {
            "relatedApplCountryCode": ["US"],
            "relatedApplNumber": ["16/123456"],
            "relatedApplFilingDate": ["20200115"],
            "relatedApplParentStatusCode": ["CON"],
        }
        result = convert_document_payload(raw)
        apps = result["related_apps"]
        assert len(apps) == 1
        assert apps[0]["country_code"] == "US"
        assert apps[0]["filing_date"] == "2020-01-15"
        assert apps[0]["parent_status_code"] == "CON"

    def test_foreign_priority(self):
        raw = {
            "priorityClaimsCountry": ["JP"],
            "priorityClaimsDocNumber": ["2020-123456"],
            "priorityClaimsDate": ["20200615"],
        }
        result = convert_document_payload(raw)
        priority = result["foreign_priority"]
        assert len(priority) == 1
        assert priority[0]["country"] == "JP"
        assert priority[0]["app_filing_date"] == "2020-06-15"

    def test_cpc_codes(self):
        raw = {
            "cpcInventive": ["G06N 3/08 20230101"],
            "cpcAdditional": ["H04L 9/32 20130101", "G06F 21/00 20130101"],
        }
        result = convert_document_payload(raw)
        assert len(result["cpc_inventive"]) == 1
        assert result["cpc_inventive"][0]["cpc_class"] == "G06N"
        assert len(result["cpc_additional"]) == 2

    def test_intl_classes(self):
        raw = {
            "ipcCodeFlattened": "G06N 3/08; H04L 9/32",
            "curIntlPatentClassificationPrimary": ["G06N 3/08 20130101"],
        }
        result = convert_document_payload(raw)
        assert result["intl_class_issued"] == ["G06N 3/08", "H04L 9/32"]
        assert len(result["intl_class_current_primary"]) == 1
        assert result["intl_class_current_primary"][0]["intl_class"] == "G06N"

    def test_empty_payload(self):
        result = convert_document_payload({})
        assert result["guid"] is None
        assert result["inventors"] == []
        assert result["us_references"] == []
        assert result["npl_references"] == []

    def test_document_section(self):
        raw = {
            "abstractHtml": "<p>Abstract text</p>",
            "backgroundTextHtml": "<p>Background</p>",
            "descriptionHtml": "<p>Description</p>",
            "briefHtml": "<p>Brief</p>",
            "claimStatement": "What is claimed is:",
            "claimsHtml": None,
        }
        result = convert_document_payload(raw)
        doc = result["document"]
        assert doc["abstract_html"] == "<p>Abstract text</p>"
        assert doc["background_html"] == "<p>Background</p>"
        assert doc["description_html"] == "<p>Description</p>"
        assert doc["brief_html"] == "<p>Brief</p>"
        assert doc["claim_statement"] == "What is claimed is:"
        assert doc["claims"] == []

    def test_applicants_extraction(self):
        raw = {
            "applicantName": ["Tech Corp"],
            "applicantCity": ["Seattle"],
            "applicantCountry": ["US"],
            "applicantState": ["WA"],
            "applicantZipCode": ["98101"],
            "applicantAuthorityType": ["assignee"],
        }
        result = convert_document_payload(raw)
        assert len(result["applicants"]) == 1
        assert result["applicants"][0]["name"] == "Tech Corp"
        assert result["applicants"][0]["authority_type"] == "assignee"
