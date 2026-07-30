"""Tests for the Google → PPUBS → EPO cascade in ``download_patent_pdf``.

The cascade's contract is that it keeps trying until a source has the PDF,
and raises ``NotFoundError`` only when none of them do. Google Patents
answers an unknown publication with a bare HTTP 404, which is not in the
exception hierarchy the other sources raise — so a very recent US
publication, present in PPUBS but not yet on Google, used to abort the whole
cascade at the first hop. That case is the reason these tests exist.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_data_core.exceptions import NotFoundError
from patent_client_agents import unified


def google_client(**behavior):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.download_patent_pdf = AsyncMock(**behavior)
    return client


def http_error(status: int, url: str = "https://patents.google.com/patent/X/en"):
    request = httpx.Request("GET", url)
    return httpx.HTTPStatusError(
        f"Client error '{status}'",
        request=request,
        response=httpx.Response(status, request=request),
    )


def ppubs_result(payload: bytes = b"%PDF from ppubs"):
    return MagicMock(
        pdf_base64=base64.b64encode(payload).decode(),
        publication_number="20260203524",
        patent_title="ARTIFICIAL INTELLIGENCE MULTI-AGENT SYSTEM FOR DECISION SUPPORT",
    )


@pytest.mark.asyncio
async def test_google_serves_the_pdf_when_it_has_one():
    with patch(
        "patent_client_agents.google_patents.GooglePatentsClient",
        return_value=google_client(return_value=b"%PDF from google"),
    ):
        out = await unified.download_patent_pdf("US10123456B2")
    assert out.source == "google_patents"
    assert out.pdf_bytes == b"%PDF from google"


@pytest.mark.asyncio
async def test_a_google_404_falls_through_to_ppubs():
    """A publication issued last week is on PPUBS long before it is on Google."""
    with (
        patch(
            "patent_client_agents.google_patents.GooglePatentsClient",
            return_value=google_client(side_effect=http_error(404)),
        ),
        patch(
            "patent_client_agents.uspto_publications.resolve_and_download_pdf",
            new=AsyncMock(return_value=ppubs_result()),
        ),
    ):
        out = await unified.download_patent_pdf("US20260203524A1")
    assert out.source == "ppubs"
    assert out.pdf_bytes == b"%PDF from ppubs"
    assert out.patent_title.startswith("ARTIFICIAL INTELLIGENCE")


@pytest.mark.asyncio
async def test_a_google_server_error_is_not_swallowed():
    """Only a 404 means 'not here'. A 503 is a fault and must surface."""
    with patch(
        "patent_client_agents.google_patents.GooglePatentsClient",
        return_value=google_client(side_effect=http_error(503)),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await unified.download_patent_pdf("US10123456B2")


@pytest.mark.asyncio
async def test_every_source_missing_it_raises_not_found_naming_each():
    epo = MagicMock()
    epo.__aenter__ = AsyncMock(return_value=epo)
    epo.__aexit__ = AsyncMock(return_value=False)
    epo.download_pdf = AsyncMock(side_effect=RuntimeError("no epo"))

    with (
        patch(
            "patent_client_agents.google_patents.GooglePatentsClient",
            return_value=google_client(side_effect=http_error(404)),
        ),
        patch(
            "patent_client_agents.uspto_publications.resolve_and_download_pdf",
            new=AsyncMock(side_effect=NotFoundError("no ppubs")),
        ),
        patch("patent_client_agents.epo_ops.client.client_from_env", return_value=epo),
    ):
        with pytest.raises(NotFoundError) as exc:
            await unified.download_patent_pdf("US99999999A1")
    message = str(exc.value)
    assert "google_patents" in message and "ppubs" in message and "epo" in message
