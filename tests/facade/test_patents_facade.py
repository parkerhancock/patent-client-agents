"""Routing contract for the consolidated cross-jurisdiction patent facade.

Path A: Google Patents is removed. Every branch routes to a clean public
source. These tests pin the *routing* — that the right ``view``/``jurisdiction``
reaches the right clean underlying function with the right arguments, that KR
degrades gracefully when ``KIPO_KIPRIS_API_KEY`` is unset, and that CN/JP/non-US
paths return an actionable message rather than a silent empty or a Google call.
Targets are patched where the facade imports them (``...facade.patents``), so no
upstream HTTP is touched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.exceptions import ValidationError
from patent_client_agents.facade.patents import (
    get_patent,
    patent_client_status,
    resolve_patent_number,
    search_patents,
)

_MOD = "patent_client_agents.facade.patents"


# ──────────────────────────────────────────────────────────────────────
# search_patents — jurisdiction routing to clean sources
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_patents_us_routes_to_ppubs():
    with patch(f"{_MOD}.search_patent_publications", new=AsyncMock(return_value="US")) as m:
        out = await search_patents(query="neural CLM/network", jurisdiction="us", limit=10)
    assert out == "US"
    m.assert_awaited_once_with(query="neural CLM/network", limit=10, full=False)


@pytest.mark.asyncio
async def test_search_patents_us_defaults_to_reliable_ppubs_page_size():
    with patch(f"{_MOD}.search_patent_publications", new=AsyncMock(return_value="US")) as m:
        out = await search_patents(query="neural.CLM.", jurisdiction="us")

    assert out == "US"
    m.assert_awaited_once_with(query="neural.CLM.", limit=20, full=False)


@pytest.mark.asyncio
async def test_search_patents_ep_wo_routes_to_epo_cql():
    with patch(f"{_MOD}.search_epo", new=AsyncMock(return_value="EPWO")) as m:
        out = await search_patents(query="ta=CRISPR", jurisdiction="ep_wo", limit=5, full=True)
    assert out == "EPWO"
    m.assert_awaited_once_with(cql_query="ta=CRISPR", range_begin=1, range_end=5, full=True)


@pytest.mark.asyncio
async def test_search_patents_kr_routes_to_kipris_when_configured(monkeypatch):
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    fake = AsyncMock(return_value="KR")
    with patch("patent_client_agents.mcp.tools.kipo_kipris.search_kipo_patents", new=fake):
        out = await search_patents(query="배터리", jurisdiction="kr", limit=10)
    assert out == "KR"
    fake.assert_awaited_once_with(query="배터리", num_of_rows=10, full=False)


@pytest.mark.asyncio
async def test_search_patents_kr_degrades_gracefully_when_unconfigured(monkeypatch):
    monkeypatch.delenv("KIPO_KIPRIS_API_KEY", raising=False)
    with pytest.raises(ValidationError) as exc:
        await search_patents(query="battery", jurisdiction="kr")
    # Actionable: names the env var and points to working alternatives.
    assert "KIPO_KIPRIS_API_KEY" in str(exc.value)
    assert "us" in str(exc.value) or "ep_wo" in str(exc.value)


# ──────────────────────────────────────────────────────────────────────
# get_patent — view + jurisdiction dispatch to clean sources
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_patent_biblio_us_routes_to_ppubs():
    with patch(f"{_MOD}.get_patent_publication", new=AsyncMock(return_value="PUB")) as m:
        out = await get_patent(view="biblio", identifier="US10123456B2")
    assert out == "PUB"
    m.assert_awaited_once_with(publication_number=["US10123456B2"])


@pytest.mark.asyncio
async def test_get_patent_biblio_nonus_routes_to_epo():
    with patch(f"{_MOD}.get_epo_biblio", new=AsyncMock(return_value="EPO")) as m:
        out = await get_patent(view="biblio", identifier="EP3456789A1")
    assert out == "EPO"
    m.assert_awaited_once_with(patent_number=["EP3456789A1"])


@pytest.mark.asyncio
async def test_get_patent_biblio_mixed_list_routes_to_epo():
    ids = ["US10123456B2", "EP3456789A1"]
    with patch(f"{_MOD}.get_epo_biblio", new=AsyncMock(return_value="EPO")) as m:
        out = await get_patent(view="biblio", identifier=ids)
    assert out == "EPO"
    m.assert_awaited_once_with(patent_number=ids)


@pytest.mark.asyncio
async def test_get_patent_biblio_kr_routes_to_kipris_when_configured(monkeypatch):
    monkeypatch.setenv("KIPO_KIPRIS_API_KEY", "k")
    fake = AsyncMock(return_value="KRREC")
    with patch("patent_client_agents.mcp.tools.kipo_kipris.get_kipo_patent", new=fake):
        out = await get_patent(view="biblio", identifier="KR1020230012345")
    assert out == "KRREC"
    fake.assert_awaited_once_with(application_number=["10" + "20230012345"])  # digits only


@pytest.mark.asyncio
async def test_get_patent_biblio_kr_degrades_when_unconfigured(monkeypatch):
    monkeypatch.delenv("KIPO_KIPRIS_API_KEY", raising=False)
    with pytest.raises(ValidationError) as exc:
        await get_patent(view="biblio", identifier="KR1020230012345")
    assert "KIPO_KIPRIS_API_KEY" in str(exc.value)


@pytest.mark.asyncio
async def test_get_patent_claims_routes_to_clean_cascade():
    with patch(f"{_MOD}.get_patent_claims_clean", new=AsyncMock(return_value="CLAIMS")) as m:
        out = await get_patent(view="claims", identifier="US10123456B2")
    assert out == "CLAIMS"
    m.assert_awaited_once_with("US10123456B2")


@pytest.mark.asyncio
async def test_get_patent_family_routes_via_odp():
    with patch(f"{_MOD}.get_patent_family", new=AsyncMock(return_value="FAMILY")) as m:
        out = await get_patent(view="family", identifier="US10123456B2")
    assert out == "FAMILY"
    m.assert_awaited_once_with("US10123456B2", identifier_type="patent")


@pytest.mark.asyncio
async def test_get_patent_figures_routes_to_clean_no_callouts():
    with patch(f"{_MOD}.get_patent_figures_clean", new=AsyncMock(return_value="FIG")) as m:
        out = await get_patent(view="figures", identifier="US10123456B2")
    assert out == "FIG"
    m.assert_awaited_once_with("US10123456B2")


@pytest.mark.asyncio
async def test_get_patent_citations_us_returns_examiner_refs_labeled_honestly():
    from mcp_data_core.envelope import ListEnvelope, ResponseEnvelope, make_provenance

    fake_oa = ListEnvelope[dict](
        summary="3 hits.",
        items=[{"reference": "US9000000B2"}],
        provenance=make_provenance(source_url="https://x", source_name="USPTO"),
    )
    with patch(f"{_MOD}.search_office_actions", new=AsyncMock(return_value=fake_oa)) as m:
        out = await get_patent(view="citations", identifier="US10123456B2")
    assert isinstance(out, ResponseEnvelope)
    # Honest: explicitly NOT forward citations.
    assert "not" in out.summary.lower() and "forward citation" in out.summary.lower()
    assert out.details["examiner_cited_references"] == [{"reference": "US9000000B2"}]
    m.assert_awaited_once()
    # keyed by application number, citations result type
    _, kwargs = m.call_args
    assert kwargs["result_type"] == "citations"
    assert "patentApplicationNumber" in kwargs["criteria"]


@pytest.mark.asyncio
async def test_get_patent_citations_nonus_returns_unavailable_not_empty():
    from mcp_data_core.envelope import ResponseEnvelope

    out = await get_patent(view="citations", identifier="EP3456789A1")
    assert isinstance(out, ResponseEnvelope)
    assert out.details["available"] is False
    assert "not available" in out.summary.lower()
    # Never silently empty, never a Google call.


@pytest.mark.asyncio
async def test_get_patent_nonbiblio_view_rejects_list():
    with pytest.raises(ValidationError):
        await get_patent(view="claims", identifier=["US1", "US2"])


# ──────────────────────────────────────────────────────────────────────
# resolve_patent_number — unchanged (never touched Google)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_mode_is_default_and_forwards_number():
    with patch(f"{_MOD}.resolve_publication_number", new=AsyncMock(return_value="RES")) as m:
        out = await resolve_patent_number(number="10123456")
    assert out == "RES"
    m.assert_awaited_once_with(publication_number="10123456")


@pytest.mark.asyncio
async def test_resolve_requires_number():
    with pytest.raises(ValidationError):
        await resolve_patent_number(mode="resolve")


@pytest.mark.asyncio
async def test_resolve_convert_epo_forwards_formats():
    with patch(f"{_MOD}.convert_epo_number", new=AsyncMock(return_value="CONV")) as m:
        out = await resolve_patent_number(
            mode="convert_epo",
            number="EP1234567A1",
            input_format="original",
            output_format="epodoc",
        )
    assert out == "CONV"
    m.assert_awaited_once_with(
        number="EP1234567A1", input_format="original", output_format="epodoc"
    )


@pytest.mark.asyncio
async def test_resolve_cql_help_takes_no_identifier():
    with patch(f"{_MOD}.get_epo_cql_help", new=AsyncMock(return_value="CQL")) as m:
        out = await resolve_patent_number(mode="cql_help")
    assert out == "CQL"
    m.assert_awaited_once_with()


# ──────────────────────────────────────────────────────────────────────
# patent_client_status — no-network utility; clean backbone advertised
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patent_client_status_reports_clean_backbone(monkeypatch):
    for var in (
        "USPTO_ODP_API_KEY",
        "EPO_OPS_API_KEY",
        "EPO_OPS_API_SECRET",
        "KIPO_KIPRIS_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("USPTO_ODP_API_KEY", "k")
    monkeypatch.setenv("EPO_OPS_API_KEY", "k")  # only one of two EPO vars

    out = await patent_client_status()

    assert isinstance(out["version"], str)
    fams = out["configured_families"]
    assert fams["uspto"] is True
    assert fams["epo"] is False
    assert fams["kipo"] is False
    # Clean backbone, no google_patents.
    assert "uspto_ppubs" in out["always_available"]
    assert "epo_ops" in out["always_available"]
    assert "google_patents" not in out["always_available"]


# ──────────────────────────────────────────────────────────────────────
# End-to-end: facade → real PPUBS dispatch → §5.9 envelope survives.
# Proves the envelope contract survives, with NO Google client touched.
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_patents_us_preserves_envelope_end_to_end():
    from mcp_data_core.envelope import ListEnvelope

    class _FakePage:
        def model_dump(self, *args, **kwargs):
            return {
                "docs": [{"publication_number": "US10123456B2", "title": "Test"}],
                "num_found": 1,  # families on this page
                "num_families": 42,
                "num_documents": 97,
            }

    with patch("patent_client_agents.mcp.tools.publications.PublicSearchClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search_biblio = AsyncMock(return_value=_FakePage())
        out = await search_patents(query="neural", jurisdiction="us", limit=1)

    assert isinstance(out, ListEnvelope)
    assert "patents.google.com" not in (out.provenance.source_url or "")
    assert len(out.items) == 1
    assert out.items[0]["publication_number"] == "US10123456B2"
    assert out.more_available is True  # 42 families, 1 shown
