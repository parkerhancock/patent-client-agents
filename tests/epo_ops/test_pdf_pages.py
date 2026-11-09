"""Tests for paced, resumable EPO OPS PDF assembly."""

from __future__ import annotations

import base64
import time
from io import BytesIO
from pathlib import Path

import httpx2
import pytest
from pypdf import PdfReader, PdfWriter

from patent_client_agents.epo_ops import client as client_module
from patent_client_agents.epo_ops.client import EpoOpsClient, OpsForbiddenError
from patent_client_agents.epo_ops.pdf_pages import (
    ImagesPacer,
    LocalPageStore,
    PdfDownloadIncomplete,
    page_key,
    parse_throttle,
)

NUMBER = "WO2026024858A1"
LINK = "published-data/images/WO/2026024858/A1/fullimage"
GREEN = "idle (images=green:6000, inpadoc=green:60, other=green:1000)"


def _inquiry(pages: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data xmlns:ops="http://ops.epo.org">
  <ops:document-inquiry>
    <ops:inquiry-result>
      <ops:document-instance system="ops.epo.org" number-of-pages="{pages}"
          desc="FullDocument" link="{LINK}"/>
    </ops:inquiry-result>
  </ops:document-inquiry>
</ops:world-patent-data>"""


def _one_page_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


PAGE_PDF = _one_page_pdf()


class FakeOps:
    """Mock OPS: token, image inquiry, and page images with scripted failures."""

    def __init__(self, pages: int, page_responses: dict[int, list[httpx2.Response]] | None = None):
        self.pages = pages
        self.page_responses = page_responses or {}
        self.page_requests: list[int] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path.endswith("/auth/accesstoken"):
            return httpx2.Response(
                200,
                json={
                    "issued_at": str(int(time.time() * 1000)),
                    "expires_in": "1200",
                    "access_token": "token",
                },
            )
        if path.endswith("/images"):
            return httpx2.Response(
                200,
                text=_inquiry(self.pages),
                headers={"X-Throttling-Control": GREEN},
            )
        if path.endswith("/fullimage.pdf"):
            page = int(request.url.params["Range"])
            self.page_requests.append(page)
            scripted = self.page_responses.get(page)
            if scripted:
                return scripted.pop(0)
            return httpx2.Response(
                200,
                content=PAGE_PDF,
                headers={"Content-Type": "application/pdf", "X-Throttling-Control": GREEN},
            )
        raise AssertionError(f"unexpected request {request.url}")


@pytest.fixture
def fast_pacer(monkeypatch: pytest.MonkeyPatch) -> ImagesPacer:
    pacer = ImagesPacer(per_minute=60000)
    monkeypatch.setattr(client_module, "images_pacer", pacer)
    # A throttle block normally waits a minute; keep tests fast.
    monkeypatch.setattr(EpoOpsClient, "_retry_after_seconds", staticmethod(lambda r: 0.01))
    return pacer


def _client(fake: FakeOps, tmp_path: Path) -> EpoOpsClient:
    return EpoOpsClient(
        api_key="key",
        api_secret="secret",
        cache_path=tmp_path / "http",
        transport=httpx2.MockTransport(fake),
    )


def _throttled() -> httpx2.Response:
    return httpx2.Response(
        403,
        text="<fault/>",
        headers={
            "X-Rejection-Reason": "ThrottlingControlQuota",
            "X-Throttling-Control": "overloaded (images=black:0, other=green:1000)",
        },
    )


class TestParseThrottle:
    def test_reads_images_service(self) -> None:
        header = "busy (images=green:100, inpadoc=green:45, other=green:1000)"
        assert parse_throttle(header) == ("green", 100)

    def test_reads_black(self) -> None:
        assert parse_throttle("overloaded (images=black:0, other=green:1000)") == ("black", 0)

    def test_missing(self) -> None:
        assert parse_throttle(None) is None
        assert parse_throttle("idle (other=green:1000)") is None


class TestImagesPacer:
    def test_observe_sets_interval_from_rate(self) -> None:
        pacer = ImagesPacer()
        pacer.observe("busy (images=green:100)")
        assert pacer.interval == pytest.approx(0.6 * 1.1)

    def test_red_backs_off(self) -> None:
        pacer = ImagesPacer()
        pacer.observe("busy (images=red:100)")
        assert pacer.interval == pytest.approx(0.6 * 1.1 * 2)

    def test_black_blocks(self) -> None:
        pacer = ImagesPacer()
        pacer.observe("overloaded (images=black:0)")
        assert pacer.seconds_until_ready() > 50


@pytest.mark.asyncio
class TestDownloadPdf:
    async def test_assembles_all_pages_and_saves_them(
        self, tmp_path: Path, fast_pacer: ImagesPacer
    ) -> None:
        fake = FakeOps(pages=3)
        store = LocalPageStore(tmp_path / "pages")
        async with _client(fake, tmp_path) as client:
            result = await client.download_pdf(number=NUMBER, page_store=store)

        assert result.num_pages == 3
        assert len(PdfReader(BytesIO(base64.b64decode(result.pdf_base64))).pages) == 3
        assert fake.page_requests == [1, 2, 3]
        assert await store.get(page_key(NUMBER, 3)) == PAGE_PDF

    async def test_throttle_block_waits_and_retries_same_page(
        self, tmp_path: Path, fast_pacer: ImagesPacer
    ) -> None:
        fake = FakeOps(pages=3, page_responses={2: [_throttled()]})
        async with _client(fake, tmp_path) as client:
            result = await client.download_pdf(
                number=NUMBER, page_store=LocalPageStore(tmp_path / "pages")
            )

        assert result.num_pages == 3
        assert fake.page_requests == [1, 2, 2, 3]

    async def test_quota_403_is_not_retried(self, tmp_path: Path, fast_pacer: ImagesPacer) -> None:
        quota = httpx2.Response(
            403,
            text="<fault/>",
            headers={"X-Rejection-Reason": "IndividualQuotaPerHour"},
        )
        fake = FakeOps(pages=3, page_responses={1: [quota]})
        async with _client(fake, tmp_path) as client:
            with pytest.raises(OpsForbiddenError):
                await client.download_pdf(
                    number=NUMBER, page_store=LocalPageStore(tmp_path / "pages")
                )
        assert fake.page_requests == [1]

    async def test_budget_stops_early_and_next_call_resumes(
        self, tmp_path: Path, fast_pacer: ImagesPacer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = LocalPageStore(tmp_path / "pages")
        fake = FakeOps(pages=4)

        # A slow pacer: after page 1, the next slot is past the 0.5s budget.
        slow = ImagesPacer(per_minute=60)
        monkeypatch.setattr(slow, "observe", lambda header: None)  # ignore the mock's fast rate
        monkeypatch.setattr(client_module, "images_pacer", slow)
        async with _client(fake, tmp_path) as client:
            with pytest.raises(PdfDownloadIncomplete) as info:
                await client.download_pdf(number=NUMBER, page_store=store, time_budget=0.5)

        assert info.value.pages_fetched == 1
        assert info.value.total_pages == 4
        assert info.value.remaining_pages == 3
        assert fake.page_requests == [1]

        monkeypatch.setattr(client_module, "images_pacer", fast_pacer)
        async with _client(fake, tmp_path) as client:
            result = await client.download_pdf(number=NUMBER, page_store=store, time_budget=60)

        assert result.num_pages == 4
        # Page 1 came from the store, not OPS.
        assert fake.page_requests == [1, 2, 3, 4]

    async def test_throttle_block_past_deadline_reports_progress(
        self, tmp_path: Path, fast_pacer: ImagesPacer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(EpoOpsClient, "_retry_after_seconds", staticmethod(lambda r: 60.0))
        fake = FakeOps(pages=3, page_responses={2: [_throttled()]})
        async with _client(fake, tmp_path) as client:
            with pytest.raises(PdfDownloadIncomplete) as info:
                await client.download_pdf(
                    number=NUMBER,
                    page_store=LocalPageStore(tmp_path / "pages"),
                    time_budget=5,
                )
        assert info.value.pages_fetched == 1


@pytest.mark.asyncio
async def test_tool_returns_in_progress_instead_of_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from patent_client_agents.mcp.tools import patents

    async def incomplete(number: str):
        raise PdfDownloadIncomplete(
            "WO2026024858A1", pages_fetched=200, total_pages=824, seconds_per_page=1.2
        )

    monkeypatch.setattr(patents.unified, "download_patent_pdf_clean", incomplete)
    result = await patents.download_patent_pdf_clean("WO2026024858A1")

    assert result["status"] == "in_progress"
    assert result["pages_fetched"] == 200
    assert result["total_pages"] == 824
    assert result["estimated_seconds_remaining"] == int(624 * 1.2) + 1
    assert "call this tool again" in result["message"].lower()
