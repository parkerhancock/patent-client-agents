"""Envelope-shape tests for the migrated JPO MCP tools.

Verifies the §5.9 contract for the JPO tool surface:
- ``get_jpo_progress`` / ``get_jpo_progress_simple`` / ``get_jpo_registration_info``
  are §5.4 list-accepting ``get_*`` tools returning ``ListEnvelope``.
- ``get_jpo_priority_info`` is a facet fetch returning ``ListEnvelope``.
- ``get_jpo_jplatpat_url`` and ``get_jpo_number_reference`` (the two §5.13
  rewrites) return ``ResponseEnvelope``.
- ``get_jpo_applicant`` collapses the prior by_code/by_name pair into one
  auto-dispatched tool per §5.3.
- Patent-only facet fetches (``get_jpo_patent_divisional_info``,
  ``get_jpo_patent_cited_documents``, ``get_jpo_pct_national_phase_number``)
  return ``ResponseEnvelope``.

Mocks ``JpoClient`` at the boundary — we're testing envelope shape, not
the upstream API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance, ResponseEnvelope
from patent_client_agents.jpo import (
    ApplicantAttorney,
    DivisionalAppInfoData,
    NumberReference,
    PatentProgressData,
    PriorityInfo,
    RegistrationInfo,
)
from patent_client_agents.mcp.tools import international as inter


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch):
    """Patch ``JpoClient`` with an async-context AsyncMock and return the inner mock."""
    inner = AsyncMock()

    class _MockCtx:
        async def __aenter__(self):
            return inner

        async def __aexit__(self, *exc):
            return None

    def _factory(*args, **kwargs):
        return _MockCtx()

    import patent_client_agents.jpo as jpo_module

    monkeypatch.setattr(jpo_module, "JpoClient", _factory)
    return inner


# ──────────────────────────────────────────────────────────────────────
# get_jpo_progress — §5.4 list-accepting ListEnvelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_jpo_progress_single_returns_list_envelope(mock_client) -> None:
    mock_client.get_patent_progress = AsyncMock(
        return_value=PatentProgressData(applicationNumber="2020123456")
    )
    result = await inter.get_jpo_progress("2020123456", ip_type="patent")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "Japan Patent Office (JPO)"
    assert "ip-data.jpo.go.jp" in result.provenance.source_url
    assert "/patent/v1/app_progress/2020123456" in result.provenance.source_url
    assert len(result.items) == 1
    assert "2020123456" in result.summary


@pytest.mark.asyncio
async def test_get_jpo_progress_list_preserves_order(mock_client) -> None:
    appls = ["2020100001", "2020100002", "2020100003"]
    responses = [PatentProgressData(applicationNumber=a) for a in appls]
    mock_client.get_patent_progress = AsyncMock(side_effect=responses)

    result = await inter.get_jpo_progress(appls, ip_type="patent")

    assert isinstance(result, ListEnvelope)
    returned = [item["application_number"] for item in result.items]
    assert returned == appls
    # Multi-id provenance points at the collection URL (no specific ID).
    assert result.provenance.source_url.endswith("/patent/v1/app_progress")
    assert "Fetched 3" in result.summary


@pytest.mark.asyncio
async def test_get_jpo_progress_empty_record_yields_empty_item(mock_client) -> None:
    mock_client.get_patent_progress = AsyncMock(return_value=None)
    result = await inter.get_jpo_progress("9999999999", ip_type="patent")
    assert isinstance(result, ListEnvelope)
    assert result.items == [{}]
    assert "no data" in result.summary.lower()


# ──────────────────────────────────────────────────────────────────────
# get_jpo_registration_info — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_jpo_registration_info_single_returns_list_envelope(mock_client) -> None:
    mock_client.get_patent_registration_info = AsyncMock(
        return_value=RegistrationInfo(registrationNumber="1234567")
    )
    result = await inter.get_jpo_registration_info("2020123456", ip_type="patent")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "Japan Patent Office (JPO)"
    assert "/patent/v1/registration_info/2020123456" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["registration_number"] == "1234567"
    assert "1234567" in result.summary


@pytest.mark.asyncio
async def test_get_jpo_registration_info_list_preserves_order(mock_client) -> None:
    appls = ["2020100001", "2020100002"]
    responses = [
        RegistrationInfo(registrationNumber="REG1"),
        RegistrationInfo(registrationNumber="REG2"),
    ]
    mock_client.get_patent_registration_info = AsyncMock(side_effect=responses)

    result = await inter.get_jpo_registration_info(appls, ip_type="patent")

    assert isinstance(result, ListEnvelope)
    assert [r["registration_number"] for r in result.items] == ["REG1", "REG2"]
    assert result.provenance.source_url.endswith("/patent/v1/registration_info")


# ──────────────────────────────────────────────────────────────────────
# get_jpo_priority_info — facet fetch, ListEnvelope per Shape D
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_jpo_priority_info_returns_list_envelope(mock_client) -> None:
    mock_client.get_patent_priority_info = AsyncMock(
        return_value=[
            PriorityInfo(parisPriorityCountryCd="US"),
            PriorityInfo(parisPriorityCountryCd="EP"),
        ]
    )
    result = await inter.get_jpo_priority_info("2020123456", ip_type="patent")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "Japan Patent Office (JPO)"
    assert "/patent/v1/priority_right_app_info/2020123456" in result.provenance.source_url
    assert len(result.items) == 2
    assert "2 priority claims" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_jpo_number_reference — §5.13 rewrite, ResponseEnvelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_jpo_number_reference_returns_response_envelope(mock_client) -> None:
    mock_client.get_patent_number_reference = AsyncMock(
        return_value=NumberReference(applicationNumber="2020123456")
    )
    result = await inter.get_jpo_number_reference(
        number="2020123456", kind="application", ip_type="patent"
    )

    assert isinstance(result, ResponseEnvelope)
    assert result.provenance.source_name == "Japan Patent Office (JPO)"
    assert "/patent/v1/case_number_reference/application/2020123456" in result.provenance.source_url
    assert result.details["application_number"] == "2020123456"
    assert "2020123456" in result.summary
    # §5.13 rewrite — the docstring first sentence names the actual operation
    # (application/publication/registration conversion), not a vague "other forms."
    assert inter.get_jpo_number_reference.__doc__
    first_sentence = inter.get_jpo_number_reference.__doc__.split("\n")[0].strip()
    assert "application" in first_sentence.lower()
    assert "publication" in first_sentence.lower()
    assert "registration" in first_sentence.lower()


# ──────────────────────────────────────────────────────────────────────
# get_jpo_jplatpat_url — §5.13 rewrite, ResponseEnvelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_jpo_jplatpat_url_returns_response_envelope(mock_client) -> None:
    permalink = "https://www.j-platpat.inpit.go.jp/c1800/PU/JP-2020-123456/x.html"
    mock_client.get_patent_jplatpat_url = AsyncMock(return_value=permalink)

    result = await inter.get_jpo_jplatpat_url("2020123456", ip_type="patent")

    assert isinstance(result, ResponseEnvelope)
    assert result.provenance.source_name == "Japan Patent Office (JPO)"
    assert "/patent/v1/jpp_fixed_address/2020123456" in result.provenance.source_url
    assert result.details["url"] == permalink
    # §5.13 rewrite — first sentence expands J-PlatPat for non-IP audience.
    assert inter.get_jpo_jplatpat_url.__doc__
    first_sentence = inter.get_jpo_jplatpat_url.__doc__.split("\n")[0].strip()
    assert "JPO public search portal" in first_sentence


@pytest.mark.asyncio
async def test_get_jpo_jplatpat_url_missing_url_empty_details(mock_client) -> None:
    mock_client.get_patent_jplatpat_url = AsyncMock(return_value=None)
    result = await inter.get_jpo_jplatpat_url("9999999999", ip_type="patent")
    assert isinstance(result, ResponseEnvelope)
    assert result.details == {}


# ──────────────────────────────────────────────────────────────────────
# get_jpo_applicant — §5.3 collapse: code/name auto-detect
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_jpo_applicant_code_branch(mock_client) -> None:
    """9-digit numeric identifier routes to the by-code endpoint."""
    mock_client.get_patent_applicant_by_code = AsyncMock(return_value="トヨタ自動車株式会社")
    result = await inter.get_jpo_applicant("000003207", ip_type="patent")

    assert isinstance(result, ResponseEnvelope)
    mock_client.get_patent_applicant_by_code.assert_awaited_once_with("000003207")
    assert result.details["name"] == "トヨタ自動車株式会社"
    assert "/patent/v1/applicant_attorney_cd/000003207" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_jpo_applicant_name_branch(mock_client) -> None:
    """Non-9-digit input routes to the by-name endpoint."""
    mock_client.get_patent_applicant_by_name = AsyncMock(
        return_value=[ApplicantAttorney(applicantAttorneyCd="000003207", name="トヨタ")]
    )
    result = await inter.get_jpo_applicant("トヨタ自動車株式会社", ip_type="patent")

    assert isinstance(result, ResponseEnvelope)
    mock_client.get_patent_applicant_by_name.assert_awaited_once_with("トヨタ自動車株式会社")
    assert len(result.details["results"]) == 1
    assert "/patent/v1/applicant_attorney/" in result.provenance.source_url


# ──────────────────────────────────────────────────────────────────────
# Patent-only facet fetches — ResponseEnvelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_jpo_patent_divisional_info_returns_response_envelope(mock_client) -> None:
    mock_client.get_patent_divisional_info = AsyncMock(return_value=DivisionalAppInfoData())
    result = await inter.get_jpo_patent_divisional_info("2020123456")

    assert isinstance(result, ResponseEnvelope)
    assert result.provenance.source_name == "Japan Patent Office (JPO)"
    assert "/patent/v1/divisional_app_info/2020123456" in result.provenance.source_url
    assert "2020123456" in result.summary


# ──────────────────────────────────────────────────────────────────────
# §5.4 — no batch tools introduced
# ──────────────────────────────────────────────────────────────────────


def test_no_batch_jpo_tools_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* covers the workflow."""
    for name in dir(inter):
        assert not name.startswith("batch_jpo")


