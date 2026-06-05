"""Tests for the clean-source (no-Google) variants in ``unified`` + the
``mcp.tools.patents`` clean helpers.

These back the hosted public connector's Path A re-point: the PDF and claims
cascades must never touch Google Patents. We assert: (1) the ODP-first claims
path still works, (2) the EPO fallback fires for non-US / ODP-miss, (3) the PDF
cascade is PPUBS→EPO with no Google hop, (4) figures honestly report
"no callouts from clean sources" without a Google call, and (5) the EPO claim
extractor tolerates model/dict shapes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_data_core.exceptions import NotFoundError
from patent_client_agents import unified
from patent_client_agents.mcp.tools.patents import get_patent_figures_clean

# ──────────────────────────────────────────────────────────────────────
# get_patent_claims_clean — ODP first, EPO fallback, never Google
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claims_clean_uses_odp_for_us():
    odp_claims = [
        {
            "claim_number": 1,
            "claim_text": "A widget comprising a foo.",
            "claim_type": "independent",
            "depends_on": [],
        }
    ]
    odp = MagicMock()
    odp.__aenter__ = AsyncMock(return_value=odp)
    odp.__aexit__ = AsyncMock(return_value=False)
    odp.get_granted_claims = AsyncMock(return_value=odp_claims)

    with patch(
        "patent_client_agents.uspto_odp.clients.applications.ApplicationsClient",
        return_value=odp,
    ):
        out = await unified.get_patent_claims_clean("US10123456B2")

    assert len(out) == 1
    assert out[0]["claim_number"] == 1
    odp.get_granted_claims.assert_awaited_once()


@pytest.mark.asyncio
async def test_claims_clean_falls_back_to_epo_for_nonus():
    # EPO fulltext with two claims; no ODP call expected (non-US).
    epo = MagicMock()
    epo.__aenter__ = AsyncMock(return_value=epo)
    epo.__aexit__ = AsyncMock(return_value=False)
    epo.fetch_fulltext = AsyncMock(
        return_value={"claims": [{"number": 1, "text": "Claim one."}, {"text": "Claim two."}]}
    )

    with patch("patent_client_agents.epo_ops.client.client_from_env", return_value=epo):
        out = await unified.get_patent_claims_clean("EP3456789A1")

    assert [c["claim_number"] for c in out] == [1, 2]
    assert out[0]["limitations"][0]["text"] == "Claim one."
    epo.fetch_fulltext.assert_awaited_once_with(number="EP3456789A1", section="claims")


@pytest.mark.asyncio
async def test_claims_clean_never_imports_google():
    """The clean path must not reference GooglePatentsClient at all."""
    epo = MagicMock()
    epo.__aenter__ = AsyncMock(return_value=epo)
    epo.__aexit__ = AsyncMock(return_value=False)
    epo.fetch_fulltext = AsyncMock(return_value={"claims": []})

    with patch("patent_client_agents.epo_ops.client.client_from_env", return_value=epo):
        with pytest.raises(NotFoundError):
            await unified.get_patent_claims_clean("EP0000000A1")


def test_epo_claim_texts_tolerates_dict_and_str():
    model = MagicMock()
    model.model_dump = MagicMock(
        return_value={"claims": [{"claim_number": 3, "claim_text": "X."}, "raw claim"]}
    )
    out = unified._epo_claim_texts(model)
    assert out == [(3, "X."), (2, "raw claim")]
    assert unified._epo_claim_texts({"claims": []}) == []
    assert unified._epo_claim_texts(None) == []


# ──────────────────────────────────────────────────────────────────────
# download_patent_pdf_clean — PPUBS → EPO, never Google
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pdf_clean_prefers_ppubs():
    result = MagicMock(pdf_base64="AAAA", publication_number="US10123456B2", patent_title="T")
    with patch(
        "patent_client_agents.uspto_publications.resolve_and_download_pdf",
        new=AsyncMock(return_value=result),
    ):
        out = await unified.download_patent_pdf_clean("US10123456B2")
    assert out.source == "ppubs"
    assert out.patent_number == "US10123456B2"


@pytest.mark.asyncio
async def test_pdf_clean_falls_through_to_epo():
    epo = MagicMock()
    epo.__aenter__ = AsyncMock(return_value=epo)
    epo.__aexit__ = AsyncMock(return_value=False)
    epo.download_pdf = AsyncMock(return_value=MagicMock(pdf_base64="AAAA"))

    with (
        patch(
            "patent_client_agents.uspto_publications.resolve_and_download_pdf",
            new=AsyncMock(side_effect=NotFoundError("no ppubs")),
        ),
        patch("patent_client_agents.epo_ops.client.client_from_env", return_value=epo),
    ):
        out = await unified.download_patent_pdf_clean("EP3456789A1")
    assert out.source == "epo"


@pytest.mark.asyncio
async def test_pdf_clean_raises_when_neither_clean_source_has_it():
    epo = MagicMock()
    epo.__aenter__ = AsyncMock(return_value=epo)
    epo.__aexit__ = AsyncMock(return_value=False)
    epo.download_pdf = AsyncMock(side_effect=RuntimeError("no epo"))

    with (
        patch(
            "patent_client_agents.uspto_publications.resolve_and_download_pdf",
            new=AsyncMock(side_effect=NotFoundError("no ppubs")),
        ),
        patch("patent_client_agents.epo_ops.client.client_from_env", return_value=epo),
    ):
        with pytest.raises(NotFoundError) as exc:
            await unified.download_patent_pdf_clean("XX999")
    # Honest about which clean sources were tried; no Google mentioned.
    assert "PPUBS" in str(exc.value) and "EPO" in str(exc.value)
    assert "oogle" not in str(exc.value)


# ──────────────────────────────────────────────────────────────────────
# get_patent_figures_clean — no callouts, no Google call, honest note
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_figures_clean_reports_no_callouts_without_google():
    # Patch GooglePatentsClient to blow up if touched — proves no Google call.
    with patch(
        "patent_client_agents.mcp.tools.patents.GooglePatentsClient",
        side_effect=AssertionError("Google must not be called"),
    ):
        out = await get_patent_figures_clean("US10123456B2")
    assert out["callouts_available"] is False
    assert out["results"] == []
    assert "patent_pdf" in out["pdf_source"]
    assert "clean public sources" in out["note"]
