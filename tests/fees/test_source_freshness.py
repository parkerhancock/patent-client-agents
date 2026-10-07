from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from lxml import html

from patent_client_agents.fees.scrapers.uspto import USPTOFeesClient, _parse_effective_date


@pytest.mark.asyncio
async def test_cached_bytes_keep_retrieval_time_and_refresh_rechecks(tmp_path):
    async with USPTOFeesClient(cache_path=tmp_path) as client:
        client._request = AsyncMock(
            return_value=httpx.Response(
                200,
                content=b"fees",
                extensions={"hishel_from_cache": True, "hishel_created_at": 1000000000.0},
            )
        )
        await client.fetch_html()
        initial = dict(client.source_metadata)
        assert initial["bytes_retrieved_at"] == datetime.fromtimestamp(1000000000, UTC).isoformat()
        client._request.return_value = httpx.Response(
            200,
            content=b"fees",
            extensions={
                "hishel_from_cache": True,
                "hishel_revalidated": True,
                "hishel_created_at": 1000000000.0,
            },
        )
        await client.fetch_html(refresh=True)
        assert client.source_metadata["bytes_retrieved_at"] == initial["bytes_retrieved_at"]
        assert client.source_metadata["source_checked_at"] > initial["source_checked_at"]
        assert client.source_metadata["refresh_outcome"] == "succeeded"
        assert client._request.call_args.kwargs["headers"] == {"Cache-Control": "no-cache"}
        before_failure = dict(client.source_metadata)
        client._request.side_effect = httpx.ConnectError("failed")
        with pytest.raises(httpx.ConnectError):
            await client.fetch_html(refresh=True)
        failed = json.loads((tmp_path / "uspto-fees-receipt.json").read_text())
        assert failed["bytes_retrieved_at"] == before_failure["bytes_retrieved_at"]
        assert failed["source_checked_at"] == before_failure["source_checked_at"]
        assert failed["refresh_outcome"] == "failed"
        assert failed["refresh_error"] == "ConnectError"


@pytest.mark.asyncio
async def test_replaced_bytes_change_hash(tmp_path):
    async with USPTOFeesClient(cache_path=tmp_path) as client:
        client._request = AsyncMock(return_value=httpx.Response(200, content=b"old"))
        await client.fetch_html()
        old_hash = client.source_metadata["content_sha256"]
        client._request.return_value = httpx.Response(200, content=b"new")
        await client.fetch_html(refresh=True)
        assert client.source_metadata["content_sha256"] != old_hash


def test_effective_and_revision_dates_do_not_collapse():
    doc = html.fromstring("<p>Effective January 19, 2030 (Last revised May 1, 2026)</p>")
    assert _parse_effective_date(doc).isoformat() == "2030-01-19"
    with pytest.raises(ValueError, match="unknown"):
        _parse_effective_date(html.fromstring("<p>changed header</p>"))


@pytest.mark.asyncio
async def test_cached_other_version_does_not_borrow_check_time(tmp_path):
    async with USPTOFeesClient(cache_path=tmp_path) as client:
        client._request = AsyncMock(return_value=httpx.Response(200, content=b"new"))
        await client.fetch_html()
        client._request.return_value = httpx.Response(
            200,
            content=b"old",
            extensions={"hishel_from_cache": True, "hishel_created_at": 1000000000.0},
        )
        await client.fetch_html()
        assert (
            client.source_metadata["source_checked_at"]
            == datetime.fromtimestamp(1000000000, UTC).isoformat()
        )
        with pytest.raises(RuntimeError, match="without source revalidation"):
            await client.fetch_html(refresh=True)
        assert client.source_metadata["refresh_outcome"] == "failed"


def test_unknown_retrieval_age_is_not_reported_as_zero():
    from datetime import date
    from decimal import Decimal

    from patent_client_agents.fees.api import estimate_freshness
    from patent_client_agents.fees.models import FeeItem, FeeSchedule

    schedule = FeeSchedule(
        jurisdiction="US",
        issuing_body="USPTO",
        office_code="USPTO",
        right="patent",
        currency="USD",
        effective_date=date(2025, 1, 19),
        source_url="https://www.uspto.gov",
        retrieved_at=None,
        fees=[
            FeeItem(
                code="1001",
                label="test",
                category="filing",
                rights=["patent"],
                amount=Decimal("1"),
                currency="USD",
            )
        ],
    )
    assert estimate_freshness(schedule)["days_since_retrieval"] is None
    assert estimate_freshness(schedule)["retrieved_at"] is None
