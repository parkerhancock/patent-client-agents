"""Tests for the download_file_history bulk tool."""

from __future__ import annotations

import asyncio
import zipfile
from contextlib import asynccontextmanager

import pytest

from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp import downloads
from patent_client_agents.mcp.tools import uspto as uspto_tools


def _doc(
    *,
    doc_id: str,
    code: str = "CTNF",
    date: str = "2024-01-15",
    description: str = "Non-Final Rejection",
    direction: str = "OUTGOING",
    page_count: int = 10,
):
    return {
        "documentIdentifier": doc_id,
        "documentCode": code,
        "officialDate": date,
        "documentCodeDescriptionText": description,
        "directionCategory": direction,
        "pageCount": page_count,
    }


class _FakeDocsResponse:
    def __init__(self, documents: list[dict]) -> None:
        self._documents = documents

    def model_dump(self) -> dict:
        return {"documents": self._documents}


class _FakeUsptoClient:
    """Minimal stand-in for UsptoOdpClient that returns canned documents.

    Only ``get_documents`` is used by ``download_file_history``; the
    actual byte fetch goes through the registered fetcher (mocked
    separately via ``register_source``).
    """

    def __init__(self, documents: list[dict]) -> None:
        self._documents = documents

    @asynccontextmanager
    async def _ctx(self):
        yield self

    async def __aenter__(self) -> _FakeUsptoClient:
        return self

    async def __aexit__(self, *_a) -> None:
        return None

    async def get_documents(self, _app_no: str) -> _FakeDocsResponse:
        return _FakeDocsResponse(self._documents)


@pytest.fixture
def _stdio_mode(monkeypatch):
    """Disable signed-URL mode so download_response writes tempfiles."""
    monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
    monkeypatch.delenv("LAW_TOOLS_PUBLIC_URL", raising=False)


@pytest.fixture
def _isolated_cache(monkeypatch, tmp_path):
    """Isolate the per-doc cache so tests don't pollute the real one."""
    monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))


@pytest.fixture(autouse=True)
def _reset_sources():
    """Source registry isolation — same pattern as the downloads tests."""
    saved = dict(downloads._SOURCES)
    downloads._SOURCES.clear()
    yield
    downloads._SOURCES.clear()
    downloads._SOURCES.update(saved)


@pytest.fixture(autouse=True)
def _enable_resource_links(monkeypatch):
    """These tests inspect the dual-transport manifest via
    ``structured_content``, which is gated behind
    ``LAW_TOOLS_CORE_RESOURCES_ENABLED`` (default off → text-only). Opt in so
    the structured payload is present. The text-only default is covered by
    mcp-data-core's download tests."""
    monkeypatch.setenv("LAW_TOOLS_CORE_RESOURCES_ENABLED", "1")


def _install_fake_fetcher(content_by_path: dict[str, bytes]) -> dict[str, int]:
    """Register a fake uspto/applications fetcher and return a call counter."""
    calls: dict[str, int] = {}

    async def fake_fetch(remainder: str) -> tuple[bytes, str]:
        calls[remainder] = calls.get(remainder, 0) + 1
        if remainder not in content_by_path:
            raise RuntimeError(f"no canned content for {remainder!r}")
        return content_by_path[remainder], f"raw_{remainder.replace('/', '_')}.pdf"

    downloads.register_source("uspto/applications", fake_fetch, "application/pdf")
    return calls


def _run(coro):
    """Run the coroutine and unwrap ``ToolResult.structured_content``.

    Bulk tools return ``ToolResult`` now (so resource-aware clients get
    a ``ResourceLink`` per item alongside the existing dict payload).
    These tests pre-date that switch and assert on the dict shape, so
    we unwrap here rather than rewrite every assertion.
    """
    result = asyncio.run(coro)
    if hasattr(result, "structured_content"):
        return result.structured_content
    return result


def _patch_client(monkeypatch, documents: list[dict]) -> None:
    monkeypatch.setattr(uspto_tools, "UsptoOdpClient", lambda: _FakeUsptoClient(documents))


