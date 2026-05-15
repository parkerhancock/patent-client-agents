"""Unit tests for the JPO MCP tool dispatcher.

Verifies that each ``ip_type``-dispatched tool routes to the correct
``JpoClient`` method. Heavy on monkey-patching; no network.

Envelope-shape assertions live in ``test_mcp_envelope.py``; these tests
focus on dispatch routing and reach through the envelope (``items[0]``
or ``.details``) to confirm the right upstream method was called.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from patent_client_agents.jpo import (
    ApplicantAttorney,
    DesignProgressData,
    DocumentBundleResult,
    NumberReference,
    PatentProgressData,
    PriorityInfo,
    RegistrationInfo,
    TrademarkProgressData,
)
from patent_client_agents.mcp.tools import international as inter


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch):
    """Patch ``patent_client_agents.jpo.JpoClient`` with an async-context AsyncMock.

    Returns the inner mock so individual methods (``get_patent_progress``,
    etc.) can be configured per-test.
    """
    inner = AsyncMock()

    class _MockCtx:
        async def __aenter__(self):
            return inner

        async def __aexit__(self, *exc):
            return None

    def _factory(*args, **kwargs):
        return _MockCtx()

    # Patch the JpoClient symbol in the lazily-imported module.
    import patent_client_agents.jpo as jpo_module

    monkeypatch.setattr(jpo_module, "JpoClient", _factory)
    return inner


# ---------------------------------------------------------------------------
# get_jpo_progress dispatcher
# ---------------------------------------------------------------------------


class TestGetJpoProgressDispatch:
    @pytest.mark.asyncio
    async def test_routes_to_patent_method(self, mock_client) -> None:
        mock_client.get_patent_progress = AsyncMock(
            return_value=PatentProgressData(applicationNumber="2020123456")
        )
        result = await inter.get_jpo_progress("2020123456", ip_type="patent")
        mock_client.get_patent_progress.assert_awaited_once_with("2020123456")
        assert result.items[0]["application_number"] == "2020123456"

    @pytest.mark.asyncio
    async def test_routes_to_design_method(self, mock_client) -> None:
        mock_client.get_design_progress = AsyncMock(
            return_value=DesignProgressData(applicationNumber="2020015234")
        )
        result = await inter.get_jpo_progress("2020015234", ip_type="design")
        mock_client.get_design_progress.assert_awaited_once_with("2020015234")
        assert result.items[0]["application_number"] == "2020015234"

    @pytest.mark.asyncio
    async def test_routes_to_trademark_method(self, mock_client) -> None:
        mock_client.get_trademark_progress = AsyncMock(
            return_value=TrademarkProgressData(applicationNumber="2024123456")
        )
        result = await inter.get_jpo_progress("2024123456", ip_type="trademark")
        mock_client.get_trademark_progress.assert_awaited_once_with("2024123456")
        assert result.items[0]["application_number"] == "2024123456"

    @pytest.mark.asyncio
    async def test_unknown_ip_type_raises(self, mock_client) -> None:
        from law_tools_core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="ip_type"):
            await inter.get_jpo_progress("2020123456", ip_type="utility")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_data(self, mock_client) -> None:
        mock_client.get_patent_progress = AsyncMock(return_value=None)
        result = await inter.get_jpo_progress("9999999999", ip_type="patent")
        # Single-id call still returns ListEnvelope per §5.4; item is {}.
        assert result.items == [{}]


# ---------------------------------------------------------------------------
# get_jpo_progress_simple
# ---------------------------------------------------------------------------


class TestGetJpoProgressSimpleDispatch:
    @pytest.mark.asyncio
    async def test_routes_design_simple(self, mock_client) -> None:
        mock_client.get_design_progress_simple = AsyncMock(
            return_value=DesignProgressData(applicationNumber="2020015234")
        )
        result = await inter.get_jpo_progress_simple("2020015234", ip_type="design")
        mock_client.get_design_progress_simple.assert_awaited_once_with("2020015234")
        assert result.items[0]["application_number"] == "2020015234"

    @pytest.mark.asyncio
    async def test_routes_trademark_simple(self, mock_client) -> None:
        mock_client.get_trademark_progress_simple = AsyncMock(
            return_value=TrademarkProgressData(applicationNumber="2024123456")
        )
        result = await inter.get_jpo_progress_simple("2024123456", ip_type="trademark")
        mock_client.get_trademark_progress_simple.assert_awaited_once_with("2024123456")
        assert result.items[0]["application_number"] == "2024123456"


# ---------------------------------------------------------------------------
# get_jpo_priority_info
# ---------------------------------------------------------------------------


class TestGetJpoPriorityInfoDispatch:
    @pytest.mark.asyncio
    async def test_routes_design_priority(self, mock_client) -> None:
        mock_client.get_design_priority_info = AsyncMock(
            return_value=[PriorityInfo(parisPriorityCountryCd="US")]
        )
        result = await inter.get_jpo_priority_info("2020015234", ip_type="design")
        mock_client.get_design_priority_info.assert_awaited_once_with("2020015234")
        assert result.items == [PriorityInfo(parisPriorityCountryCd="US").model_dump()]

    @pytest.mark.asyncio
    async def test_routes_trademark_priority(self, mock_client) -> None:
        mock_client.get_trademark_priority_info = AsyncMock(return_value=[])
        result = await inter.get_jpo_priority_info("2024123456", ip_type="trademark")
        mock_client.get_trademark_priority_info.assert_awaited_once_with("2024123456")
        assert result.items == []


# ---------------------------------------------------------------------------
# get_jpo_registration_info
# ---------------------------------------------------------------------------


class TestGetJpoRegistrationInfoDispatch:
    @pytest.mark.asyncio
    async def test_routes_design_registration(self, mock_client) -> None:
        mock_client.get_design_registration_info = AsyncMock(
            return_value=RegistrationInfo(registrationNumber="1234567")
        )
        result = await inter.get_jpo_registration_info("2020015234", ip_type="design")
        mock_client.get_design_registration_info.assert_awaited_once_with("2020015234")
        assert result.items[0]["registration_number"] == "1234567"

    @pytest.mark.asyncio
    async def test_returns_empty_for_unregistered(self, mock_client) -> None:
        mock_client.get_trademark_registration_info = AsyncMock(return_value=None)
        result = await inter.get_jpo_registration_info("2024123456", ip_type="trademark")
        assert result.items == [{}]


# ---------------------------------------------------------------------------
# get_jpo_number_reference
# ---------------------------------------------------------------------------


class TestGetJpoNumberReferenceDispatch:
    @pytest.mark.asyncio
    async def test_routes_design_number_ref(self, mock_client) -> None:
        mock_client.get_design_number_reference = AsyncMock(
            return_value=NumberReference(applicationNumber="2020015234")
        )
        result = await inter.get_jpo_number_reference(
            number="2020015234",
            kind="application",
            ip_type="design",
        )
        mock_client.get_design_number_reference.assert_awaited_once_with(
            "application", "2020015234"
        )
        assert result.details["application_number"] == "2020015234"

    @pytest.mark.asyncio
    async def test_routes_trademark_number_ref(self, mock_client) -> None:
        mock_client.get_trademark_number_reference = AsyncMock(return_value=None)
        result = await inter.get_jpo_number_reference(
            number="2024123456",
            kind="application",
            ip_type="trademark",
        )
        assert result.details == {}


# ---------------------------------------------------------------------------
# get_jpo_jplatpat_url
# ---------------------------------------------------------------------------


class TestGetJpoJplatpatUrlDispatch:
    @pytest.mark.asyncio
    async def test_routes_design_jplatpat(self, mock_client) -> None:
        mock_client.get_design_jplatpat_url = AsyncMock(
            return_value="https://j-platpat.example/design/2020015234"
        )
        result = await inter.get_jpo_jplatpat_url("2020015234", ip_type="design")
        mock_client.get_design_jplatpat_url.assert_awaited_once_with("2020015234")
        assert result.details["url"].startswith("https://")


# ---------------------------------------------------------------------------
# get_jpo_applicant — collapsed code/name lookups (§5.3)
# ---------------------------------------------------------------------------


class TestGetJpoApplicantDispatch:
    @pytest.mark.asyncio
    async def test_code_lookup_routes_design(self, mock_client) -> None:
        # 9-digit numeric → code lookup branch
        mock_client.get_design_applicant_by_code = AsyncMock(return_value="株式会社サンプル")
        result = await inter.get_jpo_applicant("000003207", ip_type="design")
        mock_client.get_design_applicant_by_code.assert_awaited_once_with("000003207")
        assert result.details["name"] == "株式会社サンプル"

    @pytest.mark.asyncio
    async def test_name_lookup_routes_trademark(self, mock_client) -> None:
        # Non-9-digit → name lookup branch
        mock_client.get_trademark_applicant_by_name = AsyncMock(
            return_value=[ApplicantAttorney(applicantAttorneyCd="000003207", name="テスト")]
        )
        result = await inter.get_jpo_applicant("テスト", ip_type="trademark")
        mock_client.get_trademark_applicant_by_name.assert_awaited_once_with("テスト")
        assert len(result.details["results"]) == 1
        assert result.details["results"][0]["applicant_attorney_cd"] == "000003207"


# ---------------------------------------------------------------------------
# Patent-only tools
# ---------------------------------------------------------------------------


class TestPatentOnlyTools:
    @pytest.mark.asyncio
    async def test_divisional_info(self, mock_client) -> None:
        mock_client.get_patent_divisional_info = AsyncMock(return_value=None)
        result = await inter.get_jpo_patent_divisional_info("2020123456")
        mock_client.get_patent_divisional_info.assert_awaited_once_with("2020123456")
        assert result.details == {}

    @pytest.mark.asyncio
    async def test_pct_national_phase(self, mock_client) -> None:
        mock_client.get_patent_pct_national_number = AsyncMock(return_value=None)
        result = await inter.get_jpo_pct_national_phase_number(
            number="JP9999999999",
            kind="international_application",
        )
        mock_client.get_patent_pct_national_number.assert_awaited_once_with(
            "international_application", "JP9999999999"
        )
        assert result.details == {}


# ---------------------------------------------------------------------------
# get_jpo_documents (parsed contents + signed download URL)
# ---------------------------------------------------------------------------


class TestGetJpoDocumentsDispatch:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_documents(self, mock_client) -> None:
        mock_client.get_patent_mailed_documents = AsyncMock(
            return_value=DocumentBundleResult(application_number="2020123456")
        )
        result = await inter.get_jpo_documents("2020123456", doc_kind="mailed", ip_type="patent")
        assert result == {}

    @pytest.mark.asyncio
    async def test_routes_design_application_docs(self, mock_client) -> None:
        from tests.jpo.fixtures.document_bundles import make_application_bundle_zip

        mock_client.get_design_application_documents = AsyncMock(
            return_value=DocumentBundleResult(
                application_number="2020015234",
                zip_bytes=make_application_bundle_zip(),
                content_type="application/zip",
            )
        )
        result = await inter.get_jpo_documents(
            "2020015234",
            doc_kind="application",
            ip_type="design",
        )
        mock_client.get_design_application_documents.assert_awaited_once_with("2020015234")
        assert result["ip_type"] == "design"
        assert result["doc_kind"] == "application"
        assert result["application_number"] == "2020015234"
        assert isinstance(result["entries"], list)
        assert len(result["entries"]) >= 1
        assert "download_url" in result
        assert result["filename"].endswith(".zip")
        assert result["content_type"] == "application/zip"

    @pytest.mark.asyncio
    async def test_routes_trademark_refusal_docs(self, mock_client) -> None:
        from tests.jpo.fixtures.document_bundles import make_refusal_bundle_zip

        mock_client.get_trademark_refusal_notices = AsyncMock(
            return_value=DocumentBundleResult(
                application_number="2024123456",
                zip_bytes=make_refusal_bundle_zip(),
                content_type="application/zip",
            )
        )
        result = await inter.get_jpo_documents(
            "2024123456",
            doc_kind="refusal",
            ip_type="trademark",
        )
        mock_client.get_trademark_refusal_notices.assert_awaited_once_with("2024123456")
        assert result["ip_type"] == "trademark"
        assert result["doc_kind"] == "refusal"
        assert len(result["entries"]) == 1
        assert result["entries"][0]["document_name"]  # 拒絶理由通知書

    @pytest.mark.asyncio
    async def test_unknown_doc_kind_raises(self, mock_client) -> None:
        from law_tools_core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="doc_kind"):
            await inter.get_jpo_documents(
                "2020123456",
                doc_kind="bogus",  # type: ignore[arg-type]
                ip_type="patent",
            )

    @pytest.mark.asyncio
    async def test_parse_false_skips_parsing_returns_download_url(
        self,
        mock_client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``parse=False`` skips the parser and returns metadata + signed URL only."""
        from tests.jpo.fixtures.document_bundles import make_mailed_bundle_zip

        # Pin a public URL so download_response returns a signed download_url
        # rather than a tempfile file_path — keeps the assertion stable.
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://mcp.example.com")

        zip_bytes = make_mailed_bundle_zip()
        mock_client.get_patent_mailed_documents = AsyncMock(
            return_value=DocumentBundleResult(
                application_number="2020123456",
                zip_bytes=zip_bytes,
                content_type="application/zip",
            )
        )
        result = await inter.get_jpo_documents(
            "2020123456",
            doc_kind="mailed",
            ip_type="patent",
            parse=False,
        )

        # Metadata fields are populated, but parsing was skipped.
        assert result["application_number"] == "2020123456"
        assert result["ip_type"] == "patent"
        assert result["doc_kind"] == "mailed"
        assert result["entries"] == []
        assert result["binary_attachments"] == []

        # Standard download response wired up.
        assert result["download_url"].startswith("https://mcp.example.com/")
        assert result["filename"].endswith(".zip")
        assert result["content_type"] == "application/zip"
        assert result["size_bytes"] == len(zip_bytes)

    @pytest.mark.asyncio
    async def test_parse_false_empty_bundle_matches_parse_true_empty(self, mock_client) -> None:
        """An empty JPO bundle (status 107/108) returns ``{}`` regardless of ``parse``."""
        # parse=True empty
        mock_client.get_patent_mailed_documents = AsyncMock(
            return_value=DocumentBundleResult(application_number="2020123456")
        )
        result_true = await inter.get_jpo_documents(
            "2020123456",
            doc_kind="mailed",
            ip_type="patent",
            parse=True,
        )

        # parse=False empty
        mock_client.get_patent_mailed_documents = AsyncMock(
            return_value=DocumentBundleResult(application_number="2020123456")
        )
        result_false = await inter.get_jpo_documents(
            "2020123456",
            doc_kind="mailed",
            ip_type="patent",
            parse=False,
        )

        assert result_true == {}
        assert result_false == {}
        # Specifically: no leaked download_url for an empty bundle.
        assert "download_url" not in result_false
        assert "file_path" not in result_false

    @pytest.mark.asyncio
    async def test_parse_true_default_unchanged(self, mock_client) -> None:
        """``parse=True`` (the default) parses the bundle and returns inline entries."""
        from tests.jpo.fixtures.document_bundles import make_mailed_bundle_zip

        mock_client.get_patent_mailed_documents = AsyncMock(
            return_value=DocumentBundleResult(
                application_number="2020123456",
                zip_bytes=make_mailed_bundle_zip(),
                content_type="application/zip",
            )
        )
        result = await inter.get_jpo_documents(
            "2020123456",
            doc_kind="mailed",
            ip_type="patent",
        )

        assert result["ip_type"] == "patent"
        assert result["doc_kind"] == "mailed"
        assert result["application_number"] == "2020123456"
        # Parsed entries are populated with body text — i.e. the parser ran.
        assert len(result["entries"]) == 1
        entry = result["entries"][0]
        assert entry["document_name"]  # 拒絶理由通知書
        assert entry["body_text"]
        assert "download_url" in result
        assert result["filename"].endswith(".zip")
        assert result["content_type"] == "application/zip"
