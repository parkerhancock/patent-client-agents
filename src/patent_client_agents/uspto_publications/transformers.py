from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

from .utils import ClaimsParser


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def take_first(values: Iterable[Any] | Any | None) -> Any:
    for value in _ensure_list(values):
        if value not in (None, "", []):
            return value
    return None


def extract_document_structure(data: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "number_of_claims": "numberOfClaims",
        "number_of_drawing_sheets": "numberOfDrawingSheets",
        "number_of_figures": "numberOfFigures",
        "page_count": "pageCount",
        "front_page_end": "frontPageEnd",
        "front_page_start": "frontPageStart",
        "bib_start": "bibStart",
        "bib_end": "bibEnd",
        "abstract_start": "abstractStart",
        "abstract_end": "abstractEnd",
        "drawings_start": "drawingsStart",
        "drawings_end": "drawingsEnd",
        "description_start": "descriptionStart",
        "description_end": "descriptionEnd",
        "specification_start": "specificationStart",
        "specification_end": "specificationEnd",
        "claims_end": "claimsEnd",
        "claims_start": "claimsStart",
        "amend_start": "amendStart",
        "amend_end": "amendEnd",
        "cert_correction_end": "certCorrectionEnd",
        "cert_correction_start": "certCorrectionStart",
        "cert_reexamination_end": "certReexaminationEnd",
        "cert_reexamination_start": "certReexaminationStart",
        "ptab_start": "ptabStart",
        "ptab_end": "ptabEnd",
        "search_report_start": "searchReportStart",
        "search_report_end": "searchReportEnd",
        "supplemental_start": "supplementalStart",
        "supplemental_end": "supplementalEnd",
    }
    payload = {}
    for target, source in mapping.items():
        coerced = _coerce_int(data.get(source))
        if coerced is not None:
            payload[target] = coerced
    return payload


def _parse_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, int | float):
        value = str(int(value))
    string = str(value).strip()
    if not string:
        return None
    if "T" in string:
        iso_string = string.replace("Z", "+00:00")
        try:
            return dt.datetime.fromisoformat(iso_string).date().isoformat()
        except ValueError:
            pass
    fmt = "%Y-%m-%d" if "-" in string else "%Y%m%d"
    try:
        return dt.datetime.strptime(string, fmt).date().isoformat()
    except ValueError:
        return None


def _parse_month(value: Any) -> str | None:
    if value in (None, ""):
        return None
    string = str(value)
    if len(string) < 6:
        return None
    try:
        year = int(string[:4])
        month = int(string[4:6])
    except ValueError:
        return None
    return dt.date(year, month, 1).isoformat()


def _split(value: Any, delimiter: str = ";") -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(delimiter)
    return [item.strip() for item in items if item and item.strip()]


def _zip_records(
    data: dict[str, Any],
    mapping: list[tuple[str, str, Any | None]],
) -> list[dict[str, Any]]:
    lengths = [len(_ensure_list(data.get(source))) for _, source, _ in mapping]
    max_len = max(lengths, default=0)
    results: list[dict[str, Any]] = []
    for index in range(max_len):
        record: dict[str, Any] = {}
        has_value = False
        for field_name, source, transform in mapping:
            values = _ensure_list(data.get(source))
            value = values[index] if index < len(values) else None
            if callable(transform):
                value = transform(value, index, data)
            if value not in (None, "", [], {}):
                has_value = True
            record[field_name] = value
        if has_value:
            results.append(record)
    return results


def _parse_cpc(code: Any) -> dict[str, Any]:
    if not code:
        return {"cpc_class": None, "cpc_subclass": None, "version": None}
    snippet = str(code).strip()
    if len(snippet) < 4:
        return {"cpc_class": None, "cpc_subclass": snippet or None, "version": None}
    cpc_class = snippet[:4]
    remainder = snippet[4:].strip()
    pieces = remainder.split(" ")
    cpc_subclass = pieces[0] if pieces else None
    version = None
    if len(pieces) > 1:
        version = _parse_date(pieces[-1])
    return {"cpc_class": cpc_class, "cpc_subclass": cpc_subclass, "version": version}


def _parse_intl(code: Any) -> dict[str, Any]:
    if not code:
        return {"intl_class": None, "intl_subclass": None, "version": None}
    snippet = str(code).strip()
    if len(snippet) < 4:
        return {"intl_class": None, "intl_subclass": snippet or None, "version": None}
    intl_class = snippet[:4]
    remainder = snippet[4:].strip()
    pieces = remainder.split(" ")
    intl_subclass = pieces[0] if pieces else None
    version = None
    if len(pieces) > 1:
        version = _parse_date(pieces[-1])
    return {"intl_class": intl_class, "intl_subclass": intl_subclass, "version": version}


