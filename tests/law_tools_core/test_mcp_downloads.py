"""Tests for law_tools_core/mcp/downloads.py."""

from __future__ import annotations

import asyncio
import os
import time
import zipfile

import pytest

from law_tools_core.exceptions import BulkDownloadError
from law_tools_core.mcp import downloads
from law_tools_core.mcp.downloads import (
    BulkItem,
    _DeleteOnSuccess,
    download_bulk_response,
    fetch_with_cache,
    reap_stale_bulk_zips,
)


@pytest.fixture(autouse=True)
def _reset_sources():
    """Clear the source registry between tests so they don't leak state."""
    saved = dict(downloads._SOURCES)
    downloads._SOURCES.clear()
    yield
    downloads._SOURCES.clear()
    downloads._SOURCES.update(saved)


@pytest.fixture
def _signing_secret(monkeypatch):
    monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "test-secret")
    yield


class TestHmac:
    def test_sign_verify_roundtrip(self, _signing_secret) -> None:
        path = "patents/US10123456B2"
        assert downloads.verify_path(path, downloads.sign_path(path))

    def test_wrong_signature_rejected(self, _signing_secret) -> None:
        assert not downloads.verify_path("patents/X", "wrongsig")

    def test_no_secret_allows_all(self, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_API_KEY", raising=False)
        monkeypatch.delenv("LAW_TOOLS_API_KEY", raising=False)
        assert downloads.verify_path("anything", "bogus")

    def test_permanent_bucket(self, _signing_secret) -> None:
        path = "patents/X"
        sig = downloads.sign_path(path, bucket="permanent")
        assert downloads.verify_path(path, sig)

    def test_legacy_env_var_alias(self, monkeypatch) -> None:
        """Legacy LAW_TOOLS_API_KEY should still work."""
        monkeypatch.delenv("LAW_TOOLS_CORE_API_KEY", raising=False)
        monkeypatch.setenv("LAW_TOOLS_API_KEY", "legacy-secret")
        path = "patents/X"
        assert downloads.verify_path(path, downloads.sign_path(path))


class TestRegistry:
    def test_register_and_match(self) -> None:
        async def fetch(_remainder: str) -> tuple[bytes, str]:
            return b"", "f.pdf"

        downloads.register_source("patents", fetch)
        match = downloads._match_source("patents/US10123456B2")
        assert match is not None
        _, remainder = match
        assert remainder == "US10123456B2"

    def test_longest_prefix_wins(self) -> None:
        async def short(_: str) -> tuple[bytes, str]:
            return b"short", "s.pdf"

        async def long(_: str) -> tuple[bytes, str]:
            return b"long", "l.pdf"

        downloads.register_source("uspto", short)
        downloads.register_source("uspto/applications", long)

        match = downloads._match_source("uspto/applications/16123456/x")
        assert match is not None
        source, _ = match
        assert source.fetch is long

    def test_unknown_path_returns_none(self) -> None:
        assert downloads._match_source("unknown/path") is None


class TestBuildDownloadUrl:
    def test_local_mode_returns_stub(self, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.delenv("LAW_TOOLS_PUBLIC_URL", raising=False)
        result = downloads.build_download_url("patents/X")
        assert "local mode" in result.lower()

    def test_remote_mode_signs_url(self, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://mcp.example.com")
        url = downloads.build_download_url("patents/X")
        assert url.startswith("https://mcp.example.com/downloads/patents/X?key=")

    def test_label_prepended(self, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://mcp.example.com")
        out = downloads.build_download_url("patents/X", label="Patent PDF")
        assert out.startswith("Patent PDF\n\nDownload:")


class TestDownloadResponse:
    async def test_local_mode_writes_tempfile(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.delenv("LAW_TOOLS_PUBLIC_URL", raising=False)
        payload = await downloads.download_response(
            "patents/X",
            b"bytes",
            filename="X.pdf",
            content_type="application/pdf",
        )
        assert "file_path" in payload
        assert os.path.exists(payload["file_path"])
        assert payload["size_bytes"] == 5
        assert payload["filename"] == "X.pdf"

    async def test_remote_mode_returns_signed_url_and_expires_at(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://mcp.example.com")
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path))
        payload = await downloads.download_response(
            "patents/X",
            b"bytes",
            filename="X.pdf",
        )
        assert payload["download_url"].startswith("https://mcp.example.com/")
        assert "expires_at" in payload
        assert "Z" in payload["expires_at"]

    async def test_permanent_url_omits_expires_at(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://mcp.example.com")
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path))
        payload = await downloads.download_response(
            "patents/X",
            b"bytes",
            filename="X.pdf",
            permanent=True,
        )
        assert "expires_at" not in payload


class TestFetchWithCache:
    def test_cache_miss_invokes_fetcher_and_writes_cache(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        calls = {"n": 0}

        async def fetcher(remainder: str) -> tuple[bytes, str]:
            calls["n"] += 1
            return f"content-for-{remainder}".encode(), f"{remainder}.pdf"

        downloads.register_source("src", fetcher)

        content, filename = asyncio.run(fetch_with_cache("src/X"))
        assert content == b"content-for-X"
        assert filename == "X.pdf"
        assert calls["n"] == 1

        # Second call hits the cache.
        content2, filename2 = asyncio.run(fetch_with_cache("src/X"))
        assert content2 == b"content-for-X"
        assert filename2 == "X.pdf"
        assert calls["n"] == 1

    def test_unknown_source_raises(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        with pytest.raises(ValueError, match="No registered fetcher"):
            asyncio.run(fetch_with_cache("nope/X"))


def _make_fetcher(payloads: dict[str, tuple[bytes, str] | Exception]):
    """Build a mock fetcher that returns canned bytes/filename or raises."""

    async def fetcher(item: BulkItem) -> tuple[bytes, str]:
        result = payloads[item.item_id]
        if isinstance(result, Exception):
            raise result
        return result

    return fetcher


class TestDownloadBulkResponse:
    def test_empty_items_raises(self) -> None:
        async def fetcher(_: BulkItem) -> tuple[bytes, str]:
            raise AssertionError("not called")

        with pytest.raises(BulkDownloadError, match="no items"):
            asyncio.run(download_bulk_response([], fetcher, container_label="empty"))

    def test_n1_short_circuits_to_download_response(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.delenv("LAW_TOOLS_PUBLIC_URL", raising=False)
        item = BulkItem(
            item_id="OA_20231201",
            resource_path="uspto/file-history/16123456/items/OA_20231201",
            metadata={"document_code": "CTNF"},
        )
        fetcher = _make_fetcher({"OA_20231201": (b"pdf-bytes", "non-final.pdf")})
        payload = asyncio.run(
            download_bulk_response(
                [item],
                fetcher,
                container_label="16123456_file_history",
                container_metadata={"container": "16123456"},
            )
        )
        # n=1 returns the standard download_response shape — no manifest, raw file.
        assert "manifest" not in payload
        assert payload["filename"] == "non-final.pdf"
        assert payload["content_type"] == "application/pdf"
        assert payload["size_bytes"] == len(b"pdf-bytes")
        assert payload["item_id"] == "OA_20231201"
        assert payload["container"] == "16123456"
        assert payload["document_code"] == "CTNF"
        # Local mode: file_path, no download_url.
        assert "file_path" in payload
        assert os.path.exists(payload["file_path"])

    def test_n_many_local_mode_returns_zip_tempfile(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.delenv("LAW_TOOLS_PUBLIC_URL", raising=False)
        items = [
            BulkItem("A", "src/A", {"order": 1}),
            BulkItem("B", "src/B", {"order": 2}),
            BulkItem("C", "src/C", {"order": 3}),
        ]
        fetcher = _make_fetcher(
            {
                "A": (b"alpha", "a.pdf"),
                "B": (b"bravo-bytes", "b.pdf"),
                "C": (b"charlie-content", "c.pdf"),
            }
        )
        payload = asyncio.run(download_bulk_response(items, fetcher, container_label="abc_bundle"))
        assert payload["content_type"] == "application/zip"
        assert payload["filename"] == "abc_bundle.zip"
        assert payload["item_count"] == 3
        assert payload["ok_count"] == 3
        assert payload["error_count"] == 0
        assert "file_path" in payload
        # Verify zip layout: {item_id}/{filename}.
        with zipfile.ZipFile(payload["file_path"]) as zf:
            names = sorted(zf.namelist())
            assert names == ["A/a.pdf", "B/b.pdf", "C/c.pdf"]
            assert zf.read("B/b.pdf") == b"bravo-bytes"

    def test_partial_failure_keeps_successes(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        items = [
            BulkItem("ok1", "src/ok1", {}),
            BulkItem("bad", "src/bad", {}),
            BulkItem("ok2", "src/ok2", {}),
        ]
        fetcher = _make_fetcher(
            {
                "ok1": (b"one", "1.pdf"),
                "bad": RuntimeError("404: gone"),
                "ok2": (b"two", "2.pdf"),
            }
        )
        payload = asyncio.run(download_bulk_response(items, fetcher, container_label="mixed"))
        assert payload["item_count"] == 3
        assert payload["ok_count"] == 2
        assert payload["error_count"] == 1
        # Manifest preserves input order.
        ids = [m["item_id"] for m in payload["manifest"]]
        assert ids == ["ok1", "bad", "ok2"]
        bad_entry = payload["manifest"][1]
        assert bad_entry["status"] == "error"
        assert "404: gone" in bad_entry["error"]
        # Successful entries carry their filename + size.
        assert payload["manifest"][0]["filename"] == "ok1/1.pdf"
        assert payload["manifest"][0]["size_bytes"] == 3
        # Zip contains only the successes.
        with zipfile.ZipFile(payload["file_path"]) as zf:
            assert sorted(zf.namelist()) == ["ok1/1.pdf", "ok2/2.pdf"]

    def test_all_fail_raises(self) -> None:
        items = [
            BulkItem("a", "src/a", {}),
            BulkItem("b", "src/b", {}),
        ]
        fetcher = _make_fetcher(
            {
                "a": RuntimeError("first error"),
                "b": RuntimeError("second error"),
            }
        )
        with pytest.raises(BulkDownloadError, match="All 2 items failed"):
            asyncio.run(download_bulk_response(items, fetcher, container_label="doomed"))

    def test_remote_mode_writes_to_bulk_zips_dir(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://mcp.example.com")
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        items = [
            BulkItem("a", "src/a", {}),
            BulkItem("b", "src/b", {}),
        ]
        fetcher = _make_fetcher(
            {
                "a": (b"one", "1.pdf"),
                "b": (b"two", "2.pdf"),
            }
        )
        payload = asyncio.run(download_bulk_response(items, fetcher, container_label="bundle"))
        assert payload["download_url"].startswith("https://mcp.example.com/downloads/bulk_zips/")
        assert "expires_at" in payload
        # Bulk zip lives in cache_parent/bulk_zips, not in cache itself.
        bulk_dir = tmp_path / "bulk_zips"
        assert bulk_dir.exists()
        zips = list(bulk_dir.glob("*.zip"))
        assert len(zips) == 1
        assert zips[0].with_suffix(".name").read_text() == "bundle.zip"

    def test_concurrency_is_bounded(self, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        in_flight = 0
        peak = 0
        lock = asyncio.Lock()

        async def slow_fetcher(item: BulkItem) -> tuple[bytes, str]:
            nonlocal in_flight, peak
            async with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            async with lock:
                in_flight -= 1
            return item.item_id.encode(), f"{item.item_id}.pdf"

        items = [BulkItem(f"i{n}", f"src/i{n}", {}) for n in range(20)]
        asyncio.run(
            download_bulk_response(items, slow_fetcher, container_label="bundle", max_concurrency=3)
        )
        assert peak <= 3, f"expected peak ≤ 3, got {peak}"


class TestDeleteOnSuccess:
    def test_deletes_after_full_read(self, tmp_path) -> None:
        target = tmp_path / "x.zip"
        target.write_bytes(b"hello world")
        target.with_suffix(".name").write_text("display.zip")

        async def consume() -> bytes:
            stream = _DeleteOnSuccess(target, expected_size=11, chunk_size=4)
            return b"".join([chunk async for chunk in stream])

        body = asyncio.run(consume())
        assert body == b"hello world"
        assert not target.exists()
        assert not target.with_suffix(".name").exists()

    def test_partial_read_leaves_file(self, tmp_path) -> None:
        target = tmp_path / "x.zip"
        target.write_bytes(b"hello world")

        async def partial() -> None:
            stream = _DeleteOnSuccess(target, expected_size=11, chunk_size=4)
            it = stream.__aiter__()
            await it.__anext__()  # only read the first chunk
            await it.aclose()

        asyncio.run(partial())
        # Aborted read → file stays for retry.
        assert target.exists()


class TestReapStaleBulkZips:
    def test_removes_old_files(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        bulk_dir = tmp_path / "bulk_zips"
        bulk_dir.mkdir()
        old = bulk_dir / "old.zip"
        new = bulk_dir / "new.zip"
        old.write_bytes(b"stale")
        new.write_bytes(b"fresh")
        # Backdate the old file by 2 hours.
        two_hours_ago = time.time() - 7200
        os.utime(old, (two_hours_ago, two_hours_ago))

        deleted = reap_stale_bulk_zips()
        assert deleted == 1
        assert not old.exists()
        assert new.exists()

    def test_no_dir_returns_zero(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "nonexistent" / "cache"))
        assert reap_stale_bulk_zips() == 0


def _build_app():
    """Mount handle_download into a tiny Starlette app for TestClient use."""
    from starlette.applications import Starlette
    from starlette.routing import Route

    return Starlette(routes=[Route("/downloads/{path:path}", downloads.handle_download)])


class TestHandleDownloadBulkZip:
    def test_serves_and_deletes_on_success(self, tmp_path, monkeypatch) -> None:
        from starlette.testclient import TestClient

        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))

        bulk_dir = tmp_path / "bulk_zips"
        bulk_dir.mkdir()
        zip_path = bulk_dir / "abc123.zip"
        zip_path.write_bytes(b"zip-bytes-payload")
        zip_path.with_suffix(".name").write_text("my_bundle.zip")

        sig = downloads.sign_path("bulk_zips/abc123")
        client = TestClient(_build_app())
        resp = client.get(f"/downloads/bulk_zips/abc123?key={sig}")

        assert resp.status_code == 200
        assert resp.content == b"zip-bytes-payload"
        assert "my_bundle.zip" in resp.headers["Content-Disposition"]
        assert resp.headers["Content-Length"] == str(len(b"zip-bytes-payload"))
        # File deleted after successful streaming.
        assert not zip_path.exists()
        assert not zip_path.with_suffix(".name").exists()

    def test_missing_zip_returns_404(self, tmp_path, monkeypatch) -> None:
        from starlette.testclient import TestClient

        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        # Don't create the file. HMAC still has to verify.
        sig = downloads.sign_path("bulk_zips/missing")
        client = TestClient(_build_app())
        resp = client.get(f"/downloads/bulk_zips/missing?key={sig}")

        assert resp.status_code == 404
        assert "no longer available" in resp.text
        assert "Re-call the bulk tool" in resp.text

    def test_nested_bulk_path_rejected(self, tmp_path, monkeypatch) -> None:
        from starlette.testclient import TestClient

        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        sig = downloads.sign_path("bulk_zips/abc/extra")
        client = TestClient(_build_app())
        resp = client.get(f"/downloads/bulk_zips/abc/extra?key={sig}")

        assert resp.status_code == 400
        assert "Invalid bulk-zip path" in resp.text

    def test_bad_signature_rejected_for_bulk(self, tmp_path, monkeypatch) -> None:
        from starlette.testclient import TestClient

        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        bulk_dir = tmp_path / "bulk_zips"
        bulk_dir.mkdir()
        (bulk_dir / "abc123.zip").write_bytes(b"x")

        client = TestClient(_build_app())
        resp = client.get("/downloads/bulk_zips/abc123?key=wrong")

        assert resp.status_code == 403
        # File survives: bad-sig request never opens it.
        assert (bulk_dir / "abc123.zip").exists()


class TestResourceUri:
    def test_build_resource_uri_strips_slashes(self) -> None:
        assert (
            downloads.build_resource_uri("/uspto/applications/16/documents/X/")
            == "pca://uspto/applications/16/documents/X"
        )

    async def test_download_response_includes_resource_uri_local(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.delenv("LAW_TOOLS_PUBLIC_URL", raising=False)
        payload = await downloads.download_response(
            "patents/X", b"bytes", filename="X.pdf", content_type="application/pdf"
        )
        # resource_uri is always emitted — independent of PUBLIC_URL —
        # so MCP resources/read works in stdio mode too.
        assert payload["resource_uri"] == "pca://patents/X"
        assert "file_path" in payload

    async def test_download_response_includes_resource_uri_remote(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_API_KEY", "secret")
        monkeypatch.setenv("LAW_TOOLS_CORE_PUBLIC_URL", "https://mcp.example.com")
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path))
        payload = await downloads.download_response("patents/X", b"bytes", filename="X.pdf")
        assert payload["resource_uri"] == "pca://patents/X"
        assert payload["download_url"].startswith("https://mcp.example.com/")


class TestDownloadToolResult:
    async def test_returns_tool_result_with_resource_link(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        result = await downloads.download_tool_result(
            "patents/US10000000B2",
            b"%PDF-1.4 hi",
            filename="US10000000B2.pdf",
            content_type="application/pdf",
        )
        # ToolResult — exposes structured_content and content blocks.
        assert hasattr(result, "structured_content")
        assert result.structured_content["resource_uri"] == "pca://patents/US10000000B2"
        assert result.structured_content["filename"] == "US10000000B2.pdf"
        # Exactly one ResourceLink content block.
        links = [c for c in (result.content or []) if c.type == "resource_link"]
        assert len(links) == 1
        link = links[0]
        assert str(link.uri) == "pca://patents/US10000000B2"
        assert link.name == "US10000000B2.pdf"
        assert link.mimeType == "application/pdf"
        # Size populated so clients can decide whether to attempt resources/read.
        assert link.size == len(b"%PDF-1.4 hi")

    async def test_extras_land_in_structured_content(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        result = await downloads.download_tool_result(
            "patents/US1",
            b"x",
            filename="US1.pdf",
            content_type="application/pdf",
            source="google_patents",
            patent_number="US1",
        )
        assert result.structured_content["source"] == "google_patents"
        assert result.structured_content["patent_number"] == "US1"


class TestReadResource:
    def test_reads_through_cache(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        calls = {"n": 0}

        async def fetcher(remainder: str) -> tuple[bytes, str]:
            calls["n"] += 1
            return f"data-{remainder}".encode(), f"{remainder}.pdf"

        downloads.register_source("foo", fetcher, "application/pdf")
        contents = asyncio.run(downloads.read_resource("foo/X"))
        assert len(contents) == 1
        assert contents[0].content == b"data-X"
        assert contents[0].mime_type == "application/pdf"
        # Second call is a cache hit — fetcher not re-invoked.
        contents2 = asyncio.run(downloads.read_resource("foo/X"))
        assert contents2[0].content == b"data-X"
        assert calls["n"] == 1

    def test_bulk_zips_refused(self) -> None:
        with pytest.raises(ValueError, match="HTTP-only"):
            asyncio.run(downloads.read_resource("bulk_zips/abc123"))


class TestDownloadBulkToolResult:
    def test_n1_short_circuits_to_single_resource_link(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))

        async def fetcher(item: BulkItem) -> tuple[bytes, str]:
            return b"only", "only.pdf"

        item = BulkItem("only-id", "patents/US1", {})
        result = asyncio.run(
            downloads.download_bulk_tool_result([item], fetcher, container_label="solo")
        )
        assert "manifest" not in result.structured_content
        assert result.structured_content["resource_uri"] == "pca://patents/US1"
        links = [c for c in (result.content or []) if c.type == "resource_link"]
        assert len(links) == 1
        assert str(links[0].uri) == "pca://patents/US1"

    def test_n_many_returns_per_item_links(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))

        # Register a source so the manifest entries get resource_uri.
        async def fetcher_for_registry(_remainder: str) -> tuple[bytes, str]:
            return b"x", "x.pdf"

        downloads.register_source("patents", fetcher_for_registry, "application/pdf")

        async def fetcher(item: BulkItem) -> tuple[bytes, str]:
            return item.item_id.encode(), f"{item.item_id}.pdf"

        items = [
            BulkItem("A", "patents/USA", {}),
            BulkItem("B", "patents/USB", {}),
        ]
        result = asyncio.run(
            downloads.download_bulk_tool_result(items, fetcher, container_label="bundle")
        )
        manifest = result.structured_content["manifest"]
        assert [m["item_id"] for m in manifest] == ["A", "B"]
        # Each manifest entry carries a resource_uri pointing at the per-doc URI.
        assert manifest[0]["resource_uri"] == "pca://patents/USA"
        assert manifest[1]["resource_uri"] == "pca://patents/USB"
        # Container also has the zip download_url stub (local mode: file_path).
        assert "file_path" in result.structured_content
        # One ResourceLink per ok item.
        links = [c for c in (result.content or []) if c.type == "resource_link"]
        uris = sorted(str(link.uri) for link in links)
        assert uris == ["pca://patents/USA", "pca://patents/USB"]

    def test_unregistered_path_omits_resource_uri(self, tmp_path, monkeypatch) -> None:
        """Bulk paths that don't map to a registered source must not
        surface dangling resource URIs — resources/read would have no
        fetcher to call."""
        monkeypatch.delenv("LAW_TOOLS_CORE_PUBLIC_URL", raising=False)
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))

        async def fetcher(item: BulkItem) -> tuple[bytes, str]:
            return item.item_id.encode(), f"{item.item_id}.pdf"

        items = [
            BulkItem("X", "ptab/trial-decisions/X", {}),
            BulkItem("Y", "ptab/trial-decisions/Y", {}),
        ]
        result = asyncio.run(
            downloads.download_bulk_tool_result(items, fetcher, container_label="bundle")
        )
        for entry in result.structured_content["manifest"]:
            assert "resource_uri" not in entry
        # No ResourceLink blocks emitted for unregistered paths.
        links = [c for c in (result.content or []) if c.type == "resource_link"]
        assert links == []


class TestSweeperThrottle:
    def test_throttled_within_interval(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        # Force the sweeper to have just run.
        monkeypatch.setattr(downloads, "_last_bulk_zip_reap", time.time())
        calls = {"n": 0}

        def fake_reap(**_kw) -> int:
            calls["n"] += 1
            return 0

        monkeypatch.setattr(downloads, "reap_stale_bulk_zips", fake_reap)
        downloads._maybe_reap_bulk_zips()
        assert calls["n"] == 0

    def test_runs_after_interval(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("LAW_TOOLS_CORE_DOWNLOAD_CACHE", str(tmp_path / "cache"))
        # Force the sweeper to have last run an hour ago.
        monkeypatch.setattr(downloads, "_last_bulk_zip_reap", time.time() - 3600)
        calls = {"n": 0}

        def fake_reap(**_kw) -> int:
            calls["n"] += 1
            return 0

        monkeypatch.setattr(downloads, "reap_stale_bulk_zips", fake_reap)
        downloads._maybe_reap_bulk_zips()
        assert calls["n"] == 1