class TestDownloadFileHistoryFiltering:
    def test_no_match_raises(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(monkeypatch, [_doc(doc_id="A", code="CTNF")])
        _install_fake_fetcher({})

        with pytest.raises(ValidationError, match="No file-history documents"):
            _run(uspto_tools.download_file_history("16123456", document_codes=["IDS"]))

    def test_cap_exceeded_raises(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        # 51 documents matches; cap is 50.
        docs = [_doc(doc_id=f"D{n}", date=f"2024-01-{(n % 28) + 1:02d}") for n in range(51)]
        _patch_client(monkeypatch, docs)
        _install_fake_fetcher({})

        with pytest.raises(ValidationError, match="max 50 per call"):
            _run(uspto_tools.download_file_history("16123456"))

    def test_item_ids_filter(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        docs = [_doc(doc_id=f"D{n}") for n in range(5)]
        _patch_client(monkeypatch, docs)
        _install_fake_fetcher(
            {
                "16123456/documents/D0": b"pdf-0",
                "16123456/documents/D2": b"pdf-2",
            }
        )

        result = _run(uspto_tools.download_file_history("16123456", item_ids=["D0", "D2"]))
        assert result["item_count"] == 2
        assert result["ok_count"] == 2
        ids = sorted(m["item_id"] for m in result["manifest"])
        assert ids == ["D0", "D2"]

    def test_document_codes_filter(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        docs = [
            _doc(doc_id="A", code="CTNF"),
            _doc(doc_id="B", code="REM"),
            _doc(doc_id="C", code="IDS"),
            _doc(doc_id="D", code="IDS"),
        ]
        _patch_client(monkeypatch, docs)
        _install_fake_fetcher(
            {
                "16123456/documents/A": b"pdf-A",
                "16123456/documents/C": b"pdf-C",
                "16123456/documents/D": b"pdf-D",
            }
        )
        result = _run(uspto_tools.download_file_history("16123456", document_codes=["CTNF", "IDS"]))
        ids = sorted(m["item_id"] for m in result["manifest"])
        assert ids == ["A", "C", "D"]

    def test_date_range_filter(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        docs = [
            _doc(doc_id="early", date="2023-12-01"),
            _doc(doc_id="mid1", date="2024-02-15"),
            _doc(doc_id="mid2", date="2024-02-20"),
            _doc(doc_id="late", date="2024-06-01"),
        ]
        _patch_client(monkeypatch, docs)
        _install_fake_fetcher(
            {
                "16123456/documents/mid1": b"pdf-mid1",
                "16123456/documents/mid2": b"pdf-mid2",
            }
        )

        result = _run(
            uspto_tools.download_file_history("16123456", after="2024-01-01", before="2024-03-01")
        )
        ids = sorted(m["item_id"] for m in result["manifest"])
        assert ids == ["mid1", "mid2"]

    def test_invalid_date_raises(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(monkeypatch, [_doc(doc_id="A")])
        _install_fake_fetcher({})

        with pytest.raises(ValidationError, match="ISO date YYYY-MM-DD"):
            _run(uspto_tools.download_file_history("16123456", after="not-a-date"))


class TestDownloadFileHistoryShape:
    def test_n1_short_circuits_to_raw_pdf(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        _patch_client(monkeypatch, [_doc(doc_id="OA1", code="CTNF", date="2024-01-15")])
        _install_fake_fetcher({"16123456/documents/OA1": b"pdf-bytes"})

        result = _run(uspto_tools.download_file_history("16123456"))
        assert "manifest" not in result  # n=1 short-circuit
        assert result["content_type"] == "application/pdf"
        assert result["filename"] == "16123456-CTNF-2024-01-15-OA1.pdf"
        assert result["application_number"] == "16123456"
        assert result["item_id"] == "OA1"
        assert result["document_code"] == "CTNF"
        # stdio mode: file_path instead of download_url
        assert "file_path" in result

    def test_n_many_returns_zip_with_manifest(
        self, _stdio_mode, _isolated_cache, monkeypatch
    ) -> None:
        docs = [
            _doc(doc_id="A", code="CTNF", date="2024-01-01"),
            _doc(doc_id="B", code="REM", date="2024-01-15"),
            _doc(doc_id="C", code="IDS", date="2024-02-01"),
        ]
        _patch_client(monkeypatch, docs)
        _install_fake_fetcher(
            {
                "16123456/documents/A": b"alpha",
                "16123456/documents/B": b"bravo",
                "16123456/documents/C": b"charlie",
            }
        )

        result = _run(uspto_tools.download_file_history("16123456"))
        assert result["content_type"] == "application/zip"
        assert result["item_count"] == 3
        assert result["ok_count"] == 3
        assert result["error_count"] == 0
        assert result["filename"] == "16123456_file_history.zip"
        assert result["application_number"] == "16123456"

        with zipfile.ZipFile(result["file_path"]) as zf:
            names = sorted(zf.namelist())
            assert names == [
                "A/16123456-CTNF-2024-01-01-A.pdf",
                "B/16123456-REM-2024-01-15-B.pdf",
                "C/16123456-IDS-2024-02-01-C.pdf",
            ]
            assert zf.read("A/16123456-CTNF-2024-01-01-A.pdf") == b"alpha"

    def test_partial_failure_in_zip(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        docs = [
            _doc(doc_id="ok1"),
            _doc(doc_id="bad"),
            _doc(doc_id="ok2"),
        ]
        _patch_client(monkeypatch, docs)
        # 'bad' is missing from the canned content → fetcher raises.
        _install_fake_fetcher(
            {
                "16123456/documents/ok1": b"one",
                "16123456/documents/ok2": b"two",
            }
        )

        result = _run(uspto_tools.download_file_history("16123456"))
        assert result["item_count"] == 3
        assert result["ok_count"] == 2
        assert result["error_count"] == 1
        bad = next(m for m in result["manifest"] if m["item_id"] == "bad")
        assert bad["status"] == "error"
        with zipfile.ZipFile(result["file_path"]) as zf:
            assert sorted(zf.namelist()) == [
                "ok1/16123456-CTNF-2024-01-15-ok1.pdf",
                "ok2/16123456-CTNF-2024-01-15-ok2.pdf",
            ]


class TestDownloadFileHistoryCacheReuse:
    def test_cache_reused_on_re_bulk(self, _stdio_mode, _isolated_cache, monkeypatch) -> None:
        docs = [_doc(doc_id="A"), _doc(doc_id="B")]
        _patch_client(monkeypatch, docs)
        calls = _install_fake_fetcher(
            {
                "16123456/documents/A": b"alpha",
                "16123456/documents/B": b"bravo",
            }
        )

        first = _run(uspto_tools.download_file_history("16123456"))
        assert first["ok_count"] == 2
        assert calls == {"16123456/documents/A": 1, "16123456/documents/B": 1}

        second = _run(uspto_tools.download_file_history("16123456"))
        assert second["ok_count"] == 2
        # Second call hit the per-doc cache for both docs — fetcher not re-called.
        assert calls == {"16123456/documents/A": 1, "16123456/documents/B": 1}