def _parse_npl(values: Iterable[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for value in values:
        snippet = (value or "").strip()
        if not snippet:
            continue
        cited = "cited by" in snippet.lower()
        if cited:
            parts = snippet.rsplit("cited by", 1)
            citation = parts[0].strip()
        else:
            citation = snippet
        results.append({"citation": citation, "cited_by_examiner": cited})
    return results


def convert_biblio(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "guid": doc.get("guid"),
        "appl_id": doc.get("applicationNumber"),
        "app_filing_date": _parse_date(take_first(doc.get("applicationFilingDate"))),
        "related_appl_filing_date": [
            _parse_date(item) for item in _ensure_list(doc.get("relatedApplFilingDate")) if item
        ],
        "publication_number": doc.get("publicationReferenceDocumentNumber"),
        "kind_code": take_first(doc.get("kindCode")),
        "publication_date": _parse_date(doc.get("datePublished")),
        "patent_title": doc.get("inventionTitle"),
        "inventors_short": doc.get("inventorsShort"),
        "applicant_names": _ensure_list(doc.get("applicantName")),
        "assignee_names": _ensure_list(doc.get("assigneeName")),
        "government_interest": _ensure_list(doc.get("governmentInterest")),
        "primary_examiner": doc.get("primaryExaminer"),
        "assistant_examiner": take_first(doc.get("assistantExaminer")),
        "main_classification_code": doc.get("mainClassificationCode"),
        "cpc_additional": _split(doc.get("cpcAdditionalFlattened")),
        "cpc_inventive": _split(doc.get("cpcInventiveFlattened")),
        "ipc_code": _split(doc.get("ipcCodeFlattened")),
        "uspc_full_classification": _split(doc.get("uspcFullClassificationFlattened")),
        "image_file_name": doc.get("imageFileName"),
        "image_location": doc.get("imageLocation"),
        "document_structure": extract_document_structure(doc),
        "type": doc.get("type"),
        "database_name": doc.get("databaseName"),
        "composite_id": doc.get("compositeId"),
        "document_id": doc.get("documentId"),
        "document_size": _coerce_int(doc.get("documentSize")),
        "family_identifier_cur": _coerce_int(doc.get("familyIdentifierCur")),
        "language_indicator": doc.get("languageIndicator"),
        "score": doc.get("score"),
    }


def convert_biblio_page(data: dict[str, Any]) -> dict[str, Any]:
    docs = []
    for doc in data.get("patents", []):
        converted = {k: v for k, v in convert_biblio(doc).items() if v not in (None, [], {}, "")}
        docs.append(converted)
    return {
        "num_found": _coerce_int(data.get("numFound")) or 0,
        "per_page": _coerce_int(data.get("perPage")) or 0,
        "page": _coerce_int(data.get("page")) or 0,
        "docs": docs,
    }


def convert_document_payload(data: dict[str, Any]) -> dict[str, Any]:
    parser = ClaimsParser()
    document = {
        "abstract_html": data.get("abstractHtml"),
        "government_interest": data.get("governmentInterest"),
        "background_html": data.get("backgroundTextHtml"),
        "brief_html": data.get("briefHtml"),
        "description_html": data.get("descriptionHtml"),
        "claim_statement": data.get("claimStatement"),
        "claims_html": data.get("claimsHtml"),
        "claims": parser.parse(data.get("claimsHtml")),
    }

    us_references = _zip_records(
        data,
        [
            ("publication_number", "urpn", None),
            ("pub_month", "usRefIssueDate", lambda v, *_: _parse_month(v)),
            ("patentee_name", "usRefPatenteeName", None),
            (
                "cited_by_examiner",
                "usRefGroup",
                lambda value, *_: "examiner" in (value or "").lower(),
            ),
        ],
    )

    foreign_references = _zip_records(
        data,
        [
            ("citation_classification", "foreignRefCitationClassification", None),
            ("citation_cpc", "foreignRefCitationCpc", None),
            ("country_code", "foreignRefCountryCode", None),
            ("patent_number", "foreignRefPatentNumber", None),
            ("pub_month", "foreignRefPubDate", lambda v, *_: _parse_month(v)),
            (
                "cited_by_examiner",
                "foreignRefGroup",
                lambda value, *_: "examiner" in (value or "").lower(),
            ),
        ],
    )

    related_apps = _zip_records(
        data,
        [
            ("child_patent_country", "relatedApplChildPatentCountry", None),
            ("child_patent_number", "relatedApplChildPatentNumber", None),
            ("country_code", "relatedApplCountryCode", None),
            ("filing_date", "relatedApplFilingDate", lambda v, *_: _parse_date(v)),
            ("number", "relatedApplNumber", None),
            ("parent_status_code", "relatedApplParentStatusCode", None),
            (
                "patent_issue_date",
                "relatedApplPatentIssueDate",
                lambda v, *_: _parse_date(v),
            ),
            ("patent_number", "relatedApplPatentNumber", None),
        ],
    )

    foreign_priority = _zip_records(
        data,
        [
            ("country", "priorityClaimsCountry", None),
            ("app_filing_date", "priorityClaimsDate", lambda v, *_: _parse_date(v)),
            ("app_number", "priorityClaimsDocNumber", None),
        ],
    )

    inventors = _zip_records(
        data,
        [
            ("name", "inventorsName", None),
            ("city", "inventorCity", None),
            ("country", "inventorCountry", None),
            ("postal_code", "inventorPostalCode", None),
            ("state", "inventorState", None),
        ],
    )

    applicants = _zip_records(
        data,
        [
            ("city", "applicantCity", None),
            ("country", "applicantCountry", None),
            ("name", "applicantName", None),
            ("state", "applicantState", None),
            ("zip_code", "applicantZipCode", None),
            ("authority_type", "applicantAuthorityType", None),
        ],
    )

    assignees = _zip_records(
        data,
        [
            ("city", "assigneeCity", None),
            ("country", "assigneeCountry", None),
            ("name", "assigneeName", None),
            ("postal_code", "assigneePostalCode", None),
            ("state", "assigneeState", None),
            ("type_code", "assigneeTypeCode", None),
        ],
    )

    npl_source = take_first(data.get("otherRefPub")) or ""
    npl_entries = [entry.strip() for entry in npl_source.split("<br />") if entry.strip()]

    payload = {
        "guid": data.get("guid"),
        "publication_number": data.get("pubRefDocNumber"),
        "publication_date": _parse_date(data.get("datePublished")),
        "appl_id": data.get("applicationNumber"),
        "patent_title": data.get("inventionTitle"),
        "app_filing_date": _parse_date(take_first(data.get("applicationFilingDate"))),
        "application_type": data.get("applicationRefFilingType"),
        "family_identifier_cur": _coerce_int(data.get("familyIdentifierCur")),
        "related_apps": related_apps,
        "foreign_priority": foreign_priority,
        "type": data.get("type"),
        "inventors": inventors,
        "inventors_short": data.get("inventorsShort"),
        "applicants": applicants,
        "assignees": assignees,
        "group_art_unit": _normalize_str(data.get("examinerGroup")),
        "primary_examiner": _normalize_str(data.get("primaryExaminer")),
        "assistant_examiner": [
            _normalize_str(value)
            for value in _ensure_list(data.get("assistantExaminer"))
            if value not in (None, "")
        ],
        "legal_firm_name": _ensure_list(data.get("legalFirmName")),
        "attorney_name": _ensure_list(data.get("attorneyName")),
        "document": document,
        "document_structure": extract_document_structure(data),
        "image_file_name": data.get("imageFileName"),
        "image_location": data.get("imageLocation"),
        "composite_id": data.get("compositeId"),
        "database_name": data.get("databaseName"),
        "derwent_week_int": _coerce_int(data.get("derwentWeekInt")),
        "us_references": us_references,
        "foreign_references": foreign_references,
        "npl_references": _parse_npl(npl_entries),
        "cpc_inventive": [_parse_cpc(code) for code in _ensure_list(data.get("cpcInventive"))],
        "cpc_additional": [_parse_cpc(code) for code in _ensure_list(data.get("cpcAdditional"))],
        "intl_class_issued": _split(data.get("ipcCodeFlattened")),
        "intl_class_current_primary": [
            _parse_intl(code)
            for code in _ensure_list(data.get("curIntlPatentClassificationPrimary"))
        ],
        "intl_class_currrent_secondary": [
            _parse_intl(code)
            for code in _ensure_list(data.get("curIntlPatentClassificationSecondary"))
        ],
        "us_class_current": _split(data.get("uspcFullClassificationFlattened")),
        "us_class_issued": _ensure_list(data.get("issuedUsClassificationFull")),
        "field_of_search_us": _ensure_list(data.get("fieldOfSearchClassSubclassHighlights")),
        "field_of_search_cpc": _ensure_list(data.get("fieldOfSearchCpcClassification")),
    }

    return payload
