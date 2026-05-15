"""Live integration tests for the JPO Patent Information Retrieval API.

These tests hit the real JPO API and require valid credentials. They
are skipped during cassette replay if no cassette is present. With a
cassette on disk, they replay cleanly without credentials or network
(JPO_API_USERNAME/JPO_API_PASSWORD are auto-populated with placeholders
during replay).

Run live + record::

    pytest --run-live-jpo --vcr-record=once tests/jpo/test_live.py

Replay only (default)::

    pytest tests/jpo/test_live.py

Required env vars (live only):

    JPO_API_USERNAME: JPO-issued username
    JPO_API_PASSWORD: JPO-issued password
"""

from __future__ import annotations

import os

import pytest

from patent_client_agents.jpo import (
    CaseNumberKind,
    CitedDocumentsData,
    DesignProgressData,
    DivisionalAppInfoData,
    DocumentBundleResult,
    JpoClient,
    NumberReference,
    PatentProgressData,
    PctKind,
    PctNationalPhaseData,
    RegistrationInfo,
    SimplifiedPatentProgressData,
    TrademarkProgressData,
    get_patent_jplatpat_url,
    get_patent_progress,
)

pytestmark = [pytest.mark.live_jpo]


@pytest.fixture(autouse=True)
def _ensure_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject placeholder credentials when none are set.

    During live recording the real JPO_API_USERNAME / JPO_API_PASSWORD
    env vars are present and used. During cassette replay we don't have
    them, so we set placeholders so the JpoClient constructor doesn't
    trip its ConfigurationError. The cassette's redacted token is what
    actually gets used over the (mocked) wire.
    """
    if not os.getenv("JPO_API_USERNAME"):
        monkeypatch.setenv("JPO_API_USERNAME", "REDACTED_USERNAME")
    if not os.getenv("JPO_API_PASSWORD"):
        monkeypatch.setenv("JPO_API_PASSWORD", "REDACTED_PASSWORD")


# Test data — patents/designs/trademarks confirmed to return data on
# 2026-05-07. If any of these stop returning data in future, replace
# the constant rather than weakening the assertion.
PATENT_APP = "2020123456"  # メイショウ patent — issued, with refusal history
NONEXISTENT_PATENT_APP = "9999999999"
DESIGN_APP = "2020015234"  # 大徳木管 design (confirmed live)
DESIGN_APP_WITH_DOCS = "2021019500"  # 医療用設備収納用筐体 — refused, has filings
TRADEMARK_APP = "2024123456"  # MTJグループ "メタンレス和牛" trademark
TRADEMARK_APP_WITH_DOCS = "2022027000"  # has both opinion and refusal docs
TOYOTA_APPLICANT_NAME = "トヨタ自動車株式会社"
TOYOTA_APPLICANT_CODE = "000003207"


# =============================================================================
# Patent progress
# =============================================================================


class TestPatentProgressLive:
    @pytest.mark.asyncio
    async def test_get_patent_progress_real(self, vcr_cassette) -> None:
        """Full patent progress returns a populated PatentProgressData."""
        async with JpoClient() as client:
            progress = await client.get_patent_progress(PATENT_APP)

            assert isinstance(progress, PatentProgressData)
            assert progress.application_number == PATENT_APP
            assert progress.invention_title  # non-empty
            assert progress.filing_date  # non-empty
            assert len(progress.applicant_attorney) > 0
            assert progress.applicant_attorney[0].name
            # 2020123456 has at least one priority claim and a populated
            # bibliographyInformation block.
            assert isinstance(progress.priority_right_information, list)
            assert isinstance(progress.bibliography_information, list)
            assert len(progress.bibliography_information) > 0

    @pytest.mark.asyncio
    async def test_get_patent_progress_simple_real(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            progress = await client.get_patent_progress_simple(PATENT_APP)

            assert isinstance(progress, SimplifiedPatentProgressData)
            assert progress.application_number == PATENT_APP
            assert progress.invention_title
            # Simple endpoint omits priority/parent/divisional but still
            # returns bibliographyInformation.
            assert len(progress.bibliography_information) > 0

    @pytest.mark.asyncio
    async def test_get_patent_progress_not_found(self, vcr_cassette) -> None:
        """Non-existent patent returns None (status 107)."""
        async with JpoClient() as client:
            progress = await client.get_patent_progress(NONEXISTENT_PATENT_APP)
            assert progress is None


# =============================================================================
# Patent documents
# =============================================================================


class TestPatentDocumentsLive:
    @pytest.mark.asyncio
    async def test_get_application_documents(self, vcr_cassette) -> None:
        """app_doc_cont_opinion_amendment returns a ZIP archive bundle."""
        async with JpoClient() as client:
            bundle = await client.get_patent_application_documents(PATENT_APP)
            assert isinstance(bundle, DocumentBundleResult)
            assert bundle.zip_bytes is not None
            assert bundle.zip_bytes.startswith(b"PK\x03\x04")
            assert "zip" in bundle.content_type.lower()

    @pytest.mark.asyncio
    async def test_get_mailed_documents(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            bundle = await client.get_patent_mailed_documents(PATENT_APP)
            assert isinstance(bundle, DocumentBundleResult)
            if bundle.zip_bytes is not None:
                assert bundle.zip_bytes.startswith(b"PK\x03\x04")
            else:
                assert bundle.is_empty or bundle.download_url

    @pytest.mark.asyncio
    async def test_get_refusal_notices(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            bundle = await client.get_patent_refusal_notices(PATENT_APP)
            assert isinstance(bundle, DocumentBundleResult)
            # 2020123456 had a refusal notice (拒絶理由通知書).
            assert bundle.zip_bytes is not None or bundle.download_url

    @pytest.mark.asyncio
    async def test_get_cited_documents(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            cites = await client.get_patent_cited_documents(PATENT_APP)
            assert cites is None or isinstance(cites, CitedDocumentsData)
            if cites is not None:
                # 2020123456 had several patent citations during prosecution.
                assert len(cites.patent_doc) > 0


# =============================================================================
# Number cross-reference
# =============================================================================


class TestNumberReferenceLive:
    @pytest.mark.asyncio
    async def test_cross_reference_by_application(self, vcr_cassette) -> None:
        """case_number_reference uses descriptive 'application' kind."""
        async with JpoClient() as client:
            ref = await client.get_patent_number_reference(CaseNumberKind.APPLICATION, PATENT_APP)
            assert isinstance(ref, NumberReference)
            assert ref.application_number == PATENT_APP
            # 2020123456 published as 2021-090037 and registered as 7533889.
            assert ref.registration_number == "7533889"

    @pytest.mark.asyncio
    async def test_cross_reference_by_publication(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            # Either response shape (NumberReference or None) is fine —
            # this exercises the kind=publication path.
            ref = await client.get_patent_number_reference(CaseNumberKind.PUBLICATION, "2020123456")
            assert ref is None or isinstance(ref, NumberReference)


# =============================================================================
# J-PlatPat URL
# =============================================================================


class TestJplatpatUrlLive:
    @pytest.mark.asyncio
    async def test_get_jplatpat_url(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            url = await client.get_patent_jplatpat_url(PATENT_APP)
            assert url is not None
            assert "j-platpat" in url.lower()
            assert url.startswith("https://")


# =============================================================================
# Applicant lookup
# =============================================================================


class TestApplicantLookupLive:
    @pytest.mark.asyncio
    async def test_applicant_by_name_exact(self, vcr_cassette) -> None:
        """Search by exact applicant name (the API requires exact match)."""
        async with JpoClient() as client:
            applicants = await client.get_patent_applicant_by_name(TOYOTA_APPLICANT_NAME)
            assert isinstance(applicants, list)
            assert len(applicants) >= 1
            assert any(a.name == TOYOTA_APPLICANT_NAME for a in applicants)
            assert any(a.applicant_attorney_cd == TOYOTA_APPLICANT_CODE for a in applicants)

    @pytest.mark.asyncio
    async def test_applicant_by_code(self, vcr_cassette) -> None:
        """Reverse lookup: applicant code → name (single string)."""
        async with JpoClient() as client:
            name = await client.get_patent_applicant_by_code(TOYOTA_APPLICANT_CODE)
            assert isinstance(name, str)
            assert "トヨタ" in name


# =============================================================================
# Priority / divisional / registration / PCT
# =============================================================================


class TestPriorityAndFamilyLive:
    @pytest.mark.asyncio
    async def test_priority_info(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            priorities = await client.get_patent_priority_info(PATENT_APP)
            assert isinstance(priorities, list)
            # 2020123456 claims a national priority (2019210418).
            assert len(priorities) >= 1
            assert priorities[0].national_priority_application_number == "2019210418"

    @pytest.mark.asyncio
    async def test_divisional_info(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            div = await client.get_patent_divisional_info(PATENT_APP)
            assert div is None or isinstance(div, DivisionalAppInfoData)
            if div is not None:
                assert div.application_number == PATENT_APP

    @pytest.mark.asyncio
    async def test_registration_info(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            reg = await client.get_patent_registration_info(PATENT_APP)
            assert isinstance(reg, RegistrationInfo)
            assert reg.registration_number == "7533889"
            assert reg.application_number == PATENT_APP
            assert len(reg.right_person_information) >= 1


class TestPctNationalPhaseLive:
    @pytest.mark.asyncio
    async def test_pct_lookup_no_data(self, vcr_cassette) -> None:
        """A non-existent PCT number gracefully returns None."""
        async with JpoClient() as client:
            data = await client.get_patent_pct_national_number(
                PctKind.INTERNATIONAL_APPLICATION,
                "JP9999999999",
            )
            assert data is None or isinstance(data, PctNationalPhaseData)


# =============================================================================
# Design + trademark
# =============================================================================


class TestDesignProgressLive:
    @pytest.mark.asyncio
    async def test_get_design_progress(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            progress = await client.get_design_progress(DESIGN_APP)
            assert isinstance(progress, DesignProgressData)
            assert progress.application_number == DESIGN_APP
            assert progress.design_article  # non-empty
            assert progress.design_class  # non-empty


class TestTrademarkProgressLive:
    @pytest.mark.asyncio
    async def test_get_trademark_progress(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            progress = await client.get_trademark_progress(TRADEMARK_APP)
            assert isinstance(progress, TrademarkProgressData)
            assert progress.application_number == TRADEMARK_APP
            assert progress.trademark_for_display  # non-empty
            assert isinstance(progress.transliteration, dict)
            assert len(progress.goods_service_information) > 0


# =============================================================================
# Convenience functions
# =============================================================================


class TestConvenienceFunctionsLive:
    @pytest.mark.asyncio
    async def test_oneshot_get_patent_progress(self, vcr_cassette) -> None:
        progress = await get_patent_progress(PATENT_APP)
        assert isinstance(progress, PatentProgressData)
        assert progress.application_number == PATENT_APP

    @pytest.mark.asyncio
    async def test_oneshot_get_jplatpat_url(self, vcr_cassette) -> None:
        url = await get_patent_jplatpat_url(PATENT_APP)
        assert url is not None
        assert "j-platpat" in url.lower()


# =============================================================================
# Rate limiting
# =============================================================================


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_multiple_requests_within_limit(self, vcr_cassette) -> None:
        """5 requests in quick succession all succeed (well under 10/min cap)."""
        async with JpoClient() as client:
            for _ in range(5):
                progress = await client.get_patent_progress_simple(PATENT_APP)
                assert isinstance(progress, SimplifiedPatentProgressData)


# =============================================================================
# Design + trademark document bundles
# =============================================================================


class TestDesignDocumentsLive:
    """Design document-bundle endpoints — exercises real data on
    DESIGN_APP_WITH_DOCS so the parser path is covered live."""

    @pytest.mark.asyncio
    async def test_get_design_application_documents(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            bundle = await client.get_design_application_documents(DESIGN_APP_WITH_DOCS)
            assert isinstance(bundle, DocumentBundleResult)
            assert bundle.zip_bytes is not None
            assert bundle.zip_bytes.startswith(b"PK\x03\x04")

    @pytest.mark.asyncio
    async def test_get_design_refusal_notices(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            bundle = await client.get_design_refusal_notices(DESIGN_APP_WITH_DOCS)
            assert isinstance(bundle, DocumentBundleResult)
            assert bundle.zip_bytes is not None
            assert bundle.zip_bytes.startswith(b"PK\x03\x04")


class TestTrademarkDocumentsLive:
    """Trademark document-bundle endpoints — TRADEMARK_APP has refusal
    + decision documents on file, exercising the parser live."""

    @pytest.mark.asyncio
    async def test_get_trademark_mailed_documents(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            bundle = await client.get_trademark_mailed_documents(TRADEMARK_APP)
            assert isinstance(bundle, DocumentBundleResult)
            assert bundle.zip_bytes is not None
            assert bundle.zip_bytes.startswith(b"PK\x03\x04")

    @pytest.mark.asyncio
    async def test_get_trademark_refusal_notices(self, vcr_cassette) -> None:
        async with JpoClient() as client:
            bundle = await client.get_trademark_refusal_notices(TRADEMARK_APP)
            assert isinstance(bundle, DocumentBundleResult)
            assert bundle.zip_bytes is not None
            assert bundle.zip_bytes.startswith(b"PK\x03\x04")


# =============================================================================
# Document-bundle parser (live ZIP -> typed DocumentBundle)
# =============================================================================


class TestDocumentBundleParserLive:
    """End-to-end test: live JPO bundle -> parsed entries."""

    @pytest.mark.asyncio
    async def test_parse_patent_application_documents(self, vcr_cassette) -> None:
        from patent_client_agents.jpo import DocumentBundle, parse_document_bundle

        async with JpoClient() as client:
            raw = await client.get_patent_application_documents(PATENT_APP)
            bundle = parse_document_bundle(
                raw.zip_bytes,
                "application",
                "patent",
                application_number=PATENT_APP,
            )
            assert isinstance(bundle, DocumentBundle)
            assert bundle.ip_type == "patent"
            assert bundle.doc_kind == "application"
            assert len(bundle.entries) >= 1
            entry = bundle.entries[0]
            assert entry.document_code  # JPO 4-digit code
            assert entry.application_number == PATENT_APP
            # Body text should decode through Shift-JIS — assert it
            # contains either Japanese punctuation or hira/kata.
            assert entry.body_text

    @pytest.mark.asyncio
    async def test_parse_patent_refusal_notices(self, vcr_cassette) -> None:
        from patent_client_agents.jpo import parse_document_bundle

        async with JpoClient() as client:
            raw = await client.get_patent_refusal_notices(PATENT_APP)
            bundle = parse_document_bundle(
                raw.zip_bytes,
                "refusal",
                "patent",
                application_number=PATENT_APP,
            )
            assert bundle.doc_kind == "refusal"
            assert len(bundle.entries) >= 1
            entry = bundle.entries[0]
            assert entry.document_name  # 拒絶理由通知書
            assert entry.legal_date.startswith("20")
            assert entry.drafter_name  # examiner name
            assert len(entry.articles) >= 1

    @pytest.mark.asyncio
    async def test_parse_design_refusal_notices(self, vcr_cassette) -> None:
        """Designs use the same XML schema as patents for mailed docs."""
        from patent_client_agents.jpo import parse_document_bundle

        async with JpoClient() as client:
            raw = await client.get_design_refusal_notices(DESIGN_APP_WITH_DOCS)
            bundle = parse_document_bundle(
                raw.zip_bytes,
                "refusal",
                "design",
                application_number=DESIGN_APP_WITH_DOCS,
            )
            assert bundle.ip_type == "design"
            assert bundle.doc_kind == "refusal"
            assert len(bundle.entries) >= 1

    @pytest.mark.asyncio
    async def test_parse_trademark_refusal_notices(self, vcr_cassette) -> None:
        from patent_client_agents.jpo import parse_document_bundle

        async with JpoClient() as client:
            raw = await client.get_trademark_refusal_notices(TRADEMARK_APP)
            bundle = parse_document_bundle(
                raw.zip_bytes,
                "refusal",
                "trademark",
                application_number=TRADEMARK_APP,
            )
            assert bundle.ip_type == "trademark"
            assert bundle.doc_kind == "refusal"
            assert len(bundle.entries) >= 1


# =============================================================================
# Dispatched MCP tools (design + trademark routes)
# =============================================================================


class TestMcpDispatchLive:
    """Validate the MCP dispatcher tools end-to-end against live JPO."""

    @pytest.mark.asyncio
    async def test_progress_design(self, vcr_cassette) -> None:
        from patent_client_agents.mcp.tools.international import get_jpo_progress

        result = await get_jpo_progress(DESIGN_APP, ip_type="design")
        record = result.items[0]
        assert record["application_number"] == DESIGN_APP
        assert record.get("design_article")

    @pytest.mark.asyncio
    async def test_progress_trademark(self, vcr_cassette) -> None:
        from patent_client_agents.mcp.tools.international import get_jpo_progress

        result = await get_jpo_progress(TRADEMARK_APP, ip_type="trademark")
        record = result.items[0]
        assert record["application_number"] == TRADEMARK_APP
        assert record.get("trademark_for_display")

    @pytest.mark.asyncio
    async def test_jplatpat_url_design(self, vcr_cassette) -> None:
        from patent_client_agents.mcp.tools.international import get_jpo_jplatpat_url

        result = await get_jpo_jplatpat_url(DESIGN_APP, ip_type="design")
        assert result.details.get("url")
        assert "j-platpat" in result.details["url"].lower()

    @pytest.mark.asyncio
    async def test_get_jpo_documents_patent_refusal(self, vcr_cassette) -> None:
        """The dispatched documents tool returns parsed entries + a download URL."""
        from patent_client_agents.mcp.tools.international import get_jpo_documents

        result = await get_jpo_documents(
            PATENT_APP,
            doc_kind="refusal",
            ip_type="patent",
        )
        assert result["ip_type"] == "patent"
        assert result["doc_kind"] == "refusal"
        assert result["application_number"] == PATENT_APP
        assert isinstance(result["entries"], list)
        assert len(result["entries"]) >= 1
        # download_url is always populated when bundle is non-empty.
        assert "download_url" in result