# ──────────────────────────────────────────────────────────────────────
# §5.3 — old by_code/by_name pair is gone
# ──────────────────────────────────────────────────────────────────────


def test_collapsed_applicant_tool_only() -> None:
    """``get_jpo_applicant_by_code`` / ``by_name`` are collapsed into ``get_jpo_applicant``."""
    assert hasattr(inter, "get_jpo_applicant")
    assert not hasattr(inter, "get_jpo_applicant_by_code")
    assert not hasattr(inter, "get_jpo_applicant_by_name")


# ──────────────────────────────────────────────────────────────────────
# §5.6 — facet fetches cross-reference get_jpo_progress
# ──────────────────────────────────────────────────────────────────────


def test_facet_fetches_cross_reference_parent_progress() -> None:
    """Per §5.6 every JPO facet fetch should name ``get_jpo_progress`` as a relative."""
    for fn in (
        inter.get_jpo_progress_simple,
        inter.get_jpo_priority_info,
        inter.get_jpo_registration_info,
        inter.get_jpo_number_reference,
        inter.get_jpo_jplatpat_url,
        inter.get_jpo_applicant,
        inter.get_jpo_patent_divisional_info,
        inter.get_jpo_patent_cited_documents,
        inter.get_jpo_pct_national_phase_number,
    ):
        doc = fn.__doc__ or ""
        assert "Related tools:" in doc, f"{fn.__name__} missing Related tools line"
        assert "get_jpo_progress" in doc, f"{fn.__name__} should cross-ref get_jpo_progress"
