"""Unit tests for the JPO document-bundle parser.

These exercise :func:`patent_client_agents.jpo.documents.parse_document_bundle`
against hand-crafted Shift-JIS ZIP fixtures (see :mod:`fixtures.document_bundles`).
The fixtures are byte-perfect Shift-JIS so they catch encoding bugs that
UTF-8 fixtures would silently mask.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from patent_client_agents.jpo import (
    DocumentBundle,
    DocumentEntry,
    parse_document_bundle,
)
from tests.jpo.fixtures.document_bundles import (
    make_application_bundle_zip,
    make_invalid_xml_bundle_zip,
    make_mailed_bundle_zip,
    make_refusal_bundle_zip,
)


class TestParseApplicationBundle:
    """Applicant-filed opinion / amendment bundles."""

    def test_returns_bundle(self) -> None:
        bundle = parse_document_bundle(
            make_application_bundle_zip(),
            "application",
            "patent",
            application_number="2020999999",
        )
        assert isinstance(bundle, DocumentBundle)
        assert bundle.ip_type == "patent"
        assert bundle.doc_kind == "application"
        assert bundle.application_number == "2020999999"

    def test_parses_one_xml_entry(self) -> None:
        bundle = parse_document_bundle(
            make_application_bundle_zip(),
            "application",
            "patent",
        )
        assert len(bundle.entries) == 1

    def test_entry_carries_jpo_fields(self) -> None:
        bundle = parse_document_bundle(
            make_application_bundle_zip(),
            "application",
            "patent",
        )
        entry = bundle.entries[0]
        assert isinstance(entry, DocumentEntry)
        assert entry.document_code == "A153"
        assert entry.document_variant == "response-a53"
        assert entry.application_number == "2020999999"
        assert entry.dispatch_number == "012345"
        assert entry.ip_type == "patent"
        assert entry.doc_kind == "application"

    def test_entry_decodes_shift_jis_body(self) -> None:
        """Body text must decode through Shift-JIS, not UTF-8."""
        bundle = parse_document_bundle(
            make_application_bundle_zip(),
            "application",
            "patent",
        )
        entry = bundle.entries[0]
        # Whatever Japanese the fixture body decodes to, it must be unicode
        # (not raw \x?? bytes) and contain Japanese punctuation.
        assert entry.body_text  # non-empty
        assert "\x95" not in entry.body_text  # not raw SJIS bytes
        # SJIS period 。is U+3002
        assert "。" in entry.body_text

    def test_collects_applicants_and_agents(self) -> None:
        bundle = parse_document_bundle(
            make_application_bundle_zip(),
            "application",
            "patent",
        )
        # Both <jp:applicant>/<jp:name> and <jp:agent>/<jp:name>
        assert len(bundle.entries[0].applicant_names) == 2

    def test_lists_binary_attachments_separately(self) -> None:
        bundle = parse_document_bundle(
            make_application_bundle_zip(),
            "application",
            "patent",
        )
        # The fake JPEG should be referenced by name, not parsed.
        assert bundle.binary_attachments == ["A53_99900012345/exhibit.jpg"]


class TestParseMailedBundle:
    """JPO-mailed notice bundles."""

    def test_parses_refusal_notice(self) -> None:
        bundle = parse_document_bundle(
            make_mailed_bundle_zip(),
            "mailed",
            "patent",
            application_number="2020999999",
        )
        assert len(bundle.entries) == 1
        entry = bundle.entries[0]
        assert entry.document_name  # 拒絶理由通知書
        assert entry.document_variant == "notice-of-rejection-a131-rn"
        assert entry.application_number == "2020999999"
        assert entry.legal_date == "20240101"

    def test_extracts_drafter_and_articles(self) -> None:
        bundle = parse_document_bundle(
            make_mailed_bundle_zip(),
            "mailed",
            "patent",
        )
        entry = bundle.entries[0]
        assert entry.drafter_name  # examiner name
        # Two article references: 第29条第1項第3号 and 第29条第2項
        assert len(entry.articles) == 2

    def test_design_ip_type_is_propagated(self) -> None:
        bundle = parse_document_bundle(
            make_mailed_bundle_zip(),
            "mailed",
            "design",
        )
        assert bundle.ip_type == "design"
        assert bundle.entries[0].ip_type == "design"


class TestParseRefusalBundle:
    """Refusal-only bundles. Schema is identical to mailed."""

    def test_parses_refusal_only(self) -> None:
        bundle = parse_document_bundle(
            make_refusal_bundle_zip(),
            "refusal",
            "patent",
        )
        assert bundle.doc_kind == "refusal"
        assert len(bundle.entries) == 1
        assert bundle.entries[0].doc_kind == "refusal"


class TestParseEmptyOrMalformed:
    """Empty bundles and parse errors must not raise."""

    def test_none_zip_bytes_returns_empty_bundle(self) -> None:
        bundle = parse_document_bundle(
            None,
            "mailed",
            "patent",
            application_number="2020999999",
        )
        assert bundle.is_empty
        assert bundle.entries == []
        assert bundle.application_number == "2020999999"

    def test_empty_bytes_returns_empty_bundle(self) -> None:
        bundle = parse_document_bundle(
            b"",
            "mailed",
            "patent",
        )
        assert bundle.is_empty

    def test_malformed_xml_records_parse_error(self) -> None:
        bundle = parse_document_bundle(
            make_invalid_xml_bundle_zip(),
            "mailed",
            "patent",
        )
        # Entry is still emitted, but with parse_error set and no fields.
        assert len(bundle.entries) == 1
        assert bundle.entries[0].parse_error
        assert bundle.entries[0].document_name == ""

    def test_empty_zip_returns_empty_bundle(self) -> None:
        empty_zip = io.BytesIO()
        with zipfile.ZipFile(empty_zip, "w"):
            pass
        bundle = parse_document_bundle(
            empty_zip.getvalue(),
            "mailed",
            "patent",
        )
        assert bundle.is_empty


class TestEncodingHandling:
    """Encoding regressions are easy to introduce silently."""

    def test_cp932_fallback_handles_extension_chars(self) -> None:
        """A byte sequence that's strict-Shift-JIS-invalid but cp932-OK
        should still parse. Build a doc whose only difference is that
        we throw a windows-private-area byte into the body."""
        # 0x87\x40 is a Microsoft-specific NEC special char (cp932 only).
        body = b"\x87\x40"  # ㈱ in cp932
        xml = (
            b'<?xml version="1.0" encoding="Shift_JIS"?>\n'
            b'<jp:notice-pat-exam-rn xmlns:jp="http://www.jpo.go.jp">\n'
            b"<jp:notice-of-rejection-a131-rn>\n"
            b"<jp:document-name>" + body + b"</jp:document-name>\n"
            b"</jp:notice-of-rejection-a131-rn>\n"
            b"</jp:notice-pat-exam-rn>\n"
        )
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("00099999-jpntce.xml", xml)
        bundle = parse_document_bundle(zip_buf.getvalue(), "mailed", "patent")
        # Either strict SJIS rejected and we fell back to cp932, or strict
        # SJIS accepted (some implementations do). Either way: no crash,
        # entry parses.
        assert len(bundle.entries) == 1
        assert bundle.entries[0].document_name


def test_invalid_zip_bytes_raise() -> None:
    """A non-empty payload that isn't a valid ZIP should raise BadZipFile.

    Empty / None payloads are permitted (return empty bundle), but
    garbage bytes are an indication of a network corruption / API change
    and should not be silently swallowed.
    """
    with pytest.raises(zipfile.BadZipFile):
        parse_document_bundle(b"not a zip", "mailed", "patent")
